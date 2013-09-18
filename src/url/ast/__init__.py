
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

"""ERMREST URL abstract syntax tree (AST).

The AST represents the parsed content but does not semantically
validate it since the actual catalog and catalog-specific ERM is not
know at parse time.

Deferred validation is performed by a second pass through the AST
once an appropriate database connection is available.

"""

from catalog import Catalogs, Catalog
import model
import data

class Name (object):
    """Represent a qualified or unqualified name in an ERMREST URL.

    """
    def __init__(self, absolute=False):
        """Initialize a zero-element name container.

           absolute = True means a name with leading ':'
           absolute = False means a name with leading text (default)
        """
        self.absolute = absolute
        self.nameparts = []

    def __len__(self):
        return len(self.nameparts)

    def __iter__(self):
        return iter(self.nameparts)

    def with_suffix(self, namepart):
        """Append a namepart to a qualifying prefix, returning full name.

           This method mutates the name and returns it as a
           convenience for composing more calls.
        """
        self.nameparts.append(namepart)
        return self
        
    def resolve(self, model, path=None, elem=None):
        """Resolve self against a specific database model and context.
        
           Absolute names :schema:table:column or :schema:table can
           only be resolved from a model.

           Relative names are conditionally resolved in order:

             1. For n0:n1 with path where n0 is alias in path, then n1
                must be a column in the path element referenced by
                alias n0.

             2. For n0 with elem, n0 must be a column in the elem.

             3. Any n0:n1:n2 
        
           Raises KeyError on failed resolution.
        """

        return model.name_lookup(self)

