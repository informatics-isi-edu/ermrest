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
from ..util import sql_identifier, sql_literal, view_exists
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

class Model (object):
    """Represents a database model.
    
    At present, this amounts to a collection of 'schemas' in the conventional
    database sense of the term.
    """
    
    def __init__(self, schemas=None):
        if schemas is None:
            schemas = dict()
        self.schemas = schemas
    
    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            schemas=dict([ 
                    (s, self.schemas[s].prejson()) for s in self.schemas 
                    ])
            )
        
    def lookup_schema(self, sname):
        if sname in self.schemas:
            return self.schemas[sname]
        else:
            web.debug(sname)
            raise exception.ConflictModel('Schema %s does not exist.' % sname)

    def lookup_table(self, sname, tname):
        if sname is not None:
            if sname not in self.schemas:
                web.debug(sname, self.schemas)
                raise exception.ConflictModel('Schema %s does not exist.' % sname)
            if tname not in self.schemas[sname].tables:
                raise exception.ConflictModel('Table %s does not exist in schema %s.' % (tname, sname))
            return self.schemas[sname].tables[tname]
        else:
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
    
    def lookup_foreign_key_ref(self, fk_sname, fk_tname, fk_cnames, pk_sname, pk_tname, pk_cnames):
        fk_table = self.lookup_table(fk_sname, fk_tname)
        pk_table = self.lookup_table(pk_sname, pk_tname)

        fk_columns = [ fk_table.lookup_column(cname) for cname in fk_cnames ]
        pk_columns = [ pk_table.lookup_column(cname) for cname in pk_cnames ]

        fk_colset = frozenset(fk_columns)
        pk_colset = frozenset(pk_columns)
        fk_ref_map = frozendict(dict(map(lambda fc, tc: (fc, tc), fk_columns, pk_columns)))

        if fk_colset not in fk_table.fkeys:
            raise exception.ConflictModel('Foreign key %s not in table %s.' % (fk_colset, fk_table))

        fk = fk_table.fkeys[fk_colset]

        if fk_ref_map not in fk.references:
            raise exception.ConflictModel('Foreign key reference %s to %s not in table %s.' % (fk_columns, pk_columns))

        return fk.references[fk_ref_map]

    def create_schema(self, conn, cur, sname):
        """Add a schema to the model."""
        if sname == '_ermrest':
            raise exception.ConflictModel('Requested schema %s is a reserved schema name.' % sname)
        if sname in self.schemas:
            raise exception.ConflictModel('Requested schema %s already exists.' % sname)
        cur.execute("""
CREATE SCHEMA %s ;
SELECT _ermrest.model_change_event();
""" % sql_identifier(sname))
        return Schema(self, sname)

    def delete_schema(self, conn, cur, sname):
        """Remove a schema from the model."""
        if sname not in self.schemas:
            raise exception.ConflictModel('Requested schema %s does not exist.' % sname)
        cur.execute("""
DROP SCHEMA %s ;
SELECT _ermrest.model_change_event();
""" % sql_identifier(sname))
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
        
class Schema (object):
    """Represents a database schema.
    
    At present, this has a 'name' and a collection of database 'tables'. It 
    also has a reference to its 'model'.
    """
    
    def __init__(self, model, name):
        self.model = model
        self.name = name
        self.tables = dict()
        
        if name not in self.model.schemas:
            self.model.schemas[name] = self

    def verbose(self):
        return json.dumps(self.prejson(), indent=2)

    def prejson(self):
        return dict(
            schema_name=self.name.encode('utf8'),
            tables=dict([
                    (t, self.tables[t].prejson()) for t in self.tables
                    ])
            )

    def delete_table(self, conn, cur, tname):
        """Drop a table from the schema."""
        if tname not in self.tables:
            raise exception.ConflictModel('Requested table %s does not exist in schema %s.' % (tname, self.name))
        self.tables[tname].pre_delete(conn, cur)
        # we keep around a bumped version for table as a tombstone to invalidate any old cached results
        cur.execute("""
DROP TABLE %(sname)s.%(tname)s ;
SELECT _ermrest.model_change_event();
SELECT _ermrest.data_change_event(%(snamestr)s, %(tnamestr)s);
""" % dict(sname=sql_identifier(self.name), 
           tname=sql_identifier(tname),
           snamestr=sql_literal(self.name), 
           tnamestr=sql_literal(tname)
           )
                    )
        del self.tables[tname]

