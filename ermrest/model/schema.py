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
from .misc import AltDict, AclDict, commentable, annotatable, hasacls
from .table import Table

import json
import web

@hasacls(
    'model',
    { },
    { "owner", "create", "enumerate", "write", "insert", "update", "delete", "select", "reference"},
    None
)
class Model (object):
    """Represents a database model.
    
    At present, this amounts to a collection of 'schemas' in the conventional
    database sense of the term.
    """
    
    def __init__(self, version, schemas=None):
        self.version = version
        if schemas is None:
            schemas = AltDict(lambda k: exception.ConflictModel(u"Schema %s does not exist." % k))
        self.schemas = schemas
        self.acls = AclDict(self)
    
    @staticmethod
    def introspect_acl(model=None, acl=None, members=None):
        model.acls[acl] = members

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        doc = dict(
            schemas=dict([ 
                (s, self.schemas[s].prejson()) for s in self.schemas
            ])
        )
        if self.has_right('owner'):
            doc['acls'] = self.acls
        return doc
        
    def lookup_table(self, tname):
        """Lookup an unqualified table name if and only if it is unambiguous across schemas."""
        tables = set()

        for schema in self.schemas.values():
            if schema.has_right('enumerate'):
                if tname in schema.tables:
                    table = schema.tables[tname]
                    if table.has_right('enumerate'):
                        tables.add( table )

        if len(tables) == 0:
            raise exception.ConflictModel('Table %s not found in model.' % tname)
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
        self.enforce_right('create')
        cur.execute("""
CREATE SCHEMA %(schema)s ;
SELECT _ermrest.model_change_event();
""" % dict(schema=sql_identifier(sname)))
        newschema = Schema(self, sname)
        if not self.has_right('owner'):
            newschema.acls['owner'] = [web.ctx.webauthn2_context.client] # so enforcement won't deny next step...
            newschema.set_acl(cur, 'owner', [web.ctx.webauthn2_context.client])
        return newschema

    def delete_schema(self, conn, cur, sname):
        """Remove a schema from the model."""
        schema = self.schemas[sname]
        schema.enforce_right('owner')
        self.schemas[sname].delete_annotation(conn, cur, None)
        self.schemas[sname].delete_acl(cur, None, purging=True)
        cur.execute("""
DROP SCHEMA %s ;
SELECT _ermrest.model_change_event();
""" % sql_identifier(sname))
        del self.schemas[sname]

@commentable()
@annotatable('schema', dict(
    schema_name=('text', lambda self: unicode(self.name))
    )
)
@hasacls(
    'schema',
    { "schema_name": ('text', lambda self: unicode(self.name)) },
    { "owner", "create", "enumerate", "write", "insert", "update", "delete", "select", "reference"},
    lambda self: self.model
)
class Schema (object):
    """Represents a database schema.
    
    At present, this has a 'name' and a collection of database 'tables'. It 
    also has a reference to its 'model'.
    """
    
    def __init__(self, model, name, comment=None, annotations={}, acls={}):
        self.model = model
        self.name = name
        self.comment = comment
        self.tables = AltDict(lambda k: exception.ConflictModel(u"Table %s does not exist in schema %s." % (k, unicode(self.name))))
        self.annotations = AltDict(lambda k: exception.NotFound(u'annotation "%s" on schema "%s"' % (k, unicode(self.name))))
        self.annotations.update(annotations)

        self.acls = AclDict(self)
        self.acls.update(acls)
        
        if name not in self.model.schemas:
            self.model.schemas[name] = self

    @staticmethod
    def introspect_annotation(model=None, schema_name=None, annotation_uri=None, annotation_value=None):
        model.schemas[schema_name].annotations[annotation_uri] = annotation_value

    @staticmethod
    def introspect_acl(model=None, schema_name=None, acl=None, members=None):
        model.schemas[schema_name].acls[acl] = members

    @staticmethod
    def create_fromjson(conn, cur, model, schemadoc, ermrest_config):
        sname = schemadoc.get('schema_name')
        comment = schemadoc.get('comment')
        annotations = schemadoc.get('annotations', {})
        acls = schemadoc.get('acls', {})
        tables = schemadoc.get('tables', {})
        
        schema = model.create_schema(conn, cur, sname)
        
        schema.set_comment(conn, cur, comment)
        
        for k, v in annotations.items():
            schema.set_annotation(conn, cur, k, v)

        for k, v in acls.items():
            schema.set_acl(cur, k, v)
            
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
        doc = dict(
            schema_name=self.name,
            comment=self.comment,
            annotations=self.annotations,
            tables=dict([
                    (t, self.tables[t].prejson()) for t in self.tables
                    ])
            )
        if self.has_right('owner'):
            doc['acls'] = self.acls
        return doc

    def delete_table(self, conn, cur, tname):
        """Drop a table from the schema."""
        if tname not in self.tables:
            raise exception.ConflictModel('Requested table %s does not exist in schema %s.' % (tname, self.name))
        self.tables[tname].delete(conn, cur)
        del self.tables[tname]

