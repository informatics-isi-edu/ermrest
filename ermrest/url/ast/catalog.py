
# 
# Copyright 2010-2013 University of Southern California
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
import web

import model
import data
from data import Api
from ... import exception, catalog, sanepg2

_application_json = 'application/json'
_text_plain = 'text/plain'

class Catalogs (Api):

    default_content_type = _application_json
    supported_types = [default_content_type, _text_plain]
    
    """A multi-tenant catalog set."""
    def __init__(self):
        Api.__init__(self, None)
    
    def POST(self, uri):
        """Perform HTTP POST of catalogs.
        """
        # content negotiation
        content_type = data.negotiated_content_type(self.supported_types, 
                                                    self.default_content_type)

        # create the catalog instance
        catalog = web.ctx.ermrest_catalog_factory.create()

        # initialize the catalog instance
        sanepg2.pooled_perform(catalog.dsn, lambda conn, cur: catalog.init_meta(conn, cur, web.ctx.webauthn2_context.client)).next()

        # register the catalog descriptor
        entry = web.ctx.ermrest_registry.register(catalog.descriptor)
        catalog_id = entry['id']
        
        web.header('Content-Type', content_type)
        web.ctx.ermrest_request_content_type = content_type
        
        # set location header and status
        if uri[-1:] == '/':
            location = uri + str(catalog_id)
        else:
            location = uri + '/' + str(catalog_id)
        web.header('Location', location)
        web.ctx.status = '201 Created'
        
        if content_type == _text_plain:
            return str(catalog_id)
        else:
            assert content_type == _application_json
            return json.dumps(dict(id=catalog_id))
        

class Catalog (Api):

    default_content_type = _application_json
    supported_types = [default_content_type]

    """A specific catalog by ID."""
    def __init__(self, catalog_id):
        Api.__init__(self, self)
        self.catalog_id = catalog_id
        self.manager = None
        entries = web.ctx.ermrest_registry.lookup(catalog_id)
        if not entries:
            raise exception.rest.NotFound('catalog ' + str(catalog_id))
        self.manager = catalog.Catalog(
            web.ctx.ermrest_catalog_factory, 
            entries[0]['descriptor'],
            web.ctx.ermrest_config
            )
        web.ctx.ermrest_catalog_dsn = sanepg2.pooled_connection(self.manager.dsn)
        self.resolve(web.ctx.ermrest_catalog_dsn[2])

    def resolve(self, cur):
        """Bootstrap catalog manager state."""
        # now enforce read permission
        self.enforce_read(cur, 'catalog/' + str(self.catalog_id))
        
    def schemas(self):
        """The schema set for this catalog."""
        return model.Schemas(self)

    def schema(self, name):
        """A specific schema for this catalog."""
        return model.Schema(self, name)

    def meta(self, key=None, value=None):
        """A metadata set for this catalog."""
        return Meta(self, key, value)

    def textfacet(self, filterelem, facetkeys, facetvals):
        """A textfacet set for this catalog."""
        return data.TextFacet(self, filterelem, facetkeys, facetvals)
    
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

    def GET(self, uri):
        """Perform HTTP GET of catalog.
        """
        # content negotiation
        content_type = data.negotiated_content_type(self.supported_types, 
                                                    self.default_content_type)
        web.header('Content-Type', content_type)
        web.ctx.ermrest_request_content_type = content_type
        
        def body(conn, cur):
            return list(self.manager.get_meta(cur))

        def post_commit(meta):
            # note that the 'descriptor' includes private system information such 
            # as the dbname (and potentially connection credentials) which should
            # not ever be shared.
            resource = dict(id=self.catalog_id,
                            meta=list(meta))
            response = json.dumps(resource) + '\n'
            web.header('Content-Length', len(response))
            return response
        
        return self.perform(body, post_commit)
    
    def DELETE(self, uri):
        """Perform HTTP DELETE of catalog.
        """
        def body(conn, cur):
            self.enforce_owner(cur, uri)
            return True

        def post_commit(destroy):
            web.ctx.ermrest_registry.unregister(self.catalog_id, destroy=True)
            web.ctx.status = '204 No Content'
            return ''

        self.perform(body, post_commit)


class Meta (Api):
    """A metadata set of the catalog."""

    default_content_type = _application_json
    supported_types = [default_content_type]

    def __init__(self, catalog, key=None, value=None):
        Api.__init__(self, catalog)
        self.key = key
        self.value = value
    
    
    def GET(self, uri):
        """Perform HTTP GET of catalog metadata.
        """
        content_type = data.negotiated_content_type(self.supported_types, 
                                                    self.default_content_type)
        def body(conn, cur):
            self.enforce_read(cur, uri)
            return self.catalog.manager.get_meta(cur, self.key, self.value)

        def post_commit(meta):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_request_content_type = content_type
            response = json.dumps(list(meta)) + '\n'
            web.header('Content-Length', len(response))
            return response

        return self.perform(body, post_commit)
    
    def PUT(self, uri):
        """Perform HTTP PUT of catalog metadata.
        """
        # disallow PUT of META
        if not self.key:
            raise exception.rest.NoMethod(uri)
        
        def body(conn, cur):
            self.enforce_write(cur, uri)
        
            if self.key == self.catalog.manager.META_OWNER:
                # must be owner to change owner
                self.enforce_owner(cur, uri)
                # must set owner to a rolename (TODO: better validation)
                if not self.value or self.value == '':
                    raise exception.rest.Forbidden(uri)
                # if all passed, SET the new owner
                self.catalog.manager.set_meta(cur, self.key, self.value)
            else:
                self.catalog.manager.add_meta(cur, self.key, self.value)
            
        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)
    
    
    def DELETE(self, uri):
        """Perform HTTP DELETE of catalog metadata.
        """
        # disallow DELETE of META
        if not self.key:
            raise exception.rest.NoMethod(uri)
        
        # disallow DELETE of OWNER
        if self.key == self.catalog.manager.META_OWNER:
            raise exception.rest.NoMethod(uri)
            
        def body(conn, cur):
            self.enforce_write(cur, uri)

            meta = self.catalog.manager.get_meta(cur, self.key, self.value)
            if not meta:
                raise exception.rest.NotFound(uri)
        
            self.catalog.manager.remove_meta(cur, self.key, self.value)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

