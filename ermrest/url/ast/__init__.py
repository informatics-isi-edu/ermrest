
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
from .name import Name

from ... import exception
from ...util import sql_identifier

def _default_link_cols(cols, left=True, reftable=None):
    """Find default reference link anchored at cols list.

       Returns (keyref, refop).

       Raises exception.ConflictModel if no default can be found.
    """
    constraint_key = frozenset(cols)
    table = cols[0].table # any column will do for this

    links = []

    # look for references ending at leftcol
    if constraint_key in table.uniques:
        refs = set()
        if reftable:
            if reftable in table.uniques[constraint_key].table_references:
                refs.update( table.uniques[constraint_key].table_references[reftable] )
        else:
            for rs in table.uniques[constraint_key].table_references.values():
                refs.update(rs)
        links.extend([ (ref, left and '@=' or '=@') for ref in refs ])
    
    # look for references starting at leftcol
    if constraint_key in table.fkeys:
        refs = set()
        if reftable:
            if reftable in table.fkeys[constraint_key].table_references:
                refs.update( table.fkeys[constraint_key].table_references[reftable] )
        else:
            for rs in table.fkeys[constraint_key].table_references.values():
                refs.update(rs)
        links.extend([ (ref, left and '=@' or '@=') for ref in refs ])
    
    if len(links) == 0:
        raise exception.ConflictModel('No link found involving columns %s' % [ str(c) for c in cols ])
    elif len(links) == 1:
        return links[0]
    else:
        raise exception.ConflictModel('Ambiguous links found involving columns %s' % [ str(c) for c in cols ])


def _default_link_col(col, left=True, reftable=None):
    """Find default reference link anchored at col.

       Returns (keyref, refop).

       Raises exception.ConflictModel if no default can be found.
    """
    return _default_link_cols([col], left, reftable)

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

class NameList (list):
    """Represent a list of Name instances.

    """
    
    def resolve_link(self, model, epath):
        """Resolve self against a specific database model and epath context.

           Returns (keyref, refop, lalias) as resolved key reference
           configuration.
        
           The first name must be resolved as a normal column name.

           All remaining columns must either be relative 'n0' and must
           be in the same table resolved for the first name.

           The identified column set must be involved in one reference
           as either foreign key or primary key.
        
           Raises exception.ConflictModel on failed resolution.
        """
        lalias = None
        left = True
        reftable = None

        c0, base = self[0].resolve_column(model, epath)
        if base in epath.aliases:
            lalias = base
        elif base == epath:
            pass
        else:
            left = False
            reftable = epath.current_entity_table()

        cols = [ c0 ]

        for n in self[1:]:
            c, b = n.resolve_column(model, epath, c0.table)
            if c.table != c0.table or base != b and not lalias:
                raise exception.ConflictModel('Linking columns must belong to the same table.')
            cols.append( c )

        keyref, refop = _default_link_cols(cols, left, reftable)

        return keyref, refop, lalias

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

