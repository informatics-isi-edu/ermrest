
#
# Copyright 2012-2019 University of Southern California
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
Defines the catalog Registry and a default implementation.

This module defines an abstract base class 'Registry' with one concrete
implementation 'SimpleRegistry'. The SimpleRegistry is backed by the system
database owned by the daemon account (typically it is named 'ermrest'). The
SimpleRegistry depends on the 'ermrest' schema and persists the state of the
registry in the 'ermrest.simple_registry' table. The base class defines the
functions supported by this module, and it allows for future implementations
that may be more sophisticated than the SimpleRegistry implementation.
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
        roles = set([r['id'] if type(r) is dict else r for r in roles]) | self.ANONYMOUS
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

    def claim_id(self, id=None):
        """Pre-claim a catalog identifier.

           This does not create the catalog.

           'id' : the id of the catalog to claim.
        """
        raise NotImplementedError()

    def register(self, descriptor, id):
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
            return next(pc.perform(body, post_commit))
        finally:
            if pc is not None:
                pc.final()

    def lookup(self, id=None):
        """See Registry.lookup()"""
        def body(conn, cur):
            filter = " AND id = %s" % sql_literal(id) if id else ""

            cur.execute("""
SELECT id, descriptor
FROM ermrest.simple_registry
WHERE deleted_on IS NULL
%(filter)s;
"""         % dict(filter=filter))

            # return results as a list of dictionaries
            return [
                dict(id=eid, descriptor=json.loads(descriptor))
                for eid, descriptor in cur
            ]

        return self.pooled_perform(body)

    def claim_id(self):
        """Return a distinct catalog identifier."""
        def body(conn, cur):
            cur.execute("""
SELECT nextval('simple_registry_id_seq');
""")
            return str(cur.fetchone()[0])

        return self.pooled_perform(body, lambda x: x)

    def register(self, descriptor, id):
        """See Registry.register()"""
        assert isinstance(descriptor, dict)

        def body(conn, cur):
            cur.execute("""
INSERT INTO ermrest.simple_registry (id, descriptor)
VALUES (%(id)s::bigint, %(descriptor)s)
RETURNING id;
""" % {
    'id': sql_literal(id),
    'descriptor': sql_literal(json.dumps(descriptor)),
})
            return cur.fetchone()[0]

        def post_commit(id):
            return dict(id=id, descriptor=descriptor)

        return self.pooled_perform(body, post_commit)

    def unregister(self, id):
        """See Registry.unregister()"""
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
