
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

def negotiated_content_type(supported_types=['text/csv', 'application/json', 'application/x-json-stream'], default=None):
    """Determine negotiated response content-type from Accept header.

       supported_types: a list of MIME types the caller would be able
         to implement if the client has requested one.

       default: a MIME type or None to return if none of the
         supported_types were requested by the client.

       This function considers the preference qfactors encoded in the
       client request to choose the preferred type when there is more
       than one supported type that the client would accept.

    """
    def accept_pair(s):
        """parse one Accept header pair into (qfactor, type)."""
        parts = s.split(';')
        q = 1.0
        t = parts[0].strip()
        for p in parts[1:]:
            fields = p.split('=')
            if len(fields) == 2 and fields[0] == 'q':
                q = fields[1]
        return (q, t)

    try:
        accept = web.ctx.env['HTTP_ACCEPT']
    except:
        accept = ""
            
    accept_types = [ 
        pair[1]
        for pair in sorted(
            [ accept_pair(s) for s in accept.lower().split(',') ],
            key=lambda pair: pair[0]
            ) 
        ]

    if accept_types:
        for accept_type in accept_types:
            if accept_type in supported_types:
                return accept_type

    return default

class Entity (Api):
    """A specific entity set by entitypath."""

    default_content_type = 'application/x-json-stream'

    def __init__(self, catalog, path):
        Api.__init__(self, catalog)
        self.path = path

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
                # TODO: consider two-hop resolution via implied association table?
                #   will add intermediate link to epath...

        return epath

    def GET(self, uri):
        """Perform HTTP GET of entities.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn):
            if not self.catalog.manager.has_content_read(
                web.ctx.webauthn2_context.attributes
                ):
                raise rest.Unauthorized(uri)

            model = ermrest.model.introspect(conn)
            epath = self.resolve(model)
            epath.add_sort(self.sort)
            return epath.get(conn, content_type=content_type, limit=limit)

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def PUT(self, uri, post_method=False, post_defaults=None):
        """Perform HTTP PUT of entities.
        """
        if not self.catalog.manager.has_content_write(
                                web.ctx.webauthn2_context.attributes):
            raise rest.Unauthorized(uri)
        
        try:
            in_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            in_content_type = in_content_type.split(";", 1)[0].strip()
        except:
            in_content_type = self.default_content_type

        content_type = negotiated_content_type(default=in_content_type)

        input_data = cStringIO.StringIO(web.ctx.env['wsgi.input'].read())
        
        def body(conn):
            input_data.seek(0) # rewinds buffer, in case of retry
            model = ermrest.model.introspect(conn)
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
        if not self.catalog.manager.has_content_write(
                                web.ctx.webauthn2_context.attributes):
            raise rest.Unauthorized(uri)
        
        def body(conn):
            model = ermrest.model.introspect(conn)
            epath = self.resolve(model)
            epath.delete(conn)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)


class Attribute (Api):
    """A specific attribute set by attributepath."""

    default_content_type = 'application/x-json-stream'

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
        return ermpath.AttributePath(epath, self.attributes)
    
    def GET(self, uri):
        """Perform HTTP GET of attributes.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn):
            if not self.catalog.manager.has_content_read(
                web.ctx.webauthn2_context.attributes
                ):
                raise rest.Unauthorized(uri)

            model = ermrest.model.introspect(conn)
            apath = self.resolve(model)
            apath.add_sort(self.sort)
            return apath.get(conn, content_type=content_type, limit=limit)

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def DELETE(self, uri):
        """Perform HTTP DELETE of entity attribute.
        """
        if not self.catalog.manager.has_content_write(
                                web.ctx.webauthn2_context.attributes):
            raise rest.Unauthorized(uri)
        
        def body(conn):
            model = ermrest.model.introspect(conn)
            apath = self.resolve(model)
            apath.delete(conn)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

class AttributeGroup (Api):
    """A specific group set by entity path, group keys, and group attributes."""

    default_content_type = 'application/x-json-stream'

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
            if not self.catalog.manager.has_content_read(
                web.ctx.webauthn2_context.attributes
                ):
                raise rest.Unauthorized(uri)

            model = ermrest.model.introspect(conn)
            agpath = self.resolve(model)
            agpath.add_sort(self.sort)
            return agpath.get(conn, content_type=content_type, limit=limit)

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def PUT(self, uri, post_method=False):
        """Perform HTTP PUT of attribute groups.
        """
        if not self.catalog.manager.has_content_write(
                                web.ctx.webauthn2_context.attributes):
            raise rest.Unauthorized(uri)
        
        try:
            in_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            in_content_type = in_content_type.split(";", 1)[0].strip()
        except:
            in_content_type = self.default_content_type

        content_type = negotiated_content_type(default=in_content_type)

        input_data = cStringIO.StringIO(web.ctx.env['wsgi.input'].read())
        
        def body(conn):
            input_data.seek(0) # rewinds buffer, in case of retry
            model = ermrest.model.introspect(conn)
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
    
