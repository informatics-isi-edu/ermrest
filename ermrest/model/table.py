
# 
# Copyright 2013-2018 University of Southern California
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

from .. import exception, ermpath
from ..util import sql_identifier, sql_literal, udecode, table_exists
from .misc import AltDict, Annotatable, HasAcls, HasDynacls, cache_rights, enforce_63byte_id, sufficient_rights, get_dynacl_clauses
from .column import Column, FreetextColumn, HistColumnLazy, LiveColumnLazy
from .key import Unique, ForeignKey, KeyReference

import urllib
import json
import web

@Annotatable.annotatable
@HasDynacls.hasdynacls
@HasAcls.hasacls
class Table (HasDynacls, HasAcls, Annotatable):
    """Represents a database table.
    
    At present, this has a 'name' and a collection of table 'columns'. It
    also has a reference to its 'schema'.
    """
    _model_restype = 'table'
    _model_keying = {
        "table_rid": ('text', lambda self: self.rid)
    }

    _acls_supported = { "owner", "enumerate", "write", "insert", "update", "delete", "select" }
    _acls_rights = { "owner", "insert", "update", "delete", "select" }

    dynacl_types_supported = { "owner", "update", "delete", "select" }

    tag_indexing_preferences = 'tag:isrd.isi.edu,2018:indexing-preferences'

    def __init__(self, schema, name, columns, kind, comment=None, annotations={}, acls={}, dynacls={}, rid=None, add_to_model=True):
        super(Table, self).__init__()
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
                ",".join([unicode(c.name) for c in k]), self.name)
            )
        )
        self.fkeys = AltDict(
            lambda k: exception.ConflictModel(
                u"Requested foreign-key %s does not exist in table %s." % (
                    ",".join([unicode(c.name) for c in k]), self)
            )
        )
        self.annotations.update(annotations)
        self.acls.update(acls)
        self.dynacls.update(dynacls)

        for c in columns:
            self.columns[c.name] = c
            c.table = self

        if add_to_model and name not in self.schema.tables:
            self.schema.tables[name] = self

    def _annotation_key_error(self, key):
        return exception.NotFound(u'annotation "%s" on table %s' % (k, self))

    def _acls_getparent(self):
        return self.schema

    def __str__(self):
        return ':%s:%s' % (
            urllib.quote(unicode(self.schema.name).encode('utf8')),
            urllib.quote(unicode(self.name).encode('utf8'))
            )

    def __repr__(self):
        return '<ermrest.model.Table %s>' % str(self)

    @cache_rights
    def has_right(self, aclname, roles=None):
        # we need parent enumeration too
        if not self.schema.has_right('enumerate', roles):
            return False
        # a table without history is not enumerable during historical access
        if web.ctx.ermrest_history_snaptime is not None:
            if not table_exists(web.ctx.ermrest_catalog_pc.cur, '_ermrest_history', 't%s' % self.rid):
                return False
        return HasAcls.has_right(self, aclname, roles)

    def columns_in_order(self):
        cols = [ c for c in self.columns.values() if c.has_right('enumerate') ]
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

    def check_primary_keys(self, require):
        try:
            self.check_system_columns()
            if frozenset([self.columns['RID']]) not in self.uniques:
                raise exception.ConflictModel('Column "%s"."RID" lacks uniqueness constraint.' % self.name)
        except exception.ConflictModel as te:
            if not require:
                # convert error to warning in log
                web.debug('WARNING: %s' % te)
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

    @staticmethod
    def create_fromjson(conn, cur, schema, tabledoc, ermrest_config):
        sname = tabledoc.get('schema_name', unicode(schema.name))
        if sname != unicode(schema.name):
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
        if not schema.has_right('owner'):
            table.acls['owner'] = [web.ctx.webauthn2_context.client] # so enforcement won't deny next step...
            table.set_acl(cur, 'owner', [web.ctx.webauthn2_context.client])

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
        table.rid = cur.next()[0]

        table.set_annotations(conn, cur, annotations)
        table.set_acls(cur, acls)

        def execute_if(sql):
            if sql:
                try:
                    cur.execute(sql)
                except:
                    web.debug('Got error executing SQL: %s' % sql)
                    raise

        cur.execute("""
SELECT
  "RID",
  column_num, 
  column_name
FROM _ermrest.known_columns
WHERE table_rid = %s
ORDER BY column_num;
""" % sql_literal(table.rid))
        for row, column in zip(cur, columns):
            assert row[2] == column.name
            column.rid, column.column_num = row[0:2]
            if column.comment is not None:
                column.set_comment(conn, cur, column.comment)
            column.set_annotations(conn, cur, column.annotations)
            column.set_acls(cur, column.acls)

        for keydoc in tabledoc.get('keys', []):
            for key in table.add_unique(conn, cur, keydoc):
                # need to drain this generating function
                pass

        for column in columns:
            try:
                execute_if(column.btree_index_sql())
                execute_if(column.pg_trgm_index_sql())
            except Exception, e:
                web.debug(table, column, e)
                raise

        fkr_dynacls = {}
        for fkeydoc in tabledoc.get('foreign_keys', []):
            if not isinstance(fkeydoc, dict):
                raise exception.BadData("Foreign key documents must be JSON objects.")
            dynacls_doc = fkeydoc.pop('acl_bindings', {})
            for fkr in table.add_fkeyref(conn, cur, fkeydoc):
                # need to drain this generating function
                fkr_dynacls[fkr] = dynacls_doc

        # defer dynacls which may depend on columns and foreign keys...
        table.set_dynacls(cur, dynacls)
        for column in columns:
            column.set_dynacls(cur, column.dynacls)
        for fkr, _dynacls in fkr_dynacls:
            fkr.set_dynacls(cur, _dynacls)

        try:
            table.check_primary_keys(ermrest_config.get('require_primary_keys', True))
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
        column.rid, column.column_num = cur.next()
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
        if web.ctx.ermrest_history_snaptime is not None:
            if not table_exists(web.ctx.ermrest_catalog_pc.cur, '_ermrest_history', 't%s' % self.rid):
                raise exception.ConflictModel(u'Historical data not available for table %s.' % unicode(self.name))
            tsql = """
(SELECT %(projs)s
 FROM %(htable)s h,
 LATERAL jsonb_to_record(h.rowdata) r(%(jfields)s)
 WHERE h.during @> %(when)s::timestamptz )
""" % {
    'projs': ','.join([
        c.type.history_projection(c)
        for c in self.columns_in_order()
    ]),
    'jfields': ','.join([
        c.type.history_unpack(c)
        for c in self.columns_in_order()
        if c.type.history_unpack(c)
    ]),
    'htable': "_ermrest_history.%s" % sql_identifier("t%s" % self.rid),
    'when': sql_literal(web.ctx.ermrest_history_snaptime),
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

class HistTableLazy (Table):
    def __init__(self, schema, rid, name, kind, coldocs, comment, acls, annotations, rights):
        Table.__init__(self, schema, name, self._columns_from_coldocs(schema, name, coldocs), kind, comment, annotations, acls, rid=rid, add_to_model=False)
        self.rights = dict(rights)

    _get_column_cls = HistColumnLazy
        
    def has_right(self, aclname):
        return self.rights[aclname]

    @classmethod
    def _columns_from_coldocs(cls, schema, table_name, coldocs):
        columns = []
        for cpos in range(len(coldocs)):
            cdoc = coldocs[cpos]
            try:
                ctype = schema.model.typesengine.lookup(cdoc["type_rid"], cdoc["column_default"], True)
            except ValueError:
                raise ValueError('Disallowed type "%s" requested for column "%s"."%s"."%s"' % (
                    schema.model.typesengine.disallowed_by_rid(cdoc["type_rid"]),
                    schema.name,
                    table_name,
                    cdoc["column_name"],
                ))
            try:
                default = ctype.default_value(cdoc["column_default"])
            except ValueError:
                default = None
            columns.append(
                cls._get_column_cls(
                    cdoc["RID"],
                    cdoc["column_name"],
                    cpos,
                    ctype,
                    default,
                    not cdoc["not_null"],
                    cdoc["comment"],
                    cdoc["column_num"],
                    cdoc["annotations"],
                    cdoc["acls"],
                    cdoc["rights"],
                )
            )
        return columns

class LiveTableLazy (HistTableLazy):
    _get_column_class = LiveColumnLazy

