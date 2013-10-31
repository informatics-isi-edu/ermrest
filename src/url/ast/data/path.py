
# 
# Copyright 2013 University of Southern California
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

"""ERMREST URL abstract syntax tree (AST) for data resource path-addressing.

"""
from ermrest.exception import *
from ermrest import model

class Api (object):
    is_filter = False

    def __init__(self, catalog):
        self.catalog = catalog

    def with_queryopts(self, qopt):
        self.queryopts = qopt
        return self

    def get_conn(self):
        return self.catalog.get_conn()

    def perform(self, body, finish):
        # TODO: implement backoff/retry on transient exceptions?
        conn = self.get_conn()
        try:
            result = body(conn)
            conn.commit()
        except NotFound, e:
            raise rest.NotFound(e.message)
        except BadData, e:
            raise rest.BadRequest(e.message)
        except ConflictData, e:
            raise rest.Conflict(e.message)
        except UnsupportedMediaType, e:
            raise rest.UnsupportedMediaType
        except:
            conn.rollback()
            raise
        return finish(result)
    

class Path (list):
    pass

class SingleElem (Api):
    """A path element with a single name may be a table or column."""
    def __init__(self, name):
        self.name = name
        self.alias = None

    def set_alias(self, alias):
        self.alias = alias

    def resolve_table(self, model):
        """Resolve self.name as a table in the model."""
        return self.name.resolve_table(model)

    def resolve_link(self, model, epath):
        """Resolve self.name as a link in the model and epath context."""
        return self.name.resolve_link(model, epath)

class MultiElem (Api):
    """A path element with multiple names must be columns."""
    def __init__(self, names):
        self.names = names
        self.alias = None

    def set_alias(self, alias):
        self.alias = alias

    def resolve_link(self, model, epath):
        """Resolve self.name as a link in the model and epath context."""
        return self.names.resolve_link(model, epath)

class ReferenceLeft (Api):
    """A path element referencing left-hand columns."""
    def __init__(self, alias, cols):
        self.alias = alias
        self.cols = cols

class ReferenceRight (Api):
    """A path element referencing right-hand columns."""
    def __init__(self, table, cols):
        self.table = table
        self.cols = cols
        

class ReferenceElem (Api):
    """A path element with directional reference addressing syntax."""
    def __init__(self, left=None, direction=None, right=None):
        self.left = left
        self.direction = direction
        self.right = right
    

class FilterElem (Api):
    """A path element that applies a filter."""
    is_filter = True

    def __init__(self, pred):
        self.pred = pred

    def __str__(self):
        return str(self.pred)

    def validate(self, epath):
        return self.pred.validate(epath)

    def sql_where(self, epath, elem):
        return self.pred.sql_where(epath, elem)


class Predicate (Api):

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

    def validate(self, epath):
        self.left_col, self.left_elem = self.left_name.validate(epath)

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
    
    def validate(self, epath):
        Predicate.validate(self, epath)
        if self.right_expr is None:
            raise TypeError('Operator %s requires right-hand value' % self.op)

    def sql_where(self, epath, elem):
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
    
    def validate(self, epath):
        BinaryPredicate.validate(self, epath)
        # TODO: test text op/column type type

_ops = dict()

@op('null')
class NullPredicate (UnaryPredicate):
    sqlop = 'IS NULL'

@op('=')
class EqualPredicate (BinaryPredicate):
    sqlop = '='

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
class TextsearchPredicate (BinaryPredicate):
    sqlop = '@@'

    def validate(self, epath):
        BinaryPredicate.validate(self, epath)
        # TODO: test right-hand expression as tsquery?

    def sql_where(self, epath, elem):
        # NOTE, build a value index like this to accelerate these operations:

        #   CREATE INDEX ON table USING gin ( (to_tsvector('english', colname)) );
        
        #   CREATE INDEX ON table USING gin ( (to_tsvector('english', colname1 || colname2 || ... || colnameN)) );
        #   sort colnames lexicographically

        if str(self.left_col.type) == 'text':
            return "to_tsvector('english', t%d.%s) @@ to_tsquery('english', %s)" % (
                self.left_elem.pos,
                self.left_col.sql_name(),
                self.right_expr.sql_literal(self.left_col.type)
                )
        elif str(self.left_col.type) == 'tsvector':
            if hasattr(self.left_col, 'sql_name_with_talias'):
                return "%s @@ to_tsquery('english'::regconfig, %s)" % (
                    self.left_col.sql_name_with_talias('t%d' % self.left_elem.pos),
                    self.right_expr.sql_literal(model.Type('text'))
                    )
            else:
                return "t%d.%s @@ to_tsquery('english'::regconfig, %s)" % (
                    self.left_elem.pos,
                    self.left_col.sql_name(),
                    self.right_expr.sql_literal(self.left_col.type)
                    )
        else:
            raise NotImplementedError('text search on left column type %s' % self.left_col.type)

def predicatecls(op):
    """Return predicate class corresponding to raw REST operator syntax string."""
    return _ops[op]



class Negation (Api):
    def __init__(self, predicate):
        self.predicate = predicate

class Conjunction (list):
    pass

class Disjunction (list):
    pass


