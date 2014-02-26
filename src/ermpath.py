
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
import psycopg2
import urllib
import csv

from model import sql_ident, Type
from ermrest.exception import *

def make_row_thunk(conn, cur, content_type):
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

        elif content_type in [ 'application/json', 'application/x-json-stream' ]:
            for row in cur:
                yield row[0] + '\n'

        elif content_type is tuple:
            for row in cur:
                yield row

        elif content_type is dict:
            for row in cur:
                yield row_to_dict(cur, row)

        cur.close()
        conn.commit()
        
    return row_thunk


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
        """Add a filtersql_name condition to this path element.
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
    
    def put(self, conn, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, allow_existing=True, allow_missing=True):
        """Put or update entities depending on allow_existing, allow_missing modes.

           conn: sanepg2 connection to catalog

           input_data:
              x with x.read() --> data will be read
              iterable --> data will be iterated

           in_content_type:
              text names of MIME types control deserialization:
                'text/csv' --> CSV table
                'application/json' --> JSON array of objects
                'application/x-json-stream' --> stream of JSON objects

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

           allow_existing: when input rows match existing keys
              True --> update existing row with input (default)
              None --> skip input row
              False --> raise exception

           allow_missing: when input rows do not match existing keys
              True --> insert input rows (default)
              None --> skip input row
              False --> raise exception

        """
        if len(self.filters) > 0:
            raise BadSyntax('Entity path filters not allowed during PUT.')
        
        # create temporary table
        cur = conn.cursor()
        cur.execute(
            "CREATE TEMPORARY TABLE input_data (%s)" % (
                ','.join([ c.ddl() for c in self.table.columns_in_order() ])
                )
            )
        if in_content_type in [ 'application/x-json-stream' ]:
            cur.execute( "CREATE TEMPORARY TABLE input_json (j json)" )
        cur.close()
        
        # copy input data to temp table
        cur = conn.cursor()
        if in_content_type == 'text/csv':
            hdr = csv.reader([ input_data.readline() ]).next()

            csvcols = []
            for cn in hdr:
                if cn not in self.table.columns:
                    raise BadData('CSV column %s not recognized.' % cn)
                else:
                    csvcols.append(cn)

            numcols = len(self.table.columns.keys())
            if len(set(csvcols)) != numcols or len(csvcols) != numcols:
                raise BadData('CSV input must have all entity columns exactly once: %s' 
                              % ', '.join([ c.sql_name() for c in self.table.columns_in_order() ]))

            try:
                cur.copy_expert(
                """
COPY input_data (%s) 
FROM STDIN WITH (
    FORMAT csv, 
    HEADER false, 
    DELIMITER ',', 
    QUOTE '"'
)""" % (
                        ','.join(csvcols)
                        ),
                input_data
                )
            except psycopg2.DataError, e:
                raise BadData('Bad CSV input. ' + e.pgerror)

        elif in_content_type == 'application/json':
            buf = input_data.read()
            try:
                cur.execute( 
                """
INSERT INTO input_data (%(cols)s)
SELECT %(cols)s 
FROM (
  SELECT (rs.r).*
  FROM (
    SELECT json_populate_recordset( NULL::input_data, %(input)s::json ) AS r
  ) rs
) s
""" % dict( 
                        cols = ','.join([ c.sql_name() for c in self.table.columns_in_order() ]),
                        input = Type('text').sql_literal(buf)
                        )
                )
            except psycopg2.DataError, e:
                raise BadData('Bad JSON array input. ' + e.pgerror)

        elif in_content_type == 'application/x-json-stream':
            try:
                cur.copy_expert( "COPY input_json (j) FROM STDIN", input_data )

                cur.execute(
                """
INSERT INTO input_data (%(cols)s)
SELECT %(cols)s
FROM (
  SELECT (rs.r).*
  FROM (
    SELECT json_populate_record( NULL::input_data, i.j ) AS r
    FROM input_json i
  ) rs
) s
""" % dict(
                        cols = ','.join([ c.sql_name() for c in self.table.columns_in_order() ])
                        )
                )
            except psycopg2.DataError, e:
                raise BadData('Bad JSON stream input. ' + e.pgerror)

        else:
            raise UnsupportedMediaType('%s input not supported' % in_content_type)

        cur.close()

        # TODO: validate input_data
        #  -- check for duplicate keys
        #  -- check for missing keys and allow_missing == false
        #  -- check for existing keys and allow_existing == false
        
        # find the "meta-key" for this table
        #  -- the union of all columns of all keys
        mkcols = set()
        for key in self.table.uniques:
            for col in key:
                mkcols.add(col)
                

        allcols = set(self.table.columns_in_order())
        nmkcols = allcols - mkcols
        mkcols = [ c.sql_name() for c in mkcols ]
        nmkcols = [ c.sql_name() for c in nmkcols ]
        
        correlating_sql = """
SELECT count(*) AS count
FROM input_data AS i
LEFT OUTER JOIN %(table)s AS t USING (%(mkcols)s)
""" % dict(table = self.table.sql_name(), mkcols = ','.join(mkcols))
        
        update_sql = """
UPDATE %(table)s AS t SET %(assigns)s
FROM input_data AS i
WHERE %(keymatches)s
RETURNING t.*
""" % dict(
            table = self.table.sql_name(),
            cols = ','.join([ "i.%s" % c.sql_name() for c in self.table.columns_in_order() ]),
            assigns = ','.join([ "%s = i.%s " % (c, c) for c in nmkcols ]),
            keymatches = ' AND '.join([ "t.%s = i.%s " % (c, c) for c in mkcols ])
            )
        
        insert_sql = """
INSERT INTO %(table)s (%(cols)s)
SELECT %(icols)s
FROM input_data AS i
LEFT OUTER JOIN %(table)s AS t USING (%(mkcols)s)
WHERE t.%(mkcol0)s IS NULL
RETURNING *
""" % dict(
            table = self.table.sql_name(),
            cols = ','.join([ c.sql_name() for c in self.table.columns_in_order() ]),
            icols = ','.join([ "i.%s" % c.sql_name() for c in self.table.columns_in_order() ]),
            mkcols = ','.join(mkcols),
            mkcol0 = mkcols[0]
        )
        
        updated_sql = "SELECT * FROM updated_rows"
        inserted_sql = "SELECT * FROM inserted_rows"
        upsert_sql = "WITH %s %s"
        
        # generate rows to caller
        if content_type == 'text/csv':
            # TODO implement and use row_to_csv() stored procedure?
            pass
        elif content_type == 'application/json':
            upsert_sql = "WITH %s SELECT array_to_json(array_agg(row_to_json(q)), True)::text FROM (%s) q"
        elif content_type == 'application/x-json-stream':
            upsert_sql = "WITH %s SELECT row_to_json(q)::text FROM (%s) q"
        elif content_type in [ dict, tuple ]:
            pass
        else:
            raise NotImplementedError('content_type %s' % content_type)
        
        upsert_ctes = []
        upsert_queries = []
        
        if allow_existing:
            upsert_ctes.append("updated_rows AS (%s)" % update_sql)
            upsert_queries.append(updated_sql)

        if allow_missing:
            upsert_ctes.append("inserted_rows AS (%s)" % insert_sql)
            upsert_queries.append(inserted_sql)
    
        upsert_sql = upsert_sql % (
            ',\n'.join(upsert_ctes),
            '\nUNION ALL\n'.join(upsert_queries)
            )

        if allow_existing is None and allow_missing is None:
            return lambda : []

        else:
            cur = conn.cursor()
            
            if allow_existing is False:
                cur.execute(correlating_sql + "\nWHERE t.%s IS NOT NULL" % mkcols[0])
                if cur.fetchone()[0] > 0:
                    raise ConflictData('input row exists while allow_existing is False')
            
            if allow_missing is False:
                cur.execute(correlating_sql + "\nWHERE t.%s IS NULL" % mkcols[0])
                if cur.fetchone()[0] > 0:
                    raise ConflictData('input row does not exist while allow_missing is False')
            
            cur = conn.cursor()
            cur.execute(upsert_sql)
            return make_row_thunk(conn, cur, content_type)

class AnyPath (object):
    """Hierarchical ERM access to resources, a generic parent-class for concrete resources.

    """
    def sql_get(self):
        """Generate SQL query to get the resources described by this path.

           The query will be of the form:

              SELECT 
                tK.* 
              FROM "x" AS t0 
                ... 
              JOIN "z" AS tK ON (...)
              WHERE ...
           
           encoding path references and filter conditions.

        """
        raise NotImplementedError('sql_get on abstract class ermpath.AnyPath')

    def get(self, conn, content_type='text/csv', output_file=None):
        """Fetch resources.

           conn: sanepg2 database connection to catalog

           content_type: 
              text names of MIME types control serialization:
                'text/csv' --> CSV table with header row
                'application/json' --> JSON array of row objects
                'application/x-json-stream' --> stream of JSON objects

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
        # TODO: refactor this common code between 

        sql = self.sql_get()

        if output_file:
            # efficiently send results to file
            if content_type == 'text/csv':
                sql = "COPY (%s) TO STDOUT CSV DELIMITER ',' HEADER" % sql
            elif content_type == 'application/json':
                sql = "COPY (SELECT array_to_json(array_agg(row_to_json(q)), True)::text FROM (%s) q) TO STDOUT" % sql
            elif content_type == 'application/x-json-stream':
                sql = "COPY (SELECT row_to_json(q)::text FROM (%s) q) TO STDOUT" % sql
            else:
                raise NotImplementedError('content_type %s with output_file.write()' % content_type)

            cur = conn.cursor()
            cur.copy_expert(sql, output_file)
            cur.close()

        else:
            # generate rows to caller
            if content_type == 'text/csv':
                # TODO implement and use row_to_csv() stored procedure?
                pass
            elif content_type == 'application/json':
                sql = "SELECT array_to_json(COALESCE(array_agg(row_to_json(q)), ARRAY[]::json[]), True)::text FROM (%s) q" % sql
            elif content_type == 'application/x-json-stream':
                sql = "SELECT row_to_json(q)::text FROM (%s) q" % sql
            elif content_type in [ dict, tuple ]:
                pass
            else:
                raise NotImplementedError('content_type %s' % content_type)

            cur = conn.execute(sql)
            
            return make_row_thunk(conn, cur, content_type)
        
class EntityPath (AnyPath):
    """Hierarchical ERM data access to whole entities, i.e. table rows.

    """
    def __init__(self, model):
        AnyPath.__init__(self)
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
                raise BadData('Alias %s bound more than once.' % ralias)
            self.aliases[ralias] = rpos


    def sql_get(self, selects=None):
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
        selects = selects or ("t%d.*" % (len(self._path) - 1))

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
  %(selects)s
FROM %(tables)s
%(where)s
""" % dict(distinct_on = ', '.join(distinct_on_cols),
           selects     = selects,
           tables      = ' JOIN '.join(tables),
           where       = wheres and ('WHERE ' + ' AND '.join(wheres)) or ''
           )
    
    def sql_delete(self):
        """Generate SQL statement to delete the entities described by this epath.
        """
        table = self._path[-1].table
        # find the "meta-key" for this table
        #  -- the union of all columns of all keys
        mkcols = set()
        for key in table.uniques:
            for col in key:
                mkcols.add(col)
        mkcols = [ c.sql_name() for c in mkcols ]
        
        return """
DELETE FROM %(table)s AS t
USING (%(getqry)s) AS i
WHERE %(keymatches)s
""" % dict(
            table = table.sql_name(),
            getqry = self.sql_get(),
            keymatches = ' AND '.join([ "t.%s = i.%s " % (c, c) for c in mkcols ])
            )
    
    def delete(self, conn):
        """Delete entities.

           conn: sanepg2 database connection to catalog
        """
        cur = conn.cursor()
        cur.execute("SELECT count(*) AS count FROM (%s) s" % self.sql_get())
        if cur.fetchone()[0] == 0:
            raise NotFound('rows matching request path')
        cur.execute(self.sql_delete())
        cur.close()
        
    def put(self, conn, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, allow_existing=True, allow_missing=True):
        """Put or update entities depending on allow_existing, allow_missing modes.

           conn: sanepg2 connection to catalog

           input_data:
              x with x.read() --> data will be read
              iterable --> data will be iterated

           in_content_type:
              text names of MIME types control deserialization:
                'text/csv' --> CSV table
                'application/json' --> JSON array of objects
                'application/x-json-stream' --> stream of JSON objects

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

           allow_existing: when input rows match existing keys
              True --> update existing row with input (default)
              None --> skip input row
              False --> raise exception

           allow_missing: when input rows do not match existing keys
              True --> insert input rows (default)
              None --> skip input row
              False --> raise exception

        """
        
        if len(self._path) != 1:
            raise BadData("unsupported path length for put")
        
        return self._path[0].put(conn, input_data, in_content_type, content_type, output_file, allow_existing, allow_missing)
        

class AttributePath (AnyPath):
    """Hierarchical ERM data access to entity attributes, i.e. table cells.

    """
    def __init__(self, epath, attributes):
        AnyPath.__init__(self)
        self.epath = epath
        self.attributes = attributes

    def sql_get(self):
        """Generate SQL query to get the resources described by this epath.

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
        # validate attributes for GET case
        selects = []
        
        for attribute in self.attributes:
            col, base = attribute.resolve_column(self.epath._model, self.epath)
            if base == self.epath:
                # column in final entity path element
                selects.append( "t%d.%s" % (len(self.epath._path) - 1, sql_ident(col.name)) )
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                selects.append( "t%d.%s" % (self.epath[base].pos, sql_ident(col.name)) )
            else:
                raise ConflictModel('Invalid attribute name "%s".' % attribute)

        selects = ', '.join(selects)

        return self.epath.sql_get(selects=selects)

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

       
