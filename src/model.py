
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
from ermrest.util import sql_identifier, sql_literal

import urllib
import json
import re

__all__ = ["introspect", "Model", "Schema", "Table", "Column", "Type"]

def frozendict (d):
    """Convert a dictionary to a canonical and immutable form."""
    items = d.items()
    items.sort() # sort by key, value pair
    return tuple(items)
        

def introspect(cur):
    """Introspects a Catalog (i.e., a database).
    
    This function (currently) does not attempt to catch any database 
    (or other) exceptions.
    
    The 'conn' parameter must be an open connection to a database.
    
    Returns the introspected Model instance.
    """
    
    # this postgres-specific code borrows bits from its information_schema view definitions
    # but is trimmed down to be a cheaper query to execute

    # Select all column metadata from database, excluding system schemas
    SELECT_TABLES = '''
SELECT
  current_database() AS table_catalog,
  nc.nspname AS table_schema,
  c.relname AS table_name
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace nc ON (c.relnamespace = nc.oid)
LEFT JOIN pg_catalog.pg_attribute a ON (a.attrelid = c.oid)
WHERE nc.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
  AND NOT pg_is_other_temp_schema(nc.oid) 
  AND (c.relkind = ANY (ARRAY['r'::"char", 'v'::"char", 'f'::"char"])) 
  AND (pg_has_role(c.relowner, 'USAGE'::text) OR has_column_privilege(c.oid, a.attnum, 'SELECT, INSERT, UPDATE, REFERENCES'::text))
GROUP BY nc.nspname, c.relname
    '''
    
    SELECT_COLUMNS = '''
SELECT
  current_database() AS table_catalog,
  nc.nspname AS table_schema,
  c.relname AS table_name,
  array_agg(a.attname::text ORDER BY a.attnum) AS column_names,
  array_agg(pg_get_expr(ad.adbin, ad.adrelid)::text ORDER BY a.attnum) AS default_values,
  array_agg(
    CASE
      WHEN t.typtype = 'd'::"char" THEN
        CASE
          WHEN bt.typelem <> 0::oid AND bt.typlen = (-1) THEN 'ARRAY'::text
          WHEN nbt.nspname = 'pg_catalog'::name THEN format_type(t.typbasetype, NULL::integer)
          ELSE 'USER-DEFINED'::text
        END
      ELSE
        CASE
          WHEN t.typelem <> 0::oid AND t.typlen = (-1) THEN 'ARRAY'::text
          WHEN nt.nspname = 'pg_catalog'::name THEN format_type(a.atttypid, NULL::integer)
          ELSE 'USER-DEFINED'::text
        END
    END::text
    ORDER BY a.attnum) AS data_types,
  array_agg(
    CASE
      WHEN t.typtype = 'd'::"char" THEN
        CASE
          WHEN bt.typelem <> 0::oid AND bt.typlen = (-1) THEN format_type(bt.typelem, NULL::integer)
          WHEN nbt.nspname = 'pg_catalog'::name THEN NULL
          ELSE 'USER-DEFINED'::text
        END
      ELSE
        CASE
          WHEN t.typelem <> 0::oid AND t.typlen = (-1) THEN format_type(t.typelem, NULL::integer)
          WHEN nt.nspname = 'pg_catalog'::name THEN NULL
          ELSE 'USER-DEFINED'::text
        END
    END::text
    ORDER BY a.attnum) AS element_types
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON (a.attrelid = c.oid)
JOIN pg_catalog.pg_namespace nc ON (c.relnamespace = nc.oid)
LEFT JOIN pg_catalog.pg_attrdef ad ON (a.attrelid = ad.adrelid AND a.attnum = ad.adnum)
JOIN pg_catalog.pg_type t ON (t.oid = a.atttypid)
JOIN pg_catalog.pg_namespace nt ON (t.typnamespace = nt.oid)
LEFT JOIN pg_catalog.pg_type bt ON (t.typtype = 'd'::"char" AND t.typbasetype = bt.oid)
LEFT JOIN pg_catalog.pg_namespace nbt ON (bt.typnamespace = nbt.oid)
WHERE nc.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
  AND NOT pg_is_other_temp_schema(nc.oid) 
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND (c.relkind = ANY (ARRAY['r'::"char", 'v'::"char", 'f'::"char"])) 
  AND (pg_has_role(c.relowner, 'USAGE'::text) OR has_column_privilege(c.oid, a.attnum, 'SELECT, INSERT, UPDATE, REFERENCES'::text))
GROUP BY nc.nspname, c.relname
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
    FKEY_COLUMNS = '''
  SELECT
    ncon.nspname::information_schema.sql_identifier AS fk_constraint_schema,
    con.conname::information_schema.sql_identifier AS fk_constraint_name,
    nfk.nspname::information_schema.sql_identifier AS fk_table_schema,
    fkcl.relname::information_schema.sql_identifier AS fk_table_name,
    (SELECT array_agg(fka.attname ORDER BY i.i)
     FROM generate_subscripts(con.conkey, 1) i
     JOIN pg_catalog.pg_attribute fka ON con.conrelid = fka.attrelid AND con.conkey[i.i] = fka.attnum
    ) AS fk_column_names,
    nk.nspname::information_schema.sql_identifier AS uq_table_schema,
    kcl.relname::information_schema.sql_identifier AS uq_table_name,
    (SELECT array_agg(ka.attname ORDER BY i.i)
     FROM generate_subscripts(con.confkey, 1) i
     JOIN pg_catalog.pg_attribute ka ON con.confrelid = ka.attrelid AND con.confkey[i.i] = ka.attnum
    ) AS uq_column_names,
    CASE con.confdeltype
            WHEN 'c'::"char" THEN 'CASCADE'::text
            WHEN 'n'::"char" THEN 'SET NULL'::text
            WHEN 'd'::"char" THEN 'SET DEFAULT'::text
            WHEN 'r'::"char" THEN 'RESTRICT'::text
            WHEN 'a'::"char" THEN 'NO ACTION'::text
            ELSE NULL::text
    END::information_schema.character_data AS rc_delete_rule,
    CASE con.confupdtype
            WHEN 'c'::"char" THEN 'CASCADE'::text
            WHEN 'n'::"char" THEN 'SET NULL'::text
            WHEN 'd'::"char" THEN 'SET DEFAULT'::text
            WHEN 'r'::"char" THEN 'RESTRICT'::text
            WHEN 'a'::"char" THEN 'NO ACTION'::text
            ELSE NULL::text
    END::information_schema.character_data AS rc_update_rule
  FROM pg_namespace ncon
  JOIN pg_constraint con ON ncon.oid = con.connamespace
  JOIN pg_class fkcl ON con.conrelid = fkcl.oid AND con.contype = 'f'::"char"
  JOIN pg_class kcl ON con.confrelid = kcl.oid AND con.contype = 'f'::"char"
  JOIN pg_namespace nfk ON fkcl.relnamespace = nfk.oid
  JOIN pg_namespace nk ON kcl.relnamespace = nk.oid
  WHERE (pg_has_role(kcl.relowner, 'USAGE'::text) 
         OR has_table_privilege(kcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text) OR has_any_column_privilege(kcl.oid, 'INSERT, UPDATE, REFERENCES'::text))
    AND (pg_has_role(fkcl.relowner, 'USAGE'::text) 
         OR has_table_privilege(fkcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text) OR has_any_column_privilege(fkcl.oid, 'INSERT, UPDATE, REFERENCES'::text))
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
    #cur = conn.cursor()

    # get schemas (including empty ones)
    cur.execute("SELECT catalog_name, schema_name FROM information_schema.schemata")

    for dname, sname in cur:
        if (dname, sname) not in schemas:
            schemas[(dname, sname)] = Schema(model, sname)

    cur.execute(SELECT_COLUMNS)
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
            default_value = pg_default_value(base_type, default_values[i])

            col = Column(cnames[i], i, base_type, default_value)
            cols.append( col )
            columns[(dname, sname, tname, cnames[i])] = col
        
        # Build up the model as we go without redundancy
        if (dname, sname) not in schemas:
            schemas[(dname, sname)] = Schema(model, sname)
        assert (dname, sname, tname) not in tables
        tables[(dname, sname, tname)] = Table(schemas[(dname, sname)], tname, cols)

    # also get empty tables
    cur.execute(SELECT_TABLES)
    for dname, sname, tname in cur:
        if (dname, sname) not in schemas:
            schemas[(dname, sname)] = Schema(model, sname)
        if (dname, sname, tname) not in tables:
            tables[(dname, sname, tname)] = Table(schemas[(dname, sname)], tname, [])

    #
    # Introspect uniques / primary key references, aggregated by constraint
    #
    cur.execute(PKEY_COLUMNS)
    for pk_schema, pk_name, pk_table_schema, pk_table_name, pk_column_names in cur:

        pk_constraint_key = (pk_schema, pk_name)

        pk_cols = [ columns[(dname, pk_table_schema, pk_table_name, pk_column_name)]
                    for pk_column_name in pk_column_names ]

        pk_colset = frozenset(pk_cols)

        # each constraint implies a pkey but might be duplicate
        if pk_colset not in pkeys:
            pkeys[pk_colset] = Unique(pk_colset, (pk_schema, pk_name) )
        else:
            pkeys[pk_colset].constraint_names.add( (pk_schema, pk_name) )

    #
    # Introspect foreign keys references, aggregated by reference constraint
    #
    cur.execute(FKEY_COLUMNS)
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
            fk.references[fk_ref_map] = KeyReference(fk, pk, fk_ref_map, on_delete, on_update, (fk_schema, fk_name) )
        else:
            fk.references[fk_ref_map].constraint_names.add( (fk_schema, fk_name) )

    return model

def pg_default_value(base_type, raw):
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

class Model (object):
    """Represents a database model.
    
    At present, this amounts to a collection of 'schemas' in the conventional
    database sense of the term.
    """
    
    def __init__(self, schemas=None):
        if schemas is None:
            schemas = dict()
        self.schemas = schemas
    
    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            schemas=dict([ 
                    (str(s), self.schemas[s].prejson()) for s in self.schemas 
                    ])
            )
        
    def lookup_schema(self, sname):
        if sname in self.schemas:
            return self.schemas[sname]
        else:
            raise exception.ConflictModel('Schema %s does not exist.' % sname)

    def lookup_table(self, sname, tname):
        if sname is not None:
            if str(sname) not in self.schemas:
                raise exception.ConflictModel('Schema %s does not exist.' % sname)
            if tname not in self.schemas[sname].tables:
                raise exception.ConflictModel('Table %s does not exist in schema %s.' % (tname, sname))
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
    
    def create_schema(self, conn, sname):
        """Add a schema to the model."""
        if sname in self.schemas:
            raise exception.ConflictModel('Requested schema %s already exists.' % sname)
        cur = conn.cursor()
        cur.execute("""
CREATE SCHEMA %s ;
SELECT _ermrest.model_change_event();
""" % sql_identifier(sname))
        cur.close()
        conn.commit()
        return Schema(self, sname)

    def delete_schema(self, conn, sname):
        """Remove a schema from the model."""
        if sname not in self.schemas:
            raise exception.ConflictModel('Requested schema %s does not exist.' % sname)
        cur = conn.cursor()
        cur.execute("""
DROP SCHEMA %s ;
SELECT _ermrest.model_change_event();
""" % sql_identifier(sname))
        cur.close()
        conn.commit()
        del self.schemas[sname]

class Schema (object):
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

    def delete_table(self, conn, tname):
        """Drop a table from the schema."""
        if tname not in self.tables:
            raise exception.ConflictModel('Requested table %s does not exist in schema %s.' % (tname, self.name))
        cur = conn.cursor()
        cur.execute("""
DROP TABLE %s.%s ;
SELECT _ermrest.model_change_event();
""" % (sql_identifier(self.name), sql_identifier(tname)))
        cur.close()
        conn.commit()
        del self.tables[tname]

class Table (object):
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

    @staticmethod
    def create_fromjson(conn, schema, tabledoc):
        sname = tabledoc.get('schema_name', str(schema.name))
        if sname != str(schema.name):
            raise exception.ConflictModel('JSON schema name %s does not match URL schema name %s' % (sname, schema.name))

        if 'table_name' not in tabledoc:
            raise exception.BadData('Table representation requires table_name field.')
        
        tname = tabledoc.get('table_name')

        if tname in schema.tables:
            raise exception.ConflictModel('Table %s already exists in schema %s.' % (tname, sname))

        columns = Column.fromjson(tabledoc.get('column_definitions',[]))
        table = Table(schema, tname, columns)
        keys = Unique.fromjson(table, tabledoc.get('keys', []))
        fkeys = ForeignKey.fromjson(table, tabledoc.get('foreign_keys', []))

        clauses = []
        for column in columns:
            clauses.append(column.sql_def())
            
        for key in keys:
            clauses.append(key.sql_def())

        for fkey in fkeys:
            for ref in fkey.references.values():
                clauses.append(ref.sql_def())

        cur = conn.cursor()
        cur.execute("""
CREATE TABLE %(sname)s.%(tname)s (
   %(clauses)s
);
SELECT _ermrest.model_change_event();
""" % dict(sname=sql_identifier(sname),
           tname=sql_identifier(tname),
           clauses=',\n'.join(clauses)
           )
                    )
        cur.close()
        conn.commit()

        return table

    def alter_table(self, conn, alterclause):
        """Generic ALTER TABLE ... wrapper"""
        cur = conn.cursor()
        cur.execute("""
ALTER TABLE %s.%s  %s ;
SELECT _ermrest.model_change_event();
""" % (sql_identifier(str(self.schema.name)),
       sql_identifier(str(self.name)),
       alterclause
       )
                    )
        cur.close()
        conn.commit()

    def add_column(self, conn, columndoc):
        """Add column to table."""
        # new column always goes on rightmost position
        position = len(self.columns)
        column = Column.fromjson_single(columndoc, position)
        if column.name in self.columns:
            raise exception.ConflictModel('Column %s already exists in table %s:%s.' % (column.name, self.schema.name, self.name))
        self.alter_table(conn, 'ADD COLUMN %s' % column.sql_def())
        self.columns[column.name] = column
        column.table = self
        return column

    def delete_column(self, conn, cname):
        """Delete column from table."""
        if cname not in self.columns:
            raise exception.NotFound('column %s in table %s:%s' % (cname, self.schema.name, self.name))
        self.alter_table(conn, 'DROP COLUMN %s' % sql_identifier(cname))
        del self.columns[cname]
                    
    def add_unique(self, conn, udoc):
        """Add a unique constraint to table."""
        for key in Unique.fromjson_single(self, udoc):
            # new key must be added to table
            self.alter_table(conn, 'ADD %s' % key.sql_def())
            yield key

    def delete_unique(self, conn, unique):
        """Delete unique constraint(s) from table."""
        if unique.columns not in self.uniques or len(unique.constraint_names) == 0:
            raise exception.ConflictModel('Unique constraint columns %s not understood in table %s:%s.' % (unique.columns, self.schema.name, self.name))
        for pk_schema, pk_name in unique.constraint_names:
            # TODO: can constraint ever be in a different postgres schema?  if so, how do you drop it?
            self.alter_table(conn, 'DROP CONSTRAINT %s' % sql_identifier(pk_name))

    def add_fkeyref(self, conn, fkrdoc):
        """Add foreign-key reference constraint to table."""
        for fkr in KeyReference.fromjson(self.schema.model, fkrdoc, None, self, None, None, None):
            # new foreign key constraint must be added to table
            self.alter_table(conn, 'ADD %s' % fkr.sql_def())
            yield fkr

    def delete_fkeyref(self, conn, fkr):
        """Delete foreign-key reference constraint(s) from table."""
        assert fkr.foreign_key.table == self
        for fk_schema, fk_name in fkr.constraint_names:
            # TODO: can constraint ever be in a different postgres schema?  if so, how do you drop it?
            self.alter_table(conn, 'DROP CONSTRAINT %s' % sql_identifier(fk_name))

    def prejson(self):
        return dict(
            schema_name=str(self.schema.name),
            table_name=str(self.name),
            column_definitions=[
                c.prejson() for c in self.columns_in_order()
                ],
            keys=[
                u.prejson() for u in self.uniques.values()
                ],
            foreign_keys=[
                fkr.prejson()
                for fk in self.fkeys.values() for fkr in fk.references.values()
                ]
            )

    def sql_name(self):
        return '.'.join([
                sql_identifier(self.schema.name),
                sql_identifier(self.name)
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


class Column (object):
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

    def is_star_column(self):
        return False

    def sql_def(self):
        """Render SQL column clause for table DDL."""
        parts = [
            sql_identifier(str(self.name)),
            str(self.type.name)
            ]
        if self.default_value:
            parts.append(sql_literal(self.default_value))
        return ' '.join(parts)

    @staticmethod
    def fromjson_single(columndoc, position):
        ctype = columndoc['type']
        return Column(
            columndoc['name'],
            position,
            Type(ctype),
            pg_default_value(ctype, columndoc['default'])
            )

    @staticmethod
    def fromjson(columnsdoc):
        columns = []
        for i in range(0, len(columnsdoc)):
            columns.append(Column.fromjson_single(columnsdoc[i], i))
        return columns

    def prejson(self):
        return dict(
            name=str(self.name), 
            type=str(self.type),
            default=self.default_value
            )

    def prejson_ref(self):
        return dict(
            schema_name=str(self.table.schema.name),
            table_name=str(self.table.name),
            column_name=str(self.name)
            )

    def sql_name(self, alias=None):
        if alias:
            return sql_identifier(alias)
        else:
            return sql_identifier(self.name)
    
    def ddl(self, alias=None):
        if alias:
            name = alias
        else:
            name = self.name
        return "%s %s" % (
            sql_identifier(name),
            self.type.sql()
            )

class FreetextColumn (Column):
    """Represents virtual table column for free text search.

       This is a tsvector computed by appending all text-type columns
       as a document, sorted by column order.
    """
    
    def __init__(self, table):
        Column.__init__(self, '*', None, Type('tsvector'), None)

        self.table = table
        
        def istext(ctype):
            return re.match( r'(text|character)( *varying)?([(]0-9*[)])?', ctype)
            
        self.srccols = [ c for c in table.columns.itervalues() if istext(str(c.type)) ]
        self.srccols.sort(key=lambda c: c.position)

    def sql_name_with_talias(self, talias):
        colnames = [ '%s.%s' % (talias, c.sql_name()) for c in self.srccols ]
        if colnames:
            return " || ' ' || ".join([ "COALESCE(%s::text,''::text)" % name for name in colnames ])
        else:
            return "''::text"

    def is_star_column(self):
        return True

class Unique (object):
    """A unique constraint."""
    
    def __init__(self, cols, constraint_name=None):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.table_references = dict()
        self.constraint_names = set()
        if constraint_name:
            self.constraint_names.add(constraint_name)

        if cols not in self.table.uniques:
            self.table.uniques[cols] = self
        
    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.Unique %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def sql_def(self):
        """Render SQL table constraint clause for DDL."""
        return 'UNIQUE(%s)' % (','.join([sql_identifier(c.name) for c in self.columns]))

    @staticmethod
    def fromjson_single(table, keydoc):
        """Yield Unique instance if and only if keydoc describes a key not already in table."""
        keycolumns = []
        kcnames = keydoc.get('unique_columns', [])
        for kcname in kcnames:
            if kcname not in table.columns:
                raise exception.BadData('Key column %s not defined in table.' % kcname)
            keycolumns.append(table.columns[kcname])
        keycolumns = frozenset(keycolumns)
        if keycolumns not in table.uniques:
            yield Unique(keycolumns)

    @staticmethod
    def fromjson(table, keysdoc):
        for keydoc in keysdoc:
            for key in Unique.fromjson_single(table, keydoc):
                yield key

    def prejson(self):
        return dict(
            unique_columns=[ str(c.name) for c in self.columns ]
            )

class ForeignKey (object):
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

    @staticmethod
    def fromjson(table, refsdoc):
        fkeys = []

        for refdoc in refsdoc:
            # callee will append newly created fkeys to our list as out-variable
            fkrs = list(KeyReference.fromjson(table.schema.model, refdoc, None, table, None, None, fkeys))

        return fkeys

    def prejson(self):
        refs = []
        for krset in self.table_references.values():
            for kr in krset:
                refs.append( kr.prejson() )
        return refs

class KeyReference:
    """A reference from a foreign key to a primary key."""
    
    def __init__(self, foreign_key, unique, fk_ref_map, on_delete='NO ACTION', on_update='NO ACTION', constraint_name=None):
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
        self.constraint_names = set()
        if constraint_name:
            self.constraint_names.add(constraint_name)

    def __str__(self):
        return self.verbose()

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def sql_def(self):
        """Render SQL table constraint clause for DDL."""   
        fk_cols = list(self.foreign_key.columns)
        return ('FOREIGN KEY (%s) REFERENCES %s.%s (%s)'
                % (
                ','.join([ sql_identifier(fk_cols[i].name) for i in range(0, len(fk_cols)) ]),
                sql_identifier(self.unique.table.schema.name),
                sql_identifier(self.unique.table.name),
                ','.join([ sql_identifier(self.reference_map[fk_cols[i]].name) for i in range(0, len(fk_cols)) ])
                ))
    
    @staticmethod
    def fromjson(model, refdoc, fkey=None, fktable=None, pkey=None, pktable=None, outfkeys=None):
        fk_cols = []
        pk_cols = []
        refs = []

        def check_columns(cols, kind):
            tnames = set(map(lambda d: (d.get('schema_name'), d.get('table_name')), cols))
            if len(tnames) != 1:
                raise exception.BadData('All %s columns must come from one table.' % kind)
            sname, tname = tnames.pop()
            table = model.lookup_table(sname, tname)
            for cname in map(lambda d: d.get('column_name'), cols):
                if cname in table.columns:
                    yield table.columns[cname]
                else:
                    raise exception.ConflictModel('The %s column %s not defined in table.' % (kind, cname))

        def get_colset_key_table(columns, is_fkey=True, key=None, table=None):
            if len(columns) == 0:
                raise exception.BadData('Foreign-key references require at least one column pair.')

            colset = frozenset(columns)

            if table is None:
                table = columns[0].table
            elif table != columns[0].table:
                raise exception.ConflictModel('Mismatch in tables for %s columns.' % (is_fkey and 'foreign-key' or 'referenced'))

            if key is None:
                if is_fkey:
                    if colset not in table.fkeys:
                        key = ForeignKey(colset)
                        if outfkeys is not None:
                            outfkeys.append(key)
                    else:
                        key = table.fkeys[colset]
                else:
                    if colset not in table.uniques:
                        raise exception.ConflictModel('Referenced columns %s are not part of a unique key.' % colset)
                    else:
                        key = table.uniques[colset]

            elif is_fkey and fk_colset != fkey.columns:
                raise exception.ConflictModel(
                    'Reference map referring columns %s do not match foreign key columns %s.' 
                    % (colset, key.columns)
                    )
            elif (not is_fkey) and fk_colset != fkey.columns:
                raise exception.ConflictModel(
                    'Reference map referenced columns %s do not match unique columns %s.' 
                    % (colset, key.columns)
                    )

            return colset, key, table

        fk_columns = list(check_columns(refdoc.get('foreign_key_columns', []), 'foreign-key'))
        pk_columns = list(check_columns(refdoc.get('referenced_columns', []), 'referenced'))

        fk_colset, fkey, fktable = get_colset_key_table(fk_columns, True, fkey, fktable)
        pk_colset, pkey, pktable = get_colset_key_table(pk_columns, False, pkey, pktable)
        fk_ref_map = frozendict(dict([ (fk_columns[i], pk_columns[i]) for i in range(0, len(fk_columns)) ]))
        
        if fk_ref_map not in fkey.references:
            fkey.references[fk_ref_map] = KeyReference(fkey, pkey, fk_ref_map)
            yield fkey.references[fk_ref_map]

    def prejson(self):
        fcs = []
        pcs = []
        for fc in self.reference_map.keys():
            fcs.append( fc.prejson_ref() )
            pcs.append( self.reference_map[fc].prejson_ref() )
        return dict(
            foreign_key_columns=fcs,
            referenced_columns=pcs
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
