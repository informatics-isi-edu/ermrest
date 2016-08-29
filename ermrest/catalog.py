# 
# Copyright 2013-2016 University of Southern California
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
Catalog management module.

This module provides catalog management features including:
    - create and delete catalogs
    - modify catalog policies (e.g., permissions, quotas, etc.)
    - modify catalog metadata
"""

import psycopg2
import sanepg2

from util import sql_identifier, sql_literal, schema_exists, table_exists, random_name
from .model import introspect
from .model.misc import annotatable_classes

__all__ = ['get_catalog_factory']

_POSTGRES_FACTORY = "postgres"
_SUPPORTED_FACTORY_TYPES = (_POSTGRES_FACTORY)


def get_catalog_factory(config):
    """Returns an instance of the catalog factory based on config.
    """
    if config.get("type") not in _SUPPORTED_FACTORY_TYPES:
        raise NotImplementedError()

    return CatalogFactory(
        dsn=config.get("dsn"),
        template=config.get('template')
        )


class CatalogFactory (object):
    """The catalog factory.

       This is a "simple" implementation based on a PostgreSQL backend.
    
       Single Host
       -----------
       At this point in the design of the CatalogFactory, it is specific to one
       host. That is, a factory is initialized with a superuser connection to a
       database server. Thus the factory operations are confined to that 
       database server alone, such as creating a new catalog, deleting a 
       catalog, and so on.
       
       Authorization
       -------------
       This factory does not enforce any application level authorization 
       policies. Those should be checked before invoking factory methods.
    """

    _KEY_DBNAME = 'dbname'  # descriptor dbname key

    def __init__(self, dsn='dbname=', template={}):
        """Initialize the Catalog Factory.
        
           dsn : database DSN of the factory.

           template : descriptor template for new catalogs.
           
           The database user must be a super user or have CREATEDB permissions.
        """
        self._dsn = dsn
        self._template = template

    def create(self):
        """Create a Catalog.
        
           This operation creates a catalog (i.e., it creates a database) on 
           the same host as the catalog factory. It does not initialize or 
           register the catalog.
           
           Returns the new catalog object representing the catalog.
        """
        # generate a random database name
        dbname = random_name(prefix='_ermrest_')

        def body(conn, cur):
            # create database
            try:
                conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                cur.execute("CREATE DATABASE " + sql_identifier(dbname))
            except psycopg2.Error, ev:
                msg = str(ev)
                idx = msg.find("\n")  # DETAIL starts after the first line feed
                if idx > -1:
                    msg = msg[0:idx]
                raise RuntimeError(msg)
            finally:
                # just in case caller didn't use sanepg2 which resets this already...
                conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ)

        def post_commit(ignored):
            # create catalog
            descriptor = dict(self._template)
            descriptor[self._KEY_DBNAME] = dbname
            return Catalog(self, descriptor)

        pc = sanepg2.PooledConnection(self._dsn)
        try:
            return pc.perform(body, post_commit).next()
        finally:
            pc.final()
    
    def _destroy_catalog(self, conn, ignored_cur, catalog):
        """Destroys a catalog.
        
           Do not call this method directly.

           NOTE: This code looks b0rken; notice reference to _dbc which is never defined
        """
        cur = None
        try:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            
            # first, attempt to disconnect clients
            cur = conn.cursor()
            cur.execute("""
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = %(dbname)s
  AND pid <> pg_backend_pid()
;"""
                % dict(dbname=sql_literal(catalog.descriptor[self._KEY_DBNAME])))
            
            #TODO: note that a client could reconnect ...now... and prevent the drop
            
            # then, drop database
            cur.execute("DROP DATABASE " + 
                        sql_identifier(catalog.descriptor[self._KEY_DBNAME]))

            cur.close()
            
        except psycopg2.Error, ev:
            msg = str(ev)
            idx = msg.find("\n") # DETAIL starts after the first line feed
            if idx > -1:
                msg = msg[0:idx]
            raise RuntimeError(msg)
        
        finally:
            if cur:
                cur.close()
            # just in case caller didn't use sanepg2 which resets this already...
            self._dbc.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ)
    
    
class Catalog (object):
    """Provides basic catalog management.
    """
    
    _POSTGRES_REGISTRY = "postgres"
    _SUPPORTED_REGISTRY_TYPES = (_POSTGRES_REGISTRY)
    _SCHEMA_NAME = '_ermrest'
    _TABLE_NAME = 'meta'
    _MODEL_VERSION_TABLE_NAME = 'model_version'
    _DATA_VERSION_TABLE_NAME = 'data_version'
    META_OWNER = 'owner'
    META_READ_USER = 'read_user'
    META_WRITE_USER = 'write_user'
    META_SCHEMA_WRITE_USER = 'schema_write_user'
    META_CONTENT_READ_USER = 'content_read_user'
    META_CONTENT_WRITE_USER = 'content_write_user'
    ANONYMOUS = '*'

    # key cache by (str(descriptor), version)
    MODEL_CACHE = dict()

    def __init__(self, factory, descriptor, config=None):
        """Initializes the catalog.
           
           The 'factory' is the factory used to create this catalog.
           
           The 'descriptor' is a dictionary containing the connection 
           parameters needed to connect to the backend database.

           The 'config' is a full ERMrest config, passed to other
           delegates that might need it.
           
           Right now, this class uses lazy initialization. Thus it does not
           open a connection until required.
        """
        assert factory is not None
        assert descriptor is not None
        self.descriptor = descriptor
        self.dsn = self._serialize_descriptor(descriptor)
        self._factory = factory
        self._model = None
        self._config = config  # Not sure we need to tuck away the config

    def _serialize_descriptor(self, descriptor):
        """Serializes the descriptor.

           For postgres, currently the only supported form, the serialized 
           form follows the libpq format.
        """
        if 'type' not in descriptor or descriptor['type'] == self._POSTGRES_REGISTRY:
            return " ".join([ "%s=%s" % (key, descriptor[key]) for key in descriptor if key != 'type' ])
        else:
            raise KeyError("Catalog descriptor type not supported: %(type)s" % descriptor)

    def get_model_version(self, cur):
        cur.execute("""
SELECT max(snap_txid) AS txid FROM %(schema)s.%(table)s WHERE snap_txid < txid_snapshot_xmin(txid_current_snapshot()) ;
""" % dict(schema=self._SCHEMA_NAME, table=self._MODEL_VERSION_TABLE_NAME))
        self._model_version = cur.next()[0]  # TODO: do we need self._model_version to be an instance var?
        return self._model_version

    def get_model_update_version(self, cur):
        cur.execute("""
SELECT txid_current(); 
""" % dict(schema=self._SCHEMA_NAME, table=self._MODEL_VERSION_TABLE_NAME))
        return cur.next()[0] 

    def get_model(self, cur, config=None, private=False):
        # TODO: turn this into a @property
        if config is None:
            config = self._config
        cache_key = (str(self.descriptor), self.get_model_version(cur))
        self._model = self.MODEL_CACHE.get(cache_key)
        if self._model is None or private:
            try:
                self._model = introspect(cur, config)
            except ValueError, te:
                raise ValueError('Introspection on existing catalog failed (likely a policy mismatch): %s' % str(te))
            if not private:
                self.MODEL_CACHE[cache_key] = self._model
        return self._model
    
    def destroy(self):
        """Destroys the catalog (i.e., drops the database).
        
           This operation will fail if there are any other open connections to
           the database.
           
           Important: THIS OPERATION IS PERMANENT... unless you have backups ;)

           NOTE: This code is clearly b0rken
        """
        # the database connection must be closed
        sanepg2.pools[self._dbname].closeall() # TODO: this should reference the pool key not dbname
            
        # drop db cannot be called by a connection to the db, so the factory
        # must do it
        #
        # Note: factory's destroy method is not robust, so for a quick and 
        #       dirty imperfect workaround we retry 3 times here
        for i in range(3):
            try:
                self._factory._destroy_catalog(self)
                return
            except RuntimeError, ev:
                msg = str(ev)
                continue
        raise RuntimeError(msg)
    
    def init_meta(self, conn, cur, owner=None):
        """Initializes the Catalog metadata.
        
           When 'owner' is None, it initializes the catalog permissions with 
           the anonymous ('*') role, including the ownership.
        """
        if type(owner) is dict:
            owner = owner['id']
        
        # create schema, if it doesn't exist
        if not schema_exists(cur, self._SCHEMA_NAME):
            cur.execute("""
CREATE SCHEMA %(schema)s;
GRANT USAGE ON SCHEMA %(schema)s TO ermrest;
""" % dict(schema=self._SCHEMA_NAME)
                        )
            
        # create meta table, if it doesn't exist
        if not table_exists(cur, self._SCHEMA_NAME, self._TABLE_NAME):
            cur.execute("""
CREATE TABLE %(schema)s.%(table)s (
    key text NOT NULL,
    value text NOT NULL,
    UNIQUE (key, value)
);
""" % dict(schema=self._SCHEMA_NAME,
           table=self._TABLE_NAME)
                        )

        # create annotation storage tables
        for klass in annotatable_classes:
            klass.create_storage_table(cur)

        if not table_exists(cur, self._SCHEMA_NAME, 'model_pseudo_key'):
            cur.execute("""
CREATE TABLE _ermrest.model_pseudo_key (
  id serial PRIMARY KEY,
  schema_name text NOT NULL,
  table_name text NOT NULL,
  column_names text[] NOT NULL,
  comment text,
  UNIQUE(schema_name, table_name, column_names)
);
""")
            
        if not table_exists(cur, self._SCHEMA_NAME, 'model_pseudo_keyref'):
            cur.execute("""
CREATE TABLE _ermrest.model_pseudo_keyref (
  id serial PRIMARY KEY,
  name text UNIQUE,
  from_schema_name text NOT NULL,
  from_table_name text NOT NULL,
  from_column_names text[] NOT NULL,
  to_schema_name text NOT NULL,
  to_table_name text NOT NULL,
  to_column_names text[] NOT NULL,
  comment text,
  UNIQUE(from_schema_name, from_table_name, from_column_names, to_schema_name, to_table_name, to_column_names)
);
""")
            
        if not table_exists(cur, self._SCHEMA_NAME, self._MODEL_VERSION_TABLE_NAME):
            cur.execute("""
CREATE TABLE %(schema)s.%(table)s (
    snap_txid bigint PRIMARY KEY
);

CREATE DOMAIN longtext text;
CREATE DOMAIN markdown text;
CREATE DOMAIN gene_sequence text;

CREATE OR REPLACE FUNCTION %(schema)s.current_client() RETURNS text STABLE AS $$
BEGIN
  RETURN current_setting('webauthn2.client');
EXCEPTION WHEN OTHERS THEN
  RETURN NULL::text;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION %(schema)s.current_attributes() RETURNS text[] STABLE AS $$
BEGIN
  RETURN (SELECT array_agg(value) FROM json_array_elements_text(current_setting('webauthn2.attributes')::json));
EXCEPTION WHEN OTHERS THEN
  RETURN NULL::text[];
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION %(schema)s.model_change_event() RETURNS void AS $$
DECLARE

  resultbool boolean;
  trigger_txid bigint;

BEGIN

  SELECT txid_current() INTO trigger_txid;

  SELECT EXISTS (SELECT snap_txid 
                 FROM %(schema)s.%(table)s 
                 WHERE snap_txid = trigger_txid) 
  INTO resultbool ;

  IF NOT resultbool THEN

    INSERT INTO %(schema)s.%(table)s (snap_txid)
      SELECT trigger_txid ;

  END IF;

END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION %(schema)s.model_change_trigger() RETURNS event_trigger AS $$
BEGIN
  PERFORM %(schema)s.model_change_event();
END;
$$ LANGUAGE plpgsql;

SELECT %(schema)s.model_change_event() ;

-- NEED TO BE POSTGRES SUPERUSER TO REGISTER AN EVENT TRIGGER!
-- This will also fire on every REST data PUT because we use temporary tables
-- Without the trigger, we only bump model version on REST schema changes but not 
-- out-of-band schema changes on server.

-- CREATE EVENT TRIGGER trigger_for_model_changes ON ddl_command_end
-- WHEN TAG IN (
--   'ALTER SCHEMA', 'ALTER TABLE', 'CREATE INDEX', 'CREATE SCHEMA', 'CREATE TABLE', 'CREATE TABLE AS', 'DROP SCHEMA', 'DROP TABLE', 'DROP INDEX'
-- )
-- EXECUTE PROCEDURE model_change_trigger() ;

""" % dict(schema=self._SCHEMA_NAME,
           table=self._MODEL_VERSION_TABLE_NAME)
                        )
            
        if not table_exists(cur, self._SCHEMA_NAME, self._DATA_VERSION_TABLE_NAME):
            cur.execute("""
CREATE TABLE %(schema)s.%(table)s (
    "schema" text,
    "table" text,
    snap_txid bigint,
    PRIMARY KEY ("schema", "table", "snap_txid")
);

CREATE OR REPLACE FUNCTION %(schema)s.data_change_event(sname text, tname text) RETURNS void AS $$
DECLARE

  resultbool boolean;
  trigger_txid bigint;

BEGIN

  SELECT txid_current() INTO trigger_txid;

  SELECT EXISTS (SELECT snap_txid 
                 FROM %(schema)s.%(table)s 
                 WHERE "schema" = sname
                   AND "table" = tname
                   AND snap_txid = trigger_txid) 
  INTO resultbool ;

  IF NOT resultbool THEN

    INSERT INTO %(schema)s.%(table)s ("schema", "table", snap_txid)
      SELECT sname, tname, trigger_txid ;

  END IF;

END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION %(schema)s.data_change_trigger() RETURNS trigger AS $$
BEGIN
  PERFORM %(schema)s.data_change_event( TG_TABLE_SCHEMA::text, TG_TABLE_NAME::text );
END;
$$ LANGUAGE plpgsql;

-- Apply this trigger to each table to get automatic data-change detection

-- CREATE TRIGGER data_changes_on_sname_tname 
--   AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE 
--   ON sname.tname FOR EACH STATEMENT
--   EXECUTE PROCEDURE %(schema)s.data_change_trigger() ;

""" % dict(schema=self._SCHEMA_NAME,
           table=self._DATA_VERSION_TABLE_NAME)
                        )

        cur.execute("""
GRANT SELECT -- INSERT, UPDATE, DELETE
  ON _ermrest.meta, _ermrest.model_pseudo_key, _ermrest.model_pseudo_keyref
  TO ermrest;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON _ermrest.model_version, _ermrest.data_version 
  TO ermrest;
GRANT ALL ON ALL SEQUENCES IN SCHEMA _ermrest TO ermrest;
""")
            
        ## initial meta values
        owner = owner if owner else self.ANONYMOUS
        self.add_meta(cur, self.META_OWNER, owner)
        self.add_meta(cur, self.META_WRITE_USER, owner)
        self.add_meta(cur, self.META_READ_USER, owner)
        self.add_meta(cur, self.META_SCHEMA_WRITE_USER, owner)
        self.add_meta(cur, self.META_CONTENT_READ_USER, owner)
        self.add_meta(cur, self.META_CONTENT_WRITE_USER, owner)
        
    
    # TODO: change API to pass conn/cur through for request handler hot-path
    def get_meta(self, cur, key=None, value=None):
        """Gets metadata fields, optionally filtered by attribute key or by 
           key and value pair, to test existence of specific pair.
        """
        where = ''
        if key is not None:
            where = "WHERE key = %s" % sql_literal(key)
            if value is not None:
                if hasattr(value, '__iter__'):
                    where += " AND value = ANY (ARRAY[%s]::text[])" % (
                        ','.join([sql_literal(v) for v in value]))
                else:
                    where += " AND value = %s" % sql_literal(value)

        cur.execute("""
SELECT key, array_agg(value) AS values FROM %(schema)s.%(table)s
%(where)s
GROUP BY key
;""" % dict(schema=self._SCHEMA_NAME,
            table=self._TABLE_NAME,
            where=where) 
                    )
        result = {}
        for k, v in cur:
            result[k] = v
        return result
    
    def add_meta(self, cur, key, value):
        """Adds a metadata (key, value) pair.
        """
        cur.execute("""
INSERT INTO %(schema)s.%(table)s
  (key, value)
VALUES
  (%(key)s, %(value)s)
EXCEPT
SELECT key, value FROM %(schema)s.%(table)s
;
""" % dict(schema=self._SCHEMA_NAME,
           table=self._TABLE_NAME,
           key=sql_literal(key),
           value=sql_literal(value)
           )
                    )
            
    def remove_meta(self, cur, key, value=None):
        """Removes a metadata (key, value) pair or all pairs that match on the
           key alone.
        """
        where = "WHERE key = %s" % sql_literal(key)
        if value:
            where += " AND value = %s" % sql_literal(value)
            
        cur.execute("""
DELETE FROM %(schema)s.%(table)s
%(where)s
;
""" % dict(schema=self._SCHEMA_NAME,
           table=self._TABLE_NAME,
           where=where
           ) 
                    )
    
    def _test_perm(self, cur, perm, roles):
        """Tests whether the user roles have a permission.
        """
        if not (type(roles) is set or type(roles) is list):
            roles = [roles]
        roles = set([ r['id'] if type(r) is dict else r for r in roles ])
        return len(self.get_meta(cur, perm, roles.union(self.ANONYMOUS))) > 0
                                  
    def has_read(self, cur, roles):
        """Tests whether the user roles have read permission.
        """
        return self.is_owner(cur, roles) or self._test_perm(cur, self.META_READ_USER, roles)
    
    def has_write(self, cur, roles):
        """Tests whether the user roles have write permission.
        """
        return self.is_owner(cur, roles) or self._test_perm(cur, self.META_WRITE_USER, roles)
    
    def has_schema_write(self, cur, roles):
        """Tests whether the user roles have schema write permission.
        """
        return self.is_owner(cur, roles) or self._test_perm(cur, self.META_SCHEMA_WRITE_USER, roles)
                                  
    def has_content_read(self, cur, roles):
        """Tests whether the user roles have content read permission.
        """
        return self.is_owner(cur, roles) or self._test_perm(cur, self.META_CONTENT_READ_USER, roles)
    
    def has_content_write(self, cur, roles):
        """Tests whether the user roles have content write permission.
        """
        return self.is_owner(cur, roles) or self._test_perm(cur, self.META_CONTENT_WRITE_USER, roles)
    
    def is_owner(self, cur, roles):
        """Tests whether the user role is owner.
        """
        return self._test_perm(cur, self.META_OWNER, roles)


