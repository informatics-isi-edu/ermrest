
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

"""ERMREST URL abstract syntax tree (AST) for data resource path-addressing.

"""


class Path (list):
    pass

class SingleElem (object):
    """A path element with a single name may be a table or column."""
    def __init__(self, name):
        self.name = name

class MultiElem (object):
    """A path element with multiple names must be columns."""
    def __init__(self, names):
        self.names = names

class ReferenceLeft (object):
    """A path element referencing left-hand columns."""
    def __init__(self, alias, cols):
        self.alias = alias
        self.cols = cols

class ReferenceRight (object):
    """A path element referencing right-hand columns."""
    def __init__(self, table, cols):
        self.table = table
        self.cols = cols
        

class ReferenceElem (object):
    """A path element with directional reference addressing syntax."""
    def __init__(self, left=None, direction=None, right=None):
        self.left = left
        self.direction = direction
        self.right = right
    

class FilterElem (object):
    """A path element that applies a filter."""
    def __init__(self, pred):
        self.pred = pred


class Predicate (object):
    def __init__(self, left_val, op, right_val=None):
        self.left_val = left_val
        self.op = op
        self.right_val = right_val


class Negation (object):
    def __init__(self, predicate):
        self.predicate = predicate

class Conjunction (list):
    pass

class Disjunction (list):
    pass


