
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

"""ERMREST data path support

The data path is the core ERM-aware mechanism for searching,
navigating, and manipulating data in an ERMREST catalog.

"""

class EntityElem (object):
    """Wrapper for instance of entity table in path.

    """
    def __init__(self, table, pos):
        self._table = table
        self._pos = pos

class EntityPath (object):
    """Hierarchical ERM data access to whole entities, i.e. table rows.

    """
    def __init__(self, model):
        self._model = model
        self._path = None
        self.aliases = {}

    def set_base_entity(self, table, alias=None):
        assert self._path is None
        self._path = [ EntityElem(table, 0) ]
        if alias is not None:
            self.aliases[alias] = 0

    def add_filter(self, filt):
        pass

    def add_reference_link(self, leftkey, refop, rightkey, alias=None):
        pass

class AttributePath (object):
    """Hierarchical ERM data access to entity attributes, i.e. table cells.

    """
    def __init__(self, epath, attributes):
        self.epath = epath
        self.attributes = attributes

class QueryPath (object):
    """Hierarchical ERM data access to query results, i.e. computed rows.

    """
    def __init__(self, epath, expressions):
        self.epath = epath
        self.expressions = expressions

