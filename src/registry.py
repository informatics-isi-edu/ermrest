
# 
# Copyright 2012-2013 University of Southern California
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
Defines the catalog Registry and a simple implementation.

This may or may not be the right way to do this, but it seems like we will
want to separate the catalog "registry" from the catalog "manager". Where the
former is used to update a registry of catalogs for the purpose of lookup, 
while the latter is used to create or delete catalogs, to modify policies 
(such as ACLs and quotas), and such.

The reason for (logically) separating the interface from the implementation is
that we can envision having a distributed lookup service (or one that uses a 
distribute cache) but we will begin with a simple implementation using a
database backend.
"""

from exceptions import NotImplementedError, ValueError, KeyError

import psycopg2

__all__ = ["RegistryFactory", "Registry"]


class RegistryFactory (object):
    """A factory of ERMREST registries.
    """
    
    def __init__(self, config):
        """Initialize the registry factory.
        """
        self.registry = None
        
        ## Should validate the configuration here
        if config.get("type") != "database":
            raise NotImplementedError()
        else:
            self._dbname = config.get("database_name")
            self._db_schema = config.get("database_schema")
            self._dsn = "dbname=" + self._dbname
        
    def get_registry(self):
        """Returns an instance of the registry.
        """
        if not self.registry:
            ## Create singleton instance
            self.registry = SimpleRegistry(
                                psycopg2.connect(self._dsn),
                                self._db_schema)
        return self.registry


class Registry (object):
    """A registry of ERMREST catalogs.
    
       Supports the registration (or un-registration) and lookup of ERMREST 
       catalogs. Note that "registering" is not the same as creating a catalog.
       A catalog should be created separately using the CatalogManager utility.
       
       Creating a registering a catalog therefore is a two-step process. First,
       one creates the catalog then registers it. The registration effectively
       amounts to a binding between an 'id' and a 'connstr' (connection 
       string) that specifies where to find the catalog and how to connect to
       it. The details of 'connstr' are yet TBD. For now it should be assumed 
       to follow the format of the postgres connection string as supported by
       libpq: 
       
       http://www.postgresql.org/docs/current/static/libpq-connect.html#LIBPQ-CONNSTRING
    """
    
    def lookup(self, id=None):
        """Lookup a registry and retrieve its description.
        
           'id' : an identifier (not sure we have defined it precisely,
                  at present an integer)
           
           returns : a collection of mappings in the form (id, connstr)
        """
        raise NotImplementedError()
    
    def register(self, connstr, id=None):
        """Register a catalog description.
        
           This does not create the catalog.
           
           'connstr' : the connection string.
           'id' : the id of the catalog to register.
        """
        raise NotImplementedError()
    
    def unregister(self, id):
        """Unregister a catalog description.
        
           'id' : the id of the catalog to unregister.
        """
        raise NotImplementedError()
    

class SimpleRegistry (Registry):
    """A simple registry implementation with a database backend.
    
       On the first pass this impl will simply use a database for each
       operation. If we end up using this impl for non-pilot users, it
       should be upgraded with at least local caching of registries.
    """
    
    TABLE_NAME = "simple_registry"
    
    def __init__(self, conn, schema_name):
        """Initialized the SimpleRegistry.
        
        The 'conn' parameter must be an open connection to the registry 
        database.
        """
        super(SimpleRegistry, self).__init__()
        self._conn = conn
        self._schema_name = schema_name
        
        
    def deploy(self):
        """Deploy the SimpleRegistry.
        
        Creates the database schema for the SimpleRegistry implementation.
        """
        try:
            cur = self._conn.cursor()
            
            # create registry schema, if it doesn't exist
            if not _schema_exists(self._conn, self._schema_name):
                cur.execute("""
CREATE SCHEMA %(schema)s;"""
                    % dict(schema=self._schema_name))
                self._conn.commit()
            
            # create registry table, if it doesn't exist
            if not _table_exists(self._conn, self._schema_name, self.TABLE_NAME):
                cur.execute("""
CREATE TABLE %(schema)s.%(table)s (
    id bigserial PRIMARY KEY,
    connstr text
);"""
                    % dict(schema=self._schema_name,
                           table=self.TABLE_NAME))
                self._conn.commit()
                
        finally:
            if cur is not None:
                cur.close()
    
    
    def lookup(self, id=None):
        if id:
            where = "WHERE id = %s" % _sql_literal(id)
        else:
            where = ""
            
        cur = self._conn.cursor()
        cur.execute("""
SELECT id, connstr
FROM %(schema)s.%(table)s
%(where)s;
"""         % dict(schema=self._schema_name,
                   table=self.TABLE_NAME,
                   where=where
                   ) );

        # return results as a list of dictionaries
        entries = list()
        for id, connstr in cur:
            entries.append(dict(id=id, connstr=connstr))
        return entries
    
    
    def register(self, connstr, id=None):
        entries = dict(connstr=connstr)
        if id:
            entries['id'] = id
        
        try:
            cur = self._conn.cursor()
            cur.execute("""
INSERT INTO %(schema)s.%(table)s (%(cols)s) values (%(values)s);
"""
                % dict(schema=self._schema_name,
                       table=self.TABLE_NAME,
                       cols=','.join([_sql_identifier(c) for c in entries.keys()]),
                       values=','.join([_sql_literal(v) for v in entries.values()])
                       ) );
            
        except psycopg2.IntegrityError:
            self._conn.rollback()
            if id:
                raise ValueError("catalog identifier ("+id+") already exists")
            else:
                # this happens when the serial number collides with a manually
                # specified id. we may want to prevent this from happening
                # simply by always autogenerating the id.
                raise ValueError("transient catalog identifier collision, please retry")
        
        # do reverse lookup if autogenerated id
        if not id:
            cur.execute("""
SELECT max(id) as id
FROM %(schema)s.%(table)s
WHERE connstr = %(connstr)s;
"""
                % dict(schema=self._schema_name,
                       table=self.TABLE_NAME,
                       connstr=_sql_literal(connstr)
                       ) );
            id = cur.fetchone()[0]
            cur.close()
        
        self._conn.commit()
        return dict(id=id, connstr=connstr)
    
    
    def unregister(self, id):
        """Unregister a catalog description.
        
           'id' : the id of the catalog to unregister.
        """
        cur = self._conn.cursor()
        cur.execute("""
DELETE FROM %(schema)s.%(table)s
WHERE id = %(id)s;
"""
            % dict(schema=self._schema_name,
                   table=self.TABLE_NAME,
                   id=_sql_literal(id)
                   ) );
        
        self._conn.commit()
        if not cur.rowcount:
            raise KeyError("catalog identifier ("+id+") does not exist")
    

## These helper functions should be coded in ONE PLACE and resued... ##
def _table_exists(conn, schemaname, tablename):
    """Return True or False depending on whether (schema.)tablename exists in our database."""
    
    cur = conn.cursor()
    cur.execute("""
SELECT * FROM information_schema.tables
WHERE table_schema = %(schema)s
AND table_name = %(table)s
"""
                     % dict(schema=_sql_literal(schemaname),
                            table=_sql_literal(tablename))
                     )
    exists = cur.rowcount > 0
    cur.close()
    return exists

    
def _schema_exists(conn, schemaname):
    """Return True or False depending on whether schema exists in our database."""

    cur = conn.cursor()
    cur.execute("""
SELECT * FROM information_schema.schemata
WHERE schema_name = %(schema)s
"""
                       % dict(schema=_sql_literal(schemaname))
                       )
    exists = cur.rowcount > 0
    cur.close()
    return exists


## These wrapper functions should be coded in ONE PLACE and reused... ##
def _string_wrap(s, escape='\\', protect=[]):
    s = s.replace(escape, escape + escape)
    for c in set(protect):
        s = s.replace(c, escape + c)
    return s

def _sql_identifier(s):
    # double " to protect from SQL
    # double % to protect from web.db
    return '"%s"' % _string_wrap(_string_wrap(s, '%'), '"') 

def _sql_literal(v):
    if v != None:
        # double ' to protect from SQL
        # double % to protect from web.db
        s = '%s' % v
        return "'%s'" % _string_wrap(_string_wrap(s, '%'), "'")
    else:
        return 'NULL'
####
    