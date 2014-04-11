
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

def model_body(conn):
    return ermrest.model.introspect(conn)

class Schemas (Api):
    """A schema set."""
    def __init__(self, catalog):
        Api.__init__(self, catalog)
        
    def GET(self, uri):
        """HTTP GET for Schemas of a Catalog."""
        def post_commit(model):
            return json.dumps(model.prejson(), indent=2) + '\n'

        return self.perform(model_body, post_commit)

def schema_body(conn, schema_name):
    model = model_body(conn)
    if schema_name not in model.schemas:
        raise exception.NotFound('schema "%s"' % schema_name)
    else:
        return model.schemas[schema_name]

class Schema (Api):
    """A specific schema by name."""
    def __init__(self, catalog, name):
        Api.__init__(self, catalog)
        self.name = name

    def tables(self):
        """The table set for this schema."""
        return Tables(self)

    def table(self, name):
        """A specific table for this schema."""
        return Table(self, name)

    def GET_body(self, conn):
        model = model_body(conn)
        return model.lookup_schema(str(self.name))

    def GET(self, uri):
        """HTTP GET for Schemas of a Catalog."""
        def post_commit(schema):
            return json.dumps(schema.prejson(), indent=2) + '\n'

        return self.perform(self.GET_body, post_commit)

class Tables (Api):
    """A table set."""
    def __init__(self, schema):
        Api.__init__(self, schema.catalog)
        self.schema = schema

    def table(self, name):
        """A specific table for this schema."""
        return self.schema.table(name)

    def GET(self, uri):
        return self.schema.GET(uri)

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

    def columns(self):
        """The column set for this table."""
        return Columns(self)

    def column(self, name):
        """A specific column for this table."""
        return Column(self, name)

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
        return Foreignkey(self, column_set)

    def references(self):
        """A set of foreign key references from this table."""
        return ForeignkeyReferences(self.schema.catalog).with_from_table(self)

    def referencedbys(self):
        """A set of foreign key references to this table."""
        return ForeignkeyReferences(self.schema.catalog).with_to_table(self)

    def GET_body(self, conn):
        model = model_body(conn)
        return model.lookup_table(
            self.schema and str(self.schema.name) or None, 
            str(self.name)
            )

    def GET(self, uri):
        def post_commit(table):
            return json.dumps(table.prejson(), indent=2) + '\n'

        return self.perform(self.GET_body, post_commit)

class Columns (Api):
    """A column set."""
    def __init__(self, table):
        Api.__init__(self, table.schema.catalog)
        self.table = table

    def GET_body(self, conn):
        return self.table.GET_body(conn)

    def GET_post_commit(self, table):
        return json.dumps([ c.prejson() for c in table.columns_in_order() ], indent=2) + '\n'

    def GET(self, uri):
        return self.perform(self.GET_body, self.GET_post_commit)

class Column (Columns):
    """A specific column by name."""
    def __init__(self, table, name):
        Columns.__init__(self, table)
        self.name = name

    def GET_post_commit(self, table):
        column_name = str(self.name)
        if column_name not in table.columns:
            raise exception.NotFound('column "%s"' % column_name)
        else:
            column = table.columns[column_name]
        return json.dumps(column.prejson(), indent=2) + '\n'

class Keys (Api):
    """A set of keys."""
    def __init__(self, table, catalog=None):
        if catalog is None:
            catalog = table.schema.catalog
        Api.__init__(self, catalog)
        self.table = table

    def GET_body(self, conn):
        return self.table.GET_body(conn)

    def GET_post_commit(self, table):
        return json.dumps([ key.prejson() for key in table.uniques.values() ], indent=2) + '\n'

    def GET(self, uri):
        return self.perform(self.GET_body, self.GET_post_commit)
        
class Key (Keys):
    """A specific key by column set."""
    def __init__(self, table, column_set, catalog=None):
        Keys.__init__(self, table, catalog)
        self.columns = column_set

    def referencedbys(self):
        """A set of foreign key references to this key."""
        return ForeignkeyReferences(self.table.schema.catalog).with_to_key(self)

    def GET_body(self, conn):
        table = Keys.GET_body(self, conn)
        try:
            cols = [ table.columns[str(c)] for c in self.columns ]
        except (KeyError), te:
            raise exception.NotFound('column "%s"' % str(te))
        fs = frozenset(cols)
        if fs not in table.uniques:
            raise exception.NotFound('key (%s)' % (','.join([ str(c) for c in cols])))
        return table.uniques[fs]
        
    def GET_post_commit(self, key):
        return json.dumps(key.prejson(), indent=2) + '\n'

class Foreignkeys (Api):
    """A set of foreign keys."""
    def __init__(self, table):
        Api.__init__(self, table.schema.catalog)
        self.table = table

    def GET_body(self, conn):
        return self.table.GET_body(conn)

    def GET(self, uri):
        def post_commit(table):
            fkeys = table.fkeys
            return json.dumps([ fk.prejson() for fk in fkeys.values() ], indent=2) + '\n'

        return self.perform(self.GET_body, post_commit)

class Foreignkey (Api):
    """A specific foreign key by column set."""
    def __init__(self, table, column_set):
        Api.__init__(self, table.schema.catalog)
        self.table = table
        self.columns = column_set

    def references(self):
        """A set of foreign key references from this foreign key."""
        return ForeignkeyReferences(self.table.schema.catalog).with_from_key(self)
    
    def GET_body(self, conn):
        table = self.table.GET_body(conn)
        try:
            cols = [ table.columns[str(c)] for c in self.columns ]
        except (KeyError), te:
            raise exception.NotFound('column "%s"' % str(te))
        fs = frozenset(cols)
        if fs not in table.fkeys:
            raise exception.NotFound('foreign key (%s)' % (','.join([ str(c) for c in cols])))
        return table.fkeys[fs]

    def GET(self, uri):
        def post_commit(fkey):
            return json.dumps(fkey.prejson(), indent=2) + '\n'

        return self.perform(self.GET_body, post_commit)

class ForeignkeyReferences (Api):
    """A set of foreign key references."""
    def __init__(self, catalog):
        Api.__init__(self, catalog)
        self.catalog = catalog
        self._from_table = None
        self._from_key = None
        self._to_table = None
        self._to_key = None

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
        self._from_table = Table(sname, tname)
        return self

    def with_from_key(self, from_key):
        """Refine reference set with foreign key information."""
        self._from_key = from_key
        return self

    def with_from_columns(self, from_columns):
        """Refine reference set with foreign key column information."""
        assert self._from_table
        return self.with_from_key(self._from_table.foreignkey(from_columns))

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
        self._to_table = Table(sname, tname, catalog=self.catalog)
        return self

    def with_to_key(self, to_key):
        """Refine reference set with referenced key information."""
        self._to_key = to_key
        return self

    def with_to_columns(self, to_columns):
        """Refine reference set with referenced column information."""
        assert self._to_table
        return self.with_to_key( self._to_table.key(to_columns) )

    def GET_body(self, conn):
        from_table, from_key = None, None
        to_table, to_key = None, None

        # get real ermrest.model instances...
        if self._from_table:
            from_table = self._from_table.GET_body(conn)

            if self._from_key:
                from_key = self._from_key.GET_body(conn)

        if self._to_table:
            to_table = self._to_table.GET_body(conn)

            if self._to_key:
                to_key = self._to_key.GET_body(conn)

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
            return json.dumps([ fkr.prejson() for fkr in fkrs ], indent=2) + '\n'

        return self.perform(self.GET_body, post_commit)
