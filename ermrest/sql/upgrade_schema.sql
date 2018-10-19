
-- 
-- Copyright 2012-2018 University of Southern California
-- 
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
-- 
--    http://www.apache.org/licenses/LICENSE-2.0
-- 
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.
--

-- help transition a legacy catalog to current schema
DO $upgrade$
<< upgrade_schema >>
BEGIN
-- NOTE, we don't indent this block so editing below is easier...

-- heal any newly created data version tracking
INSERT INTO _ermrest.table_last_modified (table_rid, ts)
SELECT t."RID", now() FROM _ermrest.known_tables t WHERE t.table_kind = 'r'
ON CONFLICT (table_rid) DO NOTHING;

-- ETL legacy _ermrest schema histories as if we always had latest definitions
IF _ermrest.table_exists('_ermrest_history', 'known_catalog_acls') THEN
  WITH orig AS (
    DELETE FROM _ermrest_history.known_catalogs
    RETURNING *
  ), timepoints("RID", ts) AS (
    SELECT "RID", lower(during) FROM orig
    UNION SELECT '0', upper(during) FROM orig
    UNION SELECT '0', lower(during) FROM _ermrest_history.known_catalog_acls
    UNION SELECT '0', upper(during) FROM _ermrest_history.known_catalog_acls
    UNION SELECT '0', lower(during) FROM _ermrest_history.known_catalog_annotations
    UNION SELECT '0', upper(during) FROM _ermrest_history.known_catalog_annotations
  ), subranges("RID", during) AS (
    SELECT "RID", tstzrange(ts, lead(ts, 1) OVER (PARTITION BY "RID" ORDER BY ts NULLS LAST), '[)')
    FROM timepoints
    WHERE ts IS NOT NULL
  ), acls("RID", during, acls) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'acl', (a.rowdata)->'members'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_catalog_acls a ON (s.during && a.during)
    GROUP BY s."RID", s.during
  ), annotations("RID", during, annotations) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'annotation_uri', (a.rowdata)->'annotation_value'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_catalog_annotations a ON (s.during && a.during)
    GROUP BY s."RID", s.during
  ) INSERT INTO _ermrest_history.known_catalogs ("RID", during, "RMB", rowdata)
  SELECT
    '0',
    s.during,
    NULL,
    jsonb_build_object(
      'RCT', (SELECT min(lower(during)) FROM subranges),
      'acls', COALESCE(a1.acls, '{}'),
      'annotations', COALESCE(a3.annotations, '{}')
    )
  FROM subranges s
  LEFT OUTER JOIN acls a1 ON (s.during = a1.during)
  LEFT OUTER JOIN annotations a3 ON (s.during = a3.during);
  
  DROP TABLE _ermrest_history.known_catalog_acls;
  DROP TABLE _ermrest_history.known_catalog_annotations;
END IF;

IF _ermrest.table_exists('_ermrest_history', 'known_schema_acls') THEN
  WITH orig AS (
    DELETE FROM _ermrest_history.known_schemas
    RETURNING *
  ), timepoints("RID", ts) AS (
    SELECT "RID", lower(during) FROM orig
    UNION SELECT "RID", upper(during) FROM orig
    UNION SELECT rowdata->>'schema_rid', lower(during) FROM _ermrest_history.known_schema_acls
    UNION SELECT rowdata->>'schema_rid', upper(during) FROM _ermrest_history.known_schema_acls
    UNION SELECT rowdata->>'schema_rid', lower(during) FROM _ermrest_history.known_schema_annotations
    UNION SELECT rowdata->>'schema_rid', upper(during) FROM _ermrest_history.known_schema_annotations
  ), subranges("RID", during) AS (
    SELECT "RID", tstzrange(ts, lead(ts, 1) OVER (PARTITION BY "RID" ORDER BY ts NULLS LAST), '[)')
    FROM timepoints
    WHERE ts IS NOT NULL
  ), rebuilt("RID", during, "RMB", rowdata) AS (
    SELECT
      s."RID",
      s.during,
      a."RMB",
      a.rowdata
    FROM subranges s
    JOIN orig a ON (s."RID" = a."RID" AND s.during && a.during)
  ), acls("RID", during, acls) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'acl', (a.rowdata)->'members'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_schema_acls a ON (s."RID" = (a.rowdata)->>'schema_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), annotations("RID", during, annotations) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'annotation_uri', (a.rowdata)->'annotation_value'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_schema_annotations a ON (s."RID" = (a.rowdata)->>'schema_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ) INSERT INTO _ermrest_history.known_schemas ("RID", during, "RMB", rowdata)
  SELECT
    s."RID",
    s.during,
    s."RMB",
    jsonb_set(
      jsonb_set(
        s.rowdata,
        ARRAY['acls'],
        COALESCE(a1.acls, (s.rowdata)->'acls', '{}')
      ),
      ARRAY['annotations'],
      COALESCE(a3.annotations, (s.rowdata)->'annotations', '{}')
    )
  FROM rebuilt s
  LEFT OUTER JOIN acls a1 ON (s."RID" = a1."RID" AND s.during = a1.during)
  LEFT OUTER JOIN annotations a3 ON (s."RID" = a3."RID" AND s.during = a3.during);
  
  DROP TABLE _ermrest_history.known_schema_acls;
  DROP TABLE _ermrest_history.known_schema_annotations;
END IF;

IF _ermrest.table_exists('_ermrest_history', 'known_table_acls') THEN
  WITH orig AS (
    DELETE FROM _ermrest_history.known_tables
    RETURNING *
  ), timepoints("RID", ts) AS (
    SELECT "RID", lower(during) FROM orig
    UNION SELECT "RID", upper(during) FROM orig
    UNION SELECT rowdata->>'table_rid', lower(during) FROM _ermrest_history.known_table_acls
    UNION SELECT rowdata->>'table_rid', upper(during) FROM _ermrest_history.known_table_acls
    UNION SELECT rowdata->>'table_rid', lower(during) FROM _ermrest_history.known_table_dynacls
    UNION SELECT rowdata->>'table_rid', upper(during) FROM _ermrest_history.known_table_dynacls
    UNION SELECT rowdata->>'table_rid', lower(during) FROM _ermrest_history.known_table_annotations
    UNION SELECT rowdata->>'table_rid', upper(during) FROM _ermrest_history.known_table_annotations
  ), subranges("RID", during) AS (
    SELECT "RID", tstzrange(ts, lead(ts, 1) OVER (PARTITION BY "RID" ORDER BY ts NULLS LAST), '[)')
    FROM timepoints
    WHERE ts IS NOT NULL
  ), rebuilt("RID", during, "RMB", rowdata) AS (
    SELECT
      s."RID",
      s.during,
      a."RMB",
      a.rowdata
    FROM subranges s
    JOIN orig a ON (s."RID" = a."RID" AND s.during && a.during)
  ), acls("RID", during, acls) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'acl', (a.rowdata)->'members'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_table_acls a ON (s."RID" = (a.rowdata)->>'table_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), acl_bindings("RID", during, acl_bindings) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'binding_name', (a.rowdata)->'binding'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_table_dynacls a ON (s."RID" = (a.rowdata)->>'table_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), annotations("RID", during, annotations) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'annotation_uri', (a.rowdata)->'annotation_value'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_table_annotations a ON (s."RID" = (a.rowdata)->>'table_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ) INSERT INTO _ermrest_history.known_tables ("RID", during, "RMB", rowdata)
  SELECT
    s."RID",
    s.during,
    s."RMB",
    jsonb_set(
      jsonb_set(
        jsonb_set(
	  s.rowdata,
	  ARRAY['acls'],
	  COALESCE(a1.acls, (s.rowdata)->'acls', '{}')
	),
	ARRAY['acl_bindings'],
	COALESCE(a2.acl_bindings, (s.rowdata)->'acl_bindings', '{}')
      ),
      ARRAY['annotations'],
      COALESCE(a3.annotations, (s.rowdata)->'annotations', '{}')
    )
  FROM rebuilt s
  LEFT OUTER JOIN acls a1 ON (s."RID" = a1."RID" AND s.during = a1.during)
  LEFT OUTER JOIN acl_bindings a2 ON (s."RID" = a2."RID" AND s.during = a2.during)
  LEFT OUTER JOIN annotations a3 ON (s."RID" = a3."RID" AND s.during = a3.during);
  
  DROP TABLE _ermrest_history.known_table_acls;
  DROP TABLE _ermrest_history.known_table_dynacls;
  DROP TABLE _ermrest_history.known_table_annotations;
END IF;

IF _ermrest.table_exists('_ermrest_history', 'known_column_acls') THEN
  WITH orig AS (
    DELETE FROM _ermrest_history.known_columns
    RETURNING *
  ), timepoints("RID", ts) AS (
    SELECT "RID", lower(during) FROM orig
    UNION SELECT "RID", upper(during) FROM orig
    UNION SELECT rowdata->>'column_rid', lower(during) FROM _ermrest_history.known_column_acls
    UNION SELECT rowdata->>'column_rid', upper(during) FROM _ermrest_history.known_column_acls
    UNION SELECT rowdata->>'column_rid', lower(during) FROM _ermrest_history.known_column_dynacls
    UNION SELECT rowdata->>'column_rid', upper(during) FROM _ermrest_history.known_column_dynacls
    UNION SELECT rowdata->>'column_rid', lower(during) FROM _ermrest_history.known_column_annotations
    UNION SELECT rowdata->>'column_rid', upper(during) FROM _ermrest_history.known_column_annotations
  ), subranges("RID", during) AS (
    SELECT "RID", tstzrange(ts, lead(ts, 1) OVER (PARTITION BY "RID" ORDER BY ts NULLS LAST), '[)')
    FROM timepoints
    WHERE ts IS NOT NULL
  ), rebuilt("RID", during, "RMB", rowdata) AS (
    SELECT
      s."RID",
      s.during,
      a."RMB",
      a.rowdata
    FROM subranges s
    JOIN orig a ON (s."RID" = a."RID" AND s.during && a.during)
  ), acls("RID", during, acls) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'acl', (a.rowdata)->'members'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_column_acls a ON (s."RID" = (a.rowdata)->>'column_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), acl_bindings("RID", during, acl_bindings) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'binding_name', (a.rowdata)->'binding'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_column_dynacls a ON (s."RID" = (a.rowdata)->>'column_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), annotations("RID", during, annotations) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'annotation_uri', (a.rowdata)->'annotation_value'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_column_annotations a ON (s."RID" = (a.rowdata)->>'column_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ) INSERT INTO _ermrest_history.known_columns ("RID", during, "RMB", rowdata)
  SELECT
    s."RID",
    s.during,
    s."RMB",
    jsonb_set(
      jsonb_set(
        jsonb_set(
	  s.rowdata,
	  ARRAY['acls'],
	  COALESCE(a1.acls, (s.rowdata)->'acls', '{}')
	),
	ARRAY['acl_bindings'],
	COALESCE(a2.acl_bindings, (s.rowdata)->'acl_bindings', '{}')
      ),
      ARRAY['annotations'],
      COALESCE(a3.annotations, (s.rowdata)->'annotations', '{}')
    )
  FROM rebuilt s
  LEFT OUTER JOIN acls a1 ON (s."RID" = a1."RID" AND s.during = a1.during)
  LEFT OUTER JOIN acl_bindings a2 ON (s."RID" = a2."RID" AND s.during = a2.during)
  LEFT OUTER JOIN annotations a3 ON (s."RID" = a3."RID" AND s.during = a3.during);
  
  DROP TABLE _ermrest_history.known_column_acls;
  DROP TABLE _ermrest_history.known_column_dynacls;
  DROP TABLE _ermrest_history.known_column_annotations;
END IF;

IF _ermrest.table_exists('_ermrest_history', 'known_key_annotations') THEN
  WITH orig AS (
    DELETE FROM _ermrest_history.known_keys
    RETURNING *
  ), timepoints("RID", ts) AS (
    SELECT "RID", lower(during) FROM orig
    UNION SELECT "RID", upper(during) FROM orig
    UNION SELECT rowdata->>'key_rid', lower(during) FROM _ermrest_history.known_key_annotations
    UNION SELECT rowdata->>'key_rid', upper(during) FROM _ermrest_history.known_key_annotations
    UNION SELECT rowdata->>'key_rid', lower(during) FROM _ermrest_history.known_key_columns
    UNION SELECT rowdata->>'key_rid', upper(during) FROM _ermrest_history.known_key_columns
  ), subranges("RID", during) AS (
    SELECT "RID", tstzrange(ts, lead(ts, 1) OVER (PARTITION BY "RID" ORDER BY ts NULLS LAST), '[)')
    FROM timepoints
    WHERE ts IS NOT NULL
  ), rebuilt("RID", during, "RMB", rowdata) AS (
    SELECT
      s."RID",
      s.during,
      a."RMB",
      jsonb_set(
        a.rowdata,
	ARRAY['column_rids'],
	COALESCE(kc.column_rids, (a.rowdata)->'column_rids', '{}'::jsonb)
      )
    FROM subranges s
    JOIN orig a ON (s."RID" = a."RID" AND s.during && a.during)
    LEFT JOIN LATERAL (
      SELECT
        (kc.rowdata)->>'key_rid',
	s.during,
	jsonb_object_agg((kc.rowdata)->>'column_rid', 'null'::jsonb)
      FROM _ermrest_history.known_key_columns kc
      WHERE s."RID" = (kc.rowdata)->>'key_rid' AND kc.during && s.during
      GROUP BY (kc.rowdata)->>'key_rid', s.during
    ) kc("RID", during, column_rids) ON (True)
  ), annotations("RID", during, annotations) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'annotation_uri', (a.rowdata)->'annotation_value'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_key_annotations a ON (s."RID" = (a.rowdata)->>'key_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ) INSERT INTO _ermrest_history.known_keys ("RID", during, "RMB", rowdata)
  SELECT
    s."RID",
    s.during,
    s."RMB",
    jsonb_set(
      s.rowdata,
      ARRAY['annotations'],
      COALESCE(a3.annotations, (s.rowdata)->'annotations', '{}')
    )
  FROM rebuilt s
  LEFT OUTER JOIN annotations a3 ON (s."RID" = a3."RID" AND s.during = a3.during);
  
  DROP TABLE _ermrest_history.known_key_annotations;
  DROP TABLE _ermrest_history.known_key_columns;
END IF;

IF _ermrest.table_exists('_ermrest_history', 'known_pseudo_key_annotations') THEN
  WITH orig AS (
    DELETE FROM _ermrest_history.known_pseudo_keys
    RETURNING *
  ), timepoints("RID", ts) AS (
    SELECT "RID", lower(during) FROM orig
    UNION SELECT "RID", upper(during) FROM orig
    UNION SELECT rowdata->>'key_rid', lower(during) FROM _ermrest_history.known_pseudo_key_annotations
    UNION SELECT rowdata->>'key_rid', upper(during) FROM _ermrest_history.known_pseudo_key_annotations
    UNION SELECT rowdata->>'key_rid', lower(during) FROM _ermrest_history.known_pseudo_key_columns
    UNION SELECT rowdata->>'key_rid', upper(during) FROM _ermrest_history.known_pseudo_key_columns
  ), subranges("RID", during) AS (
    SELECT "RID", tstzrange(ts, lead(ts, 1) OVER (PARTITION BY "RID" ORDER BY ts NULLS LAST), '[)')
    FROM timepoints
    WHERE ts IS NOT NULL
  ), rebuilt("RID", during, "RMB", rowdata) AS (
    SELECT
      s."RID",
      s.during,
      a."RMB",
      jsonb_set(
        a.rowdata,
	ARRAY['column_rids'],
	COALESCE(kc.column_rids, (a.rowdata)->'column_rids', '{}'::jsonb)
      )
    FROM subranges s
    JOIN orig a ON (s."RID" = a."RID" AND s.during && a.during)
    LEFT JOIN LATERAL (
      SELECT
        (kc.rowdata)->>'key_rid',
	s.during,
	jsonb_object_agg((kc.rowdata)->>'column_rid', 'null'::jsonb)
      FROM _ermrest_history.known_pseudo_key_columns kc
      WHERE s."RID" = (kc.rowdata)->>'key_rid' AND kc.during && s.during
      GROUP BY (kc.rowdata)->>'key_rid', s.during
    ) kc("RID", during, column_rids) ON (True)
  ), annotations("RID", during, annotations) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'annotation_uri', (a.rowdata)->'annotation_value'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_pseudo_key_annotations a ON (s."RID" = (a.rowdata)->>'key_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ) INSERT INTO _ermrest_history.known_pseudo_keys ("RID", during, "RMB", rowdata)
  SELECT
    s."RID",
    s.during,
    s."RMB",
    jsonb_set(
      s.rowdata,
      ARRAY['annotations'],
      COALESCE(a3.annotations, (s.rowdata)->'annotations', '{}')
    )
  FROM rebuilt s
  LEFT OUTER JOIN annotations a3 ON (s."RID" = a3."RID" AND s.during = a3.during);
  
  DROP TABLE _ermrest_history.known_pseudo_key_annotations;
  DROP TABLE _ermrest_history.known_pseudo_key_columns;
END IF;

IF _ermrest.table_exists('_ermrest_history', 'known_fkey_acls') THEN
  WITH orig AS (
    DELETE FROM _ermrest_history.known_fkeys
    RETURNING *
  ), timepoints("RID", ts) AS (
    SELECT "RID", lower(during) FROM orig
    UNION SELECT "RID", upper(during) FROM orig
    UNION SELECT rowdata->>'fkey_rid', lower(during) FROM _ermrest_history.known_fkey_acls
    UNION SELECT rowdata->>'fkey_rid', upper(during) FROM _ermrest_history.known_fkey_acls
    UNION SELECT rowdata->>'fkey_rid', lower(during) FROM _ermrest_history.known_fkey_dynacls
    UNION SELECT rowdata->>'fkey_rid', upper(during) FROM _ermrest_history.known_fkey_dynacls
    UNION SELECT rowdata->>'fkey_rid', lower(during) FROM _ermrest_history.known_fkey_annotations
    UNION SELECT rowdata->>'fkey_rid', upper(during) FROM _ermrest_history.known_fkey_annotations
    UNION SELECT rowdata->>'fkey_rid', lower(during) FROM _ermrest_history.known_fkey_columns
    UNION SELECT rowdata->>'fkey_rid', upper(during) FROM _ermrest_history.known_fkey_columns
  ), subranges("RID", during) AS (
    SELECT "RID", tstzrange(ts, lead(ts, 1) OVER (PARTITION BY "RID" ORDER BY ts NULLS LAST), '[)')
    FROM timepoints
    WHERE ts IS NOT NULL
  ), rebuilt("RID", during, "RMB", rowdata) AS (
    SELECT
      s."RID",
      s.during,
      a."RMB",
      jsonb_set(
        a.rowdata,
	ARRAY['fkc_pkc_rids'],
	COALESCE(fkc.fkc_pkc_rids, (a.rowdata)->'fkc_pkc_rids', '{}'::jsonb)
      )
    FROM subranges s
    JOIN orig a ON (s."RID" = a."RID" AND s.during && a.during)
    LEFT JOIN LATERAL (
      SELECT
        (fkc.rowdata)->>'fkey_rid',
	s.during,
	jsonb_object_agg((fkc.rowdata)->>'fk_column_rid', (fkc.rowdata)->>'pk_column_rid')
      FROM _ermrest_history.known_fkey_columns fkc
      WHERE s."RID" = (fkc.rowdata)->>'fkey_rid' AND s.during && fkc.during
      GROUP BY (fkc.rowdata)->>'fkey_rid', s.during
    ) fkc ("RID", during, fkc_pkc_rids) ON (True)
  ), acls("RID", during, acls) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'acl', (a.rowdata)->'members'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_fkey_acls a ON (s."RID" = (a.rowdata)->>'fkey_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), acl_bindings("RID", during, acl_bindings) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'binding_name', (a.rowdata)->'binding'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_fkey_dynacls a ON (s."RID" = (a.rowdata)->>'fkey_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), annotations("RID", during, annotations) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'annotation_uri', (a.rowdata)->'annotation_value'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_fkey_annotations a ON (s."RID" = (a.rowdata)->>'fkey_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ) INSERT INTO _ermrest_history.known_fkeys ("RID", during, "RMB", rowdata)
  SELECT
    s."RID",
    s.during,
    s."RMB",
    jsonb_set(
      jsonb_set(
        jsonb_set(
	  s.rowdata,
	  ARRAY['acls'],
	  COALESCE(a1.acls, (s.rowdata)->'acls', '{}')
	),
	ARRAY['acl_bindings'],
	COALESCE(a2.acl_bindings, (s.rowdata)->'acl_bindings', '{}')
      ),
      ARRAY['annotations'],
      COALESCE(a3.annotations, (s.rowdata)->'annotations', '{}')
    )
  FROM rebuilt s
  LEFT OUTER JOIN acls a1 ON (s."RID" = a1."RID" AND s.during = a1.during)
  LEFT OUTER JOIN acl_bindings a2 ON (s."RID" = a2."RID" AND s.during = a2.during)
  LEFT OUTER JOIN annotations a3 ON (s."RID" = a3."RID" AND s.during = a3.during);
  
  DROP TABLE _ermrest_history.known_fkey_acls;
  DROP TABLE _ermrest_history.known_fkey_dynacls;
  DROP TABLE _ermrest_history.known_fkey_annotations;
  DROP TABLE _ermrest_history.known_fkey_columns;
END IF;

IF _ermrest.table_exists('_ermrest_history', 'known_pseudo_fkey_acls') THEN
  WITH orig AS (
    DELETE FROM _ermrest_history.known_pseudo_fkeys
    RETURNING *
  ), timepoints("RID", ts) AS (
    SELECT "RID", lower(during) FROM orig
    UNION SELECT "RID", upper(during) FROM orig
    UNION SELECT rowdata->>'fkey_rid', lower(during) FROM _ermrest_history.known_pseudo_fkey_acls
    UNION SELECT rowdata->>'fkey_rid', upper(during) FROM _ermrest_history.known_pseudo_fkey_acls
    UNION SELECT rowdata->>'fkey_rid', lower(during) FROM _ermrest_history.known_pseudo_fkey_dynacls
    UNION SELECT rowdata->>'fkey_rid', upper(during) FROM _ermrest_history.known_pseudo_fkey_dynacls
    UNION SELECT rowdata->>'fkey_rid', lower(during) FROM _ermrest_history.known_pseudo_fkey_annotations
    UNION SELECT rowdata->>'fkey_rid', upper(during) FROM _ermrest_history.known_pseudo_fkey_annotations
    UNION SELECT rowdata->>'fkey_rid', lower(during) FROM _ermrest_history.known_pseudo_fkey_columns
    UNION SELECT rowdata->>'fkey_rid', upper(during) FROM _ermrest_history.known_pseudo_fkey_columns
  ), subranges("RID", during) AS (
    SELECT "RID", tstzrange(ts, lead(ts, 1) OVER (PARTITION BY "RID" ORDER BY ts NULLS LAST), '[)')
    FROM timepoints
    WHERE ts IS NOT NULL
  ), rebuilt("RID", during, "RMB", rowdata) AS (
    SELECT
      s."RID",
      s.during,
      a."RMB",
      jsonb_set(
        a.rowdata,
	ARRAY['fkc_pkc_rids'],
	COALESCE(fkc.fkc_pkc_rids, (a.rowdata)->'fkc_pkc_rids', '{}'::jsonb)
      )
    FROM subranges s
    JOIN orig a ON (s."RID" = a."RID" AND s.during && a.during)
    LEFT JOIN LATERAL (
      SELECT
        (fkc.rowdata)->>'fkey_rid',
	s.during,
	jsonb_object_agg((fkc.rowdata)->>'fk_column_rid', (fkc.rowdata)->>'pk_column_rid')
      FROM _ermrest_history.known_pseudo_fkey_columns fkc
      WHERE s."RID" = (fkc.rowdata)->>'fkey_rid' AND s.during && fkc.during
      GROUP BY (fkc.rowdata)->>'fkey_rid', s.during
    ) fkc ("RID", during, fkc_pkc_rids) ON (True)
  ), acls("RID", during, acls) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'acl', (a.rowdata)->'members'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_pseudo_fkey_acls a ON (s."RID" = (a.rowdata)->>'fkey_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), acl_bindings("RID", during, acl_bindings) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'binding_name', (a.rowdata)->'binding'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_pseudo_fkey_dynacls a ON (s."RID" = (a.rowdata)->>'fkey_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ), annotations("RID", during, annotations) AS (
    SELECT
      s."RID",
      s.during,
      COALESCE(jsonb_object_agg((a.rowdata)->>'annotation_uri', (a.rowdata)->'annotation_value'), '{}'::jsonb)
    FROM subranges s
    JOIN _ermrest_history.known_pseudo_fkey_annotations a ON (s."RID" = (a.rowdata)->>'fkey_rid' AND s.during && a.during)
    GROUP BY s."RID", s.during
  ) INSERT INTO _ermrest_history.known_pseudo_fkeys ("RID", during, "RMB", rowdata)
  SELECT
    s."RID",
    s.during,
    s."RMB",
    jsonb_set(
      jsonb_set(
        jsonb_set(
	  s.rowdata,
	  ARRAY['acls'],
	  COALESCE(a1.acls, (s.rowdata)->'acls', '{}')
	),
	ARRAY['acl_bindings'],
	COALESCE(a2.acl_bindings, (s.rowdata)->'acl_bindings', '{}')
      ),
      ARRAY['annotations'],
      COALESCE(a3.annotations, (s.rowdata)->'annotations', '{}')
    )
  FROM rebuilt s
  LEFT OUTER JOIN acls a1 ON (s."RID" = a1."RID" AND s.during = a1.during)
  LEFT OUTER JOIN acl_bindings a2 ON (s."RID" = a2."RID" AND s.during = a2.during)
  LEFT OUTER JOIN annotations a3 ON (s."RID" = a3."RID" AND s.during = a3.during);
  
  DROP TABLE _ermrest_history.known_pseudo_fkey_acls;
  DROP TABLE _ermrest_history.known_pseudo_fkey_dynacls;
  DROP TABLE _ermrest_history.known_pseudo_fkey_annotations;
  DROP TABLE _ermrest_history.known_pseudo_fkey_columns;
END IF;

RAISE NOTICE 'Completed translating any legacy schema to current ERMrest schema.';

END upgrade_schema;
$upgrade$ LANGUAGE plpgsql;

