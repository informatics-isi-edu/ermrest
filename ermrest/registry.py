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

import json

from .util import *
from . import sanepg2

__all__ = ['get_registry']

_POSTGRES_REGISTRY = "postgres"
_SUPPORTED_REGISTRY_TYPES = (_POSTGRES_REGISTRY)

_default_acls = {
    "list_catalogs_permit": [ "*" ],
    "create_catalog_permit": [ "admin" ]
}

def get_registry(config):
    """Returns an instance of the registry based on config.
    """
    if config.get("type") not in _SUPPORTED_REGISTRY_TYPES:
        raise NotImplementedError()
    
    return SimpleRegistry(
        dsn=config.get("dsn"),
        schema=config.get("schema"),
        acls=config.get("acls")
        )


class Registry (object):
    """A registry of ERMREST catalogs.
    
       Supports the registration (or un-registration) and lookup of ERMREST 
       catalogs. Note that "registering" is not the same as creating a catalog.
       A catalog should be created separately using the CatalogManager utility.
       
       Creating a registering a catalog therefore is a two-step process. First,
       one creates the catalog then registers it. The registration effectively
       amounts to a binding between an 'id' and a 'descriptor' (connection 
       descriptor) that specifies where to find the catalog and how to connect 
       to it. 
       
       An example descriptor: { "dbname" : "DATABASE_NAME" }

       
       The full details of 'descriptor' are based on the parameters of the 
       postgres connection string supported by libpq:
       
       http://www.postgresql.org/docs/current/static/libpq-connect.html#LIBPQ-CONNSTRING
    """

    ANONYMOUS = set('*')

    def __init__(self, acls):
        """Initialized the base Registry.
        """
        super(Registry, self).__init__()
        self.acls = acls if acls != None else _default_acls

    def can_list(self, roles):
        """Tests if one of roles can list all catalogs in registry.
        """
        raise NotImplementedError()

    def can_create(self, roles):
        """Tests if one of roles can create a catalog in registry.
        """
        roles = set(roles) | self.ANONYMOUS
        acl = self.acls.get('create_catalog_permit')
        acl = set(acl) if acl else set()
        return len(roles & acl) > 0

    def lookup(self, id=None, deleted=False):
        """Lookup a registry and retrieve its description.
        
           'id' : an identifier (not sure we have defined it precisely,
                  at present an integer)

           'deleted' : a boolean flag to lookup deleted catalogs
           
           returns : a collection of mappings in the form (id, descriptor)
        """
        raise NotImplementedError()
    
    def register(self, descriptor, id=None):
        """Register a catalog description.
        
           This does not create the catalog.
           
           'descriptor' : the catalog connection descriptor.
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
    
       Operations use basic connection-pooling but each does its own
       transaction since requests are usually independent and simple
       lookup is the hot path.
    """
    
    TABLE_NAME = "simple_registry"
    
    def __init__(self, dsn, schema, acls):
        """Initialized the SimpleRegistry.
        """
        super(SimpleRegistry, self).__init__(acls)
        self.dsn = dsn
        self._schema_name = schema

    def pooled_perform(self, body, post_commit=lambda x: x):
        pc = sanepg2.PooledConnection(self.dsn)
        try:
            return pc.perform(body, post_commit).next()
        finally:
            pc.final()
        
    def deploy(self):
        """Deploy the SimpleRegistry.
        
        Creates the database schema for the SimpleRegistry implementation.
        """
        def body(conn, cur):
            # create registry schema, if it doesn't exist
            if not schema_exists(cur, self._schema_name):
                cur.execute("""
CREATE SCHEMA %(schema)s;"""
                    % dict(schema=self._schema_name))
            
            # create registry table, if it doesn't exist
            if not table_exists(cur, self._schema_name, self.TABLE_NAME):
                cur.execute("""
CREATE TABLE %(schema)s.%(table)s (
    id bigserial PRIMARY KEY,
    descriptor text,
    deletedon timestamp with time zone DEFAULT NULL
);
CREATE INDEX ON %(schema)s.%(table)s (deletedon);
CREATE INDEX ON %(schema)s.%(table)s (id, deletedon);
"""
                    % dict(schema=self._schema_name,
                           table=self.TABLE_NAME))
            return None
        return self.pooled_perform(body)
                
    def lookup(self, id=None, deleted=False):
        def body(conn, cur):
            where = "WHERE deletedon"
            if deleted:
                where += " IS NOT NULL"
            else:
                where += " IS NULL"
            if id:
                where += " AND id = %s" % sql_literal(id)

            cur.execute("""
SELECT id, descriptor, deletedon
FROM %(schema)s.%(table)s
%(where)s;
"""         % dict(schema=self._schema_name,
                   table=self.TABLE_NAME,
                   where=where
                   ) )
            
            # return results as a list of dictionaries
            return [
                dict(id=eid, descriptor=json.loads(descriptor), deletedon=deletedon)
                for eid, descriptor, deletedon in cur
            ]

        return self.pooled_perform(body)

    def register(self, descriptor, id=None):
        assert isinstance(descriptor, dict)
        entry = dict(descriptor=json.dumps(descriptor))
        
        def body(conn, cur):
            cur.execute("""
INSERT INTO %(schema)s.%(table)s (%(cols)s)
VALUES (%(values)s)
RETURNING id;
""" % dict(schema=self._schema_name,
           table=self.TABLE_NAME,
           cols=','.join([sql_identifier(c) for c in entry.keys()]),
           values=','.join([sql_literal(v) for v in entry.values()])
           ) 
                        )
            return cur.fetchone()[0]
            
        def post_commit(id):
            return dict(id=id, descriptor=descriptor)

        return self.pooled_perform(body, post_commit)

    def unregister(self, id):
        """Unregister a catalog description.
        
           'id' : the id of the catalog to unregister.
        """
        assert id is not None

        def body(conn, cur):
            cur.execute("""
UPDATE %(schema)s.%(table)s
SET deletedon = current_timestamp
WHERE deletedon IS NULL AND id = %(id)s;
"""          % dict(schema=self._schema_name,
                   table=self.TABLE_NAME,
                   id=sql_literal(id)
                   ) )
            return cur.rowcount > 0

        def post_commit(deleted):
            if not deleted:
                raise KeyError("catalog identifier ("+id+") does not exist")

        return self.pooled_perform(body, post_commit)
