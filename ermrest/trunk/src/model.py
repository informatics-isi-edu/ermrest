
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

__all__ = ["introspect", "Model", "Schema", "Table", "Column"]

def introspect(conn):
    """Introspects a Catalog (i.e., a database).
    
    This function (currently) does not attempt to catch any database 
    (or other) exceptions.
    
    The 'conn' parameter must be an open connection to a database.
    
    Returns the introspected Model instance.
    """
    
    # Select all column metadata from database, excluding system schemas
    SELECT_COLUMNS = '''
SELECT c.table_catalog, c.table_schema, c.table_name, c.column_name, 
       c.ordinal_position, c.column_default, c.data_type, 
       e.data_type AS element_type
FROM information_schema.columns c LEFT JOIN information_schema.element_types e
     ON ((c.table_catalog, c.table_schema, c.table_name, 'TABLE', c.dtd_identifier)
       = (e.object_catalog, e.object_schema, e.object_name, e.object_type, 
          e.collection_type_identifier))
WHERE c.table_schema NOT IN ('information_schema', 'pg_catalog')
ORDER BY c.table_catalog, c.table_schema, c.table_name, c.ordinal_position;
    '''
    
    # Select the unique or primary key columns
    PKEY_COLUMNS = '''
SELECT
   k_c_u.constraint_schema,
   k_c_u.constraint_name,
   k_c_u.table_schema,
   k_c_u.table_name,
   k_c_u.column_name
FROM information_schema.key_column_usage k_c_u
JOIN information_schema.table_constraints t_c
ON k_c_u.constraint_schema =
   t_c.constraint_schema
   AND
   k_c_u.constraint_name =
   t_c.constraint_name 
WHERE t_c.constraint_type IN ('UNIQUE', 'PRIMARY KEY')
ORDER BY
   k_c_u.constraint_name,
   k_c_u.ordinal_position
;
    '''

    # Select the foreign key reference columns
    #
    # The following query was adapted from an example here:
    # http://msdn.microsoft.com/en-us/library/aa175805%28SQL.80%29.aspx
    FKEY_COLUMNS = '''
SELECT
     KCU1.CONSTRAINT_SCHEMA AS FK_CONSTRAINT_SCHEMA
   , KCU1.CONSTRAINT_NAME AS FK_CONSTRAINT_NAME
   , KCU1.TABLE_SCHEMA AS FK_TABLE_SCHEMA
   , KCU1.TABLE_NAME AS FK_TABLE_NAME
   , KCU1.COLUMN_NAME AS FK_COLUMN_NAME
   , KCU1.ORDINAL_POSITION AS FK_ORDINAL_POSITION
   , KCU2.TABLE_SCHEMA AS UQ_TABLE_SCHEMA
   , KCU2.TABLE_NAME AS UQ_TABLE_NAME
   , KCU2.COLUMN_NAME AS UQ_COLUMN_NAME
   , KCU2.ORDINAL_POSITION AS UQ_ORDINAL_POSITION
   , RC.DELETE_RULE AS RC_DELETE_RULE
   , RC.UPDATE_RULE AS RC_UPDATE_RULE
FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS RC
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU1
ON KCU1.CONSTRAINT_CATALOG = RC.CONSTRAINT_CATALOG
   AND KCU1.CONSTRAINT_SCHEMA = RC.CONSTRAINT_SCHEMA
   AND KCU1.CONSTRAINT_NAME = RC.CONSTRAINT_NAME
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU2
ON KCU2.CONSTRAINT_CATALOG =
RC.UNIQUE_CONSTRAINT_CATALOG
   AND KCU2.CONSTRAINT_SCHEMA =
RC.UNIQUE_CONSTRAINT_SCHEMA
   AND KCU2.CONSTRAINT_NAME =
RC.UNIQUE_CONSTRAINT_NAME
   AND KCU2.ORDINAL_POSITION = KCU1.ORDINAL_POSITION
ORDER BY
   KCU1.CONSTRAINT_NAME, KCU1.ORDINAL_POSITION
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

    model = Model()
    
    #
    # Introspect schemas, tables, columns
    #
    cur = conn.execute(SELECT_COLUMNS)
    tuples = cur.fetchall()
    for tup in tuples:
        # Qualified name from tuple
        dname = tup[0]
        sname = tup[1]
        tname = tup[2]
        cname = tup[3]
        # Column specifics from tuple
        position      = tup[4]
        default_value = tup[5]
        data_type     = tup[6]
        element_type  = tup[7]
        
        # Determine base type
        is_array = (data_type == ARRAY_TYPE)
        if is_array:
            base_type = element_type
        else:
            base_type = data_type
            
        # Translate default_value
        default_value = __pg_default_value(base_type, default_value)
        
        # Build up the model as we go without redundancy
        if (dname, sname, tname) not in tables:
            if (dname, sname) not in schemas:
                schemas[(dname, sname)] = Schema(model, sname)
            tables[(dname, sname, tname)] = Table(schemas[(dname, sname)], tname)
            
        # We shouldn't revisit Columns, so no need to check for them
        columns.setdefault((dname, sname, tname, cname), 
            Column(tables[(dname, sname, tname)], cname, position, base_type, 
                   is_array, default_value))

    #
    # Introspect uniques / primary key references
    #
    cur = conn.execute(PKEY_COLUMNS)
    tuples = cur.fetchall()
    for tup in tuples:
        pk_constraint_key   = (tup[0], tup[1]),
        pk_table_schema     = tup[2]
        pk_table_name       = tup[3]
        pk_column_name      = tup[4]
        
        # Get recorded objects
        pk_table = tables[(dname, pk_table_schema, pk_table_name)]
        pk_col = columns[(dname, pk_table_schema, pk_table_name, pk_column_name)]
        
        # Get or create pkey object
        if pk_constraint_key not in pkeys:
            pkeys[pk_constraint_key] = Unique(pk_table)
        pkey = pkeys[pk_constraint_key]
        
        # Add pk column
        pkey.columns[pk_column_name] = pk_col
    
    # Link tables to primary keys
    for pkey in pkeys.values():
        pkey.table.uniques[frozenset(pkey.columns.values())] = pkey

    #
    # Introspect foreign key references
    #
    cur = conn.execute(FKEY_COLUMNS)
    tuples = cur.fetchall()
    for tup in tuples:
        fk_constraint_key   = (tup[0], tup[1])
        fk_table_schema     = tup[2]
        fk_table_name       = tup[3]
        fk_column_name      = tup[4]
        fk_column_pos       = tup[5]
        uq_table_schema     = tup[6]
        uq_table_name       = tup[7]
        uq_column_name      = tup[8]
        uq_column_pos       = tup[9]
        on_delete           = tup[10]
        on_update           = tup[11]
        
        # Get recorded objects
        fk_table = tables[(dname, fk_table_schema, fk_table_name)]
        fk_col = columns[(dname, fk_table_schema, fk_table_name, fk_column_name)]
        uq_table = tables[(dname, uq_table_schema, uq_table_name)]
        uq_col = columns[(dname, uq_table_schema, uq_table_name, uq_column_name)]
        
        # Get or create fkey object
        if fk_constraint_key not in fkeys:
            fkeys[fk_constraint_key] = ForeignKey(fk_table)
        fkey = fkeys[fk_constraint_key]
        
        # Add fk column
        fkey.columns[fk_column_pos] = fk_col
        
        # Get or create key reference
        if uq_table not in fkey.keyreferences:
            fkey.keyreferences[uq_table] = KeyReference(fkey, uq_table, on_delete, on_update)
        keyref = fkey.keyreferences[uq_table]
        
        # Add key ref column
        keyref.columns[uq_column_pos] = uq_col
    
    # Link tables to foreign keys
    for fkey in fkeys.values():
        fkey.table.fkeys[frozenset(fkey.columns.values())] = fkey
    
    return model

def __pg_default_value(base_type, raw):
    """Converts raw default value with base_type hints.
    
    This is at present sort of an ugly hack. It is definitely incomplete but 
    handles what I've seen so far.
    """
    if not raw:
        return raw
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

class Model:
    """Represents a database model.
    
    At present, this amounts to a collection of 'schemas' in the conventional
    database sense of the term.
    """
    
    def __init__(self, schemas=dict()):
        self.schemas = schemas
    
    def verbose(self):
        s = ''
        for schema in self.schemas.values():
            s += "Schema:" + schema.verbose()
        return s
    
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
        s =  "name: %s, num_tables: %d\n" % (self.name, len(self.tables))
        for tab in self.tables.values():
            s += "Table: " + tab.verbose()
        s += "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        return s

class Table:
    """Represents a database table.
    
    At present, this has a 'name' and a collection of table 'columns'. It
    also has a reference to its 'schema'.
    """
    
    def __init__(self, schema, name):
        self.schema = schema
        self.name = name
        self.columns = dict()
        self.uniques = dict()
        self.fkeys = dict()
        
        if name not in self.schema.tables:
            self.schema.tables[name] = self

    def verbose(self):
        s = "name: %s, num_columns: %d\n" % (self.name, len(self.columns))
        for col in self.columns.values():
            s += "Column: " + col.verbose() + "\n"
        s += "--------------------------------------------------------------\n"
        s += "num_uniques: %d\n" % len(self.uniques)
        for uq in self.uniques.values():
            s += uq.verbose() + "\n"
        s += "--------------------------------------------------------------\n"
        s += "num_fkeys: %d\n" % len(self.fkeys)
        for fkey in self.fkeys.values():
            s += fkey.verbose()
        s += "--------------------------------------------------------------\n"
        return s

class Column:
    """Represents a table column.
    
    Its fields include:
     -- name: the name of the columns
     -- position: its ordinal position in the table
     -- base_type: the elemental type
     -- is_array: boolean flag indicating whether it is an array
     -- default_value: a kludgy attempt at translating the raw default 
                       value for this column
    
    It also has a reference to its 'table'.
    """
    
    def __init__(self, table, name, position, base_type, is_array, default_value):
        self.table = table
        self.name = name
        self.position = position
        self.base_type = base_type
        self.is_array = is_array
        self.default_value = default_value
        
        if name not in self.table.columns:
            self.table.columns[name] = self
    
    def verbose(self):
        return "name: %s, position: %d, base_type: %s, is_array: %s, default_value: %s" \
                % (self.name, self.position, self.base_type, self.is_array, self.default_value)

class Unique:
    """A unique constraint."""
    
    def __init__(self, table):
        self.table = table
        self.columns = dict()
        
    def verbose(self):
        s = '('
        for col in self.columns.values():
            s += col.name + ','
        s += ')'
        return s

class ForeignKey:
    """A foreign key."""

    def __init__(self, table):
        self.table = table
        self.columns = dict()
        self.keyreferences = dict()
        # We don't link into table's fkey dict yet, because we the
        # fkey dict is to be keyed on a tuple of the columns in the fkey
        
    def verbose(self):
        s = "FKEY COLS:\n"
        for col in self.columns:
            s += "Position: %s -- %s\n" % (col, self.columns[col].verbose())
        
        for kref in self.keyreferences.values():
            s += "REFERENCES: table name: %s\n" % kref.table.name
            for col in kref.columns:
                s += "Position: %s -- %s\n" % (col, kref.columns[col].verbose())
        return s

class KeyReference:
    """A reference from a foreign key to a primary key."""
    
    def __init__(self, foreign_key, table, on_delete, on_update):
        self.foreign_key = foreign_key
        self.table = table
        self.on_delete = on_delete
        self.on_update = on_update
        self.columns = dict()
        # Link into foreign key's key reference list, by table ref
        self.foreign_key.keyreferences[table] = self


if __name__ == '__main__':
    import os, sanepg2
    connstr = "dbname=%s user=%s" % \
        (os.getenv('TEST_DBNAME', 'test'), os.getenv('TEST_USER', 'test'))
    m = introspect(sanepg2.connection(connstr))
    print m.verbose()
    exit(0)
