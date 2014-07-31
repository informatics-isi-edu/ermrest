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
Catalog management module.

This module provides catalog management features including:
    - create and delete catalogs
    - modify catalog policies (e.g., permissions, quotas, etc.)
    - modify catalog metadata
"""
## NOTE: At this point, the abstractions in this module are rather weak.
##  Ideally, we might make the db-specifics (dbname, dsn, etc) opaque to the
##  caller and get some bootstrapping information out of a configuration file.
##  Then the rest of the operations could be based on "Catalogs" as more 
##  opaque encapsulations of the database details.

import uuid
import base64
import psycopg2
import sanepg2
from webauthn2.util import PooledConnection
import web

from util import sql_identifier, sql_literal, schema_exists, table_exists
from ermrest.model import introspect

__all__ = ['CatalogFactory', 'Catalog']


class CatalogFactory (object):
    """The catalog factory.
    
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
    
    def __init__(self, config=None):
        """Initialize the Catalog Factory.
        
           config : configuration parameters for the factory.
           
           The database (config['database_name']) dbuser must be a 
           super user or have CREATEDB permissions.
        """
        # Yes, this will fail here if not configured correctly
        self._dbc = psycopg2.connect(dbname=config['database_name'],
                             connection_factory=sanepg2.connection)        
        
        
    def create(self):
        """Create a Catalog.
        
           This operation creates a catalog (i.e., it creates a database) on 
           the same host as the catalog factory. It does not initialize or 
           register the catalog.
           
           Returns the new catalog object representing the catalog.
        """
        # create database
        dbname = _random_name(prefix='_ermrest_')
        self._dbc.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        try:
            cur = self._dbc.cursor()
            cur.execute("CREATE DATABASE " + sql_identifier(dbname))
            self._dbc.commit()
        except psycopg2.Error, ev:
            msg = str(ev)
            idx = msg.find("\n") # DETAIL starts after the first line feed
            if idx > -1:
                msg = msg[0:idx]
            raise RuntimeError(msg)
        finally:
            self._dbc.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)
        
        return Catalog(self, dict(dbname=dbname))
    
    
    def _destroy_catalog(self, catalog):
        """Destroys a catalog.
        
           Do not call this method directly.
        """
        try:
            self._dbc.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            
            # first, attempt to disconnect clients
            cur = self._dbc.cursor()
            cur.execute("""
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = %(dbname)s
  AND pid <> pg_backend_pid()
;"""
                % dict(dbname=sql_literal(catalog.descriptor['dbname'])))
            
            #TODO: note that a client could reconnect ...now... and prevent the drop
            
            # then, drop database
            cur.execute("DROP DATABASE " + 
                        sql_identifier(catalog.descriptor['dbname']))
            
        except psycopg2.Error, ev:
            msg = str(ev)
            idx = msg.find("\n") # DETAIL starts after the first line feed
            if idx > -1:
                msg = msg[0:idx]
            raise RuntimeError(msg)
        
        finally:
            self._dbc.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)
    
    
class Catalog (PooledConnection):
    """Provides basic catalog management.
    """
    
    _SCHEMA_NAME = '_ermrest'
    _TABLE_NAME = 'meta'
    _MODEL_VERSION_TABLE_NAME = 'model_version'
    _DATA_VERSION_TABLE_NAME = 'data_version'
    _DBNAME = 'dbname'
    META_OWNER = 'owner'
    META_READ_USER = 'read_user'
    META_WRITE_USER = 'write_user'
    META_CONTENT_READ_USER = 'content_read_user'
    META_CONTENT_WRITE_USER = 'content_write_user'
    ANONYMOUS = '*'

    # key cache by (dbname, version)
    MODEL_CACHE = dict()
    
    def __init__(self, factory, descriptor):
        """Initializes the catalog.
           
           The 'factory' is the factory used to create this catalog.
           
           The 'descriptor' is a dictionary containing the connection 
           parameters needed to connect to the backend database.
           
           Right now, this class uses lazy initialization. Thus it does not
           open a connection until required.
        """
        assert descriptor.get(self._DBNAME) is not None
        self.descriptor = descriptor
        self._factory = factory
        self._dbc = None
        self._model = None

        pool_key = (self.descriptor[self._DBNAME],)
        PooledConnection.__init__(self, pool_key)

    def _new_connection(self):
        """Create raw connection to be managed by parent pool class"""
        return psycopg2.connect(dbname=self.descriptor[self._DBNAME],
                                connection_factory=sanepg2.connection)
        
    def __del__(self):
        if self._dbc:
            self._dbc.close()
            self._dbc = None
        
    def get_connection(self):
        """Get connection from pool"""
        # TODO: turn this into a @property
        if not self._dbc:
            self._dbc = self._get_pooled_connection()
        return self._dbc

    def discard_connection(self, conn):
        """Discard connection from pool"""
        assert conn  == self._dbc
        try:
            self._dbc.close()
        except:
            pass
        self._dbc = None
    
    def release_connection(self, conn):
        """Return connection to pool"""
        assert conn  == self._dbc
        self._put_pooled_connection(conn)
        self._dbc = None
    
    def get_model_version(self, conn):
        cur = conn.cursor()
        cur.execute("""
SELECT max(snap_txid) AS txid FROM %(schema)s.%(table)s WHERE snap_txid < txid_snapshot_xmin(txid_current_snapshot()) ;
""" % dict(schema=self._SCHEMA_NAME, table=self._MODEL_VERSION_TABLE_NAME))
        self._model_version = cur.next()[0]
        cur.close()
        return self._model_version

    def get_model(self, conn=None):
        # TODO: turn this into a @property
        if conn is None:
            conn = self.get_connection()
        if not self._model:
            cache_key = (self.descriptor[self._DBNAME], self.get_model_version(conn))
            self._model = self.MODEL_CACHE.get(cache_key)
            if self._model is None:
                self._model = introspect(conn)
                self.MODEL_CACHE[cache_key] = self._model
        return self._model
    
    def destroy(self):
        """Destroys the catalog (i.e., drops the database).
        
           This operation will fail if there are any other open connections to
           the database.
           
           Important: THIS OPERATION IS PERMANENT... unless you have backups ;)
        """
        # the database connection must be closed
        if self._dbc:
            self._dbc.close()
            self._dbc = None
            
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
    
    
    def is_initialized(self):
        """Tests whether the catalog's database has been initialized.
        
           An initialized catalog's database has the ERMREST schema. If not 
           initialized, the catalog does not have metadata and other policy
           fields defined.
        """
        # TODO: turn this into a @property
        return table_exists(self._dbc, self._SCHEMA_NAME, self._TABLE_NAME)
    
    
    def init_meta(self, owner=None):
        """Initializes the Catalog metadata.
        
           When 'owner' is None, it initializes the catalog permissions with 
           the anonymous ('*') role, including the ownership.
        """
        
        # first, deploy the metadata schema
        cur = None
        try:
            cur = self.get_connection().cursor()
            
            # create schema, if it doesn't exist
            if not schema_exists(self._dbc, self._SCHEMA_NAME):
                cur.execute("""
CREATE SCHEMA %(schema)s;"""
                    % dict(schema=self._SCHEMA_NAME))
            
            # create meta table, if it doesn't exist
            if not table_exists(self._dbc, self._SCHEMA_NAME, self._TABLE_NAME):
                cur.execute("""
CREATE TABLE %(schema)s.%(table)s (
    key text NOT NULL,
    value text NOT NULL,
    UNIQUE (key, value)
);"""
                    % dict(schema=self._SCHEMA_NAME,
                           table=self._TABLE_NAME))
            
            if not table_exists(self._dbc, self._SCHEMA_NAME, self._MODEL_VERSION_TABLE_NAME):
                cur.execute("""
CREATE TABLE %(schema)s.%(table)s (
    snap_txid bigint PRIMARY KEY
);

CREATE OR REPLACE FUNCTION %(schema)s.model_change_event() RETURNS void AS $$
DECLARE

  resultbool boolean;
  trigger_txid bigint;
  previous_txid bigint;
  snapshot txid_snapshot;

BEGIN

  SELECT txid_current() INTO trigger_txid;

  SELECT EXISTS (SELECT snap_txid 
                 FROM %(schema)s.%(table)s 
                 WHERE snap_txid = trigger_txid) 
  INTO resultbool ;

  IF NOT resultbool THEN

    SELECT txid_current_snapshot() INTO snapshot;

    SELECT max(snap_txid) INTO previous_txid
    FROM %(schema)s.%(table)s
    WHERE snap_txid < txid_snapshot_xmin(snapshot) ;

    INSERT INTO %(schema)s.%(table)s (snap_txid)
      SELECT trigger_txid ;

    DELETE FROM %(schema)s.%(table)s 
    WHERE snap_txid < previous_txid ;

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
            
            if not table_exists(self._dbc, self._SCHEMA_NAME, self._DATA_VERSION_TABLE_NAME):
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
  previous_txid bigint;
  snapshot txid_snapshot;

BEGIN

  SELECT txid_current() INTO trigger_txid;

  SELECT EXISTS (SELECT snap_txid 
                 FROM %(schema)s.%(table)s 
                 WHERE "schema" = sname
                   AND "table" = tname
                   AND snap_txid = trigger_txid) 
  INTO resultbool ;

  IF NOT resultbool THEN

    SELECT txid_current_snapshot() INTO snapshot;

    SELECT max(snap_txid) INTO previous_txid
    FROM %(schema)s.%(table)s
    WHERE "schema" = sname
      AND "table" = tname
      AND snap_txid < txid_snapshot_xmin(snapshot) ;

    INSERT INTO %(schema)s.%(table)s ("schema", "table", snap_txid)
      SELECT sname, tname, trigger_txid ;

    DELETE FROM %(schema)s.%(table)s 
    WHERE "schema" = sname
      AND "table" = tname
      AND snap_txid < previous_txid ;

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
            
            self._dbc.commit()
        finally:
            if cur is not None:
                cur.close()
                
        ## initial meta values
        owner = owner if owner else self.ANONYMOUS
        self.add_meta(self.META_OWNER, owner)
        self.add_meta(self.META_WRITE_USER, owner)
        self.add_meta(self.META_READ_USER, owner)
        self.add_meta(self.META_CONTENT_READ_USER, owner)
        self.add_meta(self.META_CONTENT_WRITE_USER, owner)
        
    
    def get_meta(self, key=None, value=None):
        """Gets metadata fields, optionally filtered by attribute key or by 
           key and value pair, to test existence of specific pair.
        """
        where = ''
        if key:
            where = "WHERE key = %s" % sql_literal(key)
            if value:
                if hasattr(value, '__iter__'):
                    where += " AND value IN (%s)" % (
                                    ','.join([sql_literal(v) for v in value]))
                else:
                    where += " AND value = %s" % sql_literal(value)
        
        cur = None
        try:
            cur = self.get_connection().execute("""
SELECT * FROM %(schema)s.%(table)s
%(where)s
;"""
                % dict(schema=self._SCHEMA_NAME,
                       table=self._TABLE_NAME,
                       where=where) )
            
            meta = list()
            for k, v in cur:
                meta.append(dict(key=k, value=v))
            self._dbc.commit()
            return meta
        except psycopg2.ProgrammingError:
            self._dbc.rollback()
            return list()
        # BUG: other exceptions will not rollback??
        finally:
            if cur is not None:
                cur.close()
    
    def add_meta(self, key, value):
        """Adds a metadata (key, value) pair.
        """
        cur = None
        try:
            cur = self.get_connection().cursor()
            cur.execute("""
INSERT INTO %(schema)s.%(table)s
  (key, value)
VALUES
  (%(key)s, %(value)s)
;"""
                % dict(schema=self._SCHEMA_NAME,
                       table=self._TABLE_NAME,
                       key=sql_literal(key),
                       value=sql_literal(value)) )
            
            self._dbc.commit()
            
        except psycopg2.IntegrityError:
            # Ignore attempt to add a duplicate entry
            self._dbc.rollback()
        finally:
            if cur is not None:
                cur.close()
    
    def set_meta(self, key, value):
        """Sets a metadata (key, value) pair.
        """
        cur = None
        try:
            cur = self.get_connection().cursor()
            cur.execute("""
DELETE FROM %(schema)s.%(table)s
WHERE key=%(key)s
;
INSERT INTO %(schema)s.%(table)s
  (key, value)
VALUES
  (%(key)s, %(value)s)
;"""
                % dict(schema=self._SCHEMA_NAME,
                       table=self._TABLE_NAME,
                       key=sql_literal(key),
                       value=sql_literal(value)) )
            
            self._dbc.commit()
            
        finally:
            if cur is not None:
                cur.close()
    
    def remove_meta(self, key, value=None):
        """Removes a metadata (key, value) pair or all pairs that match on the
           key alone.
        """
        where = "WHERE key = %s" % sql_literal(key)
        if value:
            where += " AND value = %s" % sql_literal(value)
            
        cur = None
        try:
            cur = self.get_connection().cursor()
            cur.execute("""
DELETE FROM %(schema)s.%(table)s
%(where)s
;"""
                % dict(schema=self._SCHEMA_NAME,
                       table=self._TABLE_NAME,
                       where=where) )
            
            self._dbc.commit()
        finally:
            if cur is not None:
                cur.close()
    
    
    def _test_perm(self, perm, roles):
        """Tests whether the user roles have a permission.
        """
        return len(self.get_meta(perm, roles.union(self.ANONYMOUS))) > 0
                                  
    def has_read(self, roles):
        """Tests whether the user roles have read permission.
        """
        return self.is_owner(roles) or self._test_perm(self.META_READ_USER, roles)
    
    def has_write(self, roles):
        """Tests whether the user roles have write permission.
        """
        return self.is_owner(roles) or self._test_perm(self.META_WRITE_USER, roles)
                                  
    def has_content_read(self, roles):
        """Tests whether the user roles have content read permission.
        """
        return self.is_owner(roles) or self._test_perm(self.META_CONTENT_READ_USER, roles)
    
    def has_content_write(self, roles):
        """Tests whether the user roles have content write permission.
        """
        return self.is_owner(roles) or self._test_perm(self.META_CONTENT_WRITE_USER, roles)
    
    def is_owner(self, roles):
        """Tests whether the user role is owner.
        """
        return len(self.get_meta(self.META_OWNER, roles))>0


def _random_name(prefix=''):
    """Generates and returns a random name safe for use in the database.
    """
    ## This might be useful as a general utility
    return prefix + base64.urlsafe_b64encode(uuid.uuid4().bytes).replace('=','')
