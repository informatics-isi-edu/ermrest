# 
# Copyright 2013-2017 University of Southern California
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
from ..model import text_type, int8_type, jsonb_type

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
    def __init__(self, epath, alias, table, pos, keyref=None, refop=None, keyref_alias=None, context_pos=None, outer_type=None):
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
        self.outer_type = outer_type

    def _link_parts(self):
        if self.refop == '=@':
            # left to right reference
            ltable = self.keyref.foreign_key.table
        else:
            # right to left reference
            ltable = self.keyref.unique.table

        return ltable, self.refop

    def __str__(self):
        s = unicode(self.table)

        if self.alias:
            s += ' AS %s' % self.alias

        if self.keyref:
            ltable, refop = self._link_parts()
        
            if self.keyref_alias:
                ltname = self.keyref_alias
            else:
                ltname = '..'

            s += ' ON (%s)' % self.keyref.join_str(refop, ltname, '.')

        if self.filters:
            s += ' WHERE ' + ' AND '.join([ unicode(f) for f in self.filters ])

        return s

    def __repr__(self):
        return '<ermrest.ermpath.EntityElem %s>' % unicode(self)

    def add_filter(self, filt, enforce_client=True):
        """Add a filtersql_name condition to this path element.
        """
        filt.validate(self.epath, enforce_client=enforce_client)
        self.filters.append(filt)

    def sql_join_condition(self, prefix):
        """Generate SQL condition for joining this element to the epath.

        """
        if not self.keyref:
            raise NotImplementedError('self.keyref')

        ltable, refop = self._link_parts()

        if self.keyref_alias:
            ltnum = self.epath.aliases[self.keyref_alias]
        else:
            ltnum = self.context_pos

        return self.keyref.join_sql(refop, '%st%d' % (prefix, ltnum), '%st%d' % (prefix, self.pos))

    def sql_wheres(self, prefix=''):
        """Generate SQL row conditions for filtering this element in the epath.
           
        """
        return [ f.sql_where(self.epath, self, prefix=prefix) for f in self.filters ]

    def sql_table_elem(self, dynauthz=None, access_type='select', prefix='', dynauthz_testcol=None):
        """Generate SQL table element representing this entity as part of the epath JOIN.

           dynauthz: dynamic authorization mode to compile
               None: do not compile dynamic ACLs
               True: compile positive ACL... match rows client is authorized to access
               False: compile negative ACL... match rows client is NOT authorized to access

           dynauthz_testcol:
               None: normal mode
               col: match rows where client is NOT authorized to access column

        """
        alias = '%st%d' % (prefix, self.pos)
        tsql = self.table.sql_name(dynauthz=dynauthz, access_type=access_type, alias=alias, dynauthz_testcol=dynauthz_testcol)
        if self.pos == 0:
            return tsql
        else:
            return '%s JOIN %s ON (%s)' % (
                {"left": "LEFT OUTER", "right": "RIGHT OUTER", "full": "FULL OUTER", None: ""}[self.outer_type],
                tsql,
                self.sql_join_condition(prefix)
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
        system_colnames = {'RID','RCT','RMT','RCB','RMB'}

        if attr_update is not None:
            # caller has configured an attribute update request
            # input table has key columns followed by non-key columns
            mkcols, nmkcols = attr_update
            extra_return_cols = []
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
            nmkcols = [ c for c in inputcols if c not in mkcols and c.name not in system_colnames ]
            mkcols = [ c for c in inputcols if c in mkcols and c.name not in system_colnames ]
            mkcol_aliases = dict()
            nmkcol_aliases = dict()
            extra_return_cols = [ c for c in inputcols if c.name in system_colnames ]

        if len(mkcols) == 0:
            raise ConflictModel('PUT not supported on entities without key constraints.')
        
        skip_key_tests = False

        if use_defaults is not None:
            use_defaults = set([
                self.table.columns.get_enumerable(cname).name
                for cname in use_defaults
            ] + [
                # system columns aren't writable so don't make client ask for their defaults explicitly
                self.table.columns[cname]
                for cname in system_colnames
                if cname in self.table.columns
            ])

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
            if col_name is None:
                col_name = c.name
            
            json_cols.append(c.sql_name(col_name))
            sql_type = c.type.sql(basic_storage=True)
            
            if c.type.is_array:
                # extract field as JSON and transform to array
                # since PostgreSQL json_to_recordset fails for native array extraction...
                # if ELSE clause hits a non-array, we'll have a 400 Bad Request error as before
                json_projection.append("""
(CASE
 WHEN json_typeof(j->'%(field)s') = 'null'
   THEN NULL::%(type)s[]
 ELSE
   COALESCE((SELECT array_agg(x::%(type)s) FROM json_array_elements_text(j->'%(field)s') s (x)), ARRAY[]::%(type)s[])
 END) AS %(alias)s
""" % dict(
    type=c.type.base_type.sql(basic_storage=True),
    field=col_name,
    alias=c.sql_name(col_name)
)
                )
            elif c.type.name in ['json', 'jsonb']:
                json_projection.append("(j->'%s')::%s AS %s" % (
                    col_name,
                    c.type.sql(basic_storage=True),
                    c.sql_name(col_name)
                ))
            else:
                json_projection.append("(j->>'%s')::%s AS %s" % (
                    col_name,
                    c.type.sql(basic_storage=True),
                    c.sql_name(col_name)
                ))
                        
        for c in mkcols:
            json_field(mkcol_aliases.get(c), c)
                        
        for c in nmkcols:
            json_field(nmkcol_aliases.get(c), c)
                    
        # copy input data to temp table
        if in_content_type == 'text/csv':
            hdr = csv.reader([ input_data.readline() ]).next()

            inputcol_names = set(
                [ unicode(mkcol_aliases.get(c, c.name)) for c in mkcols ]
                + [ unicode(nmkcol_aliases.get(c, c.name)) for c in nmkcols ]
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
    input = text_type.sql_literal(buf),
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

        def jsonfix1(sql, c):
            return '%s::jsonb' % sql if c.type.name == 'json' else sql
        
        def jsonfix2(sql, c):
            return '%s::json' % sql if c.type.name == 'json' else sql
        
        # reusable parts interpolated into several SQL statements
        parts = dict(
            table = self.table.sql_name(),
            input_table = sql_identifier(input_table),
            assigns = u','.join([
                u"%s = i.%s " % ( c.sql_name(), jsonfix2(c.sql_name(nmkcol_aliases.get(c)), c) )
                for c in nmkcols
            ] + [
                # add these metadata maintenance tasks.  if they are in nmkcols already we'll abort with Forbidden.
                u"%s = DEFAULT " % self.table.columns[cname].sql_name()
                for cname in {'RMT','RMB'}
                if cname in self.table.columns
            ]),
            keymatches = u' AND '.join([
                u"((t.%(t)s = i.%(i)s) OR (t.%(t)s IS NULL AND i.%(i)s IS NULL))" % dict(t=c.sql_name(), i=c.sql_name(mkcol_aliases.get(c)))
                for c in mkcols
            ]),
            cols = ','.join([ c.sql_name() for c in (mkcols + nmkcols) if use_defaults is None or c.name not in use_defaults ]),
            ecols = ','.join([ jsonfix1('e.%s' % c.sql_name(), c) for c in (mkcols + nmkcols) if use_defaults is None or c.name not in use_defaults ]),
            emkcols = ','.join([ jsonfix1('e.%s' % c.sql_name(), c) for c in mkcols ]),
            icols = ','.join(
                [jsonfix1('i.%s' % c.sql_name(mkcol_aliases.get(c)), c) for c in mkcols]
                + [jsonfix1('i.%s' % c.sql_name(nmkcol_aliases.get(c)), c) for c in nmkcols]
            ),
            mkcols = ','.join([ c.sql_name() for c in mkcols ]),
            # limit input table index to 32 cols to protect against PostgresQL limit... just runs a slower correlation query here instead...
            mkcols_idx = ','.join([ c.sql_name(mkcol_aliases.get(c)) for c in mkcols ][0:32]),
            nmkcols = ','.join([ c.sql_name() for c in nmkcols ]),
            tcols = u','.join(
                [ u'i.%s AS %s' % (jsonfix2(c.sql_name(mkcol_aliases.get(c)), c), c.sql_name(mkcol_aliases.get(c))) for c in mkcols ]
                + [ u't.%s AS %s' % (jsonfix2(c.sql_name(), c), c.sql_name(nmkcol_aliases.get(c))) for c in nmkcols ]
            )
        )

        cur.execute("CREATE INDEX ON %(input_table)s (%(mkcols_idx)s);" % parts)
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

        # -- pre-checks for restricted fkey write scenarios
        # 1. accumulate all fkrs into a map  { c: {fkr,...} }
        nonnull_fkey_col_fkrs = dict()
        for fk in self.table.fkeys.values():
            for c in fk.columns:
                if c not in nonnull_fkey_col_fkrs:
                    nonnull_fkey_col_fkrs[c] = set(fk.references.values())
                else:
                    nonnull_fkey_col_fkrs[c].update(set(fk.references.values()))

        # 2. prune columns from map if column is not affected by request or no input data IS NOT NULL
        for c in list(nonnull_fkey_col_fkrs):
            if c in mkcols:
                alias = mkcol_aliases.get(c)
            elif c in nmkcols:
                alias = nmkcol_aliases.get(c)
            else:
                # prune this unaffected column
                del nonnull_fkey_col_fkrs[c]
                continue
            cur.execute("SELECT True FROM %s WHERE %s IS NOT NULL LIMIT 1" % (parts['input_table'], c.sql_name(alias)))
            row = cur.fetchone()
            if row and row[0]:
                pass
            else:
                del nonnull_fkey_col_fkrs[c]

        # 3. make mkcol and nmkcol specific maps of affected columns (same fkr may appear in both for composites fkrs)
        nonnull_mkcol_fkrs = dict()
        nonnull_nmkcol_fkrs = dict()
        nonnull_fkrs = dict()
        for c, fkrs in nonnull_fkey_col_fkrs.items():
            nonnull_fkrs[c] = fkrs
            if c in mkcols:
                nonnull_mkcol_fkrs[c] = fkrs
            elif c in nmkcols:
                nonnull_nmkcol_fkrs[c] = fkrs

        del nonnull_fkey_col_fkrs

        # do static enforcement before we start analyzing data
        if allow_existing and nmkcols:
            # if nmkcols is empty, so will be assigns... UPSERT reverts to idempotent INSERT
            self.table.enforce_right('update')
            for c in nmkcols:
                c.enforce_data_right('update')
            for fkr in set().union(*[ set(fkrs) for fkrs in nonnull_nmkcol_fkrs.values() ]):
                fkr.enforce_right('update')
        elif allow_missing:
            # static checks for pure insert case
            self.table.enforce_right('insert', require_true=True)
            for c in set(mkcols).union(set(nmkcols)):
                c.enforce_data_right('insert', require_true=True)
            for fkr in set().union(*[ set(fkrs) for fkrs in nonnull_fkrs.values() ]):
                fkr.enforce_right('insert')

        if allow_existing is False and not skip_key_tests:
            cur.execute("%s INTERSECT ALL %s" % correlating_sql)
            for row in cur:
                raise ConflictData('Input row key (%s) collides with existing entity.' % unicode(row))

        if allow_missing is False:
            cur.execute("%s EXCEPT ALL %s" % correlating_sql)
            for row in cur:
                raise ConflictData('Input row key (%s) does not match existing entity.' % unicode(row))

        def preserialize(sql):
            if content_type == 'text/csv':
                # TODO implement and use row_to_csv() stored procedure?
                pass
            elif content_type == 'application/json':
                sql = "WITH q AS (%s) SELECT COALESCE(array_to_json(array_agg(row_to_json(q.*)), True)::text, '[]') FROM q" % sql
            elif content_type == 'application/x-json-stream':
                sql = "WITH q AS (%s) SELECT row_to_json(q.*)::text FROM q" % sql
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
                if nmkcols:
                    # if nmkcols is empty, so will be assigns... UPSERT reverts to idempotent INSERT
                    if self.table.has_right('update') is None:
                        # need to enforce dynamic ACLs
                        parts2 = dict(parts)
                        parts2['table'] = self.table.sql_name(dynauthz=False, access_type='update', alias="t")
                        cur.execute(("""
SELECT i.*
FROM %(table)s
JOIN (
  SELECT %(icols)s FROM %(input_table)s i
) i
ON (%(keymatches)s)
LIMIT 1""") % parts2
                        )
                        if cur.rowcount > 0:
                            raise Forbidden(u'update access on one or more rows in table %s' % self.table)

                    for c in nmkcols:
                        if c.has_data_right('update') is None and c.dynauthz_restricted('update'):
                            # need to enforce dynamic ACLs
                            parts2 = dict(parts)
                            parts2['table'] = self.table.sql_name(access_type='update', alias="t", dynauthz_testcol=c)
                            sql = ("""
SELECT i.*
FROM %(table)s
JOIN (
  SELECT %(icols)s FROM %(input_table)s i
) i
ON (%(keymatches)s)
LIMIT 1""") % parts2
                            #web.debug(sql)
                            cur.execute(sql)
                            if cur.rowcount > 0:
                                raise Forbidden(u'update access on column %s for one or more rows' % c)

                    for fkr in set().union(*[ set(fkrs) for fkrs in nonnull_nmkcol_fkrs.values() ]):
                        if fkr.has_right('update') is None:
                            # need to enforce dynamic ACLs
                            fkr_cols = [
                                (
                                    (u'i.%s' % fc.sql_name(nmkcol_aliases.get(fc)))
                                    if fc in nmkcols
                                    else (u't.%s' % fc.sql_name())
                                )
                                for fc, uc in fkr.reference_map_frozen
                            ]
                            sql = ("""
SELECT *
FROM (
  SELECT %(fkr_cols)s
  FROM (SELECT %(icols)s FROM %(input_table)s i) i
  JOIN %(table)s t ON (%(keymatches)s)
  WHERE %(fkr_nonnull)s
  EXCEPT
  SELECT %(domain_key_cols)s FROM %(domain_table)s
) s
LIMIT 1""") % dict(
    table = parts['table'],
    input_table = parts['input_table'],
    icols = parts['icols'],
    keymatches = parts['keymatches'],
    fkr_cols = ','.join(fkr_cols),
    fkr_nonnull = ' AND '.join([ '%s IS NOT NULL' % c for c in fkr_cols ]),
    domain_table = fkr.unique.table.sql_name(dynauthz=True, access_type='update', alias='d', dynauthz_testfkr=fkr),
    domain_key_cols = ','.join([
        u'd.%s' % uc.sql_name()
        for fc, uc in fkr.reference_map_frozen
    ]),
)
                            #web.debug(sql)
                            cur.execute(sql)
                            if cur.rowcount > 0:
                                raise Forbidden(u'update access on foreign key reference %s' % fkr)

                    cur.execute(
                        preserialize(("""
UPDATE %(table)s t SET %(assigns)s FROM (
  SELECT %(icols)s FROM %(input_table)s i
) i
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
                # only check for insert rights if there are non-matching row keys
                cur.execute(("""
SELECT * FROM (
  SELECT %(icols)s FROM %(input_table)s i
""" + ("""
  JOIN (
    SELECT %(emkcols)s FROM %(input_table)s e
    EXCEPT SELECT %(mkcols)s FROM %(table)s e
  ) t ON (%(keymatches)s)""" if use_defaults is None else ""
) + ") i LIMIT 1") % parts
                )
                if cur.rowcount > 0:
                    self.table.enforce_right('insert', require_true=True)

                    for c in set(mkcols).union(set(nmkcols)):
                        c.enforce_data_right('insert', require_true=True)

                    for fkr in set().union(*[ set(fkrs) for fkrs in nonnull_fkrs.values() ]):
                        fkr.enforce_right('insert')
                        if fkr.has_right('insert') is None:
                            # need to enforce dynamic ACLs
                            fkr_cols = [
                                (u'i.%s' % fc.sql_name(nmkcol_aliases.get(fc)))
                                for fc, uc in fkr.reference_map_frozen
                            ]
                            sql = ("""
SELECT *
FROM (
  SELECT %(fkr_cols)s
  FROM (SELECT %(icols)s FROM %(input_table)s i) i
  WHERE %(fkr_nonnull)s
  EXCEPT
  SELECT %(domain_key_cols)s FROM %(domain_table)s
) s
LIMIT 1""") % dict(
    input_table = parts['input_table'],
    icols = parts['icols'],
    fkr_cols = ','.join(fkr_cols),
    fkr_nonnull = ' AND '.join([ '%s IS NOT NULL' % c for c in fkr_cols ]),
    domain_table = fkr.unique.table.sql_name(dynauthz=True, access_type='insert', alias='d', dynauthz_testfkr=fkr),
    domain_key_cols = ','.join([
        u'd.%s' % uc.sql_name()
        for fc, uc in fkr.reference_map_frozen
    ]),
)
                            #web.debug(sql)
                            cur.execute(sql)
                            if cur.rowcount > 0:
                                raise Forbidden(u'insert access on foreign key reference %s' % fkr)

                if not parts['cols']:
                    raise ConflictModel('Entity insertion requires at least one non-defaulting column.')

                parts.update(
                    icols = ','.join(
                        ['i.%s' % c.sql_name(mkcol_aliases.get(c)) for c in mkcols if use_defaults is None or c.name not in use_defaults]
                        + ['i.%s' % c.sql_name(nmkcol_aliases.get(c)) for c in nmkcols if use_defaults is None or c.name not in use_defaults]
                    ),
                    tcols = ','.join([
                        jsonfix2(c.sql_name(), c)
                        for c in (mkcols + nmkcols + extra_return_cols)
                    ])
                )
                cur.execute(
                    preserialize(("""
INSERT INTO %(table)s (%(cols)s)
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

                new_results = list(make_row_thunk(None, cur, content_type)())
                
                if content_type == 'application/json':
                    if not results:
                        pass
                    elif results == ['[]\n']:
                        results = []
                    elif new_results == ['[]\n']:
                        new_results = []
                    else:
                        # we need to splice together two serialized JSON arrays...
                        assert results[-1][-2:] == ']\n'
                        assert new_results[0][0] == '['
                        results[-1] = results[-1][:-2] # remote closing ']\n'
                        results.append(',\n') # add separator
                        new_results[0] = new_results[0][1:] # remove opening '['

                results.extend(new_results)

            for table in drop_tables:
                cur.execute("DROP TABLE %s" % sql_identifier(table))
        except psycopg2.IntegrityError, e:
            raise ConflictModel('Input data violates model. ' + e.pgerror)
            
        return results

class AnyPath (object):
    """Hierarchical ERM access to resources, a generic parent-class for concrete resources.

    """
    def sql_get(self, row_content_type='application/json', limit=None, prefix='', enforce_client=True):
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

    def _get_sort_element(self, key):
        raise NotImplementedError()

    def _get_sortvec(self):
        if self.sort is not None:
            sortvec, sort1, sort2 = sort_components(map(self._get_sort_element, self.sort), self.before is not None)
        else:
            sortvec, sort1, sort2 = (None, None, None)
        return sortvec, sort1, sort2

    def _get_page_sql(self, sortvec, output_type_overrides={}):
        if sortvec is not None:
            a, b, c = zip(*sortvec)
            if self.after is not None:
                page = 'WHERE %s' % page_filter_sql(a, b, c, self.after, is_before=False)
            elif self.before is not None:
                page = 'WHERE %s' % page_filter_sql(a, b, c, self.before, is_before=True)
            else:
                page = ''
        return page

    def _sql_get_agg_attributes(self, allow_extra=True):
        """Process attribute lists for aggregation APIs.
        """
        aggfunc_templates = dict(
            min='min(%(attr)s)', 
            max='max(%(attr)s)', 
            cnt='count(%(attr)s)', 
            cnt_d='count(DISTINCT %(attr)s)',
            array='array_to_json(array_agg(%(attr)s))::jsonb'
            )

        aggfunc_star_templates = dict(
            cnt='count(*)',
            array='array_to_json(array_agg(%(attr)s))::jsonb'
            )

        aggfunc_type_overrides = dict(
            cnt=int8_type,
            cnt_d=int8_type,
            array=jsonb_type,
        )

        aggregates = []
        extras = []
        output_type_overrides = {}

        for attribute, col, base in self.attributes:
            col.enforce_data_right('select')

            output_name = unicode(attribute.alias) if attribute.alias is not None else unicode(col.name)
            sql_attr = sql_identifier(output_name)

            if hasattr(attribute, 'aggfunc'):
                templates = col.is_star_column() and aggfunc_star_templates or aggfunc_templates

                if attribute.alias is None:
                    raise BadSyntax('Aggregated column %s must be given an alias.' % attribute)

                if unicode(attribute.aggfunc) not in templates:
                    raise BadSyntax('Unknown or unsupported aggregate function "%s" applied to column "%s".' % (attribute.aggfunc, col.name))

                aggregates.append((templates[unicode(attribute.aggfunc)] % dict(attr=sql_attr), sql_attr))

                if attribute.aggfunc in aggfunc_type_overrides:
                    output_type_overrides[output_name] = aggfunc_type_overrides[attribute.aggfunc]
            elif not allow_extra:
                raise BadSyntax('Attribute %s lacks an aggregate function.' % attribute)
            else:
                extras.append(sql_attr)

        return aggregates, extras, output_type_overrides

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

        # we defer base entity enforcement to allow insert-only use cases
        if hasattr(self, '_path'):
            # EntityPath
            self._path[0].table.enforce_right('select')
        elif hasattr(self, 'epath'):
            self.epath._path[0].table.enforce_right('select')

        sql = self.sql_get(row_content_type=content_type, limit=limit, dynauthz=True)

        #web.debug(sql)

        if output_file:
            # efficiently send results to file
            if content_type == 'text/csv':
                sql = "COPY (%s) TO STDOUT CSV DELIMITER ',' HEADER" % sql
            elif content_type == 'application/json':
                sql = "COPY (SELECT array_to_json(array_agg(row_to_json(q.*)), True)::text FROM (%s) q) TO STDOUT" % sql
            elif content_type == 'application/x-json-stream':
                sql = "COPY (SELECT row_to_json(q.*)::text FROM (%s) q) TO STDOUT" % sql
            else:
                raise NotImplementedError('content_type %s with output_file.write()' % content_type)

            cur.copy_expert(sql, output_file)

            return output_file

        else:
            # generate rows to caller
            if content_type == 'text/csv':
                # TODO implement and use row_to_csv() stored procedure?
                pass
            elif content_type == 'application/json':
                sql = "SELECT array_to_json(COALESCE(array_agg(row_to_json(q.*)), ARRAY[]::json[]), True)::text FROM (%s) q" % sql
            elif content_type == 'application/x-json-stream':
                sql = "SELECT row_to_json(q.*)::text FROM (%s) q" % sql
            elif content_type in [ dict, tuple ]:
                pass
            else:
                raise NotImplementedError('content_type %s' % content_type)

            cur.execute(sql)
            
            return make_row_thunk(None, cur, content_type)()

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
        cur.execute("""
SELECT GREATEST(
  (SELECT tlm.ts FROM _ermrest.table_last_modified tlm ORDER BY tlm.ts DESC LIMIT 1),
  (SELECT mlm.ts FROM _ermrest.model_last_modified mlm ORDER BY mlm.ts DESC LIMIT 1)
);
""")
        version = next(cur)
        return version

    def add_filter(self, filt, enforce_client=True):
        """Add a filter condition to the current path.

           Filters restrict the matched rows of the right-most table.
        """
        return self._path[self._context_index].add_filter(filt, enforce_client=enforce_client)

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
            
    def add_link(self, keyref, refop, ralias=None, lalias=None, outer_type=None, enforce_client=True):
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

        if enforce_client:
            rtable.enforce_right('select')

        assert self._context_index >= -1
        if self._context_index >= 0:
            rcontext = self._context_index
        else:
            rcontext = rpos - 1
        
        self._path.append( EntityElem(self, ralias, rtable, rpos, keyref, refop, lalias, rcontext, outer_type) )
        self._context_index = -1

        if ralias is not None:
            if ralias in self.aliases:
                raise BadData('Alias %s bound more than once.' % ralias)
            self.aliases[ralias] = rpos

    def _get_sort_element(self, key):
        table = self.current_entity_table()
        column = table.columns.get_enumerable(key.keyname)
        # select access was already enforced for enumerable output columns
        return (key.keyname, key.descending, column.type)

    def sql_get(self, selects=None, distinct_on=True, row_content_type='application/json', limit=None, dynauthz=None, access_type='select', prefix='', enforce_client=True, dynauthz_testcol=None):
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
        context_table = self._path[self._context_index].table
        context_pos = self.current_entity_position()

        if selects is None:
            # non-enumerable columns will be omitted from entity results
            for col in context_table.columns_in_order():
                if enforce_client:
                    col.enforce_data_right('select')
            selects = ", ".join([
                "%st%d.%s" % (prefix, context_pos, sql_identifier(col.name))
                for col in context_table.columns_in_order()
            ])

        if dynauthz_testcol is not None:
            assert context_table.columns[dynauthz_testcol.name] == dynauthz_testcol

        # choose a pkey that the client is allowed to use
        pkeys = [
            k
            for k, unique in context_table.uniques.items()
            if unique.has_right('select') or not enforce_client
        ]
        if pkeys:
            pkeys.sort(key=lambda k: len(k))
            shortest_pkey = context_table.uniques[pkeys[0]].columns
        else:
            shortest_pkey = context_table.columns_in_order()
            # check whether this meta-key is usable for client...
            for col in shortest_pkey:
                if enforce_client:
                    col.enforce_data_right('select')

        distinct_on_cols = [ 
            '%st%d.%s' % (prefix, context_pos, sql_identifier(c.name))
            for c in shortest_pkey
        ]

        tables = [
            elem.sql_table_elem(dynauthz=dynauthz, access_type=access_type, prefix=prefix)
            for elem in self._path[0:context_pos]
        ] + [
            # dynauthz_testcol may be None or an actual column here...
            self._path[context_pos].sql_table_elem(dynauthz=dynauthz, access_type=access_type, prefix=prefix, dynauthz_testcol=dynauthz_testcol)
        ] + [
            # this is usually empty list but might not if a URL path ends with a context reset
            elem.sql_table_elem(dynauthz=dynauthz, access_type=access_type, prefix=prefix)
            for elem in self._path[context_pos+1:]
        ]

        wheres = []
        for elem in self._path:
            wheres.extend( elem.sql_wheres(prefix=prefix) )

        if len(self._path) == 1:
            distinct_on = False
            
        sql = """
SELECT 
  %(distinct_on)s
  %(selects)s
FROM %(tables)s
%(where)s
""" % dict(distinct_on = distinct_on and ('DISTINCT ON (%s)' % ', '.join(distinct_on_cols)) or '',
           selects     = selects,
           tables      = ' '.join(tables),
           where       = wheres and ('WHERE ' + ' AND '.join(['(%s)' % w for w in wheres])) or ''
           )
	
	# This subquery is ugly and inefficient but necessary due to DISTINCT ON above
        sortvec, sort1, sort2 = self._get_sortvec()
        limit = 'LIMIT %d' % limit if limit is not None else ''
    	if sort1 is not None:
            page = self._get_page_sql(sortvec)
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
        table.enforce_right('delete')
        if not table.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % table)

        if table.has_right('delete') is None:
            # need to enforce dynamic ACLs
            cur.execute("SELECT True FROM (%s) s LIMIT 1" % self.sql_get(dynauthz=False, access_type='delete'))
            if cur.fetchone():
                raise Forbidden(u'delete access on one or more matching rows in table %s' % self.table)
        
        cur.execute("SELECT count(*) AS count FROM (%s) s" % self.sql_get())
        cnt = cur.fetchone()[0]
        if cnt == 0:
            raise NotFound('entities matching request path')
        notify_data_change(cur, table)
        cur.execute(self.sql_delete())

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

    def _get_sort_element(self, key):
        if key.keyname not in self.outputs:
            raise BadData('Sort key "%s" not among output columns.' % key.keyname)
        return (key.keyname, key.descending, self.output_types[key.keyname])

    def sql_get(self, split_sort=False, distinct_on=True, row_content_type='application/json', limit=None, dynauthz=None, access_type='select', prefix='', enforce_client=True):
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

            if hasattr(attribute, 'nbins'):
                if col.type.name not in {'int2', 'int4', 'int8', 'float', 'float4', 'float8', 'numeric', 'serial2', 'serial4', 'serial8', 'timestamptz', 'date'}:
                    raise ConflictModel('Binning not supported on column type %s.' % col.type)

                parts = {
                    'val':   "%s.%s" % (alias, col.sql_name()),
                    'nbins': sql_literal(attribute.nbins),
                    'minv':  col.type.sql_literal(str(attribute.minv)),
                    'maxv':  col.type.sql_literal(str(attribute.maxv)),
                }

                bexpr = lambda e: e
                if col.type.name in {'timestamptz', 'date'}:
                    # convert to float so width_bucket can handle it
                    bexpr = lambda e: "EXTRACT(EPOCH FROM %s)" % e

                parts['bucket'] = 'width_bucket(%(val)s, %(minv)s, %(maxv)s, %(nbins)s::int)' % {
                    'val': bexpr(parts['val']),
                    'minv': bexpr(parts['minv']),
                    'maxv': bexpr(parts['maxv']),
                    'nbins': parts['nbins'],
                }

                if col.type.name == 'date':
                    # date arithmetic produces integer when we wanted interval...
                    parts['bminv'] = "%(minv)s + '1 day'::interval * (%(maxv)s - %(minv)s) * (%(bucket)s - 1) / %(nbins)s::float4" % parts
                    parts['bmaxv'] = "%(minv)s + '1 day'::interval * (%(maxv)s - %(minv)s) * %(bucket)s       / %(nbins)s::float4" % parts
                else:
                    # most arithmetic remains within same type
                    parts['bminv'] = "%(minv)s + (%(maxv)s - %(minv)s) * (%(bucket)s - 1) / %(nbins)s::float4" % parts
                    parts['bmaxv'] = "%(minv)s + (%(maxv)s - %(minv)s) * %(bucket)s       / %(nbins)s::float4" % parts

                select = """
CASE
  WHEN %(bucket)s IS NULL
    THEN jsonb_build_array(NULL, NULL, NULL)
  WHEN %(bucket)s < 1::int
    THEN jsonb_build_array(%(bucket)s, NULL, %(minv)s)
  WHEN %(bucket)s > %(nbins)s::int
    THEN jsonb_build_array(%(bucket)s, %(maxv)s, NULL)
  ELSE   jsonb_build_array(%(bucket)s, %(bminv)s, %(bmaxv)s)
END
""" % parts
            elif hasattr(col, 'sql_name_with_talias'):
                select = col.sql_name_with_talias(alias, output=True)
            elif col is None and attribute is True:
                select = "True"
            else:
                select = "%s.%s" % (alias, col.sql_name())

            select = select

            if attribute is True and col is None:
                # short-circuit for dynacl decision output
                selects.append(select)
            elif attribute.alias is not None:
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

        # HACK: _get_sortvec() calls _get_sort_element() which looks at self.outputs and self.output_types
        self.outputs = outputs
        self.output_types = output_types
        sortvec, sort1, sort2 = self._get_sortvec()
        page = ''
        if sort1 is not None:
            page = self._get_page_sql(sortvec)

        selects = ', '.join(selects)

        limit = 'LIMIT %d' % limit if limit is not None else ''

        if split_sort:
            # let the caller compose the query and the sort clauses
            return (self.epath.sql_get(selects=selects, distinct_on=distinct_on, dynauthz=dynauthz, access_type=access_type, prefix=prefix, enforce_client=enforce_client), page, sort1, limit, sort2)
        else:
            sql = self.epath.sql_get(selects=selects, distinct_on=distinct_on, dynauthz=dynauthz, access_type=access_type, prefix=prefix, enforce_client=enforce_client)
                
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
        etable = self.epath.current_entity_table()
        etable.enforce_right('update')
        if etable.has_right('update') is None:
            # need to enforce dynamic ACLs
            cur.execute("SELECT True FROM (%s) s LIMIT 1" % self.epath.sql_get(dynauthz=False, access_type='update'))
            if cur.fetchone():
                raise Forbidden(u'update access on one or more matching rows in table %s' % etable)

        equery = self.epath.sql_get()
        nmkcols = set()

        # delete columns are named explicitly
        for attribute, col, base in self.attributes:
            if base == self.epath:
                # column in final entity path element
                col.enforce_data_right('update')
                if col.has_data_right('update') is None and col.dynauthz_restricted('update'):
                    # need to enforce dynamic ACLs
                    cur.execute("SELECT True FROM (%s) s LIMIT 1" % self.epath.sql_get(access_type='update', dynauthz_testcol=col))
                    if cur.fetchone():
                        raise Forbidden(u'update access on column %s for one or more rows' % col)
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
            
    def _get_sort_element(self, key):
        if key.keyname in self.output_type_overrides:
            otype = self.output_type_overrides[key.keyname]
        elif key.keyname in self.apath.outputs:
            otype = self.apath.output_types[key.keyname]
        else:
            raise BadData('Sort key "%s" not among output columns.' % key.keyname)
        return (key.keyname, key.descending, otype)

    def sql_get(self, row_content_type='application/json', limit=None, dynauthz=None, access_type='select', prefix='', enforce_client=True):
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
        self.apath = apath
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

        asql, page, sort1, limit, sort2 = apath.sql_get(split_sort=True, distinct_on=False, limit=limit, dynauthz=dynauthz, access_type=access_type, prefix=prefix, enforce_client=enforce_client)
        aggregates, extras, self.output_type_overrides = self._sql_get_agg_attributes()

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
            sortvec, sort1, sort2 = self._get_sortvec() # HACK: this gets output_type_overrides from side-effects above...
            page = self._get_page_sql(sortvec)
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

            if hasattr(attribute, 'nbins'):
                raise BadSyntax('Binning of column %s not allowed in PUT.' % attribute)

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
        
    def sql_get(self, row_content_type='application/json', limit=None, dynauthz=None, prefix='', enforce_client=True):
        """Generate SQL query to get the resources described by this apath.

        """
        apath = AttributePath(self.epath, self.attributes)
        aggregates, extras, output_type_overrides = self._sql_get_agg_attributes(allow_extra=False)
        asql, page, sort1, limit, sort2 = apath.sql_get(split_sort=True, distinct_on=False, dynauthz=dynauthz, prefix=prefix, enforce_client=enforce_client)

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

       
class TextFacet (AnyPath):

    def __init__(self, catalog, model, pattern):
        self.catalog = catalog
        self._model = model
        self.pattern = pattern

    def add_sort(self, sort):
        """Dummy interface."""
        pass

    def add_paging(self, after, before):
        """Dummy interface."""
        pass
            
    def columns(self):
        """Generate (schema, table, column) set."""
        def get_policy(policy, name):
            policy = policy if policy else {}
            if policy is True:
                return policy
            elif name in policy:
                return policy[name]
            else:
                return {}

        policy = web.ctx.ermrest_config.get('textfacet_policy', False)
            
        for sname, schema in self._model.schemas.items():
            if not schema.has_right('enumerate'):
                continue
            s_policy = get_policy(policy, sname)
            if s_policy:
                for tname, table in schema.tables.items():
                    if not table.has_right('select'):
                        continue
                    t_policy = get_policy(s_policy, tname)
                    if t_policy:
                        for cname, column in table.columns.items():
                            if not column.has_data_right('select'):
                                continue
                            c_policy = get_policy(t_policy, cname)
                            if c_policy:
                                yield (sname, tname, column)

    def get_data_version(self, cur):
        """Get data version txid considering all tables in catalog."""
        cur.execute("""
SELECT tlm.ts FROM _ermrest.table_last_modified tlm ORDER BY tlm.ts DESC LIMIT 1;
""")
        version = next(cur)[0]
        return max(version, self._model.version)

    def sql_get(self, row_content_type='application/json', limit=None, dynauthz=None, prefix='', enforce_client=True):
        queries = [
            # column ~* pattern is ciregexp...
            """(SELECT %(stext)s::text AS "schema", %(ttext)s::text AS "table", %(ctext)s::text AS "column" FROM %(sid)s.%(tid)s WHERE _ermrest.astext(%(cid)s) ~* %(pattern)s LIMIT 1)""" % dict(
                stext=sql_literal(sname),
                ttext=sql_literal(tname),
                ctext=sql_literal(column.name),
                pattern=sql_literal(unicode(self.pattern)),
                sid=sql_identifier(sname),
                tid=sql_identifier(tname),
                cid=sql_identifier(column.name)
            )
            for sname, tname, column in self.columns()
        ] + [
            """(SELECT 's' AS "schema", 't' AS "table", 'c' AS "column" WHERE false)"""
        ]
        return ' UNION ALL '.join(queries)
                    
