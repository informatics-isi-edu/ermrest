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
            result = dict.__getitem__(self, k)
            return result
        except KeyError:
            raise self._keyerror(k)

    def get_enumerable(self, k):
        result = self[k]
        if not result.has_right('enumerate'):
            raise self._keyerror(k)
        return result

class AclDict (dict):
    """Alternative dict that validates keys and returns default."""
    def __init__(self, subject):
        dict.__init__(self)
        self._subject = subject

    def __getitem__(self, k):
        if k not in self._subject._acls_supported:
            raise exception.NotFound('ACL %s on %s' % (k, self._subject))
        try:
            return dict.__getitem__(self, k)
        except KeyError, e:
            return None

def commentable():
    """Decorator to add comment storage access interface to model classes.
    """
    def set_comment(self, conn, cur, comment):
        """Set SQL comment."""
        self.enforce_right('owner')
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
        self.enforce_right('owner')
        interp = self._interp_annotation(key)
        where = ' AND '.join([
            "new.%(col)s = old.%(col)s AND new.%(col)s = %(val)s" % dict(col=sql_identifier(k), val=v)
            for k, v in interp.items()
        ])
        cur.execute("""
SELECT _ermrest.model_change_event();
UPDATE _ermrest.model_%(restype)s_annotation new
SET annotation_value = %(newval)s
FROM _ermrest.model_%(restype)s_annotation old
WHERE %(where)s
RETURNING old.annotation_value;
""" % dict(
    restype=restype,
    newval=sql_literal(json.dumps(value)),
    where=where
)
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
        self.enforce_right('owner')
        interp = self._interp_annotation(key)
        if key is None:
            del interp['annotation_uri']
        keys = interp.keys()
        where = ' AND '.join([
            "%s = %s" % (sql_identifier(k), interp[k])
            for k in keys
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

hasacls_classes = []

def hasacls(restype, keying, acls, getparent):
    """Decorator to add ACL storage access interface to model classes.

       restype: string to distinguish resource types for storage table naming

       keying: { colname: (psql_type, getkey_func), ... }

       acls: { aclname, ... }

       getparent: getparent_func
    """
    def _interp_acl(self, aclname):
        interp = {
            k: sql_literal(v[1](self))
            for k, v in keying.items()
        }
        interp['acl'] = sql_literal(aclname)
        return interp

    @classmethod
    def create_acl_storage_table(orig_class, cur):
        if table_exists(cur, '_ermrest', 'model_%s_acl' % restype):
            return
        keys = keying.keys() + ['acl']
        cur.execute("""
CREATE TABLE _ermrest.model_%(restype)s_acl (%(cols)s);
""" % dict(
    restype=restype,
    cols=', '.join([
        '%s %s NOT NULL' % (sql_identifier(k), keying.get(k, ('text', None))[0])
        for k in keys
    ] + [
        'members text[]',
        'UNIQUE(%s)' % ', '.join([ sql_identifier(k) for k in keys ])
    ])
)
        )

    @classmethod
    def introspect_acl_helper(orig_class, cur, model):
        keys = keying.keys() + ['acl', 'members']
        cur.execute("""
SELECT %(keys)s FROM _ermrest.model_%(restype)s_acl;
""" % dict(
    restype=restype,
    keys=', '.join([ sql_identifier(k) for k in keys ])
)
        )
        for row in cur:
            kwargs = dict([ (keys[i], row[i]) for i in range(len(keys)) ])
            kwargs['model'] = model
            try:
                orig_class.introspect_acl(**kwargs)
            except exception.ConflictModel:
                # TODO: prune orphaned ACL?
                pass

    def set_acl(self, cur, aclname, members):
        """Set annotation on %s, returning previous value for updates or None.""" % restype
        assert aclname is not None

        if members is None:
            return self.delete_acl(cur, aclname)

        self.enforce_right('owner') # pre-flight authz
        if aclname not in self._acls_supported:
            raise exception.ConflictData('ACL name %s not supported on %s.' % (aclname, self))

        self.acls[aclname] = members
        self.enforce_right('owner') # integrity check using Python data...

        interp = self._interp_acl(aclname)
        keys = interp.keys()
        where = ' AND '.join([
            'new.%(col)s = old.%(col)s AND new.%(col)s = %(val)s' % dict(col=sql_identifier(k), val=interp[k])
            for k in keys
        ])
        cur.execute("""
SELECT _ermrest.model_change_event();
UPDATE _ermrest.model_%(restype)s_acl new
SET members = %(members)s::text[]
FROM _ermrest.model_%(restype)s_acl old
WHERE %(where)s
RETURNING old.members;
""" % dict(
    restype=restype,
    members=sql_literal(list(members)),
    where=where
)
        )
        for oldvalue in cur:
            return oldvalue

        cur.execute("""
INSERT INTO _ermrest.model_%(restype)s_acl (%(columns)s, members) VALUES (%(values)s, %(members)s::text[]);
""" % dict(
    restype=restype,
    columns=', '.join([sql_identifier(k) for k in keys]),
    values=', '.join([interp[k] for k in keys]),
    members=sql_literal(members)
)
        )
        return None

    def delete_acl(self, cur, aclname, purging=False):
        interp = self._interp_acl(aclname)

        self.enforce_right('owner') # pre-flight authz

        if aclname is not None and aclname not in self._acls_supported:
            raise exception.NotFound('ACL %s on %s' % (aclname, self))

        if aclname is None:
            del interp['acl']
            self.acls.clear()
        elif aclname in self.acls:
            del self.acls[aclname]

        if not purging:
            self.enforce_right('owner') # integrity check... can't disown except when purging

        keys = interp.keys()
        where = ' AND '.join([
            '%s = %s' % (sql_identifier(k), interp[k])
            for k in keys
        ])
        cur.execute("""
SELECT _ermrest.model_change_event();
DELETE FROM _ermrest.model_%(restype)s_acl WHERE %(where)s;
""" % dict(
    restype=restype,
    where=where
    )
        )

    def has_right(self, aclname, roles=None):
        """Return access decision True, False, None.

           aclname: the symbolic name for the access mode

           roles: the client roles for whom to make a decision

        """
        sufficient_rights = {
            "owner": set(),
            "reference": set(),
            "create": {"owner"},
            "write": {"owner"},
            "insert": {"owner", "write"},
            "update": {"owner", "write"},
            "delete": {"owner", "write"},
            "select": {"owner", "write", "update", "delete"},
            "enumerate": {"owner", "create", "write", "insert", "update", "delete", "select"},
        }

        if roles is None:
            roles = set([
                r['id'] if type(r) is dict else r
                for r in web.ctx.webauthn2_context.attributes
            ])
            roles.add('*')

        if getparent is not None:
            parentres = getparent(self)
        else:
            parentres = None

        if aclname in self.acls:
            acl = self.acls[aclname]
        else:
            acl = None

        if parentres is not None:
            if parentres.has_right('owner', roles):
                # have right implicitly due to parent resource ownership rule
                return True
            elif acl is None and parentres.has_right(aclname, roles):
                # have right due to inherited parent ACL
                return True

        for aclname2 in sufficient_rights[aclname]:
            if self.has_right(aclname2, roles):
                # have right implicitly due to another sufficient right
                return True

        if acl is not None:
            if not set(acl).isdisjoint(roles):
                # have right explicitly due to ACL intersection
                return True

        # TODO: add case for when dynamic rights are possible on this resource...
            
        # finally, static deny decision
        return False

    def enforce_right(self, aclname):
        """Policy enforcement for named right."""
        decision = self.has_right(aclname)
        if decision is False:
            # we can't stop now if decision is True or None...
            raise exception.Forbidden('%s access on %s' % (aclname, web.ctx.env['REQUEST_URI']))

    def helper(orig_class):
        setattr(orig_class, '_acl_getparent', lambda self: getparent(self))
        setattr(orig_class, '_acl_keying', keying)
        setattr(orig_class, '_acls_supported', set(acls))
        setattr(orig_class, '_interp_acl', _interp_acl)
        if not hasattr(orig_class, 'has_right'):
            setattr(orig_class, 'has_right', has_right)
        else:
            setattr(orig_class, '_has_right', has_right)
        if not hasattr(orig_class, 'enforce_right'):
            setattr(orig_class, 'enforce_right', enforce_right)
        else:
            setattr(orig_class, '_enforce_right', enforce_right)
        setattr(orig_class, 'set_acl', set_acl)
        setattr(orig_class, 'delete_acl', delete_acl)
        if hasattr(orig_class, 'introspect_acl'):
            setattr(orig_class, 'introspect_acl_helper', introspect_acl_helper)
        setattr(orig_class, 'create_acl_storage_table', create_acl_storage_table)
        hasacls_classes.append(orig_class)
        return orig_class

    return helper

