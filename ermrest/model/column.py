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

import urllib
import json
import re

from .. import exception
from ..util import sql_identifier, sql_literal, udecode
from .type import tsvector_type, Type
from .misc import AltDict, AclDict, keying, annotatable, commentable, hasacls, truncated_identifier

@commentable
@annotatable
@hasacls(
    {"enumerate", "write", "insert", "update", "select"},
    {"insert", "update", "select", "delete"},
    lambda self: self.table
)
@keying(
   'column',
    {
        "schema_name": ('text', lambda self: unicode(self.table.schema.name)),
        "table_name": ('text', lambda self: unicode(self.table.name)),
        "column_name": ('text', lambda self: unicode(self.name))
    }
)
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
    
    def __init__(self, name, position, type, default_value, nullok=None, comment=None, annotations={}, acls={}):
        self.table = None
        self.name = name
        self.position = position
        self.type = type
        self.default_value = default_value
        self.nullok = nullok if nullok is not None else True
        self.comment = comment
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on column %s' % (k, self)))
        self.annotations.update(annotations)
        self.acls = AclDict(self)
        self.acls.update(acls)
    
    @staticmethod
    def introspect_annotation(model=None, schema_name=None, table_name=None, column_name=None, annotation_uri=None, annotation_value=None):
        model.schemas[schema_name].tables[table_name].columns[column_name].annotations[annotation_uri] = annotation_value

    @staticmethod
    def keyed_resource(model=None, schema_name=None, table_name=None, column_name=None):
        return model.schemas[schema_name].tables[table_name].columns[column_name]

    def sql_comment_resource(self):
        return "COLUMN %s.%s.%s" % (
            sql_identifier(unicode(self.table.schema.name)),
            sql_identifier(unicode(self.table.name)),
            sql_identifier(unicode(self.name))
        )
        
    def __str__(self):
        return ':%s:%s:%s' % (
            urllib.quote(unicode(self.table.schema.name).encode('utf8')),
            urllib.quote(unicode(self.table.name).encode('utf8')),
            urllib.quote(unicode(self.name).encode('utf8'))
            )

    def has_right(self, aclname, roles=None):
        if not self.table.has_right(aclname, roles):
            return False
        return self._has_right(aclname, roles)

    def __repr__(self):
        return '<ermrest.model.Column %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def is_star_column(self):
        return False

    def istext(self):
        # we can force casting everythign to text for searching...
        return True

    def is_indexable(self):
        return str(self.type) != 'json'

    def btree_index_sql(self):
        """Return SQL to construct a single-column btree index or None if not necessary.

           An index is not necessary if the column forms a
           single-column key already and therefore has an implicitly
           created index.

        """
        if self not in self.table.uniques and self.is_indexable():
            return """
DROP INDEX IF EXISTS %(schema)s.%(index)s ;
CREATE INDEX %(index)s ON %(schema)s.%(table)s ( %(column)s ) ;
""" % dict(schema=sql_identifier(self.table.schema.name),
           table=sql_identifier(self.table.name),
           column=sql_identifier(self.name),
           index=sql_identifier(truncated_identifier([self.table.name, '_', self.name, '_idx']))
       )
        else:
            return None

    def pg_trgm_index_sql(self):
        """Return SQL to construct single-column tri-gram index or None if not necessary.

           An index is not necessary if the column is not a textual
           column.

        """
        if self.istext():
            return """
DROP INDEX IF EXISTS %(schema)s.%(index)s ;
CREATE INDEX %(index)s ON %(schema)s.%(table)s USING gin ( %(index_val)s gin_trgm_ops ) ;
""" % dict(schema=sql_identifier(self.table.schema.name),
           table=sql_identifier(self.table.name),
           index_val=self.sql_name_astext_with_talias(None),
           index=sql_identifier(truncated_identifier([self.table.name, '_', self.name, '_pgt', 'rgm_', 'idx']))
       )
        else:
            return None

    def sql_def(self):
        """Render SQL column clause for managed table DDL."""
        parts = [
            sql_identifier(unicode(self.name)),
            self.type.sql()
            ]
        if self.default_value:
            parts.append('DEFAULT %s' % sql_literal(self.default_value))
        if self.nullok is False:
            parts.append('NOT NULL')
        return ' '.join(parts)

    def input_ddl(self, alias=None):
        """Render SQL column clause for temporary input table DDL."""
        if alias:
            name = alias
        else:
            name = self.name
        return u"%s %s" % (
            sql_identifier(name),
            self.type.sql(basic_storage=True)
            )
    
    def pre_delete(self, conn, cur):
        """Do any maintenance before column is deleted from table."""
        self.delete_annotation(conn, cur, None)
        self.delete_acl(cur, None, purging=True)
        
    @staticmethod
    def fromjson_single(columndoc, position, ermrest_config):
        ctype = Type.fromjson(columndoc['type'], ermrest_config)
        comment = columndoc.get('comment', None)
        annotations = columndoc.get('annotations', {})
        nullok = columndoc.get('nullok', True)
        acls = columndoc.get('acls', {})
        try:
            return Column(
                columndoc['name'],
                position,
                ctype,
                columndoc.get('default'),
                nullok,
                comment,
                annotations,
                acls
            )
        except KeyError, te:
            raise exception.BadData('Table document missing required field "%s"' % te)

    @staticmethod
    def fromjson(columnsdoc, ermrest_config):
        columns = []
        for i in range(0, len(columnsdoc)):
            columns.append(Column.fromjson_single(columnsdoc[i], i, ermrest_config))
        return columns

    def prejson(self):
        doc = dict(
            name=self.name,
            rights=self.rights(),
            type=self.type.prejson(),
            default=self.default_value,
            nullok=self.nullok,
            comment=self.comment,
            annotations=self.annotations
            )
        if self.has_right('owner'):
            doc['acls'] = self.acls
        return doc

    def prejson_ref(self):
        return dict(
            schema_name=self.table.schema.name,
            table_name=self.table.name,
            column_name=self.name
            )

    def sql_name(self, alias=None):
        if alias:
            return sql_identifier(alias)
        else:
            return sql_identifier(self.name)

    def sql_name_astext_with_talias(self, talias):
        name = '%s%s' % (talias + '.' if talias else '', self.sql_name())
        return '_ermrest.astext(%s)' % name

class FreetextColumn (Column):
    """Represents virtual table column for free text search.

       This is a tsvector computed by appending all text-type columns
       as a document, sorted by column order.
    """
    
    def __init__(self, table):
        Column.__init__(self, '*', None, tsvector_type, None)

        self.table = table
        
        self.srccols = [ c for c in table.columns.itervalues() if c.istext() ]
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
    index=sql_identifier(truncated_identifier([self.table.name, '__ts', 'vect', 'or', 'idx']))
)

    def pg_trgm_index_sql(self):
        # drop legacy index
        return """
DROP INDEX IF EXISTS %(schema)s.%(index)s ;
""" % dict(
    schema=sql_identifier(self.table.schema.name),
    index=sql_identifier(truncated_identifier([self.table.name, '__pg', 'trgm', '_idx'])),
)

