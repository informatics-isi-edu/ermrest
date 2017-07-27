
# 
# Copyright 2013-2016 University of Southern California
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

class PathElem (object):
    is_filter = False
    is_context = False

class TableElem (PathElem):
    """A path element with a single name must be a table."""
    def __init__(self, name):
        self.name = name
        self.alias = None

    def set_alias(self, alias):
        self.alias = alias

    def resolve_link(self, model, epath):
        """Resolve self.name as a link in the model and epath context."""
        return self.name.resolve_link(model, epath)

class ColumnsElem (PathElem):
    """A path element with parenthetic name list must be columns."""
    def __init__(self, names, outer_type=None):
        self.names = names
        self.alias = None
        self.outer_type = outer_type

    def set_alias(self, alias):
        self.alias = alias

    def set_outer_type(self, outer_type):
        self.outer_type = outer_type

    def resolve_link(self, model, epath):
        """Resolve (self.names) as a link in the model and epath context."""
        return self.names.resolve_link(model, epath)

    def add_link_rhs(self, names):
        return LinkElem(self.names, names, outer_type=self.outer_type)

class LinkElem (PathElem):
    """A path element with a fully join spec equating two parenthetic lists of columns."""
    def __init__(self, lnames, rnames, outer_type=None):
        self.lnames = lnames
        self.rnames = rnames
        self.alias = None
        self.outer_type = outer_type

    def set_alias(self, alias):
        self.alias = alias

    def resolve_link(self, model, epath):
        """Resolve (self.lnames)=(self.rnames) as a link in the model and epath context."""
        return self.lnames.resolve_link(model, epath, rnames=self.rnames)
    
class FilterElem (PathElem):
    """A path element that applies a filter."""
    is_filter = True

    def __init__(self, pred):
        self.pred = pred

    def __str__(self):
        return str(self.pred)

    def validate(self, epath, enforce_client=True):
        return self.pred.validate(epath, enforce_client=enforce_client)

    def sql_where(self, epath, elem, prefix=''):
        return self.pred.sql_where(epath, elem, prefix=prefix)

    def validate_attribute_update(self, apath):
        return self.pred.validate_attribute_update(apath)

class ContextResetElem (PathElem):
    """A path element that resets entity context via reference to earlier element."""
    is_context = True
    
    def __init__(self, name):
        self.name = name

