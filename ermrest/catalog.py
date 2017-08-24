
# 
# Copyright 2013-2017 University of Southern California
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

import web
import psycopg2
import sanepg2
import pkgutil

from util import sql_identifier, sql_literal, schema_exists, table_exists, random_name
from .model import introspect, current_model_version
from .model.misc import annotatable_classes, hasacls_classes, hasdynacls_classes
from . import sql

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
                conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)

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
            self._dbc.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
    
    
class Catalog (object):
    """Provides basic catalog management.
    """
    
    _POSTGRES_REGISTRY = "postgres"
    _SUPPORTED_REGISTRY_TYPES = (_POSTGRES_REGISTRY)

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

    def get_model_update_version(self, cur):
        cur.execute("SELECT now();")
        return cur.next()[0]

    def get_model(self, cur=None, config=None, private=False):
        if cur is None:
            cur = web.ctx.ermrest_catalog_pc.cur
        if config is None:
            config = self._config
        cache_key = (str(self.descriptor), current_model_version(cur))
        model = self.MODEL_CACHE.get(cache_key)
        if (model is None) or private:
            model = introspect(cur, config)

            if private:
                assert self.MODEL_CACHE.get(cache_key) != model
            
            if not private:
                self.MODEL_CACHE[cache_key] = model
        return model
    
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
        cur.execute(pkgutil.get_data(sql.__name__, 'ermrest_schema.sql'))
        cur.execute('SELECT _ermrest.model_change_event();')
        cur.execute('ANALYZE;')

        if type(owner) is dict:
            owner = owner['id']
            
        ## initial policy
        model = self.get_model(cur, self._config)
        owner = owner if owner else '*'
        model.acls['owner'] = [owner] # set so enforcement won't deny subsequent set_acl()
        model.set_acl(cur, 'owner', [owner])
