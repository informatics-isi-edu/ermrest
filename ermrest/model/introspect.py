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

"""
A database introspection layer.

At present, the capabilities of this module are limited to introspection of an 
existing database model. This module does not attempt to capture all of the 
details that could be found in an entity-relationship model or in the standard 
information_schema of a relational database. It represents the model as 
needed by other modules of the ermrest project.
"""

import web

from .. import exception
from ..util import table_exists, view_exists
from .misc import frozendict, Model, Schema, annotatable_classes
from .type import Type, ArrayType, canonicalize_column_type
from .column import Column
from .table import Table
from .key import Unique, ForeignKey, KeyReference, PseudoUnique, PseudoKeyReference

def introspect(cur, config=None):
    """Introspects a Catalog (i.e., a database).
    
    This function (currently) does not attempt to catch any database 
    (or other) exceptions.
    
    The 'conn' parameter must be an open connection to a database.
    
    Returns the introspected Model instance.
    """
    
    # this postgres-specific code borrows bits from its information_schema view definitions
    # but is trimmed down to be a cheaper query to execute

    # Select all schemas from database, excluding system schemas
    SELECT_SCHEMAS = '''
SELECT
  current_database() AS catalog_name,
  nc.nspname AS schema_name,
  obj_description(nc.oid) AS schema_comment
FROM 
  pg_catalog.pg_namespace nc
WHERE
  nc.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
  AND NOT pg_is_other_temp_schema(nc.oid);
    '''

    # Select all column metadata from database, excluding system schemas
    SELECT_TABLES = '''
SELECT
  current_database() AS table_catalog,
  nc.nspname AS table_schema,
  c.relname AS table_name,
  c.relkind AS table_kind,
  obj_description(c.oid) AS table_comment
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace nc ON (c.relnamespace = nc.oid)
LEFT JOIN pg_catalog.pg_attribute a ON (a.attrelid = c.oid)
WHERE nc.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
  AND NOT pg_is_other_temp_schema(nc.oid) 
  AND (c.relkind = ANY (ARRAY['r'::"char", 'v'::"char", 'f'::"char", 'm'::"char"]))
  AND (pg_has_role(c.relowner, 'USAGE'::text) OR has_column_privilege(c.oid, a.attnum, 'SELECT, INSERT, UPDATE, REFERENCES'::text))
GROUP BY nc.nspname, c.relname, c.relkind, c.oid
    '''
    
    SELECT_COLUMNS = '''
SELECT
  current_database() AS table_catalog,
  nc.nspname AS table_schema,
  c.relname AS table_name,
  c.relkind AS table_kind,
  obj_description(c.oid) AS table_comment,
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
    ORDER BY a.attnum) AS element_types,
  array_agg(
    col_description(c.oid, a.attnum)
    ORDER BY a.attnum) AS comments
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
  AND (c.relkind = ANY (ARRAY['r'::"char", 'v'::"char", 'f'::"char", 'm'::"char"]))
  AND (pg_has_role(c.relowner, 'USAGE'::text) OR has_column_privilege(c.oid, a.attnum, 'SELECT, INSERT, UPDATE, REFERENCES'::text))
GROUP BY nc.nspname, c.relname, c.relkind, c.oid
    '''
    
    # Select the unique key reference columns
    PKEY_COLUMNS = '''
  SELECT
    ncon.nspname::information_schema.sql_identifier AS pk_constraint_schema,
    con.conname::information_schema.sql_identifier AS pk_constraint_name,
    npk.nspname::information_schema.sql_identifier AS pk_table_schema,
    pkcl.relname::information_schema.sql_identifier AS pk_table_name,
    (SELECT array_agg(pka.attname ORDER BY i.i)
     FROM generate_subscripts(con.conkey, 1) i
     JOIN pg_catalog.pg_attribute pka ON con.conrelid = pka.attrelid AND con.conkey[i.i] = pka.attnum
    ) AS pk_column_names,
    obj_description(con.oid) AS constraint_comment
  FROM pg_namespace ncon
  JOIN pg_constraint con ON ncon.oid = con.connamespace
  JOIN pg_class pkcl ON con.conrelid = pkcl.oid AND con.contype = ANY (ARRAY['u'::"char",'p'::"char"])
  JOIN pg_namespace npk ON pkcl.relnamespace = npk.oid
  WHERE pg_has_role(pkcl.relowner, 'USAGE'::text) ;
'''

    PSEUDO_PKEY_COLUMNS = '''
SELECT 
  id AS pk_id,
  schema_name AS pk_table_schema,
  table_name AS pk_table_name,
  column_names AS pk_column_names,
  comment AS constraint_comment
FROM _ermrest.model_pseudo_key ;
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
    END::information_schema.character_data AS rc_update_rule,
    obj_description(con.oid) AS constraint_comment
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

    PSEUDO_FKEY_COLUMNS = '''
SELECT
  id AS fk_id,
  from_schema_name AS fk_table_schema,
  from_table_name AS fk_table_name,
  from_column_names AS fk_column_names,
  to_schema_name AS uq_table_schema,
  to_table_name AS uq_table_name,
  to_column_names AS uq_column_names,
  comment AS constraint_comment
FROM _ermrest.model_pseudo_keyref ;
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
    
    # get schemas (including empty ones)
    cur.execute(SELECT_SCHEMAS);
    for dname, sname, scomment in cur:
        if (dname, sname) not in schemas:
            schemas[(dname, sname)] = Schema(model, sname, scomment)

    # get columns
    cur.execute(SELECT_COLUMNS)
    for dname, sname, tname, tkind, tcomment, cnames, default_values, data_types, element_types, comments in cur:

        cols = []
        for i in range(0, len(cnames)):
            # Determine base type
            is_array = (data_types[i] == ARRAY_TYPE)
            if is_array:
                base_type = ArrayType(Type(canonicalize_column_type(element_types[i], default_values[i], config, True)))
            else:
                base_type = Type(canonicalize_column_type(data_types[i], default_values[i], config, True))
        
            # Translate default_value
            try:
                default_value = base_type.default_value(default_values[i])
            except ValueError:
                # TODO: raise informative exception instead of masking error
                default_value = None

            col = Column(cnames[i].decode('utf8'), i, base_type, default_value, comments[i])
            cols.append( col )
            columns[(dname, sname, tname, cnames[i])] = col
        
        # Build up the model as we go without redundancy
        if (dname, sname) not in schemas:
            schemas[(dname, sname)] = Schema(model, sname)
        assert (dname, sname, tname) not in tables
        tables[(dname, sname, tname)] = Table(schemas[(dname, sname)], tname, cols, tkind, tcomment)

    # also get empty tables
    cur.execute(SELECT_TABLES)
    for dname, sname, tname, tkind, tcomment in cur:
        if (dname, sname) not in schemas:
            schemas[(dname, sname)] = Schema(model, sname)
        if (dname, sname, tname) not in tables:
            tables[(dname, sname, tname)] = Table(schemas[(dname, sname)], tname, [], tkind, tcomment)

    #
    # Introspect uniques / primary key references, aggregated by constraint
    #
    def _introspect_pkey(pk_table_schema, pk_table_name, pk_column_names, pk_comment, pk_factory):
        pk_cols = [ columns[(dname, pk_table_schema, pk_table_name, pk_column_name)]
                    for pk_column_name in pk_column_names ]

        pk_colset = frozenset(pk_cols)

        # each constraint implies a pkey but might be duplicate
        pk = pk_factory(pk_colset)
        if pk_colset not in pkeys:
            pkeys[pk_colset] = pk
        else:
            pkeys[pk_colset].constraints.add(pk)
            if pk_comment:
                # save at least one comment in case multiple constraints have same key columns
                pkeys[pk_colset].comment = pk_comment
    
    cur.execute(PKEY_COLUMNS)
    for pk_schema, pk_name, pk_table_schema, pk_table_name, pk_column_names, pk_comment in cur:
        _introspect_pkey(
            pk_table_schema, pk_table_name, pk_column_names, pk_comment,
            lambda pk_colset: Unique(pk_colset, (pk_schema, pk_name), pk_comment)
        )

    cur.execute(PSEUDO_PKEY_COLUMNS)
    for pk_id, pk_table_schema, pk_table_name, pk_column_names, pk_comment in cur:
        _introspect_pkey(
            pk_table_schema, pk_table_name, pk_column_names, pk_comment,
            lambda pk_colset: Unique(pk_colset, (pk_schema, pk_name), pk_comment)
        )
            
    #
    # Introspect foreign keys references, aggregated by reference constraint
    #
    def _introspect_fkr(
            fk_table_schema, fk_table_name, fk_column_names,
            uq_table_schema, uq_table_name, uq_column_names, fk_comment,
            fkr_factory
    ):
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
        fkr = fkr_factory(fk, pk, fk_ref_map)
        if fk_ref_map not in fk.references:
            fk.references[fk_ref_map] = fkr
        else:
            fk.references[fk_ref_map].constraints.add(fkr)
            if fk_comment:
                # save at least one comment in case multiple csontraints have same key mapping
                fk.references[fk_ref_map].comment = fk_comment

    
    cur.execute(FKEY_COLUMNS)
    for fk_schema, fk_name, fk_table_schema, fk_table_name, fk_column_names, \
            uq_table_schema, uq_table_name, uq_column_names, on_delete, on_update, fk_comment \
            in cur:
        _introspect_fkr(
            fk_table_schema, fk_table_name, fk_column_names,
            uq_table_schema, uq_table_name, uq_column_names, fk_comment,
            lambda fk, pk, fk_ref_map: KeyReference(fk, pk, fk_ref_map, on_delete, on_update, (fk_schema, fk_name), comment=fk_comment)
        )
        
    cur.execute(PSEUDO_FKEY_COLUMNS)
    for fk_id, fk_table_schema, fk_table_name, fk_column_names, \
            uq_table_schema, uq_table_name, uq_column_names, fk_comment \
            in cur:
        _introspect_fkr(
            fk_table_schema, fk_table_name, fk_column_names,
            uq_table_schema, uq_table_name, uq_column_names, fk_comment,
            lambda fk, pk, fk_ref_map: PseudoKeyReference(fk, pk, fk_ref_map, fk_id, comment=fk_comment)
        )
    
    #
    # Introspect ERMrest model overlay annotations
    #
    for klass in annotatable_classes:
        if hasattr(klass, 'introspect_helper'):
            klass.introspect_helper(cur, model)

    # save our private schema in case we want to unhide it later...
    model.ermrest_schema = model.schemas['_ermrest']
    del model.schemas['_ermrest']
    
    if not table_exists(cur, '_ermrest', 'valuemap'):
        # rebuild missing table and add it to model manually since we already introspected
        web.debug('NOTICE: adding empty valuemap during model introspection')
        model.recreate_value_map(cur.connection, cur, empty=True)
        valuemap_columns = ['schema', 'table', 'column', 'value']
        for i in range(len(valuemap_columns)):
            valuemap_columns[i] = Column(valuemap_columns[i], i, Type(canonicalize_column_type('text', 'NULL', config, True)), None)
        model.ermrest_schema.tables['valuemap'] = Table(model.ermrest_schema, 'valuemap', valuemap_columns, 't')

    return model

