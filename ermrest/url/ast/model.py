
# 
# Copyright 2013-2015 University of Southern California
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

from ... import exception
from ... import model
from .api import Api
from ...util import negotiated_content_type

def _post_commit(handler, resource, content_type='text/plain', transform=lambda v: v):
    handler.emit_headers()
    if resource is None:
        return
    web.header('Content-Type', content_type)
    response = transform(resource)
    web.header('Content-Length', len(response))
    return response

def _post_commit_json(handler, resource):
    def prejson(v):
        if hasattr(v, 'prejson'):
            return v.prejson()
        else:
            return v
    def to_json(resource):
        if isinstance(resource, list):
            resource = [ prejson(v) for v in resource ]
        else:
            resource = prejson(resource)
        return json.dumps(resource, indent=2) + '\n'
    return _post_commit(handler, resource, 'application/json', to_json)

def _GET(handler, thunk, _post_commit):
    def body(conn, cur):
        handler.enforce_content_read(cur)
        handler.catalog.manager.get_model(cur)
        handler.set_http_etag( handler.catalog.manager._model_version )
        if handler.http_is_cached():
            web.ctx.status = '304 Not Modified'
            return None
        return thunk(conn, cur)

    return handler.perform(body, lambda resource: _post_commit(handler, resource))
    
class Schemas (Api):
    """A schema set."""
    def __init__(self, catalog):
        Api.__init__(self, catalog)

    def GET_body(self, conn, cur):
        return self.catalog.manager._model
        
    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

class Schema (Api):
    """A specific schema by name."""
    def __init__(self, catalog, name):
        Api.__init__(self, catalog)
        self.schemas = Schemas(catalog)
        self.name = name

    def tables(self):
        """The table set for this schema."""
        return Tables(self)

    def table(self, name):
        """A specific table for this schema."""
        return Table(self, name)

    def GET_body(self, conn, cur):
        model = self.catalog.manager.get_model(cur)
        try:
            return model.schemas[unicode(self.name)]
        except exception.ConflictModel:
            raise exception.NotFound(u'Schema %s not found.' % unicode(self.name))
    
    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def POST(self, uri):
        """Create a new empty schema."""
        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            model = self.catalog.manager.get_model(cur)
            model.create_schema(conn, cur, unicode(self.name))
            
        def post_commit(ignore):
            web.ctx.status = '201 Created'
            return ''

        return self.perform(body, post_commit)

    def DELETE(self, uri):
        """Delete an existing schema."""
        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            model = self.catalog.manager.get_model(cur)
            model.delete_schema(conn, cur, unicode(self.name))
            
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

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
    
    def GET_body(self, conn, cur):
        return self.schema.GET_body(conn, cur).tables.values()

    def POST(self, uri):
        """Add a new table to the schema according to input resource representation."""
        try:
            tabledoc = json.load(web.ctx.env['wsgi.input'])
        except:
            raise exception.rest.BadRequest('Could not deserialize JSON input.')

        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            schema = self.schema.GET_body(conn, cur)
            try:
                return model.Table.create_fromjson(conn, cur, schema, tabledoc, web.ctx.ermrest_config)
            except (exception.ConflictData), te:
                raise exception.rest.Conflict(str(te))

        def post_commit(table):
            web.ctx.status = '201 Created'
            return _post_commit(self, [table])

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
    def __init__(self, catalog):
        Api.__init__(self, catalog)

    def GET_subject(self, conn, cur):
        raise NotImplementedError()

    def GET_body(self, conn, cur):
        subject = self.GET_subject(conn, cur)
        if subject.comment is None:
            raise exception.rest.NotFound('comment on "%s"' % subject)
        return unicode(subject.comment) + '\n'

    def GET(self, uri):
        return _GET(self, self.GET_body, lambda response: _post_commit(self, response, 'text/plain'))

    def SET_body(self, conn, cur, getresults, comment):
        raise NotImplementedError()

    def PUT(self, uri):
        comment = web.ctx.env['wsgi.input'].read()

        def body(conn, cur):
            self.SET_body(conn, cur, self.GET_subject(conn, cur), comment)

        return self.perform(body, post_commit_200_OK)
    
    def DELETE(self, uri):
        def body(conn, cur):
            self.SET_body(conn, cur, self.GET_subject(conn, cur), None)

        return self.perform(body, post_commit_200_OK)       

class TableComment (Comment):
    """A specific table's comment."""
    
    def __init__(self, table):
        Comment.__init__(self, table.schema.catalog)
        self.table = table

    def GET_subject(self, conn, cur):
        return self.table.GET_body(conn, cur)

    def SET_body(self, conn, cur, table, comment):
        table.set_comment(conn, cur, comment)


class ColumnComment (TableComment):
    """A specific column's comment."""
    
    def __init__(self, column):
        TableComment.__init__(self, column.table)
        self.column = column

    def GET_subject(self, conn, cur):
        table = TableComment.GET_subject(self, conn, cur)
        try:
            return table.columns[unicode(self.column.name)]
        except exception.ConflictModel:
            raise exception.rest.NotFound(u'column "%s"' % self.column.name)

    def SET_body(self, conn, cur, column, comment):
        column.table.set_column_comment(conn, cur, column, comment)

class Annotations (Api):
    def __init__(self, catalog, subject):
        Api.__init__(self, catalog)
        self.subject = subject
        self.key = None

    def annotation(self, key):
        self.key = key
        return self

    def GET_subject(self, conn, cur):
        raise NotImplementedError()

    def GET_body(self, conn, cur):
        subject = self.GET_subject(conn, cur)
        if self.key is None:
            return subject.annotations
        else:
            if self.key not in subject.annotations:
                raise exception.rest.NotFound('annotation "%s" on "%s"' % (self.key, subject))
            return subject.annotations[self.key]

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def PUT_body(self, conn, cur, subject, key, value):
        """Return True for created or False for updated."""
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
            raise exception.BadData('invalid JSON input')

        def body(conn, cur):
            self.PUT_body(conn, cur, self.GET_subject(conn, cur), self.key, value)

        return self.perform(body, post_commit_200_or_201)
    
    def DELETE_body(self, conn, cur, subject, key):
        subject.delete_annotation(conn, cur, key)

    def DELETE(self, uri):
        if self.key is None:
            raise exception.rest.NoMethod('DELETE only supported on individually keyed annotations')

        def body(conn, cur):
            subject = self.GET_subject(conn, cur)
            if self.key not in subject.annotations:
                raise exception.rest.NotFound('annotation "%s" on "%s"' % (self.key, subject))
            
            self.DELETE_body(conn, cur, subject, self.key)

        return self.perform(body, post_commit_200_OK)       


class TableAnnotations (Annotations):

    def __init__(self, table):
        Annotations.__init__(self, table.schema.catalog, table)

    def GET_subject(self, conn, cur):
        return self.subject.GET_body(conn, cur)


class ColumnAnnotations (TableAnnotations):

    def __init__(self, column):
        TableAnnotations.__init__(self, column.table)
        self.column = column

    def GET_subject(self, conn, cur):
        table = TableAnnotations.GET_subject(self, conn, cur)
        try:
            return table.columns[unicode(self.column.name)]
        except KeyError:
            raise exception.rest.NotFound(u'column "%s"' % self.column.name)

class ForeignkeyReferenceAnnotations (Annotations):

    def __init__(self, fkrs):
        Annotations.__init__(self, fkrs.catalog, fkrs)

    def GET_subject(self, conn, cur):
        fkrs = self.subject.GET_body(conn, cur)
        if len(fkrs) != 1:
            raise NotImplementedError('ForeignkeyReferencesAnnotations on %d fkrs' % len(fkrs))
        return fkrs[0]

class Table (Api):
    """A specific table by name."""
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

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
    
    def GET_body(self, conn, cur):
        model = self.catalog.manager._model
        if self.schema is not None:
            schema = self.schema.GET_body(conn, cur)
        try:
            if self.schema is not None:
                return schema.tables[unicode(self.name)]
            else:
                return model.lookup_table(unicode(self.name))
        except exception.ConflictModel, e:
            raise exception.NotFound(str(e))

    def POST(self, uri):
        # give more helpful error message
        raise exception.rest.NoMethod('create tables at the table collection resource instead')

    def DELETE(self, uri):
        """Delete a table from the schema."""
        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            table = self.GET_body(conn, cur)
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

    def GET_body(self, conn, cur):
        return self.table.GET_body(conn, cur).columns_in_order()

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
    
    def POST(self, uri):
        """Add a new column to the table according to input resource representation."""
        
        try:
            columndoc = json.load(web.ctx.env['wsgi.input'])
        except:
            raise exception.rest.BadRequest('Could not deserialize JSON input.')

        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            table = self.table.GET_body(conn, cur)
            return table.add_column(conn, cur, columndoc, web.ctx.ermrest_config)

        def post_commit(column):
            web.ctx.status = '201 Created'
            return _post_commit(self, [column])

        return self.perform(body, post_commit)

class Column (Api):
    """A specific column by name."""
    def __init__(self, table, name):
        Api.__init__(self, table.schema.catalog)
        self.table = table
        self.name = name

    def comment(self):
        return ColumnComment(self)

    def annotations(self):
        return ColumnAnnotations(self)

    def GET_body(self, conn, cur):
        return self.table.GET_body(conn, cur).columns[unicode(self.name)]
    
    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
    
    def POST(self, uri):
        # turn off inherited POST method from Columns superclass
        raise exception.rest.NoMethod('create columns at the column collection resource instead')

    def DELETE(self, uri):
        """Delete column from table."""
        
        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            table = self.table.GET_body(conn, cur)
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

    def GET_body(self, conn, cur):
        return self.table.GET_body(conn, cur).uniques.values()

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
        
    def POST(self, uri):
        """Add a new key to the table according to input resource representation."""
        try:
            keydoc = json.load(web.ctx.env['wsgi.input'])
        except:
            raise exception.rest.BadRequest('Could not deserialize JSON input.')
        
        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            table = self.table.GET_body(conn, cur)
            return list(table.add_unique(conn, cur, keydoc))

        def post_commit(newkeys):
            web.ctx.status = '201 Created'
            return _post_commit(self, newkeys)

        return self.perform(body, post_commit)

class Key (Keys):
    """A specific key by column set."""
    def __init__(self, table, column_set, catalog=None):
        Keys.__init__(self, table, catalog)
        self.columns = column_set

    def GET_body(self, conn, cur):
        table = self.table.GET_body(conn, cur)
        cols = frozenset([ table.columns[str(c)] for c in self.columns ])
        if cols not in table.uniques:
            raise exception.rest.NotFound(u'key (%s)' % (u','.join([ unicode(c) for c in cols])))
        return table.uniques[cols]
        
    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def DELETE(self, uri):
        """Delete a key constraint from a table."""
        
        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            table, key = self.GET_body(conn, cur)
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

    def GET_body(self, conn, cur):
        return self.table.GET_body(conn, cur).fkeys.values()
        
    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
        
    def POST(self, uri):
        """Add a new foreign-key reference to table according to input resource representation."""
        try:
            keydoc = json.load(web.ctx.env['wsgi.input'])
        except:
            raise exception.rest.BadRequest('Could not deserialize JSON input.')
        
        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            table = self.table.GET_body(conn, cur)
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

    def GET_body(self, conn, cur):
        table = self.table.GET_body(conn, cur)
        cols = frozenset([ table.columns[str(c)] for c in self.columns ])
        if cols not in table.fkeys:
            raise exception.rest.NotFound(u'foreign key (%s)' % (u','.join([ unicode(c) for c in cols])))
        return table.fkeys[cols]
    
    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
    
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

    def GET_body(self, conn, cur):
        from_table, from_key = None, None
        to_table, to_key = None, None

        # get real ermrest.model instances...
        if self._from_key:
            from_key = self._from_key.GET_body(conn, cur)
            from_table = from_key.table
        elif self._from_table:
            from_table = self._from_table.GET_body(conn, cur)

        if self._to_key:
            to_key = self._to_key.GET_body(conn, cur)
            to_table = to_key.table
        elif self._to_table:
            to_table = self._to_table.GET_body(conn, cur)

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
        return _GET(self, self.GET_body, _post_commit_json)

    def DELETE(self, uri):
        """Delete foreign-key reference constraint from table."""
        
        def body(conn, cur):
            self.enforce_schema_write(cur, uri)
            fkrs = self.GET_body(conn, cur)
            for fkr in fkrs:
                fkr.foreign_key.table.delete_fkeyref(conn, cur, fkr)

        def post_commit(ignore):
            web.ctx.status = '204 No Content'
            return ''

        return self.perform(body, post_commit)

