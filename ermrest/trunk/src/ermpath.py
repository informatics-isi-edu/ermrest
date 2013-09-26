
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
    
    def get(self, conn, content_type='text/csv', output_file=None):
        """Fetch entities.

           conn: sanepg2 database connection to catalog

           content_type: 
              text names of MIME types control serialization:
                'text/csv' --> CSV table with header row
                'application/json' --> JSON array of row objects

              Python types select native Python result formats
                dict  --> dict of column:value per row
                tuple --> tuple of values per row

                for tuples, values will be ordered according to column
                ordering in the catalog model.

           output_file: 
              None --> thunk result, when invoked generates iterable results
              x --> x.write() the serialized output

           Note: only text content types are supported with
           output_file writing.
        """
        sql = self.sql_get()

        if output_file:
            # efficiently send results to file
            if content_type == 'text/csv':
                sql = "COPY (%s) TO STDOUT CSV DELIMITER ',' HEADER" % sql
            elif content_type == 'application/json':
                sql = """
SELECT 
  CASE WHEN row_number() OVER () = 1 THEN '' ELSE ',' END || (row_to_json(q)::text)
FROM (%s) q
""" % sql
                sql = "COPY (%s) TO STDOUT" % sql
                output_file.write('[')
            else:
                raise NotImplementedError('content_type %s with output_file.write()' % content_type)

            cur = conn.cursor()
            cur.copy_expert(sql, output_file)

            if content_type == 'application/json':
                output_file.write(']\n')

        else:
            # generate rows to caller
            if content_type == 'text/csv':
                # TODO implement and use row_to_csv() stored procedure?
                pass
            elif content_type == 'application/json':
                sql = "SELECT row_to_json(q)::text FROM (%s) q" % sql
            elif content_type in [ dict, tuple ]:
                pass
            else:
                raise NotImplementedError('content_type %s' % content_type)

            cur = conn.execute(sql)
            
            def row_thunk():
                """Allow caller to lazily expand cursor after commit."""
                
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
    
                elif content_type is tuple:
                    for row in cur:
                        yield row
    
                elif content_type is dict:
                    for row in cur:
                        yield row_to_dict(cur, row)
    
                cur.close()

            return row_thunk
        
    def put(self, conn, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, update_existing=True, insert_missing=True):
        """Put or update entities depending on allow_existing, allow_missing modes.

           conn: sanepg2 connection to catalog

           input_data:
              x with x.read() --> data will be read
              iterable --> data will be iterated

           in_content_type:
              text names of MIME types control deserialization:
                'text/csv' --> CSV table
                'application/json' --> JSON array of objects

                for MIME types, iterable input will be concatenated to
                form input byte stream, or read() will be called to
                fetch byte stream until an empty read() result is
                received.
 
              None means input is Python data stream (iter only)
                dicts will be seen as column: value, ... rows
                tuples will be seen as value, ... rows
                other types are erroneous

                for Python data streams, iterable input must yield one
                row respresentation at a time.  read() is not
                supported for Python data streams.

                for tuples, values must be ordered according to column
                ordering in the catalog model.

           content_type and output_file: see documentation for
              identical feature in get() method of this class. The
              result being controlled is a representation of each
              inserted or modified row, including any default values
              which might have been absent from the input.

           update_existing: when input rows match existing keys
              True --> update existing row with input (default)
              None --> skip input row
              False --> raise exception

           insert_missing: when input rows do not match existing keys
              True --> insert input rows (default)
              None --> skip input row
              False --> raise exception

           Special cases:

           NOTE: these cases can be transitive if keys can ever be
           mutated!
           
           Writing entity type with foreign-key reference to parent
           entity-path context.

           A. Zero parent entities are matched: disallow non-NULL
              user-provided values.

           B. Exactly one parent entity is matched: disallow
              user-provided values other than NULL or the matched
              parent key, rewrite NULL to the matched parent.

           C. More than one parent entities are matched: disallow
              user-provided values other than NULL or a matching
              parent key.

           Writing entity type with primary key referenced by
           foreign_key in parent entity-path context that is not a
           simple association.

           A. Zero parent entities are matched: write entity as if
              there were no parent context.

           B. One or more parent entities are matched: after writing
              entity, update parent entities' foreign keys to
              reference written entity.

           Writing entity type with primary key referenced by
           foreign_key in parent entity-path context that is a simple
           association to another entity in grandparent context:

           A. Zero grandparent entities are matched: write entity as
              if there were no parent context.

           B. One or more grandparent entities are matched: after
              writing entity, update parent association table to
              associate ALL matched grandparents with written entity.

        """
        # TODO:
        # 1. load input_data into temporary table in DB
        # 2. check for exception conditions
        #    A. duplicate keys in input
        #    B. insert_missing == False and row missing
        #    C. update_existing == False and row exists
        # 3. perform update (honor whole_row_key setting)
        #    A. insert_missing == True and row missing
        #    B. update_existing == True and row exists
        # 4. update metadata overlay... table/cols modified
        # 5. return modified+inserted rows

        raise NotImplementedError()

    def delete(self, conn, content_type='text/csv', output_file=None):
        """Delete entities.

           conn: sanepg2 connection to catalog

           content_type and output_file: see documentation for
              identical feature in get() method of this class. The
              result being controlled is a representation of each
              deleted row.
        
           Special cases:

           NOTE: these cases can be transitive on delete!
           
           Deleting entity type with primary key referenced by
           foreign-key in any other entity type.

           -- Cascade according to foreign key references, e.g. delete
              referencing rows or set references to NULL as
              appropriate.

        """
        # TODO:
        # 1. delete rows
        # 2. update metadata overlay... table modified
        # 3. ...returning deleted rows

        raise NotImplementedError()

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

       
