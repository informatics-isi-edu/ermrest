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

from .. import exception
from ..util import sql_identifier, sql_literal
from .misc import frozendict, AltDict, annotatable, commentable

import json

@commentable()
class Unique (object):
    """A unique constraint."""
    
    def __init__(self, cols, constraint_name=None, comment=None):
        tables = set([ c.table for c in cols ])
        assert len(tables) == 1
        self.table = tables.pop()
        self.columns = cols
        self.table_references = dict()
        self.constraint_names = set()
        self.comment = comment
        if constraint_name:
            self.constraint_names.add(constraint_name)

        if cols not in self.table.uniques:
            self.table.uniques[cols] = self
        
    def sql_comment_resource(self):
        return set([
            # we treat all unique constraints w/ same column set as equivalence class of key
            # NOTE: this overwrites comments on multiple constraints that might be different in legacy DB!
            "CONSTRAINT %s ON %s.%s" % (
                sql_identifier(unicode(pk_name)),
                sql_identifier(unicode(self.table.schema.name)),
                sql_identifier(unicode(self.table.name))
                )
            for pk_schema, pk_name in self.constraint_names
        ])

    def __str__(self):
        return ','.join([ str(c) for c in self.columns ])

    def __repr__(self):
        return '<ermrest.model.Unique %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def sql_def(self):
        """Render SQL table constraint clause for DDL."""
        return 'UNIQUE(%s)' % (','.join([sql_identifier(c.name) for c in self.columns]))

    @staticmethod
    def fromjson_single(table, keydoc):
        """Yield Unique instance if and only if keydoc describes a key not already in table."""
        keycolumns = []
        kcnames = keydoc.get('unique_columns', [])
        comment = keydoc.get('comment')
        for kcname in kcnames:
            if kcname not in table.columns:
                raise exception.BadData('Key column %s not defined in table.' % kcname)
            keycolumns.append(table.columns[kcname])
        keycolumns = frozenset(keycolumns)
        if keycolumns not in table.uniques:
            yield Unique(keycolumns, comment=comment)

    @staticmethod
    def fromjson(table, keysdoc):
        for keydoc in keysdoc:
            for key in Unique.fromjson_single(table, keydoc):
                yield key

    def pre_delete(self, conn, cur):
        """Do any maintenance before table is deleted."""
        for fkeyrefset in self.table_references.values():
            for fkeyref in fkeyrefset:
                fkeyref.pre_delete(conn, cur)

    def prejson(self):
        return dict(
            comment=self.comment,
            unique_columns=[ c.name for c in self.columns ]
            )

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

@commentable()
@annotatable('keyref', dict(
    from_schema_name=('text', lambda self: unicode(self.foreign_key.table.schema.name)),
    from_table_name=('text', lambda self: unicode(self.foreign_key.table.name)),
    from_column_names=('text[]', lambda self: self._from_column_names()),
    to_schema_name=('text', lambda self: unicode(self.unique.table.schema.name)),
    to_table_name=('text', lambda self: unicode(self.unique.table.name)),
    to_column_names=('text[]', lambda self: self._to_column_names())
    )
)
class KeyReference (object):
    """A reference from a foreign key to a primary key."""
    
    def __init__(self, foreign_key, unique, fk_ref_map, on_delete='NO ACTION', on_update='NO ACTION', constraint_name=None, annotations={}, comment=None):
        self.foreign_key = foreign_key
        self.unique = unique
        self.reference_map = dict(fk_ref_map)
        self.referenceby_map = dict([ (p, f) for f, p in fk_ref_map ])
        self.on_delete = on_delete
        self.on_update = on_update
        # Link into foreign key's key reference list, by table ref
        if unique.table not in foreign_key.table_references:
            foreign_key.table_references[unique.table] = set()
        foreign_key.table_references[unique.table].add(self)
        if foreign_key.table not in unique.table_references:
            unique.table_references[foreign_key.table] = set()
        unique.table_references[foreign_key.table].add(self)
        self.constraint_names = set()
        if constraint_name:
            self.constraint_names.add(constraint_name)
        self.annotations = dict()
        self.annotations.update(annotations)
        self.comment = comment

    @staticmethod
    def introspect_annotation(model=None, from_schema_name=None, from_table_name=None, from_column_names=None, to_schema_name=None, to_table_name=None, to_column_names=None, annotation_uri=None, annotation_value=None):
        from_table = model.schemas[from_schema_name].tables[from_table_name]
        to_table = model.schemas[to_schema_name].tables[to_table_name]
        refmap = dict([
            (from_table.columns[from_cname], to_table.columns[to_cname])
            for from_cname, to_cname in zip(from_column_names, to_column_names)
        ])
        from_table.fkeys[frozenset(refmap.keys())].references[frozendict(refmap)].annotations[annotation_uri] = annotation_value

    def sql_comment_resource(self):
        return set([
            # we treat all fkeyref constraints w/ same cmapping as equivalence class of fkeyref
            # NOTE: this overwrites comments on multiple constraints that might be different in legacy DB!
            "CONSTRAINT %s ON %s.%s" % (
                sql_identifier(unicode(fk_name)),
                sql_identifier(unicode(self.foreign_key.table.schema.name)),
                sql_identifier(unicode(self.foreign_key.table.name))
                )
            for fk_schema, fk_name in self.constraint_names
        ])

    def __str__(self):
        interp = self._interp_annotation(None, sql_wrap=False)
        interp['from_column_names'] = ','.join(interp['from_column_names'])
        interp['to_column_names'] = ','.join(interp['to_column_names'])
        return ':%(from_schema_name)s:%(from_table_name)s(%(from_column_names)s)==>:%(to_schema_name)s:%(to_table_name)s(%(to_column_names)s)' % interp

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def sql_def(self):
        """Render SQL table constraint clause for DDL."""   
        fk_cols = list(self.foreign_key.columns)
        return ('FOREIGN KEY (%s) REFERENCES %s.%s (%s)'
                % (
                ','.join([ sql_identifier(fk_cols[i].name) for i in range(0, len(fk_cols)) ]),
                sql_identifier(self.unique.table.schema.name),
                sql_identifier(self.unique.table.name),
                ','.join([ sql_identifier(self.reference_map[fk_cols[i]].name) for i in range(0, len(fk_cols)) ])
                ))

    def pre_delete(self, conn, cur):
        """Do any maintenance before foreignkey reference constraint is deleted from table."""
        self.delete_annotation(conn, cur, None)

    def _from_column_names(self):
        """Canonicalized from-column names list."""
        f_cnames = [ unicode(col.name) for col in self.foreign_key.columns ]
        f_cnames.sort()
        return f_cnames
        
    def _to_column_names(self):
        """Canonicalized to-column names list."""
        return [
            unicode(self.reference_map[self.foreign_key.table.columns[colname]].name)
            for colname in self._from_column_names()
        ]
        
    @staticmethod
    def fromjson(model, refdoc, fkey=None, fktable=None, pkey=None, pktable=None, outfkeys=None):
        fk_cols = []
        pk_cols = []
        refs = []

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

        fk_columns = list(check_columns(refdoc.get('foreign_key_columns', []), 'foreign-key'))
        pk_columns = list(check_columns(refdoc.get('referenced_columns', []), 'referenced'))
        annotations = refdoc.get('annotations', {})
        comment = refdoc.get('comment')

        fk_colset, fkey, fktable = get_colset_key_table(fk_columns, True, fkey, fktable)
        pk_colset, pkey, pktable = get_colset_key_table(pk_columns, False, pkey, pktable)
        fk_ref_map = frozendict(dict([ (fk_columns[i], pk_columns[i]) for i in range(0, len(fk_columns)) ]))
        
        if fk_ref_map not in fkey.references:
            fkey.references[fk_ref_map] = KeyReference(fkey, pkey, fk_ref_map, annotations=annotations, comment=comment)
            yield fkey.references[fk_ref_map]

    def prejson(self):
        fcs = []
        pcs = []
        for fc in self.reference_map.keys():
            fcs.append( fc.prejson_ref() )
            pcs.append( self.reference_map[fc].prejson_ref() )
        return dict(
            foreign_key_columns=fcs,
            referenced_columns=pcs,
            comment=self.comment,
            annotations=self.annotations
            )

    def __repr__(self):
        return '<ermrest.model.KeyReference %s>' % str(self)

