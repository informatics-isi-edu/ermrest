
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
