
# 
# Copyright 2013-2023 University of Southern California
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

import io
import tempfile
import psycopg2
import datetime
from datetime import timezone
import flask

from webauthn2.util import urlquote, deriva_ctx

from ..api import Api
from . import path
from ....model.predicate import predicatecls
from ....model.name import Name
from .... import ermpath, exception
from ....util import sql_literal

def _preprocess_attributes(epath, attributes):
    """Expand '*' wildcards in attributes into explicit projections understood by ermpath."""
    results = []
    for item in attributes:
        if type(item) is tuple:
            # make preprocessing resolution idempotent
            attribute, col, base = item
        else:
            attribute = item
            if len(attribute.nameparts) > 2:
                raise exception.BadSyntax('Column name %s, qualified by schema and table names, not allowed as attribute.' % attribute)
            elif len(attribute.nameparts) > 1 and attribute.nameparts[0] not in epath.aliases:
                raise exception.BadSyntax('Alias %s, qualifying column name %s, not bound in path.' % (attribute.nameparts[0], attribute))
            col, base = attribute.resolve_column(epath._model, epath)

        if col.is_star_column() and not hasattr(attribute, 'aggfunc'):
            # expand '*' wildcard sugar as if user referenced each column
            if hasattr(attribute, 'nbins'):
                raise exception.BadSyntax('Wildcard column %s does not support binning.' % attribute)
            if attribute.alias is not None:
                raise exception.BadSyntax('Wildcard column %s cannot be given an alias.' % attribute)
            if base == epath:
                # columns from final entity path element
                for col in epath._path[epath.current_entity_position()].table.columns_in_order():
                    results.append((Name([col.name]), col, base))
            elif base in epath.aliases:
                # columns from interior path referenced by alias
                for col in epath[base].table.columns_in_order():
                    results.append((Name([base, col.name]).set_alias('%s:%s' % (base, col.name)), col, base))
            else:
                raise NotImplementedError('Unresolvable * column violates program invariants!')
        else:
            results.append((attribute, col, base))
            
    return results

def _GET(handler, uri, dresource, vresource):
    """Perform HTTP GET of generic data resources.
    """
    content_type = handler.negotiated_content_type()
    limit = handler.negotiated_limit()

    if content_type == 'text/csv':
        results = tempfile.TemporaryFile()
    else:
        results = None
        
    def body(conn, cur):
        try:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ)
            handler.set_http_etag( vresource.etag(cur) )
            handler.http_check_preconditions()
            dresource.add_sort(handler.sort)
            dresource.add_paging(handler.after, handler.before)
            return dresource.get(conn, cur, content_type=content_type, output_file=results, limit=limit)
        finally:
            try:
                conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
            except:
                pass

    def post_commit(lines):
        handler.emit_headers()
        if lines is None:
            return
        deriva_ctx.deriva_response.content_type = content_type
        if 'download' in handler.queryopts and handler.queryopts['download']:
            fname = handler.queryopts['download']
            fname += {
                'application/json': '.json',
                'application/x-json-stream': '.json',
                'text/csv': '.csv'
            }.get(content_type, '.txt')
            deriva_ctx.deriva_response.headers['Content-Disposition'] = \
                "attachment; filename*=UTF-8''%s" % urlquote(fname.encode('utf8'))
        deriva_ctx.ermrest_content_type = content_type
        if hasattr(lines, 'seek'):
            lines.seek(0, 2)
            pos = lines.tell()
            lines.seek(0, 0)
            deriva_ctx.deriva_response.content_length = pos
            deriva_ctx.deriva_response.response = lines
            deriva_ctx.deriva_response.direct_passthrough = True
        else:
            deriva_ctx.deriva_response.response = lines
        return deriva_ctx.deriva_response

    return handler.perform(body, post_commit)

def _PUT(handler, uri, put_thunk, vresource):
    """Perform HTTP PUT of generic data resources.
    """
    if deriva_ctx.ermrest_history_snaptime is not None:
        raise exception.Forbidden('modification to catalog at previous revision')
    if deriva_ctx.ermrest_history_snaprange is not None:
        # should not be possible bug check anyway...
        raise NotImplementedError('modification on %s with snaprange' % uri)
    try:
        in_content_type = flask.request.environ['CONTENT_TYPE'].lower()
        in_content_type = in_content_type.split(";", 1)[0].strip()
    except:
        in_content_type = handler.default_content_type

    content_type = handler.negotiated_content_type(default=in_content_type)

    input_data = io.BytesIO(flask.request.stream.read())

    def body(conn, cur):
        input_data.seek(0) # rewinds buffer, in case of retry
        handler.set_http_etag( vresource.etag(cur) )
        handler.http_check_preconditions(method='PUT')
        result = put_thunk([
            conn,
            cur,
            input_data, 
            in_content_type,
            content_type
        ])
        handler.set_http_etag( vresource.etag(cur) )
        cur.close()
        return result

    def post_commit(lines):
        handler.emit_headers()
        deriva_ctx.deriva_response.content_type = content_type
        deriva_ctx.ermrest_request_content_type = content_type
        deriva_ctx.deriva_response.response = lines
        return deriva_ctx.deriva_response

    return handler.perform(body, post_commit)

def _DELETE(handler, uri, resource, vresource):
    """Perform HTTP DELETE of generic data resources.
    """
    if deriva_ctx.ermrest_history_snaptime is not None:
        raise exception.Forbidden('modification to catalog at previous revision')
    if deriva_ctx.ermrest_history_snaprange is not None:
        # should not be possible bug check anyway...
        raise NotImplementedError('modification on %s with snaprange' % uri)

    def body(conn, cur):
        handler.set_http_etag( vresource.etag(cur) )
        handler.http_check_preconditions(method='DELETE')
        resource.delete(conn, cur)
        handler.set_http_etag( vresource.etag(cur) )

    def post_commit(ignore):
        handler.emit_headers()
        deriva_ctx.deriva_response.status_code = 204
        deriva_ctx.deriva_response.response = []
        return deriva_ctx.deriva_response

    return handler.perform(body, post_commit)


class TextFacet (Api):
    """A specific text facet by textfragment.

    """

    default_content_type = 'application/json'

    def __init__(self, catalog, pattern):
        Api.__init__(self, catalog)
        self.http_vary.add('accept')
        cur = deriva_ctx.ermrest_catalog_pc.cur
        self.textfacet = ermpath.TextFacet(
            catalog,
            deriva_ctx.ermrest_catalog_model,
            pattern
        )

    def GET(self, uri):
        """Perform HTTP GET of text facet.
        """
        return _GET(self, uri, self.textfacet, self.textfacet)

class Entity (Api):
    """A specific entity set by entitypath."""

    default_content_type = 'application/json'

    def __init__(self, catalog, elem):
        Api.__init__(self, catalog)
        cur = deriva_ctx.ermrest_catalog_pc.cur
        self.epath = ermpath.EntityPath(deriva_ctx.ermrest_catalog_model)
        if len(elem.name.nameparts) == 2:
            table = deriva_ctx.ermrest_catalog_model.schemas.get_enumerable(elem.name.nameparts[0]).tables.get_enumerable(elem.name.nameparts[1])
        elif len(elem.name.nameparts) == 1:
            table = deriva_ctx.ermrest_catalog_model.lookup_table(elem.name.nameparts[0])
        else:
            raise exception.BadSyntax('Name %s is not a valid syntax for a table name.' % elem.name)
        self.epath.set_base_entity(table, elem.alias)
        self.http_vary.add('accept')

    def append(self, elem):
        if elem.is_filter:
            self.epath.add_filter(elem)
        elif elem.is_context:
            if len(elem.name.nameparts) > 1:
                raise exception.BadSyntax('Context name %s is not a valid syntax for an entity alias.' % elem.name)
            try:
                alias = self.epath[elem.name.nameparts[0]].alias
            except KeyError:
                raise exception.BadData('Context name %s is not a bound alias in entity path.' % elem.name)
                
            self.epath.set_context(alias)
        else:
            keyref, refop, lalias = elem.resolve_link(deriva_ctx.ermrest_catalog_model, self.epath)
            outer_type = elem.outer_type if hasattr(elem, 'outer_type') else None
            self.epath.add_link(keyref, refop, elem.alias, lalias, outer_type=outer_type)
            
    def GET(self, uri):
        """Perform HTTP GET of entities.
        """
        return _GET(self, uri, self.epath, self.epath)

    def PUT(self, uri):
        """Perform HTTP PUT of entities.
        """
        return _PUT(self, uri, lambda args: self.epath.upsert(*args), self.epath)

    def POST(self, uri):
        """Perform HTTP POST of entities.
        """
        def prepare_defaults(k):
            defaults = self.queryopts.get(k)
            if defaults and type(defaults) is not set:
                # defaults is a single column name from queryopts
                defaults = set([ defaults ])
            elif defaults is None:
                defaults = set()
            # defaults is always a set at this point
            return defaults
        onconflict = self.queryopts.get('onconflict', 'abort').lower()
        if onconflict == 'skip':
            only_nonmatch = True
        elif onconflict == 'abort':
            only_nonmatch = False
        else:
            raise exception.BadSyntax('Unknown action name in query parameter onconflict="%s". Expected "skip" or "abort".' % onconflict)
        return _PUT(self, uri, lambda args: self.epath.insert(*args, use_defaults=prepare_defaults('defaults'), non_defaults=prepare_defaults('nondefaults'), only_nonmatch=only_nonmatch), self.epath)

    def DELETE(self, uri):
        """Perform HTTP DELETE of entities.
        """
        return _DELETE(self, uri, self.epath, self.epath)

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
        self.apath = ermpath.AttributePath(self.Entity.epath, _preprocess_attributes(self.Entity.epath, attributes))
        
    def GET(self, uri):
        """Perform HTTP GET of attributes.
        """
        return _GET(self, uri, self.apath, self.apath.epath)

    def DELETE(self, uri):
        """Perform HTTP DELETE of entity attribute.
        """
        return _DELETE(self, uri, self.apath, self.apath.epath)

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
        self.agpath = ermpath.AttributeGroupPath(
            self.Entity.epath,
            _preprocess_attributes(self.Entity.epath, groupkeys),
            _preprocess_attributes(self.Entity.epath, attributes)
        )
    
    def GET(self, uri):
        """Perform HTTP GET of attribute groups.
        """
        return _GET(self, uri, self.agpath, self.agpath.epath)

    def PUT(self, uri, post_method=False):
        """Perform HTTP PUT of attribute groups.
        """
        return _PUT(self, uri, lambda args: self.agpath.update(*args), self.agpath.epath)

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
        self.agpath = ermpath.AggregatePath(self.Entity.epath, _preprocess_attributes(self.Entity.epath, attributes))
    
    def GET(self, uri):
        """Perform HTTP GET of attribute groups.
        """
        return _GET(self, uri, self.agpath, self.agpath.epath)
