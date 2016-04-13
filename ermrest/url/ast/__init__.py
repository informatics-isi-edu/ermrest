
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

import urllib

from .catalog import Catalogs, Catalog
from . import model
from . import data
from .name import Name, NameList

from ... import exception
from ...util import sql_identifier

class SortList (list):
    """Represent a list of Sortkey instances.

    """

    pass

class Sortkey (object):
    """Represent an unqualified name with optional descending flag.

    """
    def __init__(self, keyname, descending=False):
        self.keyname = keyname
        self.descending = descending

class PageList (list):
    """Represent a list of page key values
    """
    pass

class Value (object):
    """Represent a literal value in an ERMREST URL.

    """
    def __init__(self, s):
        self._str = s

    def __str__(self):
        return self._str

    def validate(self, epath, etype):
        """Validate value in typed context.

           TODO: refactor a type object instead of using Column for etype
        """
        pass

    def is_null(self):
        return self._str is None
    
    def sql_literal(self, etype):
        return etype.sql_literal(self._str)

    def validate_attribute_update(self):
        raise exception.BadSyntax('Value %s is not supported in an attribute update path filter.' % self)

class Aggregate (Name):
    """Represent an aggregate function used as an attribute."""

    def __init__(self, aggfunc, name):
        Name.__init__(self, name.nameparts)
        self.aggfunc = aggfunc

    def __str__(self):
        return '%s(%s)' % (self.aggfunc, ':'.join(map(urllib.quote, self.nameparts)))
    
    def __repr__(self):
        return '<ermrest.url.ast.aggregate %s %s>' % (str(self.aggfunc), Name.__str__(self))

