
#
# Copyright 2012-2020 University of Southern California
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
from . import exception

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

    def healthcheck(self):
        """Do basic health-check and return True or raise error."""
        raise NotImplementedError()

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

    def healthcheck(self):
        """Do basic health-check and return True or raise error."""
        def body(conn, cur):
            # a limited cost query to test registry DB path
            cur.execute("""
SELECT count(*)
FROM ermrest.simple_registry
WHERE id = '1';
""")
            if len(list(cur)) == 1:
                return True
            else:
                raise ValueError('Registry probe query returned invalid result')

        return self.pooled_perform(body)

    def _lookup(self, conn, cur, id=None, dangling=None):
        cur.execute("""
SELECT jsonb_build_object(
  'id', l.id,
  'id_owner', l.id_owner,
  'descriptor', CASE WHEN l.alias_target IS NOT NULL THEN t.descriptor ELSE l.descriptor END,
  'created_on', CASE WHEN l.alias_target IS NOT NULL THEN t.created_on ELSE l.created_on END,
  'deleted_on', CASE WHEN l.alias_target IS NOT NULL THEN t.deleted_on ELSE l.deleted_on END,
  'alias_target', l.alias_target,
  'alias_created_on', CASE WHEN l.alias_target IS NOT NULL THEN l.created_on ELSE NULL END
)
FROM ermrest.simple_registry l
LEFT OUTER JOIN ermrest.simple_registry t ON (l.alias_target = t.id)
WHERE l.deleted_on IS NULL
  AND (t.id IS NULL OR t.deleted_on IS NULL OR %(dangling)s::boolean)
  AND (l.id = %(id)s::text OR %(id)s::text IS NULL)
""" % {
    'id': sql_literal(id),
    'dangling': sql_literal(dangling),
})
        return [ row[0] for row in cur ]

    def lookup(self, id=None, dangling=False):
        """Return a list of registry entries.

        :param id: Find entry with specific id (default None finds all entries)
        :param dangling: List dangling alias entries (default False excludes dangling entries)

        There are three forms of resulting entry dict:
        1. Live catalogs have non-null values for keys {id, id_owner, descriptor, created_on}
        2. Aliased live augment (1) with non-null values for {alias_target, alias_created_on}
        3. Dangling aliases augment (2) with non-null values for {deleted_on}
        """
        def body(conn, cur):
            return self._lookup(conn, cur, id, dangling)
        return self.pooled_perform(body)

    def claim_id(self, id=None, id_owner=None):
        """Claim and return a distinct catalog identifier.

        :param id: A specific id to claim or None (default) to use serial number.
        :param id_owner: A custom ownership ACL to set on claim or None (default) to use web client id.
        """
        def body(conn, cur):
            if id_owner is None:
                owner = [ web.ctx.webauthn2_context.client_id ]
            else:
                owner = id_owner
            if id is None:
                cur.execute("""
SELECT nextval('ermrest.simple_registry_id_seq');
""")
                claim_id = cur.fetchone()[0]
            else:
                claim_id = id

            # idempotent claim pre-checks
            rows = self._lookup(conn, cur, id=claim_id, dangling=True)
            if rows:
                entry = rows[0]
                old_id_owner = entry['id_owner'] if entry['id_owner'] else []
                if set(old_id_owner).isdisjoint(set(web.ctx.webauthn2_context.attribute_ids)):
                    raise exception.Forbidden('claim access on entry id=%s' % (id,))
                if entry['alias_target'] is None and entry['descriptor'] is not None:
                    raise exception.ConflictData('Cannot claim an existing catalog id=%s' % (id,))

            # idempotent claim safe if past pre-checks
            cur.execute("""
INSERT INTO ermrest.simple_registry (id, id_owner)
SELECT %(id)s, ARRAY[%(owner)s]
ON CONFLICT (id) DO UPDATE SET id_owner = EXCLUDED.id_owner
RETURNING id;
""" % {
    'id': sql_literal(claim_id),
    'owner': ', '.join([ sql_literal(x) for x in owner if x != '*' ])
})
            return cur.fetchone()[0]

        return self.pooled_perform(body, lambda x: x)

    def register(self, id, descriptor=None, alias_target=None):
        """Register a catalog descriptor or alias target for an already claimed id.

        :param id: The claimed id.
        :param descriptor: The catalog storage descriptor to register.
        :param alias_target: The id for the target catalog to register.

        """
        assert isinstance(descriptor, dict)

        if descriptor is not None and alias_target is not None:
            raise ValueError('cannot register descriptor and alias_target for same entry')

        def body(conn, cur):
            cur.execute("""
SELECT 
  COALESCE(id_owner, ARRAY[]::text[]),
  descriptor,
  alias_target,
  deleted_on
FROM ermrest.simple_registry
WHERE id = %(id)s
""" % {
    'id': sql_literal(id),
})
            row = cur.fetchone()
            if row is None:
                raise exception.ConflictData('Cannot manage registration for unclaimed id=%r.' % (id,))

            id_owner, old_descriptor, old_alias_target, deleted_on = row
            if set(web.ctx.webauthn2_context.attribute_ids).isdisjoint(set(id_owner)):
                raise exception.Forbidden('manage registration for id=%r' % (id,))

            if deleted_on is not None:
                raise exception.ConflictData('Cannot manage registration for deleted entry id=%r.' % (id,))

            if descriptor is not None:
                if old_descriptor is not None:
                    raise exception.ConflictData('Catalog descriptor already set for entry id=%r.' % (id,))
                if old_alias_target is not None:
                    raise exception.ConflictData('Cannot set descriptor for alias entry id=%r.' % (id,))
            else:
                if old_descriptor is not None:
                    raise exception.ConflictData('Cannot set alias_target for catalog entry id=%r.' % (id,))

            cur.execute("""
UPDATE ermrest.simple_registry v
SET descriptor = %(descriptor)s,
    alias_target = %(alias_target)s
WHERE id = %(id)s;
""" % {
    'id': sql_literal(id),
    'descriptor': sql_literal(json.dumps(descriptor)),
    'alias_target': sql_literal(alias_target),
})
            return self._lookup(conn, cur, id)[0]

        def post_commit(entry):
            return entry

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
