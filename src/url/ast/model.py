
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

"""ERMREST URL abstract syntax tree (AST) for model introspection resources.

"""

import json
import web

from ermrest import exception
import ermrest.model
from data import Api
from ermrest.util import negotiated_content_type

schema_html = """
<html>
  <head>
    <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
    <link type="text/css" rel="stylesheet" href="/ajax/css/ermrest.css" />
    <script type="text/javascript" src="/ajax/js/jquery.js"></script>
   <script type="text/javascript" src="/ajax/js/ermrest.js"></script>

    <script type="text/javascript">
    $(document).ready(function () {
        %(ready)s();
    });
    </script>

  </head>
  <body>
    <div id="ermrest">
    </div>
  </body>
</html>
"""

class Schemas (Api):
    """A schema set."""

    supported_content_types = ['application/json', 'text/html']
    default_content_type = supported_content_types[0]

    def __init__(self, catalog):
        Api.__init__(self, catalog)
        self.http_vary.add('accept')

    def GET(self, uri):
        """HTTP GET for Schemas of a Catalog."""
        content_type = negotiated_content_type(self.supported_content_types, self.default_content_type)

        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_content_read(cur, uri)
            return self.catalog.manager.get_model(cur)

        def post_commit(model):
            self.set_http_etag( self.catalog.manager._model_version )
            self.emit_headers()
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return ''
            else:
                web.header('Content-Type', content_type)
                response = json.dumps(model.prejson(), indent=2) + '\n'
                web.header('Content-Length', len(response))
                return response

        if content_type == 'text/html':
            # return static AJAX page
            web.header('Content-Type', content_type)
            return schema_html % (dict(ready='initSchemas'))
        else:
            return self.perform(body, post_commit)

class Schema (Api):
    """A specific schema by name."""

    supported_content_types = ['application/json', 'text/html']
    default_content_type = supported_content_types[0]

    def __init__(self, catalog, name):
        Api.__init__(self, catalog)
        self.name = name
        self.http_vary.add('accept')

    def tables(self):
        """The table set for this schema."""
        return Tables(self)

    def table(self, name):
        """A specific table for this schema."""
        return Table(self, name)

    def GET_body(self, conn, cur, uri):
        self.catalog.resolve(cur)
        self.enforce_content_read(cur, uri)
        model = self.catalog.manager.get_model(cur)
        return model.lookup_schema(str(self.name))

    def GET(self, uri):
        """HTTP GET for Schemas of a Catalog."""
        content_type = negotiated_content_type(self.supported_content_types, self.default_content_type)

        def post_commit(schema):
            self.set_http_etag( self.catalog.manager._model_version )
            self.emit_headers()
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return ''
            else:
                web.header('Content-Type', content_type)
                response = json.dumps(schema.prejson(), indent=2) + '\n'
                web.header('Content-Length', len(response))
                return response

        if content_type == 'text/html':
            # return static AJAX page
            web.header('Content-Type', content_type)
            return schema_html % (dict(ready='initSchema'))
        else:
            return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), post_commit)

    def POST(self, uri):
        """Create a new empty schema."""
        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            model = self.catalog.manager.get_model(cur)
            model.create_schema(conn, cur, str(self.name))
            
        def post_commit(ignore):
            web.ctx.status = '201 Created'
            return ''

        return self.perform(body, post_commit)

    def DELETE(self, uri):
        """Delete an existing schema."""
        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            model = self.catalog.manager.get_model(cur)
            model.delete_schema(conn, cur, str(self.name))
            
        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)
        

class Tables (Api):
    """A table set."""
    def __init__(self, schema):
        Api.__init__(self, schema.catalog)
        self.schema = schema

    def table(self, name):
        """A specific table for this schema."""
        return self.schema.table(name)

    def GET_body(self, conn, cur, uri):
        schema = self.schema.GET_body(conn, cur, uri)
        return schema.tables.values()

    def GET_post_commit(self, tables):
        self.set_http_etag( self.catalog.manager._model_version )
        self.emit_headers()
        if self.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return ''
        else:
            web.header('Content-Type', 'application/json')
            response = json.dumps([ table.prejson() for table in tables ], indent=2) + '\n'
            web.header('Content-Length', len(response))
            return response

    def GET(self, uri):
        return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), self.GET_post_commit)

    def POST(self, uri):
        """Add a new table to the schema according to input resource representation."""
        try:
            tabledoc = json.load(web.ctx.env['wsgi.input'])
        except:
            raise exception.rest.BadRequest('Could not deserialize JSON input.')

        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            schema = self.schema.GET_body(conn, cur, uri)
            try:
                return ermrest.model.Table.create_fromjson(conn, cur, schema, tabledoc, web.ctx.ermrest_config)
            except (exception.ConflictData), te:
                raise exception.rest.Conflict(str(te))

        def post_commit(table):
            web.ctx.status = '201 Created'
            return self.GET_post_commit([table])

        return self.perform(body, post_commit)

def post_commit_200_OK(ignore):
    web.ctx.status = '200 OK'
    return ''

def post_commit_200_or_201(created):
    if created:
        web.ctx.status = '201 Created'
    else:
        web.ctx.status = '200 OK'
    return ''

class Comment (Api):
    """A specific object's comment.

       This is a hack to reuse code for Table and Column comment handling.
    """
    
    supported_content_types = ['text/plain']
    default_content_type = supported_content_types[0]

    def __init__(self, catalog):
        Api.__init__(self, catalog)

    def GET_body(self, conn, cur, uri):
        """Must return a tuple with final element being object that is commented"""
        raise NotImplementedError()

    def GET(self, uri):
        content_type = negotiated_content_type(self.supported_content_types, self.default_content_type)

        def post_commit(results):
            obj = results[-1]

            if obj.comment is None:
                raise exception.rest.NotFound('comment on "%s"' % obj)

            self.set_http_etag( self.catalog.manager._model_version )
            self.emit_headers()
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return ''
            else:
                web.header('Content-Type', content_type)
                response = obj.comment is not None and (str(obj.comment) + '\n') or ''
                web.header('Content-Length', len(response))
                return response

        return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), post_commit)

    def SET_body(self, conn, cur, getresults, comment):
        raise NotImplementedError()

    def PUT(self, uri):
        comment = web.ctx.env['wsgi.input'].read()

        def body(conn, cur):
            self.SET_body(conn, cur, self.GET_body(conn, cur, uri), comment)

        return self.perform(body, post_commit_200_OK)
    
    def DELETE(self, uri):
        def body(conn, cur):
            self.SET_body(conn, cur, self.GET_body(conn, cur, uri), None)

        return self.perform(body, post_commit_200_OK)       

class TableComment (Comment):
    """A specific table's comment."""
    
    def __init__(self, table):
        Comment.__init__(self, table.schema.catalog)
        self.table = table

    def GET_body(self, conn, cur, uri):
        return ( self.table.GET_body(conn, cur, uri), )

    def SET_body(self, conn, cur, getresults, comment):
        table = getresults[0]
        table.set_comment(conn, cur, comment)


class ColumnComment (TableComment):
    """A specific column's comment."""
    
    def __init__(self, column):
        TableComment.__init__(self, column.table)
        self.column = column

    def GET_body(self, conn, cur, uri):
        table = TableComment.GET_body(self, conn, cur, uri)[0]
        try:
            return (table, table.columns[str(self.column.name)])
        except KeyError:
            raise exception.rest.NotFound('column "%s"' % self.column.name)

    def SET_body(self, conn, cur, getresults, comment):
        table, column = getresults
        table.set_column_comment(conn, cur, column, comment)

class Annotations (Api):

    supported_content_types = ['application/json']
    default_content_type = supported_content_types[0]

    def __init__(self, catalog, subject):
        Api.__init__(self, catalog)
        self.subject = subject
        self.key = None

    def annotation(self, key):
        self.key = key
        return self

    def GET_body(self, conn, cur, uri):
        """Must return tuple with resolved subject as final element"""
        raise NotImplementedError()

    def GET(self, uri):
        content_type = negotiated_content_type(self.supported_content_types, self.default_content_type)

        def post_commit(results):
            subject = results[-1]

            if self.key is None:
                # getting list of all annotations
                response = json.dumps(subject.annotations)
            else:
                # getting single annotation by key
                if self.key not in subject.annotations:
                    raise exception.rest.NotFound('annotation "%s" on "%s"' % (self.key, subject))
                response = json.dumps(subject.annotations[self.key])

            response = response + '\n'

            self.set_http_etag( self.catalog.manager._model_version )
            self.emit_headers()
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return ''
            else:
                web.header('Content-Type', content_type)
                web.header('Content-Length', len(response))
                return response

        return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), post_commit)

    def PUT_body(self, conn, cur, getresults, key, value):
        """Return True for created or False for updated."""
        subject = getresults[-1]
        oldval = subject.set_annotation(conn, cur, key, value)
        if oldval is None:
            return True
        else:
            return False

    def PUT(self, uri):
        if self.key is None:
            raise exception.rest.NoMethod('PUT only supported on individually keyed annotations')

        value = web.ctx.env['wsgi.input'].read()

        try:
            value = json.loads(value)
        except:
            raise exception.BadRequest('invalid JSON input')

        def body(conn, cur):
            self.PUT_body(conn, cur, self.GET_body(conn, cur, uri), self.key, value)

        return self.perform(body, post_commit_200_or_201)
    
    def DELETE_body(self, conn, cur, getresults, key):
        subject = getresults[-1]
        subject.delete_annotation(conn, cur, key)

    def DELETE(self, uri):
        if self.key is None:
            raise exception.rest.NoMethod('DELETE only supported on individually keyed annotations')

        def body(conn, cur):
            getresults = self.GET_body(conn, cur, uri)
            subject = getresults[-1]
            if self.key not in subject.annotations:
                raise exception.rest.NotFound('annotation "%s" on "%s"' % (self.key, subject))
            
            self.DELETE_body(conn, cur, getresults, self.key)

        return self.perform(body, post_commit_200_OK)       


class TableAnnotations (Annotations):

    def __init__(self, table):
        Annotations.__init__(self, table.schema.catalog, table)

    def GET_body(self, conn, cur, uri):
        """Must return tuple with resolved subject as final element"""
        return ( self.subject.GET_body(conn, cur, uri), )


class ColumnAnnotations (TableAnnotations):

    def __init__(self, column):
        TableAnnotations.__init__(self, column.table)
        self.column = column

    def GET_body(self, conn, cur, uri):
        """Must return tuple with resolved subject as final element"""
        table = TableAnnotations.GET_body(self, conn, cur, uri)[-1]
        try:
            return (table, table.columns[str(self.column.name)])
        except KeyError:
            raise exception.rest.NotFound('column "%s"' % self.column.name)

class ForeignkeyReferenceAnnotations (Annotations):

    def __init__(self, fkrs):
        Annotations.__init__(self, fkrs.catalog, fkrs)

    def GET_body(self, conn, cur, uri):
        fkrs = self.subject.GET_body(conn, cur, uri)
        if len(fkrs) != 1:
            raise NotImplementedError('ForeignkeyReferencesAnnotations on %d fkrs' % len(fkrs))
        return (fkrs[0], )

class Table (Api):
    """A specific table by name."""
    
    supported_content_types = ['application/json', 'text/html']
    default_content_type = supported_content_types[0]

    def __init__(self, schema, name, catalog=None):
        if catalog is None:
            self.catalog = schema.catalog
        else:
            self.catalog = catalog
        Api.__init__(self, self.catalog)
        self.schema = schema
        self.name = name

    def comment(self):
        """The comment for this table."""
        return TableComment(self)

    def annotations(self):
        return TableAnnotations(self)

    def columns(self):
        """The column set for this table."""
        return Columns(self)

    def keys(self):
        """The key set for this table."""
        return Keys(self)

    def key(self, column_set):
        """A specific key for this table."""
        return Key(self, column_set, catalog=self.catalog)

    def foreignkeys(self):
        """The foreign key set for this table."""
        return Foreignkeys(self)

    def foreignkey(self, column_set):
        """A specific foreign key for this table."""
        return Foreignkey(self, column_set, catalog=self.catalog)

    def GET_body(self, conn, cur, uri):
        self.catalog.resolve(cur)
        self.enforce_content_read(cur, uri)
        model = self.catalog.manager.get_model(cur)
        return model.lookup_table(
            self.schema and str(self.schema.name) or None, 
            str(self.name)
            )

    def GET_post_commit(self, table):
        self.set_http_etag( self.catalog.manager._model_version )
        self.emit_headers()
        if self.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return ''
        else:
            web.header('Content-Type', 'application/json')
            response = json.dumps(table.prejson(), indent=2) + '\n'
            web.header('Content-Length', len(response))
            return response

    def GET(self, uri):
        content_type = negotiated_content_type(self.supported_content_types, self.default_content_type)
        
        """Get table resource representation."""
        if content_type == 'text/html':
            # return static AJAX page
            web.header('Content-Type', content_type)
            return schema_html % (dict(ready='initTable'))
        else:
            return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), self.GET_post_commit)

    def POST(self, uri):
        # give more helpful error message
        raise exception.rest.NoMethod('create tables at the table collection resource instead')

    def DELETE(self, uri):
        """Delete a table from the schema."""
        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            table = self.GET_body(conn, cur, uri)
            table.schema.delete_table(conn, cur, str(self.name))
            
        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)
        
class Columns (Api):
    """A column set."""
    def __init__(self, table):
        Api.__init__(self, table.schema.catalog)
        self.table = table

    def column(self, name):
        """A specific column for this table."""
        return Column(self.table, name)

    def GET_body(self, conn, cur, uri):
        return self.table.GET_body(conn, cur, uri).columns_in_order()

    def GET_post_commit(self, columns):
        self.set_http_etag( self.catalog.manager._model_version )
        self.emit_headers()
        if self.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return ''
        else:
            web.header('Content-Type', 'application/json')
            response = json.dumps([ c.prejson() for c in columns ], indent=2) + '\n'
            web.header('Content-Length', len(response))
            return response

    def GET(self, uri):
        return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), self.GET_post_commit)

    def POST(self, uri):
        """Add a new column to the table according to input resource representation."""
        
        try:
            columndoc = json.load(web.ctx.env['wsgi.input'])
        except:
            raise exception.rest.BadRequest('Could not deserialize JSON input.')

        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            table = self.table.GET_body(conn, cur, uri)
            return table.add_column(conn, cur, columndoc, web.ctx.ermrest_config)

        def post_commit(column):
            web.ctx.status = '201 Created'
            return self.GET_post_commit([column])

        return self.perform(body, post_commit)

class Column (Columns):
    """A specific column by name."""
    def __init__(self, table, name):
        Columns.__init__(self, table)
        self.name = name

    def comment(self):
        return ColumnComment(self)

    def annotations(self):
        return ColumnAnnotations(self)

    def GET_post_commit(self, columns):
        columns = dict([ (c.name, c) for c in columns ])
        column_name = str(self.name)
        if column_name not in columns:
            raise exception.rest.NotFound('column "%s"' % column_name)
        else:
            column = columns[column_name]

        self.set_http_etag( self.catalog.manager._model_version )
        self.emit_headers()
        if self.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return ''
        else:
            web.header('Content-Type', 'application/json')
            response = json.dumps(column.prejson(), indent=2) + '\n'
            web.header('Content-Length', len(response))
            return response

    def POST(self, uri):
        # turn off inherited POST method from Columns superclass
        raise exception.rest.NoMethod('create columns at the column collection resource instead')

    def DELETE(self, uri):
        """Delete column from table."""
        
        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            table = self.table.GET_body(conn, cur, uri)
            table.delete_column(conn, cur, str(self.name))

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

class Keys (Api):
    """A set of keys."""
    def __init__(self, table, catalog=None):
        if catalog is None:
            catalog = table.schema.catalog
        Api.__init__(self, catalog)
        self.table = table

    def GET_body(self, conn, cur, uri):
        return self.table.GET_body(conn, cur, uri).uniques.values()

    def GET_post_commit(self, keys):
        self.set_http_etag( self.catalog.manager._model_version )
        self.emit_headers()
        if self.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return ''
        else:
            web.header('Content-Type', 'application/json')
            response = json.dumps([ key.prejson() for key in keys ], indent=2) + '\n'
            web.header('Content-Length', len(response))
            return response

    def GET(self, uri):
        return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), self.GET_post_commit)
        
    def POST(self, uri):
        """Add a new key to the table according to input resource representation."""
        try:
            keydoc = json.load(web.ctx.env['wsgi.input'])
        except:
            raise exception.rest.BadRequest('Could not deserialize JSON input.')
        
        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            table = self.table.GET_body(conn, cur, uri)
            return list(table.add_unique(conn, cur, keydoc))

        def post_commit(newkeys):
            web.ctx.status = '201 Created'
            return self.GET_post_commit(newkeys)

        return self.perform(body, post_commit)

class Key (Keys):
    """A specific key by column set."""
    def __init__(self, table, column_set, catalog=None):
        Keys.__init__(self, table, catalog)
        self.columns = column_set

    def GET_body(self, conn, cur, uri):
        table = self.table.GET_body(conn, cur, uri)
        try:
            cols = [ table.columns[str(c)] for c in self.columns ]
        except (KeyError), te:
            raise exception.rest.NotFound('column "%s"' % str(te))
        fs = frozenset(cols)
        if fs not in table.uniques:
            raise exception.rest.NotFound('key (%s)' % (','.join([ str(c) for c in cols])))
        return table, table.uniques[fs]
        
    def GET_post_commit(self, tup):
        table, key = tup
        self.set_http_etag( self.catalog.manager._model_version )
        self.emit_headers()
        if self.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return ''
        else:
            web.header('Content-Type', 'application/json')
            response = json.dumps(key.prejson(), indent=2) + '\n'
            web.header('Content-Length', len(response))
            return response

    def DELETE(self, uri):
        """Delete a key constraint from a table."""
        
        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            table, key = self.GET_body(conn, cur, uri)
            table.delete_unique(conn, cur, key)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

class Foreignkeys (Api):
    """A set of foreign keys."""
    def __init__(self, table):
        Api.__init__(self, table.schema.catalog)
        self.table = table

    def GET_body(self, conn, cur, uri):
        return self.table.GET_body(conn, cur, uri)

    def GET(self, uri):
        def post_commit(table):
            self.set_http_etag( self.catalog.manager._model_version )
            self.emit_headers()
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return ''
            else:
                fkeys = table.fkeys
                response = []
                for fk in fkeys.values():
                    response.extend( fk.prejson() )
                response = json.dumps(response, indent=2) + '\n'
                web.header('Content-Type', 'application/json')
                web.header('Content-Length', len(response))
                return response
            
            return json.dumps(response, indent=2) + '\n'

        return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), post_commit)

    def POST(self, uri):
        """Add a new foreign-key reference to table according to input resource representation."""
        try:
            keydoc = json.load(web.ctx.env['wsgi.input'])
        except:
            raise exception.rest.BadRequest('Could not deserialize JSON input.')
        
        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            table = self.table.GET_body(conn, cur, uri)
            return list(table.add_fkeyref(conn, cur, keydoc))

        def post_commit(newrefs):
            web.ctx.status = '201 Created'
            return json.dumps([ r.prejson() for r in newrefs ], indent=2) + '\n'

        return self.perform(body, post_commit)

class Foreignkey (Api):
    """A specific foreign key by column set."""
    def __init__(self, table, column_set, catalog=None):
        if catalog is None:
            catalog = table.schema.catalog
        Api.__init__(self, catalog)
        self.table = table
        self.columns = column_set

    def references(self):
        """A set of foreign key references from this foreign key."""
        return ForeignkeyReferences(self.table.schema.catalog).with_from_key(self)
    
    def GET_body(self, conn, cur, uri):
        table = self.table.GET_body(conn, cur, uri)
        try:
            cols = [ table.columns[str(c)] for c in self.columns ]
        except (KeyError), te:
            raise exception.rest.NotFound('column "%s"' % str(te))
        fs = frozenset(cols)
        if fs not in table.fkeys:
            raise exception.rest.NotFound('foreign key (%s)' % (','.join([ str(c) for c in cols])))
        return table, table.fkeys[fs]

    def GET(self, uri):
        def post_commit(tup):
            self.set_http_etag( self.catalog.manager._model_version )
            self.emit_headers()
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return ''
            else:
                table, fkey = tup
                response = json.dumps(fkey.prejson(), indent=2) + '\n'
                web.header('Content-Type', 'application/json')
                web.header('Content-Length', len(response))
                return response

        return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), post_commit)

class ForeignkeyReferences (Api):
    """A set of foreign key references."""
    def __init__(self, catalog):
        Api.__init__(self, catalog)
        self.catalog = catalog
        self._from_table = None
        self._from_key = None
        self._to_table = None
        self._to_key = None

    # currently unused but might be useful to retain?
    def with_from_table(self, from_table):
        """Refine reference set with referencing table information."""
        self._from_table = from_table
        return self

    def with_from_table_name(self, from_table_name):
        """Refine reference set with referencing table information."""
        if len(from_table_name) == 2:
            sname, tname = from_table_name
        elif len(from_table_name) == 1:
            sname, tname = None, from_table_name
        else:
            raise ValueError('Invalid qualified table name: %s' % ':'.join(from_table_name))
        self._from_table = Table(sname, tname, catalog=self.catalog)
        return self

    def with_from_key(self, from_key):
        """Refine reference set with foreign key information."""
        self._from_key = from_key
        return self

    # currently unused but might be useful to retain?
    def with_from_columns(self, from_columns):
        """Refine reference set with foreign key column information."""
        assert self._from_table
        return self.with_from_key(self._from_table.foreignkey(from_columns))

    # currently unused but might be useful to retain?
    def with_to_table(self, to_table):
        """Refine reference set with referenced table information."""
        self._to_table = to_table
        return self

    def with_to_table_name(self, to_table_name):
        """Refine reference set with referenced table information."""
        if len(to_table_name) == 2:
            sname, tname = to_table_name
        elif len(to_table_name) == 1:
            sname, tname = None, to_table_name
        else:
            raise ValueError('Invalid qualified table name: %s' % ':'.join(to_table_name))
        self._to_table = Table(sname and Schema(self.catalog, sname), tname, catalog=self.catalog)
        return self

    def with_to_key(self, to_key):
        """Refine reference set with referenced key information."""
        self._to_key = to_key
        return self

    def with_to_columns(self, to_columns):
        """Refine reference set with referenced column information."""
        assert self._to_table
        return self.with_to_key( self._to_table.key(to_columns) )

    def annotations(self):
        return ForeignkeyReferenceAnnotations(self)

    def GET_body(self, conn, cur, uri):
        from_table, from_key = None, None
        to_table, to_key = None, None

        # get real ermrest.model instances...
        if self._from_key:
            from_table, from_key = self._from_key.GET_body(conn, cur, uri)
        elif self._from_table:
            from_table = self._from_table.GET_body(conn, cur, uri)

        if self._to_key:
            to_table, to_key = self._to_key.GET_body(conn, cur, uri)
        elif self._to_table:
            to_table = self._to_table.GET_body(conn, cur, uri)

        # find matching foreign key references...
        if from_table:
            fkrs = []
            for fk in from_table.fkeys.values():
                for rt in fk.table_references.keys():
                    fkrs.extend( fk.table_references[rt] )

            if from_key:
                # filter by foreign key
                fkrs = [ fkr for fkr in fkrs if fkr.foreign_key == from_key ]

            if to_table:
                # filter by to_table
                fkrs = [ fkr for fkr in fkrs if fkr.unique.table == to_table ]
                if to_key:
                    # filter by to_key
                    fkrs = [ fkr for fkr in fkrs if fkr.unique == to_key ]

        else:
            # since from_table is absent, we must have to_table info...
            assert to_table
            fkrs = []
            for u in to_table.uniques.values():
                for rt in u.table_references.keys():
                    fkrs.extend( u.table_references[rt] )

            if to_key:
                # filter by to_key
                fkrs = [ fkr for fkr in fkrs if fkr.unique == to_key ]

        return fkrs
        

    def GET(self, uri):
        def post_commit(fkrs):
            self.set_http_etag( self.catalog.manager._model_version )
            self.emit_headers()
            if self.http_is_cached():
                web.ctx.status = '304 Not Modified'
                return ''
            else:
                if self._from_key and self._to_key:
                    assert len(fkrs) == 1
                    response = fkrs[0].prejson()
                else:
                    response = [ fkr.prejson() for fkr in fkrs ]
                response = json.dumps(response, indent=2) + '\n'
                web.header('Content-Type', 'application/json')
                web.header('Content-Length', len(response))
                return response

        return self.perform(lambda conn, cur: self.GET_body(conn, cur, uri), post_commit)

    def DELETE(self, uri):
        """Delete foreign-key reference constraint from table."""
        
        def body(conn, cur):
            self.catalog.resolve(cur)
            self.enforce_schema_write(cur, uri)
            fkrs = self.GET_body(conn, cur, uri)
            for fkr in fkrs:
                fkr.foreign_key.table.delete_fkeyref(conn, cur, fkr)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

