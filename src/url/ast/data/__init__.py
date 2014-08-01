
# 
# Copyright 2013 University of Southern California
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

"""ERMREST URL abstract syntax tree (AST) for data resources.

"""

import cStringIO
import web

import path
from path import Api
from ermrest import ermpath
from ermrest.exception import rest, BadData
import ermrest.model
from ermrest.util import negotiated_content_type

class Entity (Api):
    """A specific entity set by entitypath."""

    default_content_type = 'application/json'

    def __init__(self, catalog, path):
        Api.__init__(self, catalog)
        self.path = path
        self.http_vary.add('accept')

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.EntityPath instance that can
           be used to perform entity-level data access.
        """
        epath = ermpath.EntityPath(model)

        if not hasattr(self.path[0], 'resolve_table'):
            raise BadData('Entity paths must start with table syntax.')

        epath.set_base_entity( 
            self.path[0].name.resolve_table(model),
            self.path[0].alias
            )

        for elem in self.path[1:]:
            if elem.is_filter:
                epath.add_filter(elem)
            else:
                keyref, refop, lalias = elem.resolve_link(model, epath)
                epath.add_link(keyref, refop, elem.alias, lalias)

        return epath

    def GET(self, uri):
        """Perform HTTP GET of entities.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn):
            self.enforce_content_read(uri)

            model = self.catalog.manager.get_model(conn)
            epath = self.resolve(model)
            self.set_http_etag( epath.get_data_version(conn) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            epath.add_sort(self.sort)
            return epath.get(conn, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def PUT(self, uri, post_method=False, post_defaults=None):
        """Perform HTTP PUT of entities.
        """
        self.enforce_content_write(uri)
        
        try:
            in_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            in_content_type = in_content_type.split(";", 1)[0].strip()
        except:
            in_content_type = self.default_content_type

        content_type = negotiated_content_type(default=in_content_type)

        input_data = cStringIO.StringIO(web.ctx.env['wsgi.input'].read())
        
        def body(conn):
            input_data.seek(0) # rewinds buffer, in case of retry
            model = self.catalog.manager.get_model(conn)
            epath = self.resolve(model)
            return epath.put(conn,
                             input_data, 
                             in_content_type=in_content_type,
                             content_type=content_type, 
                             allow_existing = not post_method,
                             use_defaults = post_defaults)

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_request_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def POST(self, uri):
        """Perform HTTP POST of entities.
        """
        return self.PUT(uri, post_method=True, post_defaults=self.queryopts.get('defaults'))

    def DELETE(self, uri):
        """Perform HTTP DELETE of entities.
        """
        self.enforce_content_write(uri)
        
        def body(conn):
            model = self.catalog.manager.get_model(conn)
            epath = self.resolve(model)
            epath.delete(conn)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)


class Attribute (Api):
    """A specific attribute set by attributepath."""

    default_content_type = 'application/json'

    def __init__(self, catalog, path):
        Api.__init__(self, catalog)
        self.attributes = path[-1]
        self.epath = Entity(catalog, path[0:-1])
        self.http_vary.add('accept')

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.AttributePath instance that
           can be used to perform attribute-level data access.
        """
        epath = self.epath.resolve(model)
        return ermpath.AttributePath(epath, self.attributes)
    
    def GET(self, uri):
        """Perform HTTP GET of attributes.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn):
            self.enforce_content_read(uri)

            model = self.catalog.manager.get_model(conn)
            apath = self.resolve(model)
            self.set_http_etag( apath.epath.get_data_version(conn) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            apath.add_sort(self.sort)
            return apath.get(conn, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def DELETE(self, uri):
        """Perform HTTP DELETE of entity attribute.
        """
        self.enforce_content_write(uri)
        
        def body(conn):
            model = self.catalog.manager.get_model(conn)
            apath = self.resolve(model)
            apath.delete(conn)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

class AttributeGroup (Api):
    """A specific group set by entity path, group keys, and group attributes."""

    default_content_type = 'application/json'

    def __init__(self, catalog, path):
        Api.__init__(self, catalog)
        self.attributes = path[-1]
        self.groupkeys = path[-2]
        self.epath = Entity(catalog, path[0:-2])

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.AttributePath instance that
           can be used to perform attribute-level data access.
        """
        epath = self.epath.resolve(model)
        return ermpath.AttributeGroupPath(epath, self.groupkeys, self.attributes)
    
    def GET(self, uri):
        """Perform HTTP GET of attribute groups.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn):
            self.enforce_content_read(uri)

            model = self.catalog.manager.get_model(conn)
            agpath = self.resolve(model)
            self.set_http_etag( agpath.epath.get_data_version(conn) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            agpath.add_sort(self.sort)
            return agpath.get(conn, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def PUT(self, uri, post_method=False):
        """Perform HTTP PUT of attribute groups.
        """
        self.enforce_content_write(uri)
        
        try:
            in_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            in_content_type = in_content_type.split(";", 1)[0].strip()
        except:
            in_content_type = self.default_content_type

        content_type = negotiated_content_type(default=in_content_type)

        input_data = cStringIO.StringIO(web.ctx.env['wsgi.input'].read())
        
        def body(conn):
            input_data.seek(0) # rewinds buffer, in case of retry
            model = self.catalog.manager.get_model(conn)
            agpath = self.resolve(model)
            return agpath.put(conn,
                              input_data, 
                              in_content_type=in_content_type)

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_request_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)


class Aggregate (Api):
    """A specific aggregate tuple."""

    default_content_type = 'application/json'

    def __init__(self, catalog, path):
        Api.__init__(self, catalog)
        self.attributes = path[-1]
        self.epath = Entity(catalog, path[0:-1])

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.AttributePath instance that
           can be used to perform attribute-level data access.
        """
        epath = self.epath.resolve(model)
        return ermpath.AggregatePath(epath, self.attributes)
    
    def GET(self, uri):
        """Perform HTTP GET of attribute groups.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn):
            self.enforce_content_read(uri)
            model = self.catalog.manager.get_model(conn)
            agpath = self.resolve(model)
            self.set_http_etag( agpath.epath.get_data_version(conn) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            agpath.add_sort(self.sort)
            return agpath.get(conn, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

class Query (Api):
    """A specific query set by querypath."""
    def __init__(self, catalog, path):
        Api.__init__(self, catalog)
        self.expressions = path[-1]
        self.epath = Entity(catalog, path[0:-1])

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.AttributePath instance that
           can be used to perform attribute-level data access.
        """
        epath = self.epath.resolve(model)
        # TODO: validate expressions
        expressions = self.expressions
        return QueryPath(epath, expressions)
    
