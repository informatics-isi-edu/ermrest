
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

"""ERMREST URL abstract syntax tree (AST) for data resource path-addressing.

"""
import psycopg2
import web
import traceback
import sys
import re
import json
import datetime
from collections import OrderedDict

from ...exception import *
from ... import sanepg2
from ...model import normalized_history_snaptime
from ...util import sql_literal, negotiated_content_type

class Api (object):

    # caches keyed by (catalog descriptor, identifier URI/guid)
    CLIENT_CACHE = OrderedDict()
    GROUP_CACHE = OrderedDict()
    CACHE_SIZE = 128
    CACHE_EXPIRE_SECONDS = 30

    @classmethod
    def _cache_has_key(cls, cache, key):
        threshold = datetime.datetime.utcnow() - datetime.timedelta(seconds=cls.CACHE_EXPIRE_SECONDS)
        victims = []
        if len(cache) > cls.CACHE_SIZE:
            # prune oldest members if cache is too large
            victims.extend(itertools.islice(cache, len(cache) - cls.CACHE_SIZE))
        for k, v in cache.items():
            if v < threshold:
                # prune stale members even if cache is small enough
                victims.append((k, v))
            else:
                break
        for k, v in victims:
            cache.pop(k, None)
        return key in cache

    @classmethod
    def _cache_insert(cls, cache, key):
        cache.pop(key, None)
        cache[key] = datetime.datetime.utcnow()

    def __init__(self, catalog):
        self.catalog = catalog
        self.queryopts = dict()
        self.sort = None
        self.before = None
        self.after = None

        try:
            self.client_register_body(
                web.ctx.ermrest_catalog_pc.conn,
                web.ctx.ermrest_catalog_pc.cur,
            )
        except Exception as te:
            # allow service to function even if this mechanism is broken
            web.debug('Got exception during ERMrest client registration: %s.' % te)
            web.ctx.ermrest_catalog_pc.conn.rollback()

        web.ctx.ermrest_catalog_model = catalog.manager.get_model(
            snapwhen=web.ctx.ermrest_history_snaptime,
            amendver=web.ctx.ermrest_history_amendver
        )
        self.http_vary = web.ctx.webauthn2_manager.get_http_vary()
        self.http_etag = None

    def client_register_body(self, conn, cur):
        client = web.ctx.webauthn2_context.client
        if isinstance(client, dict):
            client_obj = client
            client = client['id']
        else:
            client_obj = { 'id': client }

        cache_key = (str(self.catalog.manager.descriptor), client)
        if client and not self._cache_has_key(self.CLIENT_CACHE, cache_key):
            parts = {
                'id': sql_literal(client_obj['id']),
                'display_name': sql_literal(client_obj.get('display_name')),
                'full_name': sql_literal(client_obj.get('full_name')),
                'email': sql_literal(client_obj.get('email')),
                'client_obj': sql_literal(json.dumps(client_obj)),
            }
            cur.execute("""
SELECT True
FROM public."ERMrest_Client"
WHERE "ID" = %(id)s
  AND "Display_Name" IS NOT DISTINCT FROM %(display_name)s
  AND "Full_Name" IS NOT DISTINCT FROM %(full_name)s
  AND "Email" IS NOT DISTINCT FROM %(email)s
  AND "Client_Object" IS NOT DISTINCT FROM %(client_obj)s::jsonb
LIMIT 1;
""" % parts
            )
            if list(cur):
                # found matching record
                pass
            else:
                cur.execute("""
INSERT INTO public."ERMrest_Client" ("ID", "Display_Name", "Full_Name", "Email", "Client_Object")
VALUES (%(id)s, %(display_name)s, %(full_name)s, %(email)s, %(client_obj)s::jsonb)
ON CONFLICT ("ID") DO UPDATE
SET "Display_Name" = excluded."Display_Name",
    "Full_Name" = excluded."Full_Name",
    "Email" = excluded."Email",
    "Client_Object" = excluded."Client_Object";
""" % parts
                )
                # When we are causing a side-effect, commit it before
                # handling client request.
                #  1. So its effect is visible to ETag conditional processing
                #  2. If the request handler resets connection, we don't lose this update
                conn.commit()

            self._cache_insert(self.CLIENT_CACHE, cache_key)

        attrs = web.ctx.webauthn2_context.attributes if web.ctx.webauthn2_context.attributes else []
        groups = []
        cache_keys = []
        
        for g in attrs:
            if not isinstance(g, dict):
                g = {'id': g}
            if 'identities' not in g and 'display_name' in g:
                cache_key = (str(self.catalog.manager.descriptor), g['id'])
                if not self._cache_has_key(self.GROUP_CACHE, cache_key):
                    groups.append(g)
                    cache_keys.append(cache_key)

        if groups:
            parts = {
                'groups': sql_literal(json.dumps(groups))
            }
            mismatch_query = """
SELECT
  ((j.j)->>'id')::text AS "id",
  ((j.j)->>'display_name')::text AS "display_name"
FROM jsonb_array_elements( %(groups)s::jsonb ) j(j)
LEFT OUTER JOIN public."ERMrest_Group" g
 ON (    ((j.j)->>'id')::text = g."ID"
     AND ((j.j)->>'display_name')::text IS NOT DISTINCT FROM g."Display_Name")
WHERE g."ID" IS NULL
"""
            cur.execute((mismatch_query + " LIMIT 1;") % parts)
            if list(cur):
                # found at least one non-matching group
                cur.execute(("""
INSERT INTO public."ERMrest_Group" ("ID", "Display_Name")
SELECT id, display_name FROM (""" + mismatch_query + """) s
ON CONFLICT ("ID") DO UPDATE
SET "Display_Name" = excluded."Display_Name";
""") % parts
                )
                # When we are causing a side-effect, commit it before
                # handling client request.
                #  1. So its effect is visible to ETag conditional processing
                #  2. If the request handler resets connection, we don't lose this update
                conn.commit()

            for cache_key in cache_keys:
                self._cache_insert(self.GROUP_CACHE, cache_key)

    def history_range(self, h_from, h_until):
        if web.ctx.ermrest_history_snaptime is not None:
            # disable whole /history API if we have a versioned catalog snapshot
            raise NotFound()
        # model will be the current live catalog model since snaptime is None
        cur = web.ctx.ermrest_catalog_pc.cur
        h_from = normalized_history_snaptime(cur, h_from) if h_from else None
        h_until = normalized_history_snaptime(cur, h_until) if h_until else None
        web.ctx.ermrest_history_snaprange = (h_from, h_until)
        return self

    def enforce_right(self, aclname, uri=None):
        """Policy enforcement for named right."""
        decision = web.ctx.ermrest_catalog_model.has_right(aclname)
        if decision is False:
            # we can't stop now if decision is True or None...
            if uri is None:
                uri = web.ctx.env['REQUEST_URI']
            raise rest.Forbidden('%s access on %s' % (aclname, uri))

    def with_queryopts(self, qopt):
        self.queryopts = qopt
        return self

    def with_sort(self, sort):
        self.sort = sort
        return self

    def with_before(self, before):
        self.before = before
        if len(before) != len(self.sort):
            raise rest.BadRequest(
                'The "before" page key of length %d does not match the "sort" key of length %d.'
                % (len(before), len(self.sort))
            )
        return self

    def with_after(self, after):
        self.after = after
        if len(after) != len(self.sort):
            raise rest.BadRequest(
                'The "after" page key of length %d does not match the "sort" key of length %d.'
                % (len(after), len(self.sort))
            )
        return self

    def negotiated_content_type(self, supported_types=None, default=None):
        if supported_types is None:
            supported_types = ['text/csv', 'application/json', 'application/x-json-stream']

        if default is None:
            default = self.default_content_type

        try:
            accept = self.queryopts['accept']
            accept = {'csv': 'text/csv', 'json': 'application/json' }.get(accept, accept)
            if accept in supported_types:
                return accept
        except KeyError:
            pass

        return negotiated_content_type(supported_types=supported_types, default=default)

    def negotiated_limit(self):
        """Determine query result size limit to use."""
        if 'limit' in self.queryopts:
            limit = self.queryopts['limit']
            if str(limit).lower() == 'none':
                limit = None
            else:
                try:
                    limit = int(limit)
                except ValueError as e:
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
            client = web.ctx.webauthn2_context.client
            if isinstance(client, dict):
                client = client['id']
            etag.append( '%s' % client )
        else:
            etag.append( '*' )
            
        if 'accept' in self.http_vary:
            etag.append( '%s' % web.ctx.env.get('HTTP_ACCEPT', '') )
        else:
            etag.append( '*' )

        etag.append( '%s' % version )

        self.http_etag = '"%s"' % ';'.join(etag).replace('"', '\\"')

    def parse_client_etags(self, header):
        """Parse header string for ETag-related preconditions.

           Returns dict mapping ETag -> boolean indicating strong
           (true) or weak (false).

           The special key True means the '*' precondition was
           encountered which matches any representation.

        """
        def etag_parse(s):
            strong = True
            if s[0:2] == 'W/':
                strong = False
                s = s[2:]
            if s[-6:] == '-gzip"':
                # remove stupid suffix added by mod_deflate
                s = s[:-6] + '"'
            return (s, strong)

        s = header
        etags = []
        # pick off one ETag prefix at a time, consuming comma-separated list
        while s:
            s = s.strip()
            # accept leading comma that isn't really valid by spec...
            m = re.match('^,? *(?P<first>(W/)?"([^"]|\\\\")*")(?P<rest>.*)', s)
            if m:
                # found 'W/"tag"' or '"tag"'
                g = m.groupdict()
                etags.append(etag_parse(g['first']))
                s = g['rest']
                continue
            m = re.match('^,? *[*](?P<rest>.*)', s)
            if m:
                # found '*'
                # accept anywhere in list even though spec is more strict...
                g = m.groupdict()
                etags.append((True, True))
                s = g['rest']
                continue
            s = None

        return dict(etags)
        
    def http_check_preconditions(self, method='GET', resource_exists=True):
        failed = False

        match_etags = self.parse_client_etags(web.ctx.env.get('HTTP_IF_MATCH', ''))
        if match_etags:
            if resource_exists:
                if self.http_etag and self.http_etag not in match_etags \
                   and (True not in match_etags):
                    failed = True
            else:
                failed = True
        
        nomatch_etags = self.parse_client_etags(web.ctx.env.get('HTTP_IF_NONE_MATCH', ''))
        if nomatch_etags:
            if resource_exists:
                if self.http_etag and self.http_etag in nomatch_etags \
                   or (True in nomatch_etags):
                    failed = True

        if failed:
            headers={ 
                "ETag": self.http_etag, 
                "Vary": ", ".join(self.http_vary)
            }
            if method == 'GET':
                raise rest.NotModified(headers=headers)
            else:
                raise rest.PreconditionFailed(headers=headers)

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
                client = web.ctx.webauthn2_context.client
                if type(client) is dict:
                    client_obj = client
                    client = client['id']
                else:
                    client_obj = { 'id': client }

                attributes = [
                    a['id'] if type(a) is dict else a
                    for a in web.ctx.webauthn2_context.attributes
                ]
                
                cur.execute("""
SELECT set_config('webauthn2.client', %s, false);
SELECT set_config('webauthn2.client_json', %s, false);
SELECT set_config('webauthn2.attributes', %s, false);
SELECT set_config('webauthn2.attributes_array', (ARRAY[%s]::text[])::text, false);
""" % (
    sql_literal(client),
    sql_literal(json.dumps(client_obj)),
    sql_literal(json.dumps(attributes)),
    ','.join([
        sql_literal(attr)
        for attr in attributes
    ])
)
                )
                return body(conn, cur)
            except psycopg2.InterfaceError as e:
                raise rest.ServiceUnavailable("Please try again.")
            
        return web.ctx.ermrest_catalog_pc.perform(wrapbody, finish)
    
    def final(self):
        if self.catalog is not self:
            self.catalog.final()

