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

"""
A database introspection layer.

At present, the capabilities of this module are limited to introspection of an 
existing database model. This module does not attempt to capture all of the 
details that could be found in an entity-relationship model or in the standard 
information_schema of a relational database. It represents the model as 
needed by other modules of the ermrest project.
"""

from .. import exception
from ..util import sql_identifier, sql_literal
from .misc import AltDict, annotatable, commentable
from .column import Column, FreetextColumn
from .key import Unique, ForeignKey, KeyReference

import urllib
import json

@commentable()
@annotatable('table', dict(
    schema_name=('text', lambda self: unicode(self.schema.name)),
    table_name=('text', lambda self: unicode(self.name))
    )
)
class Table (object):
    """Represents a database table.
    
    At present, this has a 'name' and a collection of table 'columns'. It
    also has a reference to its 'schema'.
    """
    
    def __init__(self, schema, name, columns, kind, comment=None, annotations={}):
        self.schema = schema
        self.name = name
        self.kind = kind
        self.comment = comment
        self.columns = AltDict(lambda k: exception.ConflictModel(u"Requested column %s does not exist in table %s." % (k, self)))
        self.uniques = AltDict(lambda k: exception.ConflictModel(u"Requested key %s does not exist in table %s." % (k, self)))
        self.fkeys = AltDict(lambda k: exception.ConflictModel(u"Requested foreign-key %s does not exist in table %s." % (k, self)))
        self.annotations = dict()
        self.annotations.update(annotations)

        for c in columns:
            self.columns[c.name] = c
            c.table = self

        if name not in self.schema.tables:
            self.schema.tables[name] = self

    @staticmethod
    def introspect_annotation(model=None, schema_name=None, table_name=None, annotation_uri=None, annotation_value=None):
        model.schemas[schema_name].tables[table_name].annotations[annotation_uri] = annotation_value

    def __str__(self):
        return ':%s:%s' % (
            urllib.quote(unicode(self.schema.name).encode('utf8')),
            urllib.quote(unicode(self.name).encode('utf8'))
            )

    def __repr__(self):
        return '<ermrest.model.Table %s>' % str(self)

    def columns_in_order(self):
        cols = self.columns.values()
        cols.sort(key=lambda c: c.position)
        return cols

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

        annotations = tabledoc.get('annotations', {})
        columns = Column.fromjson(tabledoc.get('column_definitions',[]), ermrest_config)
        comment = tabledoc.get('comment')
        table = Table(schema, tname, columns, kind, comment, annotations)
        keys = Unique.fromjson(table, tabledoc.get('keys', []))
        fkeys = ForeignKey.fromjson(table, tabledoc.get('foreign_keys', []))

        clauses = []
        for column in columns:
            clauses.append(column.sql_def())
            
        for key in keys:
            clauses.append(key.sql_def())

        for fkey in fkeys:
            for ref in fkey.references.values():
                clauses.append(ref.sql_def())
        
        cur.execute("""
CREATE TABLE %(sname)s.%(tname)s (
   %(clauses)s
);
COMMENT ON TABLE %(sname)s.%(tname)s IS %(comment)s;
SELECT _ermrest.model_change_event();
SELECT _ermrest.data_change_event(%(snamestr)s, %(tnamestr)s);
""" % dict(sname=sql_identifier(sname),
           tname=sql_identifier(tname),
           snamestr=sql_literal(sname),
           tnamestr=sql_literal(tname),
           clauses=',\n'.join(clauses),
           comment=sql_literal(comment),
           )
                    )

        for k, v in annotations.items():
            table.set_annotation(conn, cur, k, v)

        for column in columns:
            if column.comment is not None:
                column.set_comment(conn, cur, column.comment)
            for k, v in column.annotations.items():
                column.set_annotation(conn, cur, k, v)

        for fkey in table.fkeys.values():
            for fkeyref in fkey.references.values():
                for k, v in fkeyref.annotations.items():
                    fkeyref.set_annotation(conn, cur, k, v)

        return table

    def pre_delete(self, conn, cur):
        """Do any maintenance before table is deleted."""
        for fkey in self.fkeys.values():
            fkey.pre_delete(conn, cur)
        for unique in self.uniques.values():
            unique.pre_delete(conn, cur)
        for column in self.columns.values():
            column.pre_delete(conn, cur)
        self.delete_annotation(conn, cur, None)

    def alter_table(self, conn, cur, alterclause):
        """Generic ALTER TABLE ... wrapper"""
        cur.execute("""
ALTER TABLE %(sname)s.%(tname)s  %(alter)s ;
SELECT _ermrest.model_change_event();
SELECT _ermrest.data_change_event(%(snamestr)s, %(tnamestr)s);
""" % dict(sname=sql_identifier(self.schema.name), 
           tname=sql_identifier(self.name),
           snamestr=sql_literal(self.schema.name), 
           tnamestr=sql_literal(self.name),
           alter=alterclause
       )
                    )

    def sql_comment_resource(self):
        return "TABLE %s.%s" % (
            sql_identifier(unicode(self.schema.name)),
            sql_identifier(unicode(self.name))
        )

    def add_column(self, conn, cur, columndoc, ermrest_config):
        """Add column to table."""
        # new column always goes on rightmost position
        position = len(self.columns)
        column = Column.fromjson_single(columndoc, position, ermrest_config)
        if column.name in self.columns:
            raise exception.ConflictModel('Column %s already exists in table %s:%s.' % (column.name, self.schema.name, self.name))
        self.alter_table(conn, cur, 'ADD COLUMN %s' % column.sql_def())
        column.set_comment(conn, cur, column.comment)
        self.columns[column.name] = column
        column.table = self
        for k, v in column.annotations.items():
            column.set_annotation(conn, cur, k, v)
        return column

    def delete_column(self, conn, cur, cname):
        """Delete column from table."""
        if cname not in self.columns:
            raise exception.NotFound('column %s in table %s:%s' % (cname, self.schema.name, self.name))
        column = self.columns[cname]
        for unique in self.uniques.values():
            if column in unique.columns:
                unique.pre_delete(conn, cur)
        for fkey in self.fkeys.values():
            if column in fkey.columns:
                fkey.pre_delete(conn, cur)
        column.pre_delete(conn, cur)
        self.alter_table(conn, cur, 'DROP COLUMN %s' % sql_identifier(cname))
        del self.columns[cname]
                    
    def add_unique(self, conn, cur, udoc):
        """Add a unique constraint to table."""
        for key in Unique.fromjson_single(self, udoc):
            # new key must be added to table
            self.alter_table(conn, cur, 'ADD %s' % key.sql_def())
            yield key

    def delete_unique(self, conn, cur, unique):
        """Delete unique constraint(s) from table."""
        if unique.columns not in self.uniques or len(unique.constraint_names) == 0:
            raise exception.ConflictModel('Unique constraint columns %s not understood in table %s:%s.' % (unique.columns, self.schema.name, self.name))
        unique.pre_delete(conn, cur)
        for pk_schema, pk_name in unique.constraint_names:
            # TODO: can constraint ever be in a different postgres schema?  if so, how do you drop it?
            self.alter_table(conn, cur, 'DROP CONSTRAINT %s' % sql_identifier(pk_name))

    def add_fkeyref(self, conn, cur, fkrdoc):
        """Add foreign-key reference constraint to table."""
        for fkr in KeyReference.fromjson(self.schema.model, fkrdoc, None, self, None, None, None):
            # new foreign key constraint must be added to table
            self.alter_table(conn, cur, 'ADD %s' % fkr.sql_def())
            for k, v in fkr.annotations.items():
                fkr.set_annotation(conn, cur, k, v)
            yield fkr

    def delete_fkeyref(self, conn, cur, fkr):
        """Delete foreign-key reference constraint(s) from table."""
        assert fkr.foreign_key.table == self
        fkr.pre_delete(conn, cur)
        for fk_schema, fk_name in fkr.constraint_names:
            # TODO: can constraint ever be in a different postgres schema?  if so, how do you drop it?
            self.alter_table(conn, cur, 'DROP CONSTRAINT %s' % sql_identifier(fk_name))

    def prejson(self):
        return dict(
            schema_name=self.schema.name,
            table_name=self.name,
            column_definitions=[
                c.prejson() for c in self.columns_in_order()
                ],
            keys=[
                u.prejson() for u in self.uniques.values()
                ],
            foreign_keys=[
                fkr.prejson()
                for fk in self.fkeys.values() for fkr in fk.references.values()
                ],
            kind={
                'r':'table', 
                'f':'foreign_table',
                'v':'view'
                }.get(self.kind, 'unknown'),
            comment=self.comment,
            annotations=self.annotations
            )

    def sql_name(self):
        return '.'.join([
                sql_identifier(self.schema.name),
                sql_identifier(self.name)
                ])

    def freetext_column(self):
        return FreetextColumn(self)

