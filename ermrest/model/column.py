
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

import urllib
import json
import re
from webauthn2.util import deriva_ctx, deriva_debug

from .. import exception
from ..util import sql_identifier, sql_literal
from .type import tsvector_type, Type
from .misc import AltDict, AclDict, DynaclDict, keying, annotatable, cache_rights, hasacls, hasdynacls, make_id, sufficient_rights, get_dynacl_clauses

@annotatable
@hasdynacls({ "owner", "update", "delete", "select" })
@hasacls(
    {"enumerate", "write", "insert", "update", "select"},
    {"insert", "update", "select", "delete"},
    lambda self: self.table
)
@keying('column', {"column_rid": ('text', lambda self: self.rid)})
class Column (object):
    """Represents a table column.
    
    Its fields include:
     -- name: the name of the columns
     -- position: its ordinal position in the table
     -- type: the type
     -- default_value: a kludgy attempt at translating the raw default 
                       value for this column
    
    It also has a reference to its 'table'.
    """
    
    def __init__(self, name, position, type, default_value, nullok=None, comment=None, column_num=None, annotations={}, acls={}, dynacls={}, rid=None):
        self.table = None
        self.name = name
        self.position = position
        self.column_num = column_num # postgres column_num
        self.rid = rid
        self.type = type
        self.default_value = default_value
        self.nullok = nullok if nullok is not None else True
        self.comment = comment
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on column %s' % (k, self)))
        self.annotations.update(annotations)
        self.acls = AclDict(self)
        self.acls.update(acls)
        self.dynacls = DynaclDict(self)
        self.dynacls.update(dynacls)

    def set_comment(self, conn, cur, comment):
        """Set SQL comment."""
        if not isinstance(comment, (str, type(None))):
            raise exception.BadData('Model comment "%s" must be a string or null' % (comment,))
        self.enforce_right('owner')
        cur.execute("""
COMMENT ON COLUMN %(sname)s.%(tname)s.%(cname)s IS %(comment)s;
UPDATE _ermrest.known_columns c
SET "comment" = %(comment)s
WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % dict(
    sname=sql_identifier(self.table.schema.name),
    tname=sql_identifier(self.table.name),
    rid=sql_literal(self.rid),
    cname=sql_identifier(self.name),
    comment=sql_literal(comment)
)
        )
        self.comment = comment

    def __str__(self):
        return ':%s:%s:%s' % (
            urllib.parse.quote(self.table.schema.name),
            urllib.parse.quote(self.table.name),
            urllib.parse.quote(self.name),
            )

    @cache_rights
    def has_right(self, aclname, roles=None):
        if self.name in {'RMT', 'RMB'} and aclname in {'insert', 'update', 'write'}:
            return False
        if self.name in {'RID', 'RCB'} and aclname in {'update', 'write'}:
            return False
        if self.table.has_right(aclname, roles) is False:
            return False
        return self._has_right(aclname, roles)

    def has_data_right(self, aclname, roles=None):
        return self.has_right(aclname, roles)

    def enforce_data_right(self, aclname, require_true=False):
        decision = self.has_data_right(aclname)
        if decision is False or require_true and not decision:
            raise exception.Forbidden('%s access on %s' % (aclname, self))

    def __repr__(self):
        return '<ermrest.model.Column %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def is_star_column(self):
        return False

    def istext(self):
        # we can force casting everythign to text for searching...
        return True

    def is_array(self):
        return self.type.is_array

    def is_indexable(self):
        return str(self.type) != 'json'

    def want_index(self, index_type, default=True):
        """Return True if we prefer to have index, False if not."""
        def get_prefs(*subjects):
            preferences = dict()
            for subject in subjects:
                subject_prefs = subject.annotations.get(self.table.tag_indexing_preferences, {})
                if not isinstance(subject_prefs, dict):
                    deriva_debug('WARNING: ignoring invalid indexing preferences on %s' % subject)
                preferences.update(subject_prefs)
            return preferences

        preferences = get_prefs(self.table.schema.model, self.table.schema, self.table, self)
        want = preferences.get(index_type, default)

        if isinstance(want, list):
            # always build custom index spec
            return want
        elif index_type == 'btree':
            for unique in self.table.uniques.values():
                if self not in unique.columns:
                    continue
                if next(iter(unique.columns)) is self:
                    # can use UNIQUE btree(self, ...)
                    return False
            for colset, fk in self.table.fkeys.items():
                if self not in colset:
                    continue
                for fkr in fk.references.values():
                    fk_cols, pk_cols = fkr._fk_pk_cols_ordered()
                    if fk_cols[0] is self:
                        # as lead column for fkey, build fkey index
                        return [ c.name for c in fk_cols ]
        # default handling
        return want

    def btree_index_sql(self):
        """Return SQL to construct a single-column btree index or None if not necessary.

           An index is not necessary if the column forms a
           single-column key already and therefore has an implicitly
           created index.

        """
        want = self.want_index('btree')

        if not self.is_indexable():
            return None

        if not want:
            return None

        cols = [ self ]
        if isinstance(want, list):
            try:
                cols = [ self.table.columns[cname] for cname in want ]
            except KeyError:
                deriva_debug('WARNING: using default column index for %s due to invalid custom btree index spec %r' % (self, want))

        return """
DROP INDEX IF EXISTS %(schema)s.%(index)s ;
DROP INDEX IF EXISTS %(schema)s.%(index2)s ;
CREATE INDEX %(index2)s ON %(schema)s.%(table)s ( %(columns)s ) ;
""" % {
    "schema": sql_identifier(self.table.schema.name),
    "table": sql_identifier(self.table.name),
    "columns": ', '.join([ sql_identifier(c.name) for c in cols ]),
    "index": sql_identifier(make_id(self.table.name, self.name, 'idx')),
    "index2": sql_identifier(make_id(self.table.name, [ c.name for c in cols ], 'idx')),
}

    def pg_gin_opclass_index_sql(self, opclass, val_template=None):
        """Return SQL to construct GIN index w/ opclass or None if not necessary.

        """
        idx_val = self.sql_name()
        if val_template:
            idx_val = val_template % (idx_val,)

        idx_name_part = {
            'gin_trgm_ops': 'pgtrgm',
            'array_ops': 'arr',
        }.get(opclass, opclass)
        return """
DROP INDEX IF EXISTS %(schema)s.%(index)s ;
CREATE INDEX %(index)s ON %(schema)s.%(table)s USING gin ( %(index_val)s %(opclass)s ) ;
""" % dict(schema=sql_identifier(self.table.schema.name),
           table=sql_identifier(self.table.name),
           index_val=idx_val,
           index=sql_identifier(make_id(self.table.name, self.name, idx_name_part, 'idx')),
           opclass=opclass,
       )

    def pg_trgm_index_sql(self):
        """Return SQL to construct single-column tri-gram index or None if not necessary.

           An index is not necessary if the column is not a textual
           column.

        """
        if self.istext() and self.want_index('trgm'):
            return self.pg_gin_opclass_index_sql('gin_trgm_ops', '_ermrest.astext(%s)')
        else:
            return None

    def pg_gin_array_index_sql(self):
        """Return SQL to construct single-column GIN array index or None if not necessary.

        """
        if self.is_array() and self.want_index('gin_array', default=False):
            return self.pg_gin_opclass_index_sql('array_ops')
        else:
            return None

    def sql_def(self):
        """Render SQL column clause for managed table DDL."""
        parts = [
            sql_identifier(self.name),
            self.type.sql()
            ]
        if self.default_value is not None:
            parts.append('DEFAULT %s' % self.type.sql_literal(self.default_value))
        if self.nullok is False:
            parts.append('NOT NULL')
        return ' '.join(parts)

    def input_ddl(self, alias=None, enforce_notnull=True):
        """Render SQL column clause for temporary input table DDL."""
        if alias:
            name = alias
        else:
            name = self.name
        return u"%s %s %s" % (
            sql_identifier(name),
            self.type.sql(basic_storage=True),
            "NOT NULL" if self.nullok is False and enforce_notnull else ""
            )

    def update(self, conn, cur, columndoc, ermrest_config):
        """Idempotently update existing column state on part-by-part basis.

        The parts to update can be made sparse by excluding any of the
        mutable fields from the input columndoc:

        - 'name'
        - 'type'
        - 'nullok'
        - 'default'
        - 'comment'
        - 'acls'
        - 'acl_bindings'
        - 'annotations'

        An absent field will retain its current state from the
        existing column in the model. To be clear, "absent" means the
        field key is not present in the input document. Presence with
        an empty value such as `"default": null` or `"acls": {}` 
        will mutate the model aspect to reach that state.

        """
        self.enforce_right('owner')
        # allow sparse update documents as a (not so restful) convenience
        newdoc = self.prejson()
        # use existing Type rather than serializing and recreating
        # as the existing type might be a "readonly" type
        newdoc['type'] = self.type
        newdoc.update(columndoc)
        newcol = Column.fromjson_single(newdoc, self.position, ermrest_config)
        actions = []
        persists = []

        def enforce_nonsyscol(access):
            if self.name in {'RID','RCT','RMT','RCB','RMB'}:
                raise exception.Forbidden('%s on %s' % (access, self))

        if self.type.name != newcol.type.name:
            enforce_nonsyscol('Alter type = %s' % newcol.type.name)
            actions.append('SET DATA TYPE %s USING %s::%s' % (
                newcol.type.sql(),
                sql_identifier(self.name),
                newcol.type.sql(basic_storage=True)
            ))
            persists.append('type_rid')

        if self.nullok != newcol.nullok:
            enforce_nonsyscol('Alter nullok = %s' % newcol.nullok)
            actions.append('%s NOT NULL' % ('DROP' if newcol.nullok else 'SET'))
            persists.append('not_null')

        if self.default_value != newcol.default_value:
            enforce_nonsyscol('Alter default = %s' % newcol.default_value)
            if newcol.default_value is None:
                actions.append('DROP DEFAULT')
            else:
                actions.append('SET DEFAULT %s' % self.type.sql_literal(newcol.default_value))
            persists.append('column_default')

        if actions:
            actions = [
                'ALTER COLUMN %s %s' % (sql_identifier(self.name), action)
                for action in actions
            ]

            self.table.alter_table(
                conn, cur,
                ', '.join(actions),
                """
UPDATE _ermrest.known_columns ec
SET %(persists)s
FROM _ermrest.introspect_columns nc
WHERE ec."RID" = %(rid)s
  AND ec.table_rid = nc.table_rid
  AND ec.column_name = nc.column_name
  AND ec.column_num = nc.column_num
""" % {
    'rid': sql_literal(self.rid),
    'persists': ', '.join([
        '%(cname)s = nc.%(cname)s' % { 'cname': cname }
        for cname in persists
    ]),
}
            )

        if self.comment != newcol.comment:
            self.set_comment(conn, cur, newcol.comment)

        if self.annotations != newcol.annotations:
            self.set_annotations(conn, cur, newcol.annotations)

        if self.acls != newcol.acls:
            self.set_acls(cur, newcol.acls)

        if self.dynacls != newcol.dynacls:
            self.set_dynacls(cur, newcol.dynacls)

        # column rename cannot be combined with other actions above
        # and must be done after we finish running any SQL or DDL using old column name
        if self.name != newcol.name:
            self.table.alter_table(
                conn, cur,
                'RENAME COLUMN %s TO %s' % (
                    sql_identifier(self.name),
                    sql_identifier(newcol.name),
                ),
                """
UPDATE _ermrest.known_columns ec
SET column_name = %(cname)s
WHERE ec."RID" = %(rid)s;
""" % {
    'rid': sql_literal(self.rid),
    'cname': sql_literal(newcol.name),
}
            )

        newcol.rid = self.rid
        newcol.table = self.table
        return newcol

    @staticmethod
    def fromjson_single(columndoc, position, ermrest_config):
        try:
            cname = columndoc['name']
            ctype = columndoc['type']
            nullok = columndoc.get('nullok', True)

            if not isinstance(ctype, Type):
                ctype = Type.fromjson(ctype, ermrest_config)

            if cname in {'RID','RCT','RMT','RCB','RMB'}:
                constructor = SystemColumn
                if ctype.name != ('ermrest_%s' % cname.lower()):
                    raise exception.BadData('System column %s cannot have type %s.' % (cname, ctype.name))
                if cname in {'RID','RCT','RMT'} and nullok:
                    raise exception.BadData('System column %s cannot have nullok=True.' % cname)
            else:
                constructor = Column

            return constructor(
                cname,
                position,
                ctype,
                columndoc.get('default'),
                nullok,
                columndoc.get('comment'),
                None, # column_num
                columndoc.get('annotations', {}),
                columndoc.get('acls', {}),
                columndoc.get('acl_bindings', {}),
                None, # rid
            )
        except KeyError as te:
            raise exception.BadData('Table document missing required field "%s"' % te)

    @staticmethod
    def fromjson(columnsdoc, ermrest_config):
        columns = []
        if not isinstance(columnsdoc, list):
            raise exception.BadData('Table column_definitions document must be an array.')
        for i in range(0, len(columnsdoc)):
            columns.append(Column.fromjson_single(columnsdoc[i], i, ermrest_config))
        return columns

    def prejson(self):
        doc = {
            "RID": self.rid,
            "name": self.name,
            "rights": self.rights(),
            "type": self.type.prejson(),
            "default": self.default_value,
            "nullok": self.nullok,
            "comment": self.comment,
            "annotations": self.annotations
        }
        if self.has_right('owner'):
            doc['acls'] = self.acls
            doc['acl_bindings'] = self.dynacls
        return doc

    def prejson_ref(self):
        return dict(
            schema_name=self.table.schema.name,
            table_name=self.table.name,
            column_name=self.name
            )

    def dynauthz_restricted(self, access_type='select'):
        """Return True if the policy check for column involves dynacls more restrictive than table."""
        if self.has_right(access_type):
            # column statically allows so is not restrictive
            return False
        if self.table.has_right(access_type):
            # column has dynacls while table does not
            return True
        for aclname in self.table.dynacls:
            if aclname in self.dynacls:
                # column overrides a table-level dynacl
                return True
        # column inherits all table-level dynacls so is equal or more permissive
        return False

    def sql_name_dynauthz(self, talias, dynauthz, access_type='select'):
        """Generate SQL representing this column for use as a SELECT clause.

           dynauthz: dynamic authorization mode to compile
               True: compile positive ACL... column value or NULL if unauthorized
               False: compile negative ACL... True if unauthorized, else False

           access_type: the access type to be enforced for dynauthz

           The result is a select clause for dynauthz=True, scalar for dynauthz=False.
        """
        csql = sql_identifier(self.name)

        # effective dynacls is inherited table dynacls overridden by local dynacls
        dynacls = dict(self.table.dynacls)
        dynacls.update(self.dynacls)
        clauses = get_dynacl_clauses(self, access_type, talias, dynacls)

        if self.has_right(access_type) is None:
            if dynauthz:
                if self.dynauthz_restricted(access_type):
                    # need to enforce more restrictive column policy
                    return "CASE WHEN %s THEN %s ELSE NULL::%s END AS %s" % (
                        ' OR '.join(["(%s)" % clause for clause in clauses ]),
                        csql,
                        self.type.sql(basic_storage=True),
                        sql_identifier(self.name)
                    )
                else:
                    # optimization: row-level access has been checked
                    pass
            else:
                return '(%s)' % ' AND '.join("COALESCE(NOT (%s), True)" % clause for clause in clauses)

        return '%s AS %s' % (csql, sql_identifier(self.name))

    def sql_name(self, alias=None):
        if alias:
            return sql_identifier(alias)
        else:
            return sql_identifier(self.name)

    def sql_name_astext_with_talias(self, talias):
        name = '%s%s' % (talias + '.' if talias else '', self.sql_name())
        return '_ermrest.astext(%s)' % name

class SystemColumn (Column):
    """Represents system columns with special access rules.
    """
    def __init__(self, name, position, type, default_value, nullok=None, comment=None, column_num=None, annotations={}, acls={}, dynacls={}, rid=None):
        Column.__init__(self, name, position, type, default_value, nullok, comment, column_num, annotations, acls, dynacls, rid)

    def has_data_right(self, aclname, roles=None):
        if self.name in {'RID', 'RCB', 'RCT'} and aclname == 'insert':
            if self.table.schema.model.has_right('owner', roles):
                return True # catalog owner can clone RID, RCT, RCB
            elif self.name == 'RID':
                return None # others may use ERMrest_RID_Lease
            else:
                return False
        elif aclname in {'owner', 'insert', 'update'}:
            return False
        return self.has_right(aclname, roles)

    def sql_def(self):
        """Render SQL column clause for managed table DDL."""
        return "%(cname)s %(ctype)s %(notnull)s DEFAULT %(default)s" % {
            'cname': sql_identifier(self.name),
            'ctype': self.type.sql(),
            'notnull': '' if self.nullok else 'NOT NULL',
            'default': {
                'RID': "_ermrest.urlb32_encode(nextval('_ermrest.rid_seq'))",
                'RCT': "now()",
                'RMT': "now()",
                'RCB': "_ermrest.current_client()",
                'RMB': "_ermrest.current_client()",
            }[self.name]
        }

class FreetextColumn (Column):
    """Represents virtual table column for free text search.

       This is a tsvector computed by appending all text-type columns
       as a document, sorted by column order.
    """
    
    def __init__(self, table):
        Column.__init__(self, '*', None, tsvector_type, None)

        self.table = table
        
        self.srccols = [ c for c in table.columns.values() if c.istext() and c.has_right('enumerate') ]
        self.srccols.sort(key=lambda c: c.position)

    def sql_name_astext_with_talias(self, talias):
        return self.sql_name_with_talias(talias)
        
    def sql_name_with_talias(self, talias, output=False):
        if output:
            # output column reference as whole-row nested record
            return 'row_to_json(%s*)' % (talias + '.' if talias else '')
        else:
            # internal column reference for predicate evaluation
            colnames = [ c.sql_name_astext_with_talias(talias) for c in self.srccols ]
            if not colnames:
                colnames = [ "NULL::text" ]
            return set(colnames)

    def is_star_column(self):
        return True

    def textsearch_index_sql(self):
        # drop legacy index
        return """
DROP INDEX IF EXISTS %(schema)s.%(index)s ;
""" % dict(
    schema=sql_identifier(self.table.schema.name),
    index=sql_identifier(make_id(self.table.name, '_tsvector', 'idx')),
)

    def pg_trgm_index_sql(self):
        # drop legacy index
        return """
DROP INDEX IF EXISTS %(schema)s.%(index)s ;
""" % dict(
    schema=sql_identifier(self.table.schema.name),
    index=sql_identifier(make_id(self.table.name, '_pgtrgm', 'idx')),
)

