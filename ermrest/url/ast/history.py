
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
from ...model.schema import Model, Schema
from ...model.table import Table
from ...model.column import Column
from ...model.key import KeyReference, PseudoKeyReference
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

def _validate_history_snaprange(cur):
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

    return h_from, h_until, amendver

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
        h_from, h_until, amendver = _validate_history_snaprange(cur)
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
WHERE "RID" = %(table_rid)s::text
  AND lower(during) >= %(h_until)s::timestamptz
LIMIT 1;
""" % {
    'table_rid': sql_literal(table_rid),
    'h_until': sql_literal(h_until),
})
            is_visible = cur.fetchone() is not None
            if not is_visible:
                # sanity check
                cur.execute('SELECT True FROM _ermrest.known_tables WHERE "RID" = %s' % sql_literal(table_rid));
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
            htable_name = 't%s' % table_rid
            if visible_after(table_rid):
                truncate_htable(table_rid, htable_name)
            else:
                drop_htable(table_rid, htable_name)

        for table_rid, htable_name in system_tables.items():
            if table_exists(cur, '_ermrest_history', htable_name):
                truncate_htable(table_rid, htable_name)

        fixup_catalog_metadata()
        return ''

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

def _validate_model_rid(cur, rid, h_from, u_until, restypes={'schema', 'table', 'column', 'key', 'pseudo_key', 'fkey', 'pseudo_fkey'}):
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

def _get_crid_table_rid(cur, column_rid):
    cur.execute("""
SELECT rowdata->>'table_rid' FROM _ermrest_history.known_columns WHERE "RID" = %(target_rid)s LIMIT 1;
""" % {
    'target_rid': sql_literal(column_rid),
})
    return cur.fetchone()[0]

def _crid_is_unpacked(cur, column_rid, readonly=True):
    cur.execute("""
SELECT array_agg(DISTINCT rowdata->>'column_name')
FROM _ermrest_history.known_columns
WHERE "RID" = %(column_rid)s
""" % {
    'column_rid': sql_literal(column_rid),
})
    cnames = set(cur.fetchone()[0])
    unpacked_cnames = cnames.intersection({'RID', 'RMT', 'RMB'})
    if unpacked_cnames:
        if len(cnames) > 1:
            raise NotImplementedError('Redaction column %s inconsistently in rowdata or unpacked?' % column_rid)
        if len(unpacked_cnames) > 1:
            raise NotImplementedError('Redaction column %s inconsistently as unpacked columns' % column_rid)
        if not readonly:
            raise exception.rest.Conflict('Redactive modification of column %s is not possible.' % column_rid)
        return unpacked_cnames.pop()
    else:
        return False

def _redact_column(cur, table_rid, target_rid, h_from, h_until, filter_rid=None, filter_value=None):
    _crid_is_unpacked(cur, target_rid, readonly=False)

    if filter_rid is not None:
        unpacked = _crid_is_unpacked(cur, filter_rid)
        v = json.loads(filter_value)
        if unpacked == 'RID':
            filter_clause = '"RID" = %s::text' % sql_literal(v)
        elif unpacked == 'RMB':
            filter_clause = '"RMB" = %s::text' % sql_literal(v)
        elif unpacked == 'RMT':
            filter_clause = 'lower(during) = %s::timestamptz' % sql_literal(v)
        elif unpacked is False:
            filter_clause = 'rowdata->%s = %s::jsonb' % (sql_literal(filter_rid), sql_literal(filter_value))
        else:
            raise NotImplementedError('Redaction unpacked column %s' % unpacked)
    else:
        filter_clause = 'True'

    # BUG: this only redacts wholly enclosed tuple versions...
    # should we also split overlapping tuple versions and redact the enclosed portion?
    cur.execute("""
UPDATE _ermrest_history.%(htable_name)s
SET rowdata = jsonb_set(rowdata, ARRAY[%(target_rid)s::text], 'null'::jsonb, False)
WHERE %(filter_clause)s
  AND tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)') @> during ;
""" % {
    'htable_name': sql_identifier('t%s' % table_rid),
    'target_rid': sql_literal(target_rid),
    'filter_clause': filter_clause,
    'h_from': sql_literal(h_from),
    'h_until': sql_literal(h_until),
})

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
        try:
            s = json.loads(filter_val)
        except:
            raise exception.rest.BadRequest(u'Filter value %s is not valid JSON.' % filter_val)
        return self

    def validate_target(self, cur, h_from, h_until):
        _validate_model_rid(cur, self.target_rid, h_from, h_until, {'column'})
        if self.filter_rid is not None:
            _validate_model_rid(cur, self.filter_rid, h_from, h_until, {'column'})

    def GET_body(self, conn, cur):
        self.enforce_right('owner')
        h_from, h_until, amendver = _validate_history_snaprange(cur)
        self.validate_target(cur, h_from, h_until)
        return (
            (h_from, h_until, amendver),
            {
                "amendver": _encode_ts(cur, amendver),
                "snaprange": [ _encode_ts(cur, h_from), _encode_ts(cur, h_until) ],
            }
        )

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def DELETE_body(self, conn, cur):
        h_from, h_until = web.ctx.ermrest_history_snaprange
        if h_from is None:
            raise exception.BadData('Redaction requires a lower time bound.')
        if h_until is None:
            raise exception.BadData('Redaction requires an upper time bound.')

        h_from, h_until, amendver = self.GET_body(conn, cur)[0]

        table_rid = _get_crid_table_rid(cur, self.target_rid)

        if self.filter_rid is not None:
            if table_rid != _get_crid_table_rid(cur, self.filter_rid):
                raise exception.rest.Conflict('Filter column %s and target column %s do not belong to the same table.' % (self.filter_rid, self.target_rid))

        if not table_exists(cur, '_ermrest_history', 't%s' % table_rid):
            raise exception.rest.Conflict('Target table %s for target column %s lacks history tracking.' % (table_rid, self.target_rid))

        cur.execute("""
INSERT INTO _ermrest.catalog_amended (ts, during)
VALUES (now(), tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)'));
""" % {
    'h_from': sql_literal(h_from),
    'h_until': sql_literal(h_until),
    })

        _redact_column(cur, table_rid, self.target_rid, h_from, h_until, self.filter_rid, self.filter_val)
        return ''

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

def _amend_config(cur, h_from, h_until, restype, configtype, rid, namecol, contentcol, contentmap):
    cur.execute("""
INSERT INTO _ermrest.catalog_amended (ts, during)
VALUES (now(), tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)'))
ON CONFLICT (ts) DO NOTHING;

-- adjust live tuples to be consistent with revised history boundary
UPDATE _ermrest.known_%(restype)s_%(configtype)ss
SET
  "RMT" = %(h_until)s::timestamptz,
  "RMB" = _ermrest.current_client()
WHERE "RMT"::timestamptz < %(h_until)s::timestamptz;

WITH content AS (
  SELECT * FROM jsonb_each(%(contentmap)s::jsonb) j (key, value)
), snaprange AS (
  SELECT tstzrange(%(h_from)s::timestamptz, %(h_until)s::timestamptz, '[)') AS snaprange
), deleted AS (
  -- clear out all overlapping configs so we can build up desired state
  DELETE FROM _ermrest_history.known_%(restype)s_%(configtype)ss
  WHERE during && (SELECT snaprange FROM snaprange)
    AND %(rid_clause)s
  RETURNING *
), restore_prefix AS (
  -- rebuild any preceding config by clamping upper
  INSERT INTO _ermrest_history.known_%(restype)s_%(configtype)ss ("RID", during, "RMB", rowdata)
  SELECT
    "RID",
    tstzrange(lower(during), %(h_from)s::timestamptz, '[)'),
    "RMB",
    rowdata
  FROM deleted
  WHERE lower(during) < %(h_from)s::timestamptz OR lower(during) IS NULL
  RETURNING *
), restore_suffix AS (
  -- rebuild any succeeding config by clamping lower
  -- HACK: existing RID may disappear and reappear before/after the amended interval
  INSERT INTO _ermrest_history.known_%(restype)s_%(configtype)ss ("RID", during, "RMB", rowdata)
  SELECT
    "RID",
    tstzrange(%(h_until)s::timestamptz, upper(during), '[)'),
    "RMB",
    rowdata
  FROM deleted
  WHERE upper(during) > %(h_until)s::timestamptz OR upper(during) IS NULL
  RETURNING *
), construct_amended AS (
  -- now, create the desired config during the amended interval using fresh RIDs
  INSERT INTO _ermrest_history.known_%(restype)s_%(configtype)ss ("RID", during, "RMB", rowdata)
  SELECT
    nextval('_ermrest.rid_seq'::regclass),
    (SELECT snaprange FROM snaprange),
    _ermrest.current_client(),
    jsonb_build_object(
      'RCB', _ermrest.current_client(),
      'RCT', %(h_from)s::timestamptz::text,
      %(j_rid_field)s
      '%(namecol)s', key,
      '%(contentcol)s', value
    )
  FROM content
  RETURNING *
)
SELECT jsonb_build_object(
    'content',   (SELECT jsonb_agg(to_jsonb(s)) FROM content s),
    'snaprange', (SELECT jsonb_agg(to_jsonb(s)) FROM snaprange s),
    'deleted',   (SELECT jsonb_agg(to_jsonb(s)) FROM deleted s),
    'prefix',    (SELECT jsonb_agg(to_jsonb(s)) FROM restore_prefix s),
    'suffix',    (SELECT jsonb_agg(to_jsonb(s)) FROM restore_suffix s),
    'construct', (SELECT jsonb_agg(to_jsonb(s)) FROM construct_amended s)
);
""" % {
    'h_from': sql_literal(h_from),
    'h_until': sql_literal(h_until),
    'restype': restype,
    'configtype': configtype,
    'rid_clause': ("rowdata->'%s_rid' = to_jsonb(%s::text)" % (restype, sql_literal(rid))) if rid is not None else 'True',
    'j_rid_field': ("'%s_rid', to_jsonb(%s::text)," % (restype, sql_literal(rid))) if rid is not None else "",
    'namecol': namecol,
    'contentcol': contentcol,
    'contentmap': sql_literal(json.dumps(contentmap)),
})
    #web.debug('_amend_config:', cur.fetchone()[0])

def _amend_acl(cur, h_from, h_until, restype, rid, contentmap):
    try:
        subject_class = {
            'catalog': Model,
            'schema': Schema,
            'table': Table,
            'column': Column,
            'fkey': KeyReference,
            'pseudo_fkey': PseudoKeyReference,
        }[restype]
    except KeyError:
        raise exception.rest.Conflict('ACLs are not supported on selected %s resource.' % restype)

    for name, content in contentmap.items():
        if name not in subject_class._acls_supported:
            raise exception.rest.Conflict('ACL name "%s" not supported on %s resources.' % (name, restype))

        if not isinstance(content, (list, type(None))):
            raise exception.rest.BadRequest('ACL content must be a list or null.')

    contentmap = {
        k: v
        for k, v in contentmap.items()
        if v is not None
    }

    _amend_config(cur, h_from, h_until, restype, 'acl', rid, 'acl', 'members', contentmap)

def _amend_acl_binding(cur, h_from, h_until, restype, rid, contentmap):
    try:
        subject_class = {
            'table': Table,
            'column': Column,
            'fkey': KeyReference,
            'pseudo_fkey': PseudoKeyReference,
        }[restype]
    except KeyError:
        raise exception.rest.Conflict('ACL bindings are not supported on selected %s resource.' % restype)

    raise exception.rest.NoMethod('Amendment of historical ACL bindings currently not implemented.')

    for name, content in contentmap.items():
        if not isinstance(name, (str, unicode)):
            raise exception.rest.Conflict('ACL binding names must be textual.')

        if not (isinstance(content, dict) or content is False):
            raise exception.rest.BadRequest('ACL binding must be an object or false value.')
        # TODO: further ACL binding validation...?

    _amend_config(cur, h_from, h_until, restype, 'dynacl', rid, 'binding_name', 'binding', contentmap)

def _amend_annotation(cur, h_from, h_until, restype, rid, contentmap):
    for name, content in contentmap.items():
        if not isinstance(name, (str, unicode)):
            raise exception.rest.Conflict('Annotation keys must be textual.')

    _amend_config(cur, h_from, h_until, restype, 'annotation', rid, 'annotation_uri', 'annotation_value', contentmap)

class ConfigHistory (Api):
    """Represents over-writable configuration resources.

       URL 1: /ermrest/catalog/N/history/from,until/API
       URL 2: /ermrest/catalog/N/history/from,until/RID/API

       This ugly code handles a matrix of target types and payload types.
    
       RID, when present, is the model resource RID of the config subject.
       API is the subresource type 'acl', 'acl_binding', or 'annotation'.

    """
    subresource_apis = {
        'acl':         (_amend_acl),
        'acl_binding': (_amend_acl_binding),
        'annotation':  (_amend_annotation),
    }
    
    def __init__(self, history_catalog, subresource_api, target_rid=None):
        Api.__init__(self, history_catalog)
        assert subresource_api in self.subresource_apis
        self.subresource_api = subresource_api
        self.target_rid = target_rid
        self.target_type = None

    def validate_target(self, cur, h_from, h_until):
        if self.target_rid is None:
            self.target_type = 'catalog'
        else:
            # probe each resource type to figure out what the RID refers to...
            self.target_type = _validate_model_rid(cur, self.target_rid, h_from, h_until)

    def GET_body(self, conn, cur):
        self.enforce_right('owner')
        h_from, h_until, amendver = _validate_history_snaprange(cur)
        self.validate_target(cur, h_from, h_until)
        return (
            (h_from, h_until, amendver),
            {
                "amendver": _encode_ts(cur, amendver),
                "snaprange": [ _encode_ts(cur, h_from), _encode_ts(cur, h_until) ],
            }
        )

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def PUT_body(self, conn, cur, content):
        h_from, h_until = web.ctx.ermrest_history_snaprange
        if h_from is None:
            raise exception.rest.BadRequest('Historical %s amendment requires a lower time bound.' % self.subresource_api)
        if h_until is None:
            raise exception.rest.BadRequest('Historical %s amendment requires an upper time bound.' % self.subresource_api)

        if not isinstance(content, dict):
            raise exception.rest.BadRequest('Amendment input must be a key-value mapping object.')

        h_from, h_until, amendver = self.GET_body(conn, cur)[0]
        self.subresource_apis[self.subresource_api](cur, h_from, h_until, self.target_type, self.target_rid, content)
        return ''

    def PUT(self, uri):
        return _MODIFY_with_json_input(self, self.PUT_body, _post_commit)
