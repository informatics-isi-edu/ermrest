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

_DEFAULT_ACLS = {
    "create_catalog_permit": ["admin"]
}

def get_registry(config):
    """Returns an instance of the registry based on config.
    """
    # "postgres" is the one and only supported registry type
    if config.get("type") != "postgres":
        raise NotImplementedError()

    return SimpleRegistry(
        dsn=config.get("dsn"),
        acls=config.get("acls")
        )


class Registry(object):
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
        self.acls = acls if acls != None else _DEFAULT_ACLS

    def can_create(self, roles):
        """Tests if one of roles can create a catalog in registry.
        """
        roles = set(roles) | self.ANONYMOUS
        acl = self.acls.get('create_catalog_permit')
        acl = set(acl) if acl else set()
        return len(roles & acl) > 0

    def lookup(self, id=None):
        """Lookup a registry and retrieve its description.

           'id' : an identifier (not sure we have defined it precisely,
                  at present an integer)

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


class SimpleRegistry(Registry):
    """A simple registry implementation with a database backend.

       Operations use basic connection-pooling but each does its own
       transaction since requests are usually independent and simple
       lookup is the hot path.
    """

    def __init__(self, dsn, acls):
        """Initialized the SimpleRegistry.
        """
        super(SimpleRegistry, self).__init__(acls)
        self.dsn = dsn

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
            cur.execute("CREATE SCHEMA IF NOT EXISTS ermrest;")

            # create registry table, if it doesn't exist
            if not table_exists(cur, "ermrest", "simple_registry"):
                cur.execute("""
CREATE TABLE ermrest.simple_registry (
    id bigserial PRIMARY KEY,
    descriptor text,
    deleted_on timestamp with time zone DEFAULT NULL
);
CREATE INDEX ON ermrest.simple_registry (deleted_on);
CREATE INDEX ON ermrest.simple_registry (id, deleted_on);
""")
            return None
        return self.pooled_perform(body)


    def lookup(self, id=None):
        def body(conn, cur):
            filter = " AND id = %s" % sql_literal(id) if id else ""

            cur.execute("""
SELECT id, descriptor, deleted_on
FROM ermrest.simple_registry
WHERE deleted_on IS NULL
%(filter)s;
"""         % dict(filter=filter))

            # return results as a list of dictionaries
            return [
                dict(id=eid, descriptor=json.loads(descriptor), deleted_on=deleted_on)
                for eid, descriptor, deleted_on in cur
            ]

        return self.pooled_perform(body)


    def register(self, descriptor, id=None):
        assert isinstance(descriptor, dict)
        entry = dict(descriptor=json.dumps(descriptor))

        def body(conn, cur):
            cur.execute("""
INSERT INTO ermrest.simple_registry (%(cols)s)
VALUES (%(values)s)
RETURNING id;
""" % dict(cols=','.join([sql_identifier(c) for c in entry.keys()]),
           values=','.join([sql_literal(v) for v in entry.values()])))

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
            """Returns True if row deleted, false if not"""
            cur.execute("""
UPDATE ermrest.simple_registry
SET deleted_on = current_timestamp
WHERE deleted_on IS NULL AND id = %(id)s;
"""          % dict(id=sql_literal(id)))
            return cur.rowcount > 0

        def post_commit(deleted):
            if not deleted:
                raise KeyError("catalog identifier ("+id+") does not exist")

        return self.pooled_perform(body, post_commit)
