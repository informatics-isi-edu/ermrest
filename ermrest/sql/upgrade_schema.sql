
-- 
-- Copyright 2012-2017 University of Southern California
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

-- clean up legacy tables
DROP TABLE IF EXISTS _ermrest.model_version;
DROP TABLE IF EXISTS _ermrest.data_version;

-- clean up legacy functions we used to define
DROP FUNCTION IF EXISTS _ermrest.ts_iso8601(anynonarray) CASCADE;
DROP FUNCTION IF EXISTS _ermrest.ts_iso8601(anyarray) CASCADE;
DROP FUNCTION IF EXISTS _ermrest.ts_iso8601(date) CASCADE;
DROP FUNCTION IF EXISTS _ermrest.ts_iso8601(timestamptz) CASCADE;
DROP FUNCTION IF EXISTS _ermrest.ts_iso8601(timestamp) CASCADE;
DROP FUNCTION IF EXISTS _ermrest.ts_iso8601(timetz) CASCADE;
DROP FUNCTION IF EXISTS _ermrest.ts_iso8601(time) CASCADE;

-- convert legacy catalog policy to catalog ACLs
DO $$
BEGIN
  IF (SELECT True
      FROM information_schema.tables
      WHERE table_schema = '_ermrest' AND table_name = 'meta') THEN
    INSERT INTO _ermrest.model_catalog_acl (acl, members)
    SELECT
      CASE
        WHEN key = 'owner' THEN 'owner'
        WHEN key = 'read_user' THEN 'enumerate'
        WHEN key = 'content_read_user' THEN 'select'
        WHEN key = 'content_write_user' THEN 'write'
        WHEN key = 'schema_write_user' THEN 'create'
      END AS key,
      array_agg(value) AS members
    FROM _ermrest.meta
    WHERE key IN ('owner', 'read_user', 'content_read_user', 'content_write_user', 'schema_write_user')
    GROUP BY key;

    DROP TABLE _ermrest.meta;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- heal any newly created data version tracking
INSERT INTO _ermrest.table_last_modified (oid, ts)
SELECT t.oid, now() FROM _ermrest.introspect_tables t WHERE t.table_kind = 'r'
ON CONFLICT (oid) DO NOTHING;

-- port legacy pseudo not-nulls
DO $$
BEGIN
  IF (SELECT True
      FROM information_schema.tables
      WHERE table_schema = '_ermrest' AND table_name = 'model_pseudo_notnull') THEN
    INSERT INTO _ermrest.known_pseudo_notnulls (table_oid, column_num)
    SELECT
      _ermrest.table_oid(schema_name, table_name),
      _ermrest.column_num(_ermrest.table_oid(schema_name, table_name), column_name)
    FROM _ermrest.model_pseudo_notnull;
    DROP TABLE _ermrest.model_pseudo_notnull;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- port legacy pseudo keys
DO $$
BEGIN
  IF (SELECT True
      FROM information_schema.tables
      WHERE table_schema = '_ermrest' AND table_name = 'model_pseudo_key') THEN

    INSERT INTO _ermrest.known_pseudo_keys (constraint_name, table_oid, column_nums, "comment")
    SELECT
      pkc.constraint_name,
      pkc.table_oid,
      array_agg(
        _ermrest.column_num(pkc.table_oid, pkc.column_name)
	ORDER BY c.column_num
      ),
      pkc."comment"
    FROM (
      SELECT
        pk."name" as constraint_name,
	_ermrest.table_oid(schema_name, table_name) AS table_oid,
	unnest(column_names) AS column_name,
	"comment"
      FROM _ermrest.model_pseudo_key pk
    ) pkc
    JOIN _ermrest.known_columns c ON (pkc.table_oid = c.table_oid AND pkc.column_name = c.column_name)
    GROUP BY pkc.table_oid, constraint_name, pkc."comment"
    ;

    DROP TABLE _ermrest.model_pseudo_key;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- port legacy pseudo foreign keys
DO $$
BEGIN
  IF (SELECT True
      FROM information_schema.tables
      WHERE table_schema = '_ermrest' AND table_name = 'model_pseudo_keyref') THEN

    INSERT INTO _ermrest.known_pseudo_fkeys (constraint_name, fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, "comment")
    SELECT
      fkr."name",
      from_oid,
      array_agg(
        c1.column_num
	ORDER BY colmap.from_index
      ),
      to_oid,
      array_agg(
        c2.column_num
	ORDER BY colmap.from_index
      ),
      fkr."comment"
    FROM (
      SELECT
        fkr.*,
	t1.oid AS from_oid,
	t2.oid AS to_oid
      FROM _ermrest.model_pseudo_keyref fkr
      JOIN _ermrest.known_schemas s1 ON (s1.schema_name = fkr.from_schema_name)
      JOIN _ermrest.known_schemas s2 ON (s2.schema_name = fkr.to_schema_name)
      JOIN _ermrest.known_tables  t1 ON (s1.oid = t1.schema_oid AND t1.table_name = fkr.from_table_name)
      JOIN _ermrest.known_tables  t2 ON (s2.oid = t2.schema_oid AND t2.table_name = fkr.to_table_name)
    ) fkr
    JOIN (
      SELECT
        fkr.id,
	fcol.n AS from_name,
	tcol.n AS to_name,
	fcol.i AS from_index
      FROM _ermrest.model_pseudo_keyref AS fkr,
      LATERAL unnest(fkr.from_column_names) WITH ORDINALITY AS fcol(n, i),
      LATERAL unnest(fkr.from_column_names) WITH ORDINALITY AS tcol(n, i)
      WHERE fcol.i = tcol.i
    ) colmap ON (fkr.id = colmap.id)
    JOIN _ermrest.known_columns c1 ON (fkr.from_oid = c1.table_oid AND c1.column_name = colmap.from_name)
    JOIN _ermrest.known_columns c2 ON (fkr.to_oid = c2.table_oid AND c2.column_name = colmap.to_name)
    GROUP BY fkr."name", from_oid, to_oid, fkr."comment"
    ;

    DROP TABLE _ermrest.model_pseudo_keyref;
  END IF;
END;
$$ LANGUAGE plpgsql;
