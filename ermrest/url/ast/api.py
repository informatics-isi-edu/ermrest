
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

"""ERMREST URL abstract syntax tree (AST) for data resource path-addressing.

"""
import psycopg2
import web
import traceback
import sys
import re

from ...exception import *
from ... import sanepg2

class Api (object):

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
            try:
                return body(conn, cur)
            except psycopg2.InterfaceError, e:
                raise rest.ServiceUnavailable("Please try again.")
            
        return web.ctx.ermrest_catalog_pc.perform(wrapbody, finish)
    
    def final(self):
        if self.catalog is not self:
            self.catalog.final()

