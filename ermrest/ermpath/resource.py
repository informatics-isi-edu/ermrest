# 
# Copyright 2013-2015 University of Southern California
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
import json

from psycopg2._json import JSON_OID, JSONB_OID

from ..exception import *
from ..util import sql_identifier, sql_literal, random_name
from ..model import Type

def make_row_thunk(conn, cur, content_type, drop_tables=[], ):
    def row_thunk():
        """Allow caller to lazily expand cursor after commit.

           If conn is not None, call conn.commit() after fetching
           results to avoid leaving it idle in transaction due to the
           cursor fetch commands.

        """
        
        if content_type == 'text/csv':
            hdr = True
            for row in cur:
                if hdr:
                    # need to defer accessing cur.description until after fetching 1st row
                    yield row_to_csv([ col.name for col in cur.description ]) + '\n'
                    hdr = False
                yield row_to_csv(row, cur.description) + '\n'

        elif content_type in [ 'application/json', 'application/x-json-stream' ]:
            for row in cur:
                yield row[0] + '\n'

        elif content_type is tuple:
            for row in cur:
                yield row

        elif content_type is dict:
            for row in cur:
                yield row_to_dict(cur, row)

        for table in drop_tables:
            cur.execute("DROP TABLE %s" % sql_identifier(table))

        #if conn is not None:
        #    conn.commit()
        
    return row_thunk

def notify_data_change(cur, table):
    """Update data version information after possible change to table.

       Conservatively updates version for any dependent tables too.
    """
    tables = set()

    def expand_table(t1):
        if t1 in tables:
            # don't re-expand tables in event of a cyclic foreign key pattern (weird but possible in SQL)
            return
        tables.add(t1)
        for unique in t1.uniques.values():
            for ftable in unique.table_references:
                expand_table(ftable)

    expand_table(table)

    for table in tables:
        cur.execute('SELECT _ermrest.data_change_event(%s, %s)' % (sql_literal(table.schema.name), sql_literal(table.name)))

def page_filter_sql(keynames, descendings, types, boundary, is_before):
    """Return SQL WHERE clause to filter by page boundary.

       Keycols, descendings, types, boundary are arrays of length N
       characterizing N-length page key.

       keynames: the names of the SQL data columns used for sorting
         and paging in result set

       descendings: True if column is sorted in descending order,
         False if sorted in ascending order

       types: the type object for columns to use when serializing key
         values.

       boundary: value or None for each page key component

       is_before: True for '@before(boundary)', False for
         '@after(boundary)'.

    """
    assert len(keynames) == len(descendings)
    assert len(keynames) == len(boundary)
    
    def helper(keynames, descendings, types, boundary):
        if descendings[0]:
            ops = {True: '>', False: '<'}
        else:
            ops = {True: '<', False: '>'}

        # only handles non-null to non-null sub-case!
        term = '%s %s %s' % (
            sql_identifier(keynames[0]),
            ops[is_before],
            boundary[0].sql_literal(types[0]) if not boundary[0].is_null() else 'NULL'
        )

        if is_before:
            if boundary[0].is_null():
                # all non-null come before this boundary
                term += ' OR %s IS NOT NULL' % sql_identifier(keynames[0])
        else:
            if not boundary[0].is_null():
                # all null come after this boundary
                term += ' OR %s IS NULL' % sql_identifier(keynames[0])
        
        if len(keynames) == 1:
            return term
        else:
            # if row field matches boundary, check secondary sort order
            return '(%s) OR (%s IS NOT DISTINCT FROM %s AND (%s))' % (
                term,
                sql_identifier(keynames[0]),
                boundary[0].sql_literal(types[0]) if not boundary[0].is_null() else 'NULL',
                helper(keynames[1:], descendings[1:], types[1:], boundary[1:])
            )

    result = helper(keynames, descendings, types, boundary)
    return result


def sort_components(sortvec, is_before):
    """Return (sortvec, sort1, sort2) SQL clauses.

       Results:
         (sortvec, None, None) means no sort
         (sortvec, sort1, None) means order by sort1 clause
         (sortvec, sort1, sort2) means order by sort1 and limit, then order by sort2

       The latter happens if is_before is True.
    """
    norm_parts = []
    revs_parts = []
    
    direction = { True: ' DESC' }

    for i in range(len(sortvec)):
        keyname = sortvec[i][0]
        descending = sortvec[i][1]
        keyname = sql_identifier(keyname)
        norm_parts.append( '%s%s NULLS LAST' % (keyname, direction.get(descending, '')) )
        revs_parts.append( '%s%s NULLS FIRST' % (keyname, direction.get(not descending, '')) )

    norm_parts = ', '.join(norm_parts)
    revs_parts = ', '.join(revs_parts)

    if is_before:
        return (sortvec, revs_parts, norm_parts)
    else:
        return (sortvec, norm_parts, None)
        
class EntityElem (object):
    """Wrapper for instance of entity table in path.

    """
    def __init__(self, epath, alias, table, pos, keyref=None, refop=None, keyref_alias=None, context_pos=None):
        self.epath = epath
        self.alias = alias
        self.table = table
        self.pos = pos
        if context_pos is None:
            context_pos = pos - 1
        self.context_pos = context_pos
        self.keyref = keyref
        self.refop = refop
        self.keyref_alias = keyref_alias
        self.filters = []

    def _link_parts(self):
        fkcols = [ c.name for c in self.keyref.foreign_key.columns ]
        pkcols = [ c.name for c in self.keyref.unique.columns ]

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
        s = unicode(self.table)

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
            s += ' WHERE ' + ' AND '.join([ unicode(f) for f in self.filters ])

        return s

    def __repr__(self):
        return '<ermrest.ermpath.EntityElem %s>' % unicode(self)

    def add_filter(self, filt):
        """Add a filtersql_name condition to this path element.
        """
        filt.validate(self.epath)
        self.filters.append(filt)

    def sql_join_condition(self):
        """Generate SQL condition for joining this element to the epath.

        """
        if not self.keyref:
            raise NotImplementedError('self.keyref')

        ltable, lcnames, rcnames, refop = self._link_parts()

        if self.keyref_alias:
            ltnum = self.epath.aliases[self.keyref_alias]
        else:
            ltnum = self.context_pos
        
        return ' AND '.join([
                't%d.%s = t%d.%s' % (
                    ltnum, 
                    sql_identifier(lcnames[i]),
                    self.pos, 
                    sql_identifier(rcnames[i])
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
    
    def put(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, allow_existing=True, allow_missing=True, attr_update=None, use_defaults=None, attr_aliases=None):
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

           attr_update: customized entity processing
              mkcols, nmkcols --> use specified metakey and non-metakey columns
              None --> use entity metakey and non-metakey columns

           use_defaults: customize entity processing
              { col, ... } --> use defaults
              None --> use input values

           Input rows are correlated to stored entities by metakey
           equivalence.  The metakey for an entity is the union of all
           its unique keys.  The metakey for a custom update may be a
           subset of columns and may in fact be a non-unique key.

           Input row data is applied to existing entities by updating
           the non-metakey columns to match the input.  Input row data
           is used to insert new entities only when allow_missing is
           False and attr_update is None.

        """
        if len(self.filters) > 0:
            raise BadSyntax('Entity filters not allowed during entity PUT.')

        if not self.table.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % self.table)
        
        input_table = random_name("input_data_")
        input_json_table = random_name("input_json_")

        drop_tables = []

        if attr_update is not None:
            # caller has configured an attribute update request
            # input table has key columns followed by non-key columns
            mkcols, nmkcols = attr_update
            if attr_aliases is not None:
                mkcol_aliases, nmkcol_aliases = attr_aliases
            else:
                mkcol_aliases = dict()
                nmkcol_aliases = dict()
        else:
            # we are doing a whole entity request
            # input table has columns in same order as entity table
            inputcols = self.table.columns_in_order()
            mkcols = set()
            for unique in self.table.uniques:
                for c in unique:
                    mkcols.add(c)
            nmkcols = [ c for c in inputcols if c not in mkcols ]
            mkcols = [ c for c in inputcols if c in mkcols ]
            mkcol_aliases = dict()
            nmkcol_aliases = dict()

        if len(mkcols) == 0:
            raise ConflictModel('PUT not supported on entities without key constraints.')
        
        skip_key_tests = False

        if use_defaults is not None:
            if use_defaults.intersection( set([ c.name for c in mkcols ]) ):
                # default values for one or more key columns have been requested
                # input rows cannot be tested for key uniqueness except by trying to insert!
                skip_key_tests = True

        # create temporary table
        cur.execute(
            "CREATE TEMPORARY TABLE %s (%s)" % (
                sql_identifier(input_table),
                ','.join(
                    [
                        c.input_ddl(mkcol_aliases.get(c))
                        for c in mkcols
                    ] + [
                        c.input_ddl(nmkcol_aliases.get(c))
                        for c in nmkcols
                    ]
                )
            )
        )
        drop_tables.append( input_table )
        if in_content_type in [ 'application/x-json-stream' ]:
            cur.execute( "CREATE TEMPORARY TABLE %s (j json)" % sql_identifier(input_json_table))
            drop_tables.append( input_json_table )
        
        # build up intermediate SQL representations of each JSON record as field lists
        # this is used in both JSON-related input data branches below, so lifted up here to share...
        json_cols = []
        json_projection = []

        def json_field(col_name, c):
            json_cols.append(col_name)
            sql_type = c.type.sql(basic_storage=True)
                    
            if c.type.is_array:
                # extract field as JSON and transform to array
                # since PostgreSQL json_to_recordset fails for native array extraction...
                json_projection.append("(SELECT array_agg(x::%s) FROM json_array_elements_text(j->'%s') s (x)) AS %s" % (
                    c.type.base_type.sql(basic_storage=True),
                    c.name,
                    col_name
                ))
            elif c.type.name in ['json', 'jsonb']:
                json_projection.append("(j->'%s')::%s AS %s" % (
                    c.name,
                    c.type.sql(basic_storage=True),
                    col_name
                ))
            else:
                json_projection.append("(j->>'%s')::%s AS %s" % (
                    c.name,
                    c.type.sql(basic_storage=True),
                    col_name
                ))
                        
        for c in mkcols:
            json_field(c.sql_name(mkcol_aliases.get(c)), c)
                        
        for c in nmkcols:
            json_field(c.sql_name(nmkcol_aliases.get(c)), c)
                    
        # copy input data to temp table
        if in_content_type == 'text/csv':
            hdr = csv.reader([ input_data.readline() ]).next()

            inputcol_names = set(
                [ unicode(mkcol_aliases.get(c, c.name)) for c in mkcols ]
                + [ unicode(mkcol_aliases.get(c, c.name)) for c in nmkcols ]
                )
            csvcol_names = set()
            csvcol_names_ordered = []
            for cn in hdr:
                cn = cn.decode('utf8')
                try:
                    inputcol_names.remove(cn)
                    csvcol_names.add(cn)
                    csvcol_names_ordered.append(cn)
                except KeyError:
                    if cn in csvcol_names:
                        raise BadData('CSV column %s appears more than once.' % cn)
                    else:
                        raise ConflictModel('CSV column %s not recognized.' % cn)

            if len(inputcol_names) > 0:
                raise ConflictModel('CSV input missing required columns: %s' 
                              % ', '.join([ '"%s"' % cn for cn in inputcol_names ]))

            try:
                cur.copy_expert(
                """
COPY %s (%s) 
FROM STDIN WITH (
    FORMAT csv, 
    HEADER false, 
    DELIMITER ',', 
    QUOTE '"'
)""" % (
    sql_identifier(input_table),
    ','.join([ sql_identifier(cn) for cn in csvcol_names_ordered ])
),
                    input_data
                )
            except psycopg2.DataError, e:
                raise BadData(u'Bad CSV input. ' + e.pgerror.decode('utf8'))

        elif in_content_type == 'application/json':
            buf = input_data.read().decode('utf8')
            try:
                cur.execute( 
                u"""
INSERT INTO %(input_table)s (%(cols)s)
SELECT %(cols)s 
FROM (
  SELECT %(json_projection)s 
  FROM json_array_elements( %(input)s::json )
    AS rs ( j )
) s
""" % dict( 
    input_table = sql_identifier(input_table),
    cols = u','.join(json_cols),
    input = Type('text').sql_literal(buf),
    json_projection=','.join(json_projection)
)
                )
            except psycopg2.DataError, e:
                raise BadData('Bad JSON array input. ' + e.pgerror)

        elif in_content_type == 'application/x-json-stream':
            try:
                cur.copy_expert( "COPY %s (j) FROM STDIN" % sql_identifier(input_json_table), input_data )
                cur.execute(
                """
INSERT INTO %(input_table)s (%(cols)s)
SELECT %(cols)s
FROM (
  SELECT %(json_projection)s
  FROM %(input_json)s i
) s
""" % dict(
    input_table = sql_identifier(input_table),
    input_json = sql_identifier(input_json_table),
    cols = ','.join(json_cols),
    json_projection=','.join(json_projection)
)
                )
            except psycopg2.DataError, e:
                raise BadData('Bad JSON stream input. ' + e.pgerror)

        else:
            raise UnsupportedMediaType('%s input not supported' % in_content_type)

        correlating_sql = [
            "SELECT %(inmkcols)s FROM %(input_table)s",
            "SELECT %(mkcols)s FROM %(table)s"
        ]
        correlating_sql = tuple([
            sql % dict(
                table = self.table.sql_name(),
                inmkcols = ','.join(
                    [ c.sql_name(mkcol_aliases.get(c)) for c in mkcols ]
                ),
                mkcols = ','.join([ c.sql_name() for c in mkcols ]),
                input_table = sql_identifier(input_table)
            )
            for sql in correlating_sql
        ])

        if allow_existing is False and not skip_key_tests:
            cur.execute("%s INTERSECT ALL %s" % correlating_sql)
            for row in cur:
                raise ConflictData('Input row key (%s) collides with existing entity.' % unicode(row))

        if allow_missing is False:
            cur.execute("%s EXCEPT ALL %s" % correlating_sql)
            for row in cur:
                raise ConflictData('Input row key (%s) does not match existing entity.' % unicode(row))

        def jsonfix1(sql, c):
            return '%s::jsonb' % sql if c.type.name == 'json' else sql
        
        def jsonfix2(sql, c):
            return '%s::json' % sql if c.type.name == 'json' else sql
        
        # reusable parts interpolated into several SQL statements
        parts = dict(
            table = self.table.sql_name(),
            input_table = sql_identifier(input_table),
            assigns = u','.join([ u"%s = i.%s " % ( c.sql_name(), jsonfix2(c.sql_name(nmkcol_aliases.get(c)), c) ) for c in nmkcols ]),
            keymatches = u' AND '.join([
                u"((t.%(t)s = i.%(i)s) OR (t.%(t)s IS NULL AND i.%(i)s IS NULL))" % dict(t=c.sql_name(), i=c.sql_name(mkcol_aliases.get(c)))
                for c in mkcols
            ]),
            cols = ','.join([ c.sql_name() for c in (mkcols + nmkcols) if use_defaults is None or c.name not in use_defaults ]),
            ecols = ','.join([ jsonfix1('e.%s' % c.sql_name(), c) for c in (mkcols + nmkcols) if use_defaults is None or c.name not in use_defaults ]),
            emkcols = ','.join([ jsonfix1('e.%s' % c.sql_name(), c) for c in mkcols ]),
            icols = ','.join([
                jsonfix1('i.%s' % c.sql_name(mkcol_aliases.get(c)), c) for c in mkcols if use_defaults is None or c.name not in use_defaults
            ] + [
                jsonfix1('i.%s' % c.sql_name(nmkcol_aliases.get(c)), c) for c in nmkcols if use_defaults is None or c.name not in use_defaults
            ]),
            mkcols = ','.join([ c.sql_name() for c in mkcols ]),
            nmkcols = ','.join([ c.sql_name() for c in nmkcols ]),
            tcols = u','.join(
                [ u'i.%s AS %s' % (jsonfix2(c.sql_name(mkcol_aliases.get(c)), c), c.sql_name(mkcol_aliases.get(c))) for c in mkcols ]
                + [ u't.%s AS %s' % (jsonfix2(c.sql_name(), c), c.sql_name(nmkcol_aliases.get(c))) for c in nmkcols ]
            )
        )

        cur.execute("CREATE INDEX ON %(input_table)s (%(mkcols)s);" % parts)
        cur.execute("ANALYZE %s;" % sql_identifier(input_table))

        #  -- check for duplicate keys
        if not skip_key_tests:
            cur.execute("SELECT count(*) FROM %s" % sql_identifier(input_table))
            total_rows = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM (SELECT DISTINCT %s FROM %s) s" % (
                    ','.join([ c.sql_name(mkcol_aliases.get(c)) for c in mkcols]),
                    sql_identifier(input_table)
                )
            )
            total_mkeys = cur.fetchone()[0]
            if total_rows > total_mkeys:
                raise ConflictData('Multiple input rows share the same unique key information.')

        def preserialize(sql):
            if content_type == 'text/csv':
                # TODO implement and use row_to_csv() stored procedure?
                pass
            elif content_type == 'application/json':
                sql = "WITH q AS (%s) SELECT COALESCE(array_to_json(array_agg(row_to_json(q)), True)::text, '[]') FROM q" % sql
            elif content_type == 'application/x-json-stream':
                sql = "WITH q AS (%s) SELECT row_to_json(q)::text FROM q" % sql
            elif content_type in [ dict, tuple ]:
                pass
            else:
                raise NotImplementedError('content_type %s' % content_type)
            #web.debug(sql)
            return sql

        # NOTE: we already prefetch the whole result so might as well build incrementally...
        results = []

        # we cannot use a held cursor here because upsert_sql modifies the DB
        try:
            notify_data_change(cur, self.table)

            if allow_existing:
                cur.execute(
                    preserialize(("""
UPDATE %(table)s t SET %(assigns)s FROM (
  SELECT %(icols)s FROM %(input_table)s i
""" + (" EXCEPT SELECT %(ecols)s FROM %(table)s e" if use_defaults is None else ""
) + """) i
WHERE %(keymatches)s
RETURNING %(tcols)s""") % parts
                    )
                )
                results.extend(make_row_thunk(None, cur, content_type)())

                if allow_missing is None:
                    raise NotImplementedError("EntityElem.put allow_existing=%s allow_missing=%s" % (allow_existing, allow_missing))
            else:
                assert allow_missing

            if allow_missing:
                parts.update(
                    tcols = ','.join([ jsonfix2(c.sql_name(), c) for c in (mkcols + nmkcols) ])
                )
                cur.execute(
                    preserialize(("""
INSERT INTO %(table)s AS t (%(cols)s)
SELECT * FROM (
  SELECT %(icols)s FROM %(input_table)s i
""" + ("""
  JOIN (
    SELECT %(emkcols)s FROM %(input_table)s e
    EXCEPT SELECT %(mkcols)s FROM %(table)s e
  ) t ON (%(keymatches)s)""" if use_defaults is None else ""
) + ") i RETURNING %(tcols)s") % parts
                    )
                )
                results.extend(make_row_thunk(None, cur, content_type)())

            for table in drop_tables:
                cur.execute("DROP TABLE %s" % sql_identifier(table))
        except psycopg2.IntegrityError, e:
            raise ConflictModel('Input data violates model. ' + e.pgerror)
            
        return results

class AnyPath (object):
    """Hierarchical ERM access to resources, a generic parent-class for concrete resources.

    """
    def sql_get(self, row_content_type='application/json', limit=None):
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

    def _sql_get_agg_attributes(self, allow_extra=True):
        """Process attribute lists for aggregation APIs.
        """
        aggfunc_templates = dict(
            min='min(%(attr)s)', 
            max='max(%(attr)s)', 
            cnt='count(%(attr)s)', 
            cnt_d='count(DISTINCT %(attr)s)',
            array='array_to_json(array_agg(%(attr)s))'
            )

        aggfunc_star_templates = dict(
            cnt='count(*)',
            array='array_to_json(array_agg(%(attr)s))'
            )

        aggregates = []
        extras = []
        
        for attribute, col, base in self.attributes:
            sql_attr = sql_identifier(
                attribute.alias is not None and unicode(attribute.alias) or unicode(col.name)
                )

            if hasattr(attribute, 'aggfunc'):
                templates = col.is_star_column() and aggfunc_star_templates or aggfunc_templates

                if attribute.alias is None:
                    raise BadSyntax('Aggregated column %s must be given an alias.' % attribute)

                if unicode(attribute.aggfunc) not in templates:
                    raise BadSyntax('Unknown or unsupported aggregate function "%s" applied to column "%s".' % (attribute.aggfunc, col.name))

                aggregates.append((templates[unicode(attribute.aggfunc)] % dict(attr=sql_attr), sql_attr))
            elif not allow_extra:
                raise BadSyntax('Attribute %s lacks an aggregate function.' % attribute)
            else:
                extras.append(sql_attr)

        return aggregates, extras

    def get(self, conn, cur, content_type='text/csv', output_file=None, limit=None):
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

        sql = self.sql_get(row_content_type=content_type, limit=limit)

        #web.debug(sql)

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

            cur.copy_expert(sql, output_file)

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
            
            return make_row_thunk(conn, cur, content_type)()
        
class EntityPath (AnyPath):
    """Hierarchical ERM data access to whole entities, i.e. table rows.

    """
    def __init__(self, model):
        AnyPath.__init__(self)
        self._model = model
        self._path = None
        self._context_index = None
        self.sort = None
        self.after = None
        self.before = None
        self.aliases = {}

    def __str__(self):
        return ' / '.join(
            [ unicode(e) for e in self._path ] 
            + self._context_index >= 0 and [ '$%s' % self._path[self._context_index].alias ] or []
            )

    def __getitem__(self, k):
        return self._path[ self.aliases[k] ]

    def set_base_entity(self, table, alias=None):
        """Root this entity path in the specified table.

           Optionally set alias for the root.
        """
        if not self._path is None:
            raise NotImplementedError('self._path')
        self._path = [ EntityElem(self, alias, table, 0) ]
        self._context_index = -1
        if alias is not None:
            self.aliases[alias] = 0

    def current_entity_table(self):
        """Get table aka entity type associated with the current path.

           The entity type of the path is the right-most table of the
           path.
        """
        return self._path[self._context_index].table

    def current_entity_position(self):
        """Get non-negative integer position of current entity context in path."""
        if self._context_index == -1:
            return len(self._path) - 1
        elif self._context_index >= 0:
            return self._context_index
        else:
            raise NotImplementedError('current_entity_position with index %s' % self._context_index)

    def set_context(self, alias):
        """Change path entity context to existing context referenced by alias."""
        self._context_index = self.aliases[alias]

    def get_data_version(self, cur):
        """Get data version txid considering all tables in entity path."""
        preds = [
            elem.table.kind == 'r'
            and
            '("schema" = %s AND "table" = %s)' % (
                sql_literal(elem.table.schema.name), 
                sql_literal(elem.table.name)
                )
            or
            'True'
            for elem in self._path
            ]
        cur.execute("""
SELECT COALESCE(max(snap_txid), 0) AS snap_txid 
FROM _ermrest.data_version
WHERE %(pred)s
""" % dict(pred=' OR '.join(preds))
                    )
        version = next(cur)
        return version

    def add_filter(self, filt):
        """Add a filter condition to the current path.

           Filters restrict the matched rows of the right-most table.
        """
        return self._path[self._context_index].add_filter(filt)

    def add_sort(self, sort):
        """Add a sortlist specification for final output.

           Each column must be part of the entity type associated with current path.
        """
        self.sort = sort

    def add_paging(self, after, before):
        """Add page key specification(s) for the final output.
        """
        if after is not None and before is not None:
            raise BadSyntax('At most one @before() or @after() modifier is permitted in a single request.')
        self.after = after
        self.before = before
            
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
        if not self._path:
            raise NotImplementedError('self._path %s' % self._path)
        rpos = len(self._path)

        if refop == '@=':
            rtable = keyref.foreign_key.table
        else:
            # '=@'
            rtable = keyref.unique.table

        assert self._context_index >= -1
        if self._context_index >= 0:
            rcontext = self._context_index
        else:
            rcontext = rpos - 1
        
        self._path.append( EntityElem(self, ralias, rtable, rpos, keyref, refop, lalias, rcontext) )
        self._context_index = -1

        if ralias is not None:
            if ralias in self.aliases:
                raise BadData('Alias %s bound more than once.' % ralias)
            self.aliases[ralias] = rpos


    def sql_get(self, selects=None, distinct_on=True, row_content_type='application/json', limit=None):
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
        selects = selects or ("t%d.*" % (self.current_entity_position()))

        pkeys = self._path[self._context_index].table.uniques.keys()
        if pkeys:
            pkeys.sort(key=lambda k: len(k))
            shortest_pkey = self._path[self._context_index].table.uniques[pkeys[0]].columns
        else:
            shortest_pkey = self._path[self._context_index].table.columns_in_order()
        distinct_on_cols = [ 
            't%d.%s' % (self.current_entity_position(), sql_identifier(c.name))
             for c in shortest_pkey
            ]

        tables = [ elem.sql_table_elem() for elem in self._path ]

        wheres = []
        for elem in self._path:
            wheres.extend( elem.sql_wheres() )

        sql = """
SELECT 
  %(distinct_on)s
  %(selects)s
FROM %(tables)s
%(where)s
""" % dict(distinct_on = distinct_on and ('DISTINCT ON (%s)' % ', '.join(distinct_on_cols)) or '',
           selects     = selects,
           tables      = ' JOIN '.join(tables),
           where       = wheres and ('WHERE ' + ' AND '.join(['(%s)' % w for w in wheres])) or ''
           )
	
	# This subquery is ugly and inefficient but necessary due to DISTINCT ON above
	if self.sort is not None:
            table = self.current_entity_table()

            def sort_lookup(key):
                if key.keyname not in table.columns:
                    raise ConflictModel('Sort key "%s" not found in table "%s".' % (key.keyname, table.name))
                return (key.keyname, key.descending, table.columns[key.keyname].type)

            sortvec, sort1, sort2 = sort_components(map(sort_lookup, self.sort), self.before is not None)
        else:
            sortvec, sort1, sort2 = (None, None, None)

        limit = 'LIMIT %d' % limit if limit is not None else ''
            
    	if sort1 is not None:
            a, b, c = map(lambda x: x[0], sortvec), map(lambda x: x[1], sortvec), map(lambda x: x[2], sortvec)
            if self.after is not None:
                page = 'WHERE %s' % page_filter_sql(a, b, c, self.after, is_before=False)
            elif self.before is not None:
                page = 'WHERE %s' % page_filter_sql(a, b, c, self.before, is_before=True)
            else:
                page = ''

            sql = "SELECT * FROM (%s) s %s ORDER BY %s %s" % (sql, page, sort1, limit)

            if sort2 is not None:
                if not limit:
                    raise BadSyntax('Page @before(...) modifier not allowed without limit parameter.')
                sql = "SELECT * FROM (%s) s ORDER BY %s" % (sql, sort2)
        else:
            sql = "%s %s" % (sql, limit)

        return sql

    def sql_delete(self):
        """Generate SQL statement to delete the entities described by this epath.
        """
        table = self._path[self._context_index].table
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
            keymatches = ' AND '.join([ "t.%s IS NOT DISTINCT FROM i.%s " % (c, c) for c in mkcols ])
            )
    
    def delete(self, conn, cur):
        """Delete entities.

           conn: sanepg2 database connection to catalog
        """
        table = self.current_entity_table()
        if not table.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % table)
        
        cur.execute("SELECT count(*) AS count FROM (%s) s" % self.sql_get())
        cnt = cur.fetchone()[0]
        if cnt == 0:
            raise NotFound('entities matching request path')
        notify_data_change(cur, table)
        cur.execute(self.sql_delete())
        if cnt > cur.rowcount:
            # HACK: assume difference in rowcount is due to row-level security??
            raise Forbidden('deletion of one or more rows')
        
    def put(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, allow_existing=True, allow_missing=True, attr_update=None, use_defaults=None, attr_aliases=None):
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
        
        return self._path[0].put(conn, cur, input_data, in_content_type, content_type, output_file, allow_existing, allow_missing, attr_update, use_defaults, attr_aliases)
        

class AttributePath (AnyPath):
    """Hierarchical ERM data access to entity attributes, i.e. table cells.

    """
    def __init__(self, epath, attributes):
        AnyPath.__init__(self)
        self.epath = epath
        self.attributes = attributes
        self.sort = None
        self.after = None
        self.before = None


    def add_sort(self, sort):
        """Add a sortlist specification for final output.

           Validation deferred until sql_get() runs... sort keys must match designated output columns.
        """
        self.sort = sort

    def add_paging(self, after, before):
        """Add page key specification(s) for the final output.
        """
        if after is not None and before is not None:
            raise BadSyntax('At most one @before() or @after() modifier is permitted in a single request.')
        self.after = after
        self.before = before
            
    def sql_get(self, split_sort=False, distinct_on=True, row_content_type='application/json', limit=None):
        """Generate SQL query to get the resources described by this apath.

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

        outputs = set()
        output_types = {}

        for attribute, col, base in self.attributes:
            if base == self.epath:
                # column in final entity path element
                alias = "t%d" % self.epath.current_entity_position()
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                alias = "t%d" % self.epath[base].pos
            else:
                raise ConflictModel('Invalid attribute name "%s".' % attribute)

            if hasattr(col, 'sql_name_with_talias'):
                select = col.sql_name_with_talias(alias, output=True)
            else:
                select = "%s.%s" % (alias, col.sql_name())

            select = select

            if attribute.alias is not None:
                if unicode(attribute.alias) in outputs:
                    raise BadSyntax('Output column name "%s" appears more than once.' % attribute.alias)
                outputs.add(unicode(attribute.alias))
                output_types[unicode(attribute.alias)] = col.type
                selects.append('%s AS %s' % (select, sql_identifier(attribute.alias)))
            else:
                if unicode(col.name) in outputs:
                    raise BadSyntax('Output column name "%s" appears more than once.' % col.name)
                outputs.add(unicode(col.name))
                output_types[unicode(col.name)] = col.type
                selects.append('%s AS %s' % (select, col.sql_name()))

        if self.sort:
            def sort_lookup(key):
                if key.keyname not in outputs:
                    raise BadData('Sort key "%s" not among output columns.' % key.keyname)
                return (key.keyname, key.descending, output_types[key.keyname])
            
            sortvec, sort1, sort2 = sort_components(map(sort_lookup, self.sort), self.before is not None)
        else:
            sortvec, sort1, sort2 = (None, None, None)

        page = ''
            
        if sort1 is not None:
            a, b, c = map(lambda x: x[0], sortvec), map(lambda x: x[1], sortvec), map(lambda x: x[2], sortvec)
            if self.after is not None:
                page = 'WHERE %s' % page_filter_sql(a, b, c, self.after, is_before=False)
            elif self.before is not None:
                page = 'WHERE %s' % page_filter_sql(a, b, c, self.before, is_before=True)
                
        selects = ', '.join(selects)

        limit = 'LIMIT %d' % limit if limit is not None else ''

        if split_sort:
            # let the caller compose the query and the sort clauses
            return (self.epath.sql_get(selects=selects, distinct_on=distinct_on), page, sort1, limit, sort2)
        else:
            sql = self.epath.sql_get(selects=selects, distinct_on=distinct_on)
                
            if sort1 is not None:
                sql = "SELECT * FROM (%s) s %s ORDER BY %s %s" % (sql, page, sort1, limit)

                if sort2 is not None:
                    if not limit:
                        raise BadSyntax('Page @before(...) modifier not allowed without limit parameter.')
                    sql = "SELECT * FROM (%s) s ORDER BY %s" % (sql, sort2)
            else:
                sql = "%s %s" % (sql, limit)        

            return sql

    def sql_delete(self, del_columns, equery=None):
        """Generate SQL statement to delete the attributes described by this apath.

           del_columns: iterable set of Column instances to be deleted

        """
        if equery is None:
            equery = self.epath.sql_get()

        etable = self.epath.current_entity_table()

        if not etable.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % etable)

        mkcols = set()
        for unique in etable.uniques:
            for c in unique:
                mkcols.add(c)

        for c in del_columns:
            if c in mkcols:
                raise ConflictModel('Deletion of attribute %s not supported because it is part of a unique key for entities.' % c.name)

        # actually correlate by full row, not just unique meta-key
        mkcols = [ c.sql_name() for c in etable.columns_in_order() ]
        nmkcols = [ c.sql_name() for c in del_columns ]
        
        return """
UPDATE %(table)s AS t SET %(updates)s
FROM (%(getqry)s) AS i
WHERE %(keymatches)s
""" % dict(
            table = etable.sql_name(),
            getqry = equery,
            keymatches = ' AND '.join([ "t.%s IS NOT DISTINCT FROM i.%s " % (c, c) for c in mkcols ]),
            updates = ', '.join([ "%s = NULL" % c for c in nmkcols ])
            )
    
    def delete(self, conn, cur):
        """Delete entity attributes.

        """
        equery = self.epath.sql_get()
        nmkcols = set()
        
        # delete columns are named explicitly
        for attribute, col, base in self.attributes:
            if base == self.epath:
                # column in final entity path element
                nmkcols.add(col)
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                raise ConflictModel('Only unqualified attribute names from entity %s can be modified by DELETE.' % etable.name)
            else:
                raise ConflictModel('Invalid attribute name "%s".' % attribute)
        
        dquery = self.sql_delete(nmkcols, equery)

        cur.execute("SELECT count(*) AS count FROM (%s) s" % equery)
        if cur.fetchone()[0] == 0:
            raise NotFound('entities matching request path')
        table = self.epath.current_entity_table()
        notify_data_change(cur, table)
        cur.execute(dquery)

class AttributeGroupPath (AnyPath):
    """Hierarchical ERM data access to entity attributes, i.e. table cells.

    """
    def __init__(self, epath, groupkeys, attributes):
        AnyPath.__init__(self)
        self.epath = epath
        self.groupkeys = groupkeys
        self.attributes = attributes
        self.sort = None
        self.after = None
        self.before = None

        if not groupkeys:
            raise BadSyntax('Attribute group requires at least one group key.')

    def add_sort(self, sort):
        """Add a sortlist specification for final output.

           Validation deferred until sql_get() runs... sort keys must match designated output columns.
        """
        self.sort = sort

    def add_paging(self, after, before):
        """Add page key specification(s) for the final output.
        """
        if after is not None and before is not None:
            raise BadSyntax('At most one @before() or @after() modifier is permitted in a single request.')
        self.after = after
        self.before = before
            
    def sql_get(self, row_content_type='application/json', limit=None):
        """Generate SQL query to get the resources described by this apath.

           The query will be of the form:

              SELECT
                group keys...,
                attributes...
              FROM (
                ...
              ) s
              GROUP BY group keys...

           and may join on an additional DISTINCT ON query if the
           attribute list includes non-key non-aggregate values.
           
           encoding path references and filter conditions.

        """
        apath = AttributePath(self.epath, self.groupkeys + self.attributes)
        apath.add_sort(self.sort)
        apath.add_paging(self.after, self.before)
        
        groupkeys = []
        aggregates = []
        extras = []

        for key, col, base in self.groupkeys:
            if key.alias is not None:
                groupkeys.append( sql_identifier(unicode(key.alias)) )
            else:
                groupkeys.append( sql_identifier(unicode(col.name)) )

        aggregates, extras = self._sql_get_agg_attributes()
        asql, page, sort1, limit, sort2 = apath.sql_get(split_sort=True, distinct_on=False, limit=limit)

        if extras:
            # an impure aggregate query includes extras which must be reduced 
            # by an arbitrary DISTINCT ON and joined to the core aggregate query
            sql = """
SELECT * FROM (
SELECT
  %(selects)s
FROM (
  SELECT %(groupaggs)s FROM ( %(asql)s ) s GROUP BY %(groupkeys)s
) g
JOIN ( 
  SELECT DISTINCT ON ( %(groupkeys)s )
    %(groupextras)s
  FROM ( %(asql)s ) s
) e ON ( %(joinons)s ) ) s
"""
        else:
            # a pure aggregate query has only group keys and aggregates
            sql = """
SELECT %(groupaggs)s
FROM ( %(asql)s ) s
GROUP BY %(groupkeys)s
"""
        sql = sql % dict(
            asql=asql,
            selects=', '.join(['g.%s' % k for k in groupkeys + [ a[1] for a in aggregates]]
                              + [ 'e.%s' % e for e in extras ]),
            groupkeys=', '.join(groupkeys),
            groupaggs=', '.join(groupkeys + ["%s AS %s" % a for a in aggregates]),
            groupextras=', '.join(groupkeys + extras),
            joinons=' AND '.join([ 
                    '(g.%s IS NOT DISTINCT FROM e.%s)' % (k, k)
                    for k in groupkeys
                    ])
            )

        if sort1 is not None:
            sql = "SELECT * FROM (%s) s %s ORDER BY %s %s" % (sql, page, sort1, limit)

            if sort2 is not None:
                if not limit:
                    raise BadSyntax('Page @before(...) modifier not allowed without limit parameter.')
                sql = "SELECT * FROM (%s) s ORDER BY %s" % (sql, sort2)
        else:
            sql = "%s %s" % (sql, limit)

        return sql

    def put(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None):
        """Update entity attributes.

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
        mkcols = set()
        mkcol_aliases = dict()
        for groupkey, col, base in self.groupkeys:
            if col in mkcols:
                raise BadSyntax('Group key column %s cannot be bound more than once.' % col)
            if groupkey.alias:
                mkcol_aliases[col] = groupkey.alias
            if base == self.epath:
                # column in final entity path element
                mkcols.add(col)
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                mkcols.add(col)
            else:
                raise ConflictModel('Invalid groupkey name "%s".' % groupkey)

        nmkcols = set()
        nmkcol_aliases = dict()
        for attribute, col, base in self.attributes:
            if hasattr(attribute, 'aggfunc'):
                raise BadSyntax('Aggregated column %s not allowed in PUT.' % attribute)

            if col in nmkcols:
                raise BadSyntax('Update column %s cannot be bound more than once.' % col)
            if attribute.alias:
                nmkcol_aliases[col] = attribute.alias
            if base == self.epath:
                # column in final entity path element
                nmkcols.add(col)
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                raise ConflictModel('Only unqualified attribute names from entity %s can be modified by PUT.' % etable.name)
            else:
                raise ConflictModel('Invalid attribute name "%s".' % attribute)
        
        if not nmkcols:
            raise BadSyntax('Grouped attribute update requires at least one target attribute.')

        attr_update = (list(mkcols), list(nmkcols))
        attr_aliases = (mkcol_aliases, nmkcol_aliases)
        return self.epath.put(conn, cur, input_data, in_content_type, content_type, output_file, allow_existing=True, allow_missing=False, attr_update=attr_update, attr_aliases=attr_aliases)
        

class AggregatePath (AnyPath):
    """Hierarchical ERM data access to aggregate row.

    """
    def __init__(self, epath, attributes):
        AnyPath.__init__(self)
        self.epath = epath
        self.attributes = attributes

        if not attributes:
            raise BadSyntax('Aggregate requires at least one attribute.')

    def add_sort(self, sort):
        """Add a sortlist specification for final output.

           Validation deferred until sql_get() runs... sort keys must match designated output columns.
        """
        if sort:
            raise BadSyntax('Sort is meaningless for aggregates returning one row.')

    def add_paging(self, before, after):
        # to honour generic API.  actually gated on self.add_sort() above so no need to test again
        pass
        
    def sql_get(self, row_content_type='application/json', limit=None):
        """Generate SQL query to get the resources described by this apath.

        """
        apath = AttributePath(self.epath, self.attributes)
        aggregates, extras = self._sql_get_agg_attributes(allow_extra=False)
        asql, page, sort1, limit, sort2 = apath.sql_get(split_sort=True, distinct_on=False)

        # a pure aggregate query has aggregates
        sql = """
SELECT %(aggs)s
FROM ( %(asql)s ) s
"""
        return sql % dict(
            asql=asql,
            aggs=', '.join([ '%s AS %s' % (a[0], a[1]) for a in aggregates]),
            )

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

def val_to_csv(v, cdesc=None):
    def condquote(v):
        if v.find(u',') > -1 or v.find(u'"') > -1:
            return u'"%s"' % (v.replace(u'"', u'""'))
        else:
            return v

    if cdesc is not None:
        if cdesc.type_code in [ JSON_OID, JSONB_OID ]:
            return condquote(json.dumps(v))

    if v is None:
        return u''

    if type(v) in [ int, float, long ]:
        return u'%s' % v

    if type(v) is list:
        return condquote(u'{%s}' % u",".join([ val_to_csv(e) for e in v ]))

    elif type(v) is str:
        return condquote(v.decode('utf8'))
    
    else:
        return condquote(unicode(v))

def row_to_csv(row, desc=None):
    try:
        return (u','.join([ val_to_csv(row[i], desc[i] if desc is not None else None) for i in range(len(row)) ])).encode('utf8')
    except Exception, e:
        web.debug('row_to_csv', row, e)

       
