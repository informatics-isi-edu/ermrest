
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

"""
A database introspection layer.

At present, the capabilities of this module are limited to introspection of an 
existing database model. This module does not attempt to capture all of the 
details that could be found in an entity-relationship model or in the standard 
information_schema of a relational database. It represents the model as 
needed by other modules of the ermrest project.
"""

import urllib
import json
import web
from functools import reduce

from .. import exception, ermpath
from ..util import sql_identifier, sql_literal, table_exists, OrderedFrozenSet
from .misc import AltDict, AclDict, DynaclDict, keying, annotatable, cache_rights, hasacls, hasdynacls, enforce_63byte_id, sufficient_rights, get_dynacl_clauses
from .column import Column, FreetextColumn
from .key import Unique, ForeignKey, KeyReference

def _execute_if(cur, sql):
    if sql:
        try:
            cur.execute(sql)
        except:
            deriva_debug('Got error executing SQL: %s' % sql)
            raise

@annotatable
@hasdynacls(
    { "owner", "update", "delete", "select" }
)
@hasacls(
    { "owner", "enumerate", "write", "insert", "update", "delete", "select" },
    { "owner", "insert", "update", "delete", "select" },
    lambda self: self.schema
)
@keying(
    'table',
    {
        "table_rid": ('text', lambda self: self.rid)
    }
)
class Table (object):
    """Represents a database table.
    
    At present, this has a 'name' and a collection of table 'columns'. It
    also has a reference to its 'schema'.
    """
    tag_indexing_preferences = 'tag:isrd.isi.edu,2018:indexing-preferences'
    tag_history_capture = 'tag:isrd.isi.edu,2020:history-capture'
    
    def __init__(self, schema, name, columns, kind, comment=None, annotations={}, acls={}, dynacls={}, rid=None):
        self.schema = schema
        self.name = name
        self.rid = rid
        self.kind = kind
        self.comment = comment
        self.columns = AltDict(
            lambda k: exception.ConflictModel(u"Requested column %s does not exist in table %s." % (k, self.name)),
            lambda k, v: enforce_63byte_id(k, "Column")
        )
        self.uniques = AltDict(
            lambda k: exception.ConflictModel(u"Requested key %s does not exist in table %s." % (
                ",".join([c.name for c in k]), self.name)
            )
        )
        self.fkeys = AltDict(
            lambda k: exception.ConflictModel(
                u"Requested foreign-key %s does not exist in table %s." % (
                    ",".join([c.name for c in k]), self)
            )
        )
        self.annotations = AltDict(
            lambda k: exception.NotFound(u'annotation "%s" on table %s' % (k, self))
        )
        self.annotations.update(annotations)
        self.acls = AclDict(self)
        self.acls.update(acls)
        self.dynacls = DynaclDict(self)
        self.dynacls.update(dynacls)

        for c in columns:
            self.columns[c.name] = c
            c.table = self

        if name not in self.schema.tables:
            self.schema.tables[name] = self

    def __str__(self):
        return ':%s:%s' % (
            urllib.parse.quote(self.schema.name),
            urllib.parse.quote(self.name),
            )

    def __repr__(self):
        return '<ermrest.model.Table %s>' % str(self)

    @cache_rights
    def has_right(self, aclname, roles=None):
        # we need parent enumeration too
        if not self.schema.has_right('enumerate', roles):
            return False
        # a table without history is not enumerable during historical access
        if deriva_ctx.ermrest_history_snaptime is not None:
            if not table_exists(deriva_ctx.ermrest_catalog_pc.cur, '_ermrest_history', 't%s' % self.rid):
                return False
            if self.annotations.get(self.tag_history_capture, True) is False:
                return False
        return self._has_right(aclname, roles)

    def columns_in_order(self, enforce_client=True):
        cols = [ c for c in self.columns.values() if c.has_right('enumerate') or not enforce_client ]
        cols.sort(key=lambda c: c.position)
        return cols

    def has_primary_key(self):
        for k in self.uniques.values():
            if k.is_primary_key():
                return True
        return False

    def check_system_columns(self):
        for cname in {'RID','RCT','RMT','RCB','RMB'}:
            if cname not in self.columns:
                raise exception.ConflictModel('Table %s lacks required system column %s.' % (self, cname))

    def check_primary_keys(self, require, warn):
        try:
            self.check_system_columns()
            if OrderedFrozenSet([self.columns['RID']]) not in self.uniques:
                raise exception.ConflictModel('Column "%s"."RID" lacks uniqueness constraint.' % self.name)
        except exception.ConflictModel as te:
            if not require:
                if warn:
                    # convert error to warning in log
                    deriva_debug('WARNING: %s' % te)
            else:
                raise te

    def writable_kind(self):
        """Return true if table is writable in SQL.

           TODO: handle writable views some day?
        """
        if self.kind == 'r':
            return True
        return False

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def update(self, conn, cur, tabledoc, ermrest_config):
        """Idempotently update existing table state on part-by-part basis.

        The parts to update can be made sparse by excluding any of the
        mutable fields from the input tabledoc:

        - 'schema_name'
        - 'table_name'
        - 'comment'
        - 'acls'
        - 'acl_bindings'
        - 'annotations'

        An absent field will retain its current state from the
        existing table in the model. To be clear, "absent" means the
        field key is not present in the input document. Presence with
        an empty value such as `"acls": {}` will mutate the model
        aspect to reach that state.

        """
        self.enforce_right('owner')
        newtable = Table(
            self.schema,
            tabledoc.get('table_name', self.name),
            [],
            self.kind,
            tabledoc.get('comment', self.comment),
            tabledoc.get('annotations', self.annotations),
            tabledoc.get('acls', self.acls),
            tabledoc.get('acl_bindings', self.dynacls),
            self.rid,
        )

        if self.comment != newtable.comment:
            self.set_comment(conn, cur, newtable.comment)

        if self.annotations != newtable.annotations:
            self.set_annotations(conn, cur, newtable.annotations)

        if self.acls != newtable.acls:
            self.set_acls(cur, newtable.acls)

        if self.dynacls != newtable.dynacls:
            self.set_dynacls(cur, newtable.dynacls)

        if self.name != newtable.name:
            self.alter_table(
                conn, cur,
                'RENAME TO %s' % (sql_identifier(newtable.name),),
                """
UPDATE _ermrest.known_tables e
SET table_name = %(tname)s
WHERE e."RID" = %(rid)s;
""" % {
    'rid': sql_literal(self.rid),
    'tname': sql_literal(newtable.name),
}
            )

        if 'schema_name' in tabledoc and str(self.schema.name) != tabledoc['schema_name']:
            newschema = self.schema.model.schemas.get_enumerable(tabledoc['schema_name'])
            newtable.alter_table(
                conn, cur,
                'SET SCHEMA %s' % (sql_identifier(newschema.name),),
                """
UPDATE _ermrest.known_tables e
SET schema_rid = %(srid)s
WHERE e."RID" = %(trid)s;

UPDATE _ermrest.known_keys e
SET schema_rid = %(srid)s
WHERE e.table_rid = %(trid)s;

UPDATE _ermrest.known_fkeys e
SET schema_rid = %(srid)s
WHERE e.fk_table_rid = %(trid)s;
""" % {
    'trid': sql_literal(self.rid),
    'srid': sql_literal(newschema.rid),
}
            )
            # fixup in-memory model just enough to render JSON responses
            self.schema = newschema
            newtable.schema = newschema
            for k in self.uniques.values():
                k.constraint_name = (str(newschema.name), k.constraint_name[1])
            for fk in self.fkeys.values():
                for fkr in fk.references.values():
                    fkr.constraint_name = (str(newschema.name), fkr.constraint_name[1])

        newtable.uniques = self.uniques
        newtable.fkeys = self.fkeys
        for c in self.columns_in_order():
            newtable.columns[c.name] = c
            c.table = newtable

        return newtable

    @staticmethod
    def create_fromjson(conn, cur, schema, tabledoc, ermrest_config):
        sname = tabledoc.get('schema_name', schema.name)
        if sname != schema.name:
            raise exception.ConflictModel('JSON schema name %s does not match URL schema name %s' % (sname, schema.name))

        if 'table_name' not in tabledoc:
            raise exception.BadData('Table representation requires table_name field.')
        
        tname = tabledoc.get('table_name')

        if tname in schema.tables:
            raise exception.ConflictModel('Table %s already exists in schema %s.' % (tname, sname))

        kind = tabledoc.get('kind', 'table')
        if kind != 'table':
            raise exception.ConflictData('Kind "%s" not supported in table creation' % kind)

        schema.enforce_right('create')

        acls = tabledoc.get('acls', {})
        dynacls = tabledoc.get('acl_bindings', {})
        annotations = tabledoc.get('annotations', {})
        columns = Column.fromjson(tabledoc.get('column_definitions',[]), ermrest_config)
        comment = tabledoc.get('comment')
        table = Table(schema, tname, columns, 'r', comment, annotations)

        clauses = []
        for column in columns:
            clauses.append(column.sql_def())

        cur.execute("""
CREATE TABLE %(sname)s.%(tname)s (
   %(clauses)s
);
COMMENT ON TABLE %(sname)s.%(tname)s IS %(comment)s;

SELECT _ermrest.record_new_table(%(schema_rid)s, %(tnamestr)s);
""" % dict(
    schema_rid=sql_literal(schema.rid),
    sname=sql_identifier(sname),
    tname=sql_identifier(tname),
    snamestr=sql_literal(sname),
    tnamestr=sql_literal(tname),
    clauses=',\n'.join(clauses),
    comment=sql_literal(comment),
)
        )
        table.rid = cur.fetchone()[0]

        if not table.has_right('owner'):
            # client gets ownership by default
            table.acls['owner'] = [deriva_ctx.webauthn2_context.get_client_id()]
            # merge client-specified ACLs on top
            table.acls.update(acls)
            acls = table.acls.copy()

        table.set_annotations(conn, cur, annotations)
        table.set_acls(cur, acls)
        table.set_dynacls(cur, dynacls)

        cur.execute("""
SELECT
  "RID",
  column_num, 
  column_name
FROM _ermrest.known_columns
WHERE table_rid = %s
ORDER BY column_num;
""" % sql_literal(table.rid))
        rows = list(cur)
        for row, column in zip(rows, columns):
            assert row[2] == column.name
            column.rid, column.column_num = row[0:2]
            if column.comment is not None:
                column.set_comment(conn, cur, column.comment)
            column.set_annotations(conn, cur, column.annotations)
            column.set_acls(cur, column.acls)
            column.set_dynacls(cur, column.dynacls)

        for keydoc in tabledoc.get('keys', []):
            for key in table.add_unique(conn, cur, keydoc):
                # need to drain this generating function
                pass

        for fkeydoc in tabledoc.get('foreign_keys', []):
            for fkr in table.add_fkeyref(conn, cur, fkeydoc):
                # need to drain this generating function
                pass

        for column in columns:
            try:
                _execute_if(cur, column.btree_index_sql())
                _execute_if(cur, column.pg_trgm_index_sql())
                _execute_if(cur, column.pg_gin_array_index_sql())
            except Exception as e:
                deriva_debug(table, column, e)
                raise

        try:
            table.check_primary_keys(ermrest_config.get('require_primary_keys', True), ermrest_config.get('warn_missing_system_columns', True))
        except exception.ConflictModel as te:
            # convert into BadData
            raise exception.BadData(te)

        return table

    def delete(self, conn, cur):
        self.enforce_right('owner')
        cur.execute("""
DROP %(kind)s %(sname)s.%(tname)s ;
DELETE FROM _ermrest.known_tables WHERE "RID" = %(table_rid)s;
SELECT _ermrest.model_version_bump();
""" % dict(
    kind={'r': 'TABLE', 'v': 'VIEW', 'f': 'FOREIGN TABLE'}[self.kind],
    sname=sql_identifier(self.schema.name), 
    tname=sql_identifier(self.name),
    table_rid=sql_literal(self.rid),
)
        )

    def alter_table(self, conn, cur, alterclause, altermodelstmts):
        """Generic ALTER TABLE ... wrapper"""
        self.enforce_right('owner')
        cur.execute("""
SELECT _ermrest.model_version_bump();
ALTER TABLE %(sname)s.%(tname)s  %(alter)s ;
%(alter_known_model)s
""" % dict(
    sname=sql_identifier(self.schema.name), 
    tname=sql_identifier(self.name),
    alter=alterclause,
    alter_known_model=altermodelstmts,
)
        )

    def set_comment(self, conn, cur, comment):
        """Set SQL comment."""
        if not isinstance(comment, (str, type(None))):
            raise exception.BadData('Model comment "%s" must be a string or null' % (comment,))
        self.enforce_right('owner')
        cur.execute("""
COMMENT ON TABLE %(sname)s.%(tname)s IS %(comment)s;
UPDATE _ermrest.known_tables t
SET "comment" = %(comment)s
WHERE t."RID" = %(table_rid)s;
SELECT _ermrest.model_version_bump();
""" % dict(
    sname=sql_identifier(self.schema.name),
    tname=sql_identifier(self.name),
    table_rid=sql_literal(self.rid),
    comment=sql_literal(comment)
)
        )
        self.comment = comment

    def add_column(self, conn, cur, columndoc, ermrest_config):
        """Add column to table."""
        self.enforce_right('owner')
        # new column always goes on rightmost position
        position = len(self.columns)
        column = Column.fromjson_single(columndoc, position, ermrest_config)
        if column.name in self.columns:
            raise exception.ConflictModel('Column %s already exists in table %s:%s.' % (column.name, self.schema.name, self.name))
        column.table = self
        self.alter_table(
            conn, cur,
            'ADD COLUMN %s' % column.sql_def(),
            """
INSERT INTO _ermrest.known_columns (table_rid, column_num, column_name, type_rid, not_null, column_default, "comment")
SELECT table_rid, column_num, column_name, type_rid, not_null, column_default, "comment"
FROM _ermrest.introspect_columns c
WHERE table_rid = %s AND column_name = %s
RETURNING "RID", column_num;
""" % (sql_literal(self.rid), sql_literal(column.name))
        )
        column.rid, column.column_num = cur.fetchone()
        column.set_comment(conn, cur, column.comment)
        self.columns[column.name] = column
        column.table = self
        for k, v in column.annotations.items():
            column.set_annotation(conn, cur, k, v)
        for k, v in column.acls.items():
            column.set_acl(cur, k, v)
        if column.default_value is not None:
            # do this seemingly redundant UPDATE so history-tracking triggers see the new column value!
            cur.execute("""
UPDATE %(sname)s.%(tname)s SET %(cname)s = %(default)s;
""" % {
    "sname": sql_identifier(self.schema.name),
    "tname": sql_identifier(self.name),
    "cname": sql_identifier(column.name),
    "default": column.type.sql_literal(column.default_value),
}
            )
        try:
            _execute_if(cur, column.btree_index_sql())
            _execute_if(cur, column.pg_trgm_index_sql())
            _execute_if(cur, column.pg_gin_array_index_sql())
        except Exception as e:
            deriva_debug(table, column, e)
            raise
        return column

    def delete_column(self, conn, cur, cname):
        """Delete column from table."""
        self.enforce_right('owner')
        column = self.columns[cname]
        self.alter_table(
            conn, cur,
            'DROP COLUMN %s' % sql_identifier(cname),
            """
DELETE FROM _ermrest.known_columns
WHERE "RID" = %s;
""" % sql_literal(column.rid)
        )
        del self.columns[cname]
                    
    def add_unique(self, conn, cur, udoc):
        """Add a unique constraint to table."""
        self.enforce_right('owner')
        for key in Unique.fromjson_single(self, udoc):
            key.add(conn, cur)
            key.set_annotations(conn, cur, key.annotations)
            yield key

    def add_fkeyref(self, conn, cur, fkrdoc):
        """Add foreign-key reference constraint to table."""
        self.enforce_right('owner')
        for fkr in KeyReference.fromjson(self.schema.model, fkrdoc, None, self, None, None, None):
            # new foreign key constraint must be added to table
            fkr.add(conn, cur)

            fkr.set_annotations(conn, cur, fkr.annotations)
            fkr.set_acls(cur, fkr.acls, anon_mutation_ok=True)
            fkr.set_dynacls(cur, fkr.dynacls)

            fk_cols, pk_cols = fkr._fk_pk_cols_ordered()
            try:
                _execute_if(cur, fk_cols[0].btree_index_sql())
            except Exception as e:
                deriva_debug(self, fk_cols[0], e)
                raise

            yield fkr

    def prejson(self):
        doc = {
            "RID": self.rid,
            "schema_name": self.schema.name,
            "table_name": self.name,
            "rights": self.rights(),
            "column_definitions": [
                c.prejson() for c in self.columns_in_order()
            ],
            "keys": [
                u.prejson() for u in self.uniques.values() if u.has_right('enumerate')
            ],
            "foreign_keys": [
                fkr.prejson()
                for fk in self.fkeys.values() for fkr in fk.references.values() if fkr.has_right('enumerate')
            ],
            "kind": {
                'r':'table', 
                'f':'foreign_table',
                'v':'view'
            }.get(self.kind, 'unknown'),
            "comment": self.comment,
            "annotations": self.annotations
        }
        if self.has_right('owner'):
            doc['acls'] = self.acls
            doc['acl_bindings'] = self.dynacls
        return doc

    def skip_cols_dynauthz(self, access_type):
        return reduce(
            lambda x, y: x and y,
            [ not c.dynauthz_restricted(access_type) for c in self.columns_in_order() ],
            True
        )

    def sql_name(self, dynauthz=None, access_type='select', alias=None, dynauthz_testcol=None, dynauthz_testfkr=None):
        """Generate SQL representing this entity for use as a FROM clause.

           dynauthz: dynamic authorization mode to compile
               None: do not compile dynamic ACLs
               True: compile positive ACL... match rows client is authorized to access
               False: compile negative ACL... match rows client is NOT authorized to access

           access_type: the access type to be enforced for dynauthz

           dynauthz_testcol:
               None: normal mode
               col: match rows where client is NOT authorized to access column

           dynauthz_testfkr:
               None: normal mode
               fkr: compile using dynamic ACLs from fkr instead of from this table

           The result is a schema-qualified table name for dynauthz=None, else a subquery.
        """
        if deriva_ctx.ermrest_history_snaptime is not None:
            if not table_exists(deriva_ctx.ermrest_catalog_pc.cur, '_ermrest_history', 't%s' % self.rid):
                raise exception.ConflictModel(u'Historical data not available for table %s.' % self.name)
            tsql = """
(SELECT %(projs)s
 FROM %(htable)s h
 WHERE h.during @> %(when)s::timestamptz )
""" % {
    'projs': ','.join([
        c.type.history_projection(c)
        for c in self.columns_in_order(enforce_client=False)
    ]),
    'htable': "_ermrest_history.%s" % sql_identifier("t%s" % self.rid),
    'when': sql_literal(deriva_ctx.ermrest_history_snaptime),
}
        else:
            tsql = '%s.%s' % (sql_identifier(self.schema.name), sql_identifier(self.name))

        talias = alias if alias else 's'

        if dynauthz is not None:
            assert alias is not None
            assert dynauthz_testcol is None
            if dynauthz_testfkr is not None:
                assert dynauthz_testfkr.unique.table == self

            clauses = get_dynacl_clauses(self if dynauthz_testfkr is None else dynauthz_testfkr, access_type, alias)

            if dynauthz:
                skip_col_dynauthz = self.skip_cols_dynauthz(access_type)
                if ['True'] == clauses and skip_col_dynauthz:
                    # so use bare table for better query plans
                    pass
                else:
                    tsql = "(SELECT %s FROM %s %s WHERE (%s))" % (
                        '*' if skip_col_dynauthz else ', '.join([ c.sql_name_dynauthz(talias, dynauthz=True, access_type=access_type) for c in self.columns_in_order()]),
                        tsql,
                        talias,
                        ' OR '.join(["(%s)" % clause for clause in clauses ]),
                    )
            else:
                tsql = "(SELECT * FROM %s %s WHERE (%s))" % (
                    tsql,
                    talias,
                    ' AND '.join(["COALESCE(NOT (%s), True)" % clause for clause in clauses ])
                )
        elif dynauthz_testcol is not None:
            assert alias is not None
            tsql = "(SELECT * FROM %s %s WHERE (%s))" % (
                tsql,
                talias,
                dynauthz_testcol.sql_name_dynauthz(talias, dynauthz=False, access_type=access_type)
            )

        if alias is not None:
            tsql = "%s AS %s" % (tsql, sql_identifier(alias))

        return tsql

    def freetext_column(self):
        return FreetextColumn(self)

