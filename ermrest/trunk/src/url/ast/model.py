
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
from data import Api

class Schemas (Api):
    """A schema set."""
    def __init__(self, catalog):
        self.catalog = catalog
        
    def GET(self, uri):
        """HTTP GET for Schemas of a Catalog."""
        model = self.catalog.manager.get_model()
        schema_names = model.schemas.keys()
        return json.dumps(schema_names) + '\n'

class Schema (Api):
    """A specific schema by name."""
    def __init__(self, catalog, name):
        self.catalog = catalog
        self.name = name

    def tables(self):
        """The table set for this schema."""
        return Tables(self)

    def table(self, name):
        """A specific table for this schema."""
        return Table(self, name)

    def GET(self, uri):
        """HTTP GET for Schemas of a Catalog."""
        try:
            model = self.catalog.manager.get_model()
            schema = model.schemas[str(self.name)]
        except KeyError:
            raise exception.rest.NotFound(uri)
        
        table_names = schema.tables.keys()
        return json.dumps(table_names) + '\n'

class Tables (Api):
    """A table set."""
    def __init__(self, schema):
        self.schema = schema

    def GET(self, uri):
        return self.schema.GET(uri)

class Table (Api):
    """A specific table by name."""
    def __init__(self, schema, name):
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
        return Key(self, column_set)

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

    def GET(self, uri):
        try:
            model = self.schema.catalog.manager.get_model()
            schema = model.schemas[str(self.schema.name)]
            table = schema.tables[str(self.name)]
        except KeyError:
            raise exception.rest.NotFound(uri)

        response = dict()
        response['schema_name'] = str(schema.name)
        response['table_name'] = str(table.name)
        columns = table.columns.values()
        columns.sort(key=lambda c: c.position)
        response['column_definitions'] = [
            dict(name=str(c.name), type=str(c.type))
            for c in columns
            ]
        response['uniques'] = [
            dict(
                unique_columns=[ str(c.name) for c in ucs ],
                referenced_bys=[
                    dict( referring_table=dict( schema_name=str(rt.schema.name), table_name=str(rt.name) ),
                          unique_to_referring_maps=[
                            dict([ (str(p.name), str(f.name)) for p, f in kr.referenceby_map.items() ])
                            for kr in u.table_references[rt]
                            ]
                          )
                    for rt in u.table_references.keys()
                    ]
                )
            for ucs, u in table.uniques.items()
            ]
        response['foreign_keys'] = [
            dict(
                ref_columns=[ str(c.name) for c in fkcs ],
                references=[
                    dict( referred_table=dict( schema_name=str(rt.schema.name), table_name=str(rt.name) ),
                          referring_to_unique_maps=[
                            dict([ (str(f.name), str(p.name)) for f, p in kr.reference_map.items() ])
                            for kr in fk.table_references[rt]
                            ]
                          )
                    for rt in fk.table_references.keys()
                    ]
                )
            for fkcs, fk in table.fkeys.items()
            ]
        
        return json.dumps(response) + '\n'


class Columns (Api):
    """A column set."""
    def __init__(self, table):
        self.table = table


class Column (Api):
    """A specific column by name."""
    def __init__(self, table, name):
        self.table = table
        self.name = name


class Keys (Api):
    """A set of keys."""
    def __init__(self, table):
        self.table = table

class Key (Api):
    """A specific key by column set."""
    def __init__(self, table, column_set):
        self.table = table
        self.columns = column_set

    def referencedbys(self):
        """A set of foreign key references to this key."""
        return ForeignkeyReferences(self.table.schema.catalog).with_to_key(self)

class Foreignkeys (Api):
    """A set of foreign keys."""
    def __init__(self, table):
        self.table = table

class Foreignkey (Api):
    """A specific foreign key by column set."""
    def __init__(self, table, column_set):
        self.table = table
        self.columns = column_set

    def references(self):
        """A set of foreign key references from this foreign key."""
        return ForeignkeyReferences(self.table.schema.catalog).with_from_key(self)


class ForeignkeyReferences (Api):
    """A set of foreign key references."""
    def __init__(self, catalog):
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
        self._to_table = Table(sname, tname)
        return self

    def with_to_key(self, to_key):
        """Refine reference set with referenced key information."""
        self._to_key = to_key
        return self

    def with_to_columns(self, to_columns):
        """Refine reference set with referenced column information."""
        assert self._to_table
        return self.with_to_key( self._to_table.key(to_columns) )

