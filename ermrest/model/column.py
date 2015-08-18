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

import urllib
import json
import re

from .. import exception
from ..util import sql_identifier, sql_literal
from .type import Type
from .misc import annotatable

@annotatable('column', dict(
    schema_name=lambda self: unicode(self.table.schema.name),
    table_name=lambda self: unicode(self.table.name),
    column_name=lambda self: unicode(self.name)
    )
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
    
    def __init__(self, name, position, type, default_value, comment=None, annotations={}):
        self.table = None
        self.name = name
        self.position = position
        self.type = type
        self.default_value = default_value
        self.comment = comment
        self.annotations = dict()
        self.annotations.update(annotations)
    
    def __str__(self):
        return ':%s:%s:%s' % (
            urllib.quote(self.table.schema.name),
            urllib.quote(self.table.name),
            urllib.quote(self.name)
            )

    def __repr__(self):
        return '<ermrest.model.Column %s>' % str(self)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def is_star_column(self):
        return False

    def istext(self):
        return re.match( r'(text|character)( *varying)?([(]0-9*[)])?', str(self.type))

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
DROP INDEX IF EXISTS %(index)s ;
CREATE INDEX %(index)s ON %(schema)s.%(table)s ( %(column)s ) ;
""" % dict(schema=sql_identifier(self.table.schema.name),
           table=sql_identifier(self.table.name),
           column=sql_identifier(self.name),
           index=sql_identifier("%s_%s_idx" % (self.table.name, self.name))
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
DROP INDEX IF EXISTS %(index)s ;
CREATE INDEX %(index)s ON %(schema)s.%(table)s USING gin ( %(column)s gin_trgm_ops ) ;
""" % dict(schema=sql_identifier(self.table.schema.name),
           table=sql_identifier(self.table.name),
           column=sql_identifier(self.name),
           index=sql_identifier("%s_%s_pgtrgm_idx" % (self.table.name, self.name))
       )
        else:
            return None

    def ermrest_value_map_sql(self):
        """Return SQL to construct reversed value map rows or None if not necessary.

           A reverse map is not necessary if the column type doesn't have text values.
        """
        if self.istext():
            colref = sql_identifier(self.name)
            if self.type.is_array:
                colref = 'unnest(%s)' % colref

            return 'SELECT %s::text, %s::text, %s::text, %s::text FROM %s.%s' % (
                sql_literal(self.table.schema.name),
                sql_literal(self.table.name),
                sql_literal(self.name),
                colref,
                sql_identifier(self.table.schema.name),
                sql_identifier(self.table.name)
                )
        else:
            return None
        
    def sql_def(self):
        """Render SQL column clause for table DDL."""
        parts = [
            sql_identifier(unicode(self.name)),
            str(self.type.name)
            ]
        if self.default_value:
            parts.append('DEFAULT %s' % sql_literal(self.default_value))
        return ' '.join(parts)

    def pre_delete(self, conn, cur):
        """Do any maintenance before column is deleted from table."""
        self.delete_annotation(conn, cur, None)
        
    @staticmethod
    def fromjson_single(columndoc, position, ermrest_config):
        ctype = Type.fromjson(columndoc['type'], ermrest_config)
        comment = columndoc.get('comment', None)
        annotations = columndoc.get('annotations', {})
        try:
            return Column(
                columndoc['name'],
                position,
                ctype,
                columndoc.get('default'),
                comment,
                annotations
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
        return dict(
            name=self.name, 
            type=self.type.prejson(),
            default=self.default_value,
            comment=self.comment,
            annotations=self.annotations
            )

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
    
    def ddl(self, alias=None):
        if alias:
            name = alias
        else:
            name = self.name
        return u"%s %s" % (
            sql_identifier(name),
            self.type.sql()
            )
    

class FreetextColumn (Column):
    """Represents virtual table column for free text search.

       This is a tsvector computed by appending all text-type columns
       as a document, sorted by column order.
    """
    
    def __init__(self, table):
        Column.__init__(self, '*', None, Type('tsvector'), None)

        self.table = table
        
        self.srccols = [ c for c in table.columns.itervalues() if c.istext() ]
        self.srccols.sort(key=lambda c: c.position)

    def sql_name_with_talias(self, talias, output=False):
        if talias:
            talias += '.'
        else:
            # allow fall-through without talias. prefix
            talias = ''

        if output:
            # output column reference as whole-row nested record
            return 'row_to_json(%s*)' % talias
        else:
            # internal column reference for predicate evaluation
            colnames = [ '%s%s' % (talias, c.sql_name()) for c in self.srccols ]
            if colnames:
                return " || ' ' || ".join([ "COALESCE(%s::text,''::text)" % name for name in colnames ])
            else:
                return "''::text"

    def is_star_column(self):
        return True

    def textsearch_index_sql(self):
        return """
DROP INDEX IF EXISTS %(index)s ;
CREATE INDEX %(index)s ON %(schema)s.%(table)s USING gin (
  (to_tsvector('english'::regconfig, %(fulltext)s))
);
""" % dict(
            schema=sql_identifier(self.table.schema.name),
            table=sql_identifier(self.table.name),
            index=sql_identifier("%s__tsvector_idx" % self.table.name),
            fulltext=self.sql_name_with_talias(None)
           )

    def pg_trgm_index_sql(self):
        return """
DROP INDEX IF EXISTS %(index)s ;
CREATE INDEX %(index)s ON %(schema)s.%(table)s USING gin (
  (%(fulltext)s) gin_trgm_ops
);
""" % dict(
            schema=sql_identifier(self.table.schema.name),
            table=sql_identifier(self.table.name),
            index=sql_identifier("%s__pgtrgm_idx" % self.table.name),
            fulltext=self.sql_name_with_talias(None)
           )

