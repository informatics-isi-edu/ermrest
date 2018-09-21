
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

from .. import exception
from ..util import sql_identifier, sql_literal, view_exists, udecode
from .misc import AltDict, Annotatable, HasAcls, enforce_63byte_id, current_request_snaptime
from .table import Table, LiveTableLazy, HistTableLazy
from .column import Column

import json
import web

@Annotatable.annotatable
@HasAcls.hasacls
class Model (HasAcls, Annotatable):
    """Represents a database model.
    
    At present, this amounts to a collection of 'schemas' in the conventional
    database sense of the term.
    """
    _model_restype = 'catalog'
    _model_keying = {}

    _acls_supported = { "owner", "create", "enumerate", "write", "insert", "update", "delete", "select" }
    _acls_rights = { "owner", "create" }
    _acls_can_remove = False

    def __init__(self, snapwhen, amendver, annotations={}, acls={}):
        super(Model, self).__init__()
        self.snaptime = snapwhen
        self.amendver = amendver
        self.rid = '0' # hard-coded for consistency w/ other model-storage tables
        self.last_access = None # hack: slot to track LRU state for model_cache
        self.schemas = AltDict(
            lambda k: exception.ConflictModel(u"Schema %s does not exist." % k),
            lambda k, v: enforce_63byte_id(k, "Schema"),
            lazy_get=self._lazy_get_schema,
        )
        self.acls.update(acls)
        self.annotations.update(annotations)

    def _acls_getparent(self):
        return None

    def _lazy_get_schema(self, sname):
        raise KeyError(sname)

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self, brief=False, snaptime=None):
        if snaptime is None:
            # this is model snaptime, but catalog reuses representation w/ catalog snaptime!
            cur = web.ctx.ermrest_catalog_pc.cur
            cur.execute("SELECT _ermrest.tstzencode(%s::timestamptz);" % sql_literal(self.snaptime))
            snaptime = cur.fetchone()[0]
        doc = {
            "snaptime": snaptime,
            "annotations": self.annotations,
            "rights": self.rights(),
        }
        if not brief:
            doc["schemas"] = {
                sname: schema.prejson()
                for sname, schema in self.schemas.items()
                if schema.has_right('enumerate')
            }
        if self.has_right('owner'):
            doc['acls'] = self.acls
        return doc

    def etag(self, mutation_cur=None):
        """Produce ETag for this model or for the model resulting from this mutation request.

           mutation_cur:
             None (default): produce ETag for model at start of request.
             live cursor: produce ETag for new model produced as result of this request.
        """
        if mutation_cur is not None:
            return current_request_snaptime(mutation_cur)
        elif self.amendver is not None:
            return '%s-%s' % (self.snaptime, self.amendver)
        else:
            return '%s' % self.snaptime

    def check_primary_keys(self, require):
        for schema in self.schemas.values():
            schema.check_primary_keys(require)

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
        enforce_63byte_id(sname)
        if sname == '_ermrest':
            raise exception.ConflictModel('Requested schema %s is a reserved schema name.' % sname)
        if sname in self.schemas:
            raise exception.ConflictModel('Requested schema %s already exists.' % sname)
        self.enforce_right('create')
        cur.execute("""
CREATE SCHEMA %(schema)s ;
SELECT _ermrest.model_version_bump();
INSERT INTO _ermrest.known_schemas (oid, schema_name, "comment")
SELECT oid, schema_name, "comment"
 FROM _ermrest.introspect_schemas WHERE schema_name = %(schema_str)s
RETURNING "RID";
""" % dict(schema=sql_identifier(sname), schema_str=sql_literal(sname)))
        srid = cur.next()[0]
        newschema = Schema(self, sname, rid=srid)
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
DROP SCHEMA %(schema)s ;
DELETE FROM _ermrest.known_schemas WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % dict(schema=sql_identifier(sname), rid=sql_literal(schema.rid)))
        del self.schemas[sname]

@Annotatable.annotatable
@HasAcls.hasacls
class Schema (HasAcls, Annotatable):
    """Represents a database schema.
    
    At present, this has a 'name' and a collection of database 'tables'. It 
    also has a reference to its 'model'.
    """
    _model_restype = 'schema'
    _model_keying = {
        "schema_rid": ('text', lambda self: self.rid)
    }

    _acls_supported = { "owner", "create", "enumerate", "write", "insert", "update", "delete", "select" }
    _acls_rights = { "owner", "create" }

    def __init__(self, model, name, comment=None, annotations={}, acls={}, rid=None, add_to_model=True):
        super(Schema, self).__init__()
        self.model = model
        self.rid = rid
        self.name = name
        self.comment = comment
        self.tables = AltDict(
            lambda k: exception.ConflictModel(u"Table %s does not exist in schema %s." % (k, unicode(self.name))),
            lambda k, v: enforce_63byte_id(k, "Table"),
            lazy_get=self._lazy_get_table,
        )
        self.annotations.update(annotations)
        self.acls.update(acls)
        
        if add_to_model and name not in self.model.schemas:
            self.model.schemas[name] = self

    def _annotation_key_error(self, key):
        return exception.NotFound(u'annotation "%s" on schema "%s"' % (key, unicode(self.name)))

    def _acls_getparent(self):
        return self.model

    def _lazy_get_table(self, tname):
        raise KeyError(tname)

    @staticmethod
    def create_fromjson(conn, cur, model, schemadoc, ermrest_config):
        sname = schemadoc.get('schema_name')
        comment = schemadoc.get('comment')
        annotations = schemadoc.get('annotations', {})
        acls = schemadoc.get('acls', {})
        tables = schemadoc.get('tables', {})
        
        schema = model.create_schema(conn, cur, sname)
        
        schema.set_comment(conn, cur, comment)
        schema.set_annotations(conn, cur, annotations)
        schema.set_acls(cur, acls)
            
        for k, tabledoc in tables.items():
            tname = tabledoc.get('table_name', k)
            if k != tname:
                raise exception.BadData('JSON table key %s does not match table_name %s' % (k, tname))
            tabledoc['table_name'] = tname
            table = Table.create_fromjson(conn, cur, schema, tabledoc, ermrest_config)
            
        return schema
        
    def __unicode__(self):
        return u"%s" % self.name

    def set_comment(self, conn, cur, comment):
        """Set SQL comment."""
        self.enforce_right('owner')
        cur.execute("""
COMMENT ON SCHEMA %(sname)s IS %(comment)s;
UPDATE _ermrest.known_schemas SET "comment" = %(comment)s WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % dict(
    sname=sql_identifier(self.name),
    rid=sql_literal(self.rid),
    comment=sql_literal(comment)
)
        )
        self.comment = comment

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        doc = {
            "RID": self.rid,
            "schema_name": self.name,
            "comment": self.comment,
            "rights": self.rights(),
            "annotations": self.annotations,
            "tables": {
                tname: table.prejson()
                for tname, table in self.tables.items()
                if table.has_right('enumerate')
            }
        }
        if self.has_right('owner'):
            doc['acls'] = self.acls
        return doc

    def check_primary_keys(self, require):
        for table in self.tables.values():
            table.check_primary_keys(require)

    def delete_table(self, conn, cur, tname):
        """Drop a table from the schema."""
        if tname not in self.tables:
            raise exception.ConflictModel(u'Requested table %s does not exist in schema %s.' % (udecode(tname), udecode(self.name)))
        self.tables[tname].delete(conn, cur)
        del self.tables[tname]

class HistSchemaLazy (Schema):
    def __init__(self, model, rid, name, comment, acls, annotations, rights):
        Schema.__init__(self, model, name, comment, annotations, acls, rid, add_to_model=False)
        self.rights = dict(rights)

    _get_table_sql = """
EXECUTE ermrest_hist_table(%(schema_rid)s, %(tname)s, %(roles)s);
"""
    _get_table_cls = HistTableLazy

    def _lazy_get_table(self, tname):
        self.model.cur.execute(
            self._get_table_sql % {
                'schema_rid': sql_literal(self.rid),
                'tname': sql_literal(tname),
                'snapwhen': self.model.snaptime_sql,
                'roles': self.model.client_roles_sql,
            }
        )
        for rid, srid, table_name, kind, comment, coldocs, acls, annotations, rights in list(self.model.cur):
            try:
                return self._get_table_cls(self, rid, table_name, kind, coldocs, comment, acls, annotations, rights)
            except KeyError as te:
                raise NotImplementedError(te)
        raise KeyError(tname)

    def has_right(self, aclname):
        return self.rights[aclname]

class LiveSchemaLazy (HistSchemaLazy):
    _get_table_sql = """
EXECUTE ermrest_live_table(%(schema_rid)s, %(tname)s, %(roles)s);
"""
    _get_table_cls = LiveTableLazy

class HistModelLazy (Model):
    def __init__(self, conn, typesengine, snapwhen, amendver):
        Model.__init__(self, snapwhen, amendver)
        self.conn = conn
        self.cur = conn.cursor()
        self.typesengine = typesengine
        self.client_roles = web.ctx.ermrest_client_roles
        self.client_roles_sql = web.ctx.ermrest_client_roles_sql
        self.snaptime_sql = sql_literal(snapwhen)
        self.rights = dict()
        self._populate_model()

    _populate_model_sql = """
EXECUTE ermrest_past_catalogs(%(snapwhen)s, %(roles)s);
"""
    def _populate_model(self):
        self.cur.execute(
            self._populate_model_sql % {
                'snapwhen': self.snaptime_sql,
                'roles': self.client_roles_sql,
            }
        )
        for acls, annotations, rights in self.cur:
            # success when we have enumerable catalog
            self.acls = acls
            self.annotations = annotations
            self.rights = rights
            return
        # treat non-enumeration like not found
        raise exception.NotFound(u'catalog')

    _get_schema_sql = """
EXECUTE ermrest_past_schema(%(sname)s, %(roles)s);
"""
    _get_schema_cls = HistSchemaLazy

    def _lazy_get_schema(self, sname):
        self.cur.execute(
            self._get_schema_sql % {
                'sname': sql_literal(sname),
                'snapwhen': self.snaptime_sql,
                'roles': self.client_roles_sql,
            }
        )
        for rid, schema_name, comment, acls, annotations, rights in list(self.cur):
            return self._get_schema_cls(self, rid, schema_name, comment, acls, annotations, rights)
        raise KeyError(sname)

    def has_right(self, aclname):
        return self.rights[aclname]

class LiveModelLazy (HistModelLazy):
    def __init__(self, conn, typesengine, snapwhen_key):
        HistModelLazy.__init__(self, conn, typesengine, snapwhen_key, None)

    _populate_model_sql = """
EXECUTE ermrest_live_catalogs(%(roles)s);
"""
    _get_schema_sql = """
EXECUTE ermrest_live_schema(%(sname)s, %(roles)s);
"""
    _get_schema_cls = LiveSchemaLazy

