
# 
# Copyright 2017 University of Southern California
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

from ...model import current_request_snaptime
from ... import exception
from ...util import sql_literal, sql_identifier, table_exists
from .api import Api

def _post_commit(handler, resource, content_type='text/plain', transform=lambda v: v):
    handler.emit_headers()
    if resource is None and content_type == 'text/plain':
        return ''
    if resource is '' and web.ctx.status == '200 OK':
        web.ctx.status = '204 No Content'
        return ''
    web.header('Content-Type', content_type)
    response = transform(resource)
    web.header('Content-Length', len(response))
    return response

def _post_commit_json(handler, py_pj_pair):
    def to_json(py_pj_pair):
        return json.dumps(py_pj_pair[1], indent=2) + '\n'
    return _post_commit(handler, py_pj_pair, 'application/json', to_json)

_RANGE_AMENDVER_SQL="""
SELECT ts 
FROM _ermrest.catalog_amended 
WHERE during && tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)')
ORDER BY ts DESC 
LIMIT 1
"""

def _etag(cur):
    """Get current history ETag during request processing."""
    h_from, h_until = web.ctx.ermrest_history_snaprange
    cur.execute(("SELECT _ermrest.tstzencode( GREATEST( %(h_until)s::timestamptz, (" + _RANGE_AMENDVER_SQL + ")) );") % {
        'h_from': sql_literal(h_from),
        'h_until': sql_literal(h_until),
    })
    return cur.next()[0]

def _encode_ts(cur, ts):
    cur.execute("SELECT _ermrest.tstzencode(%s::timestamptz)::text;" % sql_literal(ts))
    return cur.next()[0]

def _GET(handler, thunk, _post_commit):
    def body(conn, cur):
        handler.enforce_right('owner')
        handler.set_http_etag(_etag(cur))
        handler.http_check_preconditions()
        return thunk(conn, cur)
    return handler.perform(body, lambda resource: _post_commit(handler, resource))

def _MODIFY(handler, thunk, _post_commit):
    def body(conn, cur):
        handler.enforce_right('owner')
        h_from, h_until = web.ctx.ermrest_history_snaprange
        amendver = web.ctx.ermrest_history_amendver
        # this is the ETag at start of request processing
        handler.set_http_etag(_etag(cur))
        handler.http_check_preconditions(method='PUT')
        result = thunk(conn, cur)
        # this is the ETag resulting from request processing
        amendver = current_request_snaptime(cur)
        handler.set_http_etag(amendver)
        return result
    return handler.perform(body, lambda resource: _post_commit(handler, resource))

def _MODIFY_with_json_input(handler, thunk, _post_commit):
    try:
        doc = json.load(web.ctx.env['wsgi.input'])
    except:
        raise exception.rest.BadRequest('Could not deserialize JSON input.')
    return _MODIFY(handler, lambda conn, cur: thunk(conn, cur, doc), _post_commit)

class CatalogHistory (Api):
    """Represents whole-catalog history resource.

       URL: /ermrest/catalog/N/history/from,until

    """
    def __init__(self, history_catalog):
        Api.__init__(self, history_catalog)

    def GET_body(self, conn, cur):
        """Produce (python, prejson) status summary.

           Result: (python_status, prejson_status)
             python_status: ( (h_from, h_until), amendver )
             prejson_status: { "snaprange": [ h_from_epoch, h_until_epoch ], "amendver": amendver_epoch }
        """
        h_from, h_until = web.ctx.ermrest_history_snaprange

        if h_from is None:
            cur.execute("""
SELECT LEAST(
  (SELECT ts 
   FROM _ermrest.model_modified 
   WHERE tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)') @> ts
   ORDER BY ts LIMIT 1),
  (SELECT ts 
   FROM _ermrest.table_modified 
   WHERE tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)') @> ts
   ORDER BY ts LIMIT 1)
);
""" % {
    'h_from': sql_literal(h_from),
    'h_until': sql_literal(h_until),
})
            h_from = cur.next()[0]

        if h_until is None:
            cur.execute("""
SELECT GREATEST(
  (SELECT ts 
   FROM _ermrest.model_modified 
   WHERE tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)') @> ts
   ORDER BY ts DESC LIMIT 1),
  (SELECT ts 
   FROM _ermrest.table_modified 
   WHERE tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)') @> ts
   ORDER BY ts DESC LIMIT 1)
);
""" % {
    'h_from': sql_literal(h_from),
    'h_until': sql_literal(h_until),
})
            h_until = cur.next()[0]

        if h_from is None or h_until is None:
            raise exception.rest.NotFound('history range [%s,%s)' % (h_from, h_until))

        cur.execute(_RANGE_AMENDVER_SQL % {
            'h_from': sql_literal(h_from),
            'h_until': sql_literal(h_until),
        })
        amendver = cur.fetchone()
        amendver = amendver[0] if amendver is not None else None

        return (
            ( (h_from, h_until), amendver ),
            {
                'snaprange': [ _encode_ts(cur, h_from), _encode_ts(cur, h_until) ],
                'amendver': _encode_ts(cur, amendver),
            }
        )

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
        
    def DELETE_body(self, conn, cur):
        h_from, h_until = web.ctx.ermrest_history_snaprange
        if h_from is not None:
            raise exception.BadData('History truncation requires an empty lower time bound.')
        if h_until is None:
            raise exception.BadData('History truncation requires an upper time bound.')

        # get normalized history range or raise NotFound early...
        py_pj_pair = self.GET_body(conn, cur)
        snaprange, amendver = py_pj_pair[0]
        
        # find all table RIDs known during the history range we plan to nuke
        def affected_tables():
            """Find affected tables as (user_tables, system_tables) pair."""
            cur.execute("""
SELECT DISTINCT
 t."RID", 
 CASE WHEN s.rowdata->>'schema_name' = '_ermrest' THEN  t.rowdata->>'table_name' ELSE NULL::text END AS system_table_name
FROM _ermrest_history.known_tables t
JOIN _ermrest_history.known_schemas s ON (to_jsonb(s."RID") = t.rowdata->'schema_rid' AND t.during && s.during)
WHERE t.during && tstzrange(NULL, %(h_until)s::timestamptz, '[)');
""" % {
    'h_until': sql_literal(h_until),
})
            user_tables = set()
            system_tables = {}
            for table_rid, system_table_name in cur:
                if system_table_name is not None:
                    system_tables[table_rid] = system_table_name
                else:
                    user_tables.add(table_rid)
            return user_tables, system_tables

        def visible_after(table_rid):
            cur.execute("""
SELECT True
FROM _ermrest_history.known_tables
WHERE "RID" = %(table_rid)s::int8
  AND lower(during) >= %(h_until)s::timestamptz
LIMIT 1;
""" % {
    'table_rid': sql_literal(table_rid),
    'h_until': sql_literal(h_until),
})
            is_visible = cur.fetchone() is not None
            if not is_visible:
                # sanity check
                cur.execute('SELECT True FROM _ermrest.known_tables WHERE "RID" = %s' % table_rid);
                assert cur.fetchone() is None
            return is_visible

        def truncate_htable(table_rid, htable_name):
            """Truncate record of this still-visible table."""
            if table_exists(cur, '_ermrest_history', htable_name):
                # prune history tuple storage
                cur.execute("""
DELETE FROM _ermrest_history.%(htable_name)s WHERE upper(during) <= %(h_until)s::timestamptz;
""" % {
    'htable_name': sql_identifier(htable_name),
    'h_until': sql_literal(h_until),
})
            # fixup metadata
            cur.execute("""
DELETE FROM _ermrest.table_modified WHERE table_rid = %(table_rid)s AND ts < %(h_until)s::timestamptz;
DELETE FROM _ermrest.table_last_modified WHERE table_rid = %(table_rid)s AND ts < %(h_until)s::timestamptz;

INSERT INTO _ermrest.table_modified (ts, table_rid) VALUES (now(), %(table_rid)s)
  ON CONFLICT (ts, table_rid) DO NOTHING;

INSERT INTO _ermrest.table_last_modified (ts, table_rid) VALUES (now(), %(table_rid)s)
  ON CONFLICT (table_rid) DO NOTHING;
""" % {
    'htable_name': sql_identifier(htable_name),
    'h_until': sql_literal(h_until),
    'table_rid': sql_literal(table_rid),
})

        def drop_htable(table_rid, htable_name):
            """Remove all record of this purged table."""
            if table_exists(cur, '_ermrest_history', htable_name):
                # drop history tuple storage
                cur.execute("""
DROP TABLE _ermrest_history.%(htable_name)s;
""" % {
    'htable_name': sql_identifier(htable_name),
    'table_rid': sql_literal(table_rid),
})
            # fixup metadata
            cur.execute("""
DELETE FROM _ermrest.table_modified WHERE table_rid = %(table_rid)s;
DELETE FROM _ermrest.table_last_modified WHERE table_rid = %(table_rid)s;
""" % {
    'htable_name': sql_identifier(htable_name),
    'table_rid': sql_literal(table_rid),
})

        def fixup_catalog_metadata():
            cur.execute("""
DELETE FROM _ermrest.model_modified WHERE ts < %(h_until)s::timestamptz;
DELETE FROM _ermrest.model_last_modified WHERE ts < %(h_until)s::timestamptz;

INSERT INTO _ermrest.model_modified (ts) VALUES (now()) ON CONFLICT (ts) DO NOTHING;
INSERT INTO _ermrest.model_last_modified (ts) VALUES (now()) ON CONFLICT (ts) DO NOTHING;

DELETE FROM _ermrest.catalog_amended WHERE upper(during) <= %(h_until)s::timestamptz;

INSERT INTO _ermrest.catalog_amended (ts, during)
  VALUES (now(), tstzrange(NULL::timestamptz, %(h_until)s::timestamptz, '[)'));
""" % {
    'h_until': sql_literal(h_until),
})

        user_tables, system_tables = affected_tables()
        
        for table_rid in user_tables:
            htable_name = 't%d' % table_rid
            if visible_after(table_rid):
                truncate_htable(table_rid, htable_name)
            else:
                drop_htable(table_rid, htable_name)

        for table_rid, htable_name in system_tables.items():
            if table_exists(cur, '_ermrest_history', htable_name):
                truncate_htable(table_rid, htable_name)

        fixup_catalog_metadata()

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

def _validate_model_rid(cur, rid, restypes={'schema', 'table', 'column', 'key', 'pseudo_key', 'fkey', 'pseudo_fkey'}):
    for restype in restypes:
        cur.execute("""
SELECT True FROM _ermrest_history.known_%(restype)ss WHERE "RID" = %(target_rid)s LIMIT 1;
""" % {
    'restype': restype,
    'target_rid': sql_literal(rid),
})
        res = cur.fetchone()
        if res is not None:
            return restype
    raise exception.NotFound('Historical model resource with RID=%s' % rid)
    
class DataHistory (Api):
    """Represents data history resources.

       URL1: /ermrest/catalog/N/history/from,until/attribute/CRID
       URL2: /ermrest/catalog/N/history/from,until/attribute/CRID/FRID=FVAL

    """
    def __init__(self, history_catalog, target_rid, filter_rid=None, filter_val=None):
        Api.__init__(self, history_catalog)
        self.target_rid = target_rid
        self.filter_rid = None
        self.filter_val = None

    def filtered(self, filter_rid, filter_val):
        """Add a value filter to a data history resource."""
        self.filter_rid = filter_rid
        self.filter_val = filter_val
        return self

    def validate_target(self, cur):
        self.target_type = _validate_model_rid(cur, self.target_rid, {'table', 'column'})

    def DELETE_body(self, conn, cur):
        self.enforce_right('owner')
        h_from, h_until = web.ctx.ermrest_history_range
        if h_from is None:
            raise exception.BadData('Redaction requires a lower time bound.')
        if h_until is None:
            raise exception.BadData('Redaction requires an upper time bound.')
        self.validate_target(cur)
        # TODO: perform data redaction
        raise exception.ConflictModel('Historical data redaction not yet implemented.')

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

class ConfigHistory (Api):
    """Represents over-writable configuration resources.

       URL 1: /ermrest/catalog/N/history/from,until/API
       URL 2: /ermrest/catalog/N/history/from,until/RID/API

       This ugly code handles a matrix of target types and payload types.
    
       RID, when present, is the model resource RID of the config subject.
       API is the subresource type 'acl', 'acl_binding', or 'annotation'.

    """
    subresource_apis = {
        'acl':         (),
        'acl_binding': (),
        'annotation':  (),
    }
    
    def __init__(self, history_catalog, subresource_api, target_rid=None):
        Api.__init__(self, history_catalog)
        assert subresource_api in subresource_apis
        self.subresource_api = subresource_api
        self.target_rid = target_rid
        self.target_type = None

    def validate_target(self, cur):
        if self.target_rid is None:
            self.target_type = 'catalog'
        else:
            # probe each resource type to figure out what the RID refers to...
            self.target_type = _validate_mode_rid(cur, self.target_rid)

    def PUT_body(self, cur, content):
        self.enforce_right('owner')
        if h_from is None:
            raise exception.BadData('Historical %s amendment requires a lower time bound.' % self.subresource_api)
        if h_until is None:
            raise exception.BadData('Historical %s amendment requires an upper time bound.' % self.subresource_api)
        self.validate_target(cur)
        # TODO: amend historical config
        raise exception.ConflictModel('Historical %s amendment not yet implemented.' % self.subresource_api)

    def PUT(self, uri):
        return _MODIFY_with_json_input(self, self.PUT_body, _post_commit)
