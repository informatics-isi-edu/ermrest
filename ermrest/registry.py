
#
# Copyright 2012-2024 University of Southern California
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
registry in the 'ermrest.registry' table. The base class defines the
functions supported by this module, and it allows for future implementations
that may be more sophisticated than the SimpleRegistry implementation.
"""

import json
from webauthn2.util import deriva_ctx

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

class NoChange (object):
    """Sentinel value for detecting default keyword args distinct from None value."""
    pass

# sentinel singletone
_nochange = NoChange()

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
    nochange = _nochange

    def __init__(self, dsn, acls):
        """Initialized the SimpleRegistry.
        """
        super(SimpleRegistry, self).__init__(acls)
        self.dsn = dsn

    def pooled_perform(self, body, post_commit=lambda x: x):
        pc = sanepg2.PooledConnection(self.dsn)
        try:
            return pc.perform(body, post_commit)
        finally:
            if pc is not None:
                pc.final()

    def healthcheck(self):
        """Do basic health-check and return True or raise error."""
        def body(conn, cur):
            # a limited cost query to test registry DB path
            cur.execute("""
SELECT count(*)
FROM ermrest.registry
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
  'is_catalog', l.is_catalog,
  'owner', l.owner,
  'descriptor', CASE WHEN l.alias_target IS NOT NULL THEN t.descriptor ELSE l.descriptor END,
  'created_on', CASE WHEN l.alias_target IS NOT NULL THEN t."RCT" ELSE l."RCT" END,
  'deleted_on', CASE WHEN l.alias_target IS NOT NULL THEN t.deleted_on ELSE l.deleted_on END,
  'alias_target', l.alias_target,
  'alias_created_on', CASE WHEN l.alias_target IS NOT NULL THEN l."RCT" ELSE NULL END,
  'name', CASE WHEN l.alias_target IS NOT NULL THEN t.name ELSE l.name END,
  'description', CASE WHEN l.alias_target IS NOT NULL THEN t.description ELSE l.description END
)
FROM ermrest.registry l
LEFT OUTER JOIN ermrest.registry t ON (l.alias_target = t.id)
WHERE l.deleted_on IS NULL
  AND (l.descriptor IS NOT NULL OR t.descriptor IS NOT NULL OR %(dangling)s::boolean)
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
        1. Live catalogs have non-null values for keys {id, owner, descriptor, created_on}
        2. Aliased live augment (1) with non-null values for {alias_target, alias_created_on}
        3. Dangling aliases augment (2) with non-null values for {deleted_on}
        """
        def body(conn, cur):
            return self._lookup(conn, cur, id, dangling)
        return self.pooled_perform(body)

    def _set_webauthn_context(self, cur):
        """Prepare registry DB connection for mutations on behalf of web client

        Since the registry has become an ERMrest catalog for
        introspection, we need to fake up the minimal webauthn state
        needed for provenance metadata tracking of registty changes
        via the registry APIs, since they are independent of the
        normal catalog-specific sub-APIs where we already do this.
        """
        client = deriva_ctx.webauthn2_context.client
        if isinstance(client, dict):
            client_obj = client
            client = client['id']
        else:
            client_obj = { 'id': client }

        attributes = [
            a['id'] if type(a) is dict else a
            for a in deriva_ctx.webauthn2_context.attributes
        ]

        cur.execute("""
INSERT INTO public."ERMrest_Client" ("ID", "Display_Name", "Full_Name", "Email", "Client_Object")
VALUES (%(id)s, %(display_name)s, %(full_name)s, %(email)s, %(client_obj)s::jsonb)
ON CONFLICT ("ID") DO UPDATE
SET "Display_Name" = excluded."Display_Name",
    "Full_Name" = excluded."Full_Name",
    "Email" = excluded."Email",
    "Client_Object" = excluded."Client_Object";
""" % {
    'id': sql_literal(client_obj['id']),
    'display_name': sql_literal(client_obj.get('display_name')),
    'full_name': sql_literal(client_obj.get('full_name')),
    'email': sql_literal(client_obj.get('email')),
    'client_obj': sql_literal(json.dumps(client_obj)),
})
        cur.execute("""
SELECT set_config('webauthn2.client', %(client)s, false);
SELECT set_config('webauthn2.client_json', %(client_obj)s, false);
SELECT set_config('webauthn2.attributes', %(attributes)s, false);
SELECT set_config('webauthn2.attributes_array', (ARRAY[%(attributes_list)s]::text[])::text, false);
""" % {
    'client': sql_literal(client),
    'client_obj': sql_literal(json.dumps(client_obj)),
    'attributes': sql_literal(json.dumps(attributes)),
    'attributes_list': ','.join([
        sql_literal(attr)
        for attr in attributes
    ]),
})

    def claim_id(self, id=None, id_owner=None):
        """Claim and return a distinct catalog identifier.

        :param id: A specific id to claim or None (default) to use serial number.
        :param id_owner: A custom ownership ACL to set on claim or None (default) to use web client id.
        """
        def body(conn, cur):
            if id_owner is None:
                owner = [ deriva_ctx.webauthn2_context.client_id ]
            else:
                owner = id_owner

            if set(owner).isdisjoint(set(deriva_ctx.webauthn2_context.attribute_ids)):
                raise exception.ConflictData('Cannot set owner ACL to exclude self.')

            if id is None:
                cur.execute("""
SELECT nextval('ermrest.registry_id_seq');
""")
                claim_id = cur.fetchone()[0]
            else:
                claim_id = id

            # idempotent claim pre-checks
            rows = self._lookup(conn, cur, id=claim_id, dangling=True)
            if rows:
                entry = rows[0]
                old_id_owner = entry['owner'] if entry['owner'] else []
                if set(old_id_owner).isdisjoint(set(deriva_ctx.webauthn2_context.attribute_ids)):
                    raise exception.Forbidden('claim access on entry id=%s' % (id,))
                if entry['alias_target'] is None and entry['descriptor'] is not None:
                    raise exception.ConflictData('Cannot claim an existing catalog id=%s' % (id,))

            # idempotent claim safe if past pre-checks
            self._set_webauthn_context(cur)
            cur.execute("""
INSERT INTO ermrest.registry (id, is_catalog, owner)
SELECT %(id)s, False, ARRAY[%(owner)s]
ON CONFLICT (id) DO UPDATE SET owner = EXCLUDED.owner
RETURNING id;
""" % {
    'id': sql_literal(claim_id),
    'owner': ', '.join([ sql_literal(x) for x in owner if x != '*' ])
})
            return cur.fetchone()[0]

        return self.pooled_perform(body, lambda x: x)

    def register(self, id, descriptor=None, alias_target=_nochange, name=_nochange, description=_nochange, is_catalog=None, clone_source=_nochange, is_persistent=_nochange):
        """Register a catalog descriptor or alias target for an already claimed id.

        :param id: The claimed id.
        :param descriptor: The catalog storage descriptor to register.
        :param alias_target: The id for the target catalog to register (default: leave unchanged).
        :param name: The name text for the registry entry (default: leave unchanged).
        :param description: The description text (markdown) for the registry entry (default: leave unchanged).
        :param is_catalog: True for catalog, false for alias or unbound ID (default: infer)
        :param clone_source: The id for a clone source catalog to register (default: leave unchanged)
        :param is_persistent: True for persistent entries, false for auto-expiring ones (default: leave unchanged)

        """
        assert descriptor is None or isinstance(descriptor, dict)

        if is_catalog is None:
            is_catalog = descriptor is not None

        if is_persistent is not _nochange:
            if not isinstance(is_persistent, bool):
                raise ValueError('if supplied, is_persistent must be true or false')

        if clone_source is not _nochange and clone_source is not None and not isinstance(clone_source, str):
            raise ValueError('if supplied, clone_source must be a string or null')

        if is_catalog:
            if descriptor is None:
                raise ValueError('descriptor required when is_catalog=true')
            if alias_target is not _nochange:
                raise ValueError('alias_target not allowed when is_catalog=true')
        else:
            if descriptor is not None:
                raise ValueError('descriptor not allowed when is_catalog=false')
            if clone_source is not _nochange:
                raise ValueError('clone_source not appropriate when is_catalog=false')

        def body(conn, cur):
            if is_persistent is not _nochange:
                # need to emulate is_persistent.enforce_right('update')
                # but we don't have an active catalog/model context here
                cur.execute("""
SELECT
  (SELECT jsonb_object_agg(acl, members)
   FROM _ermrest.known_catalog_acls) AS catalog_acls,
  (SELECT jsonb_object_agg(a.acl, a.members)
   FROM _ermrest.known_schemas s
   JOIN _ermrest.known_schema_acls a ON (s."RID" = a.schema_rid)
   WHERE s.schema_name = 'ermrest') AS schema_acls,
  (SELECT jsonb_object_agg(a.acl, a.members)
   FROM _ermrest.known_schemas s
   JOIN _ermrest.known_tables t ON (s."RID" = t.schema_rid)
   JOIN _ermrest.known_table_acls a ON (t."RID" = a.table_rid)
   WHERE s.schema_name = 'ermrest'
     AND t.table_name = 'registry') AS table_acls,
  (SELECT jsonb_object_agg(a.acl, a.members)
   FROM _ermrest.known_schemas s
   JOIN _ermrest.known_tables t ON (s."RID" = t.schema_rid)
   JOIN _ermrest.known_columns c ON (t."RID" = c.table_rid)
   JOIN _ermrest.known_column_acls a ON (c."RID" = a.column_rid)
   WHERE s.schema_name = 'ermrest'
     AND t.table_name = 'registry'
     AND c.column_name = 'is_persistent') AS column_acls;
""")
                row = cur.fetchone()
                catalog_acls, schema_acls, table_acls, column_acls = row
                effective_put_acl = set()

                # owner acls accumulate
                for aclset in [ column_acls, table_acls, schema_acls, catalog_acls ]:
                    if isinstance(aclset, dict):
                        acl = aclset.get('owner')
                        if isinstance(acl, list):
                            effective_put_acl.update(acl)

                # update acls mask inherited versions
                for aclset in [ column_acls, table_acls, schema_acls, catalog_acls ]:
                    if isinstance(aclset, dict):
                        acl = aclset.get('update')
                        if isinstance(acl, list):
                            effective_put_acl.update(acl)
                            break

                if effective_put_acl.isdisjoint(set(deriva_ctx.webauthn2_context.attribute_ids)):
                    raise exception.Forbidden('supplying value for "is_persistent"')

            cur.execute("""
SELECT
  COALESCE(owner, ARRAY[]::text[]),
  is_catalog,
  is_persistent,
  descriptor,
  alias_target,
  clone_source,
  name,
  description,
  deleted_on
FROM ermrest.registry
WHERE id = %(id)s
""" % {
    'id': sql_literal(id),
})
            row = cur.fetchone()
            if row is None:
                raise exception.ConflictData('Cannot manage registration for unclaimed id=%r.' % (id,))

            id_owner, old_is_catalog, old_is_persistent, old_descriptor, \
                old_alias_target, old_clone_source, old_name, old_description, deleted_on = row

            if set(deriva_ctx.webauthn2_context.attribute_ids).isdisjoint(set(id_owner)):
                raise exception.Forbidden('manage registration for id=%r' % (id,))

            if deleted_on is not None:
                raise exception.ConflictData('Cannot manage registration for deleted entry id=%r.' % (id,))

            self._set_webauthn_context(cur)
            if old_is_catalog:
                if descriptor is not None:
                    raise exception.ConflictData('Cannot set descriptor on existing catalog id=%r.' % (id,))
                if alias_target is not _nochange:
                    raise exception.ConflictData('Cannot set alias_target on existing catalog id=%r.' % (id,))
                cur.execute("""
UPDATE ermrest.registry v
SET "name" = %(name)s,
    description = %(description)s,
    is_persistent = %(is_persistent)s,
    clone_source = %(clone_source)s
WHERE id = %(id)s;
""" % {
    'id': sql_literal(id),
    'name': sql_literal(name if name is not _nochange else old_name),
    'description': sql_literal(description if description is not _nochange else old_description),
    'is_persistent': sql_literal(is_persistent if is_persistent is not _nochange else old_is_persistent),
    'clone_source': sql_literal(clone_source if clone_source is not _nochange else old_clone_source),
})
            else:
                # earlier checks validated is_catalog/descriptor/alias_target args
                cur.execute("""
UPDATE ermrest.registry v
SET is_catalog = %(is_catalog)s,
    descriptor = %(descriptor)s,
    alias_target = %(alias_target)s,
    "name" = %(name)s,
    description = %(description)s,
    is_persistent = %(is_persistent)s,
    clone_source = %(clone_source)s
WHERE id = %(id)s;
""" % {
    'id': sql_literal(id),
    'is_catalog': sql_literal(is_catalog),
    'descriptor': sql_literal(json.dumps(descriptor)),
    'alias_target': sql_literal(alias_target if alias_target is not _nochange else old_alias_target),
    'name': sql_literal(name if name is not _nochange else old_name),
    'description': sql_literal(description if description is not _nochange else old_description),
    'is_persistent': sql_literal(is_persistent if is_persistent is not _nochange else old_is_persistent),
    'clone_source': sql_literal(clone_source if clone_source is not _nochange else old_clone_source),
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
            self._set_webauthn_context(cur)
            cur.execute("""
WITH deleted_alias AS (
  DELETE FROM ermrest.registry
  WHERE id = %(id)s
    AND descriptor IS NULL
    AND deleted_on IS NULL
  RETURNING id
), softdeleted_catalog AS (
  UPDATE ermrest.registry
  SET deleted_on = current_timestamp
  WHERE id = %(id)s
    AND deleted_on IS NULL
  RETURNING id
)
SELECT * FROM deleted_alias
UNION
SELECT * FROM softdeleted_catalog;
""" % {
    "id": sql_literal(id),
})
            return cur.rowcount > 0

        def post_commit(deleted):
            if not deleted:
                raise KeyError("catalog identifier ("+id+") does not exist")

        return self.pooled_perform(body, post_commit)
