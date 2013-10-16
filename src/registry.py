
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

import exceptions

class Registry:
    """A registry of ERMREST catalogs.
    
       Supports the registration (or un-registration) and lookup of ERMREST 
       catalogs. Note that "registering" is not the same as creating a catalog.
       A catalog should be created separately using the CatalogManager utility.
       
       Creating a registering a catalog therefore is a two-step process. First,
       one creates the catalog then registers it. The registration effectively
       amounts to a binding between an 'id' and a 'connstr' (connection 
       string) that specifies where to find the catalog and how to connect to
       it. The details of 'connstr' are yet TBD.
    """
    
    def lookup(self, id):
        """Lookup a registry and retrieve its description.
        
           'id' : an identifier (not sure we have defined it precisely,
                  at present an integer)
           
           returns : a catalog connection string.
        """
        raise exceptions.NotImplementedError()
    
    def all(self, id):
        """Lookup all catalogs.
        
           returns : not sure whether this should return an iterator over
                     catalog 'id's or 'connstr's or ('id', 'connstr') pairs.
                     Probably should be the latter.
        """
        raise exceptions.NotImplementedError()
    
    def register(self, id, connstr):
        """Register a catalog description.
        
           This does not create the catalog.
           
           'id' : the id of the catalog to register.
           'connstr' : the connection string.
        """
        raise exceptions.NotImplementedError()
    
    def unregister(self, id):
        """Unregister a catalog description.
        
           'id' : the id of the catalog to unregister.
        """
        raise exceptions.NotImplementedError()
    

class SimpleRegistry (Registry):
    """A simple registry implementation with a database backend.
    
       On the first pass this impl will simply use a database for each
       operation. If we end up using this impl for non-pilot users, it
       should be upgraded with at least local caching of registries.
    """
    
    def __init__(self):
        super(self, SimpleRegistry).__init__()
        
