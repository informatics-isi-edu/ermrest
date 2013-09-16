
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

__all__ = ["introspect", "Model", "Catalog", "Schema", "Table", "Column"]

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
    
    # PostgreSQL denotes array types with the string 'ARRAY'
    ARRAY_TYPE = 'ARRAY'
    
    # Dicts for quick lookup
    catalogs = dict()
    schemas  = dict()
    tables   = dict()
    columns  = dict()
    
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
                if dname not in catalogs:
                    catalogs[dname] = Catalog(dname)
                schemas[(dname, sname)] = Schema(catalogs[dname], sname)
            tables[(dname, sname, tname)] = Table(schemas[(dname, sname)], tname)
            
        # We shouldn't revisit Columns, so no need to check for them
        columns.setdefault((dname, sname, tname, cname), 
            Column(tables[(dname, sname, tname)], cname, position, base_type, 
                   is_array, default_value))
        
    return Model(catalogs)

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
    
    At present, this amounts to a collection of 'catalogs' in the conventional
    database sense of the term.
    """
    
    def __init__(self, catalogs):
        self.catalogs = catalogs
    
    def __str__(self):
        s = ''
        for cat in self.catalogs.values():
            s += "Catalog: " + str(cat)
        return s
    
class Catalog:
    """Represents a database catalog.
    
    At present, this has a 'name' and a collection of database 'schemas'.
    """
    
    def __init__(self, name):
        self.name = name
        self.schemas = dict()

    def __str__(self):
        s = "name: %s, num_schemas: %d\n" % (self.name, len(self.schemas))
        for schema in self.schemas.values():
            s += "Schema: " + str(schema)
        s += "==============================================================\n"
        return s

class Schema:
    """Represents a database schema.
    
    At present, this has a 'name' and a collection of database 'tables'. It 
    also has a reference to its 'catalog'.
    """
    
    def __init__(self, catalog, name):
        self.catalog = catalog
        self.name = name
        self.tables = dict()
        
        if name not in self.catalog.schemas:
            self.catalog.schemas[name] = self

    def __str__(self):
        s =  "name: %s, num_tables: %d\n" % (self.name, len(self.tables))
        for tab in self.tables.values():
            s += "Table: " + str(tab)
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
        
        if name not in self.schema.tables:
            self.schema.tables[name] = self

    def __str__(self):
        s = "name: %s, num_columns: %d\n" % (self.name, len(self.columns))
        for col in self.columns.values():
            s += "Column: " + str(col) + "\n"
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
    
    def __str__(self):
        return "name: %s, position: %d, base_type: %s, is_array: %s, default_value: %s" \
                % (self.name, self.position, self.base_type, self.is_array, self.default_value)

class Unique:
    """A unique constraint."""
    pass

class ForeignKey:
    """A foreign key."""
    pass

class KeyReference:
    """A reference from a foreign key to a primary key."""
    pass
