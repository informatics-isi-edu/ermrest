
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

-- The following SQL idempotently creates per-catalog _ermrest schema.

CREATE SCHEMA IF NOT EXISTS _ermrest;

CREATE OR REPLACE FUNCTION _ermrest.create_domain_if_not_exists(domain_schema text, domain_name text, basetype text) RETURNS boolean AS $$
BEGIN
  IF (SELECT True FROM information_schema.domains d WHERE d.domain_schema = $1 AND d.domain_name = $2) THEN
    RETURN False;
  ELSE
    EXECUTE 'CREATE DOMAIN ' || quote_ident($1) || '.' || quote_ident($2) || ' ' || $3 || ';';
    RETURN True;
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.astext(timestamptz) RETURNS text IMMUTABLE AS $$
  SELECT to_char($1 AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"');
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.astext(timestamp) RETURNS text IMMUTABLE AS $$
  SELECT to_char($1, 'YYYY-MM-DD"T"HH24:MI:SS');
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.astext(timetz) RETURNS text IMMUTABLE AS $$
  SELECT to_char(date_part('hour', $1 AT TIME ZONE 'UTC'), '09') 
     || ':' || to_char(date_part('minute', $1 AT TIME ZONE 'UTC'), '09') 
     || ':' || to_char(date_part('second', $1 AT TIME ZONE 'UTC'), '09');
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.astext(time) RETURNS text IMMUTABLE AS $$
  SELECT to_char(date_part('hour', $1), '09') 
     || ':' || to_char(date_part('minute', $1), '09') 
     || ':' || to_char(date_part('second', $1), '09');
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.astext(date) RETURNS text IMMUTABLE AS $$
  SELECT to_char($1, 'YYYY-MM-DD');
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.astext(anyarray) RETURNS text IMMUTABLE AS $$
  SELECT array_agg(_ermrest.astext(v))::text FROM unnest($1) s(v);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.astext(anynonarray) RETURNS text IMMUTABLE AS $$
  SELECT $1::text;
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.current_client() RETURNS text STABLE AS $$
BEGIN
  RETURN current_setting('webauthn2.client');
EXCEPTION WHEN OTHERS THEN
  RETURN NULL::text;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.current_client_obj() RETURNS json STABLE AS $$
BEGIN
  RETURN current_setting('webauthn2.client_json')::json;
EXCEPTION WHEN OTHERS THEN
  RETURN NULL::json;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.current_attributes() RETURNS text[] STABLE AS $$
  SELECT current_setting('webauthn2.attributes_array')::text[];
$$ LANGUAGE SQL;

SELECT _ermrest.create_domain_if_not_exists('public', 'longtext', 'text');
SELECT _ermrest.create_domain_if_not_exists('public', 'markdown', 'text');
-- SELECT _ermrest.create_domain_if_not_exists('public', 'gene_sequence', 'text');

CREATE TABLE IF NOT EXISTS _ermrest.model_last_modified (
    ts timestamptz PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS _ermrest.table_last_modified (
    "oid" oid PRIMARY KEY,
    ts timestamptz
);
CREATE INDEX IF NOT EXISTS tlm_ts_oid ON _ermrest.table_last_modified (ts, oid);


CREATE TABLE IF NOT EXISTS _ermrest.known_schemas (
  oid oid PRIMARY KEY,
  schema_name text UNIQUE NOT NULL,
  "comment" text
);

CREATE TABLE IF NOT EXISTS _ermrest.known_types (
  oid oid PRIMARY KEY,
  schema_oid oid NOT NULL REFERENCES _ermrest.known_schemas(oid) ON DELETE CASCADE,
  type_name text NOT NULL,
  array_element_type_oid oid REFERENCES _ermrest.known_types(oid),
  domain_element_type_oid oid REFERENCES _ermrest.known_types(oid),
  domain_notnull boolean,
  domain_default text,
  "comment" text,
  UNIQUE(schema_oid, type_name),
  CHECK(array_element_type_oid IS NULL OR domain_element_type_oid IS NULL)
);
CREATE INDEX IF NOT EXISTS known_types_basetype_idx
 ON _ermrest.known_types (array_element_type_oid NULLS FIRST, domain_element_type_oid NULLS FIRST);

CREATE TABLE IF NOT EXISTS _ermrest.known_tables (
  oid oid PRIMARY KEY,
  schema_oid oid NOT NULL REFERENCES _ermrest.known_schemas(oid) ON DELETE CASCADE,
  table_name text NOT NULL,
  table_kind text NOT NULL,
  "comment" text,
  UNIQUE(schema_oid, table_name)
);

CREATE TABLE IF NOT EXISTS _ermrest.known_columns (
  table_oid oid REFERENCES _ermrest.known_tables(oid) ON DELETE CASCADE,
  column_num int,
  column_name text NOT NULL,
  type_oid oid NOT NULL REFERENCES _ermrest.known_types(oid) ON DELETE CASCADE,
  not_null boolean NOT NULL,
  column_default text,
  "comment" text,
  PRIMARY KEY(table_oid, column_num),
  UNIQUE(table_oid, column_name)
);

DROP TABLE IF EXISTS _ermrest.known_psuedo_notnulls;
CREATE TABLE IF NOT EXISTS _ermrest.known_pseudo_notnulls (
  table_oid oid REFERENCES _ermrest.known_tables(oid) ON DELETE CASCADE,
  column_num int,
  PRIMARY KEY(table_oid, column_num),
  FOREIGN KEY(table_oid, column_num) REFERENCES _ermrest.known_columns (table_oid, column_num) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS _ermrest.known_keys (
  oid oid PRIMARY KEY,
  schema_oid oid NOT NULL REFERENCES _ermrest.known_schemas(oid) ON DELETE CASCADE,
  constraint_name text NOT NULL,
  table_oid oid NOT NULL REFERENCES _ermrest.known_tables(oid) ON DELETE CASCADE,
  column_nums int[] NOT NULL,
  "comment" text,
  UNIQUE(schema_oid, constraint_name)
);

CREATE TABLE IF NOT EXISTS _ermrest.known_pseudo_keys (
  id serial PRIMARY KEY,
  constraint_name text UNIQUE,
  table_oid oid NOT NULL REFERENCES _ermrest.known_tables(oid) ON DELETE CASCADE,
  column_nums int[] NOT NULL,
  "comment" text
);

CREATE TABLE IF NOT EXISTS _ermrest.known_fkeys (
  oid oid PRIMARY KEY,
  schema_oid oid NOT NULL REFERENCES _ermrest.known_schemas(oid) ON DELETE CASCADE,
  constraint_name text NOT NULL,
  fk_table_oid oid NOT NULL REFERENCES _ermrest.known_tables(oid) ON DELETE CASCADE,
  fk_column_nums int[] NOT NULL,
  pk_table_oid oid NOT NULL REFERENCES _ermrest.known_tables(oid) ON DELETE CASCADE,
  pk_column_nums int[] NOT NULL,
  delete_rule text NOT NULL,
  update_rule text NOT NULL,
  "comment" text,
  UNIQUE(schema_oid, constraint_name),
  CHECK(array_length(fk_column_nums, 1) = array_length(pk_column_nums, 1))
);

CREATE TABLE IF NOT EXISTS _ermrest.known_pseudo_fkeys (
  id serial PRIMARY KEY,
  constraint_name text UNIQUE,
  fk_table_oid oid NOT NULL REFERENCES _ermrest.known_tables(oid) ON DELETE CASCADE,
  fk_column_nums int[] NOT NULL,
  pk_table_oid oid NOT NULL REFERENCES _ermrest.known_tables(oid) ON DELETE CASCADE,
  pk_column_nums int[] NOT NULL,
  "comment" text,
  CHECK(array_length(fk_column_nums, 1) = array_length(pk_column_nums, 1))
);

CREATE OR REPLACE VIEW _ermrest.introspect_schemas AS
  SELECT
    nc.oid,
    nc.nspname::text AS schema_name,
    obj_description(nc.oid)::text AS "comment"
  FROM pg_catalog.pg_namespace nc
  WHERE nc.nspname NOT IN ('information_schema', 'pg_toast')
    AND NOT pg_is_other_temp_schema(nc.oid)
;

CREATE OR REPLACE VIEW _ermrest.introspect_types AS
  -- base types
  SELECT
    t.oid as "oid",
    t.typnamespace as "schema_oid",
    pg_catalog.format_type(t.oid, NULL)::text AS "type_name",
    NULL::oid AS "array_element_type_oid",
    NULL::oid AS "domain_element_type_oid",
    NULL::boolean AS "domain_notnull",
    NULL::text AS domain_default,
    pg_catalog.obj_description(t.oid, 'pg_type')::text as "comment"
  FROM pg_catalog.pg_type t
  WHERE t.typtype != 'd'::char
    AND t.typelem = 0::oid
    AND t.typrelid = 0
    AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_type el WHERE el.typarray = t.oid)
    AND pg_catalog.pg_type_is_visible(t.oid)

  UNION

  -- array types
  SELECT
    t.oid as "oid",
    t.typnamespace as "schema_oid",
    pg_catalog.format_type(t.oid, NULL)::text AS "type_name",
    et.oid as "array_element_type_oid",
    NULL::oid AS "domain_element_type_oid",
    NULL::boolean AS "domain_notnull",
    NULL::text AS domain_default,
    NULL::text AS "comment"
  FROM pg_catalog.pg_type t
  JOIN pg_catalog.pg_type et ON (et.typarray = t.oid)
  WHERE t.typtype != 'd'::char
    AND et.typelem = 0::oid
    AND et.typrelid = 0
    AND pg_catalog.pg_type_is_visible(t.oid)

  UNION

  -- domains
  SELECT
    t.oid as "oid",
    t.typnamespace as "schema_oid",
    pg_catalog.format_type(t.oid, NULL)::text AS "type_name",
    NULL::oid AS array_element_type_oid,
    t.typbasetype as "domain_element_type_oid",
    t.typnotnull AS "domain_notnull",
    t.typdefault::text AS "domain_value",
    d.description::text as "comment"
  FROM pg_catalog.pg_type t
  LEFT JOIN pg_catalog.pg_description d ON (d.classoid = t.tableoid AND d.objoid = t.oid AND d.objsubid = 0)
  WHERE t.typtype = 'd'
    AND pg_catalog.pg_type_is_visible(t.oid)
;

CREATE OR REPLACE VIEW _ermrest.introspect_tables AS
  SELECT
    c.oid AS oid,
    nc.oid AS schema_oid,
    c.relname::text AS table_name,
    c.relkind::text AS table_kind,
    obj_description(c.oid)::text AS "comment"
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace nc ON (c.relnamespace = nc.oid)
  WHERE nc.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
    AND NOT pg_is_other_temp_schema(nc.oid) 
    AND (c.relkind = ANY (ARRAY['r'::"char", 'v'::"char", 'f'::"char", 'm'::"char"]))
;

CREATE OR REPLACE VIEW _ermrest.introspect_columns AS
  SELECT
    c.oid AS table_oid,
    a.attnum::int AS column_num,
    a.attname::text AS column_name,
    a.atttypid AS type_oid,
    a.attnotnull AS not_null,
    pg_get_expr(ad.adbin, ad.adrelid)::text AS column_default,
    col_description(c.oid, a.attnum)::text AS comment
  FROM pg_catalog.pg_attribute a
  JOIN pg_catalog.pg_class c ON (a.attrelid = c.oid)
  JOIN pg_catalog.pg_namespace nc ON (c.relnamespace = nc.oid)
  LEFT JOIN pg_catalog.pg_attrdef ad ON (a.attrelid = ad.adrelid AND a.attnum = ad.adnum)
  WHERE nc.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
    AND NOT pg_is_other_temp_schema(nc.oid) 
    AND a.attnum > 0
    AND NOT a.attisdropped
    AND (c.relkind = ANY (ARRAY['r'::"char", 'v'::"char", 'f'::"char", 'm'::"char"]))
;

CREATE OR REPLACE VIEW _ermrest.introspect_keys AS
  SELECT
    con.oid AS "oid",
    ncon.oid AS "schema_oid",
    con.conname::information_schema.sql_identifier::text AS constraint_name,
    pkcl.oid AS "table_oid",
    (SELECT array_agg(pka.attnum::int ORDER BY i.i)
     FROM generate_subscripts(con.conkey, 1) i
     JOIN pg_catalog.pg_attribute pka ON con.conrelid = pka.attrelid AND con.conkey[i.i] = pka.attnum
    ) AS column_nums,
    obj_description(con.oid)::text AS comment
  FROM pg_namespace ncon
  JOIN pg_constraint con ON (ncon.oid = con.connamespace)
  JOIN pg_class pkcl ON (con.conrelid = pkcl.oid AND con.contype = ANY (ARRAY['u'::"char",'p'::"char"]))
  JOIN pg_namespace npk ON (pkcl.relnamespace = npk.oid)
  WHERE has_table_privilege(pkcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
     OR has_any_column_privilege(pkcl.oid, 'INSERT, UPDATE, REFERENCES'::text)
;

CREATE OR REPLACE VIEW _ermrest.introspect_fkeys AS
  SELECT
    con.oid AS "oid",
    ncon.oid AS schema_oid,
    con.conname::information_schema.sql_identifier::text AS constraint_name,
    fkcl.oid AS fk_table_oid,
    (SELECT array_agg(fka.attnum::int ORDER BY i.i)
     FROM generate_subscripts(con.conkey, 1) i
     JOIN pg_catalog.pg_attribute fka ON con.conrelid = fka.attrelid AND con.conkey[i.i] = fka.attnum
    ) AS fk_column_nums,
    kcl.oid AS pk_table_oid,
    (SELECT array_agg(ka.attnum::int ORDER BY i.i)
     FROM generate_subscripts(con.confkey, 1) i
     JOIN pg_catalog.pg_attribute ka ON con.confrelid = ka.attrelid AND con.confkey[i.i] = ka.attnum
    ) AS pk_column_nums,
    CASE con.confdeltype
       WHEN 'c'::"char" THEN 'CASCADE'::text
       WHEN 'n'::"char" THEN 'SET NULL'::text
       WHEN 'd'::"char" THEN 'SET DEFAULT'::text
       WHEN 'r'::"char" THEN 'RESTRICT'::text
       WHEN 'a'::"char" THEN 'NO ACTION'::text
       ELSE NULL::text
    END AS delete_rule,
    CASE con.confupdtype
       WHEN 'c'::"char" THEN 'CASCADE'::text
       WHEN 'n'::"char" THEN 'SET NULL'::text
       WHEN 'd'::"char" THEN 'SET DEFAULT'::text
       WHEN 'r'::"char" THEN 'RESTRICT'::text
       WHEN 'a'::"char" THEN 'NO ACTION'::text
       ELSE NULL::text
    END AS update_rule,
    obj_description(con.oid)::text AS comment
  FROM pg_namespace ncon
  JOIN pg_constraint con ON (ncon.oid = con.connamespace)
  JOIN pg_class fkcl ON (con.conrelid = fkcl.oid AND con.contype = 'f'::"char")
  JOIN pg_class kcl ON (con.confrelid = kcl.oid AND con.contype = 'f'::"char")
  JOIN pg_namespace nfk ON (fkcl.relnamespace = nfk.oid)
  JOIN pg_namespace nk ON (kcl.relnamespace = nk.oid)
  WHERE (   pg_has_role(kcl.relowner, 'USAGE'::text) 
         OR has_table_privilege(kcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
         OR has_any_column_privilege(kcl.oid, 'INSERT, UPDATE, REFERENCES'::text))
    AND (   pg_has_role(fkcl.relowner, 'USAGE'::text) 
         OR has_table_privilege(fkcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
         OR has_any_column_privilege(fkcl.oid, 'INSERT, UPDATE, REFERENCES'::text))
;

CREATE OR REPLACE FUNCTION _ermrest.rescan_introspect() RETURNS boolean AS $$
DECLARE
  model_changed boolean;
  had_changes int;
BEGIN
  model_changed := False;

  -- sync up known with currently visible schemas
  WITH deleted AS (
    DELETE FROM _ermrest.known_schemas k
    USING (
      SELECT oid FROM _ermrest.known_schemas
      EXCEPT SELECT oid FROM _ermrest.introspect_schemas
    ) d
    WHERE k.oid = d.oid
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_schemas k
    SET
      schema_name = v.schema_name,
      "comment" = v."comment"
    FROM _ermrest.introspect_schemas v
    WHERE k.oid = v.oid
      AND ROW(k.*) IS DISTINCT FROM ROW(v.*)
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_schemas
    SELECT * FROM _ermrest.introspect_schemas
    EXCEPT SELECT * FROM _ermrest.known_schemas
    RETURNING oid
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible types
  WITH deleted AS (
    DELETE FROM _ermrest.known_types k
    USING (
      SELECT oid FROM _ermrest.known_types
      EXCEPT SELECT oid FROM _ermrest.introspect_types
    ) d
    WHERE k.oid = d.oid
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_types k
    SET
      schema_oid = v.schema_oid,
      type_name = v.type_name,
      array_element_type_oid = v.array_element_type_oid,
      domain_element_type_oid = v.domain_element_type_oid,
      domain_notnull = v.domain_notnull,
      domain_default = v.domain_default,
      "comment" = v."comment"
    FROM _ermrest.introspect_types v
    WHERE k.oid = v.oid
      AND ROW(k.*) IS DISTINCT FROM ROW(v.*)
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_types
    SELECT * FROM _ermrest.introspect_types
    EXCEPT SELECT * FROM _ermrest.known_types
    RETURNING oid
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible tables
  WITH deleted AS (
    DELETE FROM _ermrest.known_tables k
    USING (
      SELECT oid FROM _ermrest.known_tables
      EXCEPT SELECT oid FROM _ermrest.introspect_tables
    ) d
    WHERE k.oid = d.oid
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_tables k
    SET
      schema_oid = v.schema_oid,
      table_name = v.table_name,
      table_kind = v.table_kind,
      "comment" = v."comment"
    FROM _ermrest.introspect_tables v
    WHERE k.oid = v.oid
      AND ROW(k.*) IS DISTINCT FROM ROW(v.*)
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_tables
    SELECT * FROM _ermrest.introspect_tables
    EXCEPT SELECT * FROM _ermrest.known_tables
    RETURNING oid
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible columns
  WITH deleted AS (
    DELETE FROM _ermrest.known_columns k
    USING (
      SELECT table_oid, column_num FROM _ermrest.known_columns
      EXCEPT SELECT table_oid, column_num FROM _ermrest.introspect_columns
    ) d
    WHERE k.table_oid = d.table_oid AND k.column_num = d.column_num
    RETURNING k.table_oid, k.column_num
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_columns k
    SET
      column_name = v.column_name,
      type_oid = v.type_oid,
      not_null = v.not_null,
      column_default = v.column_default,
      "comment" = v."comment"
    FROM _ermrest.introspect_columns v
    WHERE k.table_oid = v.table_oid AND k.column_num = v.column_num
      AND ROW(k.*) IS DISTINCT FROM ROW(v.*)
    RETURNING k.table_oid, k.column_num
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_columns
    SELECT * FROM _ermrest.introspect_columns
    EXCEPT SELECT * FROM _ermrest.known_columns
    RETURNING table_oid, column_num
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;


  -- sync up known with currently visible keys
  WITH deleted AS (
    DELETE FROM _ermrest.known_keys k
    USING (
      SELECT oid FROM _ermrest.known_keys
      EXCEPT SELECT oid FROM _ermrest.introspect_keys
    ) d
    WHERE k.oid = d.oid
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_keys k
    SET
      schema_oid = v.schema_oid,
      constraint_name = v.constraint_name,
      table_oid = v.table_oid,
      column_nums = v.column_nums,
      "comment" = v."comment"
    FROM _ermrest.introspect_keys v
    WHERE k.oid = v.oid
      AND ROW(k.*) IS DISTINCT FROM ROW(v.*)
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_keys
    SELECT * FROM _ermrest.introspect_keys
    EXCEPT SELECT * FROM _ermrest.known_keys
    RETURNING oid
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;


  -- sync up known with currently visible foreign keys
  WITH deleted AS (
    DELETE FROM _ermrest.known_fkeys k
    USING (
      SELECT oid FROM _ermrest.known_fkeys
      EXCEPT SELECT oid FROM _ermrest.introspect_fkeys
    ) d
    WHERE k.oid = d.oid
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_fkeys k
    SET
      schema_oid = v.schema_oid,
      constraint_name = v.constraint_name,
      fk_table_oid = v.fk_table_oid,
      fk_column_nums = v.fk_column_nums,
      pk_table_oid = v.pk_table_oid,
      pk_column_nums = v.pk_column_nums,
      delete_rule = v.delete_rule,
      update_rule = v.update_rule,
      "comment" = v."comment"
    FROM _ermrest.introspect_fkeys v
    WHERE k.oid = v.oid
      AND ROW(k.*) IS DISTINCT FROM ROW(v.*)
    RETURNING k.oid
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_fkeys
    SELECT * FROM _ermrest.introspect_fkeys
    EXCEPT SELECT * FROM _ermrest.known_fkeys
    RETURNING oid
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;


  RETURN model_changed;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION _ermrest.table_oid(sname text, tname text) RETURNS oid STABLE AS $$
  SELECT t.oid
  FROM _ermrest.introspect_tables t
  JOIN _ermrest.introspect_schemas s ON (t.schema_oid = s.oid)
  WHERE s.schema_name = $1 AND t.table_name = $2;
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.column_num(toid oid, cname text) RETURNS int STABLE AS $$
  SELECT c.column_num
  FROM _ermrest.introspect_columns c
  WHERE c.table_oid = $1 AND c.column_name = $2;
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.model_version_bump() RETURNS void AS $$
DECLARE
  last_ts timestamptz;
BEGIN
  SELECT ts INTO last_ts FROM _ermrest.model_last_modified ORDER BY ts DESC LIMIT 1;

  IF last_ts > now() THEN
    -- paranoid integrity check in case we aren't using SERIALIZABLE isolation somehow...
    RAISE EXCEPTION serialization_failure USING MESSAGE = 'ERMrest model version clock reversal!';
  END IF;

  DELETE FROM _ermrest.model_last_modified WHERE ts != now();

  INSERT INTO _ermrest.model_last_modified (ts)
    VALUES (now())
    ON CONFLICT (ts) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.model_change_idempotent() RETURNS void AS $$
DECLARE
  model_changed boolean;
BEGIN
  SELECT _ermrest.rescan_introspect() INTO model_changed;
  
  IF _ermrest.rescan_introspect() THEN
    PERFORM _ermrest.model_version_bump();
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.model_change_event() RETURNS void AS $$
BEGIN
  -- use the new, smarter scan
  PERFORM _ermrest.model_change_idempotent();

  -- but force version change for backward-compatibility with DBAs and legacy code
  PERFORM _ermrest.model_version_bump();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.data_change_event(sname text, tname text) RETURNS void AS $$
BEGIN
  IF (SELECT ts
      FROM _ermrest.table_last_modified
      WHERE oid = _ermrest.table_oid($1, $2)
      ORDER BY ts DESC
      LIMIT 1) > now() THEN
    -- paranoid integrity check in case we aren't using SERIALIZABLE isolation somehow...
    RAISE EXCEPTION serialization_failure USING MESSAGE = 'ERMrest table version clock reversal!';
  END IF;

  DELETE FROM _ermrest.table_last_modified
  WHERE oid = _ermrest.table_oid($1, $2) AND ts != now();

  INSERT INTO _ermrest.table_last_modified (oid, ts)
    VALUES (_ermrest.table_oid($1, $2), now())
    ON CONFLICT (oid) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS _ermrest.model_catalog_acl (
  acl text PRIMARY KEY,
  members text[]
);

CREATE TABLE IF NOT EXISTS _ermrest.model_schema_acl (
  schema_name text,
  acl text,
  members text[],
  PRIMARY KEY (schema_name, acl)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_table_acl (
  schema_name text,
  table_name text,
  acl text,
  members text[],
  PRIMARY KEY (schema_name, table_name, acl)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_column_acl (
  schema_name text,
  table_name text,
  column_name text,
  acl text,
  members text[],
  PRIMARY KEY (schema_name, table_name, column_name, acl)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_keyref_acl (
  from_schema_name text,
  from_table_name text,
  from_column_names text[],
  to_schema_name text,
  to_table_name text,
  to_column_names text[],
  acl text,
  members text[],
  PRIMARY KEY (from_schema_name, from_table_name, from_column_names, to_schema_name, to_table_name, to_column_names, acl)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_table_dynacl (
  schema_name text,
  table_name text,
  binding_name text,
  binding jsonb NOT NULL,
  PRIMARY KEY (schema_name, table_name, binding_name)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_column_dynacl (
  schema_name text,
  table_name text,
  column_name text,
  binding_name text,
  binding jsonb NOT NULL,
  PRIMARY KEY (schema_name, table_name, column_name, binding_name)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_keyref_dynacl (
  from_schema_name text,
  from_table_name text,
  from_column_names text[],
  to_schema_name text,
  to_table_name text,
  to_column_names text[],
  binding_name text,
  binding jsonb NOT NULL,
  PRIMARY KEY (from_schema_name, from_table_name, from_column_names, to_schema_name, to_table_name, to_column_names, binding_name)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_catalog_annotation (
  annotation_uri text PRIMARY KEY,
  annotation_value json
);


SELECT _ermrest.model_change_event();
