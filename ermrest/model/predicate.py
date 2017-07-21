
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

"""ERMREST URL abstract syntax tree (AST) for data predicates.

"""

from ..util import sql_literal
from ..exception import *
from .type import text_type

import web

class Value (object):
    """Represent a literal value in an ERMREST URL.

    """
    def __init__(self, s):
        self._str = s

    def __str__(self):
        return self._str

    def validate(self, epath, etype, enforce_client=True):
        """Validate value in typed context.

           TODO: refactor a type object instead of using Column for etype
        """
        pass

    def is_null(self):
        return self._str is None

    def sql_literal(self, etype):
        return etype.sql_literal(etype.url_parse(self._str))

    def validate_attribute_update(self):
        raise BadSyntax('Value %s is not supported in an attribute update path filter.' % self)

class AclBasePredicate (object):
    def validate(self, epath, allow_star=False, enforce_client=True):
        pass

    def sql_where(self, epath, elem, prefix=None):
        assert prefix
        key = None
        for unique in elem.table.uniques.values():
            nullok = False
            for col in unique.columns:
                if col.nullok:
                    nullok = True
                    break
            if nullok:
                continue
            else:
                key = unique
                break
        assert key
        clauses = [
            '%s.%s = %st0.%s' % (
                prefix,
                col.sql_name(),
                prefix,
                col.sql_name()
            )
            for col in key.columns
        ]
        return ' AND '.join(['(%s)' % clause for clause in clauses ])

class AclPredicate (object):
    def __init__(self, binding, column):
        self.binding = binding
        self.left_col = column
        self.left_elem = None

    def validate(self, epath, allow_star=False, enforce_client=True):
        self.left_elem = epath._path[epath.current_entity_position()]

    def sql_where(self, epath, elem, prefix=''):
        lname = '%st%d.%s' % (prefix, self.left_elem.pos, self.left_col.sql_name())
        if self.binding['projection_type'] == 'acl':
            attrs = 'ARRAY[%s]::text[]' % ','.join([ sql_literal(a['id']) for a in web.ctx.webauthn2_context.attributes ] + [sql_literal('*')])
            if self.left_col.type.is_array:
                return '%s && %s' % (lname, attrs)
            else:
                return '%s = ANY (%s)' % (lname, attrs)
        else:
            return '%s IS NOT NULL' % (lname,)

class Predicate (object):

    def __init__(self, left_name, op):
        self.left_name = left_name
        self.left_col = None
        self.left_elem = None
        self.op = op

    def __str__(self):
        return '%s %s' % (
            str(self.left_name),
            str(self.op)
            )

    def validate(self, epath, allow_star=False, enforce_client=True):
        self.left_col, self.left_elem = self.left_name.validate(epath)
        if enforce_client:
            self.left_col.enforce_right('select')
        if not allow_star and self.left_col.is_star_column():
            raise BadSyntax('Operator %s does not support text-search psuedo-column "*".' % self.op)

    def validate_attribute_update(self, apath):
        raise BadSyntax('Predicate %s is not supported in an attribute update path filter.' % self)

class UnaryPredicate (Predicate):
    def __init__(self, left_name, right_expr=None):
        Predicate.__init__(self, left_name, self.restop)
        self.right_expr = right_expr

    def validate(self, epath, enforce_client=True):
        Predicate.validate(self, epath, enforce_client=enforce_client)
        if self.right_expr is not None:
            raise TypeError('Operator %s does not accept right-hand value' % self.op)

    def sql_where(self, epath, elem, prefix=''):
        return '%st%d.%s %s' % (
            prefix,
            self.left_elem.pos,
            self.left_col.sql_name(),
            self.sqlop
            )

class BinaryPredicate (Predicate):

    def __init__(self, left_name, right_expr):
        Predicate.__init__(self, left_name, self.restop)
        self.right_expr = right_expr

    def __str__(self):
        return  '%s %s' % (
            Predicate.__str__(self),
            str(self.right_expr)
            )
    
    def validate(self, epath, allow_star=False, enforce_client=True):
        Predicate.validate(self, epath, allow_star=allow_star, enforce_client=enforce_client)
        if self.right_expr is None:
            raise TypeError('Operator %s requires right-hand value' % self.op)

    def sql_where(self, epath, elem, prefix=''):
        if self.left_col.type.is_array:
            return '(SELECT bool_or(v %s %s) FROM unnest(%st%d.%s) x (v))' % (
                self.sqlop,
                self.right_expr.sql_literal(self.left_col.type.base_type),
                prefix,
                self.left_elem.pos,
                self.left_col.sql_name()
            )
        else:
            return '%st%d.%s %s %s' % (
                prefix,
                self.left_elem.pos,
                self.left_col.sql_name(),
                self.sqlop,
                self.right_expr.sql_literal(self.left_col.type)
            )

def op(rest_syntax):
    def helper(original_class):
        original_class.restop = rest_syntax
        _ops[rest_syntax] = original_class
        return original_class
    return helper

class BinaryOrderedPredicate (BinaryPredicate):
    
    def validate(self, epath, enforce_client=True):
        BinaryPredicate.validate(self, epath, enforce_client=enforce_client)
        self.right_expr.validate(epath, self.left_col)
        # TODO: test ordered op/column type compatibility

class BinaryTextPredicate (BinaryPredicate):
    
    _sql_left_type = 'text'

    def validate(self, epath, allow_star=True, enforce_client=True):
        BinaryPredicate.validate(self, epath, allow_star=allow_star, enforce_client=enforce_client)
        # TODO: test text op/column type type

    def _sql_left_value(self, prefix=''):
        """Generate SQL column value expression to allow overriding by subclasses."""
        if hasattr(self.left_col, 'sql_name_astext_with_talias'):
            return self.left_col.sql_name_astext_with_talias('%st%d' % (prefix, self.left_elem.pos))
        else:
            return "%st%d.%s::%s" % (
                prefix,
                self.left_elem.pos,
                self.left_col.sql_name(),
                self._sql_left_type
            )

    def _sql_right_value(self):
        return self.right_expr.sql_literal(text_type)

    def sql_where(self, epath, elem, prefix=''):
        def where_one(left):
            return '(%s %s %s)' % (
                left,
                self.sqlop,
                self._sql_right_value()
            )
            
        left = self._sql_left_value(prefix=prefix)
        if type(left) is set:
            return '(%s)' % ' OR '.join(map(where_one, left))
        else:
            return where_one(left)

_ops = dict()

@op('null')
class NullPredicate (UnaryPredicate):
    sqlop = 'IS NULL'

@op('=')
class EqualPredicate (BinaryPredicate):
    sqlop = '='

    def validate_attribute_update(self, apath):
        tcol, base = self.left_name.resolve_column(apath.epath._model, apath.epath)
        if base == apath.epath:
            # column in final entity path element
            pass
        elif base in apath.epath.aliases:
            raise ConflictModel('Only unqualified attribute names from entity %s can be constrained in PUT.' % apath.epath.current_entity_table().name)
        else:
            raise ConflictModel('Invalid attribute name "%s".' % attribute)
        
        icolname = self.right_expr.validate_attribute_update()
        return tcol, icolname

@op('geq')
class GreaterEqualPredicate (BinaryOrderedPredicate):
    sqlop = '>='

@op('gt')
class GreaterThanPredicate (BinaryOrderedPredicate):
    sqlop = '>'

@op('leq')
class LessEqualPredicate (BinaryOrderedPredicate):
    sqlop = '<='

@op('lt')
class LessThanPredicate (BinaryOrderedPredicate):
    sqlop = '<'

@op('regexp')
class RegexpPredicate (BinaryTextPredicate):
    sqlop = '~'

@op('ciregexp')
class RegexpPredicate (BinaryTextPredicate):
    sqlop = '~*'

@op('ts')
class TextsearchPredicate (BinaryTextPredicate):
    sqlop = '@@'

    def _sql_left_value(self, prefix=''):
        def wrap(left):
            'to_tsvector(%s)' % left
        left = BinaryTextPredicate._sql_left_value(self, prefix=prefix)
        if type(left) is set:
            return set(map(wrap, left))
        else:
            return wrap(left)

    def _sql_right_value(self):
        return 'to_tsquery(%s)' % BinaryTextPredicate._sql_right_value(self)

def predicatecls(op):
    """Return predicate class corresponding to raw REST operator syntax string."""
    return _ops[op]



class Negation (object):
    def __init__(self, predicate):
        self.predicate = predicate

    def validate(self, epath, enforce_client=True):
        return self.predicate.validate(epath, enforce_client=enforce_client)

    def sql_where(self, epath, elem, prefix=''):
        return 'NOT (%s)' % self.predicate.sql_where(epath, elem, prefix=prefix)


class Disjunction (list):
    def validate(self, epath, enforce_client=True):
        return [ f.validate(epath, enforce_client=enforce_client) for f in self ]

    def sql_where(self, epath, elem, prefix=''):
        preds_sql = [ "(%s)" % f.sql_where(epath, elem, prefix=prefix) for f in self ]
        return " OR ".join(preds_sql)

class Conjunction (list):
    def validate(self, epath, enforce_client=True):
        return [ f.validate(epath, enforce_client=enforce_client) for f in self ]

    def sql_where(self, epath, elem, prefix=''):
        preds_sql = [ "(%s)" % f.sql_where(epath, elem, prefix=prefix) for f in self ]
        return " AND ".join(preds_sql)


