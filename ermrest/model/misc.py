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
from ..util import sql_identifier, sql_literal, view_exists, table_exists
from .type import _default_config

import json
import web

def frozendict (d):
    """Convert a dictionary to a canonical and immutable form."""
    items = d.items()
    items.sort() # sort by key, value pair
    return tuple(items)
        
def _get_ermrest_config():
    """Helper method to return the ERMrest config.
    """ 
    if web.ctx and 'ermrest_config' in web.ctx:
        return web.ctx['ermrest_config']
    else:
        return _default_config

class AltDict (dict):
    """Alternative dict that raises custom errors."""
    def __init__(self, keyerror):
        dict.__init__(self)
        self._keyerror = keyerror

    def __getitem__(self, k):
        try:
            return dict.__getitem__(self, k)
        except KeyError:
            raise self._keyerror(k)

def commentable():
    """Decorator to add comment storage access interface to model classes.
    """
    def set_comment(self, conn, cur, comment):
        """Set SQL comment."""
        resources = self.sql_comment_resource()
        if not isinstance(resources, set):
            # backwards compatibility
            resources = set([resources])
        for resource in resources:
            cur.execute("""
COMMENT ON %s IS %s;
SELECT _ermrest.model_change_event();
""" % (resource, sql_literal(comment))
            )
    
    def helper(orig_class):
        setattr(orig_class, 'set_comment', set_comment)
        return orig_class
    return helper
        
annotatable_classes = []
        
def annotatable(restype, keying):
    """Decorator to add annotation storage access interface to model classes.

       restype: the string name for the resource type, used to name storage, 
       e.g. "table" for annotations on tables.

       keying: dictionary of column names mapped to (psql_type, function) pairs
         which define the Postgres storage type and compute 
         literals for those columns to key the individual annotations.

    """
    def _interp_annotation(self, key, sql_wrap=True):
        if sql_wrap:
            sql_wrap = sql_literal
        else:
            sql_wrap = lambda v: v
        return dict([
            (k, sql_wrap(v[1](self))) for k, v in keying.items()
        ] + [
            ('annotation_uri', sql_wrap(key))
        ])
        
    def set_annotation(self, conn, cur, key, value):
        """Set annotation on %s, returning previous value for updates or None.""" % restype
        assert key is not None
        if value is None:
            raise exception.BadData('Null value is not a valid annotation.')
        interp = self._interp_annotation(key)
        where = ' AND '.join([
            "%s = %s" % (sql_identifier(k), v)
            for k, v in interp.items()
        ])
        cur.execute("""
SELECT _ermrest.model_change_event();
UPDATE _ermrest.model_%s_annotation 
SET annotation_value = %s
WHERE %s 
RETURNING annotation_value;
""" % (restype, sql_literal(json.dumps(value)), where)
        )
        for oldvalue in cur:
            # happens zero or one time
            return oldvalue

        # only run this if update returned empty set
        columns = ', '.join([sql_identifier(k) for k in interp.keys()] + ['annotation_value'])
        values = ', '.join([interp[k] for k in interp.keys()] + [sql_literal(json.dumps(value))])
        cur.execute("""
INSERT INTO _ermrest.model_%s_annotation (%s) VALUES (%s);
""" % (restype, columns, values)
        )
        return None

    def delete_annotation(self, conn, cur, key):
        """Delete annotation on %s.""" % restype
        interp = self._interp_annotation(key)
        if key is None:
            del interp['annotation_uri']
        where = ' AND '.join([
            "%s = %s" % (sql_identifier(k), v)
            for k, v in interp.items()
        ])
        cur.execute("""
SELECT _ermrest.model_change_event();
DELETE FROM _ermrest.model_%s_annotation WHERE %s;
""" % (restype, where)
        )

    @classmethod
    def create_storage_table(orig_class, cur):
        if table_exists(cur, '_ermrest', 'model_%s_annotation' % restype):
            return
        keys = keying.keys() + ['annotation_uri']
        cur.execute("""
CREATE TABLE _ermrest.model_%(restype)s_annotation (%(cols)s);
GRANT SELECT ON _ermrest.model_%(restype)s_annotation TO ermrest;
""" % dict(
    restype=restype,
    cols=', '.join([ '%s %s NOT NULL' % (sql_identifier(k), keying.get(k, ('text', None))[0]) for k in keys ]
                   + [
                       'annotation_value json',
                       'UNIQUE(%s)' % ', '.join([ sql_identifier(k) for k in keys ])
                   ]
    )
)
        )
        
    @classmethod
    def introspect_helper(orig_class, cur, model):
        """Introspect annotations on %s, adding them to model.""" % restype
        keys = keying.keys() + ['annotation_uri', 'annotation_value']
        cur.execute("""
SELECT %s FROM _ermrest.model_%s_annotation;
""" % (
    ','.join([ sql_identifier(k) for k in keys]),
    restype
)
        )
        for row in cur:
            kwargs = dict([ (keys[i], row[i]) for i in range(len(keys)) ])
            kwargs['model'] = model
            try:
                orig_class.introspect_annotation(**kwargs)
            except exception.ConflictModel:
                # TODO: prune orphaned annotation?
                pass
                
    def helper(orig_class):
        setattr(orig_class, '_interp_annotation', _interp_annotation)
        setattr(orig_class, 'set_annotation', set_annotation)
        setattr(orig_class, 'delete_annotation', delete_annotation)
        setattr(orig_class, '_annotation_keying', keying)
        if hasattr(orig_class, 'introspect_annotation'):
            setattr(orig_class, 'introspect_helper', introspect_helper)
        setattr(orig_class, 'create_storage_table', create_storage_table)
        annotatable_classes.append(orig_class)
        return orig_class
    return helper

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
GRANT USAGE ON SCHEMA %(schema)s TO ermrest;
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
GRANT SELECT ON _ermrest.valuemap TO ermrest;
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

