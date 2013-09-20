
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

"""ERMREST data path support

The data path is the core ERM-aware mechanism for searching,
navigating, and manipulating data in an ERMREST catalog.

"""
import urllib

class EntityElem (object):
    """Wrapper for instance of entity table in path.

    """
    def __init__(self, epath, alias, table, pos, keyref=None, refop=None, keyref_alias=None):
        self.epath = epath
        self.alias = alias
        self.table = table
        self.pos = pos
        self.keyref = keyref
        self.refop = refop
        self.keyref_alias = keyref_alias
        self.filters = []

    def __str__(self):
        s = str(self.table)

        if self.alias:
            s += ' AS %s' % self.alias

        if self.keyref:

            fkcols = [ urllib.quote(c.name) for c in self.keyref.foreign_key.columns ]
            pkcols = [ urllib.quote(c.name) for c in self.keyref.unique.columns ]

            if self.refop == '=@':
                # left to right reference
                ltable = self.keyref.foreign_key.table
                lcnames, rcnames = fkcols, pkcols
                refop = 'refs'
            else:
                # right to left reference
                ltable = self.keyref.unique.table
                lcnames, rcnames = pkcols, fkcols
                refop = 'refby'

            if self.keyref_alias:
                ltname = self.keyref_alias
            else:
                ltname = '..'

            lcols = ltname + ':' + ','.join(lcnames)
            rcols = '.' + ':' + ','.join(rcnames)

            s += ' ON (%s %s %s)' % (lcols, refop, rcols)

        if self.filters:
            s += ' WHERE ' + ' AND '.join([ str(f) for f in self.filters ])

        return s

    def __repr__(self):
        return '<ermrest.ermpath.EntityElem %s>' % str(self)

    def add_filter(self, filt):
        """Add a filter condition to this path element.
        """
        filt.validate(self.epath)
        self.filters.append(filt)

class EntityPath (object):
    """Hierarchical ERM data access to whole entities, i.e. table rows.

    """
    def __init__(self, model):
        self._model = model
        self._path = None
        self.aliases = {}

    def __str__(self):
        return ' / '.join([ str(e) for e in self._path ])

    def __getitem__(self, k):
        return self._path[ self.aliases[k] ]

    def set_base_entity(self, table, alias=None):
        """Root this entity path in the specified table.

           Optionally set alias for the root.
        """
        assert self._path is None
        self._path = [ EntityElem(self, alias, table, 0) ]
        if alias is not None:
            self.aliases[alias] = 0

    def current_entity_table(self):
        """Get table aka entity type associated with the current path.

           The entity type of the path is the right-most table of the
           path.
        """
        return self._path[-1].table

    def add_filter(self, filt):
        """Add a filter condition to the current path.

           Filters restrict the matched rows of the right-most table.
        """
        return self._path[-1].add_filter(filt)

    def add_link(self, keyref, refop, ralias=None, lalias=None):
        """Extend the path by linking in another table.

           keyref specifies the foreign key and primary keys used
           for linkage.

           refop specifies the direction of linkage, i.e. whether the
           left table references the right table or vice versa.  The
           direction can only be successfully reversed when left and
           right tables are of the same type and direction isn't
           statically restricted. But, refop must match the allowed
           direction even when left and right tables are inequal.

           the ralias optionally defines an alias for the newly added
           right-most table instance.

           the lalias selects a left-hand table instance other than
           the right-most table prior to extension.
        """
        assert self._path
        rpos = len(self._path)

        if refop == '@=':
            rtable = keyref.foreign_key.table
        else:
            # '=@'
            rtable = keyref.unique.table

        self._path.append( EntityElem(self, ralias, rtable, rpos, keyref, refop, lalias) )

        if ralias is not None:
            if ralias in self.aliases:
                raise ValueError('Alias %s bound more than once.' % ralias)
            self.aliases[ralias] = rpos
        

class AttributePath (object):
    """Hierarchical ERM data access to entity attributes, i.e. table cells.

    """
    def __init__(self, epath, attributes):
        self.epath = epath
        self.attributes = attributes

class QueryPath (object):
    """Hierarchical ERM data access to query results, i.e. computed rows.

    """
    def __init__(self, epath, expressions):
        self.epath = epath
        self.expressions = expressions

