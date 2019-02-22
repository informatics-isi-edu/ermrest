
# 
# Copyright 2013-2019 University of Southern California
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
import web
import hashlib
import base64

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
    if web.ctx and 'ermrest_config' in web.ctx:
        return web.ctx['ermrest_config']
    else:
        return _default_config

def enforce_63byte_id(s, prefix="Identifier"):
    if isinstance(s, Name):
        s = s.one_str()
    if not isinstance(s, str):
        raise exception.BadData(u'%s "%s" "%s" is unsupported and should be unicode string.' % (prefix, s, type(s)))
    if len(s.encode('utf8')) > 63:
        raise exception.BadData(u'%s "%s" exceeded 63-byte limit when encoded as UTF-8.' % (prefix, s))

def truncated_identifier(parts, threshold=4):
    """Build a 63 byte (or less) postgres identifier out of sequentially concatenated parts.
    """
    len_static = len((''.join([ p for p in parts if len(p.encode()) <= threshold ]).encode()))
    if len_static >= 26:
        raise NotImplementedError('truncated_identifier static parts exceed length limit %s' % parts)
    num_components = len([ p for p in parts if len(p.encode()) > threshold ])
    max_component_len = (63 - len_static) // (num_components or 1)

    def convert(p):
        if len(p.encode()) <= max_component_len:
            return p
        # return a truncated hash using base64 chars
        h = hashlib.md5()
        h.update(p.encode())
        return base64.b64encode(h.digest()).decode()[0:max_component_len]

    result = ''.join([ convert(p) for p in parts ])
    assert len(result) <= 63
    return result

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
        web.ctx.ermrest_model_rights_cache.clear()
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
        web.ctx.ermrest_model_rights_cache.clear()
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
        self.binding_doc = doc

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
            roles = web.ctx.ermrest_client_roles
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
hasacls_classes = []
hasdynacls_classes = []

def cache_rights(orig_method):
    def helper(self, aclname, roles=None):
        key = (self, orig_method, aclname, frozenset(roles) if roles is not None else None)
        if key in web.ctx.ermrest_model_rights_cache:
            result = web.ctx.ermrest_model_rights_cache[key]
        else:
            result = orig_method(self, aclname, roles)
            web.ctx.ermrest_model_rights_cache[key] = result
        return result
    return helper

class Annotatable (object):
    """Aspect class to add annotation storage access interface to model classes."""
    def __init__(self):
        super(Annotatable, self).__init__()
        self.annotations = AltDict(lambda k: self._annotation_key_error(k))

    def _annotation_key_error(self, key):
        return exception.NotFound(u'annotation "%s"' % (key,))

    def _interp_annotation(self, newval=None):
        return {
            'RID': sql_literal(self.rid),
            'restype': self._model_restype,
            'newval': sql_literal(json.dumps(newval)),
        }

    def set_annotations(self, conn, cur, doc):
        """Replace full annotations doc, returning None."""
        if not isinstance(doc, dict):
            raise exception.BadData(u'Annotation set %s must be a dictionary.' % json.dumps(doc))
        doc = dict(doc)
        self.enforce_right('owner')
        self.annotations.clear()
        self.annotations.update(doc)
        interp = self._interp_annotation(doc)
        cur.execute("""
SELECT _ermrest.model_version_bump();
UPDATE _ermrest.known_%(restype)ss
SET annotations = %(newval)s::jsonb
WHERE "RID" = %(RID)s;
""" % interp)

    def set_annotation(self, conn, cur, key, value):
        """Set annotation, returning previous value for updates or None."""
        assert key is not None
        doc = dict(self.annotations)
        oldvalue = self.annotations.get(key)
        doc[key] = value
        self.set_annotations(conn, cur, doc)
        return oldvalue

    def delete_annotation(self, conn, cur, key):
        """Delete annotation"""
        if key is None:
            doc = {}
        else:
            doc = dict(self.annotations)
            doc.pop(key, None)
        self.set_annotations(conn, cur, doc)

    @staticmethod
    def annotatable(klass):
        """Register annotatable classes."""
        annotatable_classes.append(klass)
        return klass

class HasAcls (object):
    """Aspect class to add ACL storage access interface to model classes."""
    _acls_can_remove = True
    _anon_mutation_ok = False

    def __init__(self):
        super(HasAcls, self).__init__()
        self.acls = AclDict(self, can_remove=self._acls_can_remove)

    def _interp_acl(self, newval=None):
        return {
            'RID': sql_literal(self.rid),
            'restype': self._model_restype,
            'newval': sql_literal(json.dumps(newval)),
        }

    def set_acls(self, cur, doc, purging=False):
        """Replace full acls doc, returning None."""
        if not isinstance(doc, dict):
            raise exception.BadData(u'ACL set input %s must be a dictionary.' % json.dumps(doc))
        doc = dict(doc)
        for aclname in doc.keys():
            if aclname not in self._acls_supported:
                raise exception.ConflictData('ACL name %s not supported on %s.' % (aclname, self))
        self.enforce_right('owner')
        self.acls.clear()
        self.acls.update(doc)
        if not purging:
            self.enforce_right('owner') # integrity check using Python data... unless we are purging
        for aclname, members in self.acls.items():
            if aclname not in {'enumerate', 'select'} \
               and members is not None and '*' in members \
               and not self._anon_mutation_ok:
                raise exception.BadData('ACL name %s does not support wildcard member.' % aclname)
        interp = self._interp_acl(self.acls)
        cur.execute("""
SELECT _ermrest.model_version_bump();
UPDATE _ermrest.known_%(restype)ss
SET acls = %(newval)s::jsonb
WHERE "RID" = %(RID)s;
""" % interp)

    def set_acl(self, cur, aclname, members, purging=False):
        """Set annotation on %s, returning previous value for updates or None.""" % self._model_restype
        assert aclname is not None

        oldvalue = self.acls.get(aclname)

        doc = dict(self.acls)
        if members is not None:
            doc[aclname] = members
        elif not self.acls.can_delete:
            doc[aclname] = []
        else:
            del doc[aclname]

        self.set_acls(cur, doc, purging=purging)
        return oldvalue

    def delete_acl(self, cur, aclname, purging=False):
        if aclname is None:
            if self.acls.can_remove:
                doc = {}
            else:
                doc = {
                    aclname: []
                    for aclname in self._acls_supported
                }
        else:
            if aclname not in self._acls_supported:
                raise exception.NotFound('ACL %s on %s' % (aclname, self))
            doc = dict(self.acls)
            if self.acls.can_remove:
                doc.pop(aclname, None)
            else:
                doc[aclname] = []

        self.set_acls(cur, doc, purging=purging)

    @cache_rights
    def has_right(self, aclname, roles=None):
        """Return access decision True, False, None.

           aclname: the symbolic name for the access mode

           roles: the client roles for whom to make a decision

        """
        if roles is None:
            roles = web.ctx.ermrest_client_roles

        if roles == {'*'} and aclname not in {'enumerate', 'select'} and not self._anon_mutation_ok:
            # anonymous clients cannot have mutation permissions
            return False

        if self.acls.intersects(aclname, roles):
            # have right explicitly due to ACL intersection
            # on named acl or another acl sufficient for named acl
            return True

        parentres = self._acls_getparent()

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
            aclname: self.has_right(aclname) if aclname == 'select' or web.ctx.ermrest_history_snaptime is None else False
            for aclname in self._acls_rights
        }

    @staticmethod
    def hasacls(klass):
        """Decorator to register hasacls classes."""
        hasacls_classes.append(klass)
        return klass

class HasDynacls (object):
    """Aspect class to add dynamic ACL storage access to mode classes."""
    def __init__(self):
        super(HasDynacls, self).__init__()
        self.dynacls = DynaclDict(self)

    def _interp_dynacl(self, newval=None):
        return {
            'RID': sql_literal(self.rid),
            'restype': self._model_restype,
            'newval': sql_literal(
                json.dumps(newval)
            ),
        }

    def set_dynacls(self, cur, doc):
        """Replace full dynacls doc, returning None."""
        if not isinstance(doc, dict):
            raise exception.BadData(u'ACL bindings set input %s must be a dictionary.' % json.dumps(doc))
        doc = dict(doc)
        self.enforce_right('owner')
        for binding_name in list(doc.keys()):
            binding = doc[binding_name]
            if not (binding is False or isinstance(binding, AclBinding)):
                # convert binding doc to binding instance to validate etc.
                doc[binding_name] = AclBinding(web.ctx.ermrest_catalog_model, self, binding_name, binding)
        self.dynacls.clear()
        self.dynacls.update(doc)
        interp = self._interp_dynacl(doc)
        cur.execute("""
SELECT _ermrest.model_version_bump();
UPDATE _ermrest.known_%(restype)ss v
SET acl_bindings = _ermrest.compile_acl_bindings(v, %(newval)s::jsonb)
WHERE v."RID" = %(RID)s;
""" % interp)

    def set_dynacl(self, cur, name, binding):
        assert name is not None

        if binding is None:
            return self.delete_dynacl(cur, name)

        self.enforce_right('owner') # pre-flight authz

        oldvalue = self.dynacls.get(name)
        self.dynacls[name] = binding
        self.set_dynacls(cur, self.dynacls)
        return oldvalue

    def delete_dynacl(self, cur, name):
        self.enforce_right('owner') # pre-flight authz

        if name is None:
            self.dynacls.clear()
        else:
            self.dynacls.pop(name, None)

        self.set_dynacls(cur, self.dynacls)

    @staticmethod
    def hasdynacls(klass):
        hasdynacls_classes.append(klass)
        return klass
