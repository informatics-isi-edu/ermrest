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

from .. import exception
from ..util import sql_identifier, sql_literal, constraint_exists
from .misc import frozendict, AltDict, AclDict, keying, annotatable, commentable, hasacls, enforce_63byte_id, truncated_identifier

import json

@annotatable
@keying(
    'key',
    {
        "schema_name": ('text', lambda self: unicode(self.table.schema.name)),
        "table_name": ('text', lambda self: unicode(self.table.name)),
        "column_names": ('text[]', lambda self: self._column_names())
    }
)
class Unique (object):
    """A unique constraint."""
    
    def __init__(self, cols, constraint_name=None, comment=None, annotations={}):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.table_references = dict()
        if constraint_name is not None:
            enforce_63byte_id(constraint_name[1], 'Uniqueness constraint')
        self.constraint_name = constraint_name
        self.constraints = set([self])
        self.comment = comment
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on key %s' % (k, unicode(self.constraint_name))))
        self.annotations.update(annotations)

        if cols not in self.table.uniques:
            self.table.uniques[cols] = self
        
    @staticmethod
    def keyed_resource(model=None, schema_name=None, table_name=None, column_names=None):
        table = model.schemas[schema_name].tables[table_name]
        columns = [ table.columns[cname] for cname in column_names ]
        return table.uniques[frozenset(columns)]

    def enforce_right(self, aclname):
        """Proxy enforce_right to self.table for interface consistency."""
        self.table.enforce_right(aclname)

    def set_comment(self, conn, cur, comment):
        # comment this particular constraint
        if self.constraint_name:
            pk_schema, pk_name = self.constraint_name
            cur.execute("""
COMMENT ON CONSTRAINT %s ON %s.%s IS %s;
SELECT _ermrest.model_change_event();
""" % (
    sql_identifier(unicode(pk_name)),
    sql_identifier(unicode(self.table.schema.name)),
    sql_identifier(unicode(self.table.name)),
    sql_literal(comment)
)
        )
        # also update other constraints sharing same key colset
        for pk in self.constraints:
            if pk != self:
                pk.set_comment(conn, cur, comment)
 
    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.Unique %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def sql_def(self):
        """Render SQL table constraint clause for DDL."""
        return '%s UNIQUE(%s)' % (
            ('CONSTRAINT %s' % sql_identifier(self.constraint_name[1]) if self.constraint_name else ''),
            ','.join([sql_identifier(c.name) for c in self.columns]),
        )

    def _column_names(self):
        """Canonicalized column names list."""
        cnames = [ unicode(col.name) for col in self.columns ]
        cnames.sort()
        return cnames
        
    @staticmethod
    def fromjson_single(table, keydoc):
        """Yield Unique instance if and only if keydoc describes a key not already in table."""
        def check_names(names):
            if not names:
                return []
            for n in names:
                if type(n) is not list \
                   or len(n) != 2:
                    raise exception.BadData('Key name %s must be an 2-element array [ schema_name, constraint_name ].' % n)
                if type(n[1]) not in [str, unicode]:
                    raise exception.BadData('Key constraint_name %s must be textual' % n[1])
            return names

        pk_names = check_names(keydoc.get('names', []))
        keycolumns = []
        kcnames = keydoc.get('unique_columns', [])
        comment = keydoc.get('comment')
        annotations = keydoc.get('annotations', {})
        for kcname in kcnames:
            if kcname not in table.columns:
                raise exception.BadData('Key column %s not defined in table.' % kcname)
            keycolumns.append(table.columns[kcname])
        keycolumns = frozenset(keycolumns)

        pk_name = pk_names[0] if pk_names else None
        
        if keycolumns not in table.uniques:
            if table.kind == 'r':
                yield Unique(keycolumns, constraint_name=pk_name, comment=comment, annotations=annotations)
            else:
                yield PseudoUnique(keycolumns, constraint_name=pk_name, comment=comment, annotations=annotations)

    @staticmethod
    def fromjson(table, keysdoc):
        for keydoc in keysdoc:
            for key in Unique.fromjson_single(table, keydoc):
                yield key

    def pre_delete(self, conn, cur):
        """Do any maintenance before table is deleted."""
        self.delete_annotation(conn, cur, None)
        for fkeyrefset in self.table_references.values():
            for fkeyref in fkeyrefset:
                fkeyref.pre_delete(conn, cur)

    def add(self, conn, cur):
        if not self.constraint_name:
            n = 1
            while True:
                name = truncated_identifier(
                    [self.table.name, '_', list(self.columns)[0].name, '%d' % n]
                )
                if not constraint_exists(cur, name):
                    break
                n += 1
            self.constraint_name = (self.table.schema.name, name)
        self.table.alter_table(conn, cur, 'ADD %s' % self.sql_def())
        self.set_comment(conn, cur, self.comment)
        for k, v in self.annotations.items():
            self.set_annotation(conn, cur, k, v)
                
    def delete(self, conn, cur):
        self.pre_delete(conn, cur)
        if self.constraint_name:
            pk_schema, pk_name = self.constraint_name
            self.table.alter_table(conn, cur, 'DROP CONSTRAINT %s' % sql_identifier(pk_name))
        for pk in self.constraints:
            if pk != self:
                pk.delete(conn, cur)
        
    def prejson(self):
        return dict(
            comment=self.comment,
            annotations=self.annotations,
            unique_columns=[ c.name for c in self.columns ],
            names=[ [ c.constraint_name[0], c.constraint_name[1] ] for c in self.constraints ]
            )

    def has_right(self, aclname, roles=None):
        assert aclname == 'enumerate'
        for c in self.columns:
            if not c.has_right('enumerate', roles):
                return False
        return True

@annotatable
@keying(
    'key',
    {
        "schema_name": ('text', lambda self: unicode(self.table.schema.name)),
        "table_name": ('text', lambda self: unicode(self.table.name)),
        "column_names": ('text[]', lambda self: self._column_names())
    }
)
class PseudoUnique (object):
    """A pseudo-uniqueness constraint."""

    def __init__(self, cols, id=None, constraint_name=None, comment=None, annotations={}):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.table_references = dict()
        self.id = id
        self.constraint_name = constraint_name
        self.constraints = set([self])
        self.comment = comment
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on key %s' % (k, unicode(self.constraint_name))))
        self.annotations.update(annotations)

        if cols not in self.table.uniques:
            self.table.uniques[cols] = self

    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.PseudoUnique %s>' % str(self)

    def enforce_right(self, aclname):
        """Proxy enforce_right to self.table for interface consistency."""
        self.table.enforce_right(aclname)

    def set_comment(self, conn, cur, comment):
        # comment this particular constraint
        if self.id:
            cur.execute("""
UPDATE _ermrest.model_pseudo_key
SET comment = %s
WHERE id = %s ;
SELECT _ermrest.model_change_event();
""" % (
    sql_literal(comment),
    sql_literal(self.id)
)
        )
        # also update other constraints sharing same key colset
        for pk in self.constraints:
            if pk != self:
                pk.set_comment(conn, cur, comment)
 
    def _column_names(self):
        """Canonicalized column names list."""
        cnames = [ unicode(col.name) for col in self.columns ]
        cnames.sort()
        return cnames
        
    def prejson(self):
        return dict(
            comment=self.comment,
            annotations=self.annotations,
            unique_columns=[ c.name for c in self.columns ],
            names=[ [ c.constraint_name[0], c.constraint_name[1] ] for c in self.constraints ]
            )

    def pre_delete(self, conn, cur):
        """Do any maintenance before table is deleted."""
        self.delete_annotation(conn, cur, None)
        for fkeyrefset in self.table_references.values():
            for fkeyref in fkeyrefset:
                fkeyref.pre_delete(conn, cur)

    def add(self, conn, cur):
        self.table.enforce_right('owner') # since we don't use alter_table which enforces for real keys
        cur.execute("""
SELECT _ermrest.model_change_event();
INSERT INTO _ermrest.model_pseudo_key 
  (schema_name, table_name, column_names, comment, name)
  VALUES (%s, %s, ARRAY[%s], %s, %s) 
  RETURNING id;
""" % (
    sql_literal(unicode(self.table.schema.name)),
    sql_literal(unicode(self.table.name)),
    ','.join([ sql_literal(unicode(c.name)) for c in self.columns ]),
    sql_literal(self.comment),
    sql_literal(self.constraint_name[1]) if self.constraint_name else 'NULL'
)
        )
        self.id = cur.fetchone()[0]
        self.constraint_name = [
            "",
            self.constraint_name[1] if self.constraint_name else self.id
        ]
        for k, v in self.annotations.items():
            self.set_annotation(conn, cur, k, v)

    def delete(self, conn, cur):
        self.table.enforce_right('owner') # since we don't use alter_table which enforces for real keys
        self.pre_delete(conn, cur)
        if self.id:
            cur.execute("""
DELETE FROM _ermrest.model_pseudo_key WHERE id = %s;
SELECT _ermrest.model_change_event();
""" % sql_literal(self.id)
            )
        for pk in self.constraints:
            if pk != self:
                pk.delete(conn, cur)

    def has_right(self, aclname, roles=None):
        assert aclname == 'enumerate'
        for c in self.columns:
            if not c.has_right('enumerate', roles):
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

    def pre_delete(self, conn, cur):
        """Do any maintenance before foreignkey is deleted."""
        for fkeyref in self.references.values():
            fkeyref.pre_delete(conn, cur)

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
            if not c.has_right(aclname, roles):
                return False
        return True

    def has_right(self, aclname, roles=None):
        assert aclname == 'enumerate'
        if not self.columns_have_right(aclname, roles):
            return False
        for krset in self.table_references.values():
            for kr in krset:
                if kr.has_right(aclname, roles):
                    return True
        return False

def _guarded_add(s, new_fkr):
    """Deduplicate FKRs by tracking duplicates under leader.constraints if leader exists in set s.
    """
    for fkr in s:
        if fkr.reference_map_frozen == new_fkr.reference_map_frozen:
            fkr.constraints.add(new_fkr)
            return
    # otherwise this is a new leader
    s.add(new_fkr)

def _keyref_join_str(self, refop, lname, rname):
    if refop == '=@':
        lcols = self._from_column_names()
        rcols = self._to_column_names()
    else:
        lcols = self._to_column_names()
        rcols = self._from_column_names()
    return '%s:%s%s%s:%s' % (lname, ','.join(lcols), refop, rname, ','.join(rcols))

def _keyref_join_sql(self, refop, lname, rname):
    if refop == '=@':
        lcols = self._from_column_names()
        rcols = self._to_column_names()
    else:
        lcols = self._to_column_names()
        rcols = self._from_column_names()
    return ' AND '.join([
        '%s.%s = %s.%s' % (lname, sql_identifier(lcols[i]), rname, sql_identifier(rcols[i]))
        for i in range(len(lcols))
    ])

def _keyref_from_column_names(self):
    f_cnames = [ unicode(col.name) for col in self.foreign_key.columns ]
    f_cnames.sort()
    return f_cnames

def _keyref_to_column_names(self):
    return [
        unicode(self.reference_map[self.foreign_key.table.columns[colname]].name)
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
    doc = dict(
        foreign_key_columns=fcs,
        referenced_columns=pcs,
        rights=self.rights(),
        comment=self.comment,
        annotations=self.annotations,
        names=[ constraint_name_prejson(c) for c in self.constraints ]
    )
    if self.has_right('owner'):
        doc['acls'] = self.acls
    return doc

def _keyref_has_right(self, aclname, roles=None):
    if not self.unique.has_right('enumerate', roles):
        return False
    if not self.foreign_key.columns_have_right(aclname):
        return False
    return self._has_right(aclname, roles)

@annotatable
@hasacls(
    {"write", "insert", "update", "enumerate"},
    {"insert", "update"},
    lambda self: self.foreign_key.table
)
@keying(
    'keyref',
    {
        "from_schema_name": ('text', lambda self: unicode(self.foreign_key.table.schema.name)),
        "from_table_name": ('text', lambda self: unicode(self.foreign_key.table.name)),
        "from_column_names": ('text[]', lambda self: self._from_column_names()),
        "to_schema_name": ('text', lambda self: unicode(self.unique.table.schema.name)),
        "to_table_name": ('text', lambda self: unicode(self.unique.table.name)),
        "to_column_names": ('text[]', lambda self: self._to_column_names())
    }
)
class KeyReference (object):
    """A reference from a foreign key to a primary key."""
    
    def __init__(self, foreign_key, unique, fk_ref_map, on_delete='NO ACTION', on_update='NO ACTION', constraint_name=None, annotations={}, comment=None, acls={}):
        self.foreign_key = foreign_key
        self.unique = unique
        self.reference_map_frozen = fk_ref_map
        self.reference_map = dict(fk_ref_map)
        self.referenceby_map = dict([ (p, f) for f, p in fk_ref_map ])
        self.on_delete = on_delete
        self.on_update = on_update
        # Link into foreign key's key reference list, by table ref
        if unique.table not in foreign_key.table_references:
            foreign_key.table_references[unique.table] = set()
        _guarded_add(foreign_key.table_references[unique.table], self)
        if foreign_key.table not in unique.table_references:
            unique.table_references[foreign_key.table] = set()
        _guarded_add(unique.table_references[foreign_key.table], self)
        if constraint_name is not None:
            enforce_63byte_id(constraint_name[1], 'Foreign-key constraint')
        self.constraint_name = constraint_name
        self.constraints = set([self])
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on foreign key %s' % (k, unicode(self.constraint_name))))
        self.annotations.update(annotations)
        self.acls = AclDict(self)
        self.acls.update(acls)
        self.comment = comment

    @staticmethod
    def keyed_resource(model=None, from_schema_name=None, from_table_name=None, from_column_names=None, to_schema_name=None, to_table_name=None, to_column_names=None):
        from_table = model.schemas[from_schema_name].tables[from_table_name]
        to_table = model.schemas[to_schema_name].tables[to_table_name]
        refmap = dict([
            (from_table.columns[from_cname], to_table.columns[to_cname])
            for from_cname, to_cname in zip(from_column_names, to_column_names)
        ])
        return from_table.fkeys[frozenset(refmap.keys())].references[frozendict(refmap)]

    def set_comment(self, conn, cur, comment):
        if self.constraint_name:
            fkr_schema, fkr_name = self.constraint_name
            cur.execute("""
COMMENT ON CONSTRAINT %s ON %s.%s IS %s;
SELECT _ermrest.model_change_event();
""" % (
    sql_identifier(unicode(fkr_name)),
    sql_identifier(unicode(self.foreign_key.table.schema.name)),
    sql_identifier(unicode(self.foreign_key.table.name)),
    sql_literal(comment)
)
            )
        # also update other constraints sharing same mapping
        for fkr in self.constraints:
            if fkr != self:
                fkr.set_comment(conn, cur, comment)
        
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
            '%s FOREIGN KEY (%s) REFERENCES %s.%s (%s)' % (
                ('CONSTRAINT %s' % sql_identifier(self.constraint_name[1]) if self.constraint_name else ''),
                ','.join([ sql_identifier(fk_cols[i].name) for i in range(0, len(fk_cols)) ]),
                sql_identifier(self.unique.table.schema.name),
                sql_identifier(self.unique.table.name),
                ','.join([ sql_identifier(self.reference_map[fk_cols[i]].name) for i in range(0, len(fk_cols)) ])
            )
        )

    def pre_delete(self, conn, cur):
        self.delete_annotation(conn, cur, None)
        self.delete_acl(cur, None, purging=True)
    
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
        self.foreign_key.table.alter_table(conn, cur, 'ADD %s' % self.sql_def())
        self.set_comment(conn, cur, self.comment)
        for k, v in self.annotations.items():
            self.set_annotation(conn, cur, k, v)
                
    def delete(self, conn, cur):
        self.pre_delete(conn, cur)
        if self.constraint_name:
            fkr_schema, fkr_name = self.constraint_name
            self.foreign_key.table.alter_table(conn, cur, 'DROP CONSTRAINT %s' % sql_identifier(fkr_name))
        for fkr in self.constraints:
            if fkr != self:
                fkr.delete(conn, cur)
        
    def _from_column_names(self):
        """Canonicalized from-column names list."""
        return _keyref_from_column_names(self)
        
    def _to_column_names(self):
        """Canonicalized to-column names list."""
        return _keyref_to_column_names(self)
        
    @staticmethod
    def fromjson(model, refdoc, fkey=None, fktable=None, pkey=None, pktable=None, outfkeys=None):
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
                if type(n[1]) not in [str, unicode]:
                    raise exception.BadData('Foreign key constraint_name %s must be textual' % n[1])
            return names
                
        def check_columns(cols, kind):
            tnames = set(map(lambda d: (d.get('schema_name'), d.get('table_name')), cols))
            if len(tnames) != 1:
                raise exception.BadData('All %s columns must come from one table.' % kind)
            sname, tname = tnames.pop()
            table = model.schemas[sname].tables[tname]
            for cname in map(lambda d: d.get('column_name'), cols):
                if cname in table.columns:
                    yield table.columns[cname]
                else:
                    raise exception.ConflictModel('The %s column %s not defined in table.' % (kind, cname))

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

            elif is_fkey and fk_colset != fkey.columns:
                raise exception.ConflictModel(
                    'Reference map referring columns %s do not match foreign key columns %s.' 
                    % (colset, key.columns)
                    )
            elif (not is_fkey) and fk_colset != fkey.columns:
                raise exception.ConflictModel(
                    'Reference map referenced columns %s do not match unique columns %s.' 
                    % (colset, key.columns)
                    )

            return colset, key, table

        fk_names = check_names(refdoc.get('names', []))
        fk_columns = list(check_columns(refdoc.get('foreign_key_columns', []), 'foreign-key'))
        pk_columns = list(check_columns(refdoc.get('referenced_columns', []), 'referenced'))
        annotations = refdoc.get('annotations', {})
        comment = refdoc.get('comment')

        fk_colset, fkey, fktable = get_colset_key_table(fk_columns, True, fkey, fktable)
        pk_colset, pkey, pktable = get_colset_key_table(pk_columns, False, pkey, pktable)
        fk_ref_map = frozendict(dict([ (fk_columns[i], pk_columns[i]) for i in range(0, len(fk_columns)) ]))

        fk_name = fk_names[0] if fk_names else None
            
        if fk_ref_map not in fkey.references:
            if fktable.kind == 'r' and pktable.kind == 'r':
                fkr = KeyReference(fkey, pkey, fk_ref_map, constraint_name=fk_name, annotations=annotations, comment=comment)
            else:
                fkr = PseudoKeyReference(fkey, pkey, fk_ref_map, constraint_name=fk_name, annotations=annotations, comment=comment)
            fkey.references[fk_ref_map] = fkr
            yield fkey.references[fk_ref_map]

    def prejson(self):
        return _keyref_prejson(self)

    def __repr__(self):
        return '<ermrest.model.KeyReference %s>' % str(self)

    def has_right(self, aclname, roles=None):
        return _keyref_has_right(self, aclname, roles)

@annotatable
@hasacls(
    {"write", "insert", "update", "enumerate"},
    {"insert", "update"},
    lambda self: self.foreign_key.table
)
@keying(
    'keyref',
    {
        "from_schema_name": ('text', lambda self: unicode(self.foreign_key.table.schema.name)),
        "from_table_name": ('text', lambda self: unicode(self.foreign_key.table.name)),
        "from_column_names": ('text[]', lambda self: self._from_column_names()),
        "to_schema_name": ('text', lambda self: unicode(self.unique.table.schema.name)),
        "to_table_name": ('text', lambda self: unicode(self.unique.table.name)),
        "to_column_names": ('text[]', lambda self: self._to_column_names())
    }
)
class PseudoKeyReference (object):
    """A psuedo-reference from a foreign key to a primary key."""
    
    def __init__(self, foreign_key, unique, fk_ref_map, id=None, constraint_name=("", None), annotations={}, comment=None, acls={}):
        self.foreign_key = foreign_key
        self.unique = unique
        self.reference_map_frozen = fk_ref_map
        self.reference_map = dict(fk_ref_map)
        self.referenceby_map = dict([ (p, f) for f, p in fk_ref_map ])
        # Link into foreign key's key reference list, by table ref
        if unique.table not in foreign_key.table_references:
            foreign_key.table_references[unique.table] = set()
        _guarded_add(foreign_key.table_references[unique.table], self)
        if foreign_key.table not in unique.table_references:
            unique.table_references[foreign_key.table] = set()
        _guarded_add(unique.table_references[foreign_key.table], self)
        self.id = id
        self.constraint_name = constraint_name
        self.constraints = set([self])
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on foreign key %s' % (k, unicode(self.constraint_name))))
        self.annotations.update(annotations)
        self.acls = AclDict(self)
        self.acls.update(acls)
        self.comment = comment

    def set_comment(self, conn, cur, comment):
        if self.id:
            cur.execute("""
UPDATE _ermrest.model_pseudo_keyref
SET comment = %s
WHERE id = %s
SELECT _ermrest.model_change_event();
""" % (
    sql_literal(comment),
    sql_literal(self.id)
)
            )
        # also update other constraints sharing same mapping
        for fkr in self.constraints:
            if fkr != self:
                fkr.set_comment(conn, cur, comment)

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

    def pre_delete(self, conn, cur):
        self.delete_annotation(conn, cur, None)
        self.delete_acl(cur, None, purging=True)

    def add(self, conn, cur):
        self.foreign_key.table.enforce_right('owner') # since we don't use alter_table which enforces for real keyrefs
        fk_cols = list(self.foreign_key.columns)
        cur.execute("""
SELECT _ermrest.model_change_event();
INSERT INTO _ermrest.model_pseudo_keyref
  (from_schema_name, from_table_name, from_column_names, to_schema_name, to_table_name, to_column_names, comment, name)
  VALUES (%s, %s, ARRAY[%s], %s, %s, ARRAY[%s], %s, %s)
  RETURNING id
""" % (
    sql_literal(unicode(self.foreign_key.table.schema.name)),
    sql_literal(unicode(self.foreign_key.table.name)),
    ', '.join([ sql_literal(unicode(fk_cols[i].name)) for i in range(len(fk_cols)) ]),
    sql_literal(unicode(self.unique.table.schema.name)),
    sql_literal(unicode(self.unique.table.name)),
    ', '.join([ sql_literal(unicode(self.reference_map[fk_cols[i]].name)) for i in range(len(fk_cols)) ]),
    sql_literal(self.comment),
    sql_literal(self.constraint_name[1]) if self.constraint_name else 'NULL'
)
        )
        self.id = cur.fetchone()[0]
        self.constraint_name = [
            "",
            self.constraint_name[1] if self.constraint_name else self.id
        ]
        for k, v in self.annotations.items():
            self.set_annotation(conn, cur, k, v)
        
    def delete(self, conn, cur):
        self.foreign_key.table.enforce_right('owner') # since we don't use alter_table which enforces for real keyrefs
        self.pre_delete(conn, cur)
        if self.id:
            cur.execute("""
DELETE FROM _ermrest.model_pseudo_keyref WHERE id = %s;
SELECT _ermrest.model_change_event();
""" % sql_literal(self.id)
            )
        for fkr in self.constraints:
            if fkr != self:
                fkr.delete(conn, cur)

    def has_right(self, aclname, roles=None):
        return _keyref_has_right(self, aclname, roles)

class _Endpoint(object):

    def __init__(self, table):
        self.table = table
                
class MultiKeyReference (object):
    """A disjunctive join condition collecting several links.

       This abstraction simulates a left-to-right reference.
    """

    def __init__(self, links):
        assert len(links) > 0
        
        self.ltable = None
        self.rtable = None

        for keyref, refop in links:
            if refop == '=@':
                ltable = keyref.foreign_key.table
                rtable = keyref.unique.table
            else:
                ltable = keyref.unique.table
                rtable = keyref.foreign_key.table
                
            assert self.ltable is None or self.ltable == ltable
            assert self.rtable is None or self.rtable == rtable

            self.ltable = ltable
            self.rtable = rtable

        self.links = links
        self.foreign_key = _Endpoint(ltable)
        self.unique = _Endpoint(rtable)

    def _visible_links(self):
        return [ l for l in self.links if l.has_right('enumerate') ]

    def join_str(self, refop, lname='..', rname='.'):
        """Build a simplified representation of the join condition."""
        assert refop == '=@'
        parts = []
        for keyref, refop in self._visible_links():
            parts.append(keyref.join_str(refop, lname, rname))
        return '(%s)' % (' OR '.join(parts))
                         
    def join_sql(self, refop, lname, rname):
        assert refop == '=@'
        return ' OR '.join([
            '(%s)' % keyref.join_sql(refop, lname, rname)
            for keyref, refop in self._visible_links()
        ])

    def has_right(self, aclname, roles=None):
        assert aclname == 'enumerate'
        return self._visible_links()

class ExplicitJoinReference (object):

    def __init__(self, lcols, rcols):
        assert len(lcols) == len(rcols)

        self.lcols = lcols
        self.rcols = rcols

        ltable = lcols[0].table
        rtable = rcols[0].table

        self.foreign_key = _Endpoint(ltable)
        self.unique = _Endpoint(rtable)

    def _from_column_names(self):
        return [ c.name for c in self.lcols ]

    def _to_column_names(self):
        return [ c.name for c in self.rcols ]
        
    def join_str(self, refop, lname='..', rname='.'):
        assert refop == '=@'
        return _keyref_join_str(self, refop, lname, rname)
        
    def join_sql(self, refop, lname, rname):
        assert refop == '=@'
        return _keyref_join_sql(self, refop, lname, rname)

    def has_right(self, aclname, roles=None):
        assert aclname == 'enumerate'
        for c in self.lcols + self.rcols:
            if not c.has_right(aclname, roles):
                return False
        return True
