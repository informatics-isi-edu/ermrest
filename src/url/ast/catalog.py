
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

class Catalogs (Api):
    """A multi-tenant catalog set."""
    def __init__(self):
        Api.__init__(self, None)
    
    def POST(self, uri):
        """Perform HTTP POST of catalogs.
        """
        #TODO: content negotiation
        #TODO: exception handling
        ctx = util.initial_context()
        registry = ctx['ermrest_registry']
        factory = ctx['ermrest_catalog_factory']
        
        # create and register catalog, return only its id
        catalog = factory.create()
        catalog.init_meta()
        entry=registry.register(catalog.descriptor)
        
        # set status and headers
        web.ctx.status = '201 Created'
        #TODO: set headers
        #TODO: set location
        return json.dumps(dict(id=entry['id']))

class Catalog (Api):
    """A specific catalog by ID."""
    def __init__(self, catalog_id):
        Api.__init__(self, self)
        self.catalog_id = catalog_id
        
        # lookup the catalog manager
        ctx = util.initial_context()
        self.registry = ctx['ermrest_registry']
        entries = self.registry.lookup(catalog_id)
        if not entries or len(entries) == 0:
            raise exception.rest.NotFound('catalog ' + str(catalog_id))
        self.manager = catalog.Catalog(ctx['ermrest_catalog_factory'], 
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
    
    def GET(self, uri):
        """Perform HTTP GET of catalog.
        """
        #TODO: content negotiation
        #TODO: exception handling
        
        # note that the 'descriptor' includes private system information such 
        # as the dbname (and potentially connection credentials) which should
        # not ever be shared.
        resource = dict(id=self.catalog_id,
                        meta=self.manager.get_meta())
        return json.dumps(resource)
    
    def DELETE(self, uri):
        """Perform HTTP DELETE of catalog.
        """
        #TODO: exception handling
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

    default_content_type = 'application/x-json-stream'

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
        
        return json.dumps(self.catalog.manager.get_meta(self.key, self.value))
    
    def PUT(self, uri):
        """Perform HTTP PUT of catalog metadata.
        """
        if not self.catalog.manager.has_write(
                                web.ctx.webauthn2_context.attributes):
            raise exception.rest.Unauthorized(uri)
        
        # disallow PUT on ...catalog/<i>/meta
        if not self.key:
            raise exception.rest.NoMethod(uri)
        
        self.catalog.manager.add_meta(self.key, self.value)
        web.ctx.status = '204 No Content'
        return ''
    
    def DELETE(self, uri):
        """Perform HTTP DELETE of catalog metadata.
        """
        if not self.catalog.manager.has_write(
                                web.ctx.webauthn2_context.attributes):
            raise exception.rest.Unauthorized(uri)
        
        # disallow DELETE on ...catalog/<i>/meta
        if not self.key:
            raise exception.rest.NoMethod(uri)
        
        # note: this does not throw exception if value is specified but does 
        #       not exist
        self.catalog.manager.remove_meta(self.key, self.value)
        web.ctx.status = '204 No Content'
        return ''
