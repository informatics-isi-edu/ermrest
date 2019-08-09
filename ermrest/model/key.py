
# 
# Copyright 2013-2019 University of Southern California
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

import web
import json

from .. import exception
from ..util import sql_identifier, sql_literal, constraint_exists
from .misc import frozendict, AltDict, AclDict, DynaclDict, keying, annotatable, cache_rights, hasacls, hasdynacls, enforce_63byte_id, truncated_identifier
from .name import _keyref_join_str, _keyref_join_sql

@annotatable
@keying('key', {"key_rid": ('text', lambda self: self.rid)})
class Unique (object):
    """A unique constraint."""
    
    def __init__(self, cols, constraint_name=None, comment=None, annotations={}, rid=None):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.rid = rid
        self.table_references = dict()
        if constraint_name is not None:
            enforce_63byte_id(constraint_name[1], 'Uniqueness constraint')
        self.constraint_name = constraint_name
        self.comment = comment
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on key %s' % (k, self.constraint_name)))
        self.annotations.update(annotations)

        if cols not in self.table.uniques:
            self.table.uniques[cols] = self

    def enforce_right(self, aclname):
        """Proxy enforce_right to self.table for interface consistency."""
        self.table.enforce_right(aclname)

    def set_comment(self, conn, cur, comment):
        if self.constraint_name:
            pk_schema, pk_name = self.constraint_name
            cur.execute("""
COMMENT ON CONSTRAINT %(constraint_name)s ON %(sname)s.%(tname)s IS %(comment)s;
UPDATE _ermrest.known_keys SET "comment" = %(comment)s WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % {
    'constraint_name': sql_identifier(pk_name),
    'sname': sql_identifier(self.table.schema.name),
    'tname': sql_identifier(self.table.name),
    'rid': sql_literal(self.rid),
    'comment': sql_literal(comment),
})
 
    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.Unique %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def sql_def(self):
        """Render SQL table constraint clause for DDL."""
        pk_schema, pk_name = self.constraint_name
        return '%(named_constraint)s UNIQUE(%(columns)s)' % {
            'named_constraint': 'CONSTRAINT %s' % sql_identifier(pk_name) if self.constraint_name else '',
            'columns': ','.join([sql_identifier(c.name) for c in self.columns]),
        }

    def is_primary_key(self):
        if not self.columns:
            return False
        for col in self.columns:
            if col.nullok:
                return False
        return True

    def _column_names(self):
        """Canonicalized column names list."""
        cnames = [ col.name for col in self.columns ]
        cnames.sort()
        return cnames
        
    def update(self, conn, cur, keydoc, ermrest_config):
        """Idempotently update existing key state on part-by-part basis.

        The parts to update can be made sparse by excluding any of the
        mutable fields from the input doc:

        - 'names'
        - 'comment'
        - 'annotations'

        An absent field will retain its current state from the
        existing column in the model. To be clear, "absent" means the
        field key is not present in the input document.

        """
        self.enforce_right('owner')
        # allow sparse update documents as a (not so restful) convenience
        newdoc = self.prejson()
        if 'names' not in keydoc \
           or not keydoc['names'][0:1] \
           or not keydoc['names'][0][1:2] \
           or not keydoc['names'][0][1]:
            del keydoc['names']
        newdoc.update(keydoc)
        newdoc['names'][0][0] = self.table.schema.name
        newkey = list(Unique.fromjson_single(self.table, newdoc, reject_duplicates=False))[0]
        newkey.rid = self.rid

        if self.columns != newkey.columns:
            raise exception.BadData('Key columns in URL and in JSON must match.')

        if self.comment != newkey.comment:
            self.set_comment(conn, cur, newkey.comment)

        if self.annotations != newkey.annotations:
            self.set_annotations(conn, cur, newkey.annotations)

        # key rename cannot be combined with other actions above
        if self.constraint_name[1] != newkey.constraint_name[1]:
            self.table.alter_table(
                conn, cur,
                'RENAME CONSTRAINT %s TO %s' % (
                    sql_identifier(self.constraint_name[1]),
                    sql_identifier(newkey.constraint_name[1]),
                ),
                """
UPDATE _ermrest.known_keys e
SET constraint_name = %(name)s
WHERE e."RID" = %(rid)s;
""" % {
    'rid': sql_literal(self.rid),
    'name': sql_literal(newkey.constraint_name[1]),
}
            )

        return newkey

    @staticmethod
    def fromjson_single(table, keydoc, reject_duplicates=True):
        """Yield Unique instance if and only if keydoc describes a key not already in table."""
        def check_names(names):
            if not names:
                return []
            for n in names:
                if type(n) is not list \
                   or len(n) != 2:
                    raise exception.BadData('Key name %s must be an 2-element array [ schema_name, constraint_name ].' % n)
                if not isinstance(n[1], str):
                    raise exception.BadData('Key constraint_name %s must be textual' % n[1])
            return names

        if not isinstance(keydoc, dict):
            raise exception.BadData('Key document must be a single object.')

        pk_namepairs = check_names(keydoc.get('names', []))
        keycolumns = []
        kcnames = keydoc.get('unique_columns', [])
        comment = keydoc.get('comment')
        annotations = keydoc.get('annotations', {})
        for kcname in kcnames:
            if kcname not in table.columns:
                raise exception.BadData('Key column %s not defined in table.' % kcname)
            keycolumns.append(table.columns[kcname])
        keycolumns = frozenset(keycolumns)

        pk_namepair = pk_namepairs[0] if pk_namepairs else None
        
        if keycolumns not in table.uniques or not reject_duplicates:
            if table.kind == 'r':
                yield Unique(keycolumns, constraint_name=pk_namepair, comment=comment, annotations=annotations)
            else:
                yield PseudoUnique(keycolumns, constraint_name=pk_namepair, comment=comment, annotations=annotations)
        else:
            raise exception.ConflictModel("Unique key %s already exists on table %s for columns %s." % (
                table.uniques[keycolumns].constraint_name[1],
                table.name,
                ','.join([ c.name for c in keycolumns]),
            ))

    @staticmethod
    def fromjson(table, keysdoc):
        for keydoc in keysdoc:
            for key in Unique.fromjson_single(table, keydoc):
                yield key

    def _constraint_name_exists(self, cur, sname, name):
        return constraint_exists(cur, name)

    def _find_new_constraint_name(self, cur, sname):
        n = 1
        while True:
            name = truncated_identifier(
                [self.table.name, '_', list(self.columns)[0].name, 'key', '%d' % n]
            )
            if not self._constraint_name_exists(cur, sname, name):
                break
            n += 1
        return (sname, name)

    def add(self, conn, cur):
        if not self.constraint_name:
            self.constraint_name = self._find_new_constraint_name(cur, self.table.schema.name)
        self.table.alter_table(
            conn, cur,
            'ADD %s' % self.sql_def(),
            """
INSERT INTO _ermrest.known_keys (oid, schema_rid, constraint_name, table_rid, "comment")
SELECT oid, schema_rid, constraint_name, table_rid, "comment"
FROM _ermrest.introspect_keys
WHERE table_rid = %(t_rid)s AND constraint_name = %(c_name)s;

INSERT INTO _ermrest.known_key_columns (key_rid, column_rid)
SELECT key_rid, column_rid
FROM _ermrest.introspect_key_columns
WHERE key_rid = (
  SELECT "RID" 
  FROM _ermrest.known_keys k
  WHERE table_rid = %(t_rid)s AND constraint_name = %(c_name)s
)
RETURNING key_rid;
""" % {
    't_rid': sql_literal(self.table.rid),
    'c_name': sql_literal(self.constraint_name[1])
})
        self.rid = cur.fetchone()[0]
        self.set_comment(conn, cur, self.comment)

    def delete(self, conn, cur):
        if self.constraint_name:
            pk_schema, pk_name = self.constraint_name
            self.table.alter_table(
                conn, cur,
                'DROP CONSTRAINT %s' % sql_identifier(pk_name),
                'DELETE FROM _ermrest.known_keys WHERE "RID" = %s;' % sql_literal(self.rid),
            )
        del self.table.uniques[self.columns]
        if web.ctx.ermrest_config.get('require_primary_keys', True) and not self.table.has_primary_key():
            raise exception.ConflictModel('Cannot remove only remaining not-null key on table %s.' % self.table)

    def prejson(self):
        return {
            'RID': self.rid,
            'comment': self.comment,
            'annotations': self.annotations,
            'unique_columns': [ c.name for c in self.columns ],
            'names': [ self.constraint_name ],
        }

    @cache_rights
    def has_right(self, aclname, roles=None):
        assert aclname == 'enumerate'
        for c in self.columns:
            # hide key if any column is non-enumerable (even if dynacl gives it None select rights)
            if not c.has_right('enumerate', roles):
                return False
        for c in self.columns:
            if c.has_right('select', roles) is False:
                return False
        return True

@annotatable
@keying('pseudo_key', {"pkey_rid": ('text', lambda self: self.rid)})
class PseudoUnique (object):
    """A pseudo-uniqueness constraint."""

    def __init__(self, cols, rid=None, constraint_name=None, comment=None, annotations={}):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.table_references = dict()
        self.rid = rid
        self.constraint_name = constraint_name
        self.comment = comment
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on key %s' % (k, self.constraint_name)))
        self.annotations.update(annotations)

        if cols not in self.table.uniques:
            self.table.uniques[cols] = self

    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.PseudoUnique %s>' % str(self)

    def update(self, conn, cur, keydoc, ermrest_config):
        """Idempotently update existing key state on part-by-part basis.

        The parts to update can be made sparse by excluding any of the
        mutable fields from the input doc:

        - 'names'
        - 'comment'
        - 'annotations'

        An absent field will retain its current state from the
        existing column in the model. To be clear, "absent" means the
        field key is not present in the input document.

        """
        self.enforce_right('owner')
        # allow sparse update documents as a (not so restful) convenience
        newdoc = self.prejson()
        if 'names' not in keydoc \
           or not keydoc['names'][0:1] \
           or not keydoc['names'][0][1:2] \
           or not keydoc['names'][0][1]:
            del keydoc['names']
        newdoc.update(keydoc)
        newdoc['names'][0][0] = self.constraint_name[0]
        newkey = list(Unique.fromjson_single(self.table, newdoc, reject_duplicates=False))[0]
        newkey.rid = self.rid

        if self.columns != newkey.columns:
            raise exception.BadData('Key columns in URL and in JSON must match.')

        if self.comment != newkey.comment:
            self.set_comment(conn, cur, newkey.comment)

        if self.annotations != newkey.annotations:
            self.set_annotations(conn, cur, newkey.annotations)

        # key rename cannot be combined with other actions above
        if self.constraint_name[1] != newkey.constraint_name[1]:
            cur.execute(
                """
SELECT _ermrest.model_version_bump();
UPDATE _ermrest.known_pseudo_keys e
SET constraint_name = %(name)s
WHERE e."RID" = %(rid)s;
""" % {
    'rid': sql_literal(self.rid),
    'name': sql_literal(newkey.constraint_name[1]),
}
            )

        return newkey

    def enforce_right(self, aclname):
        """Proxy enforce_right to self.table for interface consistency."""
        self.table.enforce_right(aclname)

    def set_comment(self, conn, cur, comment):
        if self.rid:
            cur.execute("""
UPDATE _ermrest.known_pseudo_keys SET comment = %(comment)s WHERE "RID" = %(rid)s ;
SELECT _ermrest.model_version_bump();
""" % {
    'comment': sql_literal(comment),
    'rid': sql_literal(self.rid),
})

    def is_primary_key(self):
        if not self.columns:
            return False
        for col in self.columns:
            if col.nullok:
                return False
        return True

    def _column_names(self):
        """Canonicalized column names list."""
        cnames = [ col.name for col in self.columns ]
        cnames.sort()
        return cnames
        
    def prejson(self):
        return {
            'RID': self.rid,
            'comment': self.comment,
            'annotations': self.annotations,
            'unique_columns': [ c.name for c in self.columns ],
            'names': [ self.constraint_name ],
        }

    def _constraint_name_exists(self, cur, name):
        cur.execute("""
SELECT True
FROM _ermrest.known_pseudo_keys
WHERE constraint_name = %(constraint_name)s;
""" % {
    'constraint_name': name,
})
        return cur.fetchone()[0]

    def add(self, conn, cur):
        self.table.enforce_right('owner') # since we don't use alter_table which enforces for real keys
        if not self.constraint_name:
            self.constraint_name = self._find_new_constraint_name(cur, "")
        cur.execute("""
SELECT _ermrest.model_version_bump();
INSERT INTO _ermrest.known_pseudo_keys (constraint_name, table_rid, comment)
VALUES (%(constraint_name)s, %(table_rid)s, %(comment)s)
RETURNING "RID";
""" % {
    'constraint_name': sql_literal(name),
    'table_rid': sql_literal(self.table.rid),
    'comment': sql_literal(self.comment),
})
        self.rid = cur.fetchone()[0]
        cur.execute("""
INSERT INTO _ermrest.known_pseudo_key_columns (key_rid, column_rid)
SELECT %(rid)s, c.rid FROM unnest(%(col_rids)s) c(rid);
""" % {
    'rid': sql_literal(self.rid),
    'col_rids': 'ARRAY[%s]::text[]' % (','.join([ sql_literal(c.rid) for c in self.columns ])),
})

    def delete(self, conn, cur):
        self.table.enforce_right('owner') # since we don't use alter_table which enforces for real keys
        if self.rid:
            cur.execute("""
DELETE FROM _ermrest.known_pseudo_keys WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % {
    'rid': sql_literal(self.rid),
})
        del self.table.uniques[self.columns]
        if web.ctx.ermrest_config.get('require_primary_keys', True) and not self.table.has_primary_key():
            raise exception.ConflictModel('Cannot remove only remaining not-null key on table %s.' % self.table)

    @cache_rights
    def has_right(self, aclname, roles=None):
        assert aclname == 'enumerate'
        for c in self.columns:
            # hide key if any column is non-enumerable (even if dynacl gives it None select rights)
            if not c.has_right('enumerate', roles):
                return False
        for c in self.columns:
            if c.has_right('select', roles) is False:
                return False
        return True

class ForeignKey (object):
    """A foreign key."""

    def __init__(self, cols):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.references = AltDict(lambda k: exception.ConflictModel(u"Primary key %s not referenced by foreign key %s." % (k, self)))
        self.table_references = dict()
        
        if cols not in self.table.fkeys:
            self.table.fkeys[cols] = self

    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.ForeignKey %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    @staticmethod
    def fromjson(table, refsdoc):
        fkeys = []
        for refdoc in refsdoc:
            # callee will append newly created fkeys to our list as out-variable
            fkrs = list(KeyReference.fromjson(table.schema.model, refdoc, None, table, None, None, fkeys))
        return fkeys

    def prejson(self):
        refs = []
        for krset in self.table_references.values():
            for kr in krset:
                refs.append( kr.prejson() )
        return refs

    def columns_have_right(self, aclname, roles=None):
        for c in self.columns:
            decision = c.has_right(aclname, roles)
            if not decision:
                return decision
        return True

    @cache_rights
    def has_right(self, aclname, roles=None):
        assert aclname == 'enumerate'
        if not self.columns_have_right("enumerate", roles):
            return False
        if self.columns_have_right("select", roles) is False:
            return False
        for krset in self.table_references.values():
            for kr in krset:
                if kr.has_right(aclname, roles):
                    return True
        return False

def _guarded_add(s, new_fkr, reject_duplicates=True):
    for fkr in s:
        if fkr.reference_map_frozen == new_fkr.reference_map_frozen and reject_duplicates:
            raise NotImplementedError(
                'Foreign key constraint %s collides with constraint %s on table %s.' % (
                    new_fkr.constraint_name,
                    fkr.constraint_name,
                    fkr.foreign_key.table
                )
            )
    # otherwise this is a new leader
    s.add(new_fkr)

def _keyref_from_column_names(self):
    f_cnames = [ col.name for col in self.foreign_key.columns ]
    f_cnames.sort()
    return f_cnames

def _keyref_to_column_names(self):
    return [
        self.reference_map[self.foreign_key.table.columns[colname]].name
        for colname in self._from_column_names()
    ]

def _keyref_prejson(self):
    fcs = []
    pcs = []

    def constraint_name_prejson(c):
        return [ c.constraint_name[0], c.constraint_name[1] ]
    
    for fc in self.reference_map.keys():
        fcs.append( fc.prejson_ref() )
        pcs.append( self.reference_map[fc].prejson_ref() )
    doc = {
        'RID': self.rid,
        'foreign_key_columns': fcs,
        'referenced_columns': pcs,
        'rights': self.rights(),
        'comment': self.comment,
        'annotations': self.annotations,
        'names': [ constraint_name_prejson(self) ],
    }
    if self.has_right('owner'):
        doc['acls'] = self.acls
        doc['acl_bindings'] = self.dynacls
    if self.on_delete is not None:
        doc['on_delete'] = self.on_delete
    if self.on_update is not None:
        doc['on_update'] = self.on_update
    return doc

def _keyref_rights(self):
    rights = self._rights()
    for aclname in {'insert', 'update'}:
        if rights[aclname] and web.ctx.ermrest_history_snaptime is None:
            rights[aclname] = self.foreign_key.columns_have_right(aclname)
    return rights

def _keyref_has_right(self, aclname, roles=None):
    if aclname == 'enumerate':
        if not self.unique.has_right('enumerate', roles):
            return False
        if not self.foreign_key.columns_have_right('enumerate', roles):
            return False
        decision = self.foreign_key.columns_have_right('select', roles)
        if decision is False:
            return False
        decision = self.unique.has_right(aclname, roles)
        if decision is False:
            return False
    if aclname in {'update', 'insert'} and aclname not in self.acls:
        return True
    return self._has_right(aclname, roles, anon_mutation_ok=True)

@annotatable
@hasdynacls({ "owner", "insert", "update" })
@hasacls(
    {"write", "insert", "update", "enumerate"},
    {"insert", "update"},
    lambda self: self.foreign_key.table
)
@keying('fkey', {"fkey_rid": ('text', lambda self: self.rid)})
class KeyReference (object):
    """A reference from a foreign key to a primary key."""
    
    def __init__(self, foreign_key, unique, fk_ref_map, on_delete='NO ACTION', on_update='NO ACTION', constraint_name=None, annotations={}, comment=None, acls={}, dynacls={}, rid=None, reject_duplicates=True):
        self.foreign_key = foreign_key
        self.unique = unique
        self.rid = rid
        self.reference_map_frozen = fk_ref_map
        self.reference_map = dict(fk_ref_map)
        self.referenceby_map = dict([ (p, f) for f, p in fk_ref_map ])
        self.on_delete = on_delete
        self.on_update = on_update
        # Link into foreign key's key reference list, by table ref
        if constraint_name is not None:
            enforce_63byte_id(constraint_name[1], 'Foreign-key constraint')
        self.constraint_name = constraint_name
        if unique.table not in foreign_key.table_references:
            foreign_key.table_references[unique.table] = set()
        _guarded_add(foreign_key.table_references[unique.table], self, reject_duplicates=reject_duplicates)
        if foreign_key.table not in unique.table_references:
            unique.table_references[foreign_key.table] = set()
        _guarded_add(unique.table_references[foreign_key.table], self, reject_duplicates=reject_duplicates)
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on foreign key %s' % (k, self.constraint_name)))
        self.annotations.update(annotations)
        self.acls = AclDict(self)
        self.acls.update(acls)
        self.dynacls = DynaclDict(self)
        self.dynacls.update(dynacls)
        self.comment = comment

    def set_comment(self, conn, cur, comment):
        if self.constraint_name:
            fkr_schema, fkr_name = self.constraint_name
            cur.execute("""
COMMENT ON CONSTRAINT %(constraint_name)s ON %(sname)s.%(tname)s IS %(comment)s;
UPDATE _ermrest.known_fkeys SET "comment" = %(comment)s WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % {
    'constraint_name': sql_identifier(fkr_name),
    'sname': sql_identifier(self.foreign_key.table.schema.name),
    'tname': sql_identifier(self.foreign_key.table.name),
    'rid': sql_literal(self.rid),
    'comment': sql_literal(comment),
})

    def join_str(self, refop, lname, rname):
        return _keyref_join_str(self, refop, lname, rname)

    def join_sql(self, refop, lname, rname):
        return _keyref_join_sql(self, refop, lname, rname)
    
    def __str__(self):
        return self.join_str('=@', str(self.foreign_key.table), str(self.unique.table))

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def sql_def(self):
        """Render SQL table constraint clause for DDL."""   
        fk_cols = list(self.foreign_key.columns)
        return (
            '%s FOREIGN KEY (%s) REFERENCES %s.%s (%s) %s %s' % (
                ('CONSTRAINT %s' % sql_identifier(self.constraint_name[1]) if self.constraint_name else ''),
                ','.join([ sql_identifier(fk_cols[i].name) for i in range(0, len(fk_cols)) ]),
                sql_identifier(self.unique.table.schema.name),
                sql_identifier(self.unique.table.name),
                ','.join([ sql_identifier(self.reference_map[fk_cols[i]].name) for i in range(0, len(fk_cols)) ]),
                'ON DELETE %s' % self.on_delete,
                'ON UPDATE %s' % self.on_update,
            )
        )

    def add(self, conn, cur):
        if not self.constraint_name:
            n = 1
            while True:
                name = truncated_identifier(
                    [ self.foreign_key.table.name, '_', list(self.foreign_key.columns)[0].name, '%d' % n ]
                )
                if not constraint_exists(cur, name):
                    break
                n += 1
            self.constraint_name = (self.foreign_key.table.schema.name, name)
        self.foreign_key.table.alter_table(
            conn, cur,
            'ADD %s' % self.sql_def(),
            """
INSERT INTO _ermrest.known_fkeys (oid, schema_rid, constraint_name, fk_table_rid, pk_table_rid, delete_rule, update_rule)
SELECT oid, schema_rid, constraint_name, fk_table_rid, pk_table_rid, delete_rule, update_rule
FROM _ermrest.introspect_fkeys
WHERE fk_table_rid = %(table_rid)s
  AND constraint_name = %(constraint_name)s;

INSERT INTO _ermrest.known_fkey_columns (fkey_rid, fk_column_rid, pk_column_rid)
SELECT fkey_rid, fk_column_rid, pk_column_rid
FROM _ermrest.introspect_fkey_columns fkc
WHERE fkey_rid = (
  SELECT "RID"
  FROM _ermrest.known_fkeys
  WHERE fk_table_rid = %(table_rid)s
    AND constraint_name = %(constraint_name)s
)
RETURNING fkey_rid;
""" % {
    'table_rid': sql_literal(self.foreign_key.table.rid),
    'constraint_name': sql_literal(self.constraint_name[1]),
})
        self.rid = cur.fetchone()[0]
        self.set_comment(conn, cur, self.comment)
                
    def delete(self, conn, cur):
        if self.constraint_name:
            fkr_schema, fkr_name = self.constraint_name
            self.foreign_key.table.alter_table(
                conn, cur,
                'DROP CONSTRAINT %s' % sql_identifier(fkr_name),
                'DELETE FROM _ermrest.known_fkeys WHERE "RID" = %s;' % sql_literal(self.rid),
            )

    def _from_column_names(self):
        """Canonicalized from-column names list."""
        return _keyref_from_column_names(self)
        
    def _to_column_names(self):
        """Canonicalized to-column names list."""
        return _keyref_to_column_names(self)
        
    def update(self, conn, cur, refdoc, ermrest_config):
        """Idempotently update existing fkey state on part-by-part basis.

        The parts to update can be made sparse by excluding any of the
        mutable fields from the input doc:

        - 'names'
        - 'on_update'
        - 'on_delete'
        - 'comment'
        - 'acls'
        - 'acl_bindings'
        - 'annotations'

        An absent field will retain its current state from the
        existing column in the model. To be clear, "absent" means the
        field key is not present in the input document.

        """
        self.enforce_right('owner')
        # allow sparse update documents as a (not so restful) convenience
        newdoc = self.prejson()
        refdoc = refdoc[0] if isinstance(refdoc, list) else refdoc
        newdoc.update(refdoc)
        newfkr = list(KeyReference.fromjson(
            self.foreign_key.table.schema.model,
            newdoc,
            self.foreign_key,
            self.foreign_key.table,
            self.unique,
            self.unique.table,
            reject_duplicates=False
        ))[0]
        newfkr.rid = self.rid

        # undo default ACLs generated in fromjson on acls: {} input...
        newfkr.acls.clear()
        if 'acls' in refdoc:
            newfkr.acls.update(refdoc['acls'])
        else:
            newfkr.acls.update(self.acls)

        if self.reference_map_frozen != newfkr.reference_map_frozen:
            raise exception.BadData('Foreign key column mapping in URL and in JSON must match.')

        if self.comment != newfkr.comment:
            self.set_comment(conn, cur, newfkr.comment)

        if self.annotations != newfkr.annotations:
            self.set_annotations(conn, cur, newfkr.annotations)

        if self.acls != newfkr.acls:
            self.set_acls(cur, newfkr.acls, anon_mutation_ok=True)

        if self.dynacls != newfkr.dynacls:
            self.set_dynacls(cur, newfkr.dynacls)

        if (self.on_delete != newfkr.on_delete
            or self.on_update != newfkr.on_update
            or self.constraint_name[1] != newfkr.constraint_name[1]):
            # update/delete actions cannot be altered via ALTER TABLE
            # so just recreate in-place as a brute-force solution
            self.foreign_key.table.alter_table(
                conn, cur,
                """
DROP CONSTRAINT %(constraint_name)s,
ADD %(constraint_def)s
""" % {
    "constraint_name": sql_identifier(self.constraint_name[1]),
    "constraint_def": newfkr.sql_def(),
},
                """
UPDATE _ermrest.known_fkeys e
SET oid = i.oid,
    constraint_name = i.constraint_name,
    delete_rule = i.delete_rule,
    update_rule = i.update_rule
FROM _ermrest.introspect_fkeys i
WHERE i.fk_table_rid = %(table_rid)s
  AND i.constraint_name = %(new_constraint_name)s
  AND e."RID" = %(rid)s;
""" % {
    "rid": sql_literal(self.rid),
    "table_rid": sql_literal(self.foreign_key.table.rid),
    "new_constraint_name": sql_literal(newfkr.constraint_name[1]),
})

        return newfkr

    @staticmethod
    def fromjson(model, refdoc, fkey=None, fktable=None, pkey=None, pktable=None, outfkeys=None, reject_duplicates=True):
        fk_cols = []
        pk_cols = []
        refs = []

        def check_names(names):
            if not names:
                return []
            for n in names:
                if type(n) is not list \
                   or len(n) != 2:
                    raise exception.BadData('Foreign key name %s must be an 2-element array [ schema_name, constraint_name ].' % n)
                if not isinstance(n[1], str):
                    raise exception.BadData('Foreign key constraint_name %s must be textual' % n[1])
            return names
                
        def check_columns(cols, kind):
            fksname = fktable.schema.name if fktable else None
            fktname = fktable.name if fktable else None
            def get_tname(d):
                if not isinstance(d, dict):
                    raise exception.BadRequest('Foreign key column document "%s" should be an object.' % d)
                return (d.get('schema_name', fksname), d.get('table_name', fktname))
            tnames = set([ get_tname(d) for d in cols ])
            if len(tnames) != 1:
                raise exception.BadData('All %s columns must come from one table.' % kind)
            sname, tname = tnames.pop()
            table = model.schemas[sname].tables[tname]
            def get_cname(d):
                if 'column_name' not in d:
                    raise exception.BadRequest('Foreign key column document "%s" must have field "column_name".' % d)
                return d['column_name']
            for cname in [ get_cname(d) for d in cols ]:
                if cname in table.columns:
                    yield table.columns[cname]
                else:
                    raise exception.ConflictModel('The %s column %s not defined in table.' % (kind, cname))

        def check_rule(rulename):
            action = refdoc.get(rulename)
            action = action if action is not None else 'no action'
            if action.upper() not in {'NO ACTION', 'RESTRICT', 'CASCADE', 'SET NULL', 'SET DEFAULT'}:
                raise exception.BadData('Invalid action "%s" for reference rule %s.' % (action, rulename))
            return action.upper()

        def get_colset_key_table(columns, is_fkey=True, key=None, table=None):
            if len(columns) == 0:
                raise exception.BadData('Foreign-key references require at least one column pair.')

            colset = frozenset(columns)

            if table is None:
                table = columns[0].table
            elif table != columns[0].table:
                raise exception.ConflictModel('Mismatch in tables for %s columns.' % (is_fkey and 'foreign-key' or 'referenced'))

            if key is None:
                if is_fkey:
                    if colset not in table.fkeys:
                        key = ForeignKey(colset)
                        if outfkeys is not None:
                            outfkeys.append(key)
                    else:
                        key = table.fkeys[colset]
                else:
                    if colset not in table.uniques:
                        raise exception.ConflictModel('Referenced columns %s are not part of a unique key.' % colset)
                    else:
                        key = table.uniques[colset]

            elif is_fkey and colset != fkey.columns:
                raise exception.ConflictModel(
                    'Reference map referring columns %s do not match foreign key columns %s.' 
                    % (colset, key.columns)
                    )
            elif (not is_fkey) and colset != fkey.columns:
                raise exception.ConflictModel(
                    'Reference map referenced columns %s do not match unique columns %s.' 
                    % (colset, key.columns)
                    )

            return colset, key, table

        if not isinstance(refdoc, dict):
            raise exception.BadData('Foreign-key reference document must be a single object.')

        fk_names = check_names(refdoc.get('names', []))
        fk_columns = list(check_columns(refdoc.get('foreign_key_columns', []), 'foreign-key'))
        pk_columns = list(check_columns(refdoc.get('referenced_columns', []), 'referenced'))
        annotations = refdoc.get('annotations', {})
        comment = refdoc.get('comment')
        acls = {"insert": ["*"], "update": ["*"]}
        acls.update(refdoc.get('acls', {}))
        dynacls = refdoc.get('acl_bindings', {})

        fk_colset, fkey, fktable = get_colset_key_table(fk_columns, True, fkey, fktable)
        pk_colset, pkey, pktable = get_colset_key_table(pk_columns, False, pkey, pktable)
        fk_ref_map = frozendict(dict([ (fk_columns[i], pk_columns[i]) for i in range(0, len(fk_columns)) ]))
        fk_name = fk_names[0] if fk_names else None
            
        if fk_ref_map not in fkey.references or not reject_duplicates:
            if fktable.kind == 'r' and pktable.kind == 'r':
                on_delete = check_rule('on_delete')
                on_update = check_rule('on_update')
                fkr = KeyReference(fkey, pkey, fk_ref_map, on_delete, on_update, fk_name, annotations, comment, acls, dynacls, reject_duplicates=reject_duplicates)
            else:
                fkr = PseudoKeyReference(fkey, pkey, fk_ref_map, None, fk_name, annotations, comment, acls, dynacls, reject_duplicates=reject_duplicates)
            fkey.references[fk_ref_map] = fkr
        else:
            raise exception.ConflictModel("Foreign key %s already exists from table %s to %s with reference mapping %s." % (
                fkey.references[fk_ref_map].constraint_name[1],
                fktable.name,
                pktable.name,
                ",".join([
                    "%s->%s" % (c1.name, c2.name)
                    for c1, c2 in fk_ref_map # frozendict is a sequence of items already...
                ])
            ))
        yield fkey.references[fk_ref_map]

    def prejson(self):
        return _keyref_prejson(self)

    def __repr__(self):
        return '<ermrest.model.KeyReference %s>' % str(self)

    @cache_rights
    def has_right(self, aclname, roles=None):
        return _keyref_has_right(self, aclname, roles)

    def rights(self):
        return _keyref_rights(self)

@annotatable
@hasdynacls({ "owner", "insert", "update" })
@hasacls(
    {"write", "insert", "update", "enumerate"},
    {"insert", "update"},
    lambda self: self.foreign_key.table
)
@keying('pseudo_fkey', {"fkey_rid": ('text', lambda self: self.rid)})
class PseudoKeyReference (object):
    """A psuedo-reference from a foreign key to a primary key."""
    
    def __init__(self, foreign_key, unique, fk_ref_map, rid=None, constraint_name=("", None), annotations={}, comment=None, acls={}, dynacls={}, reject_duplicates=True):
        self.foreign_key = foreign_key
        self.unique = unique
        self.reference_map_frozen = fk_ref_map
        self.reference_map = dict(fk_ref_map)
        self.referenceby_map = dict([ (p, f) for f, p in fk_ref_map ])
        self.on_delete = None
        self.on_update = None
        # Link into foreign key's key reference list, by table ref
        if unique.table not in foreign_key.table_references:
            foreign_key.table_references[unique.table] = set()
        _guarded_add(foreign_key.table_references[unique.table], self)
        if foreign_key.table not in unique.table_references:
            unique.table_references[foreign_key.table] = set()
        _guarded_add(unique.table_references[foreign_key.table], self)
        self.rid = rid
        self.constraint_name = constraint_name
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on foreign key %s' % (k, self.constraint_name)))
        self.annotations.update(annotations)
        self.acls = AclDict(self)
        self.acls.update(acls)
        self.dynacls = DynaclDict(self)
        self.dynacls.update(dynacls)
        self.comment = comment

    def set_comment(self, conn, cur, comment):
        if self.rid:
            cur.execute("""
UPDATE _ermrest.known_pseudo_fkeys SET comment = %(comment)s WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % {
    'comment': sql_literal(comment),
    'rid': sql_literal(self.rid),
})

    def join_str(self, refop, lname, rname):
        return _keyref_join_str(self, refop, lname, rname)
                
    def join_sql(self, refop, lname, rname):
        return _keyref_join_sql(self, refop, lname, rname)
    
    def __str__(self):
        return self.join_str('=@', str(self.foreign_key.table), str(self.unique.table))

    def _from_column_names(self):
        """Canonicalized from-column names list."""
        return _keyref_from_column_names(self)
        
    def _to_column_names(self):
        """Canonicalized to-column names list."""
        return _keyref_to_column_names(self)
        
    def prejson(self):
        return _keyref_prejson(self)

    def __repr__(self):
        return '<ermrest.model.KeyReference %s>' % str(self)

    def update(self, conn, cur, refdoc, ermrest_config):
        """Idempotently update existing fkey state on part-by-part basis.

        The parts to update can be made sparse by excluding any of the
        mutable fields from the input doc:

        - 'names'
        - 'comment'
        - 'acls'
        - 'acl_bindings'
        - 'annotations'

        An absent field will retain its current state from the
        existing column in the model. To be clear, "absent" means the
        field key is not present in the input document.

        """
        self.enforce_right('owner')
        # allow sparse update documents as a (not so restful) convenience
        newdoc = self.prejson()
        refdoc = refdoc[0] if isinstance(refdoc, list) else refdoc
        newdoc.update(refdoc)
        newfkr = list(KeyReference.fromjson(
            self.foreign_key.table.schema.model,
            newdoc,
            self.foreign_key,
            self.foreign_key.table,
            self.unique,
            self.unique.table,
            reject_duplicates=False
        ))[0]
        newfkr.rid = self.rid

        # undo default ACLs generated in fromjson on acls: {} input...
        newfkr.acls.clear()
        if 'acls' in refdoc:
            newfkr.acls.update(refdoc['acls'])
        else:
            newfkr.acls.update(self.acls)

        if self.reference_map_frozen != newfkr.reference_map_frozen:
            raise exception.BadData('Foreign key column mapping in URL and in JSON must match.')

        if self.comment != newfkr.comment:
            self.set_comment(conn, cur, newfkr.comment)

        if self.annotations != newfkr.annotations:
            self.set_annotations(conn, cur, newfkr.annotations)

        if self.acls != newfkr.acls:
            self.set_acls(cur, newfkr.acls, anon_mutation_ok=True)

        if self.dynacls != newfkr.dynacls:
            self.set_dynacls(cur, newfkr.dynacls)

        # key rename cannot be combined with other actions above
        if self.constraint_name[1] != newfkr.constraint_name[1]:
            cur.execute("""
SELECT _ermrest.model_version_bump();
UPDATE _ermrest.known_pseudo_fkeys e
SET constraint_name = %(name)s
WHERE e."RID" = %(rid)s;
""" % {
    'rid': sql_literal(self.rid),
    'name': sql_literal(newfkr.constraint_name[1]),
}
            )

        return newfkr

    def add(self, conn, cur):
        self.foreign_key.table.enforce_right('owner') # since we don't use alter_table which enforces for real keyrefs
        fk_cols = list(self.foreign_key.columns)
        cur.execute("""
SELECT _ermrest.model_version_bump();
INSERT INTO _ermrest.known_pseudo_fkeys (constraint_name, fk_table_rid, pk_table_rid)
VALUES (%(constraint_name)s, %(fk_table_rid)s, %(pk_table_rid)s)
RETURNING "RID";
""" % {
    'fk_table_rid': sql_literal(self.foreign_key.table.rid),
    'pk_table_rid': sql_literal(self.unique.table.rid),
    'comment': sql_literal(self.comment),
    'constraint_name': sql_literal(self.constraint_name[1]) if self.constraint_name else 'NULL',
})
        self.rid = cur.fetchone()[0]

        cur.execute("""
INSERT INTO _ermrest.known_pseudo_fkey_columns (fkey_rid, fk_column_rid, pk_column_rid) VALUES %(values)s;
""" % {
    'values': ','.join([
        '(%s, %s, %s)' % (
            sql_literal(self.rid),
            sql_literal(fk_cols[i].rid),
            sql_literal(self.reference_map[fk_cols[i]].rid),
        )
        for i in range(len(fk_cols))
    ]),
})
        self.constraint_name = ["", self.constraint_name[1] if self.constraint_name else self.rid]

    def delete(self, conn, cur):
        self.foreign_key.table.enforce_right('owner') # since we don't use alter_table which enforces for real keyrefs
        if self.rid:
            cur.execute("""
DELETE FROM _ermrest.known_pseudo_fkeys WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % {
    'rid': sql_literal(self.rid),
})

    @cache_rights
    def has_right(self, aclname, roles=None):
        return _keyref_has_right(self, aclname, roles)

    def rights(self):
        return _keyref_rights(self)
