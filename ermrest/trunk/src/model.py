
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

"""
A database introspection layer.

At present, the capabilities of this module are limited to introspection of an 
existing database model. This module does not attempt to capture all of the 
details that could be found in an entity-relationship model or in the standard 
information_schema of a relational database. It represents the model as 
needed by other modules of the ermrest project.
"""

from ermrest import exception

import urllib
import json

__all__ = ["introspect", "Model", "Schema", "Table", "Column", "Type", "sql_ident"]

def frozendict (d):
    """Convert a dictionary to a canonical and immutable form."""
    items = d.items()
    items.sort() # sort by key, value pair
    return tuple(items)
        

def introspect(conn):
    """Introspects a Catalog (i.e., a database).
    
    This function (currently) does not attempt to catch any database 
    (or other) exceptions.
    
    The 'conn' parameter must be an open connection to a database.
    
    Returns the introspected Model instance.
    """
    
    # Select all column metadata from database, excluding system schemas
    SELECT_COLUMNS = '''
SELECT 
   c.table_catalog, 
   c.table_schema, 
   c.table_name, 
   array_agg(c.column_name::text ORDER BY c.ordinal_position) AS column_names, 
   array_agg(c.column_default::text ORDER BY c.ordinal_position) AS default_values, 
   array_agg(c.data_type::text ORDER BY c.ordinal_position) AS data_types, 
   array_agg(e.data_type::text ORDER BY c.ordinal_position) AS element_types
FROM information_schema.columns c 
LEFT JOIN information_schema.element_types e
  ON ((c.table_catalog, c.table_schema, c.table_name, 'TABLE', c.dtd_identifier)
       = (e.object_catalog, e.object_schema, e.object_name, e.object_type, e.collection_type_identifier))
WHERE c.table_schema NOT IN ('information_schema', 'pg_catalog')
GROUP BY 
   c.table_catalog, 
   c.table_schema, 
   c.table_name
    '''
    
    # Select the unique or primary key columns
    PKEY_COLUMNS = '''
SELECT
   k_c_u.constraint_schema,
   k_c_u.constraint_name,
   k_c_u.table_schema,
   k_c_u.table_name,
   array_agg(k_c_u.column_name::text) AS column_names
FROM information_schema.key_column_usage AS k_c_u
JOIN information_schema.table_constraints AS t_c
ON k_c_u.constraint_schema = t_c.constraint_schema
   AND k_c_u.constraint_name = t_c.constraint_name 
WHERE t_c.constraint_type IN ('UNIQUE', 'PRIMARY KEY')
GROUP BY 
   k_c_u.constraint_schema, k_c_u.constraint_name,
   k_c_u.table_schema, k_c_u.table_name
;
    '''

    # Select the foreign key reference columns
    #
    # The following query was adapted from an example here:
    # http://msdn.microsoft.com/en-us/library/aa175805%28SQL.80%29.aspx
    FKEY_COLUMNS = '''
SELECT
   kcu1.constraint_schema AS fk_constraint_schema,
   kcu1.constraint_name AS fk_constraint_name,
   kcu1.table_schema AS fk_table_schema,
   kcu1.table_name AS fk_table_name,
   array_agg(kcu1.column_name::text ORDER BY kcu1.ordinal_position) AS fk_column_names,
   kcu2.table_schema AS uq_table_schema,
   kcu2.table_name AS uq_table_name,
   array_agg(kcu2.column_name::text ORDER BY kcu1.ordinal_position) AS uq_column_names,
   rc.delete_rule AS rc_delete_rule,
   rc.update_rule AS rc_update_rule
FROM information_schema.referential_constraints AS rc
JOIN information_schema.key_column_usage AS kcu1
  ON kcu1.constraint_catalog = rc.constraint_catalog
     AND kcu1.constraint_schema = rc.constraint_schema
     AND kcu1.constraint_name = rc.constraint_name
JOIN information_schema.key_column_usage AS kcu2
  ON kcu2.constraint_catalog = rc.unique_constraint_catalog
     AND kcu2.constraint_schema = rc.unique_constraint_schema
     AND kcu2.constraint_name = rc.unique_constraint_name
     AND kcu2.ordinal_position = kcu1.ordinal_position
GROUP BY 
   kcu1.constraint_schema, kcu1.constraint_name, 
   kcu1.table_schema, kcu1.table_name, 
   kcu2.table_schema, kcu2.table_name, 
   rc.delete_rule, rc.update_rule
;
    '''
    
    # PostgreSQL denotes array types with the string 'ARRAY'
    ARRAY_TYPE = 'ARRAY'
    
    # Dicts for quick lookup
    schemas  = dict()
    tables   = dict()
    columns  = dict()
    pkeys    = dict()
    fkeys    = dict()
    fkeyrefs = dict()

    model = Model()
    
    #
    # Introspect schemas, tables, columns
    #
    cur = conn.execute(SELECT_COLUMNS)
    for dname, sname, tname, cnames, default_values, data_types, element_types in cur:

        cols = []
        for i in range(0, len(cnames)):
            # Determine base type
            is_array = (data_types[i] == ARRAY_TYPE)
            if is_array:
                base_type = ArrayType(Type(element_types[i]))
            else:
                base_type = Type(data_types[i])
        
            # Translate default_value
            default_value = __pg_default_value(base_type, default_values[i])

            col = Column(cnames[i], i, base_type, default_value)
            cols.append( col )
            columns[(dname, sname, tname, cnames[i])] = col
        
        # Build up the model as we go without redundancy
        if (dname, sname) not in schemas:
            schemas[(dname, sname)] = Schema(model, sname)
        assert (dname, sname, tname) not in tables
        tables[(dname, sname, tname)] = Table(schemas[(dname, sname)], tname, cols)
            
    cur.close()

    #
    # Introspect uniques / primary key references, aggregated by constraint
    #
    cur = conn.execute(PKEY_COLUMNS)
    for pk_schema, pk_name, pk_table_schema, pk_table_name, pk_column_names in cur:

        pk_constraint_key = (pk_schema, pk_name)

        pk_cols = [ columns[(dname, pk_table_schema, pk_table_name, pk_column_name)]
                    for pk_column_name in pk_column_names ]

        pk_colset = frozenset(pk_cols)

        # each constraint implies a pkey but might be duplicate
        if pk_colset not in pkeys:
            pkeys[pk_colset] = Unique(pk_colset)

    cur.close()

    #
    # Introspect foreign keys references, aggregated by reference constraint
    #
    cur = conn.execute(FKEY_COLUMNS)
    for fk_schema, fk_name, fk_table_schema, fk_table_name, fk_column_names, \
            uq_table_schema, uq_table_name, uq_column_names, on_delete, on_update \
            in cur:

        fk_constraint_key = (fk_schema, fk_name)

        fk_cols = [ columns[(dname, fk_table_schema, fk_table_name, fk_column_names[i])]
                    for i in range(0, len(fk_column_names)) ]
        pk_cols = [ columns[(dname, uq_table_schema, uq_table_name, uq_column_names[i])]
                    for i in range(0, len(uq_column_names)) ]

        fk_colset = frozenset(fk_cols)
        pk_colset = frozenset(pk_cols)
        fk_ref_map = frozendict(dict([ (fk_cols[i], pk_cols[i]) for i in range(0, len(fk_cols)) ]))

        # each reference constraint implies a foreign key but might be duplicate
        if fk_colset not in fkeys:
            fkeys[fk_colset] = ForeignKey(fk_colset)

        fk = fkeys[fk_colset]
        pk = pkeys[pk_colset]

        # each reference constraint implies a foreign key reference but might be duplicate
        if fk_ref_map not in fk.references:
            fk.references[fk_ref_map] = KeyReference(fk, pk, fk_ref_map, on_delete, on_update)

    cur.close()

    return model

def __pg_default_value(base_type, raw):
    """Converts raw default value with base_type hints.
    
    This is at present sort of an ugly hack. It is definitely incomplete but 
    handles what I've seen so far.
    """
    if not raw:
        return raw
    elif raw.find("'::text") >= 0:
        return raw[1:raw.find("'::text")]
    elif raw.find('nextval') >= 0:
        return 'sequence' #TODO: or 'incremental'?
    elif base_type == 'integer' or base_type == 'bigint':
        return int(raw)
    elif base_type == 'float':
        return float(raw)
    elif raw.find('timestamp') >= 0:
        return raw #TODO: not sure what def vals apply
    else:
        return 'unknown'

def sql_ident(s):
    return '"' + s.replace('"', '""') + '"'

class Model:
    """Represents a database model.
    
    At present, this amounts to a collection of 'schemas' in the conventional
    database sense of the term.
    """
    
    def __init__(self, schemas=dict()):
        self.schemas = schemas
    
    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            schemas=dict([ 
                    (str(s), self.schemas[s].prejson()) for s in self.schemas 
                    ])
            )
        

    def lookup_table(self, sname, tname):
        if sname is not None:
            return self.schemas[sname].tables[tname]
        else:
            tables = set()

            for schema in self.schemas.values():
                if tname in schema.tables:
                    tables.add( schema.tables[tname] )

            if len(tables) == 0:
                raise exception.ConflictModel('Table %s does not exist.' % tname)
            elif len(tables) > 1:
                raise exception.ConflictModel('Table name %s is ambiguous.' % tname)
            else:
                return tables.pop()
    
class Schema:
    """Represents a database schema.
    
    At present, this has a 'name' and a collection of database 'tables'. It 
    also has a reference to its 'model'.
    """
    
    def __init__(self, model, name):
        self.model = model
        self.name = name
        self.tables = dict()
        
        if name not in self.model.schemas:
            self.model.schemas[name] = self

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            schema_name=str(self.name),
            tables=dict([
                    (str(t), self.tables[t].prejson()) for t in self.tables
                    ])
            )

class Table:
    """Represents a database table.
    
    At present, this has a 'name' and a collection of table 'columns'. It
    also has a reference to its 'schema'.
    """
    
    def __init__(self, schema, name, columns):
        self.schema = schema
        self.name = name
        self.columns = dict()
        self.uniques = dict()
        self.fkeys = dict()

        for c in columns:
            self.columns[c.name] = c
            c.table = self

        if name not in self.schema.tables:
            self.schema.tables[name] = self

    def __str__(self):
        return ':%s:%s' % (
            urllib.quote(self.schema.name),
            urllib.quote(self.name)
            )

    def __repr__(self):
        return '<ermrest.model.Table %s>' % str(self)

    def columns_in_order(self):
        cols = self.columns.values()
        cols.sort(key=lambda c: c.position)
        return cols

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            table_name=str(self.name),
            columns=[
                c.prejson() for c in self.columns_in_order()
                ],
            uniques=[
                u.prejson() for u in self.uniques.values()
                ],
            fkeys=[
                fk.prejson() for fk in self.fkeys.values()
                ]
            )

    def sql_name(self):
        return '.'.join([
                sql_ident(self.schema.name),
                sql_ident(self.name)
                ])

    def freetext_column(self):
        return FreetextColumn(self)


class Type (object):
    """Represents a column type."""
    is_array = False
    
    def __init__(self, name):
        self.name = name
    
    def __str__(self):
        return str(self.name)
    
    def sql(self):
        return self.name

    def sql_literal(self, v):
        if self.name in [ 'integer', 'int8', 'bigint' ]:
            return "%s" % int(v)
        elif self.name in [ 'float', 'float8' ]:
            return "%s" % float(v)
        else:
            # text and text-like...
            return "'" + str(v).replace("'", "''") + "'::%s" % self.sql()


class ArrayType(Type):
    """Represents a column array type."""
    is_array = True
    
    def __init__(self, base_type):
        Type.__init__(self, base_type.name + "[]")
        self.base_type = base_type
    
    def __str__(self):
        return "%s[]" % self.base_type
        
    def sql(self):
        return "%s[]" % self.base_type.sql()


class Column:
    """Represents a table column.
    
    Its fields include:
     -- name: the name of the columns
     -- position: its ordinal position in the table
     -- type: the type
     -- default_value: a kludgy attempt at translating the raw default 
                       value for this column
    
    It also has a reference to its 'table'.
    """
    
    def __init__(self, name, position, type, default_value):
        self.table = None
        self.name = name
        self.position = position
        self.type = type
        self.default_value = default_value
    
    def __str__(self):
        return ':%s:%s:%s' % (
            urllib.quote(self.table.schema.name),
            urllib.quote(self.table.name),
            urllib.quote(self.name)
            )

    def __repr__(self):
        return '<ermrest.model.Column %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            column_name=str(self.name),
            position=self.position,
            type=str(self.type),
            default_value=self.default_value
            )

    def sql_name(self):
        return sql_ident(self.name)
    
    def ddl(self):
        return "%s %s" % (
            sql_ident(self.name),
            self.type.sql()
            )

class FreetextColumn (Column):
    """Represents virtual table column for free text search.

       This is a tsvector computed by appending all text-type columns
       as a document, sorted by column order.
    """
    
    def __init__(self, table):
        self.table = table
        self.srccols = [ c for c in table.columns.itervalues() if str(c.type) == 'text' ]
        self.srccols.sort(key=lambda c: c.position)
        self.type = Type('tsvector')

    def sql_name_with_talias(self, talias):
        colnames = [ '%s.%s' % (talias, c.sql_name()) for c in self.srccols ]
        if colnames:
            return "to_tsvector('english'::regconfig, %s)" % (' || '.join([ "COALESCE(%s::text,''::text)" % name for name in colnames ]))
        else:
            return "to_tsvector('english'::regconfig, ''::text)"

class Unique:
    """A unique constraint."""
    
    def __init__(self, cols):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.table_references = dict()

        if cols not in self.table.uniques:
            self.table.uniques[cols] = self
        
    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.Unique %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            unique_columns=[
                str(c.name) for c in self.columns
                ]
            )

class ForeignKey:
    """A foreign key."""

    def __init__(self, cols):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.references = dict()
        self.table_references = dict()
        
        if cols not in self.table.fkeys:
            self.table.fkeys[cols] = self

    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.ForeignKey %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            fkey_columns=[
                str(c.name) for c in self.columns
                ],
            references=[
                fkr.prejson() for fkr in self.references.values()
                ]
            )
            

class KeyReference:
    """A reference from a foreign key to a primary key."""
    
    def __init__(self, foreign_key, unique, fk_ref_map, on_delete, on_update):
        self.foreign_key = foreign_key
        self.unique = unique
        self.reference_map = dict(fk_ref_map)
        self.referenceby_map = dict([ (p, f) for f, p in fk_ref_map ])
        self.on_delete = on_delete
        self.on_update = on_update
        # Link into foreign key's key reference list, by table ref
        if unique.table not in foreign_key.table_references:
            foreign_key.table_references[unique.table] = set()
        foreign_key.table_references[unique.table].add(self)
        if foreign_key.table not in unique.table_references:
            unique.table_references[foreign_key.table] = set()
        unique.table_references[foreign_key.table].add(self)

    def __str__(self):
        return self.verbose()

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        fks = []
        pks = []
        for fk in self.reference_map.keys():
            fks.append( str(fk) )
            pks.append( str(self.reference_map[fk]) )
        return dict(
            foreign_key_columns=fks,
            referenced_columns=pks
            )

    def __repr__(self):
        return '<ermrest.model.KeyReference %s>' % str(self)


if __name__ == '__main__':
    import os, sanepg2
    connstr = "dbname=%s user=%s" % \
        (os.getenv('TEST_DBNAME', 'test'), os.getenv('TEST_USER', 'test'))
    m = introspect(sanepg2.connection(connstr))
    print m.verbose()
    exit(0)
