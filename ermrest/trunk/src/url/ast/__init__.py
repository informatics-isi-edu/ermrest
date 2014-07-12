
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

from ermrest.util import sql_identifier
from ermrest import exception

import urllib

def _default_link_table2table(left, right):
    """Find default reference link between left and right tables.

       Returns (keyref, refop).

       Raises exception.ConflictModel if no default can be found.
    """
    if left == right:
        raise exception.ConflictModel('Ambiguous self-link for table %s' % left)

    links = []

    # look for right-to-left references
    for pk in left.uniques.values():
        if right in pk.table_references:
            links.extend([
                    (ref, '@=')
                    for ref in pk.table_references[right]
                    ])

    # look for left-to-right references
    for fk in left.fkeys.values():
        if right in fk.table_references:
            links.extend([
                    (ref, '=@')
                    for ref in fk.table_references[right]
                    ])

    if len(links) == 0:
        raise exception.ConflictModel('No link found between tables %s and %s' % (left, right))
    elif len(links) == 1:
        return links[0]
    else:
        raise exception.ConflictModel('Ambiguous links found between tables %s and %s' % (left, right))

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
            refs.update( table.uniques[constraint_key].table_references[reftable] )
        else:
            for rs in table.uniques[constraint_key].table_references.values():
                refs.update(rs)
        links.extend([ (ref, left and '@=' or '=@') for ref in refs ])
    
    # look for references starting at leftcol
    if constraint_key in table.fkeys:
        refs = set()
        if reftable:
            refs.update( table.fkeys[constraint_key].table_references[reftable] )
        else:
            for rs in table.fkeys[constraint_key].table_references.values():
                refs.update(rs)
        links.extend([ (ref, left and '=@' or '@=') for ref in refs ])
    
    if len(links) == 0:
        raise exception.ConflictModel('No link found involving columns %s' % cols)
    elif len(links) == 1:
        return links[0]
    else:
        raise exception.ConflictModel('Ambiguous links found involving columns %s' % cols)


def _default_link_col(col, left=True, reftable=None):
    """Find default reference link anchored at col.

       Returns (keyref, refop).

       Raises exception.ConflictModel if no default can be found.
    """
    return _default_link_cols([col], left, reftable)


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

class Name (object):
    """Represent a qualified or unqualified name in an ERMREST URL.

    """
    def __init__(self):
        """Initialize a zero-element name container.
        """
        self.nameparts = []

    def __str__(self):
        return ':'.join(map(urllib.quote, self.nameparts))
    
    def __repr__(self):
        return '<ermrest.url.ast.Name %s>' % str(self)

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
        
    def resolve_column(self, model, epath, table=None):
        """Resolve self against a specific database model and epath context.

           Returns (column, base) where base is one of:

            -- a left table alias string if column is relative to alias
            -- epath if column is relative to epath or table arg
            -- None if column is relative to model
        
           The name must be resolved in this preferred order:

             1. a relative 'n0' must be a column in the current epath
                table type or the provided table arg if not None

             2. a relative '*' may be a freetext virtual column
                on the current epath table

             3. a relative 'n0:n1' may be a column in alias n0 of
                current epath

             4. a relative 'n0:n1' may be a column in a table in the
                model

             5. any 'n0:n1:n2' must be a column in the model

           Raises exception.ConflictModel on failed resolution.
        """
        ptable = epath.current_entity_table()

        if table is None:
            table = ptable
        
        if len(self.nameparts) == 3:
            n0, n1, n2 = self.nameparts
            return (model.lookup_table(n0, n1).columns[n2], None)
        
        else:
            if len(self.nameparts) == 1:
                if self.nameparts[0] in table.columns:
                    return (table.columns[self.nameparts[0]], epath)
                elif self.nameparts[0] == '*':
                    return (ptable.freetext_column(), epath)
                else:
                    raise exception.ConflictModel('Column %s does not exist in table %s.' % (self.nameparts[0], str(table)))

            elif len(self.nameparts) == 2:
                n0, n1 = self.nameparts
                if n0 in epath.aliases:
                    if n1 in epath[n0].table.columns:
                        return (epath[n0].table.columns[n1], n0)
                    else:
                        raise exception.ConflictModel('Column %s does not exist in table %s (alias %s).' % (n1, epath[n0].table, n0))

                return (model.lookup_table(None, n0).columns[n1], None)

        raise exception.BadSyntax('Name %s is not a valid syntax for columns.' % self)

    def resolve_link(self, model, epath):
        """Resolve self against a specific database model and epath context.

           Returns (keyref, refop, lalias) as resolved key reference
           configuration.
        
           A name 'n0:n1:n2' must be:

             1. a column in the model to link its containing entity to
                the path by involved reference

           A name 'n0' may be:

             1. a column of the current epath table type involved in
                exactly one reference.

             2. an unambiguous table in the model, and also can be
                linked to the path

           A name 'n0:n1' may be:

             1. a column of an aliased table in the epath context,
                involved in exactly one reference.

             2. a table in the model that can be linked to the path by
                implicit reference.

             3. a column in the model involved in exactly one
                reference back to the current epath table type.

           TODO: add other column-based methods?
           TODO: review resolution policy for sanity?
        
           Raises exception.ConflictModel on failed resolution.
        """
        ptable = epath.current_entity_table()
        
        if len(self.nameparts) == 3:
            n0, n1, n2 = self.nameparts
            table = model.lookup_table(n0, n1)
            keyref, refop = _default_link_col(table.columns[n2], left=False, reftable=ptable)
            return keyref, refop, None
        
        elif len(self.nameparts) == 1:
            name = self.nameparts[0]
            if name in ptable.columns:
                keyref, refop = _default_link_col(ptable.columns[name])
                return keyref, refop, None

            else:
                table = self.resolve_table(model)
                keyref, refop = _default_link_table2table(ptable, table)
                return keyref, refop, None

        elif len(self.nameparts) == 2:
            n0, n1 = self.nameparts
            if n0 in epath.aliases \
                    and n1 in epath[n0].table.columns:
                keyref, refop = _default_link_col(epath[n0].table.columns[n1])
                return keyref, refop, n0

            try:
                table = model.lookup_table(n0, n1)
            except exception.ConflictModel:
                table = None

            if table:
                keyref, refop = _default_link_table2table(ptable, table)
                return keyref, refop, None

            table = model.lookup_table(None, n0)
            keyref, refop = _default_link_col(table.columns[n1], left=False, reftable=ptable)
            return keyref, refop, None
            
        raise exception.BadSyntax('Name %s is not a valid syntax for table-linking.' % self)

    def resolve_table(self, model):
        """Resolve self as table name.
        
           Qualified names 'n0:n1' can only be resolved from the model
           as schema:table.  Bare names 'n0' can be resolved as table
           if that is unambiguous across all schemas in the model.

           Raises exception.ConflictModel on failed resolution.
        """
        if len(self.nameparts) == 2:
            sname, tname = self.nameparts
            return model.lookup_table(sname, tname)
        elif len(self.nameparts) == 1:
            tname = self.nameparts[0]
            return model.lookup_table(None, tname)

        raise exception.BadSyntax('Name %s is not a valid syntax for a table name.' % self)
            
    def validate(self, epath):
        """Validate name in epath context, raising exception on problems.

           Name must be a column of path's current entity type.

           TODO: generalize to ancestor references later.
        """
        table = epath.current_entity_table()
        col, base = self.resolve_column(epath._model, epath)
        if base != epath:
            raise NotImplementedError('Name ancestor column validation')

        return col, epath._path[-1]

    def sql_column(self, epath, elem):
        """Generate SQL column reference for name in epath elem context.

           TODO: generalize to ancestor references later.
        """
        return 't%d.%s' % (
            elem.pos,
            sql_identifier(self.nameparts[-1])
            )

    def sql_literal(self, etype):
        if len(self.nameparts) == 1:
            return Value(self.nameparts[0]).sql_literal(etype)
        else:
            raise exception.BadSyntax('Names such as "%s" not supported in filter expressions.' % self)
        
    def validate_attribute_update(self):
        """Return icolname for valid input column reference.
           
        """
        if len(self.nameparts) == 1:
            return self.nameparts[0]
        else:
            raise exception.BadSyntax('Name "%s" is not a valid input column reference.' % self)

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

