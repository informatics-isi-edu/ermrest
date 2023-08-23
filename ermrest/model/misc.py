
# 
# Copyright 2013-2023 University of Southern California
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

import json
import hashlib
import base64
from webauthn2.util import deriva_ctx

from .. import exception
from ..util import sql_identifier, sql_literal, table_exists
from .. import ermpath
from .type import _default_config
from .name import Name
from . import predicate
from ..ermpath.resource import get_dynacl_clauses

# these are in ermpath to avoid recursive imports
from ..ermpath import current_request_snaptime, current_catalog_snaptime, current_model_snaptime, normalized_history_snaptime, current_history_amendver

def frozendict (d):
    """Convert a dictionary to a canonical and immutable form."""
    return frozenset(d.items())

def _get_ermrest_config():
    """Helper method to return the ERMrest config.
    """
    try:
        return deriva_ctx.ermrest_config
    except:
        return _default_config

def enforce_63byte_id(s, prefix="Identifier"):
    if isinstance(s, Name):
        s = s.one_str()
    if not isinstance(s, str):
        raise exception.BadData(u'%s "%s" "%s" is unsupported and should be unicode string.' % (prefix, s, type(s)))
    if len(s.encode('utf8')) > 63:
        raise exception.BadData(u'%s "%s" exceeded 63-byte limit when encoded as UTF-8.' % (prefix, s))

def make_id(*components):
    """Build an identifier that will be OK for ERMrest and Postgres.

    Naively, append as '_'.join(components).

    Fallback to heuristics mixing truncation with short hashes.
    """
    # accept lists at top-level for convenience (compound keys, etc.)
    expanded = []
    for e in components:
        if isinstance(e, list):
            expanded.extend(e)
        else:
            expanded.append(e)

    # prefer to use naive name as requested
    naive_result = '_'.join(expanded)
    naive_len = len(naive_result.encode('utf8'))
    if naive_len <= 63:
        return naive_result

    # we'll need to truncate and hash in some way...
    def hash(s, nbytes):
        return base64.urlsafe_b64encode(hashlib.md5(s.encode('utf8')).digest()).decode()[0:nbytes]

    def truncate(s, maxlen):
        encoded_len = len(s.encode('utf8'))
        # we need to chop whole (unicode) chars but test encoded byte lengths!
        for i in range(max(1, len(s) - maxlen), len(s) - 1):
            result = s[0:-1 * i].rstrip()
            if len(result.encode('utf8')) <= (maxlen - 2):
                return result + '..'
        return s

    naive_hash = hash(naive_result, 5)
    parts = [
        (i, expanded[i])
        for i in range(len(expanded))
    ]

    # try to find a solution truncating individual fields
    for maxlen in [15, 12, 9]:
        parts.sort(key=lambda p: (len(p[1].encode('utf8')), p[0]), reverse=True)
        for i in range(len(parts)):
            idx, part = parts[i]
            if len(part.encode('utf8')) > maxlen:
                parts[i] = (idx, truncate(part, maxlen))
            candidate_result = '_'.join([
                p[1]
                for p in sorted(parts, key=lambda p: p[0])
            ] + [naive_hash])
            if len(candidate_result.encode('utf8')) < 63:
                return candidate_result

    # fallback to truncating original naive name
    # try to preserve suffix and trim in middle
    result = ''.join([
        truncate(naive_result, len(naive_result)//3),
        naive_result[-len(naive_result)//3:],
        '_',
        naive_hash
    ])
    if len(result.encode('utf8')) <= 63:
        return result

    # last-ditch (e.g. multibyte unicode suffix worst case)
    return truncate(naive_result, 55) + naive_hash

sufficient_rights = {
    "owner": set(),
    "create": {"owner"},
    "write": {"owner"},
    "insert": {"owner", "write"},
    "update": {"owner", "write"},
    "delete": {"owner", "write"},
    "select": {"owner", "write", "update", "delete"},
    "enumerate": {"owner", "create", "write", "insert", "update", "delete", "select"},
}

class AltDict (dict):
    """Alternative dict that raises custom errors."""
    def __init__(self, keyerror, validator=lambda k, v: (k, v)):
        dict.__init__(self)
        self._keyerror = keyerror
        self._validator = validator

    def __getitem__(self, k):
        try:
            if isinstance(k, Name):
                k = k.one_str()
            return dict.__getitem__(self, k)
        except KeyError:
            raise self._keyerror(k)
        except TypeError:
            raise self._keyerror(k)

    def __contains__(self, k):
        try:
            return dict.__contains__(self, k)
        except TypeError:
            raise exception.BadSyntax('Invalid model element name: %s' % k)

    def __setitem__(self, k, v):
        self._validator(k, v)
        return dict.__setitem__(self, k, v)

    def get_enumerable(self, k, skip_enum_check=False):
        result = self[k]
        if not result.has_right('enumerate') and not skip_enum_check:
            raise self._keyerror(k)
        return result

    def update(self, d):
        if not isinstance(d, dict):
            raise exception.BadData(u'Input %s must be a dictionary.' % json.dumps(d))
        dict.update(self, d)

class AclDict (dict):
    """Alternative dict that validates keys and returns default."""
    def __init__(self, subject, can_remove=True):
        dict.__init__(self)
        self._subject = subject
        self.can_remove = can_remove
        self._acls = None
        self.clear()

    def _digest(self):
        deriva_ctx.ermrest_model_rights_cache.clear()
        self._acls = dict()
        for aclname, members in self.items():
            if members is None:
                continue
            members = set(members)
            if aclname not in self._acls:
                self._acls[aclname] = set()
            self._acls[aclname].update(members)
            for aclname2, sufficient in sufficient_rights.items():
                if aclname in sufficient:
                    if aclname2 not in self._acls:
                        self._acls[aclname2] = set()
                    self._acls[aclname2].update(members)

    def __getitem__(self, k):
        if isinstance(k, Name):
            k = k.one_str()
        if k not in self._subject._acls_supported:
            raise exception.NotFound('ACL %s on %s' % (k, self._subject))
        try:
            return dict.__getitem__(self, k)
        except KeyError as e:
            return None

    def __contains__(self, k):
        try:
            return dict.__contains__(self, k)
        except TypeError:
            raise exception.BadSyntax('Invalid ACL name: %s' % k)

    def __setitem__(self, k, v):
        dict.__setitem__(self, k, v)
        self._digest()

    def __delitem__(self, k):
        if self.can_remove:
            dict.__delitem__(self, k)
        else:
            dict.__setitem__(self, k, [])
        self._digest()

    def update(self, d):
        if not isinstance(d, dict):
            raise exception.BadData(u'ACL set %s must be a dictionary.' % json.dumps(d))
        dict.update(self, d)
        self._digest()

    def clear(self):
        if self.can_remove:
            dict.clear(self)
        else:
            for aclname in self._subject._acls_supported:
                dict.__setitem__(self, aclname, [])
        self._digest()

    def intersects(self, aclname, roles):
        return not self._acls.get(aclname, set()).isdisjoint(roles)

class DynaclDict (dict):
    """Alternative dict specialized for dynamic acl bindings."""
    def __init__(self, subject):
        dict.__init__(self)
        self._subject = subject
        self._binding_types = None
        self._digest()

    def _digest(self):
        deriva_ctx.ermrest_model_rights_cache.clear()
        self._binding_types = set()
        for binding in self.values():
            if binding:
                self._binding_types.update(set(binding['types']))

    def __getitem__(self, k):
        try:
            result = dict.__getitem__(self, k)
            return result
        except KeyError:
            raise exception.NotFound(u"dynamic ACL binding %s on %s" % (k, self._subject))

    def __contains__(self, k):
        try:
            return dict.__contains__(self, k)
        except TypeError:
            raise exception.BadSyntax('Invalid dynamic ACL binding name: %s' % k)

    def __setitem__(self, k, v):
        dict.__setitem__(self, k, v)
        self._digest()

    def __delitem__(self, k):
        dict.__delitem__(self, k)
        self._digest()


    def update(self, d):
        if not isinstance(d, dict):
            raise exception.BadData(u'ACL binding set %s must be a dictionary.' % json.dumps(d))
        dict.update(self, d)
        self._digest()

    def clear(self):
        dict.clear(self)
        self._digest()

class AclBinding (AltDict):
    """Represents one acl binding."""
    def __init__(self, model, resource, binding_name, doc):
        def keyerror(k):
            return KeyError(k)
        def validator(k, v):
            if k == 'types':
                if type(v) is not list or len(v) == 0:
                    raise exception.BadData('Field "types" in ACL binding "%s" must be a non-empty list of type names.' % binding_name)
                for t in v:
                    if t not in resource.dynacl_types_supported:
                        raise exception.BadData('ACL binding type %r is not supported on this resource.' % t)
            elif k == 'projection':
                pass
            elif k == 'projection_type':
                if v not in ['acl', 'nonnull']:
                    raise exception.BadData('ACL binding projection-type %r is not supported.' % (v,))
            elif k == 'comment':
                if not isinstance(v, str):
                    raise exception.BadData('ACL binding comment must be of string type.')
            elif k == 'scope_acl':
                if not isinstance(v, list) or len(v) == 0:
                    raise exception.BadData('Field "scope_acl" in ACL binding "%s" must be a non-empty list of members.' % binding_name)
                for m in v:
                    if not isinstance(m, str):
                        raise exception.BadData('Field "scope_acl" in ACL binding "%s" must only contain textual member attribute names or the wildcard string.' % binding_name)
            else:
                raise exception.BadData('Field "%s" in ACL binding "%s" not recognized.' % (k, binding_name))
        AltDict.__init__(self, keyerror, validator)
        self.model = model
        self.resource = resource
        self.binding_name = binding_name

        # let AltDict validator behavior check each field above for simple stuff...
        for k, v in doc.items():
            self[k] = v

        # now check overall constraints...
        for k in ['types', 'projection']:
            if k not in self:
                raise exception.BadData('Field "%s" is required for ACL bindings.' % k)

        # validate the projection against the model
        aclpath, col, ctype = self._compile_projection()

        # set default
        if 'projection_type' not in self:
            self['projection_type'] = 'acl' if ctype.name == 'text' else 'nonnull'

        if 'scope_acl' not in self:
            self['scope_acl'] = ['*']

    def inscope(self, access_type, roles=None):
        """Return True if this ACL binding applies to this access type for this client, False otherwise."""
        if roles is None:
            roles = deriva_ctx.ermrest_client_roles
        if set(self['scope_acl']).isdisjoint(roles):
            return False
        if set(self['types']).isdisjoint(sufficient_rights[access_type].union({access_type})):
            return False
        return True

    def _compile_projection(self):
        proj = self['projection']

        if isinstance(proj, str):
            # expand syntactic sugar for bare column name projection
            proj = [proj]

        epath = ermpath.EntityPath(self.model)

        if hasattr(self.resource, 'unique'):
            epath.set_base_entity(self.resource.unique.table, 'base')
        elif hasattr(self.resource, 'table'):
            epath.set_base_entity(self.resource.table, 'base')
        else:
            epath.set_base_entity(self.resource, 'base')

        epath.add_filter(predicate.AclBasePredicate(), enforce_client=False)

        def compile_join(elem):
            # HACK: this repeats some of the path resolution logic that is tangled in the URL parser/AST code...
            lalias = elem.get('context')
            if lalias is not None:
                if not isinstance(lalias, str):
                    raise exception.BadData('Context %r in ACL binding %s must be a string literal alias name.' % (lalias, self.binding_name))
                epath.set_context(elem['context'])

            ltable = epath.current_entity_table()
            ralias = elem.get('alias')
            if ralias is not None:
                if not isinstance(ralias, str):
                    raise exception.BadData('Alias %r in ACL binding %s must be a string literal alias name.' % (lalias, self.binding_name))
            fkeyname = elem.get('inbound', elem.get('outbound'))
            if (type(fkeyname) is not list \
                or len(fkeyname) != 2 \
                or (not isinstance(fkeyname[0], str)) \
                or (not isinstance(fkeyname[1], str)) \
            ):
                raise exception.BadData('Foreign key name %r in ACL binding %s not valid.' % (fkeyname, self.binding_name))
            fkeyname = tuple(fkeyname)

            def find_fkeyref(sources, fkeyname):
                for source in sources.values():
                    for fkeyrefset in source.table_references.values():
                        for constr in fkeyrefset:
                            if constr.constraint_name == fkeyname:
                                return constr
                raise exception.ConflictModel('No foreign key %r found connected to table %s in ACL binding %s' % (
                    fkeyname, ltable, self.binding_name
                ))

            if elem.get('inbound') is not None:
                fkeyref = find_fkeyref(ltable.uniques, fkeyname)
                refop = '@='
            else:
                fkeyref = find_fkeyref(ltable.fkeys, fkeyname)
                refop = '=@'
            epath.add_link(fkeyref, refop, ralias=ralias, enforce_client=False)

        def compile_filter(elem):
            if 'and' in elem:
                filt = predicate.Conjunction([ compile_filter(e) for e in elem['and'] ])
            elif 'or' in elem:
                filt = predicate.Disjunction([ compile_filter(e) for e in elem['or'] ])
            elif 'filter' in elem:
                lname = elem['filter']
                if isinstance(lname, str):
                    # expand syntactic sugar for bare column name filter
                    lname = [ lname ]
                if type(lname) is list and lname[0] is None:
                    lname = lname[1:]
                if (type(lname) is not list \
                    or len(lname) < 1 \
                    or (not isinstance(lname[0], str)) \
                    or len(lname) >= 2 and (not isinstance(lname[1], str)) \
                    or len(lname) > 2
                ):
                    raise exception.BadData('Invalid filter column name %r in ACL binding %s.' % (lname, self.binding_name))
                lname = Name(lname)
                operator = elem.get('operator', '=')
                try:
                    klass = predicate.predicatecls(operator)
                except KeyError:
                    raise exception.BadData('Unknown operator %r in ACL binding %s.' % (operator, self.binding_name))
                if operator == 'null':
                    filt = klass(lname)
                else:
                    operand = predicate.Value(elem.get('operand', ''))
                    filt = klass(lname, operand)
            else:
                raise exception.BadData('Filter element %r of ACL binding %s is malformed.' % (elem, self.binding_name))
            if elem.get('negate', False):
                filt = predicate.Negation(filt)
            return filt

        # extend path with each element left to right
        for elem in proj[0:-1]:
            if type(elem) is not dict:
                raise exception.BadData('Projection element %s of ACL binding %s must be an object.' % (elem, self.binding_name))
            if 'inbound' in elem or 'outbound' in elem:
                compile_join(elem)
            else:
                filt = compile_filter(elem)
                epath.add_filter(filt, enforce_client=False)

        # apply final projection
        if not isinstance(proj[-1], str):
            raise exception.BadData('Projection for ACL binding %s must conclude with a string literal column name.' % self.binding_name)

        col = epath.current_entity_table().columns[proj[-1]]
        aclpath = ermpath.AttributePath(epath, [ (Name([proj[-1]]), col, epath) ])
        ctype = col.type
        while ctype.is_array or ctype.is_domain:
            ctype = ctype.base_type

        if self.get('projection_type') == 'acl' and ctype.name != 'text':
            raise exception.ConflictModel('ACL binding projection type %r not allowed for column %s in ACL binding %s.' % (
                self['projection_type'], col, self.binding_name
            ))

        return (aclpath, col, ctype)
        
annotatable_classes = []

def keying(restype, keying):
    """Decorator to configure resource type and keying for model classes.

       restype: the string name for the resource type, used to name auxilliary storage

       keying: dictionary of column names mapped to (psql_type, function) pairs
         which define the Postgres storage type and compute 
         literals for those columns to key the individual annotations.

    """
    def helper(orig_class):
        setattr(orig_class, '_model_restype', restype)
        setattr(orig_class, '_model_keying', keying)
        return orig_class
    return helper

def cache_rights(orig_method):
    def helper(self, aclname, roles=None, anon_mutation_ok=False):
        key = (self, orig_method, aclname, frozenset(roles) if roles is not None else None, anon_mutation_ok)
        if key in deriva_ctx.ermrest_model_rights_cache:
            result = deriva_ctx.ermrest_model_rights_cache[key]
        else:
            result = orig_method(self, aclname, roles)
            deriva_ctx.ermrest_model_rights_cache[key] = result
        return result
    return helper

def annotatable(orig_class):
    """Decorator to add annotation storage access interface to model classes.

       The keying() decorator MUST be applied before this one.
    """
    def _interp_annotation(self, key, newval=None):
        keying = {
            k: sql_literal(v[1](self))
            for k, v in orig_class._model_keying.items()
        }
        if key is not None:
            keying['annotation_uri'] = sql_literal(key)
        keycols = keying.keys()
        return {
            'restype': orig_class._model_restype,
            'cols': ','.join(keycols),
            'vals': ','.join([ keying[k] for k in keycols ]),
            'newval': sql_literal(json.dumps(newval)),
            'where': ' AND '.join(['True'] + [ "%s = %s" % (k, v) for k, v in keying.items() ]),
        }

    def set_annotations(self, conn, cur, doc):
        """Replace full annotations doc on %s, returning None."""
        if not isinstance(doc, dict):
            raise exception.BadData(u'Annotation set %s must be a dictionary.' % json.dumps(doc))
        doc = dict(doc)
        self.enforce_right('owner')
        self.annotations.update(doc)
        keying = [
            (k, '%s::%s' % (sql_literal(v[1](self)), v[0]))
            for k, v in self._model_keying.items()
        ]
        cur.execute("""
SELECT _ermrest.model_version_bump();
DELETE FROM _ermrest.known_%(restype)s_annotations
WHERE %(subj_keytests)s NOT %(doc)s::jsonb ? annotation_uri;
INSERT INTO _ermrest.known_%(restype)s_annotations
  (%(subj_keycols)s annotation_uri, annotation_value)
SELECT
  %(subj_keyvals)s k, v
FROM jsonb_each(%(doc)s::jsonb) doc(k, v)
EXCEPT
SELECT
  %(subj_keyvals)s annotation_uri, annotation_value
FROM _ermrest.known_%(restype)s_annotations
WHERE %(subj_keytests)s True
ON CONFLICT (%(subj_keycols)s annotation_uri)
DO UPDATE SET annotation_value = EXCLUDED.annotation_value;
""" % {
    'restype': self._model_restype,
    'subj_keycols': ', '.join([ k for k, v in keying ]) + (', ' if keying else ''),
    'subj_keyvals': ', '.join([ v for k, v in keying ]) + (', ' if keying else ''),
    'subj_keytests': ' AND '.join([ '%s = %s' % (k, v) for k, v in keying ]) + (' AND ' if keying else ''),
    'doc': sql_literal(json.dumps(doc)),
})
        self.annotations.clear()
        self.annotations.update(doc)

    def set_annotation(self, conn, cur, key, value):
        """Set annotation on %s, returning previous value for updates or None.""" % orig_class._model_restype
        assert key is not None
        self.enforce_right('owner')
        interp = self._interp_annotation(key, value)
        oldvalue = self.annotations.get(key)
        self.annotations[key] = value
        cur.execute("""
SELECT _ermrest.model_version_bump();
INSERT INTO _ermrest.known_%(restype)s_annotations (%(cols)s, annotation_value) VALUES (%(vals)s, %(newval)s)
ON CONFLICT (%(cols)s) DO UPDATE SET annotation_value = %(newval)s;
""" % interp)
        return oldvalue

    def delete_annotation(self, conn, cur, key):
        """Delete annotation on %s.""" % orig_class._model_restype
        self.enforce_right('owner')
        self.annotations.clear()
        interp = self._interp_annotation(key)
        cur.execute("""
SELECT _ermrest.model_version_bump();
DELETE FROM _ermrest.known_%(restype)s_annotations WHERE %(where)s;
""" % interp)

    setattr(orig_class, '_interp_annotation', _interp_annotation)
    setattr(orig_class, 'set_annotation', set_annotation)
    setattr(orig_class, 'set_annotations', set_annotations)
    setattr(orig_class, 'delete_annotation', delete_annotation)
    annotatable_classes.append(orig_class)
    return orig_class

hasacls_classes = []

def hasacls(acls_supported, rights_supported, getparent):
    """Decorator to add ACL storage access interface to model classes.

       acls_supported: { aclname, ... }

       rights_supported: { aclname, ... }

       getparent: getparent_func

       The keying() decorator MUST be applied first.
    """
    def _interp_acl(self, aclname, newval=None):
        keying = {
            k: sql_literal(v[1](self))
            for k, v in self._model_keying.items()
        }
        if aclname is not None:
            assert newval is not None
            keying['acl'] = sql_literal(aclname)
        keycols = keying.keys()
        return {
            'restype': self._model_restype,
            'cols': ','.join(keycols),
            'vals': ','.join([ keying[k] for k in keycols ]),
            'newval': '%s::text[]' % sql_literal(newval) if newval is not None else None,
            'where': ' AND '.join(['True'] + [ "%s = %s" % (k, v) for k, v in keying.items() ]),
        }

    def set_acls(self, cur, doc, anon_mutation_ok=False):
        """Replace full acls doc, returning None."""
        if not isinstance(doc, dict):
            raise exception.BadData(u'ACL set input %s must be a dictionary.' % json.dumps(doc))
        doc = dict(doc)
        for aclname in doc.keys():
            if aclname not in self._acls_supported:
                raise exception.ConflictData('ACL name %s not supported on %s.' % (aclname, self))
        self.delete_acl(cur, None, purging=True) # enforces owner rights for us...
        self.acls.update(doc)
        self.enforce_right('owner') # integrity check using Python data...
        for aclname, members in self.acls.items():
            if aclname not in {'enumerate', 'select'} \
               and members is not None and '*' in members \
               and not anon_mutation_ok:
                raise exception.BadData('ACL name %s does not support wildcard member.' % aclname)
        interp = self._interp_acl(None)
        if doc:
            if interp['cols']:
                interp['cols'] = interp['cols'] + ','
                interp['vals'] = interp['vals'] + ','
            # build rows for each field in doc
            interp['vals'] = ', '.join([
                '(%s %s, %s::text[])' % (interp['vals'], sql_literal(key), sql_literal(value))
                for key, value in doc.items()
                if value is not None
            ])
            cur.execute("""
SELECT _ermrest.model_version_bump();
INSERT INTO _ermrest.known_%(restype)s_acls (%(cols)s acl, members) VALUES %(vals)s;
""" % interp)

    def set_acl(self, cur, aclname, members, anon_mutation_ok=False):
        """Set annotation on %s, returning previous value for updates or None.""" % self._model_restype
        assert aclname is not None

        if members is None:
            if self.acls.can_remove:
                return self.delete_acl(cur, aclname)
            else:
                members = []

        self.enforce_right('owner') # pre-flight authz
        if aclname not in self._acls_supported:
            raise exception.ConflictData('ACL name %s not supported on %s.' % (aclname, self))

        if aclname not in {'enumerate', 'select'} and '*' in members and not anon_mutation_ok:
            raise exception.BadData('ACL name %s does not support wildcard member.' % aclname)

        oldvalue = self.acls.get(aclname)

        self.acls[aclname] = members
        self.enforce_right('owner') # integrity check using Python data...

        interp = self._interp_acl(aclname, members)
        cur.execute("""
SELECT _ermrest.model_version_bump();
INSERT INTO _ermrest.known_%(restype)s_acls (%(cols)s, members) VALUES (%(vals)s, %(newval)s)
ON CONFLICT (%(cols)s) DO UPDATE SET members = %(newval)s;
""" % interp)
        return oldvalue

    def delete_acl(self, cur, aclname, purging=False):
        interp = self._interp_acl(aclname)

        self.enforce_right('owner') # pre-flight authz
        if aclname is not None and aclname not in self._acls_supported:
            raise exception.NotFound('ACL %s on %s' % (aclname, self))

        if self.acls.can_remove:
            if aclname is None:
                self.acls.clear()
            elif aclname in self.acls:
                del self.acls[aclname]

            if not purging:
                self.enforce_right('owner') # integrity check... can't disown except when purging
            # not conditional on purging
            cur.execute("""
SELECT _ermrest.model_version_bump();
DELETE FROM _ermrest.known_%(restype)s_acls WHERE %(where)s;
""" % interp)
        else:
            if aclname is None:
                for aclname in self._acls_supported:
                    self.set_acl(cur, aclname, [])
            else:
                self.set_acl(cur, aclname, [])

    @cache_rights
    def has_right(self, aclname, roles=None, anon_mutation_ok=False):
        """Return access decision True, False, None.

           aclname: the symbolic name for the access mode

           roles: the client roles for whom to make a decision

        """
        if roles is None:
            roles = deriva_ctx.ermrest_client_roles

        if roles == {'*'} and aclname not in {'enumerate', 'select'} and not anon_mutation_ok:
            # anonymous clients cannot have mutation permissions
            return False

        if self.acls.intersects(aclname, roles):
            # have right explicitly due to ACL intersection
            # on named acl or another acl sufficient for named acl
            return True

        if getparent is not None:
            parentres = getparent(self)
        else:
            parentres = None

        if parentres is not None:
            if parentres.has_right('owner', roles):
                # have right implicitly due to parent resource ownership rule
                return True
            elif aclname not in self.acls and parentres.has_right(aclname, roles):
                # have right due to inherited parent ACL
                return True

        if hasattr(self, 'dynacls'):
            for binding in self.dynacls.values():
                if binding and binding.inscope(aclname, roles):
                    return None

            if parentres is not None and hasattr(parentres, 'dynacls'):
                # only check for non-overridden parent bindings that are in scope...
                for binding_name, binding in parentres.dynacls.items():
                    if binding_name not in self.dynacls and binding and binding.inscope(aclname, roles):
                        return None

        elif parentres is not None and parentres.has_right(aclname, roles) is None:
            return None

        # finally, static deny decision
        return False

    def enforce_right(self, aclname, require_true=False):
        """Policy enforcement for named right."""
        decision = self.has_right(aclname)
        if decision is False or require_true and not decision:
            # None means static right is absent but dynamic rights are possible...
            raise exception.Forbidden('%s access on %s' % (aclname, self))

    def rights(self):
        return {
            aclname: self.has_right(aclname) if aclname == 'select' or deriva_ctx.ermrest_history_snaptime is None else False
            for aclname in self._acls_rights
        }

    def helper(orig_class):
        setattr(orig_class, '_acl_getparent', lambda self: getparent(self))
        setattr(orig_class, '_acls_supported', set(acls_supported))
        setattr(orig_class, '_acls_rights', set(rights_supported))
        setattr(orig_class, '_interp_acl', _interp_acl)
        if not hasattr(orig_class, 'rights'):
            setattr(orig_class, 'rights', rights)
        else:
            setattr(orig_class, '_rights', rights)
        if not hasattr(orig_class, 'has_right'):
            setattr(orig_class, 'has_right', has_right)
        else:
            setattr(orig_class, '_has_right', has_right)
        if not hasattr(orig_class, 'enforce_right'):
            setattr(orig_class, 'enforce_right', enforce_right)
        else:
            setattr(orig_class, '_enforce_right', enforce_right)
        setattr(orig_class, 'set_acls', set_acls)
        setattr(orig_class, 'set_acl', set_acl)
        setattr(orig_class, 'delete_acl', delete_acl)
        hasacls_classes.append(orig_class)
        return orig_class

    return helper

hasdynacls_classes = []

def hasdynacls(dynacl_types_supported):
    """Decorator to add dynamic ACL storage access to model classes.

       The keying() decorator MUST be applied first.
    """
    def _interp_dynacl(self, name, newval=None):
        keying = {
            k: sql_literal(v[1](self))
            for k, v in self._model_keying.items()
        }
        if name is not None:
            keying['binding_name'] = sql_literal(name)
        keycols = keying.keys()
        return {
            'restype': self._model_restype,
            'cols': ','.join(keycols),
            'vals': ','.join([ keying[k] for k in keycols ]),
            'newval': sql_literal(json.dumps(newval)),
            'where': ' AND '.join([ "%s = %s" % (k, v) for k, v in keying.items() ]),
        }

    def set_dynacls(self, cur, doc):
        """Replace full dynacls doc, returning None."""
        if not isinstance(doc, dict):
            raise exception.BadData(u'ACL bindings set input %s must be a dictionary.' % json.dumps(doc))
        doc = dict(doc)
        self.delete_dynacl(cur, None) # enforces owner rights for us...
        self.dynacls.update(doc)
        interp = self._interp_dynacl(None)
        if doc:
            if interp['cols']:
                interp['cols'] = interp['cols'] + ','
                interp['vals'] = interp['vals'] + ','
            # build rows for each field in doc
            interp['vals'] = ', '.join([
                '(%s %s, %s::jsonb)' % (interp['vals'], sql_literal(key), sql_literal(json.dumps(value)))
                for key, value in doc.items()
                if value is not None
            ])
            cur.execute("""
SELECT _ermrest.model_version_bump();
INSERT INTO _ermrest.known_%(restype)s_dynacls (%(cols)s binding_name, binding) VALUES %(vals)s;
""" % interp)

    def set_dynacl(self, cur, name, binding):
        assert name is not None

        if binding is None:
            return self.delete_dynacl(cur, name)

        self.enforce_right('owner') # pre-flight authz

        oldvalue = self.dynacls.get(name)
        if binding is False:
            self.dynacls[name] = False
        else:
            self.dynacls[name] = AclBinding(deriva_ctx.ermrest_catalog_model, self, name, binding)

        interp = self._interp_dynacl(name, binding)
        cur.execute("""
SELECT _ermrest.model_version_bump();
INSERT INTO _ermrest.known_%(restype)s_dynacls (%(cols)s, binding) VALUES (%(vals)s, %(newval)s::jsonb)
ON CONFLICT (%(cols)s) DO UPDATE SET binding = %(newval)s::jsonb;
""" % interp
        )
        return oldvalue

    def delete_dynacl(self, cur, name):
        self.enforce_right('owner') # pre-flight authz

        interp = self._interp_dynacl(name)
        if name is None:
            self.dynacls.clear()
        elif name in self.dynacls:
            del self.dynacls[name]

        cur.execute("""
SELECT _ermrest.model_version_bump();
DELETE FROM _ermrest.known_%(restype)s_dynacls WHERE %(where)s;
""" % interp
        )

    def helper(orig_class):
        setattr(orig_class, '_interp_dynacl', _interp_dynacl)
        setattr(orig_class, 'set_dynacls', set_dynacls)
        setattr(orig_class, 'set_dynacl', set_dynacl)
        setattr(orig_class, 'delete_dynacl', delete_dynacl)
        setattr(orig_class, 'dynacl_types_supported', dynacl_types_supported)
        hasdynacls_classes.append(orig_class)
        return orig_class

    return helper

