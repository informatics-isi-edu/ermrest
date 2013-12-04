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
    
    def __init__(self, dbc):
        """Initialize the Catalog Factory.
        
           dbc : a postgres database connection. The db user must be a 
                 super user or have CREATEDB permissions.
        """
        ## TBD: is there something besides a dbc that this factory could use
        ##      in order to initialize itself, something more opaque to the
        ##      caller like a configuration object?
        pass
    
    def create(self, dbname):
        """Create a Catalog.
        
           dbname : the database name for the catalog to be created.
           
           Returns : a catalog object.
        """
        ## TBD: should it create a "catalog" without taking a database name?
        pass
    
    def initialize(self, catalog):
        """Initializes a Catalog.
        
           Initialization adds the ERMREST specific schema to an existing 
           database.
        """
        pass
    
    def delete(self, dbname):
        """Delete a Catalog.
        
           Important: This operation is permanent.
           
           dbname : the database name of the catalog to be deleted.
        """
        ## TBD: should it take a Catalog instance instead of the dbname?
        pass
    
    def load(self, dsn):
        """Load a Catalog.
        
           dsn : the database connection string for the catalog.
           
           Returns : a catalog object.
        """
        ## TBD: should it take a catalog id instead?
        
        # create pg conn
        # initial Catalog with pg conn
        # return catalog instance
        pass

    
class Catalog (object):
    """The catalog management interface.
    
       This object should be instantiated via the CatalogFactory only.
    """
    
    def __init__(self, dbc):
        pass
    
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
