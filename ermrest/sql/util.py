
#
# Copyright 2017 University of Southern California
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

import sys
import pkgutil
from ..util import sql_identifier
from .. import sanepg2, sql
from ..catalog import Catalog
from ..apicore import catalog_factory, registry

def for_each_catalog(thunk, id=None):
    """Run thunk(catalog, conn, cur) for one or all catalogs in registry."""
    if not registry:
        raise NotImplementedError('ERMrest catalog registry not configured.')

    results = registry.lookup(id)
    for result in results:
        catalog = Catalog(catalog_factory, result['descriptor'])
        pc = sanepg2.PooledConnection(catalog.dsn)
        pc.perform(lambda conn, cur: thunk(catalog, conn, cur), verbose=False).next()
        pc.final()

def extupgrade_sql(dbname):
    """Return SQL to perform upgrade of extensions.

       This SQL should be run via 'psql' as postgres or another DB superuser.
    """
    return """
\\connect %(dbname)s
DO $$
DECLARE
  mustreindex boolean;
  orig_version text;
BEGIN
  mustreindex := False;

  SELECT extversion INTO orig_version FROM pg_catalog.pg_extension WHERE extname = 'pg_trgm';
  IF orig_version IS NULL THEN
    CREATE EXTENSION "pg_trgm";
  ELSE
    ALTER EXTENSION "pg_trgm" UPDATE;
    IF (SELECT extversion FROM pg_catalog.pg_extension WHERE extname = 'pg_trgm') != orig_version THEN
      mustreindex := True;
    END IF;
  END IF;

  SELECT extversion INTO orig_version FROM pg_catalog.pg_extension WHERE extname = 'btree_gist';
  IF orig_version IS NULL THEN
    CREATE EXTENSION "btree_gist";
  ELSE
    ALTER EXTENSION "btree_gist" UPDATE;
    IF (SELECT extversion FROM pg_catalog.pg_extension WHERE extname = 'btree_gist') != orig_version THEN
      mustreindex := True;
    END IF;
  END IF;

  -- there might be more than one extension requiring reindexing in the future?
  IF mustreindex THEN
    REINDEX DATABASE %(dbname)s;
    ANALYZE;
  END IF;
END;
$$ LANGUAGE plpgsql;
""" % {
    "dbname": sql_identifier(dbname)
}

def print_extupgrade_sql(dbname):
    sys.stdout.write(extupgrade_sql(dbname))

def print_redeploy_registry_sql():
    """Output SQL to perform idempotent re-deploy of registry.

       This SQL should be run via 'psql' as postgres or another DB superuser.
    """
    sys.stdout.write("""
\\connect template1
%(template1_extupgrade)s
\\connect ermrest
BEGIN;
ALTER DATABASE ermrest OWNER TO ermrest;
%(registry_sql)s
%(upgrade_sql)s
%(change_owners_sql)s
COMMIT;
ANALYZE;
""" % {
    "template1_extupgrade": extupgrade_sql('template1'),
    "registry_sql": pkgutil.get_data(sql.__name__, 'registry.sql'),
    "upgrade_sql": pkgutil.get_data(sql.__name__, 'upgrade_registry.sql'),
    "change_owners_sql": pkgutil.get_data(sql.__name__, 'change_owner.sql'),
})

def print_redeploy_catalogs_sql():
    """Output SQL to perform idempotent re-deploy of catalogs.

       This SQL should be run via 'psql' as postgres or another DB superuser.
    """
    def catalog_helper(catalog, conn, cur):
        """Print SQL to re-deploy one catalog."""
        sys.stdout.write("""
\\connect %(dbname)s
%(catalog_extupgrade)s
BEGIN;
ALTER DATABASE %(dbname)s OWNER TO ermrest;
%(ermrest_sql)s
SELECT _ermrest.model_change_event();
%(upgrade_sql)s
%(change_owners_sql)s
COMMIT;
ANALYZE;
""" % {
    "catalog_extupgrade": extupgrade_sql(catalog.descriptor['dbname']),
    "dbname": sql_identifier(catalog.descriptor['dbname']),
    "ermrest_sql": pkgutil.get_data(sql.__name__, 'ermrest_schema.sql'),
    "upgrade_sql": pkgutil.get_data(sql.__name__, 'upgrade_schema.sql'),
    "change_owners_sql": pkgutil.get_data(sql.__name__, 'change_owner.sql'),
})

    for_each_catalog(catalog_helper)
