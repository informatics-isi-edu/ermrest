
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

"""ERMREST URL abstract syntax tree (AST) for data resources.

"""

import path
from path import Api

import ermrest.ermpath

class Entity (Api):
    """A specific entity set by entitypath."""
    def __init__(self, catalog, path):
        self.catalog = catalog
        self.path = path

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.EntityPath instance that can
           be used to perform entity-level data access.
        """
        epath = ermpath.EntityPath(model)
        # TODO: resolve and translate path
        return epath


class Attribute (Api):
    """A specific attribute set by attributepath."""
    def __init__(self, catalog, path):
        self.catalog = catalog
        self.attributes = path[-1]
        self.epath = Entity(catalog, path[0:-1])

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.AttributePath instance that
           can be used to perform attribute-level data access.
        """
        epath = self.epath.resolve(model)
        # TODO: validate attributes
        attributes = self.attributes
        return AttributePath(epath, attributes)
    

class Query (Api):
    """A specific query set by querypath."""
    def __init__(self, catalog, path):
        self.catalog = catalog
        self.expressions = path[-1]
        self.epath = Entity(catalog, path[0:-1])

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.AttributePath instance that
           can be used to perform attribute-level data access.
        """
        epath = self.epath.resolve(model)
        # TODO: validate expressions
        expressions = self.expressions
        return QueryPath(epath, expressions)
    
