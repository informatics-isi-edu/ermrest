
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
from ermrest import ermpath
import ermrest.model

class Entity (Api):
    """A specific entity set by entitypath."""
    def __init__(self, catalog, path):
        Api.__init__(self, catalog)
        self.path = path

    def resolve(self, model):
        """Resolve self against a specific database model.

           The path is validated against the model and any unqualified
           names or implicit entity referencing patterns are resolved
           to a canonical ermrest.ermpath.EntityPath instance that can
           be used to perform entity-level data access.
        """
        epath = ermpath.EntityPath(model)

        if not hasattr(self.path[0], 'resolve_table'):
            raise TypeError('Entity paths must start with table syntax.')

        epath.set_base_entity( 
            self.path[0].name.resolve_table(model),
            self.path[0].alias
            )

        for elem in self.path[1:]:
            if elem.is_filter:
                epath.add_filter(elem)
            else:
                keyref, refop, lalias = elem.resolve_link(model, epath)
                epath.add_link(keyref, refop, elem.alias, lalias)
                # TODO: consider two-hop resolution via implied association table?
                #   will add intermediate link to epath...

        return epath

    def GET(self, uri):
        """Perform HTTP GET of entities.
        """
        def body(conn):
            # TODO: map exceptions into web errors
            model = ermrest.model.introspect(conn)
            epath = self.resolve(model)
            # TODO: content-type negotiation?
            return epath.get_iter(conn, content_type='application/json')

        def post_commit(lines):
            # TODO: set web.py response headers/status
            for line in lines:
                yield line

        return self.perform(body, post_commit)


class Attribute (Api):
    """A specific attribute set by attributepath."""
    def __init__(self, catalog, path):
        Api.__init__(self, catalog)
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
        Api.__init__(self, catalog)
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
    
