
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

CREATE TABLE IF NOT EXISTS _ermrest.model_version (
    snap_txid bigint PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS _ermrest.data_version (
    "schema" text,
    "table" text,
    snap_txid bigint,
    PRIMARY KEY ("schema", "table", "snap_txid")
);

CREATE OR REPLACE FUNCTION _ermrest.model_change_event() RETURNS void AS $$
DECLARE
  resultbool boolean;
  trigger_txid bigint;
BEGIN
  SELECT txid_current() INTO trigger_txid;

  SELECT EXISTS (SELECT snap_txid
                 FROM _ermrest.model_version
                 WHERE snap_txid = trigger_txid)
  INTO resultbool ;

  IF NOT resultbool THEN
    INSERT INTO _ermrest.model_version (snap_txid)
      SELECT trigger_txid ;
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.data_change_event(sname text, tname text) RETURNS void AS $$
DECLARE
  resultbool boolean;
  trigger_txid bigint;
BEGIN
  SELECT txid_current() INTO trigger_txid;

  SELECT EXISTS (SELECT snap_txid
                 FROM _ermrest.data_version
                 WHERE "schema" = sname
                   AND "table" = tname
                   AND snap_txid = trigger_txid) 
  INTO resultbool ;

  IF NOT resultbool THEN
    INSERT INTO _ermrest.data_version ("schema", "table", snap_txid)
      SELECT sname, tname, trigger_txid ;
  END IF;
END;
$$ LANGUAGE plpgsql;



CREATE TABLE IF NOT EXISTS _ermrest.model_pseudo_key (
  id serial PRIMARY KEY,
  name text UNIQUE,
  schema_name text NOT NULL,
  table_name text NOT NULL,
  column_names text[] NOT NULL,
  comment text,
  UNIQUE(schema_name, table_name, column_names)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_pseudo_keyref (
  id serial PRIMARY KEY,
  name text UNIQUE,
  from_schema_name text NOT NULL,
  from_table_name text NOT NULL,
  from_column_names text[] NOT NULL,
  to_schema_name text NOT NULL,
  to_table_name text NOT NULL,
  to_column_names text[] NOT NULL,
  comment text,
  UNIQUE(from_schema_name, from_table_name, from_column_names, to_schema_name, to_table_name, to_column_names)
);

CREATE TABLE IF NOT EXISTS _ermrest.model_pseudo_notnull (
  id serial PRIMARY KEY,
  schema_name text NOT NULL,
  table_name text NOT NULL,
  column_name text NOT NULL,
  UNIQUE(schema_name, table_name, column_name)
);


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
