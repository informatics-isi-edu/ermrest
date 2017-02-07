
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

"""ERMREST URL abstract syntax tree (AST) for data predicates.

"""

from ....exception import *
from .... import model

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

    def validate(self, epath, allow_star=False):
        self.left_col, self.left_elem = self.left_name.validate(epath)
        if not allow_star and self.left_col.is_star_column():
            raise BadSyntax('Operator %s does not support text-search psuedo-column "*".' % self.op)

    def validate_attribute_update(self, apath):
        raise BadSyntax('Predicate %s is not supported in an attribute update path filter.' % self)

class UnaryPredicate (Predicate):
    def __init__(self, left_name, right_expr=None):
        Predicate.__init__(self, left_name, self.restop)
        self.right_expr = right_expr

    def validate(self, epath):
        Predicate.validate(self, epath)
        if self.right_expr is not None:
            raise TypeError('Operator %s does not accept right-hand value' % self.op)

    def sql_where(self, epath, elem):
        return 't%d.%s %s' % (
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
    
    def validate(self, epath, allow_star=False):
        Predicate.validate(self, epath, allow_star=allow_star)
        if self.right_expr is None:
            raise TypeError('Operator %s requires right-hand value' % self.op)

    def sql_where(self, epath, elem):
        if self.left_col.type.is_array:
            return '(SELECT bool_or(v %s %s) FROM unnest(t%d.%s) x (v))' % (
                self.sqlop,
                self.right_expr.sql_literal(self.left_col.type.base_type),
                self.left_elem.pos,
                self.left_col.sql_name()
            )
        else:
            return 't%d.%s %s %s' % (
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
    
    def validate(self, epath):
        BinaryPredicate.validate(self, epath)
        self.right_expr.validate(epath, self.left_col)
        # TODO: test ordered op/column type compatibility

class BinaryTextPredicate (BinaryPredicate):
    
    _sql_left_type = 'text'

    def validate(self, epath, allow_star=True):
        BinaryPredicate.validate(self, epath, allow_star=allow_star)
        # TODO: test text op/column type type

    def _sql_left_value(self):
        """Generate SQL column value expression to allow overriding by subclasses."""
        if hasattr(self.left_col, 'sql_name_astext_with_talias'):
            name = self.left_col.sql_name_astext_with_talias('t%d' % self.left_elem.pos)
        else:
            name = "t%d.%s" % (
                self.left_elem.pos,
                self.left_col.sql_name()
                )
        return "%s::%s" % (name, self._sql_left_type)

    def _sql_right_value(self):
        return self.right_expr.sql_literal(model.text_type)

    def sql_where(self, epath, elem):
        return '%s %s %s' % (
            self._sql_left_value(),
            self.sqlop,
            self._sql_right_value()
            )


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

    def _sql_left_value(self):
        return 'to_tsvector(%s)' % BinaryTextPredicate._sql_left_value(self)

    def _sql_right_value(self):
        return 'to_tsquery(%s)' % BinaryTextPredicate._sql_right_value(self)

def predicatecls(op):
    """Return predicate class corresponding to raw REST operator syntax string."""
    return _ops[op]



class Negation (object):
    def __init__(self, predicate):
        self.predicate = predicate

    def validate(self, epath):
        return self.predicate.validate(epath)

    def sql_where(self, epath, elem):
        return 'NOT (%s)' % self.predicate.sql_where(epath, elem)


class Disjunction (list):
    def validate(self, epath):
        return [ f.validate(epath) for f in self ]

    def sql_where(self, epath, elem):
        preds_sql = [ "(%s)" % f.sql_where(epath, elem) for f in self ]
        return " OR ".join(preds_sql)

class Conjunction (list):
    def validate(self, epath):
        return [ f.validate(epath) for f in self ]

    def sql_where(self, epath, elem):
        preds_sql = [ "(%s)" % f.sql_where(epath, elem) for f in self ]
        return " AND ".join(preds_sql)


