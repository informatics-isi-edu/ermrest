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
from ..util import sql_identifier, sql_literal, table_exists
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
            self.comment = comment
    
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

