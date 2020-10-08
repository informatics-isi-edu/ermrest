
# 
# Copyright 2013-2020 University of Southern California
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

from .catalog import Service, Catalogs, Catalog
from ...model.name import Name, NameList
from . import history

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

class Aggregate (Name):
    """Represent an aggregate function used as an attribute."""

    def __init__(self, aggfunc, name):
        Name.__init__(self, name.nameparts)
        self.aggfunc = aggfunc

    def __str__(self):
        return '%s(%s)' % (self.aggfunc, ':'.join(map(urllib.parse.quote, self.nameparts)))
    
    def __repr__(self):
        return '<ermrest.url.ast.aggregate %s %s>' % (str(self.aggfunc), Name.__str__(self))

class Binning (Name):
    """Represent a binning function used as an attribute."""

    def __init__(self, name, nbins=25, minv=None, maxv=None):
        Name.__init__(self, name.nameparts)
        if nbins is not None:
            try:
                self.nbins = nbins
            except ValueError:
                raise exception.BadSyntax('Value "%s" is not a valid decimal integer number of bins.' % self.nbins)
        self.minv = minv
        self.maxv = maxv

    def __str__(self):
        return 'bin(%s)' % (';'.join([Name.__str__(self), str(self.nbins), str(self.minv), str(self.maxv)]))
