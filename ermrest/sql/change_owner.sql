
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

-- fix up any legacy object ownership

DO $$
DECLARE
  srow record;
  trow record;
  vrow record;
  seqrow record;
  frow record;
BEGIN
  FOR srow
  IN SELECT nspname
     FROM pg_namespace
     WHERE nspname NOT IN ('pg_toast', 'pg_catalog', 'information_schema')
       AND NOT pg_is_other_temp_schema(oid)
  LOOP
    EXECUTE 'ALTER SCHEMA ' || quote_ident(srow.nspname) || ' OWNER TO ermrest;';

    FOR trow
    IN SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = srow.nspname
      AND table_type = 'BASE TABLE'
    LOOP
      EXECUTE 'ALTER TABLE ' || quote_ident(srow.nspname) || '.' || quote_ident(trow.table_name) || ' OWNER TO ermrest;';
    END LOOP;

    FOR vrow
    IN SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = srow.nspname
      AND table_type = 'VIEW'
    LOOP
      EXECUTE 'ALTER VIEW ' || quote_ident(srow.nspname) || '.' || quote_ident(vrow.table_name) || ' OWNER TO ermrest;';
    END LOOP;

    FOR seqrow
    IN SELECT sequence_name
    FROM information_schema.sequences
    WHERE sequence_schema = srow.nspname
    LOOP
      EXECUTE 'ALTER SEQUENCE ' || quote_ident(srow.nspname) || '.' || quote_ident(seqrow.sequence_name) || ' OWNER TO ermrest;';
    END LOOP;

    FOR frow
    IN SELECT
      r.routine_schema,
      r.routine_name,
      p.argtypes
    FROM information_schema.routines r
    LEFT OUTER JOIN (
      SELECT
        specific_schema,
	specific_name,
	array_agg(parameter_mode || ' ' || udt_name ORDER BY ordinal_position) AS argtypes
      FROM information_schema.parameters p
      GROUP BY specific_schema, specific_name
    ) p ON (r.specific_schema = p.specific_schema AND r.specific_name = p.specific_name)
    WHERE r.routine_type = 'FUNCTION'
      AND r.routine_schema IN ('_ermrest', '_ermrest_history')
    LOOP
      EXECUTE 'ALTER FUNCTION '
        || quote_ident(frow.routine_schema) || '.' || quote_ident(frow.routine_name)
	|| '(' || array_to_string(COALESCE(frow.argtypes, ARRAY[]::text[]), ', ') || ')'
	|| ' OWNER TO ermrest;';
    END LOOP;

  END LOOP;
END;
$$ LANGUAGE plpgsql;
