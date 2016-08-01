
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

"""ERMREST data path support

The data path is the core ERM-aware mechanism for searching,
navigating, and manipulating data in an ERMREST catalog.

"""
import psycopg2
import urllib
import csv
import web

from ...util import sql_identifier, sql_literal
from ... import exception
from ...model.key import MultiKeyReference, ExplicitJoinReference

def _exact_link_cols(lcols, rcols):
    if len(lcols) != len(rcols):
        raise exception.BadSyntax('Left and right name lists in (left)=(right) link notation must be equal length.')

    return (ExplicitJoinReference(lcols, rcols), '=@')

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
        return (MultiKeyReference(links), '=@')

class Name (object):
    """Represent a qualified or unqualified name in an ERMREST URL.

    """
    def __init__(self, nameparts=None):
        """Initialize a zero-element name container.
        """
        self.nameparts = nameparts and list(nameparts) or []
        self.alias = None

    def set_alias(self, alias):
        self.alias = alias
        return self

    def __unicode__(self):
        return ':'.join(self.nameparts)

    def __str__(self):
        return (unicode(self)).encode('utf8')
    
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

             4. a relative 'n0:*' may be a freetext virtual column
                in alias n0 of current epath

             5. a relative 'n0:n1' may be a column in a table in the
                model

             6. any 'n0:n1:n2' must be a column in the model

           Raises exception.ConflictModel on failed resolution.
        """
        ptable = epath.current_entity_table()

        if table is None:
            table = ptable
        
        if len(self.nameparts) == 3:
            n0, n1, n2 = self.nameparts
            return (model.schemas[n0].tables[n1].columns[n2],None)
        
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
                    elif self.nameparts[1] == '*':
                        return (epath[n0].table.freetext_column(), n0)
                    else:
                        raise exception.ConflictModel('Column %s does not exist in table %s (alias %s).' % (n1, epath[n0].table, n0))

                table = model.lookup_table(n0)
                return (table.columns[n1], None)

        raise exception.BadSyntax('Name %s is not a valid syntax for columns.' % self)

    def resolve_link(self, model, epath):
        """Resolve self against a specific database model and epath context.

           Returns (keyref, refop, lalias) as resolved key reference
           configuration.
        
           A name 'n0' must be an unambiguous table in the model

           A name 'n0:n1' must be a table in the model

           The named table must have an unambiguous implicit reference
           to the epath context.

           Raises exception.ConflictModel on failed resolution.
        """
        ptable = epath.current_entity_table()
        
        if len(self.nameparts) == 1:
            name = self.nameparts[0]
            table = model.lookup_table(name)
            keyref, refop = _default_link_table2table(ptable, table)
            return keyref, refop, None

        elif len(self.nameparts) == 2:
            n0, n1 = self.nameparts

            table = model.schemas[n0].tables[n1]
            keyref, refop = _default_link_table2table(ptable, table)
            return keyref, refop, None

        raise exception.BadSyntax('Name %s is not a valid syntax for a table name.' % self)

    def validate(self, epath):
        """Validate name in epath context, raising exception on problems.

           Name must be a column of path's current entity type 
           or alias-qualified column of ancestor path entity type.
        """
        table = epath.current_entity_table()
        col, base = self.resolve_column(epath._model, epath)
        if base == epath:
            return col, epath._path[epath.current_entity_position()]
        elif base in epath.aliases:
            return col, epath._path[epath.aliases[base]]

        raise exception.ConflictModel('Referenced column %s not bound in entity path.' % (col.table))

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

class NameList (list):
    """Represent a list of Name instances.

    """
    
    def resolve_link_complete(self, model, epath, rnames):
        """Resolve self (self)=(rnames) against a specific database model and epath context.

           Returns (keyref, refop, lalias) as resolved key reference
           configuration.
        
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
            raise exception.ConflictModel('Left names in (left)=(right) link notation must resolve to columns in entity path.')

        lcols = [ c0 ]

        for n in self[1:]:
            c, b = n.resolve_column(model, epath, c0.table)
            if c.table != c0.table or base != b and not lalias:
                raise exception.ConflictModel('Linking columns must belong to the same table.')
            lcols.append( c )

        c0, base = rnames[0].resolve_column(model, epath)
        if base in epath.aliases or base == epath:
            raise exception.ConflictModel('Right names in (left)=(right) link notation must not resolve to new table instance.')

        rcols = [ c0 ]

        for n in rnames[1:]:
            c, b = n.resolve_column(model, epath, c0.table)
            if c.table != c0.table or base != b and not lalias:
                raise exception.ConflictModel('Linking columns must belong to the same table.')
            rcols.append( c )
            
        keyref, refop = _exact_link_cols(lcols, rcols)

        return keyref, refop, lalias

    def resolve_link(self, model, epath, rnames=None):
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
        if rnames is not None:
            return self.resolve_link_complete(model, epath, rnames)
        
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

