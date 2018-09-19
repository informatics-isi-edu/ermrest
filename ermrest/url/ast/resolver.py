
#
# Copyright 2018 University of Southern California
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

from .api import Api
from .model import _GET, _post_commit_json
from .history import _encode_ts
from ...util import sql_literal, sql_identifier
from ... import exception

class EntityRidResolver (Api):
    """Represents entity RID

       URL: /ermrest/catalog/N[@rev]/entity_rid/rid

    """
    def __init__(self, catalog, rid):
        super(EntityRidResolver, self).__init__(catalog)
        self._resolve_rid = rid

    def _table_found_or_gone(self, cur, rid, snaptime=None):
        """Return (entity_rid, table_rid, gonetime) or None if not found.

           table_rid is the table where rid was resolved.
           gonetime is None when found or an earlier timestamp when gone.
        """
        cur.execute("""
SELECT
  ve.entity_rid,
  ve.table_rid,
  CASE WHEN ve.during @> %(snaptime)s THEN NULL ELSE upper(ve.during) END
FROM _ermrest_history.visible_entities ve
WHERE (entity_rid = %(rid)s OR entity_rid = _ermrest.urlb32_encode(_ermrest.urlb32_decode(%(rid)s, False)))
  AND (ve.during @> %(snaptime)s OR upper(ve.during) <= %(snaptime)s)
ORDER BY during DESC
LIMIT 1;
""" % {
    'rid': sql_literal(self._resolve_rid),
    'snaptime': '%s::timestamptz' % (sql_literal(snaptime) if snaptime is not None else 'now()'),
}
            )
        for row in cur:
            return row
        return None

    def _last_visible_snaptime(self, cur, table_rid, rid, gonetime=None):
        """Find latest catalog snapshot where rid is visible in table prior to gonetime.

           This is only meaningful when resolving an entity which is gone.
        """
        cur.execute("""
SELECT
  GREATEST(
    (SELECT m.ts
     FROM _ermrest.model_modified m
     WHERE m.ts < upper(h.during)
     ORDER BY m.ts DESC
     LIMIT 1),
    (SELECT m.ts
     FROM _ermrest.table_modified m
     WHERE m.ts < upper(h.during)
     ORDER BY m.ts DESC
     LIMIT 1)
  )
FROM _ermrest_history.%(htable)s h
WHERE h."RID" = %(rid)s
  AND (upper(h.during) <= %(gonetime)s)
ORDER BY h.during DESC
LIMIT 1;
""" % {
    'rid': sql_literal(rid),
    'htable': sql_identifier('t%s' % table_rid),
    'gonetime': '%s::timestamptz' % (sql_literal(gonetime) if gonetime is not None else 'NULL'),
}
        )
        return cur.fetchone()[0]

    def _table_info(self, cur, table_rid, snaptime=None):
        """Find (sname, tname) for table_rid at snaptime."""
        cur.execute("""
SELECT
  (s.rowdata)->>'schema_name',
  (t.rowdata)->>'table_name'
FROM _ermrest_history.known_tables t
JOIN _ermrest_history.known_schemas s ON ((t.rowdata)->>'schema_rid' = s."RID")
WHERE t."RID" = %(table_rid)s
  AND t.during @> %(snaptime)s
  AND s.during @> %(snaptime)s;
""" % {
    'table_rid': sql_literal(table_rid),
    'snaptime': '%s::timestamptz' % (sql_literal(snaptime) if snaptime is not None else 'now()'),
}
        )
        return cur.fetchone()

    def GET_body(self, conn, cur):
        """Resolve RID"""
        # TODO: add rights check here if we decide not to leave this public
        row = self._table_found_or_gone(cur, self._resolve_rid, web.ctx.ermrest_history_snaptime)
        if row is None:
            raise exception.rest.NotFound('entity with RID=%s' % self._resolve_rid)

        entity_rid, table_rid, gone_when = row

        if gone_when is not None:
            last_visible = self._last_visible_snaptime(cur, table_rid, self._resolve_rid, gone_when)
            sname, tname = self._table_info(cur, table_rid, last_visible)
        else:
            sname, tname = self._table_info(cur, table_rid, web.ctx.ermrest_history_snaptime)

        if sname == '_ermrest':
            # for now, we act like model element RIDs are non-resolvable
            web.ctx.ermrest_request_trace(
                'Refusing resolution of model entity %s:%s/RID=%s' % (sname, tname, self._resolve_rid)
            )
            raise exception.rest.NotFound('entity with RID=%s' % self._resolve_rid)

        prejson = {
            'RID': entity_rid,
            'schema_name': sname,
            'table_name': tname,
        }
        if gone_when is not None:
            prejson.update({
                'deleted_at': gone_when.isoformat(' '),
                'last_visible_at': last_visible.isoformat(' '),
                'last_visible_snaptime': _encode_ts(cur, last_visible),
            })

        return prejson

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
