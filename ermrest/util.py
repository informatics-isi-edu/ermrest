
# 
# Copyright 2012-2026 University of Southern California
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
"""
General utilities for ERMREST.
"""

# Right now these are all DB related utilities. We should keep it that way.

import re
import urllib
import uuid
import base64
import collections
from webauthn2.util import urlquote

__version__ = '0.5.0'

def urlunquote(url):
    text = urllib.parse.unquote_plus(url)
    return text

def schema_exists(cur, schemaname):
    """Return True or False depending on whether schema exists in our 
       database.
       
       schemaname : the schema name
    """

    cur.execute("""
SELECT * FROM information_schema.schemata
WHERE schema_name = %(schema)s
"""
                       % dict(schema=sql_literal(schemaname))
                       )
    exists = cur.rowcount > 0
    return exists


def table_exists(cur, schemaname, tablename):
    """Return True or False depending on whether (schema.)tablename exists in 
       our database.
       
       
       schemaname : the schema name
       tablename : the table name
    """
    cur.execute("""
SELECT * FROM information_schema.tables
WHERE table_schema = %(schema)s
AND table_name = %(table)s
"""
                     % dict(schema=sql_literal(schemaname),
                            table=sql_literal(tablename))
                     )
    exists = cur.rowcount > 0
    return exists

def column_exists(cur, schemaname, tablename, columnname):
    cur.execute("""
SELECT * FROM information_schema.columns
WHERE table_schema = %(schema)s
  AND table_name = %(table)s
  AND column_name = %(column)s
""" % dict(
    schema=sql_literal(schemaname),
    table=sql_literal(tablename),
    column=sql_literal(columnname)
)
    )
    exists = cur.rowcount > 0
    return exists

class IndexABC:
    """Abstract base to represent an index"""
    def __init__(self, **kwargs):
        self.tname = kwargs['tname']
        self.indexname = kwargs['indexname']
        self.definition = None
        self.primary = kwargs['primary']
        self.unique = kwargs['unique']
        self.exclusion = kwargs['exclusion']
        self.valid = kwargs['valid']
        self.ready = kwargs['ready']
        self.live = kwargs['live']
        self.sqldef = kwargs['sqldef']
        self.sqlexprs = kwargs['sqlexprs']

    def to_dict(self):
        return {
            "indexname": self.indexname,
            "definition": self.definition,
            "primary": self.primary,
            "unique": self.unique,
            "exclusion": self.exclusion,
            "valid": self.valid,
            "ready": self.ready,
            "live": self.live,
            "sqldef": self.sqldef,
        }

    def check_conflicts(self, op, exc_factory):
        conflicts = {
            k
            for k, v in {
                    "primary": self.primary,
                    "unique": self.unique,
                    "exclusion": self.exclusion,
            }.items()
            if v
        }
        if conflicts:
            raise exc_factory(f'{op} of {"+".join(conflicts)} index {self.indexname!r}')

class IndexLive (IndexABC):
    """Represent an index on a current live table in the model"""
    @classmethod
    def check_available(cls, cur, table, indexname, conflict_factory, forbidden_factory):
        for idx in cls.from_db_schema(cur, table.schema.name, indexname):
            if idx.tname != table.name:
                raise conflict_factory(f"index name {idx.indexname!r} in use on table {table.schema.name!r}.{table.name!r}")
            else:
                idx.check_conflicts("replacement", forbidden_factory)

    @classmethod
    def idxdoc_to_sql(cls, cur, idxdoc, table, indexname, baddata_factory, conflict_factory, forbidden_factory):
        cls.check_available(
            cur,
            table,
            indexname,
            conflict_factory,
            forbidden_factory,
        )

        if not isinstance(idxdoc, dict):
            raise baddata_factory('index creation input must be a JSON object')

        require_mutual_exclusive = {'btree', 'trgm', 'gin_array'}
        index_types = set(idxdoc.keys()).intersection(require_mutual_exclusive)
        if len(index_types) != 1:
            raise baddata_factory(f'index creation input must specify exactly one of {"/".join(require_mutual_exclusive)}')

        index_type = index_types.pop()
        index_want = idxdoc[index_type]

        if isinstance(index_want, list):
            if not all([ isinstance(e, str) for e in index_want ]):
                raise baddata_factory(f"index creation field not understood {index_type}={index_want}")

            for cname in index_want[1:]:
                if cname not in table.columns:
                    raise conflict_factory(f"index creation field {index_type} references unknown column {sql_identifier(cname)}")

            base_cname = index_want[0]
        else:
            if not isinstance(index_want, str):
                raise baddata_factory(f"index creation field not understood {index_type}={index_want}")
            base_cname = index_want

        if base_cname not in table.columns:
            raise conflict_factory(f"index creation field {index_type} references unknown column {sql_identifier(base_cname)}")

        base_column = table.columns[base_cname]

        if index_type == 'btree':
            sql = base_column.btree_index_sql(index_want, indexname)
        elif index_type == 'trgm':
            sql = base_column.pg_trgm_index_sql(index_want, indexname)
        elif index_type == 'gin_array':
            sql = base_column.pg_gin_array_index_sql(index_want, indexname)
        else:
            raise baddata_factory(f"unknown indexing preference field {index_type}")

        if sql is None:
            raise baddata_factory("desired index cannot be determined from input")

        return sql

    @classmethod
    def from_row(cls, table, row):
        sname, tname, iname, prim, uniq, excl, valid, ready, live, sqldef, sqlexprs = row
        return cls(
            table,
            schemaname=sname, tname=tname, indexname=iname,
            primary=prim, unique=uniq, exclusion=excl,
            valid=valid, ready=ready, live=live,
            sqldef=sqldef, sqlexprs=sqlexprs,
        )

    @classmethod
    def from_db_single(cls, cur, table, indexname):
        row = index_exists_on_table(cur, table.schema.name, table.name, indexname)
        if row:
            return cls.from_row(table, row)
        else:
            return None

    @classmethod
    def from_db_schema(cls, cur, sname, indexname):
        return [
            cls.from_row(None, row)
            for row in enumerate_indexes(cur, sname, None, indexname)
        ]

    @classmethod
    def from_db_table(cls, cur, table):
        return [
            cls.from_row(table, row)
            for row in enumerate_indexes(cur, table.schema.name, table.name, None)
        ]

    def __init__(self, table, *, schemaname, tname, indexname, primary, unique, exclusion, valid, ready, live, sqldef, sqlexprs):
        kwargs = { k: v for k, v in locals().items() if k != 'self' }
        assert(table.schema.name == schemaname)
        super(IndexLive, self).__init__(**kwargs)
        self.table = table
        self.schemaname = schemaname
        self.definition = self.sql_to_defn()

    def to_dict(self):
        return {
            "schemaname": self.schemaname
        } | super(IndexLive, self).to_dict()

    def sql_to_defn(self):
        """Return pre-JSON (dict) definition of index if we can infer it from SQL DDL, or None"""
        if self.table is None:
            return None

        s1 = self.sqldef

        # prefix: CREATE (UNIQUE|PRIMARY KEY) INDEX
        m = re.match('CREATE( [A-Z]+)* INDEX ', s1)
        if not m:
            return None
        s1 = s1[m.end():]

        # quoted or unquoted SQL identifier
        pat_ident = '([^" (),:.]+|"([^"]|"")+")'

        # prefix: indexname ON schema.table
        m = re.match(f'{pat_ident} ON {pat_ident}[.]{pat_ident} ', s1)
        if not m:
            return None
        s1 = s1[m.end():]

        # prefix: USING indextype
        m = re.match(f'USING ({pat_ident}) [(]', s1)
        if not m:
            return None
        indextype = m.group(1).lower()
        s1 = s1[m.end():]

        def sql_ident_unquote(s):
            if s.startswith('"') and s.endswith('"'):
                s = s[1:-1]
                s = s.replace('""', '"')
            return s

        if indextype == 'gin':
            if len(self.sqlexprs) > 1:
                # we don't create composite GIN indexes!
                return None

            # ignore sqlexprs because it may have different parens than sqldef
            # which we need to analyze for ops class :-(
            if s1.startswith('_ermrest.astext(') and s1.find('gin_trgm_ops)') > 0:
                # looks like our trgm indexing pattern...

                m = re.match(f'_ermrest.astext[(]({pat_ident})(::[^,():]+)?[)] gin_trgm_ops', s1)
                if not m:
                    m = re.match(f'_ermrest.astext[(]([(]{pat_ident}[)])(::[^,():]+)?[)] gin_trgm_ops', s1)
                if not m:
                    return None

                cname = sql_ident_unquote(m.group(1))
                if cname not in self.table.columns:
                    return None

                return {'trgm': [cname]}

            # looks like our gin-array pattern...?
            m = re.match(pat_ident, s1)
            if not m:
                return None

            cname = sql_ident_unquote(m.group(0))
            if cname not in self.table.columns:
                return None

            if not self.table.columns[cname].is_array:
                return None

            return {'gin_array': [cname]}

        elif indextype == 'btree':
            cnames = []

            for s2 in self.sqlexprs:
                m = re.fullmatch(pat_ident, s2)
                if not m:
                    return None

                s1 = s1[len(s2)+1:]
                cname = sql_ident_unquote(m.group(0))
                if cname not in self.table.columns:
                    return None

                cnames.append(cname)

            return {'btree': cnames}
        else:
            # not one we allow clients to make!
            return None

        return None

def history_trid_syscol_rids(cur, table_rid, notfound_factory):
    """Probe for table RID and return (history_tname, syscol_rids_d) pair"""
    # find first occurrence of table_rid and its schema name
    # ignoring internal _ermrest schema
    cur.execute(f"""
SELECT
  t."RID",
  c_rid.rid,
  c_rmb.rid,
  c_rmt.rid
FROM _ermrest_history.known_tables t
JOIN LATERAL (
  SELECT c_rid."RID"
  FROM _ermrest_history.known_columns c_rid
  WHERE c_rid.rowdata->>'table_rid' = t."RID"
    AND c_rid.rowdata->>'column_name' = 'RID'
    AND lower(c_rid.during) <@ t.during
  LIMIT 1
) c_rid(rid) ON (True)
JOIN LATERAL (
  SELECT c_rmb."RID"
  FROM _ermrest_history.known_columns c_rmb
  WHERE c_rmb.rowdata->>'table_rid' = t."RID"
    AND c_rmb.rowdata->>'column_name' = 'RMB'
    AND lower(c_rmb.during) <@ t.during
  LIMIT 1
) c_rmb(rid) ON (True)
JOIN LATERAL (
  SELECT c_rmt."RID"
  FROM _ermrest_history.known_columns c_rmt
  WHERE c_rmt.rowdata->>'table_rid' = t."RID"
    AND c_rmt.rowdata->>'column_name' = 'RMT'
    AND lower(c_rmt.during) <@ t.during
  LIMIT 1
) c_rmt(rid) ON (True)
WHERE t."RID" = {sql_literal(table_rid)}
  AND EXISTS (
    SELECT true
    FROM _ermrest_history.known_schemas s
    WHERE s."RID" = t.rowdata->>'schema_rid'
      AND lower(t.during) <@ s.during
      AND s.rowdata->>'schema_name' != '_ermrest'
)
LIMIT 1
""")
    found_table_row = None
    for row in cur:
        found_table_row = row

    # make sure table is known in model history
    if not found_table_row:
        raise notfound_factory(f'History table with RID={table_rid}')

    # and we actually have a backing history table
    tname = f"t{table_rid}"
    if not table_exists(cur, '_ermrest_history', tname):
        raise exception.rest.NotFound(f'History table with RID={table_rid}')

    trid, rid_rid, rmb_rid, rmt_rid = found_table_row
    rids = {
        'RID': rid_rid,
        'RMB': rmb_rid,
        'RMT': rmt_rid,
    }
    return tname, rids

def history_trid_crid_typeinfo(cur, table_rid, column_rid, conflict_factory, require_single_type=True):
    """Probe column RID for table RID and return typeinfo"""
    # find column rid for table (we've already validated table rid)
    # and get longitudinal typing info
    cur.execute(f"""
SELECT DISTINCT
  t1.type_name,
  t2.type_name AS base_type_name
FROM _ermrest_history.known_columns c
JOIN LATERAL (
  -- t0 is the original type which may be a domain/array/base type
  SELECT
    t0."RID",
    t0.during,
    t0.rowdata->>'domain_element_type_rid' AS domain_element_type_rid
  FROM _ermrest_history.known_types t0
  WHERE t0."RID" = c.rowdata->>'type_rid'
    AND t0.during && c.during
) t0 ON true
JOIN LATERAL (
  -- t1 strips the t0 domain type wrapper (if any)
  SELECT
    t1."RID",
    t1.during,
    t1.rowdata->>'type_name' AS type_name,
    t1.rowdata->>'domain_element_type_rid' AS domain_element_type_rid,
    t1.rowdata->>'array_element_type_rid' AS array_element_type_rid
  FROM _ermrest_history.known_types t1
  WHERE t1."RID" = COALESCE(t0.domain_element_type_rid, t0."RID")
    AND t1.during && t0.during
) t1 ON true
LEFT JOIN LATERAL (
  -- t2 is the base type of t1 iff t1 is an array type
  SELECT
    t2."RID",
    t2.during,
    t2.rowdata->>'type_name' AS type_name,
    t2.rowdata->>'domain_element_type_rid' AS domain_element_type_rid,
    t2.rowdata->>'array_element_type_rid' AS array_element_type_rid
  FROM _ermrest_history.known_types t2
  WHERE t2."RID" = t1.array_element_type_rid
    AND t2.during && t1.during
) t2 ON true
WHERE c."RID" = {sql_literal(column_rid)}
  AND c.rowdata->>'table_rid' = {sql_literal(table_rid)}
""")
    type_info = list(cur)

    if not type_info:
        raise conflict_factory(f'Unknown column RID={column_rid} on history table RID={table_rid}')

    if require_single_type:
        if len(type_info) > 1:
            raise conflict_factory(f'Ambiguous type for column RID={column_rid} on history table RID={table_rid}')
        return type_info[0]
    else:
        return type_info

class IndexHistorical (IndexABC):
    """Represent an index on a history table"""
    @classmethod
    def check_available(cls, cur, tname, indexname, conflict_factory, forbidden_factory):
        for idx in cls.from_db_schema(cur, indexname):
            if idx.tname != tname:
                raise conflict_factory(f"Index name {indexname} in use on a different history table.")
            else:
                idx.check_conflicts("replacement", forbidden_factory)

    # HACK: the following must be kept in sync with
    # ermrest.model.types OOP methods which are written in terms of a
    # catalog (or snapshot) model, rather than the longitudinal
    # perspective we have to take here.  potential hazards:
    #
    # 1. a column that is altered to change type over time
    # 2. a type RID that changes meaning over time (?)
    #
    @classmethod
    def idxdoc_to_sql(cls, cur, idxdoc, table_rid, tname, syscol_rids, indexname, baddata_factory, conflict_factory, forbidden_factory):
        syscol_rids_invert = {
            rid: cname
            for cname, rid in syscol_rids.items()
        }
        cls.check_available(cur, tname, indexname, conflict_factory, forbidden_factory)

        # validate input idxdoc...
        if not isinstance(idxdoc, dict):
            raise baddata_factory('index creation input must be a JSON object')

        require_mutual_exclusive = {'btree', 'trgm', 'gin_array'}
        index_types = set(idxdoc.keys()).intersection(require_mutual_exclusive)
        if len(index_types) != 1:
            raise baddata_factory(f'index creation input must specify exactly one of {"/".join(require_mutual_exclusive)}')

        index_type = index_types.pop()
        index_want = idxdoc[index_type]

        crid_typeinfo = {}

        if isinstance(index_want, list):
            if not len(index_want) > 0:
                raise baddata_factory(f'index creation field not understood {index_type}={index_want}')

            if not all([ isinstance(e, str) for e in index_want ]):
                raise baddata_factory(f'index creation field not understood {index_type}={index_want}')

            for crid in index_want[1:]:
                crid_typeinfo[crid] = history_trid_crid_typeinfo(
                    cur,
                    table_rid,
                    crid,
                    conflict_factory,
                    require_single_type=True,
                )

            base_crid = index_want[0]
        elif isinstance(index_want, str):
            base_crid = index_want
        else:
            raise baddata_factory(f"index creation field not understood {index_type}={index_want}")

        crid_typeinfo[base_crid] = history_trid_crid_typeinfo(
            cur,
            table_rid,
            base_crid,
            conflict_factory,
            require_single_type=True,
        )

        def basic_store_type(type_name):
            return {
                'serial2': 'int2',
                'serial4': 'int4',
                'serial8': 'int8',
            }.get(type_name, type_name)

        def is_array(crid):
            type_name, elem_type_name = crid_typeinfo[crid]
            return elem_type_name is not None

        def is_indexable(crid):
            type_name, elem_type_name = crid_typeinfo[crid]
            if elem_type_name is not None:
                elem_type_name = basic_store_type(type_name)
                return elem_type_name != 'json'
            else:
                type_name = basic_store_type(type_name)
                return type_name != 'json'

        def history_projection(crid, cast=True):
            # this type info already collapses domain types to underlying types
            type_name, elem_type_name = crid_typeinfo[crid]
            type_name = basic_store_type(type_name)

            if elem_type_name is not None:
                # use type-specific IMMUTABLE wrapper functions
                elem_type_name = basic_store_type(elem_type_name)
                target = {
                    'text': 'text',
                    'int2': 'int2',
                    'smallint': 'int2',
                    'int4': 'int4',
                    'integer': 'int4',
                    'int8': 'int8',
                    'bigint': 'int8',
                    'float4': 'float4',
                    'real': 'float4',
                    'float8': 'float8',
                    'double precision': 'float8',
                    'jsonb': 'jsonb',
                    'json': 'json',
                    'date': 'date',
                    'boolean': 'boolean',
                    'timestamp with time zone': 'timestamptz',
                }.get(elem_type_name)
                if target is None:
                    raise conflict_factory(f"History column {crid} has unsupported type: array of {elem_type_name}")
                return f"_ermrest.history_{target}_arr(rowdata->{sql_literal(crid)})"
            else:
                # scalar column
                column_name = syscol_rids_invert.get(crid)
                if column_name in {'RID', 'RMB'}:
                    return sql_identifier(column_name)
                elif column_name == 'RMT':
                    return f"(lower(during))"
                else:
                    op = '->' if type_name == 'jsonb' else '->>'
                    expr = f"rowdata{op}{sql_literal(crid)}"
                    if not cast:
                        return f"({expr})"
                    elif type_name in {'timestamptz', 'timestamp with time zone'}:
                        return f"(_ermrest.history_timestamptz({expr}))"
                    elif type_name in {'date'}:
                        return f"(_ermrest.history_date({expr}))"
                    elif type_name in {'timestamp', 'timestamp without time zone'}:
                        raise conflict_factory(f"History column {crid} has unsupported type: {type_name}")
                    else:
                        return f"(({expr})::{type_name})"

        sql_parts = [
            f"DROP INDEX IF EXISTS _ermrest_history.{sql_identifier(indexname)};",
            f"CREATE INDEX {sql_identifier(indexname)} ON _ermrest_history.{sql_identifier(tname)}",
            "USING btree (" if index_type == 'btree' else "USING GIN ("
        ]

        if index_type == 'trgm':
            if not isinstance(index_want, str):
                raise baddata_factory(f"Invalid compound index {index_type}={index_want}")
            # everything gets cast to text
            sql_parts.append(f"_ermrest.astext({history_projection(base_crid, cast=False)}) gin_trgm_ops")
        elif index_type == 'gin_array':
            if not isinstance(index_want, str):
                raise baddata_factory(f"Invalid compound index {index_type}={index_want}")
            if not is_array(base_crid) or not is_indexable(base_crid):
                raise conflict_factory(f"Conflicting column type for index {index_type}={index_want}")
            sql_parts.append(f"{history_projection(base_crid)} array_ops")
        elif index_type == 'btree':
            if base_crid == index_want:
                index_want = [ base_crid ]

            def btree_col(crid):
                if not is_indexable(crid):
                    raise conflict_factory(f"Conflicting column type for index {index_type}=...{crid}...")
                return history_projection(crid)

            sql_parts.append(', '.join([ btree_col(crid) for crid in index_want]))
        else:
            raise baddata_factory(f"Invalid index {index_type}={index_want}")

        sql_parts.append(");")
        sql_parts.append("SELECT _ermrest.model_version_bump();")
        sql = "\n".join(sql_parts)
        return sql

    @classmethod
    def from_row(cls, table_rid, syscol_rids, row):
        sname, tname, iname, prim, uniq, excl, valid, ready, live, sqldef, sqlexprs = row
        return cls(
            table_rid,
            syscol_rids,
            schemaname=sname, tname=tname, indexname=iname,
            primary=prim, unique=uniq, exclusion=excl,
            valid=valid, ready=ready, live=live,
            sqldef=sqldef, sqlexprs=sqlexprs,
        )

    @classmethod
    def from_db_schema(cls, cur, indexname):
        return [
            cls.from_row(None, {}, row)
            for row in enumerate_indexes(cur, '_ermrest_history', None, indexname)
        ]

    @classmethod
    def from_db_table(cls, cur, table_rid, tname, syscol_rids, iname=None):
        return [
            cls.from_row(table_rid, syscol_rids, row)
            for row in enumerate_indexes(cur, '_ermrest_history', tname, iname)
        ]

    @classmethod
    def from_db_single(cls, cur, table_rid, tname, syscol_rids, iname):
        idxlist = cls.from_db_table(cur, table_rid, tname, syscol_rids, iname)
        assert(len(idxlist)==1)
        return idxlist[0]

    def __init__(self, table_rid, syscol_rids, *, schemaname, tname, indexname, primary, unique, exclusion, valid, ready, live, sqldef, sqlexprs):
        kwargs = { k: v for k, v in locals().items() if k != 'self' }
        super(IndexHistorical, self).__init__(**kwargs)
        self.table_rid = table_rid
        self.syscol_rids = syscol_rids
        self.definition = self.sql_to_defn()

    def sql_to_defn(self):
        """Return pre-JSON (dict) definition of index if we can infer it from SQL DDL, or None

        """
        s1 = self.sqldef

        # prefix: CREATE (UNIQUE|PRIMARY KEY) INDEX
        m = re.match('CREATE( [A-Z]+)* INDEX ', s1)
        if not m:
            return None
        s1 = s1[m.end():]

        # quoted or unquoted SQL identifier
        pat_ident = '([^" (),:.]+|"([^"]|"")+")'

        # prefix: indexname ON schema.table
        m = re.match(f'{pat_ident} ON {pat_ident}[.]{pat_ident} ', s1)
        if not m:
            return None
        s1 = s1[m.end():]

        # prefix: USING indextype
        m = re.match(f'USING ({pat_ident}) [(]', s1)
        if not m:
            return None
        indextype = m.group(1).lower()
        s1 = s1[m.end():]

        def sql_ident_unquote(s):
            if s.startswith('"') and s.endswith('"'):
                s = s[1:-1]
                s = s.replace('""', '"')
            return s

        pat_ridproj = "[(]rowdata *->>? *'([-0-9A-Z]+)'::text[)]"

        if indextype == 'gin':
            if len(self.sqlexprs) > 1:
                # we don't create composite GIN indexes!
                return None

            # ignore sqlexprs because it may have different parens than sqldef
            # which we need to analyze for ops class :-(

            if s1.startswith('_ermrest.astext(') and s1.find('gin_trgm_ops)') > 0:
                # looks like our trgm indexing pattern...
                m = re.match(f'_ermrest.astext[(]{pat_ridproj}[)] gin_trgm_ops', s1)
                if not m:
                    m = re.match(f'_ermrest.astext[(]_ermrest.history_[^()]+[(]{pat_ridproj}[)][)] gin_trgm_ops', s1)
                if m:
                    crid = m.group(1)
                else:
                    # these special cases do not embed a column RID in the index def
                    m = re.match(f'_ermrest.astext[(]("RID"|"RMB"|lower[(]during[)])[)] gin_trgm_ops', s1)
                    if not m:
                        return None
                    cname = sql_ident_unquote(m.group(1))
                    if cname == 'lower(during)':
                        cname = 'RMT'
                    crid = rids.get(cname)

                return {'trgm': [crid]}

            # looks like our gin-array pattern...?
            m = re.match(f'_ermrest.history_[^()_]+_arr[(]{pat_ridproj}[)]', s1)
            if not m:
                return None

            crid = m.group(1)

            return {'gin_array': [crid]}

        elif indextype == 'btree':
            crids = []

            for s2 in self.sqlexprs:
                m = re.fullmatch(f'{pat_ridproj}', s2)
                if not m:
                    m = re.fullmatch(f'[(]{pat_ridproj}(::[^:()]+)?[)]', s2)
                if not m:
                    # pat_ridproj is already surrounded by literal parens so this is func call
                    m = re.fullmatch(f'_ermrest.history_[^()]+{pat_ridproj}', s2)
                if m:
                    crid = m.group(1)
                else:
                    # special cases again...
                    m = re.fullmatch(f'("RID"|"RMB"|lower[(]during[)])', s2)
                    if not m:
                        return None
                    cname = sql_ident_unquote(m.group(1))
                    if cname == 'lower(during)':
                        cname = 'RMT'
                    crid = self.syscol_rids.get(cname, cname)

                crids.append(crid)

            return {'btree': crids}
        else:
            return None

        return None

def enumerate_indexes(cur, schemaname, tablename=None, indexname=None):
    tableclause = f"  AND ct.relname = {sql_literal(tablename)}" if tablename else ""
    nameclause = f"  AND ci.relname = {sql_literal(indexname)}" if indexname else ""
    cur.execute(f"""
SELECT
  nt.nspname AS schema_name,
  ct.relname AS table_name,
  ci.relname AS index_name,
  i.indisprimary AS primary,
  i.indisunique AS unique,
  i.indisexclusion AS exclusion,
  i.indisvalid AS valid,
  i.indisready AS ready,
  i.indislive AS live,
  pg_get_indexdef(ci.oid) AS indexdef_sql,
  (SELECT array_agg(pg_get_indexdef(ci.oid, ne.n, true) ORDER BY ne.n)
   FROM generate_series(1, i.indnatts, 1) ne (n)) AS expr_sqls
FROM pg_catalog.pg_index i
JOIN pg_catalog.pg_class ci ON (i.indexrelid = ci.oid)
JOIN pg_catalog.pg_class ct ON (i.indrelid = ct.oid)
JOIN pg_catalog.pg_namespace nt on (ct.relnamespace = nt.oid)
WHERE nt.nspname = {sql_literal(schemaname)}
{tableclause}
{nameclause}
""")
    for row in cur:
        yield row

def index_exists_on_table(cur, schemaname, tablename, indexname):
    for row in enumerate_indexes(cur, schemaname, tablename, indexname):
        return row

def drop_index(cur, schemaname, indexname):
    # manually bump version to force ETag to change!
    cur.execute(f"""
DROP INDEX {sql_identifier(schemaname)}.{sql_identifier(indexname)};
SELECT _ermrest.model_version_bump();
""")

def constraint_exists(cur, constraintname):
    cur.execute("SELECT * FROM pg_catalog.pg_constraint WHERE conname = %s" % sql_literal(constraintname))
    return cur.rowcount > 0

def view_exists(cur, schemaname, tablename):
    """Return True or False depending on whether (schema.)tablename view exists in our database."""

    cur.execute("""
SELECT True 
FROM pg_namespace nc, pg_class c
WHERE c.relnamespace = nc.oid 
  AND nc.nspname::text = %(schema)s
  AND c.relname::text = %(table)s
  AND c.relkind IN ('v'::"char", 'm'::"char") 
  AND NOT pg_is_other_temp_schema(nc.oid) 
  AND (pg_has_role(c.relowner, 'USAGE'::text) 
     OR has_table_privilege(c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text) 
     OR has_any_column_privilege(c.oid, 'SELECT, INSERT, UPDATE, REFERENCES'::text))
"""
                % dict(schema=sql_literal(schemaname),
                       table=sql_literal(tablename))
    )
    exists = cur.rowcount > 0
    return exists

def sql_identifier(s):
    # double " to protect from SQL
    return '"%s"' % (s.replace('"', '""'))

def sql_literal(v):
    if type(v) is list:
        return 'ARRAY[%s]' % (','.join(map(sql_literal, v)))
    elif v is not None:
        # double ' to protect from SQL
        s = '%s' % v
        return "'%s'" % (s.replace("'", "''"))
    else:
        return 'NULL'

def random_name(prefix=''):
    """Generates and returns a random name in URL-safe base64 minus '=' padding.

       An optional prefix is prepended to the random bits.  The random
       bits are encoded using base64 so the suffix characters will be
       drawn from 'a'-'z', 'A'-'Z', '0'-'9', '-', and '_'.

    """
    # TODO: trim out uuid version 4 static bits?  Is 122 random bits overkill?
    return prefix + base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().replace('=','')

def service_features():
    return {
        "trs": True,
        "tcrs": True,
        "history_control": True,
        "implicit_fkey_index": True,
        "catalog_post_input": True,
        "catalog_alias": True,
        "indexing_preferences": {
            "btree": True,
            "btree_column_list": True,
            "trgm": True,
            "gin_array": True,
        },
        "quantified_value_lists": True,
        "quantified_rid_lists": True,
        "rid_lease": True,
        "registry_catalog": True,
        "csv_array_json": True,
        "index_management": {
            "btree": True,
            "btree_column_list": True,
            "trgm": True,
            "gin_array": True,
        },
    }

class OrderedFrozenSet (collections.abc.Set):
    """Similar to a regular frozenset but remembers order of input iterable of members.
    """
    def __init__(self, iterable):
        super(OrderedFrozenSet, self).__init__()
        self._members = tuple(iterable)
        self._members_set = frozenset(iterable)

    def __contains__(self, x): return x in self._members_set
    def __iter__(self): return iter(self._members)
    def __len__(self): return len(self._members_set)
    def __le__(self, other): return self._members_set <= other
    def __ge__(self, other): return self._members_set >= other
    def __hash__(self): return hash(self._members_set)
    def __repr__(self): return '<%s(%r)>' % (type(self).__name__, self._members)

class OrderedFrozenDict (collections.abc.Mapping):
    """Analogous to OrderedFrozenSet, hashable but with preserved ordered dict content.
    """
    def __init__(self, mapping):
        super(OrderedFrozenDict, self).__init__()
        self._mapping = dict(mapping)
        self._frozen = frozenset(self._mapping.items())

    def __iter__(self): return iter(self._mapping)
    def __len__(self): return len(self._mapping)
    def __getitem__(self, k): return self._mapping[k]
    def __hash__(self): return hash(self._frozen)
    def __repr__(self): return '<%s(%r)>' % (type(self).__name__, self._mapping)
