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
from ..util import sql_identifier, view_exists
from .misc import AltDict, commentable, annotatable
from .table import Table

import json
import web

class Model (object):
    """Represents a database model.
    
    At present, this amounts to a collection of 'schemas' in the conventional
    database sense of the term.
    """
    
    def __init__(self, schemas=None):
        if schemas is None:
            schemas = AltDict(lambda k: exception.ConflictModel(u"Schema %s does not exist." % k))
        self.schemas = schemas
    
    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            schemas=dict([ 
                    (s, self.schemas[s].prejson()) for s in self.schemas 
                    ])
            )
        
    def lookup_table(self, tname):
        """Lookup an unqualified table name if and only if it is unambiguous across schemas."""
        tables = set()

        for schema in self.schemas.values():
            if tname in schema.tables:
                tables.add( schema.tables[tname] )

        if len(tables) == 0:
            raise exception.ConflictModel('Table %s does not exist.' % tname)
        elif len(tables) > 1:
            raise exception.ConflictModel('Table name %s is ambiguous.' % tname)
        else:
            return tables.pop()
    
    def create_schema(self, conn, cur, sname):
        """Add a schema to the model."""
        if sname == '_ermrest':
            raise exception.ConflictModel('Requested schema %s is a reserved schema name.' % sname)
        if sname in self.schemas:
            raise exception.ConflictModel('Requested schema %s already exists.' % sname)
        cur.execute("""
CREATE SCHEMA %(schema)s ;
SELECT _ermrest.model_change_event();
""" % dict(schema=sql_identifier(sname)))
        return Schema(self, sname)

    def delete_schema(self, conn, cur, sname):
        """Remove a schema from the model."""
        if sname not in self.schemas:
            raise exception.ConflictModel('Requested schema %s does not exist.' % sname)
        cur.execute("""
DROP SCHEMA %s ;
SELECT _ermrest.model_change_event();
""" % sql_identifier(sname))
        self.schemas[sname].delete_annotation(conn, cur, None)
        del self.schemas[sname]

    def recreate_value_map(self, conn, cur, empty=False):
        vmap_parts = []
        for schema in self.schemas.values():
            for table in schema.tables.values():
                for column in table.columns.values():
                    part = column.ermrest_value_map_sql()
                    if part:
                        vmap_parts.append(part)

        if empty or not vmap_parts:
            # create a dummy/empty view if no data sources exist (or empty table is requested)
            vmap_parts = ["SELECT 's'::text, 't'::text, 'c'::text, 'v'::text WHERE False"]

        if view_exists(cur, '_ermrest', 'valuemap'):
            cur.execute("DROP MATERIALIZED VIEW IF EXISTS _ermrest.valuemap ;")
                        
        cur.execute("""
DROP TABLE IF EXISTS _ermrest.valuemap ;
CREATE TABLE _ermrest.valuemap ("schema", "table", "column", "value")
AS %s ;
CREATE INDEX _ermrest_valuemap_cluster_idx ON _ermrest.valuemap ("schema", "table", "column");
CREATE INDEX _ermrest_valuemap_value_idx ON _ermrest.valuemap USING gin ( "value" gin_trgm_ops );
""" % ' UNION '.join(vmap_parts)
                )

@commentable()
@annotatable('schema', dict(
    schema_name=('text', lambda self: unicode(self.name))
    )
)
class Schema (object):
    """Represents a database schema.
    
    At present, this has a 'name' and a collection of database 'tables'. It 
    also has a reference to its 'model'.
    """
    
    def __init__(self, model, name, comment=None, annotations={}):
        self.model = model
        self.name = name
        self.comment = comment
        self.tables = AltDict(lambda k: exception.ConflictModel(u"Table %s does not exist in schema %s." % (k, self)))
        self.annotations = dict()
        self.annotations.update(annotations)
        
        if name not in self.model.schemas:
            self.model.schemas[name] = self

    @staticmethod
    def introspect_annotation(model=None, schema_name=None, annotation_uri=None, annotation_value=None):
        model.schemas[schema_name].annotations[annotation_uri] = annotation_value

    @staticmethod
    def create_fromjson(conn, cur, model, schemadoc, ermrest_config):
        sname = schemadoc.get('schema_name')
        comment = schemadoc.get('comment')
        annotations = schemadoc.get('annotations', {})
        tables = schemadoc.get('tables', {})
        
        schema = model.create_schema(conn, cur, sname)
        
        schema.set_comment(conn, cur, comment)
        
        for k, v in annotations.items():
            schema.set_annotation(conn, cur, k, v)
            
        for k, tabledoc in tables.items():
            tname = tabledoc.get('table_name', k)
            if k != tname:
                raise exception.BadData('JSON table key %s does not match table_name %s' % (k, tname))
            tabledoc['table_name'] = tname
            table = Table.create_fromjson(conn, cur, schema, tabledoc, ermrest_config)
            
        return schema
        
    def __unicode__(self):
        return u"%s" % self.name

    def sql_comment_resource(self):
        return u'SCHEMA %s' % sql_identifier(unicode(self.name))
    
    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            schema_name=self.name,
            comment=self.comment,
            annotations=self.annotations,
            tables=dict([
                    (t, self.tables[t].prejson()) for t in self.tables
                    ])
            )

    def delete_table(self, conn, cur, tname):
        """Drop a table from the schema."""
        if tname not in self.tables:
            raise exception.ConflictModel('Requested table %s does not exist in schema %s.' % (tname, self.name))
        self.tables[tname].delete(conn, cur)
        del self.tables[tname]

