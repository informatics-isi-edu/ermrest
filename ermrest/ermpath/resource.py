
# 
# Copyright 2013-2023 University of Southern California
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
import csv
import json
import re
import datetime
from datetime import timezone
from webauthn2.util import deriva_ctx, deriva_debug

from psycopg2._json import JSON_OID, JSONB_OID

from ..exception import *
from ..util import sql_identifier, sql_literal, random_name
from ..model.type import text_type, aggfuncs
from ..model import predicate

class _FakeEntityElem (object):
    def __init__(self, pos):
        self.pos = pos

class _NullEntityElem (object):
    def sql_table_elem(self, dynauthz=None, access_type='select', prefix='', dynauthz_testcol=None):
        return ''

    def sql_wheres(self, prefix=''):
        return []

def _set_statement_timeout(cur):
    """Try to set a sensible timeout for the next statement we will execute."""
    try:
        request_timeout_s = float(deriva_ctx.ermrest_config.get('request_timeout_s', '55'))
        elapsed = datetime.datetime.now(timezone.utc) - deriva_ctx.ermrest_start_time
        remaining_time_s = request_timeout_s - elapsed.total_seconds()
        if remaining_time_s < 0:
            raise rest.BadRequest('Query run time limit exceeded.')
        timeout_ms = int(1000.0 * max(remaining_time_s, 0.001))
        cur.execute("SELECT set_config('statement_timeout', %s, true);" % sql_literal(timeout_ms))
    except Exception as e:
        deriva_debug(e)
        pass

def get_dynacl_clauses(src, access_type, prefix, dynacls=None):
    if dynacls is None:
        dynacls = src.dynacls

    if src.has_right(access_type) is None:
        clauses = []

        # we have to guard against prefixes not matching our t#t#... idiom
        # for special case optimizations below
        prefix_ok = re.match('^(t[0-9]+)+$', prefix)
        prefix_positions = prefix.split('t')
        fake_prefix = 't'.join(prefix_positions[0:-1])

        for binding in dynacls.values():
            if binding is False:
                continue
            if not binding.inscope(access_type):
                continue

            aclpath, col, ctype = binding._compile_projection()
            aclpath.epath.add_filter(predicate.AclPredicate(binding, col))
            authzpath = AttributePath(aclpath.epath, [ (True, None, aclpath.epath) ])

            generic_clause = authzpath.sql_get(limit=1, distinct_on=False, prefix=prefix, enforce_client=False)
            redundant_base_elem = aclpath.epath._path[0]
            assert isinstance(redundant_base_elem.filters[0], predicate.AclBasePredicate)

            if prefix_ok and len(aclpath.epath._path) == 1:
                # mangle this to simple SQL predicates w/o subquery
                assert isinstance(_filters[-1], predicate.AclPredicate)
                del redundant_base_elem.filters[0]

                fake_base_elem = _FakeEntityElem(int(prefix_positions[-1]))
                def mangle(pred):
                    if isinstance(pred, (predicate.Predicate, predicate.AclPredicate)):
                        pred.left_elem = fake_base_elem
                    elif isinstance(pred, predicate.Negation):
                        mangle(pred.predicate)
                    elif isinstance(pred, (predicate.Disjunction, predicate.Conjunction)):
                        for p in pred:
                            mangle(p)

                for f in redundant_base_elem.filters:
                    mangle(f)

                clauses.append(
                    ' AND '.join([
                        f.sql_where(None, fake_base_elem, fake_prefix)
                        for f in redundant_base_elem.filters
                    ])
                )
            elif prefix_ok and len(redundant_base_elem.filters) == 1 \
                 and aclpath.epath._path[1].context_pos == 0 \
                 and len([ e for e in aclpath.epath._path if e.context_pos == 0 ]) == 1:
                # mangle this to avoid unnecessary repetition of base table in subquery
                joined_elem = aclpath.epath._path[1]
                joined_elem.add_filter(predicate.AclBaseJoinPredicate(joined_elem.refop))
                joined_elem.refop = None
                aclpath.epath._path[0] = _NullEntityElem()

                clause = authzpath.sql_get(limit=1, distinct_on=False, prefix=prefix, enforce_client=False)
                clauses.append(clause)
            else:
                # fall back on less-optimized code
                clauses.append(generic_clause)

        if not clauses:
            clauses = ['False']
    else:
        clauses = ['True']

    return clauses

def current_request_snaptime(cur):
    """The snaptime produced by this mutation request."""
    cur.execute("""
SELECT now();
""")
    return cur.fetchone()[0]

def current_catalog_snaptime(cur, encode=False):
    """The whole catalog snaptime is the latest transaction of any type.

       Encode:
         False (default): return raw snaptime
         True: encode as a simple URL-safe string as time since EPOCH
    """
    cur.execute("""
SELECT %(prefix)s GREATEST(
  (SELECT ts FROM _ermrest.model_last_modified ORDER BY ts DESC LIMIT 1),
  (SELECT ts FROM _ermrest.table_last_modified ORDER BY ts DESC LIMIT 1)
) %(suffix)s;
""" % {
    'prefix': '_ermrest.tstzencode(' if encode else '',
    'suffix': ')' if encode else '',
})
    return cur.fetchone()[0]

def current_model_snaptime(cur):
    """The current model snaptime is the most recent change to the live model."""
    cur.execute("""
SELECT ts FROM _ermrest.model_last_modified ORDER BY ts DESC LIMIT 1;
""")
    return cur.fetchone()[0]

def normalized_history_snaptime(cur, snapwhen, encoded=True):
    """Clamp snapwhen to the latest historical snapshot which precedes it.

       Encoded:
         True (default): snapwhen should be a float8 input string as time since EPOCH
         False: snapwhen should be a timestamptz input string
    """
    cur.execute("""
SELECT GREATEST(
  (SELECT ts FROM _ermrest.model_modified WHERE ts <= %(when)s::timestamptz ORDER BY ts DESC LIMIT 1),
  (SELECT ts FROM _ermrest.table_modified WHERE ts <= %(when)s::timestamptz ORDER BY ts DESC LIMIT 1)
);
""" % {
    'when': ("_ermrest.tstzdecode(%s)" % sql_literal(snapwhen)) if encoded else sql_literal(snapwhen)
})
    when2 = cur.fetchone()[0]
    if when2 is None:
        raise ConflictData('Requested catalog revision "%s" is prior to any known revision.' % snapwhen)
    return when2

def current_history_amendver(cur, snapwhen):
    cur.execute("""
SELECT GREATEST(
  %(when)s::timestamptz,
  (SELECT ts FROM _ermrest.catalog_amended WHERE during @> %(when)s::timestamptz ORDER BY ts DESC LIMIT 1)
);
""" % {
    'when': sql_literal(snapwhen)
})
    return cur.fetchone()[0]

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
            _set_statement_timeout(cur)
            cur.execute("DROP TABLE %s" % sql_identifier(table))

        #if conn is not None:
        #    conn.commit()
        
    return row_thunk

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
        # cover non-null/non-null total orderings
        term = '%(field)s %(op)s %(boundary)s' % {
            'field': sql_identifier(keynames[0]),
            'op': { # (descending, is_before)
                (True,  True):  '>', # field is before boundary descending
                (True,  False): '<', # field is after boundary descending
                (False, True):  '<', # field is before boundary ascending
                (False, False): '>', # field is after boundary ascending
            }[(descendings[0], is_before)],
            'boundary': boundary[0].sql_literal(types[0]) if not boundary[0].is_null() else 'NULL',
        }

        # cover mixed null/non-null total orderings
        nulltests = { # (nullbound, descending, is_before)
            (True,  True,  False): 'IS NOT NULL', # field is after null boundary descending
            (False, True,  True):  'IS NULL',     # field is before non-null boundary descending
            (True,  False, True):  'IS NOT NULL', # field is before null boundary ascending
            (False, False, False): 'IS NULL',     # field is after non-null boundary ascending
        }
        ntestkey = (boundary[0].is_null(), descendings[0], is_before)
        if ntestkey in nulltests:
            term += ' OR %(field)s %(ntest)s' % {
                'field': sql_identifier(keynames[0]),
                'ntest': nulltests[ntestkey],
            }

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
    
    direction = { True: 'DESC NULLS FIRST', False: 'ASC NULLS LAST' }
    direction_revs = { False: 'DESC NULLS FIRST', True: 'ASC NULLS LAST' }

    for i in range(len(sortvec)):
        keyname = sortvec[i][0]
        descending = sortvec[i][1]
        keyname = sql_identifier(keyname)
        norm_parts.append( '%s %s' % (keyname, direction.get(descending, '')) )
        revs_parts.append( '%s %s' % (keyname, direction_revs.get(descending, '')) )

    norm_parts = ', '.join(norm_parts)
    revs_parts = ', '.join(revs_parts)

    if is_before:
        return (sortvec, revs_parts, norm_parts)
    else:
        return (sortvec, norm_parts, None)

# used in several functions below
system_colnames = {'RID','RCT','RMT','RCB','RMB'}

def _create_temp_input_tables(cur, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, in_content_type, drop_tables=None, use_defaults=None):
    if use_defaults is None:
        use_defaults = set()
    input_table = random_name("input_data_")
    input_json_table = None
    cur.execute(
        "CREATE TEMPORARY TABLE %s (%s)" % (
            sql_identifier(input_table),
            ','.join(
                [
                    c.input_ddl(mkcol_aliases.get(c), c not in use_defaults)
                    for c in mkcols
                ] + [
                    c.input_ddl(nmkcol_aliases.get(c), c not in use_defaults)
                    for c in nmkcols
                ]
            )
        )
    )
    if drop_tables is not None:
        drop_tables.append(input_table)
    if in_content_type in [ 'application/x-json-stream' ]:
        input_json_table = random_name("input_json_")
        cur.execute( "CREATE TEMPORARY TABLE %s (j json)" % sql_identifier(input_json_table))
        if drop_tables is not None:
            drop_tables.append(input_json_table)
    return input_table, input_json_table

def _build_json_projections(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults=None):
    """Build up intermediate SQL representations of each JSON record as field lists."""
    if use_defaults is None:
        use_defaults = set()

    def json_fields(col_name, c):
        sql_type = c.type.sql(basic_storage=True)

        json_col = c.sql_name(col_name)

        if c.type.is_array:
            # extract field as JSON and transform to array
            # since PostgreSQL json_to_recordset fails for native array extraction...
            # if ELSE clause hits a non-array, we'll have a 400 Bad Request error as before
            json_proj = """
(CASE
 WHEN json_typeof(j->%(field)s) = 'null'
   THEN NULL::%(type)s[]
 ELSE
   COALESCE((SELECT array_agg(x::%(type)s) FROM json_array_elements_text(j->%(field)s) s (x)), ARRAY[]::%(type)s[])
 END) AS %(alias)s
""" % {
    'type': c.type.base_type.sql(basic_storage=True),
    'field': sql_literal(col_name),
    'alias': c.sql_name(col_name),
}
        elif sql_type in ['json', 'jsonb']:
            json_proj = "(j->%s)::%s AS %s" % (
                sql_literal(col_name),
                sql_type,
                c.sql_name(col_name)
            )
        else:
            json_proj = "(j->>%s)::%s AS %s" % (
                sql_literal(col_name),
                sql_type,
                c.sql_name(col_name)
            )

        return json_col, json_proj

    parts = [
        json_fields(mkcol_aliases.get(c, c.name), c)
        for c in mkcols if c not in use_defaults
    ] + [
        json_fields(nmkcol_aliases.get(c, c.name), c)
        for c in nmkcols if c not in use_defaults
    ]

    # split back into json_cols, json_projection lists
    return zip(*parts)

def _load_input_data_csv(cur, input_data, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults=None):
    if use_defaults is None:
        use_defaults = set()

    hdr = next(csv.reader([ input_data.readline().decode() ]))

    inputcol_names = set(
        [ mkcol_aliases.get(c, c.name) for c in mkcols ]
        + [ nmkcol_aliases.get(c, c.name) for c in nmkcols ]
    )
    csvcol_names = set()
    csvcol_names_ordered = []
    for cn in hdr:
        try:
            inputcol_names.remove(cn)
            csvcol_names.add(cn)
            csvcol_names_ordered.append(cn)
        except KeyError:
            if cn in csvcol_names:
                raise BadData('CSV column %s appears more than once.' % cn)
            else:
                raise ConflictModel('CSV column %s not recognized.' % cn)

    inputcol_names = set(inputcol_names).difference(set([ c.name for c in use_defaults ]))
    if inputcol_names:
        raise BadData('Missing expected CSV column%s: %s.' % (
            ('' if len(inputcol_names) == 0 else 's'),
            ', '.join([ sql_identifier(cn) for cn in inputcol_names ])
        ))

    try:
        cur.copy_expert(u"""
COPY %(input_table)s (%(cols)s)
FROM STDIN WITH (
    FORMAT csv,
    HEADER false,
    DELIMITER ',',
    QUOTE '"'
)""" % {
    'input_table': sql_identifier(input_table),
    'cols': ','.join([ sql_identifier(cn) for cn in csvcol_names_ordered ])
},
            input_data
        )
    except psycopg2.DataError as e:
        raise BadData(u'Bad CSV input. ' + e.pgerror)

def _load_input_data_json(cur, input_data, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults=None):
    if use_defaults is None:
        use_defaults = set()

    json_cols, json_projection = _build_json_projections(
        mkcols, nmkcols,
        mkcol_aliases, nmkcol_aliases
    )
    buf = input_data.read().decode('utf8')
    try:
        _set_statement_timeout(cur)
        cur.execute(u"""
INSERT INTO %(input_table)s (%(cols)s)
SELECT %(cols)s
FROM (
  SELECT %(json_projection)s
  FROM json_array_elements( %(input)s::json )
    AS rs ( j )
) s
""" % {
    'input_table': sql_identifier(input_table),
    'cols': u','.join(json_cols),
    'input': text_type.sql_literal(buf),
    'json_projection': ','.join(json_projection)
}
        )
    except psycopg2.DataError as e:
        raise BadData('Bad JSON array input. ' + e.pgerror)

def _load_input_data_json_stream(cur, input_data, input_table, input_json_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults=None):
    json_cols, json_projection = _build_json_projections(
        mkcols, nmkcols,
        mkcol_aliases, nmkcol_aliases
    )
    try:
        cur.copy_expert( "COPY %s (j) FROM STDIN" % sql_identifier(input_json_table), input_data )
        _set_statement_timeout(cur)
        cur.execute(u"""
INSERT INTO %(input_table)s (%(cols)s)
SELECT %(cols)s
FROM (
  SELECT %(json_projection)s
  FROM %(input_json)s i
) s
""" % {
    'input_table': sql_identifier(input_table),
    'input_json': sql_identifier(input_json_table),
    'cols': ','.join(json_cols),
    'json_projection': ','.join(json_projection),
}
        )
    except psycopg2.DataError as e:
        raise BadData('Bad JSON stream input. ' + e.pgerror)

def _load_input_data(cur, input_data, input_table, input_json_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, in_content_type, use_defaults=None):
    if in_content_type == 'text/csv':
        _load_input_data_csv(cur, input_data, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults)
    elif in_content_type == 'application/json':
        _load_input_data_json(cur, input_data, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults)
    elif in_content_type == 'application/x-json-stream':
        _load_input_data_json_stream(cur, input_data, input_table, input_json_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults)
    else:
        raise UnsupportedMediaType('%s input not supported' % in_content_type)

def jsonfix1(sql, c):
    return '%s::jsonb' % sql if c.type.sql(basic_storage=True) == 'json' else sql

def jsonfix2(sql, c):
    return '%s::json' % sql if c.type.sql(basic_storage=True) == 'json' else sql

def keymatch(c, aliases, fix1=False):
    parts = {
        't': c.sql_name(),
        'i': c.sql_name(aliases.get(c)),
    }
    if fix1:
        parts['i'] = jsonfix1(parts['i'], c)
        parts['t'] = jsonfix1(parts['t'], c)
    sql = 't.%(t)s = i.%(i)s' % parts
    if c.nullok:
        sql += ' OR (t.%(t)s IS NULL AND i.%(i)s IS NULL)' % parts
    return '(%s)' % sql

def preserialize(sql, content_type):
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
    return sql

def _analyze_input_table(cur, input_table, mkcols, mkcol_aliases):
    """Index and analyze input_table ensuring mkcols uniqueness."""
    parts = {
        'input_table': sql_identifier(input_table),
        'mkcols_idx': ','.join([ c.sql_name(mkcol_aliases.get(c)) for c in mkcols ][0:32]),
    }
    if len(mkcols) > 0:
        try:
            _set_statement_timeout(cur)
            cur.execute("CREATE UNIQUE INDEX ON %(input_table)s (%(mkcols_idx)s);" % parts)
        except psycopg2.IntegrityError as e:
            raise BadData(u'Multiple input rows share the same unique key information.')

    _set_statement_timeout(cur)
    cur.execute("ANALYZE %s;" % parts['input_table'])

    if len(mkcols) > 32:
        # index is truncated, so check for collisions via brute-force
        _set_statement_timeout(cur)
        cur.execute("""
SELECT True AS is_duplicate
FROM %(input_table)s
GROUP BY %(mkcols_idx)s
HAVING count(*) > 1
LIMIT 1;
""" % parts
        )
        for row in cur:
            raise BadData(u'Multiple input rows share the same unique key information.')

def _table_col_fkrs(table):
    col_fkrs = dict()
    for fk in table.fkeys.values():
        for c in fk.columns:
            if c not in col_fkrs:
                col_fkrs[c] = set(fk.references.values())
            else:
                col_fkrs[c].update(set(fk.references.values()))
    return col_fkrs

def _affected_fkrs(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults=None):
    if use_defaults is None:
        use_defaults = set()
    # 1. accumulate all fkrs into a map  { c: {fkr,...} }
    col_fkrs = _table_col_fkrs(table)
    # 2. prune columns from map if column is not affected by request or no input data IS NOT NULL
    for c in list(col_fkrs):
        if c in mkcols and c not in use_defaults:
            alias = mkcol_aliases.get(c)
        elif c in nmkcols and c not in use_defaults:
            alias = nmkcol_aliases.get(c)
        else:
            # prune this unaffected column
            del col_fkrs[c]
            continue
        _set_statement_timeout(cur)
        cur.execute("SELECT True FROM %s WHERE %s IS NOT NULL LIMIT 1" % (sql_identifier(input_table), c.sql_name(alias)))
        row = cur.fetchone()
        if row and row[0]:
            pass
        else:
            del col_fkrs[c]
    # 3. make mkcol and nmkcol specific maps of affected columns (same fkr may appear in both for composites fkrs)
    mkcol_fkrs = {
        c: fkrs
        for c, fkrs in col_fkrs.items()
        if c in mkcols and c not in use_defaults
    }
    nmkcol_fkrs = {
        c: fkrs
        for c, fkrs in col_fkrs.items()
        if c in nmkcols and c not in use_defaults
    }
    return mkcol_fkrs, nmkcol_fkrs

def _enforce_table_access_static(cur, access, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, require_tc=False, use_defaults=None):
    if use_defaults is None:
        use_defaults = set()
    table.enforce_right(access, require_true=require_tc)
    for c in nmkcols:
        if c not in use_defaults:
            c.enforce_data_right(access, require_true=require_tc)
    mkcol_fkrs, nmkcol_fkrs = _affected_fkrs(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)
    for fkr in set().union(*[ set(fkrs) for fkrs in nmkcol_fkrs.values() ]):
        fkr.enforce_right(access)
    if access == 'insert':
        for fkr in set().union(*[ set(fkrs) for fkrs in mkcol_fkrs.values() ]):
            fkr.enforce_right(access)

def _enforce_table_update_static(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases):
    _enforce_table_access_static(cur, 'update', table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)

def _enforce_table_insert_static(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults=None):
    if use_defaults is None:
        use_defaults = set()
    _enforce_table_access_static(cur, 'insert', table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, require_tc=True, use_defaults=use_defaults)
    for c in mkcols:
        if c not in use_defaults:
            c.enforce_data_right('insert', require_true=True)

def _enforce_table_upsert_static(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases):
    """Raise access error or return will_insert boolean determination from input_table."""
    if nmkcols:
        # treat as static update and conditionally check for static insert rights below...
        _enforce_table_update_static(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)
    else:
        # treat as static insert since no update is possible
        _enforce_table_insert_static(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)

    if nmkcols:
        _set_statement_timeout(cur)
        cur.execute("""
SELECT %(icols)s
FROM %(input_table)s i
LEFT OUTER JOIN %(table)s t ON (%(keymatches)s)
WHERE COALESCE(NOT (%(keymatches)s), True)
LIMIT 1""" % {
    'input_table': sql_identifier(input_table),
    'table': table.sql_name(),
    'icols': _icols(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases),
    'keymatches': _keymatches(mkcols, mkcol_aliases),
}
        )
        if cur.rowcount > 0:
            _enforce_table_insert_static(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)
            return True
        else:
            return False
    else:
        return True

def _keymatches(mkcols, mkcol_aliases):
    return u' AND '.join([ keymatch(c, mkcol_aliases) for c in mkcols ])

def _cols(mkcols, nmkcols, use_defaults):
    return ','.join([ c.sql_name() for c in (mkcols + nmkcols) if c not in use_defaults ])

def _icols(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults=None):
    if use_defaults is None:
        use_defaults = set()
    return ','.join(
        [jsonfix1('i.%s' % c.sql_name(mkcol_aliases.get(c)), c) for c in mkcols if c not in use_defaults]
        + [jsonfix1('i.%s' % c.sql_name(nmkcol_aliases.get(c)), c) for c in nmkcols if c not in use_defaults]
    )

def _tcols(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases):
    return u','.join(
        [ u'i.%s AS %s' % (jsonfix2(c.sql_name(mkcol_aliases.get(c)), c), c.sql_name(mkcol_aliases.get(c))) for c in mkcols ]
        + [ u't.%s AS %s' % (jsonfix2(c.sql_name(), c), c.sql_name(nmkcol_aliases.get(c))) for c in nmkcols ]
    )

def _enforce_input_exists(cur, input_table, table, mkcols, mkcol_aliases):
    _set_statement_timeout(cur)
    cur.execute("""
SELECT *
FROM %(input_table)s i
LEFT OUTER JOIN %(table)s t ON (%(keymatches)s)
WHERE NOT (%(keymatches)s)
LIMIT 1;""" % {
    'input_table': sql_identifier(input_table),
    'table': table.sql_name(),
    'keymatches': _keymatches(mkcols, mkcol_aliases),
}
    )
    for row in cur:
        raise ConflictData('Input row key (%s) does not match existing entity.' % row)

def _enforce_table_insert_dynamic(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults=None):
    if use_defaults is None:
        use_defaults = set()
    input_table_sql = sql_identifier(input_table)
    icols = _icols(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults)

    mkcol_fkrs, nmkcol_fkrs = _affected_fkrs(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)
    for fkr in set().union(*[ set(fkrs) for fkrs in list(nmkcol_fkrs.values()) + list(mkcol_fkrs.values()) ]):
        if fkr.has_right('insert') is not None:
            continue
        fkr_cols = [
            (
                (u'i.%s' % fc.sql_name(nmkcol_aliases.get(fc)))
                if fc in nmkcols or fc in mkcols
                else (u't.%s' % fc.sql_name())
            )
            for fc, uc in fkr.reference_map_frozen
        ]
        _set_statement_timeout(cur)
        cur.execute(("""
SELECT *
FROM (
  SELECT %(fkr_cols)s
  FROM (SELECT %(icols)s FROM %(input_table)s i) i
  WHERE %(fkr_nonnull)s
  EXCEPT
  SELECT %(domain_key_cols)s FROM %(domain_table)s
) s
LIMIT 1""") % {
    'input_table': input_table_sql,
    'fkr_nonnull': ' AND '.join([ '%s IS NOT NULL' % c for c in fkr_cols ]),
    'fkr_cols': ','.join(fkr_cols),
    'icols': icols,
    'domain_table': fkr.unique.table.sql_name(dynauthz=True, access_type='insert', alias='d', dynauthz_testfkr=fkr),
    'domain_key_cols': ','.join([ u'd.%s' % uc.sql_name() for fc, uc in fkr.reference_map_frozen ]),
    }
        )
        if cur.rowcount > 0:
            raise Forbidden(u'insert access on foreign key reference %s' % fkr)

def _enforce_table_update_dynamic(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases):
    input_table_sql = sql_identifier(input_table)
    keymatches = _keymatches(mkcols, mkcol_aliases)
    icols = _icols(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)

    if table.has_right('update') is None:
        _set_statement_timeout(cur)
        cur.execute(("""
SELECT i.*
FROM %(table)s
JOIN (
  SELECT %(icols)s FROM %(input_table)s i
) i
ON (%(keymatches)s)
LIMIT 1""") % {
    'table': table.sql_name(dynauthz=False, access_type='update', alias="t"),
    'input_table': input_table_sql,
    'keymatches': keymatches,
    'icols': icols,
}
    )
        if cur.rowcount > 0:
            raise Forbidden(u'update access on one or more rows in table %s' % table)

    for c in nmkcols:
        if c.has_data_right('update') is not None:
            continue
        if not c.dynauthz_restricted('update'):
            continue
        _set_statement_timeout(cur)
        cur.execute(("""
SELECT i.*
FROM %(table)s
JOIN (
  SELECT %(icols)s FROM %(input_table)s i
) i
ON (%(keymatches)s)
LIMIT 1""") % {
    'table': table.sql_name(access_type='update', alias="t", dynauthz_testcol=c),
    'input_table': input_table_sql,
    'keymatches': keymatches,
    'icols': icols,
}
        )
        if cur.rowcount > 0:
            raise Forbidden(u'update access on column %s for one or more rows' % c)

    mkcol_fkrs, nmkcol_fkrs = _affected_fkrs(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)
    for fkr in set().union(*[ set(fkrs) for fkrs in nmkcol_fkrs.values() ]):
        if fkr.has_right('update') is not None:
            continue
        fkr_cols = [
            (
                (u'i.%s' % fc.sql_name(nmkcol_aliases.get(fc)))
                if fc in nmkcols
                else (u't.%s' % fc.sql_name())
            )
            for fc, uc in fkr.reference_map_frozen
        ]
        _set_statement_timeout(cur)
        cur.execute(("""
SELECT *
FROM (
  SELECT %(fkr_cols)s
  FROM (SELECT %(icols)s FROM %(input_table)s i) i
  JOIN %(table)s t ON (%(keymatches)s)
  WHERE %(fkr_nonnull)s
  EXCEPT
  SELECT %(domain_key_cols)s FROM %(domain_table)s
) s
LIMIT 1""") % {
    'table': table.sql_name(),
    'input_table': input_table_sql,
    'keymatches': keymatches,
    'fkr_nonnull': ' AND '.join([ '%s IS NOT NULL' % c for c in fkr_cols ]),
    'fkr_cols': ','.join(fkr_cols),
    'icols': icols,
    'domain_table': fkr.unique.table.sql_name(dynauthz=True, access_type='update', alias='d', dynauthz_testfkr=fkr),
    'domain_key_cols': ','.join([ u'd.%s' % uc.sql_name() for fc, uc in fkr.reference_map_frozen ]),
    }
        )
        if cur.rowcount > 0:
            raise Forbidden(u'update access on foreign key reference %s' % fkr)

def _enforce_table_upsert_dynamic(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, will_insert):
    if nmkcols:
        _enforce_table_update_dynamic(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)

    if will_insert:
        _enforce_table_insert_dynamic(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases)

def _perform_table_update(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, content_type):
    _set_statement_timeout(cur)
    cur.execute(
        preserialize("""
UPDATE %(table)s t SET %(assigns)s FROM (
  SELECT %(icols)s FROM %(input_table)s i
) i
WHERE %(keymatches)s
RETURNING %(tcols)s""" % {
    'table': table.sql_name(),
    'input_table': sql_identifier(input_table),
    'keymatches': _keymatches(mkcols, mkcol_aliases),
    'assigns': u','.join([
        u"%s = i.%s " % ( c.sql_name(), jsonfix2(c.sql_name(nmkcol_aliases.get(c)), c) )
        for c in nmkcols
    ] + [
        # add these metadata maintenance tasks.  if they are in nmkcols already we'll abort with Forbidden.
        u"%s = DEFAULT " % table.columns[cname].sql_name()
        for cname in {'RMT','RMB'}
        if cname in table.columns
    ]),
    'icols': _icols(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases),
    'tcols': _tcols(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases),
},
                     content_type
        )
    )
    return list(make_row_thunk(None, cur, content_type)())

def _perform_table_insert(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, content_type, use_defaults, extra_return_cols, only_nonmatch=False):
    _set_statement_timeout(cur)
    cur.execute(
        preserialize(("""
INSERT INTO %(table)s (%(cols)s)
SELECT %(icols)s FROM %(input_table)s i
""" + ("""
ON CONFLICT DO NOTHING
""" if only_nonmatch else "") + """
RETURNING %(rcols)s""") % {
    'table': table.sql_name(),
    'input_table': sql_identifier(input_table),
    'cols': _cols(mkcols, nmkcols, use_defaults),
    'icols': _icols(mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, use_defaults),
    'rcols': ','.join([
        c.sql_name()
        for c in (mkcols + nmkcols + extra_return_cols)
    ]),
},
                     content_type
        )
    )
    results = list(make_row_thunk(None, cur, content_type)())
    if 'RID' in table.columns and table.columns['RID'] not in use_defaults:
        # try to avoid RID sequence conflicts when users insert values
        _set_statement_timeout(cur)
        cur.execute("""
SELECT
  max(_ermrest.urlb32_decode("RID")),
  nextval('_ermrest.rid_seq')
FROM %(table)s
""" % {
    'table': table.sql_name(),
}
        )
        max_stored, next_issued = cur.fetchone()
        if max_stored > next_issued:
            _set_statement_timeout(cur)
            cur.execute("""
SELECT setval('_ermrest.rid_seq', %(newval)s)
""" % {
    'newval': sql_literal(max_stored),
}
            )
    return results

def _perform_table_upsert(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, content_type, use_defaults, extra_return_cols):
    results1 = _perform_table_update(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, content_type)
    results2 = _perform_table_insert(cur, table, input_table, mkcols, nmkcols, mkcol_aliases, nmkcol_aliases, content_type, use_defaults, extra_return_cols, only_nonmatch=True)
    return results1, results2

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
        s = str(self.table)

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
            s += ' WHERE ' + ' AND '.join([ str(f) for f in self.filters ])

        return s

    def __repr__(self):
        return '<ermrest.ermpath.EntityElem %s>' % self

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
        if self.refop is None:
            return tsql
        elif access_type == 'select' \
             and self.table.skip_cols_dynauthz(access_type) \
             and self.outer_type in {'left', None} \
             and dynauthz is not None \
             and dynauthz_testcol is None:
            # common case where we can lift row-dynauthz into join condition as optimization
            clauses = get_dynacl_clauses(self.table, 'select', alias)
            joincond = self.sql_join_condition(prefix)
            if ['True'] == clauses:
                pass
            else:
                joincond = '(%s) AND (%s)' % (
                    joincond,
                    ' OR '.join([ "(%s)" % clause for clause in clauses ]),
                )
            return "%s JOIN %s ON (%s)" % (
                {"left": "LEFT OUTER", None: ""}[self.outer_type],
                self.table.sql_name(alias=alias),
                joincond,
            )
        else:
            return '%s JOIN %s ON (%s)' % (
                {"left": "LEFT OUTER", "right": "RIGHT OUTER", "full": "FULL OUTER", None: ""}[self.outer_type],
                tsql,
                self.sql_join_condition(prefix)
            )

    def upsert(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, use_defaults=None):
        """Insert or update entities.

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

           use_defaults: customize entity processing
              { col, ... } --> use defaults
              None --> use input values

           Input rows are correlated to stored entities by metakey
           equivalence.  The metakey for an entity is the union of all
           its unique keys.

           Input row data is applied to existing entities by updating
           the non-metakey columns to match the input.

        """
        if len(self.filters) > 0:
            raise BadSyntax('Entity filters not allowed during entity PUT.')

        if not self.table.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % self.table)
        
        drop_tables = []

        # we are doing a whole entity request
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

        if use_defaults is not None:
            raise NotImplementedError("use_defaults in upsert is not supported")

        if not mkcols:
            raise ConflictModel('Entity PUT requires at least one client-managed key for input correlation.')

        use_defaults = set([
            # system columns aren't writable so don't make client ask for their defaults explicitly
            self.table.columns[cname]
            for cname in system_colnames
            if cname in self.table.columns
        ])

        input_table, input_json_table = _create_temp_input_tables(
            cur,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            in_content_type,
            drop_tables,
            use_defaults
        )

        _load_input_data(
            cur, input_data, input_table, input_json_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            in_content_type
        )

        _analyze_input_table(cur, input_table, mkcols, mkcol_aliases)

        will_insert = _enforce_table_upsert_static(
            cur, self.table, input_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases
        )

        if will_insert:
            if not set(mkcols).union(set(nmkcols)).difference(use_defaults):
                raise ConflictModel('Entity insertion requires at least one non-defaulting column.')

        _enforce_table_upsert_dynamic(
            cur, self.table, input_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            will_insert
        )

        try:
            results1, results2 = _perform_table_upsert(
                cur, self.table, input_table,
                mkcols, nmkcols,
                mkcol_aliases, nmkcol_aliases,
                content_type,
                use_defaults,
                extra_return_cols
            )

            for table in drop_tables:
                _set_statement_timeout(cur)
                cur.execute("DROP TABLE %s" % sql_identifier(table))

        except psycopg2.IntegrityError as e:
            raise ConflictModel('Input data violates model. ' + e.pgerror)

        if content_type == 'application/json':
            if not results1:
                pass
            elif results1 == ['[]\n']:
                results1 = []
            elif results2 == ['[]\n']:
                results2 = []
            else:
                # we need to splice together two serialized JSON arrays...
                assert results1[-1][-2:] == ']\n'
                assert results2[0][0] == '['
                results1[-1] = results1[-1][:-2] # remote closing ']\n'
                results1.append(',\n') # add separator
                results2[0] = results2[0][1:] # remove opening '['

        results1.extend(results2)
        return results1

    def insert(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, use_defaults=None, non_defaults=None, only_nonmatch=False):
        """Insert entities.

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

           use_defaults: customize entity processing
              { col, ... } --> use defaults for zero or more columns
              None --> same as empty set

           non_defaults: customize entity processing
              { col, ... } --> use input data for zero or more columns
              None --> same as empty set

           only_nonmatch: customize entity processing
              skip input rows that collide with existing row

           If a column is named in both use_defaults and non_defaults,
           the latter takes precedence. In practice, the non_defaults
           parameter is only necessary to reverse built-in implicit
           defaulting behavior for system columns like RID, RCT, or
           RCB.

        """
        if len(self.filters) > 0:
            raise BadSyntax('Entity filters not allowed during entity insertion.')

        if not self.table.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % self.table)

        drop_tables = []

        if use_defaults is None:
            use_defaults = set()

        if non_defaults is None:
            non_defaults = set()

        use_defaults = set([
            self.table.columns.get_enumerable(cname)
            for cname in use_defaults
            if cname not in non_defaults
        ] + [
            # system columns aren't writable so don't make client ask for their defaults explicitly
            self.table.columns.get(cname)
            for cname in system_colnames
            # but allow them to suppress this using nondefaults param...
            if cname in self.table.columns and cname not in non_defaults
        ])

        # we are doing a whole entity request
        inputcols = self.table.columns_in_order()
        mkcols = set()
        for unique in self.table.uniques:
            for c in unique:
                if c not in use_defaults:
                    mkcols.add(c)
        nmkcols = [
            c
            for c in inputcols
            if c not in mkcols
        ]
        mkcols = [
            c
            for c in inputcols
            if c in mkcols
        ]
        mkcol_aliases = dict()
        nmkcol_aliases = dict()
        extra_return_cols = [ c for c in inputcols if c.name in system_colnames ]

        if not set(mkcols).union(set(nmkcols)).difference(use_defaults):
            raise ConflictModel('Entity insertion requires at least one non-defaulting column.')

        input_table, input_json_table = _create_temp_input_tables(
            cur,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            in_content_type,
            drop_tables,
            use_defaults
        )

        _load_input_data(
            cur, input_data, input_table, input_json_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            in_content_type,
            use_defaults
        )

        _analyze_input_table(cur, input_table, mkcols, mkcol_aliases)

        _enforce_table_insert_static(
            cur, self.table, input_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            use_defaults
        )

        _enforce_table_insert_dynamic(
            cur, self.table, input_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            use_defaults
        )

        try:
            results = _perform_table_insert(
                cur, self.table, input_table,
                mkcols, nmkcols,
                mkcol_aliases, nmkcol_aliases,
                content_type,
                use_defaults,
                extra_return_cols,
                only_nonmatch=only_nonmatch
            )

            for table in drop_tables:
                _set_statement_timeout(cur)
                cur.execute("DROP TABLE %s" % sql_identifier(table))

        except psycopg2.IntegrityError as e:
            raise ConflictModel('Input data violates model. ' + e.pgerror)

        return results

    def update(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, attr_update=None, attr_aliases=None):
        """Update entities.

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

           attr_update: customized entity processing
              mkcols, nmkcols --> use specified metakey and non-metakey columns
              None --> use entity metakey and non-metakey columns

           attrs_aliases: customized input column naming
              mkcol_aliases, nmkcol_aliases --> use specific aliasesed for external columns
              None --> use table column names for external columns

           Input rows are correlated to stored entities by metakey
           equivalence.  The metakey for a custom update may be a
           subset of columns and may in fact be a non-unique key.

           Input row data is applied to existing entities by updating
           the non-metakey columns to match the input.

        """
        if len(self.filters) > 0:
            raise BadSyntax('Entity filters not allowed during entity update.')

        if not self.table.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % self.table)

        if attr_update is None:
            raise BadSyntax('Entity update requires grouping and target column lists.')

        drop_tables = []

        # caller has configured an attribute update request
        mkcols, nmkcols = attr_update
        mkcol_aliases, nmkcol_aliases = attr_aliases if attr_aliases is not None else (dict(), dict())

        input_table, input_json_table = _create_temp_input_tables(
            cur,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            in_content_type,
            drop_tables
        )

        _load_input_data(
            cur, input_data, input_table, input_json_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases,
            in_content_type
        )

        _analyze_input_table(cur, input_table, mkcols, mkcol_aliases)

        _enforce_table_update_static(
            cur, self.table, input_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases
        )

        _enforce_input_exists(cur, input_table, self.table, mkcols, mkcol_aliases)

        # NOTE: we already prefetch the whole result so might as well build incrementally...
        results = []

        _enforce_table_update_dynamic(
            cur, self.table, input_table,
            mkcols, nmkcols,
            mkcol_aliases, nmkcol_aliases
        )

        try:
            results = _perform_table_update(
                cur, self.table, input_table,
                mkcols, nmkcols,
                mkcol_aliases, nmkcol_aliases,
                content_type
            )

            for table in drop_tables:
                _set_statement_timeout(cur)
                cur.execute("DROP TABLE %s" % sql_identifier(table))

        except psycopg2.IntegrityError as e:
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

    def etag(self, cur):
        """Return snaptime of data resource.

           Result may vary if performed *before* or *after* mutation actions on catalog.
        """
        return current_catalog_snaptime(cur)

    def _get_sort_element(self, key):
        raise NotImplementedError()

    def _get_sortvec(self):
        if self.sort is not None:
            sortvec, sort1, sort2 = sort_components(
                [ self._get_sort_element(e) for e in self.sort ],
                self.after is None and self.before is not None
            )
        else:
            sortvec, sort1, sort2 = (None, None, None)
        return sortvec, sort1, sort2

    def _get_page_sql(self, sortvec, output_type_overrides={}):
        if sortvec is not None:
            a, b, c = zip(*sortvec)
            if self.after is not None:
                page = 'WHERE (%s)' % page_filter_sql(a, b, c, self.after, is_before=False)
                if self.before is not None:
                    page = '%s AND (%s)' % (page, page_filter_sql(a, b, c, self.before, is_before=True))
            elif self.before is not None:
                page = 'WHERE (%s)' % page_filter_sql(a, b, c, self.before, is_before=True)
            else:
                page = ''
        return page

    def _sql_get_agg_attributes(self, allow_extra=True):
        """Process attribute lists for aggregation APIs.
        """
        aggregates = []
        extras = [] # deprecated
        output_type_overrides = {}

        for attribute, col, base in self.attributes:
            col.enforce_data_right('select')

            output_name = str(attribute.alias) if attribute.alias is not None else col.name
            sql_attr = sql_identifier(output_name)

            if hasattr(attribute, 'aggfunc'):
                try:
                    aggfunc = aggfuncs[attribute.aggfunc](attribute, col, sql_attr)
                except KeyError as ev:
                    raise BadSyntax('Unknown aggregate function %s.' % ev)

                agg_sql, agg_type = aggfunc.sql()
                aggregates.append((agg_sql, sql_attr))
                if agg_type is not None:
                    output_type_overrides[output_name] = agg_type
            elif not allow_extra:
                raise BadSyntax('Attribute %s lacks an aggregate function.' % attribute)
            else:
                # get example values via custom agg func
                agg_sql = 'coalesce_agg(%s)' % (sql_attr,)
                aggregates.append((agg_sql, sql_attr))

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

        #deriva_debug(sql)

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

            _set_statement_timeout(cur)
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

            #deriva_debug(sql)
            _set_statement_timeout(cur)
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
            [ str(e) for e in self._path ] 
            + ([ '$%s' % self._path[self._context_index].alias ] if self._context_index >= 0 else [])
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
            # non-enumerable columns will be omitted from entity results when enforcing
            if enforce_client:
                for col in context_table.columns_in_order(enforce_client=enforce_client):
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
            if unique.is_primary_key() and (unique.has_right('select') or not enforce_client)
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
            # use 'select' visibility for all but context table instance
            elem.sql_table_elem(dynauthz=True if dynauthz is not None else None, access_type='select', prefix=prefix)
            for elem in self._path[0:context_pos]
        ] + [
            # dynauthz_testcol may be None or an actual column here...
            self._path[context_pos].sql_table_elem(dynauthz=dynauthz, access_type=access_type, prefix=prefix, dynauthz_testcol=dynauthz_testcol)
        ] + [
            # this is usually empty list but might not if a URL path ends with a context reset
            # use 'select' visibility for all but context table instance
            elem.sql_table_elem(dynauthz=True if dynauthz is not None else None, access_type='select', prefix=prefix)
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
            _set_statement_timeout(cur)
            cur.execute("SELECT True FROM (%s) s LIMIT 1" % self.sql_get(dynauthz=False, access_type='delete'))
            if cur.fetchone():
                raise Forbidden(u'delete access on one or more matching rows in table %s' % table)

        table = self._path[self._context_index].table
        victim_table = sql_identifier(random_name('victims_'))
        primary_keys = [ key for key in table.uniques.values() if key.is_primary_key() ]
        if primary_keys:
            # use shortest non-nullable key if available
            primary_keys.sort(key=lambda k: len(k.columns))
            mkcols = set(primary_keys[0].columns)
        else:
            # use full metakey if there are no non-nullable keys
            mkcols = set()
            for key in table.uniques:
                for col in key:
                    mkcols.add(col)
        mkcols = list(mkcols)

        cur.execute("CREATE TEMPORARY TABLE %s AS %s;" % (victim_table, self.sql_get()))
        _set_statement_timeout(cur)
        cur.execute("CREATE INDEX ON %s (%s);" % (
            victim_table,
            ', '.join([ c.sql_name() for c in mkcols])
        ))
        _set_statement_timeout(cur)
        cur.execute("ANALYZE %s;" % victim_table)
        _set_statement_timeout(cur)
        cur.execute("SELECT count(*) AS count FROM %s;" % victim_table)
        cnt = cur.fetchone()[0]
        if cnt == 0:
            raise NotFound('entities matching request path')
        _set_statement_timeout(cur)
        cur.execute(
            "DELETE FROM %s AS t USING %s AS v WHERE %s;" % (
                table.sql_name(),
                victim_table,
                ' AND '.join([
                    ("(t.%(c)s = v.%(c)s)" if not c.nullok \
                     else "(t.%(c)s = v.%(c)s OR t.%(c)s IS NULL AND v.%(c) IS NULL)"
                    ) % {'c': c.sql_name()}
                    for c in mkcols
                ])
            )
        )
        _set_statement_timeout(cur)
        cur.execute("DROP TABLE %s;" % victim_table)

    def upsert(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None):
        """Insert oro update entities.

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

        """
        if len(self._path) != 1:
            raise BadData("unsupported path length for put")

        return self._path[0].upsert(conn, cur, input_data, in_content_type, content_type, output_file)

    def insert(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, use_defaults=None, non_defaults=None, only_nonmatch=False):
        """Insert entities.

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

        """
        if len(self._path) != 1:
            raise BadData("unsupported path length for insertion")

        return self._path[0].insert(conn, cur, input_data, in_content_type, content_type, output_file, use_defaults, non_defaults, only_nonmatch=only_nonmatch)

    def update(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, attr_update=None, attr_aliases=None):
        """Update entities.

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
            raise BadData("unsupported path length for update")

        return self._path[0].update(conn, cur, input_data, in_content_type, content_type, output_file, attr_update, attr_aliases)

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
                typname = col.type.sql(basic_storage=True)

                if typname not in {'int2', 'int4', 'int8', 'float', 'float4', 'float8', 'numeric', 'timestamptz', 'timestamp', 'date'}:
                    raise ConflictModel('Binning not supported on column type %s.' % col.type)

                parts = {
                    'val':   "%s.%s" % (alias, col.sql_name()),
                    'nbins': sql_literal(attribute.nbins),
                    'minv':  col.type.sql_literal(str(attribute.minv)),
                    'maxv':  col.type.sql_literal(str(attribute.maxv)),
                }

                bexpr = lambda e: e
                if typname in {'timestamptz', 'timestamp', 'date'}:
                    # convert to float so width_bucket can handle it
                    bexpr = lambda e: "EXTRACT(EPOCH FROM %s)" % e

                parts['bucket'] = 'width_bucket(%(val)s, %(minv)s, %(maxv)s, %(nbins)s::int)' % {
                    'val': bexpr(parts['val']),
                    'minv': bexpr(parts['minv']),
                    'maxv': bexpr(parts['maxv']),
                    'nbins': parts['nbins'],
                }

                if typname == 'date':
                    # date arithmetic produces integer when we wanted interval...
                    parts['bminv'] = "%(minv)s + '1 day'::interval * ((%(maxv)s - %(minv)s) * (%(bucket)s - 1) / %(nbins)s::float4)" % parts
                    parts['bmaxv'] = "%(minv)s + '1 day'::interval * ((%(maxv)s - %(minv)s) * %(bucket)s       / %(nbins)s::float4)" % parts
                else:
                    # most arithmetic remains within same type
                    parts['bminv'] = "%(minv)s + (%(maxv)s - %(minv)s) * ((%(bucket)s - 1) / %(nbins)s::float4)" % parts
                    parts['bmaxv'] = "%(minv)s + (%(maxv)s - %(minv)s) * (%(bucket)s       / %(nbins)s::float4)" % parts

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
            elif hasattr(attribute, 'rights_summary'):
                if not col.name == 'RID':
                    raise ConflictModel('Rights summary not supported on column "%s".' % col.name)
                rights = {
                    'update': None,
                    'delete': None,
                }
                for access in list(rights):
                    right = col.table.has_right(access)
                    if isinstance(right, bool):
                        rights[access] = '%s::boolean' % right
                    elif right is None:
                        rights[access] = 'COALESCE(%s, False)' % (' OR '.join([
                            '(%s)' % clause
                            for clause in get_dynacl_clauses(col.table, access, alias)
                        ]))
                    else:
                        raise NotImplementedError('unexpected access right %s = %r in entity rights summary' % (access, right))
                    if attribute.summarize_columns:
                        col_rights = {
                            c: None
                            for c in col.table.columns_in_order()
                        }
                        for c in list(col_rights):
                            if c.name in {'RID', 'RMT', 'RCT', 'RMB', 'RCB'}:
                                right = False
                            else:
                                right = c.has_right('update')
                            if isinstance(right, bool):
                                col_rights[c] = '%s::boolean' % right
                            elif right is None:
                                col_rights[c] = '(NOT (%s))' % c.sql_name_dynauthz(alias, dynauthz=False, access_type='update')
                            else:
                                raise NotImplementedError('unexpected column update right %r in entity rights summary' % (right,))
                        col_rights = [ '%s, %s' % (sql_literal(c.name), right) for c, right in col_rights.items() ]
                        # bypass postgres limit for number of args to a func
                        def chunked(l, chunksize=25):
                            for offset in range(0, len(l), chunksize):
                                yield l[offset:offset+chunksize]
                        rights['column_update'] = ' || '.join([
                            'jsonb_build_object(%s)' % (','.join(batch))
                            for batch in chunked(col_rights)
                        ])
                select = 'jsonb_build_object(%s)' % (','.join([ '%s::text, %s' % (sql_literal(access), right) for access, right in rights.items() ]))
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
                if str(attribute.alias) in outputs:
                    raise BadSyntax('Output column name "%s" appears more than once.' % attribute.alias)
                outputs.add(str(attribute.alias))
                output_types[str(attribute.alias)] = col.type
                selects.append('%s AS %s' % (select, sql_identifier(attribute.alias)))
            else:
                if col.name in outputs:
                    raise BadSyntax('Output column name "%s" appears more than once.' % col.name)
                outputs.add(col.name)
                output_types[col.name] = col.type
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
            _set_statement_timeout(cur)
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
                    _set_statement_timeout(cur)
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

        _set_statement_timeout(cur)
        cur.execute("SELECT count(*) AS count FROM (%s) s" % equery)
        if cur.fetchone()[0] == 0:
            raise NotFound('entities matching request path')
        table = self.epath.current_entity_table()
        _set_statement_timeout(cur)
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
        extras = [] # deprecated

        for key, col, base in self.groupkeys:
            if key.alias is not None:
                groupkeys.append( sql_identifier(str(key.alias)) )
            else:
                groupkeys.append( sql_identifier(col.name) )

        asql, page, sort1, limit, sort2 = apath.sql_get(split_sort=True, distinct_on=False, limit=limit, dynauthz=dynauthz, access_type=access_type, prefix=prefix, enforce_client=enforce_client)
        aggregates, extras, self.output_type_overrides = self._sql_get_agg_attributes()

        if extras:
            raise NotImplementedError('found unexpected extras in aggregation')
            # an impure aggregate query finds exemplars via custom coalesce_agg() 
            # which is folded into the core aggregate query, so extras should ALWAYS be empty now
        else:
            # a pure aggregate query has only group keys and aggregates
            sql = """
SELECT %(groupaggs)s
FROM ( %(asql)s ) s
GROUP BY %(groupkeys)s
"""
        sql = sql % dict(
            asql=asql,
            groupkeys=', '.join(groupkeys),
            groupaggs=', '.join(groupkeys + ["%s AS %s" % a for a in aggregates]),
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

    def update(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None):
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
        return self.epath.update(conn, cur, input_data, in_content_type, content_type, output_file, attr_update=attr_update, attr_aliases=attr_aliases)

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
        if v.find(',') > -1 or v.find('"') > -1:
            return '"%s"' % (v.replace('"', '""'))
        else:
            return v

    if cdesc is not None:
        if cdesc.type_code in [ JSON_OID, JSONB_OID ]:
            return condquote(json.dumps(v))

    if v is None:
        return ''

    if isinstance(v, (int, float)):
        return '%s' % v

    if isinstance(v, list):
        return condquote('{%s}' % ",".join([ val_to_csv(e) for e in v ]))

    else:
        return condquote(str(v))

def row_to_csv(row, desc=None):
    try:
        return ','.join([ val_to_csv(row[i], desc[i] if desc is not None else None) for i in range(len(row)) ])
    except Exception as e:
        deriva_debug('row_to_csv', row, e)
        raise
       
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

        policy = deriva_ctx.ermrest_config.get('textfacet_policy', False)
            
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

    def sql_get(self, row_content_type='application/json', limit=None, dynauthz=None, prefix='', enforce_client=True):
        queries = [
            # column ~* pattern is ciregexp...
            """(SELECT %(stext)s::text AS "schema", %(ttext)s::text AS "table", %(ctext)s::text AS "column" FROM %(sid)s.%(tid)s WHERE _ermrest.astext(%(cid)s) ~* %(pattern)s LIMIT 1)""" % dict(
                stext=sql_literal(sname),
                ttext=sql_literal(tname),
                ctext=sql_literal(column.name),
                pattern=sql_literal(str(self.pattern)),
                sid=sql_identifier(sname),
                tid=sql_identifier(tname),
                cid=sql_identifier(column.name)
            )
            for sname, tname, column in self.columns()
        ] + [
            """(SELECT 's' AS "schema", 't' AS "table", 'c' AS "column" WHERE false)"""
        ]
        return ' UNION ALL '.join(queries)
                    
