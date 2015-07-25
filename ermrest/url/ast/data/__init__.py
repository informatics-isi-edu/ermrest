
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

from .path import Api, Path
from .... import ermpath
from ....exception import rest, BadData
from ....util import negotiated_content_type

class TextFacet (Api):
    """A specific text facet by textfragment.

       HACK: Parameters for the corresponding AttributeGroupPath query
       are built by the URL parser to avoid circular dependencies in
       the AST sub-modules.

    """

    default_content_type = 'application/json'

    def __init__(self, catalog, filterelem, facetkeys, facetvals):
        Api.__init__(self, catalog)
        self.filterelem = filterelem
        self.facetkeys = facetkeys
        self.facetvals = facetvals
        self.http_vary.add('accept')

    def resolve(self, model):
        """Resolve self against a specific database model.

        """
        epath = ermpath.EntityPath(model)
        epath.set_base_entity(model.ermrest_schema.tables['valuemap'])
        epath.add_filter(self.filterelem)
        return ermpath.AttributeGroupPath(epath, self.facetkeys, self.facetvals)

    def GET(self, uri):
        """Perform HTTP GET of text facet.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.enforce_content_read(cur, uri)
            model = self.catalog.manager.get_model(cur)
            agpath = self.resolve(model)
            epath = agpath.epath
            self.set_http_etag( epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            return agpath.get(conn, cur, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

class Entity (Api):
    """A specific entity set by entitypath."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        cur = web.ctx.ermrest_catalog_dsn[2]
        self.enforce_content_read(cur)
        self.model = self.catalog.manager.get_model(cur)
        self.epath = ermpath.EntityPath(self.model)
        self.epath.set_base_entity( 
            elem.name.resolve_table(self.model),
            elem.alias
        )
        self.http_vary.add('accept')

    def append(self, elem):
        if elem.is_filter:
            self.epath.add_filter(elem)
        elif elem.is_context:
            self.epath.set_context(elem)
        else:
            keyref, refop, lalias = elem.resolve_link(self.model, self.epath)
            self.epath.add_link(keyref, refop, elem.alias, lalias)
            
    def GET(self, uri):
        """Perform HTTP GET of entities.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.set_http_etag( self.epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            self.epath.add_sort(self.sort)
            return self.epath.get(conn, cur, content_type=content_type, limit=limit)

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
        try:
            in_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            in_content_type = in_content_type.split(";", 1)[0].strip()
        except:
            in_content_type = self.default_content_type

        content_type = negotiated_content_type(default=in_content_type)

        input_data = cStringIO.StringIO(web.ctx.env['wsgi.input'].read())
        
        def body(conn, cur):
            input_data.seek(0) # rewinds buffer, in case of retry
            self.enforce_content_write(cur, uri)
            return self.epath.put(
                conn,
                cur,
                input_data, 
                in_content_type=in_content_type,
                content_type=content_type, 
                allow_existing = not post_method,
                use_defaults = post_defaults
            )

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_request_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

    def POST(self, uri):
        """Perform HTTP POST of entities.
        """
        defaults = self.queryopts.get('defaults')
        if defaults and type(defaults) is not set:
            # defaults is a single column name from queryopts
            defaults = set([ defaults ])
        else:
            # defaults is already a set of column names from queryopts
            # or it is None
            pass
        return self.PUT(uri, post_method=True, post_defaults=defaults)

    def DELETE(self, uri):
        """Perform HTTP DELETE of entities.
        """
        def body(conn, cur):
            self.enforce_content_write(cur, uri)
            self.epath.delete(conn, cur)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)


class Attribute (Api):
    """A specific attribute set by attributepath."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        self.Entity = Entity(catalog, elem)
        self.apath = None
        self.http_vary.add('accept')

    def append(self, elem):
        self.Entity.append(elem)

    def set_projection(self, attributes):
        self.apath = ermpath.AttributePath(self.Entity.epath, attributes)
        
    def GET(self, uri):
        """Perform HTTP GET of attributes.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.enforce_content_read(cur, uri)
            self.set_http_etag( self.apath.epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            self.apath.add_sort(self.sort)
            return self.apath.get(conn, cur, content_type=content_type, limit=limit)

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
        def body(conn, cur):
            self.enforce_content_write(cur, uri)
            self.apath.delete(conn, cur)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

class AttributeGroup (Api):
    """A specific group set by entity path, group keys, and group attributes."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        self.Entity = Entity(catalog, elem)
        self.agpath = None
        self.http_vary.add('accept')

    def append(self, elem):
        self.Entity.append(elem)

    def set_projection(self, groupkeys, attributes):
        self.agpath = ermpath.AttributeGroupPath(self.Entity.epath, groupkeys, attributes)
    
    def GET(self, uri):
        """Perform HTTP GET of attribute groups.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.enforce_content_read(cur, uri)
            self.set_http_etag( self.agpath.epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            self.agpath.add_sort(self.sort)
            return self.agpath.get(conn, cur, content_type=content_type, limit=limit)

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
        try:
            in_content_type = web.ctx.env['CONTENT_TYPE'].lower()
            in_content_type = in_content_type.split(";", 1)[0].strip()
        except:
            in_content_type = self.default_content_type

        content_type = negotiated_content_type(default=in_content_type)

        input_data = cStringIO.StringIO(web.ctx.env['wsgi.input'].read())
        
        def body(conn, cur):
            input_data.seek(0) # rewinds buffer, in case of retry
            self.enforce_content_write(cur, uri)
            return self.agpath.put(
                conn,
                cur,
                input_data, 
                in_content_type=in_content_type
            )

        def post_commit(lines):
            web.header('Content-Type', content_type)
            web.ctx.ermrest_request_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)


class Aggregate (Api):
    """A specific aggregate tuple."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        self.Entity = Entity(catalog, elem)
        self.agpath = None
        self.http_vary.add('accept')

    def append(self, elem):
        self.Entity.append(elem)

    def set_projection(self, attributes):
        self.agpath = ermpath.AggregatePath(self.Entity.epath, attributes)
    
    def GET(self, uri):
        """Perform HTTP GET of attribute groups.
        """
        content_type = negotiated_content_type(default=self.default_content_type)
        limit = self.negotiated_limit()
        
        def body(conn, cur):
            self.enforce_content_read(cur, uri)
            self.set_http_etag( self.agpath.epath.get_data_version(cur) )
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return None
            self.agpath.add_sort(self.sort)
            return self.agpath.get(conn, cur, content_type=content_type, limit=limit)

        def post_commit(lines):
            self.emit_headers()
            if lines is None:
                return
            web.header('Content-Type', content_type)
            web.ctx.ermrest_content_type = content_type
            for line in lines:
                yield line

        return self.perform(body, post_commit)

