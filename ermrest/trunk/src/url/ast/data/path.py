
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
import psycopg2
from ermrest import sanepg2
import web
import traceback
import sys
import re

class Api (object):
    is_filter = False

    def __init__(self, catalog):
        self.catalog = catalog
        self.queryopts = dict()
        self.sort = None
        self.http_vary = web.ctx.webauthn2_manager.get_http_vary()
        self.http_etag = None

    def enforce_owner(self, cur, uri=''):
        """Policy enforcement on is_owner.
        """
        if not self.catalog.manager.is_owner(
                        cur, web.ctx.webauthn2_context.client):
            raise rest.Forbidden(uri)

    def enforce_read(self, cur, uri=''):
        """Policy enforcement on has_read test.
        """
        if not (self.catalog.manager.has_read(
                        cur, web.ctx.webauthn2_context.attributes)
                or self.catalog.manager.is_owner(
                        cur, web.ctx.webauthn2_context.client) ):
            raise rest.Forbidden(uri)

    def enforce_write(self, cur, uri=''):
        """Policy enforcement on has_write test.
        """
        if not (self.catalog.manager.has_write(
                        cur, web.ctx.webauthn2_context.attributes)
                or self.catalog.manager.is_owner(
                        cur, web.ctx.webauthn2_context.client) ):
            raise rest.Forbidden(uri)

    def enforce_content_read(self, cur, uri=''):
        """Policy enforcement on has_content_read test.
        """
        if not (self.catalog.manager.has_content_read(
                        cur, web.ctx.webauthn2_context.attributes)
                or self.catalog.manager.is_owner(
                        cur, web.ctx.webauthn2_context.client) ):
            raise rest.Forbidden(uri)

    def enforce_content_write(self, cur, uri=''):
        """Policy enforcement on has_content_write test.
        """
        if not (self.catalog.manager.has_content_write(
                        cur, web.ctx.webauthn2_context.attributes)
                or self.catalog.manager.is_owner(
                        cur, web.ctx.webauthn2_context.client) ):
            raise rest.Forbidden(uri)

    def enforce_schema_write(self, cur, uri=''):
        """Policy enforcement on has_schema_write test.
        """
        if not (self.catalog.manager.has_schema_write(
                        cur, web.ctx.webauthn2_context.attributes)
                or self.catalog.manager.is_owner(
                        cur, web.ctx.webauthn2_context.client) ):
            raise rest.Forbidden(uri)

    def with_queryopts(self, qopt):
        self.queryopts = qopt
        return self

    def with_sort(self, sort):
        self.sort = sort
        return self

    def negotiated_limit(self):
        """Determine query result size limit to use."""
        if 'limit' in self.queryopts:
            limit = self.queryopts['limit']
            if str(limit).lower() == 'none':
                limit = None
            else:
                try:
                    limit = int(limit)
                except ValueError, e:
                    raise rest.BadRequest('The "limit" query-parameter requires an integer or the string "none".')
            return limit
        else:
            try:
                limit = web.ctx.ermrest_config.get('default_limit', 100)
                if str(limit).lower() == 'none' or limit is None:
                    limit = None
                else:
                    limit = int(limit)
            except:
                return 100
    
    def set_http_etag(self, version):
        """Set an ETag from version key.

        """
        etag = []

        # TODO: compute source_checksum to help with cache invalidation
        #etag.append( source_checksum )

        if 'cookie' in self.http_vary:
            etag.append( '%s' % web.ctx.webauthn2_context.client )
        else:
            etag.append( '*' )
            
        if 'accept' in self.http_vary:
            etag.append( '%s' % web.ctx.env.get('HTTP_ACCEPT', '') )
        else:
            etag.append( '*' )

        etag.append( '%s' % version )

        self.http_etag = '"%s"' % ';'.join(etag).replace('"', '\\"')

    def http_is_cached(self):
        """Determine whether a request is cached and the request can return 304 Not Modified.
           Currently only considers ETags via HTTP "If-None-Match" header, if caller set self.http_etag.
        """
        def etag_parse(s):
            strong = True
            if s[0:2] == 'W/':
                strong = False
                s = s[2:]
            return (s, strong)

        def etags_parse(s):
            etags = []
            s, strong = etag_parse(s)
            while s:
                s = s.strip()
                m = re.match('^,? *(?P<first>(W/)?"(.|\\")*")(?P<rest>.*)', s)
                if m:
                    g = m.groupdict()
                    etags.append(etag_parse(g['first']))
                    s = g['rest']
                else:
                    s = None
            return dict(etags)
        
        client_etags = etags_parse( web.ctx.env.get('HTTP_IF_NONE_MATCH', ''))
        #web.debug(client_etags)
        
        if self.http_etag is not None and client_etags.has_key('%s' % self.http_etag):
            return True

        return False

    def emit_headers(self):
        """Emit any automatic headers prior to body beginning."""
        #TODO: evaluate whether this function is necessary
        if self.http_vary:
            web.header('Vary', ', '.join(self.http_vary))
        if self.http_etag:
            web.header('ETag', '%s' % self.http_etag)
        
    def perform(self, body, finish):
        def wrapbody(conn, cur):
            # TODO: implement backoff/retry on transient exceptions?
            try:
                return body(conn, cur)
            except psycopg2.InterfaceError, e:
                raise rest.ServiceUnavailable("Please try again.")
            except NotFound, e:
                raise rest.NotFound(e.message)
            except BadData, e:
                raise rest.BadRequest(e.message)
            except ConflictData, e:
                et, ev, tb = sys.exc_info()
                web.debug('got exception "%s" during Api.perform()' % str(ev),
                      traceback.format_exception(et, ev, tb))
                raise rest.Conflict(e.message)
            except UnsupportedMediaType, e:
                raise rest.UnsupportedMediaType

        return sanepg2.pooled_perform(self.catalog.manager._dbname, wrapbody, finish)
    
    def final(self):
        pass

class Path (list):
    pass

class TableElem (Api):
    """A path element with a single name must be a table."""
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

class ColumnsElem (Api):
    """A path element with parenthetic name list must be columns."""
    def __init__(self, names):
        self.names = names
        self.alias = None

    def set_alias(self, alias):
        self.alias = alias

    def resolve_link(self, model, epath):
        """Resolve self.name as a link in the model and epath context."""
        return self.names.resolve_link(model, epath)


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

    def validate_attribute_update(self, apath):
        return self.pred.validate_attribute_update(apath)

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
    
    def validate(self, epath, allow_star=False):
        BinaryPredicate.validate(self, epath, allow_star=allow_star)
        # TODO: test text op/column type type

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
class TextsearchPredicate (BinaryPredicate):
    sqlop = '@@'

    def validate(self, epath):
        BinaryPredicate.validate(self, epath, allow_star=True)
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


