
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


class NameList (list):
    """Represent a list of Name instances.

    """
    pass

def _default_link_table2table(left, right):
    """Find default reference link between left and right tables.

       Returns (keyref, refop).

       Raises KeyError if no default can be found.
    """
    if left == right:
        raise KeyError('Ambiguous self-link for table %s' % left)

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
        raise KeyError('No link found between tables %s and %s' % (left, right))
    elif len(links) == 1:
        return links[0]
    else:
        raise KeyError('Ambiguous links found between tables %s and %s' % (left, right))

def _default_link_leftcol(leftcol):
    """Find default reference link anchored at leftcol.

       Returns (keyref, refop).

       Raises KeyError if no default can be found.
    """
    left = leftcol.table
    constraint_key = frozenset([leftcol])

    links = []

    # look for right-to-left references ending at leftcol
    if constraint_key in left.uniques:
        refs = set()
        for rs in left.uniques[constraint_key].table_references.values():
            refs.update(rs)
        links.extend([ (ref, '@=') for ref in refs ])
    
    # look for left-to-right references starting at leftcol
    if constraint_key in left.fkeys:
        refs = set()
        for rs in left.fkeys[constraint_key].table_references.values():
            refs.update(rs)
        links.extend([ (ref, '=@') for ref in refs ])
    
    if len(links) == 0:
        raise KeyError('No link found involving left column %s' % leftcol)
    elif len(links) == 1:
        return links[0]
    else:
        raise KeyError('Ambiguous links found involving left column %s' % leftcol)

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

    def __str__(self):
        return '%s%s' % (
            self.absolute and ':' or '',
            ':'.join(map(urllib.quote, self.nameparts))
            )

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
        
    def resolve_link(self, model, epath):
        """Resolve self against a specific database model and epath context.

           Returns (keyref, refop, lalias) as resolved key reference
           configuration.
        
           An absolute name ':n0:n1' must be:

             1. a table in the model that can be linked to the path by
                implicit reference.

           A relative name 'n0' may be:

             1. a column of the current epath table type, which must
                be a single-column key or foreign key unambiguously
                identifying a specific reference.

             2. an unambiguous table in the model, and also can be
                linked to the path

           A relative name 'n0:n1' may be:

             1. a column of an aliased table in the epath context,
                which must be a single-column key or foreign key
                unambiguously identifying a specific reference.

             2. a table in the model that can be linked to the path by
                implicit reference.

           TODO: add other column-based methods?
        
           Raises KeyError on failed resolution.
        """
        ptable = epath.current_entity_table()

        if self.absolute and len(self.nameparts) == 2:
            table = self.resolve_table(model)
            keyref, refop = _default_link_table2table(ptable, table)
            return keyref, refop, None

        elif not self.absolute:
            if len(self.nameparts) == 1:
                name = self.nameparts[0]
                if name in ptable.columns:
                    keyref, refop = _default_link_leftcol(ptable.columns[name])
                    return keyref, refop, None

                else:
                    table = self.resolve_table(model)
                    keyref, refop = _default_link_table2table(ptable, table)
                    return keyref, refop, None

            elif len(self.nameparts) == 2:
                n0, n1 = self.nameparts
                if n0 in epath.aliases \
                        and n1 in epath[n0].table.columns:
                    keyref, refop = _default_link_leftcol(epath[n0].table.columns[n1])
                    return keyref, refop, n0

                table = model.lookup_table(n0, n1)
                keyref, refop = _default_link_table2table(ptable, table)
                return keyref, refop, None

        raise TypeError('Name %s is not a valid syntax for table-linking.' % self)

    def resolve_table(self, model):
        """Resolve self as table name.
        
           Qualified names ':n0:n1' or 'n0:n1' can only be resolved
           from the model as :schema:table.  Bare names 'n0' can be
           resolved as table if that is unambiguous across all
           schemas in the model.

           Raises KeyError on failed resolution.
        """
        if len(self.nameparts) == 2:
            sname, tname = self.nameparts
            return model.lookup_table(sname, tname)
        elif len(self.nameparts) == 1 and not self.absolute:
            tname = self.nameparts[0]
            return model.lookup_table(None, tname)

        raise TypeError('Name %s is not a valid syntax for a table name.' % self)
            
        
        
