
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

class Attribute (Api):
    """A specific attribute set by attributepath."""
    def __init__(self, catalog, path):
        self.catalog = catalog
        self.path = path

class Entity (Api):
    """A specific entity set by entitypath."""
    def __init__(self, catalog, path):
        self.catalog = catalog
        self.path = path

class Query (Api):
    """A specific query set by querypath."""
    def __init__(self, catalog, path):
        self.catalog = catalog
        self.path = path

