
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
