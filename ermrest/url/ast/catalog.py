
# 
# Copyright 2010-2023 University of Southern California
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""ERMREST URL abstract syntax tree (AST) classes for catalog resources.
"""

import json
import psycopg2.extensions
import base64
import hashlib
import flask
from webauthn2.util import deriva_ctx, deriva_debug, negotiated_content_type

from . import model, data, resolver
from .api import ApiBase, Api
from ... import exception, catalog, sanepg2
from ...exception import *
from ...model import current_catalog_snaptime
from ...util import sql_literal, service_features, __version__

_application_json = 'application/json'
_text_plain = 'text/plain'

class Service (object):
    """The top-level service advertisement."""

    default_content_type = _application_json
    supported_types = [default_content_type,]

    def GET(self, uri=''):
        """Perform HTTP GET of service advertisement
        """
        # content negotiation
        content_type = negotiated_content_type(flask.request.environ, self.supported_types, self.default_content_type)

        try:
            status = deriva_ctx.ermrest_registry.healthcheck()
            response = {
                "version": __version__,
                "features": service_features(),
            }
        except Exception as e:
            deriva_debug(e)
            raise rest.ServiceUnavailable('Registry health-check failed.')

        deriva_ctx.deriva_response.content_type = content_type
        deriva_ctx.deriva_response.status_code = 200

        assert content_type == _application_json
        deriva_ctx.deriva_response.response = [ json.dumps(response) + '\n', ]
        return deriva_ctx.deriva_response

    def with_queryopts(self, qopt):
        # stub to satisfy ermrest.url.ast.api.Api interface
        return self

    def final(self):
        # stub to satisfy ermrest.url.ast.api.Api interface
        pass

class Catalogs (object):
    """A multi-tenant catalog set."""

    default_content_type = _application_json
    supported_types = [default_content_type, _text_plain]

    def POST(self, uri='catalog'):
        """Perform HTTP POST of catalogs.
        """
        # content negotiation
        content_type = negotiated_content_type(flask.request.environ, self.supported_types, self.default_content_type)

        # registry acl enforcement
        allowed = deriva_ctx.ermrest_registry.can_create(deriva_ctx.webauthn2_context.attributes)
        if not allowed:
            raise rest.Forbidden(uri)

        # optional input
        docstr = flask.request.stream.read().decode().strip()
        if docstr:
            try:
                doc = json.loads(docstr)
            except:
                raise exception.rest.BadRequest('Could not deserialize JSON input.')
        else:
            doc = {}

        owner = doc.get('owner')
        annotations = doc.get('annotations')

        # create the catalog instance
        catalog_id = deriva_ctx.ermrest_registry.claim_id(id=doc.get('id'), id_owner=owner)
        catalog = deriva_ctx.ermrest_catalog_factory.create(catalog_id)

        # initialize the catalog instance
        pc = sanepg2.PooledConnection(catalog.dsn)
        try:
            pc.perform(lambda conn, cur: catalog.init_meta(conn, cur, owner=owner, annotations=annotations))
        finally:
            pc.final()

        # register the catalog descriptor
        entry = deriva_ctx.ermrest_registry.register(catalog_id, descriptor=catalog.descriptor)

        deriva_ctx.deriva_response.content_type = content_type
        deriva_ctx.ermrest_request_content_type = content_type

        # set location header and status
        location = '/ermrest/catalog/%s' % catalog_id
        deriva_ctx.deriva_response.location = location
        deriva_ctx.deriva_response.status_code = 201

        if content_type == _text_plain:
            deriva_ctx.deriva_response.response = [ str(catalog_id), ]
        else:
            assert content_type == _application_json
            deriva_ctx.deriva_response.response = [ json.dumps({"id": catalog_id}), ]

        return deriva_ctx.deriva_response

class CatalogAliases (object):
    """A multi-tenant catalog alias set."""

    default_content_type = _application_json
    supported_types = [default_content_type, _text_plain]

    def POST(self, uri='catalog'):
        """Perform HTTP POST of catalog aliases.
        """
        # content negotiation
        content_type = negotiated_content_type(flask.request.environ, self.supported_types, self.default_content_type)

        # registry acl enforcement
        allowed = deriva_ctx.ermrest_registry.can_create(deriva_ctx.webauthn2_context.attributes)
        if not allowed:
            raise rest.Forbidden(uri)

        # optional input
        docstr = flask.request.stream.read().decode().strip()
        if docstr:
            try:
                doc = json.loads(docstr)
            except:
                raise exception.rest.BadRequest('Could not deserialize JSON input.')
        else:
            doc = {}

        # create the alias entry
        catalog_id = deriva_ctx.ermrest_registry.claim_id(id=doc.get('id'), id_owner=doc.get('owner'))

        # register the catalog descriptor
        entry = deriva_ctx.ermrest_registry.register(catalog_id, alias_target=doc.get('alias_target'))

        location = '/ermrest/catalog/%s' % catalog_id
        deriva_ctx.deriva_response.content_type = content_type
        deriva_ctx.deriva_response.location = location
        deriva_ctx.deriva_response.status_code = 201

        if content_type == _text_plain:
            deriva_ctx.deriva_response.response = [ str(catalog_id), ]
        else:
            assert content_type == _application_json
            deriva_ctx.deriva_response.response = [ json.dumps({"id": catalog_id}), ]

        return deriva_ctx.deriva_response

def _acls_to_meta(acls):
    meta_keys = {
        "owner": "owner",
        "read_user": "enumerate",
        "content_read_user": "select",
        "content_write_user": "write",
        "schema_write_user": 'create',
        "write_user": False,
    }
    return dict([
        (metakey, acls[aclname] or [])
        for metakey, aclname in meta_keys.items()
        if aclname
    ] + [
        (metakey, [])
        for metakey, aclname in meta_keys.items()
        if not aclname
    ])

class Catalog (Api):

    default_content_type = _application_json
    supported_types = [default_content_type]

    """A specific catalog by ID."""
    def __init__(self, catalog_id):
        self.catalog_id = catalog_id
        self.manager = None
        entries = deriva_ctx.ermrest_registry.lookup(catalog_id)
        if not entries:
            raise exception.rest.NotFound('catalog ' + str(catalog_id))
        entry = entries[0]
        self.manager = catalog.Catalog(
            deriva_ctx.ermrest_catalog_factory,
            reg_entry=entry,
            config=deriva_ctx.ermrest_config,
        )
        
        assert deriva_ctx.ermrest_catalog_pc is None
        deriva_ctx.ermrest_catalog_pc = sanepg2.PooledConnection(self.manager.dsn)

        Api.__init__(self, self)
        # now enforce read permission
        self.enforce_right('enumerate', 'catalog/' + str(self.catalog_id))

    def final(self):
        deriva_ctx.ermrest_catalog_pc.final()

    def acls(self):
        return model.CatalogAcl(self)

    def annotations(self):
        return model.CatalogAnnotations(self)

    def schemas(self):
        """The schema set for this catalog."""
        return model.Schemas(self)

    def schema(self, name):
        """A specific schema for this catalog."""
        return model.Schema(self, name)

    def meta(self, key=None, value=None):
        """A metadata set for this catalog."""
        return Meta(self, key, value)

    def textfacet(self, filterelem):
        """A textfacet set for this catalog."""
        return data.TextFacet(self, filterelem)
    
    def entity(self, elem):
        """An entity set for this catalog."""
        return data.Entity(self, elem)

    def attribute(self, apath):
        """An attribute set for this catalog."""
        return data.Attribute(self, apath)

    def attributegroup(self, agpath):
        """An attributegroup set for this catalog."""
        return data.AttributeGroup(self, agpath)

    def aggregate(self, agpath):
        """An aggregate row for this catalog."""
        return data.Aggregate(self, agpath)

    def query(self, qpath):
        """A query set for this catalog."""
        return data.Query(self, qpath)

    def entity_rid(self, rid):
        """An entity_rid resolver query."""
        return resolver.EntityRidResolver(self, rid)

    def GET_body(self, conn, cur):
        _model = deriva_ctx.ermrest_catalog_model
        if deriva_ctx.ermrest_history_snaptime is not None:
            cur.execute("SELECT _ermrest.tstzencode(%s::timestamptz);" % sql_literal(deriva_ctx.ermrest_history_snaptime))
            self.catalog_snaptime = cur.fetchone()[0]
            cur.execute("SELECT _ermrest.tstzencode(%s::timestamptz);" % sql_literal(deriva_ctx.ermrest_history_amendver))
            self.catalog_amendver = cur.fetchone()[0]
        else:
            self.catalog_snaptime = current_catalog_snaptime(cur, encode=True)
            self.catalog_amendver = None
        return _model

    def GET(self, uri):
        """Perform HTTP GET of catalog.
        """
        # content negotiation
        content_type = negotiated_content_type(flask.request.environ, self.supported_types, self.default_content_type)
        deriva_ctx.ermrest_request_content_type = content_type
        
        def post_commit(_model):
            # note that the 'descriptor' includes private system information such 
            # as the dbname (and potentially connection credentials) which should
            # not ever be shared.
            resource = _model.prejson(brief=True, snaptime=self.catalog_snaptime)
            resource["id"] = self.catalog_id
            if self.manager.alias_target is not None:
                resource["alias_target"] = self.manager.alias_target
            if self.catalog_amendver:
                self.set_http_etag( '%s-%s' % (self.catalog_snaptime, self.catalog_amendver) )
            else:
                self.set_http_etag( self.catalog_snaptime )
            self.http_check_preconditions()
            self.emit_headers()
            deriva_ctx.deriva_response.content_type = content_type
            deriva_ctx.deriva_response.response = [ json.dumps(resource) + '\n', ]
            return deriva_ctx.deriva_response

        return self.perform(self.GET_body, post_commit)
    
    def DELETE(self, uri):
        """Perform HTTP DELETE of catalog.
        """
        def body(conn, cur):
            self.enforce_right('owner', uri)
            if deriva_ctx.ermrest_history_snaptime is not None:
                raise exception.Forbidden('deletion of catalog at previous revision')
            if deriva_ctx.ermrest_history_snaprange is not None:
                # should not be possible bug check anyway...
                raise NotImplementedError('deletion of catalog with snapshot range')
            self.set_http_etag( deriva_ctx.ermrest_catalog_model.etag() )
            self.http_check_preconditions(method='DELETE')
            self.emit_headers()
            return True

        def post_commit(destroy):
            deriva_ctx.ermrest_registry.unregister(self.catalog_id)
            deriva_ctx.deriva_response.status_code = 204
            deriva_ctx.deriva_response.response = []
            return deriva_ctx.deriva_response

        return self.perform(body, post_commit)

    def POST(self, uri):
        """Perform maintenance tasks on catalog.
        """
        def body(conn, cur):
            self.enforce_right('owner', uri)
            if deriva_ctx.ermrest_history_snaptime is not None:
                raise exception.Forbidden('maintenance of catalog at previous revision')
            if deriva_ctx.ermrest_history_snaprange is not None:
                # should not be possible bug check anyway...
                raise NotImplementedError('maintenance of catalog with snapshot range')
            self.set_http_etag( deriva_ctx.ermrest_catalog_model.etag() )
            self.http_check_preconditions(method='GET')
            self.emit_headers()
            return True

        def post_commit(ignore):
            if 'vacuum' in self.queryopts:
                deriva_ctx.ermrest_catalog_pc.conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                deriva_ctx.ermrest_catalog_pc.cur.execute('VACUUM ANALYZE;')
                deriva_ctx.ermrest_catalog_pc.conn.commit()
                deriva_ctx.ermrest_catalog_pc.conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
            elif 'analyze' in self.queryopts:
                deriva_ctx.ermrest_catalog_pc.cur.execute('ANALYZE;')
                deriva_ctx.ermrest_catalog_pc.conn.commit()
            else:
                raise exception.BadData('Maintenance query parameters not recognized.')
            deriva_ctx.deriva_response.status_code = 204
            deriva_ctx.deriva_response.response = []
            return deriva_ctx.deriva_response

        return self.perform(body, post_commit)

class CatalogAlias (ApiBase):

    default_content_type = _application_json
    supported_types = [default_content_type]

    """A specific catalog by ID."""
    def _prepare(self, catalog_id, missing_ok=False):
        super(CatalogAlias, self)._prepare()

        self.catalog_id = catalog_id
        entries = deriva_ctx.ermrest_registry.lookup(catalog_id, dangling=True)
        if not entries:
            if missing_ok:
                self.entry = None
                self.set_http_etag('None')
                return
            raise exception.rest.NotFound('alias/%s' % (catalog_id,))
        self.entry = entries[0]
        if self.entry['descriptor'] is not None and self.entry['alias_target'] is None:
            # regular catalog entry is not an alias
            raise exception.rest.NotFound('alias/%s' % (catalog_id,))

        # now enforce read permission
        self.enforce_right('enumerate')
        self.set_http_etag()

    def set_http_etag(self, version=None):
        if version is None:
            normalized = [
                self.entry['id'],
                self.entry['id_owner'],
                self.entry['alias_target'],
            ]
            version = base64.urlsafe_b64encode(hashlib.md5(json.dumps(normalized).encode('utf8')).digest()).decode()
        super(CatalogAlias, self).set_http_etag(version)

    @property
    def id_owner(self):
        if isinstance(self.entry['id_owner'], list):
            return self.entry['id_owner']
        else:
            return []

    def enforce_right(self, acl):
        if set(self.id_owner).isdisjoint(deriva_ctx.webauthn2_context.attribute_ids):
            raise exception.Forbidden('%s access to alias/%s' % (acl, self.catalog_id))

    def final(self):
        pass

    def prejson(self):
        return {
            'id': self.entry['id'],
            'owner': self.entry['id_owner'],
            'alias_target': self.entry['alias_target'],
        }

    def GET(self, catalog_id):
        """Perform HTTP retrieval of catalog alias registry entry
        """
        self._prepare(catalog_id)
        # content negotiation
        content_type = negotiated_content_type(flask.request.environ, self.supported_types, self.default_content_type)
        deriva_ctx.ermrest_request_content_type = content_type

        resource = self.prejson()
        self.http_check_preconditions()
        self.emit_headers()
        deriva_ctx.deriva_response.content_type = content_type
        deriva_ctx.deriva_response.response = json.dumps(resource) + '\n'
        return deriva_ctx.deriva_response

    def PUT(self, catalog_id):
        """Perform HTTP update/create of catalog alias registry entry
        """
        self._prepare(catalog_id, missing_ok=True)
        self.http_check_preconditions()

        # optional input
        docstr = flask.request.stream.read().decode().strip()
        if docstr:
            try:
                doc = json.loads(docstr)
            except:
                raise exception.rest.BadRequest('Could not deserialize JSON input.')
        else:
            doc = {}

        if doc.get('id', catalog_id) != catalog_id:
            raise exception.rest.BadRequest('Alias id=%s in body does not match id=%s in URL..' % (doc.get('id'), catalog_id))

        if self.entry is None:
            # check static permissions as in POST alias/
            allowed = deriva_ctx.ermrest_registry.can_create(deriva_ctx.webauthn2_context.attributes)
            if not allowed:
                raise rest.Forbidden('alias/%s' % (catalog_id,))

        # abuse idempotent claim to update and to check existing claim permissions
        catalog_id = deriva_ctx.ermrest_registry.claim_id(id=catalog_id, id_owner=doc.get('owner'))

        # update the alias config
        entry = deriva_ctx.ermrest_registry.register(catalog_id, alias_target=doc.get('alias_target'))

        content_type = _application_json
        deriva_ctx.ermrest_request_content_type = content_type
        response = json.dumps({
            'id': entry['id'],
            'owner': entry['id_owner'],
            'alias_target': entry['alias_target'],
        }) + '\n'

        deriva_ctx.deriva_response.content_type = content_type
        deriva_ctx.deriva_response.response = response

        # set location header and status
        if self.entry is None:
            location = '/ermrest/alias/%s' % catalog_id
            deriva_ctx.deriva_response.location = location
            deriva_ctx.deriva_response.status_code = 201
        else:
            deriva_ctx.ermrest_request_content_type = None
            deriva_ctx.deriva_response.status_code = 200

        return deriva_ctx.deriva_response

    def DELETE(self, catalog_id):
        """Perform HTTP DELETE of catalog alias.
        """
        self._prepare(catalog_id)
        self.http_check_preconditions()

        self.enforce_right('owner')
        deriva_ctx.ermrest_registry.unregister(self.catalog_id)
        deriva_ctx.deriva_response.status_code = 204
        deriva_ctx.deriva_response.response = []
        return deriva_ctx.deriva_response

class Meta (Api):
    """A metadata set of the catalog.

       This is a temporary map of ACLs to old meta API for introspection by older clients.

       DEPRECATED.
    """

    default_content_type = _application_json
    supported_types = [default_content_type]

    def __init__(self, catalog, key=None, value=None):
        Api.__init__(self, catalog)
        self.key = key
        self.value = value

    def GET(self, uri):
        """Perform HTTP GET of catalog metadata.
        """
        content_type = negotiated_content_type(flask.request.environ, self.supported_types, self.default_content_type)
        def body(conn, cur):
            self.enforce_right('enumerate', uri)
            return deriva_ctx.ermrest_catalog_model.acls

        def post_commit(acls):
            self.set_http_etag( deriva_ctx.ermrest_catalog_model.etag() )
            self.http_check_preconditions()
            self.emit_headers()
            deriva_ctx.deriva_response.content_type = content_type
            deriva_ctx.ermrest_request_content_type = content_type

            meta = _acls_to_meta(acls)

            if self.key is not None:
                # project out single ACL from ACL set
                try:
                    meta = meta[self.key]
                except KeyError:
                    raise exception.rest.NotFound(uri)

            deriva_ctx.deriva_response.response = [ json.dumps(meta) + '\n', ]
            return deriva_ctx.deriva_response

        return self.perform(body, post_commit)

