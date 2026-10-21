
# 
# Copyright 2017-2026 University of Southern California
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
import flask
from webauthn2.util import deriva_ctx, deriva_debug

from ...model import current_request_snaptime
from ...model.schema import Model, Schema
from ...model.table import Table
from ...model.column import Column
from ...model.key import KeyReference, PseudoKeyReference
from ... import exception
from ...util import sql_literal, sql_identifier, table_exists, enumerate_indexes, drop_index, index_exists_on_table
from .api import Api

def _post_commit(handler, resource, content_type='text/plain', transform=lambda v: v):
    handler.emit_headers()
    if resource is None and content_type == 'text/plain':
        deriva_ctx.deriva_response.response = []
        return deriva_ctx.deriva_response
    if resource == '' and deriva_ctx.deriva_response.status_code == 200:
        deriva_ctx.deriva_response.status_code = 204
        deriva_ctx.deriva_response.response = []
        return deriva_ctx.deriva_response
    deriva_ctx.deriva_response.content_type = content_type
    response = transform(resource)
    deriva_ctx.deriva_response.content_length = len(response)
    deriva_ctx.deriva_response.response = response
    return deriva_ctx.deriva_response

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
    h_from, h_until = deriva_ctx.ermrest_history_snaprange
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
        h_from = cur.fetchone()[0]

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
        h_until = cur.fetchone()[0]

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
    h_from, h_until = deriva_ctx.ermrest_history_snaprange if deriva_ctx.ermrest_history_snaprange else (None, None)

    cur.execute(("SELECT _ermrest.tstzencode( GREATEST( %(h_until)s::timestamptz, (" + _RANGE_AMENDVER_SQL + ")) );") % {
        'h_from': sql_literal(h_from),
        'h_until': sql_literal(h_until),
    })
    return cur.fetchone()[0]

def _encode_ts(cur, ts):
    cur.execute("SELECT _ermrest.tstzencode(%s::timestamptz)::text;" % sql_literal(ts))
    return cur.fetchone()[0]

def _GET(handler, thunk, _post_commit):
    def body(conn, cur):
        handler.set_http_etag(_etag(cur))
        handler.http_check_preconditions()
        return thunk(conn, cur)
    return handler.perform(body, lambda resource: _post_commit(handler, resource))

def _MODIFY(handler, thunk, _post_commit):
    def body(conn, cur):
        handler.enforce_right('owner')
        h_from, h_until = deriva_ctx.ermrest_history_snaprange if deriva_ctx.ermrest_history_snaprange else (None, None)
        amendver = deriva_ctx.ermrest_history_amendver
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
        doc = json.loads(flask.request.stream.read().decode())
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
        self.enforce_right('enumerate')
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
        h_from, h_until = deriva_ctx.ermrest_history_snaprange
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
  AND upper(during) >= %(h_until)s::timestamptz OR upper(during) IS NULL
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

INSERT INTO _ermrest.table_last_modified (ts, table_rid)
SELECT now(), t."RID"
FROM _ermrest.known_tables t
WHERE t."RID" = %(table_rid)s
  ON CONFLICT (table_rid) DO NOTHING;

DELETE FROM _ermrest_history.visible_entities
WHERE upper(during) <= %(h_until)s::timestamptz
  AND table_rid = %(table_rid)s;
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
DELETE FROM _ermrest_history.visible_entities WHERE table_rid = %(table_rid)s;
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
        h_from, h_until = deriva_ctx.ermrest_history_snaprange
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
    #deriva_debug('_amend_config:', cur.fetchone()[0])

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

    for name, content in contentmap.items():
        if not isinstance(name, str):
            raise exception.rest.Conflict('ACL binding names must be textual.')

        if not (isinstance(content, dict) or content is False):
            raise exception.rest.BadRequest('ACL binding must be an object or false value.')
        # TODO: further ACL binding validation...?

    _amend_config(cur, h_from, h_until, restype, 'dynacl', rid, 'binding_name', 'binding', contentmap)

def _amend_annotation(cur, h_from, h_until, restype, rid, contentmap):
    for name, content in contentmap.items():
        if not isinstance(name, str):
            raise exception.rest.Conflict('Annotation keys must be textual.')
        if name in {Table.tag_history_capture}:
            raise exception.rest.BadRequest('Annotations with key %s cannot be amended.' % name)

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
        h_from, h_until = deriva_ctx.ermrest_history_snaprange
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

class HistoryTables:
    """Represents set of history tables

       URL: /ermrest/catalog/N/history/table/

    """
    def __init__(self, catalog):
        assert deriva_ctx.ermrest_history_snaprange is None
        self.catalog = catalog

    def with_trid(self, table_rid):
        return HistoryTable(self.catalog, table_rid)

class HistoryTable:
    """Represents one history table

       URL: /ermrest/catalog/N/history/table/

    """
    def __init__(self, catalog, table_rid):
        self.catalog = catalog
        self.table_rid = table_rid

    def indexing(self):
        return HistoryTableIndexing(self.catalog, self.table_rid)

class HistoryTableIndexing (Api):
    """Represents data history resources.

       URL1: /ermrest/catalog/N/history/table/TRID/index/
       URL2: /ermrest/catalog/N/history/table/TRID/index/INAME

    """
    def __init__(self, catalog, table_rid):
        Api.__init__(self, catalog)
        assert deriva_ctx.ermrest_history_snaprange is None
        self.table_rid = table_rid
        self.index_name = None
        if deriva_ctx.ermrest_history_snaptime is not None:
            raise exception.rest.NotFound('History table index management on a versioned catalog snapshot.')

    @classmethod
    def row_to_dict(cls, row):
        schemaname, tablename, indexname, primary, unique, exclusion, sqldef = row
        return {
            "indexname": indexname,
            "primary": primary,
            "unique": unique,
            "exclusion": exclusion,
            "sqldef": sqldef,
        }

    def _check_conflicts(self, resource, op):
        conflicts = { k for k in {"primary", "unique", "exclusion"} if resource[k] }
        if conflicts:
            raise exception.Forbidden(f'{op} of {"+".join(conflicts)} index {self.index_name!r}')

    def with_name(self, index_name):
        assert self.index_name is None
        self.index_name = index_name
        return self

    # HACK: the following must be kept in sync with
    # ermrest.model.types OOP methods which are written in terms of a
    # catalog (or snapshot) model, rather than the longitudinal
    # perspective we have to take here.  potential hazards:
    #
    # 1. a column that is altered to change type over time
    # 2. a type RID that changes meaning over time (?)
    #

    def _check_trid(self, cur):
        # find first occurrence of table_rid and its schema name
        # ignoring internal _ermrest schema
        cur.execute(f"""
SELECT
  t."RID"
FROM _ermrest_history.known_tables t
WHERE t."RID" = {sql_literal(self.table_rid)}
  AND EXISTS (
    SELECT true
    FROM _ermrest_history.known_schemas s
    WHERE s."RID" = t.rowdata->>'schema_rid'
      AND lower(t.during) <@ s.during
      AND s.rowdata->>'schema_name' != '_ermrest'
)
LIMIT 1
""")
        found_table_rid = False
        for row in cur:
            found_table_rid = True

        # make sure table is known in model history
        if not found_table_rid:
            raise exception.rest.NotFound(f'History table with RID={self.table_rid}')

        # and we actually have a backing history table
        tname = f"t{self.table_rid}"
        if not table_exists(cur, '_ermrest_history', tname):
            raise exception.rest.NotFound(f'History table with RID={self.table_rid}')

        return tname

    def _check_crid(self, cur, crid, require_single_type=True):
        # find column rid for table (we've already validated table rid)
        # and get longitudinal typing info
        cur.execute(f"""
SELECT DISTINCT
  c.rowdata->>'column_name' AS column_name,
  t1.type_name,
  t2.type_name AS base_type_name
FROM _ermrest_history.known_columns c
JOIN LATERAL (
  -- t0 is the original type which may be a domain/array/base type
  SELECT
    t0."RID",
    t0.during,
    t0.rowdata->>'domain_element_type_rid' AS domain_element_type_rid
  FROM _ermrest_history.known_types t0
  WHERE t0."RID" = c.rowdata->>'type_rid'
    AND t0.during && c.during
) t0 ON true
JOIN LATERAL (
  -- t1 strips the t0 domain type wrapper (if any)
  SELECT
    t1."RID",
    t1.during,
    t1.rowdata->>'type_name' AS type_name,
    t1.rowdata->>'domain_element_type_rid' AS domain_element_type_rid,
    t1.rowdata->>'array_element_type_rid' AS array_element_type_rid
  FROM _ermrest_history.known_types t1
  WHERE t1."RID" = COALESCE(t0.domain_element_type_rid, t0."RID")
    AND t1.during && t0.during
) t1 ON true
LEFT JOIN LATERAL (
  -- t2 is the base type of t1 iff t1 is an array type
  SELECT
    t2."RID",
    t2.during,
    t2.rowdata->>'type_name' AS type_name,
    t2.rowdata->>'domain_element_type_rid' AS domain_element_type_rid,
    t2.rowdata->>'array_element_type_rid' AS array_element_type_rid
  FROM _ermrest_history.known_types t2
  WHERE t2."RID" = t1.array_element_type_rid
    AND t2.during && t1.during
) t2 ON true
WHERE c."RID" = {sql_literal(crid)}
  AND c.rowdata->>'table_rid' = {sql_literal(self.table_rid)}
""")
        type_info = list(cur)

        if not type_info:
            raise exception.rest.Conflict(f'Unknown column RID={crid} on history table RID={self.table_rid}')

        if require_single_type:
            if len(type_info) > 1:
                raise exception.rest.Conflict(f'Ambiguous type for column RID={crid} on history table RID={self.table_rid}')
            return type_info[0]
        else:
            return type_info

    def GET_body(self, conn, cur):
        self.enforce_right('owner')
        tname = self._check_trid(cur)
        results = list(enumerate_indexes(cur, '_ermrest_history', tname, self.index_name))

        if self.index_name is not None:
            if not results:
                raise exception.rest.NotFound(f'Index {sql_identifier(self.index_name)} on history table with RID={self.table_rid}.')
            assert len(results) == 1, f"oops: len({results}) != 1 for {self.index_name}"
            return self.row_to_dict(results[0])
        else:
            return [ self.row_to_dict(row) for row in results ]

    def GET(self, uri):
        def post_commit(handler, resource):
            return _post_commit_json(handler, [resource, resource])
        return _GET(self, self.GET_body, post_commit)

    def PUT_body(self, conn, cur, idxdoc):
        assert self.index_name is not None
        self.enforce_right("owner")
        tname = self._check_trid(cur)

        # check for conflicting use of index_name
        for row in enumerate_indexes(cur, '_ermrest_history', None, self.index_name):
            schemaname, tablename, indexname, primary, unique, exclusion, sqldef = row
            if tablename != tname:
                raise exception.rest.Conflict(f"Index name {self.index_name} in use on a different history table.")
            else:
                resource = self.row_to_dict(row)
                self._check_conflicts(resource, "replacement")

        # validate input idxdoc...
        if not isinstance(idxdoc, dict):
            raise exception.BadData('index creation input must be a JSON object')

        require_mutual_exclusive = {'btree', 'trgm', 'gin_array'}
        index_types = set(idxdoc.keys()).intersection(require_mutual_exclusive)
        if len(index_types) != 1:
            raise exception.BadData(f'index creation input must specify exactly one of {"/".join(require_mutual_exclusive)}')

        index_type = index_types.pop()
        index_want = idxdoc[index_type]

        crid_typeinfo = {}

        if isinstance(index_want, list):
            if not len(index_want) > 0:
                raise exception.BadData(f'index creation field not understood {index_type}={index_want}')

            if not all([ isinstance(e, str) for e in index_want ]):
                raise exception.BadData(f'index creation field not understood {index_type}={index_want}')

            for crid in index_want[1:]:
                crid_typeinfo[crid] = self._check_crid(cur, crid, require_single_type=True)

            base_crid = index_want[0]
        elif isinstance(index_want, str):
            base_crid = index_want
        else:
            raise exception.BadData(f"index creation field not understood {index_type}={index_want}")

        crid_typeinfo[base_crid] = self._check_crid(cur, base_crid, require_single_type=True)

        def basic_store_type(type_name):
            return {
                'serial2': 'int2',
                'serial4': 'int4',
                'serial8': 'int8',
            }.get(type_name, type_name)

        def is_array(crid):
            column_name, type_name, elem_type_name = crid_typeinfo[crid]
            return elem_type_name is not None

        def is_indexable(crid):
            column_name, type_name, elem_type_name = crid_typeinfo[crid]
            if elem_type_name is not None:
                elem_type_name = basic_store_type(type_name)
                return elem_type_name != 'json'
            else:
                type_name = basic_store_type(type_name)
                return type_name != 'json'

        def history_projection(crid, cast=True):
            # this type info already collapses domain types to underlying types
            column_name, type_name, elem_type_name = crid_typeinfo[crid]
            type_name = basic_store_type(type_name)

            if elem_type_name is not None:
                # use type-specific IMMUTABLE wrapper functions
                elem_type_name = basic_store_type(elem_type_name)
                target = {
                    'text': 'text',
                    'int2': 'int2',
                    'smallint': 'int2',
                    'int4': 'int4',
                    'integer': 'int4',
                    'int8': 'int8',
                    'bigint': 'int8',
                    'float4': 'float4',
                    'real': 'float4',
                    'float8': 'float8',
                    'double precision': 'float8',
                    'jsonb': 'jsonb',
                    'json': 'json',
                    'timestamp with time zone': 'timestamptz',
                }.get(elem_type_name)
                if target is None:
                    raise exception.rest.Conflict(f"History column {crid} has unsupported type: array of {elem_type_name}")
                return f"_ermrest.history_{target}_arr(rowdata->{sql_literal(crid)})"
            else:
                # scalar column
                if column_name in {'RID', 'RMB'}:
                    return sql_identifier(column_name)
                elif column_name == 'RMT':
                    return f"(lower(during))"
                else:
                    op = '->' if type_name == 'jsonb' else '->>'
                    expr = f"rowdata{op}{sql_literal(crid)}"
                    if not cast:
                        return f"({expr})"
                    elif type_name in {'timestamptz', 'timestamp with time zone'}:
                        return f"(_ermrest.history_timestamptz({expr}))"
                    else:
                        return f"(({expr})::{type_name})"

        sql_parts = [
            f"DROP INDEX IF EXISTS _ermrest_history.{sql_identifier(self.index_name)};",
            f"CREATE INDEX {sql_identifier(self.index_name)} ON _ermrest_history.{sql_identifier(tname)}",
            "USING btree (" if index_type == 'btree' else "USING GIN ("
        ]

        if index_type == 'trgm':
            if not isinstance(index_want, str):
                raise exception.BadData(f"Invalid compound index {index_type}={index_want}")
            # everything gets cast to text
            sql_parts.append(f"_ermrest.astext({history_projection(base_crid, cast=False)}) gin_trgm_ops")
        elif index_type == 'gin_array':
            if not isinstance(index_want, str):
                raise exception.BadData(f"Invalid compound index {index_type}={index_want}")
            if not is_array(base_crid) or not is_indexable(base_crid):
                raise exception.rest.Conflict(f"Conflicting column type for index {index_type}={index_want}")
            sql_parts.append(f"{history_projection(base_crid)} array_ops")
        elif index_type == 'btree':
            if base_crid == index_want:
                index_want = [ base_crid ]

            def btree_col(crid):
                if not is_indexable(crid):
                    raise exception.rest.Conflict(f"Conflicting column type for index {index_type}=...{crid}...")
                return history_projection(crid)

            sql_parts.append(', '.join([ btree_col(crid) for crid in index_want]))
        else:
            raise exception.BadData(f"Invalid index {index_type}={index_want}")

        sql_parts.append(");")
        sql_parts.append("SELECT _ermrest.model_version_bump();")

        sql = "\n".join(sql_parts)
        cur.execute(sql)
        return self.row_to_dict(index_exists_on_table(cur, '_ermrest_history', tname, self.index_name))

    def PUT(self, uri):
        def post_commit(handler, resource):
            return _post_commit_json(handler, [resource, resource])
        return _MODIFY_with_json_input(self, self.PUT_body, post_commit)

    def DELETE_body(self, conn, cur):
        if self.index_name is None:
            raise exception.rest.NoMethod('DELETE requires a specific index-name')

        resource = self.GET_body(conn, cur)
        self._check_conflicts(resource, "deletion")
        drop_index(cur, '_ermrest_history', self.index_name)
        return ''

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)
