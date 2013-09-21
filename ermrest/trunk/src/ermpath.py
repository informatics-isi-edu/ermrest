
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
from model import sql_ident

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

    def _link_parts(self):
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

        return ltable, lcnames, rcnames, refop

    def __str__(self):
        s = str(self.table)

        if self.alias:
            s += ' AS %s' % self.alias

        if self.keyref:
            ltable, lcnames, rcnames, refop = self._link_parts()
        
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

    def sql_join_condition(self):
        """Generate SQL condition for joining this element to the epath.

        """
        assert self.keyref

        ltable, lcnames, rcnames, refop = self._link_parts()

        if self.keyref_alias:
            ltnum = self.epath.aliases[self.keyref_alias]
        else:
            ltnum = self.pos - 1
        
        return ' AND '.join([
                't%d.%s = t%d.%s' % (
                    ltnum, 
                    sql_ident(lcnames[i]),
                    self.pos, 
                    sql_ident(rcnames[i])
                    )
                for i in range(0, len(lcnames))
                ])

    def sql_wheres(self):
        """Generate SQL row conditions for filtering this element in the epath.
           
        """
        return [ f.sql_where(self.epath, self) for f in self.filters ]

    def sql_table_elem(self):
        """Generate SQL table element representing this entity as part of the epath JOIN.

        """
        if self.pos == 0:
            return '%s AS t0' % self.table.sql_name()

        else:
            return '%s AS t%d ON (%s)' % (
                self.table.sql_name(),
                self.pos,
                self.sql_join_condition()
                )

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


    def sql_get(self):
        """Generate SQL query to get the entities described by this epath.

           The query will be of the form:

              SELECT 
                DISTINCT ON (...)
                tK.* 
              FROM "x" AS t0 
                ... 
              JOIN "z" AS tK ON (...)
              WHERE ...
           
           encoding path references and filter conditions.

        """
        pkeys = self._path[-1].table.uniques.keys()
        pkeys.sort(key=lambda k: len(k))
        shortest_pkey = self._path[-1].table.uniques[pkeys[0]]
        distinct_on_cols = [ 
            't%d.%s' % (len(self._path) - 1, sql_ident(c.name))
             for c in shortest_pkey.columns
            ]

        tables = [ elem.sql_table_elem() for elem in self._path ]

        wheres = []
        for elem in self._path:
            wheres.extend( elem.sql_wheres() )

        return """
SELECT 
  DISTINCT ON (%(distinct_on)s)
  t%(len)d.*
FROM %(tables)s
%(where)s
""" % dict(distinct_on = ', '.join(distinct_on_cols),
           len         = len(self._path) - 1,
           tables      = ' JOIN '.join(tables),
           where       = wheres and ('WHERE ' + ' AND '.join(wheres)) or ''
           )
    
    def get_to_file(self, conn, fp, content_type='text/csv'):
        """Write entities to file.

           fp: the file pointer with a write() method

           content_type:
              'text/csv'         --> CSV row stream
              'application/json' --> JSON row object stream

           TODO: fix JSON output to have array syntax around row objects
        """
        sql = self.sql_get()

        if content_type == 'text/csv':
            sql = "COPY (%s) TO STDOUT CSV DELIMITER ',' HEADER" % sql
        elif content_type == 'application/json':
            sql = "SELECT row_to_json(q) FROM (%s) q" % sql
            sql = "COPY (%s) TO STDOUT" % sql
        else:
            raise NotImplementedError()
        
        cur = conn.cursor()
        cur.copy_expert(sql, fp)

    def get_iter(self, conn, content_type='text/csv', row_type=tuple):
        """Yield entities.

           content_type: 
              'text/csv'         --> CSV table with header row
              'application/json' --> JSON array of row objects
              None --> raw Python rows (see row_type)

           row_type:  (when content_type is None)
              tuple --> tuple of values per row
              dict  --> dict of column name: value per row

        """
        sql = self.sql_get()

        if content_type == 'text/csv':
            # TODO implement and use row_to_csv() stored procedure?
            pass
        elif content_type == 'application/json':
            sql = "SELECT row_to_json(q)::text FROM (%s) q" % sql
        elif content_type is None:
            pass
        else:
            raise NotImplementedError()

        cur = conn.execute(sql)
        
        if content_type == 'text/csv':
            hdr = True
            for row in cur:
                if hdr:
                    # need to defer accessing cur.description until after fetching 1st row
                    yield row_to_csv([ col[0] for col in cur.description ]) + '\n'
                    hdr = False
                yield row_to_csv(row) + '\n'

        elif content_type == 'application/json':
            pre = '['
            for row in cur:
                yield pre + row[0] + '\n'
                pre = ','
            yield ']\n'

        elif content_type is None:
            if row_type is tuple:
                for row in cur:
                    yield row

            elif row_type is dict:
                for row in cur:
                    yield row_to_dict(cur, row)

            else:
                raise NotImplementedError('row_type %s' % str(row_type))
            
        cur.close()

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

def row_to_dict(cur, row):
    return dict([
            (cur.description[i][0], row[i])
            for i in range(0, len(row))
            ])

def val_to_csv(v):
    if type(v) in [ int, float, long ]:
        return '%s' % v

    else:
        v = str(v)
        if v.find(',') > 0 or v.find('"') > 0:
            return '"%s"' % (v.replace('"', '""'))
        else:
            return v

def row_to_csv(row):
    return ','.join([ val_to_csv(v) for v in row ])

       
