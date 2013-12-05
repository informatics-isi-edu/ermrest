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
            cur.execute("CREATE DATABASE " + dbname)
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
        self._dbc.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        try:
            cur = self._dbc.cursor()
            cur.execute("DROP DATABASE " + catalog.descriptor['dbname'])
        except psycopg2.Error, ev:
            msg = str(ev)
            idx = msg.find("\n") # DETAIL starts after the first line feed
            if idx > -1:
                msg = msg[0:idx]
            raise RuntimeError(msg)
        finally:
            self._dbc.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)
    
    
class Catalog (object):
    """Provides basic catalog management.
    """
    
    def __init__(self, factory, descriptor):
        """Initializes the catalog.
           
           The 'factory' is the factory used to create this catalog.
           
           The 'descriptor' is a dictionary containing the connection 
           parameters needed to connect to the backend database.
           
           Right now, this class uses lazy initialization. Thus it does not
           open a connection until required.
        """
        self.descriptor = descriptor
        self._factory = factory
        self._dbc = None
        
    def get_connection(self):
        if not self._dbc:
            self._dbc = psycopg2.connect(dbname=self.descriptor['dbname'],
                                         connection_factory=sanepg2.connection)
        return self._dbc
    
    
    def destroy(self):
        """Destroys the catalog (i.e., drops the database).
        
           This operation will fail if there are any other open connections to
           the database.
           
           Important: THIS OPERATION IS PERMANENT... unless you have backups ;)
        """
        # the database connection must be closed
        if self._dbc:
            self._dbc.close()
            
        # drop db cannot be called by a connection to the db, so the factory
        # must do it
        self._factory._destroy_catalog(self)
    
    
    def is_initialized(self):
        """Tests whether the catalog's database has been initialized.
        
           An initialized catalog's database has the ERMREST schema. If not 
           initialized, the catalog does not have metadata and other policy
           fields defined.
        """
        pass
    
    
    def get_meta(self, key=None):
        """Gets metadata fields, optionally filtered by attribute key.
        """
        pass
    
    
    def add_meta(self, key, value):
        """Adds a metadata (key, value) pair.
        """
        pass
    
    
    def remove_meta(self, key, value):
        """Removes a metadata (key, value) pair.
        """
        pass
    
    
    def has_read(self, role):
        """Tests whether the user role has read permission.
        """
        pass
    
    
    def has_write(self, role):
        """Tests whether the user role has write permission.
        """
        pass
    

def _random_name(prefix=''):
    """Generates and returns a random name safe for use in the database.
    """
    ## This might be useful as a general utility
    return prefix + base64.urlsafe_b64encode(uuid.uuid4().bytes).replace('=','')
