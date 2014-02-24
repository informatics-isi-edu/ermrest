
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
from model import Api
from ermrest import util, exception, catalog

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
        web.header('Content-Type', content_type)
        web.ctx.ermrest_request_content_type = content_type
        
        # create and register catalog, return only its id
        catalog = web.ctx.ermrest_catalog_factory.create()
        catalog.init_meta(web.ctx.webauthn2_context.client)
        entry=web.ctx.ermrest_registry.register(catalog.descriptor)
        catalog_id = entry['id']
        
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
        
        # lookup the catalog manager
        self.registry = web.ctx.ermrest_registry
        entries = self.registry.lookup(catalog_id)
        if not entries or len(entries) == 0:
            raise exception.rest.NotFound('catalog ' + str(catalog_id))
        self.manager = catalog.Catalog(web.ctx.ermrest_catalog_factory, 
                                       entries[0]['descriptor'])

    def schemas(self):
        """The schema set for this catalog."""
        return model.Schemas(self)

    def schema(self, name):
        """A specific schema for this catalog."""
        return model.Schema(self, name)

    def meta(self, key=None, value=None):
        """A metadata set for this catalog."""
        return Meta(self, key, value)
    
    def entity(self, epath):
        """An entity set for this catalog."""
        return data.Entity(self, epath)

    def attribute(self, apath):
        """An attribute set for this catalog."""
        return data.Attribute(self, apath)

    def query(self, qpath):
        """A query set for this catalog."""
        return data.Query(self, qpath)

    def get_conn(self):
        """get db conn to this catalog."""
        return self.manager.get_connection()
    
    def discard_conn(self, conn):
        self.manager.discard_connection(conn)

    def release_conn(self, conn):
        """release db conn to this catalog."""
        self.manager.release_connection(conn)
    
    def GET(self, uri):
        """Perform HTTP GET of catalog.
        """
        # content negotiation
        content_type = data.negotiated_content_type(self.supported_types, 
                                                    self.default_content_type)
        web.header('Content-Type', content_type)
        web.ctx.ermrest_request_content_type = content_type
        
        # meta can be none, if catalog is not initialized
        try:
            meta = self.manager.get_meta()
        except:
            meta = None
            
        # note that the 'descriptor' includes private system information such 
        # as the dbname (and potentially connection credentials) which should
        # not ever be shared.
        resource = dict(id=self.catalog_id,
                        meta=meta)
        return json.dumps(resource)
    
    def DELETE(self, uri):
        """Perform HTTP DELETE of catalog.
        """
        if not self.manager.is_owner(web.ctx.webauthn2_context.client):
            raise exception.rest.Unauthorized(uri)
        
        ######
        # TODO: needs to be done in two steps
        #  1. in registry, flag the catalog to-be-destroyed
        #  2. in manager, attempt to destroy catalog
        #  3.a. in registry, unregister the catalog
        #  3.b. if 2 fails, either rollback the registry
        #       --or-- run a sweeper that finishes the job
        ######
        self.manager.destroy()
        self.registry.unregister(self.catalog_id)
        web.ctx.status = '204 No Content'
        return ''


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
        if not self.catalog.manager.has_read(
                                web.ctx.webauthn2_context.attributes):
            raise exception.rest.Unauthorized(uri)
        
        content_type = data.negotiated_content_type(self.supported_types, 
                                                    self.default_content_type)
        web.header('Content-Type', content_type)
        web.ctx.ermrest_request_content_type = content_type
        return json.dumps(self.catalog.manager.get_meta(self.key, self.value))
    
    
    def PUT(self, uri):
        """Perform HTTP PUT of catalog metadata.
        """
        if not (self.catalog.manager.has_write(
                        web.ctx.webauthn2_context.attributes)
                or self.catalog.manager.is_owner(
                        web.ctx.webauthn2_context.client) ):
            raise exception.rest.Unauthorized(uri)
        
        # disallow PUT of META
        if not self.key:
            raise exception.rest.NoMethod(uri)
        
        if self.key == self.catalog.manager.META_OWNER:
            # must be owner to change owner
            if not self.catalog.manager.is_owner(
                            web.ctx.webauthn2_context.client):
                raise exception.rest.Unauthorized(uri)
            # must set owner to a rolename (TODO: better validation)
            if not self.value or self.value == '':
                raise exception.rest.Forbidden(uri)
            # if all passed, SET the new owner
            self.catalog.manager.set_meta(self.key, self.value)
        else:
            self.catalog.manager.add_meta(self.key, self.value)
            
        web.ctx.status = '204 No Content'
        return ''
    
    
    def DELETE(self, uri):
        """Perform HTTP DELETE of catalog metadata.
        """
        if not (self.catalog.manager.has_write(
                        web.ctx.webauthn2_context.attributes)
                or self.catalog.manager.is_owner(
                        web.ctx.webauthn2_context.client) ):
            raise exception.rest.Unauthorized(uri)
        
        # disallow DELETE of META
        if not self.key:
            raise exception.rest.NoMethod(uri)
        
        # disallow DELETE of OWNER
        if self.key == self.catalog.manager.META_OWNER:
            raise exception.rest.Forbidden(uri)
            
        # note: this does not throw exception if value is specified but does 
        #       not exist
        self.catalog.manager.remove_meta(self.key, self.value)
        web.ctx.status = '204 No Content'
        return ''
