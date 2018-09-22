
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

-- The following SQL idempotently creates per-catalog _ermrest schema.

DO $ermrest_schema$
<< ermrest_schema >>
DECLARE
  looprow record;
BEGIN
-- NOTE, we don't indent this block so editing below is easier...
-- We use a lot of conditionals rather than idempotent DDL to make successful operation quieter...

IF (SELECT True FROM information_schema.schemata WHERE schema_name = '_ermrest') IS NULL THEN
  CREATE SCHEMA _ermrest;
END IF;

IF (SELECT True FROM information_schema.schemata WHERE schema_name = '_ermrest_history') IS NULL THEN
  CREATE SCHEMA _ermrest_history;
END IF;

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

BEGIN
  CREATE TYPE ermrest_acls AS (
    "enumerate" text[],
    "select" text[],
    "insert" text[],
    "update" text[],
    "delete" text[],
    "write" text[],
    "create" text[],
    "owner" text[]
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END;

BEGIN
  CREATE TYPE ermrest_acl_matches AS (
    "enumerate" boolean,
    "select" boolean,
    "insert" boolean,
    "update" boolean,
    "delete" boolean,
    "write" boolean,
    "create" boolean,
    "owner" boolean
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END;

BEGIN
  CREATE TYPE ermrest_rights AS (
    "enumerate" boolean,
    "select" boolean,
    "insert" boolean,
    "update" boolean,
    "delete" boolean,
    "create" boolean,
    "owner" boolean
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END;

-- convert jsonb '["a", "b", ...]' to ARRAY['a', 'b', ...]
CREATE OR REPLACE FUNCTION _ermrest.jsonb_to_text_array(v jsonb) RETURNS text[] IMMUTABLE AS $$
SELECT
  CASE WHEN v = 'null'::jsonb THEN NULL
  ELSE
    (SELECT array_agg(e ORDER BY n)
     FROM jsonb_array_elements_text(v) WITH ORDINALITY s (e, n))
  END;
$$ LANGUAGE SQL;

-- unpack jsonb acls into composite type record
CREATE OR REPLACE FUNCTION _ermrest.to_acls(acls jsonb) RETURNS ermrest_acls IMMUTABLE AS $$
SELECT
  _ermrest.jsonb_to_text_array(acls->'enumerate'),
  _ermrest.jsonb_to_text_array(acls->'select'),
  _ermrest.jsonb_to_text_array(acls->'insert'),
  _ermrest.jsonb_to_text_array(acls->'update'),
  _ermrest.jsonb_to_text_array(acls->'delete'),
  _ermrest.jsonb_to_text_array(acls->'write'),
  _ermrest.jsonb_to_text_array(acls->'create'),
  _ermrest.jsonb_to_text_array(acls->'owner');
$$ LANGUAGE SQL;

-- unpack stack of jsonb acls into composite type record
CREATE OR REPLACE FUNCTION _ermrest.to_acls(acls1 jsonb, acls2 jsonb)
RETURNS ermrest_acls IMMUTABLE AS $$
SELECT _ermrest.to_acls($1 || jsonb_strip_nulls($2));
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.to_acls(acls1 jsonb, acls2 jsonb, acls3 jsonb)
RETURNS ermrest_acls IMMUTABLE AS $$
SELECT _ermrest.to_acls(($1 || jsonb_strip_nulls($2)) || jsonb_strip_nulls($3));
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.to_acls(acls1 jsonb, acls2 jsonb, acls3 jsonb, acls4 jsonb)
RETURNS ermrest_acls IMMUTABLE AS $$
SELECT _ermrest.to_acls((($1 || jsonb_strip_nulls($2)) || jsonb_strip_nulls($3)) || jsonb_strip_nulls($4));
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.matches(acls ermrest_acls, roles text[])
RETURNS ermrest_acl_matches IMMUTABLE AS $$
SELECT
  acls."enumerate" && roles,
  acls."select" && roles,
  acls."insert" && roles,
  acls."update" && roles,
  acls."delete" && roles,
  acls."write" && roles,
  acls."create" && roles,
  acls."owner" && roles;
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.rights(acls ermrest_acls, roles text[])
RETURNS ermrest_rights IMMUTABLE AS $$
DECLARE
  am ermrest_acl_matches;
  ar ermrest_rights;
BEGIN
  am := _ermrest.matches(acls, roles);

  ar."owner" := am."owner";
  ar."create" := am."create" OR ar."owner";
  ar."delete" := am."delete" OR am."write" OR ar."owner";
  ar."update" := am."update" OR am."write" OR ar."owner";
  ar."insert" := am."insert" OR am."write" OR ar."owner";
  ar."select" := am."select" OR ar."update" OR ar."delete" OR ar."owner";
  ar."enumerate" := am."enumerate" OR ar."select" OR ar."insert";

  RETURN ar;
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

CREATE OR REPLACE FUNCTION _ermrest.urlb32_encode(int8) RETURNS text IMMUTABLE AS $$
DECLARE
  raw bit(65);
  code int;
  encoded text;
  symbols text[];
BEGIN
  symbols := '{0,1,2,3,4,5,6,7,8,9,A,B,C,D,E,F,G,H,J,K,M,N,P,Q,R,S,T,V,W,X,Y,Z}'::text[];
  raw := $1::bit(64) || B'0';
  encoded := '';
  
  FOR d IN 1..13 LOOP
    IF d > 2 AND (d-1) % 4 = 0
    THEN
      encoded := '-' || encoded;
    END IF;
    code := substring(raw from 61 for 5)::int;
    encoded := symbols[ code + 1 ] || encoded;
    raw := raw >> 5;
  END LOOP;

  encoded := regexp_replace(encoded, '^[0-]+', '');
  IF encoded = '' THEN encoded := '0'; END IF;

  RETURN encoded;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.urlb32_decode(encoded text, raise_errors boolean) RETURNS int8 IMMUTABLE AS $$
DECLARE
  raw bit(65);
  code int;
  symbol text;
  encoded text;
BEGIN
  encoded = regexp_replace(upper($1), '-', '', 'g');
  raw := 0::bit(65);

  IF octet_length(encoded) > 13
  THEN
    IF raise_errors THEN
      RAISE SQLSTATE '22P02' USING DETAIL = $1, HINT = 'Length exceeds 13 symbols';
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  FOR d IN 1 .. octet_length(encoded) LOOP
    CASE substring(encoded from 1 for 1)
      WHEN '0', 'O' THEN code := 0;
      WHEN '1', 'I', 'L' THEN code := 1;
      WHEN '2' THEN code := 2;
      WHEN '3' THEN code := 3;
      WHEN '4' THEN code := 4;
      WHEN '5' THEN code := 5;
      WHEN '6' THEN code := 6;
      WHEN '7' THEN code := 7;
      WHEN '8' THEN code := 8;
      WHEN '9' THEN code := 9;
      WHEN 'A' THEN code := 10;
      WHEN 'B' THEN code := 11;
      WHEN 'C' THEN code := 12;
      WHEN 'D' THEN code := 13;
      WHEN 'E' THEN code := 14;
      WHEN 'F' THEN code := 15;
      WHEN 'G' THEN code := 16;
      WHEN 'H' THEN code := 17;
      WHEN 'J' THEN code := 18;
      WHEN 'K' THEN code := 19;
      WHEN 'M' THEN code := 20;
      WHEN 'N' THEN code := 21;
      WHEN 'P' THEN code := 22;
      WHEN 'Q' THEN code := 23;
      WHEN 'R' THEN code := 24;
      WHEN 'S' THEN code := 25;
      WHEN 'T' THEN code := 26;
      WHEN 'V' THEN code := 27;
      WHEN 'W' THEN code := 28;
      WHEN 'X' THEN code := 29;
      WHEN 'Y' THEN code := 30;
      WHEN 'Z' THEN code := 31;
      ELSE
        IF raise_errors THEN
          RAISE SQLSTATE '22P02' USING DETAIL = $1, HINT = 'Invalid character: ' || quote_literal(substring(encoded from 1 for 1));
	ELSE
	  RETURN NULL;
	END IF;
    END CASE;
    raw := (raw << 5) | ((0::bit(60) || code::bit(5)));
    encoded := substring(encoded from 2);
  END LOOP;

  RETURN substring(raw from 1 for 64)::int8;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.urlb32_decode(text) RETURNS int8 IMMUTABLE AS $$
SELECT _ermrest.urlb32_decode($1, True);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.tstzencode(timestamptz) RETURNS text IMMUTABLE AS $$
  SELECT _ermrest.urlb32_encode(floor(EXTRACT(epoch FROM $1))::int8 * 1000000 + EXTRACT(microseconds FROM $1)::int8 % 1000000);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.tstzdecode(text) RETURNS timestamptz IMMUTABLE AS $$
  SELECT timestamptz('epoch') + (_ermrest.urlb32_decode($1) / 1000000) * interval '1 second' + (_ermrest.urlb32_decode($1) % 1000000) * interval '1 microsecond';
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

IF (SELECT True FROM information_schema.sequences WHERE sequence_schema = '_ermrest' AND sequence_name = 'rid_seq') IS NULL THEN
  -- MAXVALUE 2**63 - 1 default
  CREATE SEQUENCE _ermrest.rid_seq NO CYCLE;
END IF;

PERFORM _ermrest.create_domain_if_not_exists('public', 'longtext', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'markdown', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'gene_sequence', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'ermrest_rid', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'ermrest_rcb', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'ermrest_rmb', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'ermrest_rct', 'timestamptz');
PERFORM _ermrest.create_domain_if_not_exists('public', 'ermrest_rmt', 'timestamptz');
PERFORM _ermrest.create_domain_if_not_exists('public', 'ermrest_uri', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'ermrest_curie', 'text');

-- use as a BEFORE INSERT UPDATE PER ROW trigger...
CREATE OR REPLACE FUNCTION _ermrest.maintain_row() RETURNS TRIGGER AS $$
DECLARE
  colrow RECORD;
  newj jsonb;
  oldj jsonb;
  val text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    newj := to_jsonb(NEW);
    IF newj ? 'RID' AND NEW."RID" IS NULL THEN
      NEW."RID" := _ermrest.urlb32_encode(nextval('_ermrest.rid_seq'));
    END IF;
    IF newj ? 'RCB' AND NEW."RCB" IS NULL THEN
      NEW."RCB" := _ermrest.current_client();
    END IF;
    IF newj ? 'RCT' AND NEW."RCT" IS NULL THEN
      NEW."RCT" := now();
    END IF;
    IF newj ? 'RMB' THEN NEW."RMB" := _ermrest.current_client(); END IF;
    IF newj ? 'RMT' THEN NEW."RMT" := now(); END IF;

    -- find columns of this row using ermrest_uri or ermrest_curie domains
    FOR colrow IN
      SELECT c.*
      FROM _ermrest.known_schemas s
      JOIN _ermrest.known_tables t ON (s."RID" = t.schema_rid)
      JOIN _ermrest.known_columns c ON (t."RID" = c.table_rid)
      JOIN _ermrest.known_types typ ON (typ."RID" = c.type_rid)
      JOIN _ermrest.known_schemas s2 ON (s2."RID" = typ.schema_rid)
      WHERE s.schema_name = TG_TABLE_SCHEMA
        AND t.table_name = TG_TABLE_NAME
	AND typ.type_name IN ('ermrest_uri', 'ermrest_curie')
	AND c.column_name IN ('uri', 'id')
	AND s2.schema_name = 'public'
    LOOP
      -- we can only handle these two standard column names
      -- because plpgsql doesn't provide computed field access like NEW[colname]
      IF colrow.column_name = 'uri' THEN
         val := NEW.uri;
      ELSIF colrow.column_name = 'id' THEN
         val := NEW.id;
      END IF;

      -- check whether supplied value looks like a template containing '{RID}' and expand it
      IF val ~ '[{]RID[}]' THEN
         val := regexp_replace(val, '[{]RID[}]', NEW."RID");
         IF colrow.column_name = 'uri' THEN
            NEW.uri := val;
         ELSIF colrow.column_name = 'id' THEN
            NEW.id := val;
         END IF;
      END IF;
    END LOOP;
  ELSEIF TG_OP = 'UPDATE' THEN
    -- do not allow values to change... is this too strict?
    oldj := to_jsonb(OLD);
    IF oldj ? 'RID' THEN NEW."RID" := OLD."RID"; END IF;
    IF oldj ? 'RCB' THEN NEW."RCB" := OLD."RCB"; END IF;
    IF oldj ? 'RCT' THEN NEW."RCT" := OLD."RCT"; END IF;

    IF oldj ? 'RMB' THEN NEW."RMB" := _ermrest.current_client(); END IF;
    IF oldj ? 'RMT' THEN NEW."RMT" := now(); END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_last_modified') IS NULL THEN
  CREATE TABLE _ermrest.model_last_modified (
    ts timestamptz PRIMARY KEY,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client()
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_modified') IS NULL THEN
  CREATE TABLE _ermrest.model_modified (
    ts timestamptz PRIMARY KEY,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client()
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'catalog_amended') IS NULL THEN
  CREATE TABLE _ermrest.catalog_amended (
    ts timestamptz PRIMARY KEY,
    during tstzrange NOT NULL,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client()
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_catalogs') IS NULL THEN
  CREATE TABLE _ermrest.known_catalogs (
    "RID" ermrest_rid PRIMARY KEY DEFAULT '0',
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    acls jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}',
    CHECK("RID" = '0')
  );
  INSERT INTO _ermrest.known_catalogs ("RID", acls, annotations) VALUES ('0', '{}', '{}');
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_schemas') IS NULL THEN
  CREATE TABLE _ermrest.known_schemas (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE NOT NULL,
    schema_name text UNIQUE NOT NULL,
    "comment" text,
    acls jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}'
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_types') IS NULL THEN
  CREATE TABLE _ermrest.known_types (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE NOT NULL,
    schema_rid text NOT NULL REFERENCES _ermrest.known_schemas("RID") ON DELETE CASCADE,
    type_name text NOT NULL,
    array_element_type_rid text REFERENCES _ermrest.known_types("RID"),
    domain_element_type_rid text REFERENCES _ermrest.known_types("RID"),
    domain_notnull boolean,
    domain_default text,
    "comment" text,
    UNIQUE(schema_rid, type_name),
    CHECK(array_element_type_rid IS NULL OR domain_element_type_rid IS NULL)
  );
  CREATE INDEX known_types_basetype_idx
  ON _ermrest.known_types (array_element_type_rid NULLS FIRST, domain_element_type_rid NULLS FIRST);
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_tables') IS NULL THEN
  CREATE TABLE _ermrest.known_tables (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE NOT NULL,
    schema_rid text NOT NULL REFERENCES _ermrest.known_schemas("RID") ON DELETE CASCADE,
    table_name text NOT NULL,
    table_kind text NOT NULL,
    "comment" text,
    acls jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}',
    UNIQUE(schema_rid, table_name)
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'table_last_modified') IS NULL THEN
  CREATE TABLE _ermrest.table_last_modified (
    table_rid text PRIMARY KEY REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    ts timestamptz,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client()
  );
  CREATE INDEX tlm_ts_rid ON _ermrest.table_last_modified (ts, table_rid);
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'table_modified') IS NULL THEN
  CREATE TABLE _ermrest.table_modified (
    ts timestamptz,
    table_rid text,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    PRIMARY KEY (ts, table_rid)
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest_history' AND table_name = 'visible_entities') IS NULL THEN
  CREATE TABLE _ermrest_history.visible_entities (
    entity_rid text NOT NULL,
    table_rid text NOT NULL,
    during tstzrange NOT NULL,
    PRIMARY KEY (table_rid, entity_rid, during)
  );
  CREATE INDEX ve_open_idx ON _ermrest_history.visible_entities (table_rid, entity_rid, lower(during)) WHERE upper(during) IS NULL;
  CREATE INDEX ve_resolve_idx ON _ermrest_history.visible_entities (entity_rid, during);

  -- logic to perform one-time conversion associated with creation of visible_entities on existing catalogs
  CREATE OR REPLACE FUNCTION _ermrest.htable_to_visible_entities(trid text, sname text, tname text, htname text) RETURNS void AS $$
  DECLARE
    record record;
    prev_record record;
    prev_record_rid text;
    prev_born timestamptz;
  BEGIN
    -- we can assume the visible_entities table contains NO records for this table yet
    prev_born := NULL;
    FOR record IN
      EXECUTE 'SELECT "RID"::text, during FROM _ermrest_history.' || quote_ident(htname) || ' h ORDER BY "RID", during'
    LOOP
      IF prev_born IS NOT NULL THEN
        IF record."RID" = prev_record."RID" AND (prev_record.during -|- record.during OR prev_record.during && record.during) THEN
          -- this is a continuation of previous interval
          record.during := prev_record.during + record.during; -- tolerate imprecise history ranges
          prev_record := record;
          CONTINUE;
        ELSE
          -- last record is final part of previous interval
	  INSERT INTO _ermrest_history.visible_entities (entity_rid, table_rid, during)
	  VALUES (prev_record."RID", trid, tstzrange(prev_born, upper(prev_record.during), '[)'));
	END IF;
      END IF;
      -- this begins the first (or next interval if previous was flushed above)
      prev_record := record;
      prev_born := lower(record.during);
    END LOOP;
    IF prev_born IS NOT NULL THEN
      -- flush final interval of iteration
      INSERT INTO _ermrest_history.visible_entities (entity_rid, table_rid, during)
      VALUES (prev_record."RID", trid, tstzrange(prev_born, upper(prev_record.during), '[)'));
    END IF;
  END;
  $$ LANGUAGE plpgsql;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_columns') IS NULL THEN
  CREATE TABLE _ermrest.known_columns (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    column_num int NOT NULL,
    column_name text NOT NULL,
    type_rid text NOT NULL REFERENCES _ermrest.known_types("RID") ON DELETE CASCADE,
    not_null boolean NOT NULL,
    column_default text,
    "comment" text,
    acls jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}',
    UNIQUE(table_rid, column_num) DEFERRABLE,
    UNIQUE(table_rid, column_name) DEFERRABLE
  );
ELSE
  ALTER TABLE _ermrest.known_columns
    DROP CONSTRAINT known_columns_table_rid_column_name_key,
    DROP CONSTRAINT known_columns_table_rid_column_num_key,
    ADD CONSTRAINT known_columns_table_rid_column_name_key UNIQUE (table_rid, column_name) DEFERRABLE,
    ADD CONSTRAINT known_columns_table_rid_column_num_key UNIQUE (table_rid, column_num) DEFERRABLE;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_pseudo_notnulls') IS NULL THEN
  CREATE TABLE _ermrest.known_pseudo_notnulls (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    column_rid text NOT NULL UNIQUE REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_keys') IS NULL THEN
  CREATE TABLE _ermrest.known_keys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE NOT NULL,
    schema_rid text NOT NULL REFERENCES _ermrest.known_schemas("RID") ON DELETE CASCADE,
    constraint_name text NOT NULL,
    table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    column_rids jsonb NOT NULL, -- store as RID->null hashmap
    "comment" text,
    annotations jsonb NOT NULL DEFAULT '{}',
    UNIQUE(schema_rid, constraint_name)
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_pseudo_keys') IS NULL THEN
  CREATE TABLE _ermrest.known_pseudo_keys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    constraint_name text UNIQUE,
    table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    column_rids jsonb NOT NULL, -- store as RID->null hashmap
    "comment" text,
    annotations jsonb NOT NULL DEFAULT '{}'
  );
END IF;

CREATE OR REPLACE FUNCTION _ermrest.fkey_fk_column_rids(column_rid_map jsonb) RETURNS jsonb IMMUTABLE AS $$
SELECT jsonb_build_object(fk_column_rid, NULL::text)
FROM jsonb_each_text(column_rid_map) s(fk_column_rid, pk_column_rid)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.fkey_pk_column_rids(column_rid_map jsonb) RETURNS jsonb IMMUTABLE AS $$
SELECT jsonb_build_object(pk_column_rid, NULL::text)
FROM jsonb_each_text(column_rid_map) s(fk_column_rid, pk_column_rid)
$$ LANGUAGE SQL;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_fkeys') IS NULL THEN
  CREATE TABLE _ermrest.known_fkeys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE NOT NULL,
    schema_rid text NOT NULL REFERENCES _ermrest.known_schemas("RID") ON DELETE CASCADE,
    constraint_name text NOT NULL,
    fk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    pk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    column_rid_map jsonb NOT NULL, -- store as fk->pk RID hashmap
    delete_rule text NOT NULL,
    update_rule text NOT NULL,
    "comment" text,
    acls jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}',
    UNIQUE(schema_rid, constraint_name)
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_pseudo_fkeys') IS NULL THEN
  CREATE TABLE _ermrest.known_pseudo_fkeys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    constraint_name text NOT NULL UNIQUE,
    fk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    pk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    column_rid_map jsonb NOT NULL, -- store as fk->pk RID hashmap
    "comment" text,
    acls jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}'
  );
END IF;

CREATE OR REPLACE FUNCTION _ermrest.column_invalidate() RETURNS TRIGGER AS $$
BEGIN
  DELETE FROM _ermrest.known_keys k WHERE k.column_rids ? OLD."RID";
  DELETE FROM _ermrest.known_pseudo_keys k WHERE k.column_rids ? OLD."RID";
  DELETE FROM _ermrest.known_fkeys k
  WHERE _ermrest.fkey_fk_column_rids(k.column_rid_map) ? OLD."RID"
     OR _ermrest.fkey_pk_column_rids(k.column_rid_map) ? OLD."RID";
  DELETE FROM _ermrest.known_pseudo_fkeys k
  WHERE _ermrest.fkey_fk_column_rids(k.column_rid_map) ? OLD."RID"
     OR _ermrest.fkey_pk_column_rids(k.column_rid_map) ? OLD."RID";
  PERFORM _ermrest.model_version_bump();
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

IF COALESCE(
     (SELECT False
      FROM information_schema.triggers tg
      WHERE tg.event_object_schema = '_ermrest'
        AND tg.event_object_table = 'known_columns'
        AND tg.trigger_name = 'column_invalidate'
        AND tg.event_manipulation = 'DELETE'),
     True) THEN
  CREATE TRIGGER column_invalidate
    AFTER DELETE ON _ermrest.known_columns
    FOR EACH ROW EXECUTE PROCEDURE _ermrest.column_invalidate();
END IF;

CREATE OR REPLACE FUNCTION _ermrest.find_schema_rid(sname text) RETURNS text AS $$
  SELECT s."RID" FROM _ermrest.known_schemas s
  WHERE schema_name = $1;
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.find_table_rid(sname text, tname text) RETURNS text AS $$
  SELECT t."RID"
  FROM _ermrest.known_schemas s
  JOIN _ermrest.known_tables t ON (s."RID" = t.schema_rid)
  WHERE s.schema_name = $1 AND t.table_name = $2;
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.find_column_rid(sname text, tname text, cname text) RETURNS text AS $$
  SELECT c."RID"
  FROM _ermrest.known_schemas s
  JOIN _ermrest.known_tables t ON (s."RID" = t.schema_rid)
  JOIN _ermrest.known_columns c ON (t."RID" = c.table_rid)
  WHERE s.schema_name = $1 AND t.table_name = $2 AND c.column_name = $3;
$$ LANGUAGE SQL;

CREATE OR REPLACE VIEW _ermrest.introspect_schemas AS
  SELECT
    nc.oid,
    nc.nspname::text AS schema_name,
    obj_description(nc.oid)::text AS "comment"
  FROM pg_catalog.pg_namespace nc
  WHERE nc.nspname NOT IN ('information_schema', 'pg_toast', '_ermrest_history')
    AND nc.nspname !~ '^pg_(toast_)?temp_'
    AND NOT pg_is_other_temp_schema(nc.oid)
;

CREATE OR REPLACE VIEW _ermrest.introspect_types AS
  -- base types
  SELECT
    t.oid as "oid",
    s."RID" as "schema_rid",
    pg_catalog.format_type(t.oid, NULL)::text AS "type_name",
    NULL::text AS "array_element_type_rid",
    NULL::text AS "domain_element_type_rid",
    NULL::boolean AS "domain_notnull",
    NULL::text AS domain_default,
    pg_catalog.obj_description(t.oid, 'pg_type')::text as "comment"
  FROM pg_catalog.pg_type t
  JOIN _ermrest.known_schemas s ON (t.typnamespace = s.oid)
  WHERE t.typtype != 'd'::char
    AND t.typelem = 0::oid
    AND t.typrelid = 0
    AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_type el WHERE el.typarray = t.oid)
    AND pg_catalog.pg_type_is_visible(t.oid)

  UNION

  -- array types
  SELECT
    t.oid as "oid",
    s."RID" as "schema_rid",
    pg_catalog.format_type(t.oid, NULL)::text AS "type_name",
    ekt."RID" as "array_element_type_rid",
    NULL::text AS "domain_element_type_rid",
    NULL::boolean AS "domain_notnull",
    NULL::text AS domain_default,
    NULL::text AS "comment"
  FROM pg_catalog.pg_type t
  JOIN _ermrest.known_schemas s ON (t.typnamespace = s.oid)
  JOIN pg_catalog.pg_type et ON (et.typarray = t.oid)
  JOIN _ermrest.known_types ekt ON (et.oid = ekt.oid)
  WHERE t.typtype != 'd'::char
    AND et.typelem = 0::oid
    AND et.typrelid = 0
    AND pg_catalog.pg_type_is_visible(t.oid)

  UNION

  -- domains
  SELECT
    t.oid as "oid",
    s."RID" as "schema_rid",
    pg_catalog.format_type(t.oid, NULL)::text AS "type_name",
    NULL::text AS array_element_type_rid,
    ekt."RID" as "domain_element_type_rid",
    t.typnotnull AS "domain_notnull",
    t.typdefault::text AS "domain_value",
    d.description::text as "comment"
  FROM pg_catalog.pg_type t
  JOIN _ermrest.known_schemas s ON (t.typnamespace = s.oid)
  JOIN _ermrest.known_types ekt ON (t.typbasetype = ekt.oid)
  LEFT JOIN pg_catalog.pg_description d ON (d.classoid = t.tableoid AND d.objoid = t.oid AND d.objsubid = 0)
  WHERE t.typtype = 'd'
    AND pg_catalog.pg_type_is_visible(t.oid)
;

CREATE OR REPLACE VIEW _ermrest.introspect_tables AS
  SELECT
    c.oid AS oid,
    s."RID" AS schema_rid,
    c.relname::text AS table_name,
    c.relkind::text AS table_kind,
    obj_description(c.oid)::text AS "comment"
  FROM pg_catalog.pg_class c
  JOIN _ermrest.known_schemas s ON (c.relnamespace = s.oid)
  WHERE c.relkind IN ('r'::"char", 'v'::"char", 'f'::"char", 'm'::"char")
    AND s.schema_name != 'pg_catalog' -- we need types but not tables from this schema...
;

CREATE OR REPLACE VIEW _ermrest.introspect_columns AS
  SELECT
    kt."RID" AS table_rid,
    a.attnum::int AS column_num,
    a.attname::text AS column_name,
    kty."RID" AS type_rid,
    a.attnotnull AS not_null,
    pg_get_expr(ad.adbin, ad.adrelid)::text AS column_default,
    col_description(kt.oid, a.attnum)::text AS comment
  FROM pg_catalog.pg_attribute a
  JOIN _ermrest.known_tables kt ON (a.attrelid = kt.oid)
  JOIN _ermrest.known_types kty ON (a.atttypid = kty.oid)
  LEFT JOIN pg_catalog.pg_attrdef ad ON (a.attrelid = ad.adrelid AND a.attnum = ad.adnum)
  WHERE a.attnum > 0
    AND NOT a.attisdropped
;

CREATE OR REPLACE VIEW _ermrest.introspect_keys AS
  SELECT
    con.oid AS "oid",
    ks."RID" AS "schema_rid",
    con.conname::information_schema.sql_identifier::text AS constraint_name,
    kt."RID" AS "table_rid",
    con.conkey AS "conkey",
    cols.col_rids AS "column_rids",
    obj_description(con.oid)::text AS comment
  FROM pg_constraint con
  JOIN _ermrest.known_schemas ks ON (ks.oid = con.connamespace)
  JOIN pg_class pkcl ON (con.conrelid = pkcl.oid AND con.contype = ANY (ARRAY['u'::"char",'p'::"char"]))
  JOIN _ermrest.known_tables kt ON (pkcl.oid = kt.oid)
  JOIN LATERAL (
    SELECT
      jsonb_object_agg(kc."RID", NULL::text)
    FROM unnest(con.conkey) ca(attnum)
    JOIN _ermrest.known_columns kc ON (kc.table_rid = kt."RID" AND kc.column_num = ca.attnum)
  ) cols(col_rids) ON (True)
  WHERE has_table_privilege(pkcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
     OR has_any_column_privilege(pkcl.oid, 'INSERT, UPDATE, REFERENCES'::text)
;

CREATE OR REPLACE VIEW _ermrest.introspect_fkeys AS
  SELECT
    con.oid AS "oid",
    s."RID" AS schema_rid,
    con.conname::information_schema.sql_identifier::text AS constraint_name,
    fk_kt."RID" AS fk_table_rid,
    pk_kt."RID" AS pk_table_rid,
    cols.col_map AS column_rid_map,
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
  FROM pg_constraint con
  JOIN _ermrest.known_schemas s ON (s.oid = con.connamespace)
  JOIN pg_class fkcl ON (con.conrelid = fkcl.oid)
  JOIN pg_class kcl ON (con.confrelid = kcl.oid)
  JOIN _ermrest.known_tables fk_kt ON (fkcl.oid = fk_kt.oid)
  JOIN _ermrest.known_tables pk_kt ON (kcl.oid = pk_kt.oid)
  JOIN LATERAL (
    SELECT
      jsonb_object_agg(fk_kc."RID", pk_kc."RID")
    FROM unnest(con.conkey, con.confkey) ca(fk_attnum, pk_attnum)
    JOIN _ermrest.known_columns fk_kc ON (fk_kc.table_rid = fk_kt."RID" AND fk_kc.column_num = ca.fk_attnum)
    JOIN _ermrest.known_columns pk_kc ON (pk_kc.table_rid = pk_kt."RID" AND pk_kc.column_num = ca.pk_attnum)
  ) cols(col_map) ON (True)
  WHERE con.contype = 'f'::"char"
    AND (   pg_has_role(kcl.relowner, 'USAGE'::text) 
         OR has_table_privilege(kcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
         OR has_any_column_privilege(kcl.oid, 'INSERT, UPDATE, REFERENCES'::text))
    AND (   pg_has_role(fkcl.relowner, 'USAGE'::text) 
         OR has_table_privilege(fkcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
         OR has_any_column_privilege(fkcl.oid, 'INSERT, UPDATE, REFERENCES'::text))
;

CREATE OR REPLACE FUNCTION _ermrest.insert_types() RETURNS int AS $$
DECLARE
  had_changes int;
BEGIN
  WITH inserted AS (
    INSERT INTO _ermrest.known_types (
      oid,
      schema_rid,
      type_name,
      array_element_type_rid,
      domain_element_type_rid,
      domain_notnull,
      domain_default,
      "comment"
    )
    SELECT
      it.oid,
      it.schema_rid,
      it.type_name,
      it.array_element_type_rid,
      it.domain_element_type_rid,
      it.domain_notnull,
      it.domain_default,
      it."comment"
    FROM _ermrest.introspect_types it
    LEFT OUTER JOIN _ermrest.known_types kt ON (it.oid = kt.oid)
    WHERE kt.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  RETURN had_changes;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.table_change() RETURNS TRIGGER AS $$
DECLARE
  trid text;
BEGIN
  IF TG_OP IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE') THEN
    SELECT "RID" INTO trid FROM _ermrest.known_tables t WHERE t.oid = TG_RELID;
    PERFORM _ermrest.data_change_event(trid);
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.enable_table_history(table_rid text, heal_existing boolean) RETURNS void AS $func$
DECLARE
  sname text;
  tname text;
  htname text;
  otname text;
  ntname text;
  htable_exists bool;
  old_trigger_exists bool;
  new_trigger_exists bool;
  old_exclusion_exists bool;
BEGIN
  SELECT s.schema_name, t.table_name INTO sname, tname
  FROM _ermrest.known_tables t
  JOIN _ermrest.known_schemas s ON (t.schema_rid = s."RID")
  LEFT OUTER JOIN pg_catalog.pg_trigger tg ON (t.oid = tg.tgrelid AND tg.tgname = 'ermrest_table_change')
  WHERE t."RID" = $1
    AND t.table_kind = 'r'
    AND s.schema_name NOT IN ('pg_catalog', '_ermrest', '_ermrest_history')
    AND tg.tgrelid IS NULL;

  IF sname IS NOT NULL THEN
    EXECUTE
      'CREATE TRIGGER ermrest_table_change'
      ' AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON ' || quote_ident(sname) || '.' || quote_ident(tname) ||
      ' FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.table_change();' ;
  END IF;

  SELECT
    s.schema_name,
    t.table_name,
    it.relname IS NOT NULL,
    tgo.trigger_name IS NOT NULL,
    tgn.trigger_name IS NOT NULL,
    xc.conname IS NOT NULL
  INTO
    sname,
    tname,
    htable_exists,
    old_trigger_exists,
    new_trigger_exists,
    old_exclusion_exists
  FROM _ermrest.known_tables t
  JOIN _ermrest.known_schemas s ON (t.schema_rid = s."RID")
  JOIN pg_catalog.pg_namespace hs ON (hs.nspname = '_ermrest_history')
  LEFT OUTER JOIN pg_catalog.pg_class it
    ON (it.relnamespace = hs.oid
        AND it.relname = CASE WHEN s.schema_name = '_ermrest' THEN t.table_name ELSE 't' || t."RID" END)
  LEFT OUTER JOIN information_schema.triggers tgo
    ON (tgo.event_object_schema = s.schema_name
        AND tgo.event_object_table = t.table_name
	AND tgo.trigger_name = 'ermrest_history'
	AND tgo.event_manipulation = 'INSERT') -- ignore UPDATE/DELETE that would duplicate table names...
  LEFT OUTER JOIN information_schema.triggers tgn
    ON (tgn.event_object_schema = s.schema_name
        AND tgn.event_object_table = t.table_name
	AND tgn.trigger_name = 'ermrest_history_insert'
	AND tgn.event_manipulation = 'INSERT') -- ignore UPDATE/DELETE that would duplicate table names...
  LEFT OUTER JOIN pg_catalog.pg_constraint xc
    ON (xc.conname = it.relname || '_RID_during_excl'
        AND xc.connamespace = hs.oid
	AND xc.conrelid = it.oid
	AND xc.contype = 'x')
  WHERE t."RID" = $1
  AND t.table_kind = 'r'
  AND s.schema_name NOT IN ('pg_catalog')
  AND (SELECT True FROM _ermrest.known_columns c WHERE c.table_rid = t."RID" AND c.column_name = 'RID')
  AND (SELECT True FROM _ermrest.known_columns c WHERE c.table_rid = t."RID" AND c.column_name = 'RMT')
  AND (SELECT True FROM _ermrest.known_columns c WHERE c.table_rid = t."RID" AND c.column_name = 'RMB')
  ;

  IF sname IS NULL THEN RETURN; END IF;

  -- use literal table name for internal schema, but table_rid for user-generated data.
  -- we do the same for column names within the history jsonb rowdata blobs below.
  htname := CASE WHEN sname = '_ermrest' THEN tname ELSE 't' || table_rid END;
  otname := '_ermrest_oldtuples_t' || table_rid;
  ntname := '_ermrest_newtuples_t' || table_rid;

  IF NOT htable_exists
  THEN
    -- avoid doing dynamic SQL during every trigger event by generating a custom function per table here...
    EXECUTE
      'CREATE TABLE _ermrest_history.' || quote_ident(htname) || '('
      '  "RID" text NOT NULL,'
      '  during tstzrange NOT NULL,'
      '  "RMB" text,'
      '  rowdata jsonb NOT NULL,'
      '  UNIQUE("RID", during)'
      ');' ;
  END IF;

  IF old_exclusion_exists
  THEN
    EXECUTE 'ALTER TABLE _ermrest_history.' || quote_ident(htname) ||
      ' DROP CONSTRAINT ' || quote_ident(htname || '_RID_during_excl') || ','
      ' ADD CONSTRAINT ' || quote_ident(htname || '_RID_during_idx') || ' UNIQUE ("RID", during) ;' ;
  END IF;

  EXECUTE 'COMMENT ON TABLE _ermrest_history.' || quote_ident(htname) || ' IS '
    || quote_literal('History from ' || now()::text || ' for table ' || quote_ident(sname) || '.' || quote_ident(tname)) || ';';

  IF old_trigger_exists
  THEN
    EXECUTE 'DROP TRIGGER ermrest_history ON ' || quote_ident(sname) || '.' || quote_ident(tname) || ';' ;
  END IF;

  EXECUTE
    'CREATE OR REPLACE FUNCTION _ermrest_history.' || quote_ident('maintain_' || htname) || '() RETURNS TRIGGER AS $$'
    'DECLARE'
    '  rowsnap jsonb;'
    'BEGIN'
    '  IF TG_OP = ''DELETE'' THEN'
    '    UPDATE _ermrest_history.visible_entities ve'
    '    SET during = tstzrange(lower(ve.during), now(), ''[)'')'
    '    FROM ' || quote_ident(otname) || ' o'
    '    WHERE ve.entity_rid = o."RID"'
    '      AND ve.table_rid = ' || quote_literal(table_rid) ||
    '      AND upper(ve.during) IS NULL ;'
    '  END IF;'
    '  IF TG_OP IN (''UPDATE'', ''DELETE'') THEN'
    '    DELETE FROM _ermrest_history.' || quote_ident(htname) || ' t'
    '    USING ' || quote_ident(otname) || ' o'
    '    WHERE t."RID" = o."RID"'
    '      AND t.during = tstzrange(o."RMT", NULL, ''[)'')'
    '      AND o."RMT" >= now();'
    '    UPDATE _ermrest_history.' || quote_ident(htname) || ' t'
    '    SET during = tstzrange(o."RMT", now(), ''[)'')'
    '    FROM ' || quote_ident(otname) || ' o'
    '    WHERE t."RID" = o."RID"'
    '      AND t.during = tstzrange(o."RMT", NULL, ''[)'')'
    '      AND o."RMT" < now();'
    '  END IF;'
    '  IF TG_OP = ''INSERT'' THEN'
    '    INSERT INTO _ermrest_history.visible_entities (table_rid, entity_rid, during)'
    '    SELECT'
    '      ' || quote_literal(table_rid) || ','
    '      n."RID",'
    '      tstzrange(now(), NULL, ''[)'')'
    '    FROM ' || quote_ident(ntname) || ' n ;'
    '  END IF;'
    '  IF TG_OP IN (''INSERT'', ''UPDATE'') THEN'
    '    INSERT INTO _ermrest_history.' || quote_ident(htname) || ' ("RID", during, "RMB", rowdata)'
    '    SELECT'
    '      n."RID",'
    '      tstzrange(n."RMT", NULL, ''[)''),'
    '      n."RMB",'
    '      jsonb_object_agg(' || CASE WHEN sname = '_ermrest' THEN 'j.k' ELSE 'c."RID"::text' END || ', j.v)'
    '    FROM ' || quote_ident(ntname) || ' n'
    '    JOIN LATERAL jsonb_each(to_jsonb(n)) j (k, v) ON (True)'
    '    JOIN _ermrest.known_columns c ON (j.k = c.column_name AND c.table_rid = ' || quote_literal(table_rid) || ')'
    '    WHERE c.column_name NOT IN (''RID'', ''RMT'', ''RMB'')'
    '    GROUP BY n."RID", n."RMB", n."RMT" ;'
    '  END IF;'
    '  RETURN NULL;'
    'END; $$ LANGUAGE plpgsql;' ;

  IF NOT new_trigger_exists
  THEN
    EXECUTE
      'CREATE TRIGGER ermrest_history_insert AFTER INSERT ON ' || quote_ident(sname) || '.' || quote_ident(tname)
      || ' REFERENCING NEW TABLE AS ' || quote_ident(ntname)
      || ' FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest_history.' || quote_ident('maintain_' || htname) || '();';

    EXECUTE
      'CREATE TRIGGER ermrest_history_update AFTER UPDATE ON ' || quote_ident(sname) || '.' || quote_ident(tname)
      || ' REFERENCING OLD TABLE AS ' || quote_ident(otname) || ' NEW TABLE AS ' || quote_ident(ntname)
      || ' FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest_history.' || quote_ident('maintain_' || htname) || '();';

    EXECUTE
      'CREATE TRIGGER ermrest_history_delete AFTER DELETE ON ' || quote_ident(sname) || '.' || quote_ident(tname)
      || ' REFERENCING OLD TABLE AS ' || quote_ident(otname)
      || ' FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest_history.' || quote_ident('maintain_' || htname) || '();';
  END IF;

  -- this function becomes a no-op under steady state operations but handles one-time resolver upgrade
  PERFORM _ermrest.htable_to_visible_entities(table_rid, sname, tname, htname);

  -- skip healing if requested by caller and history table seems superficially active already
  IF htable_exists AND (new_trigger_exists OR old_trigger_exists) AND NOT heal_existing
  THEN
    RETURN;
  END IF;

  -- seal off open history tuples if we missed a delete or update
  EXECUTE
    'UPDATE _ermrest_history.' || quote_ident(htname) || ' h'
    ' SET during = tstzrange(lower(h.during), COALESCE(s."RMT", now()), ''[)'')'
    ' FROM ('
        ' SELECT h2."RID", h2.during, s."RMT"'
	' FROM _ermrest_history.' || quote_ident(htname) || ' h2'
        ' LEFT OUTER JOIN ' || quote_ident(sname) || '.' || quote_ident(tname) || ' s'
	'   ON (h2."RID" = s."RID")'
	' WHERE upper(h2.during) IS NULL'
	'   AND (lower(h2.during) < s."RMT" OR s."RID" IS NULL)'
    ' ) s'
    ' WHERE h."RID" = s."RID" AND h.during = s.during;' ;

  EXECUTE
    'UPDATE _ermrest_history.visible_entities ve'
    ' SET during = tstzrange(lower(ve.during), now(), ''[)'')'
    ' FROM ('
    '   SELECT ve.entity_rid, ve.table_rid, ve.during'
    '   FROM _ermrest_history.visible_entities ve'
    '   LEFT OUTER JOIN ' || quote_ident(sname) || '.' || quote_ident(tname) || ' s ON (ve.entity_rid = s."RID")'
    '   WHERE upper(ve.during) IS NULL'
    '     AND ve.table_rid = ' || quote_literal(table_rid) ||
    '     AND s."RID" IS NULL'
    ' ) s'
    ' WHERE ve.table_rid = s.table_rid'
    '   AND ve.entity_rid = s.entity_rid'
    '   AND upper(ve.during) IS NULL;' ;

  -- replicate latest live data if it's not already there
  EXECUTE
    'INSERT INTO _ermrest_history.' || quote_ident(htname) || '("RID", during, "RMB", rowdata)'
    'SELECT'
    '  t."RID",'
    '  tstzrange(t."RMT", NULL, ''[)''),'
    '  t."RMB",'
    '  (SELECT jsonb_object_agg(' || CASE WHEN sname = '_ermrest' THEN 'j.k' ELSE 'c."RID"::text' END || ', j.v)'
    '   FROM jsonb_each(to_jsonb(t)) j (k, v)'
    '   JOIN _ermrest.known_columns c ON (j.k = c.column_name AND c.table_rid = ' || quote_literal(table_rid) || ')'
    '   WHERE c.column_name NOT IN (''RID'', ''RMT''))'
    ' FROM ' || quote_ident(sname) || '.' || quote_ident(tname) || ' t'
    ' LEFT OUTER JOIN _ermrest_history.' || quote_ident(htname) || ' h'
    '  ON (t."RID" = h."RID" AND h.during = tstzrange(t."RMT", NULL, ''[)''))'
    ' WHERE h."RID" IS NULL;' ;

  EXECUTE
    'INSERT INTO _ermrest_history.visible_entities (entity_rid, table_rid, during)'
    ' SELECT s."RID", ' || quote_literal(table_rid) || ', tstzrange(s."RMT", NULL, ''[)'')'
    ' FROM ' || quote_ident(sname) || '.' || quote_ident(tname) || ' s'
    ' LEFT OUTER JOIN _ermrest_history.visible_entities ve'
    '   ON (s."RID" = ve.entity_rid AND ve.table_rid = ' || quote_literal(table_rid) || ' AND upper(ve.during) IS NULL)'
    ' WHERE ve.entity_RID IS NULL;' ;
END;
$func$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.enable_table_history(table_rid text) RETURNS void AS $$
BEGIN
  PERFORM _ermrest.enable_table_history(table_rid, False);
  RETURN;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.enable_table_histories(heal_existing boolean) RETURNS void AS $$
DECLARE
  looprow record;
BEGIN
  FOR looprow IN SELECT t."RID" FROM _ermrest.known_tables t
  LOOP
    -- this function is smart enough to skip views and idempotently create history tracking
    PERFORM _ermrest.enable_table_history(looprow."RID", heal_existing);
  END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.enable_table_histories() RETURNS void AS $$
BEGIN
  PERFORM _ermrest.enable_table_histories(False);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.rescan_introspect_by_oid(heal_existing boolean) RETURNS boolean AS $$
DECLARE
  model_changed boolean;
  had_changes int;
  srid text;
  new_sname text;
  new_tname text;
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
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_schemas k
    SET
      schema_name = v.schema_name,
      "comment" = v."comment",
      "RMT" = DEFAULT,
      "RMB" = DEFAULT
    FROM _ermrest.introspect_schemas v
    WHERE k.oid = v.oid
      AND ROW(k.schema_name, k."comment")
          IS DISTINCT FROM
          ROW(v.schema_name, v."comment")
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_schemas (oid, schema_name, "comment")
    SELECT i.oid, i.schema_name, i."comment"
    FROM _ermrest.introspect_schemas i
    LEFT OUTER JOIN _ermrest.known_schemas k ON (i.oid = k.oid)
    WHERE k.oid IS NULL
    RETURNING "RID"
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
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_types k
    SET
      schema_rid = v.schema_rid,
      type_name = v.type_name,
      array_element_type_rid = v.array_element_type_rid,
      domain_element_type_rid = v.domain_element_type_rid,
      domain_notnull = v.domain_notnull,
      domain_default = v.domain_default,
      "comment" = v."comment",
      "RMT" = DEFAULT,
      "RMB" = DEFAULT
    FROM _ermrest.introspect_types v
    WHERE k.oid = v.oid
      AND ROW(k.schema_rid, k.type_name, k.array_element_type_rid, k.domain_element_type_rid,
              k.domain_notnull, k.domain_default, k."comment")
          IS DISTINCT FROM
          ROW(v.schema_rid, v.type_name, v.array_element_type_rid, v.domain_element_type_rid,
	      v.domain_notnull, v.domain_default, v."comment")
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  -- need to do this 3x for base type, array, domain dependency chains
  had_changes := _ermrest.insert_types();
  model_changed := model_changed OR had_changes > 0;

  had_changes := _ermrest.insert_types();
  model_changed := model_changed OR had_changes > 0;

  had_changes := _ermrest.insert_types();
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible tables
  WITH deleted AS (
    DELETE FROM _ermrest.known_tables k
    USING (
      SELECT oid FROM _ermrest.known_tables
      EXCEPT SELECT oid FROM _ermrest.introspect_tables
    ) d
    WHERE k.oid = d.oid
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_tables k
    SET
      schema_rid = v.schema_rid,
      table_name = v.table_name,
      table_kind = v.table_kind,
      "comment" = v."comment",
      "RMT" = DEFAULT,
      "RMB" = DEFAULT
    FROM _ermrest.introspect_tables v
    WHERE k.oid = v.oid
      AND ROW(k.schema_rid, k.table_name, k.table_kind, k."comment")
          IS DISTINCT FROM
	  ROW(v.schema_rid, v.table_name, v.table_kind, v."comment")
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  FOR srid, new_tname IN
    INSERT INTO _ermrest.known_tables (oid, schema_rid, table_name, table_kind, "comment")
    SELECT
      it.oid,
      it.schema_rid,
      it.table_name,
      it.table_kind,
      it."comment"
    FROM _ermrest.introspect_tables it
    LEFT OUTER JOIN _ermrest.known_tables kt ON (it.oid = kt.oid)
    WHERE kt.oid IS NULL
    RETURNING schema_rid, table_name
  LOOP
    model_changed := True;
    -- for safety, disconnect existing trigger on newly arriving tables
    -- this addresses a possible inconsistency found when a DBA does 'ALTER ... RENAME ...' unsafely
    SELECT schema_name INTO new_sname FROM _ermrest.known_schemas WHERE "RID" = srid;
    EXECUTE
      'DROP TRIGGER IF EXISTS ermrest_history_insert'
      ' ON ' || quote_ident(new_sname) || '.' || quote_ident(new_tname) || ';'
      'DROP TRIGGER IF EXISTS ermrest_history_update'
      ' ON ' || quote_ident(new_sname) || '.' || quote_ident(new_tname) || ';'
      'DROP TRIGGER IF EXISTS ermrest_history_delete'
      ' ON ' || quote_ident(new_sname) || '.' || quote_ident(new_tname) || ';' ;
  END LOOP;

  -- sync up known with currently visible columns
  WITH deleted AS (
    DELETE FROM _ermrest.known_columns k
    USING (
      SELECT k."RID"
      FROM _ermrest.known_columns k
      LEFT OUTER JOIN _ermrest.introspect_columns i ON (k.table_rid = i.table_rid AND k.column_num = i.column_num)
      WHERE i.column_num IS NULL
    ) d
    WHERE k."RID" = d."RID"
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_columns k
    SET
      column_name = v.column_name,
      type_rid = v.type_rid,
      not_null = v.not_null,
      column_default = v.column_default,
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_columns v
    WHERE k.table_rid = v.table_rid AND k.column_num = v.column_num
      AND ROW(k.column_name, k.type_rid, k.not_null, k.column_default, k.comment)
          IS DISTINCT FROM
	  ROW(v.column_name, v.type_rid, v.not_null, v.column_default, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_columns (table_rid, column_num, column_name, type_rid, not_null, column_default, comment)
    SELECT ic.table_rid, ic.column_num, ic.column_name, ic.type_rid, ic.not_null, ic.column_default, ic.comment
    FROM _ermrest.introspect_columns ic
    LEFT OUTER JOIN _ermrest.known_columns kc ON (ic.table_rid = kc.table_rid AND ic.column_num = kc.column_num)
    WHERE kc.column_num IS NULL
    RETURNING "RID"
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
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_keys k
    SET
      schema_rid = v.schema_rid,
      constraint_name = v.constraint_name,
      table_rid = v.table_rid,
      column_rids = v.column_rids,
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_keys v
    WHERE k.oid = v.oid
      AND ROW(k.schema_rid, k.constraint_name, k.table_rid, k.column_rids, k.comment)
          IS DISTINCT FROM
	  ROW(v.schema_rid, v.constraint_name, v.table_rid, v.column_rids, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_keys (oid, schema_rid, constraint_name, table_rid, column_rids, comment)
    SELECT ik.oid, ik.schema_rid, ik.constraint_name, ik.table_rid, ik.column_rids, ik.comment
    FROM _ermrest.introspect_keys ik
    LEFT OUTER JOIN _ermrest.known_keys kk ON (ik.oid = kk.oid)
    WHERE kk.oid IS NULL
    RETURNING "RID"
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
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_fkeys k
    SET
      schema_rid = v.schema_rid,
      constraint_name = v.constraint_name,
      fk_table_rid = v.fk_table_rid,
      pk_table_rid = v.pk_table_rid,
      column_rid_map = v.column_rid_map,
      delete_rule = v.delete_rule,
      update_rule = v.update_rule,
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_fkeys v
    WHERE k.oid = v.oid
      AND ROW(k.schema_rid, k.constraint_name, k.fk_table_rid, k.pk_table_rid, k.column_rid_map, k.delete_rule, k.update_rule, k.comment)
          IS DISTINCT FROM
	  ROW(v.schema_rid, v.constraint_name, v.fk_table_rid, v.pk_table_rid, v.column_rid_map, v.delete_rule, v.update_rule, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_fkeys (oid, schema_rid, constraint_name, fk_table_rid, pk_table_rid, column_rid_map, delete_rule, update_rule, comment)
    SELECT i.oid, i.schema_rid, i.constraint_name, i.fk_table_rid, i.pk_table_rid, i.column_rid_map, i.delete_rule, i.update_rule, i.comment
    FROM _ermrest.introspect_fkeys i
    LEFT OUTER JOIN _ermrest.known_fkeys kfk ON (i.oid = kfk.oid)
    WHERE kfk.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  PERFORM _ermrest.enable_table_histories(heal_existing);

  RETURN model_changed;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.rescan_introspect_by_oid() RETURNS boolean AS $$
BEGIN
  RETURN _ermrest.rescan_introspect_by_oid(False);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.rescan_introspect_by_name(heal_existing boolean) RETURNS boolean AS $$
DECLARE
  model_changed boolean;
  had_changes int;
  srid text;
  new_sname text;
  new_tname text;
BEGIN
  model_changed := False;

  -- sync up known with currently visible schemas
  WITH deleted AS (
    DELETE FROM _ermrest.known_schemas k
    USING (
      SELECT schema_name FROM _ermrest.known_schemas
      EXCEPT SELECT schema_name FROM _ermrest.introspect_schemas
    ) d
    WHERE k.schema_name = d.schema_name
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_schemas k
    SET
      oid = v.oid,
      "comment" = v."comment",
      "RMT" = DEFAULT,
      "RMB" = DEFAULT
    FROM _ermrest.introspect_schemas v
    WHERE k.schema_name = v.schema_name
      AND ROW(k.oid, k."comment")
          IS DISTINCT FROM
          ROW(v.oid, v."comment")
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_schemas (oid, schema_name, "comment")
    SELECT i.oid, i.schema_name, i."comment"
    FROM _ermrest.introspect_schemas i
    LEFT OUTER JOIN _ermrest.known_schemas k ON (i.oid = k.oid)
    WHERE k.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible types
  WITH deleted AS (
    DELETE FROM _ermrest.known_types k
    USING (
      SELECT schema_rid, type_name FROM _ermrest.known_types
      EXCEPT SELECT schema_rid, type_name FROM _ermrest.introspect_types
    ) d
    WHERE k.type_name = d.type_name
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_types k
    SET
      oid = v.oid,
      array_element_type_rid = v.array_element_type_rid,
      domain_element_type_rid = v.domain_element_type_rid,
      domain_notnull = v.domain_notnull,
      domain_default = v.domain_default,
      "comment" = v."comment",
      "RMT" = DEFAULT,
      "RMB" = DEFAULT
    FROM _ermrest.introspect_types v
    WHERE k.schema_rid = v.schema_rid AND k.type_name = v.type_name
      AND ROW(k.oid, k.array_element_type_rid, k.domain_element_type_rid,
              k.domain_notnull, k.domain_default, k."comment")
          IS DISTINCT FROM
          ROW(v.oid, v.array_element_type_rid, v.domain_element_type_rid,
	      v.domain_notnull, v.domain_default, v."comment")
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  -- need to do this 3x for base type, array, domain dependency chains
  had_changes := _ermrest.insert_types();
  model_changed := model_changed OR had_changes > 0;

  had_changes := _ermrest.insert_types();
  model_changed := model_changed OR had_changes > 0;

  had_changes := _ermrest.insert_types();
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible tables
  WITH deleted AS (
    DELETE FROM _ermrest.known_tables k
    USING (
      SELECT schema_rid, table_name FROM _ermrest.known_tables
      EXCEPT SELECT schema_rid, table_name FROM _ermrest.introspect_tables
    ) d
    WHERE k.schema_rid = d.schema_rid AND k.table_name = d.table_name
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_tables k
    SET
      oid = v.oid,
      table_kind = v.table_kind,
      "comment" = v."comment",
      "RMT" = DEFAULT,
      "RMB" = DEFAULT
    FROM _ermrest.introspect_tables v
    WHERE k.schema_rid = v.schema_rid AND k.table_name = v.table_name
      AND ROW(k.oid, k.table_kind, k."comment")
          IS DISTINCT FROM
	  ROW(v.oid, v.table_kind, v."comment")
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  FOR srid, new_tname IN
    INSERT INTO _ermrest.known_tables (oid, schema_rid, table_name, table_kind, "comment")
    SELECT
      it.oid,
      it.schema_rid,
      it.table_name,
      it.table_kind,
      it."comment"
    FROM _ermrest.introspect_tables it
    JOIN _ermrest.known_schemas s ON (it.schema_rid = s."RID")
    LEFT OUTER JOIN _ermrest.known_tables kt ON (it.oid = kt.oid)
    WHERE kt.oid IS NULL
    RETURNING schema_rid, table_name
  LOOP
    model_changed := True;
    -- for safety, disconnect existing trigger on newly arriving tables
    -- this addresses a possible inconsistency found when a DBA does 'ALTER ... RENAME ...' unsafely
    SELECT schema_name INTO new_sname FROM _ermrest.known_schemas WHERE "RID" = srid;
    EXECUTE
      'DROP TRIGGER IF EXISTS ermrest_history_insert'
      ' ON ' || quote_ident(new_sname) || '.' || quote_ident(new_tname) || ';'
      'DROP TRIGGER IF EXISTS ermrest_history_update'
      ' ON ' || quote_ident(new_sname) || '.' || quote_ident(new_tname) || ';'
      'DROP TRIGGER IF EXISTS ermrest_history_delete'
      ' ON ' || quote_ident(new_sname) || '.' || quote_ident(new_tname) || ';' ;
  END LOOP;

  -- sync up known with currently visible columns
  WITH deleted AS (
    DELETE FROM _ermrest.known_columns k
    USING (
      SELECT k."RID"
      FROM _ermrest.known_columns k
      LEFT OUTER JOIN _ermrest.introspect_columns i ON (k.table_rid = i.table_rid AND k.column_name = i.column_name)
      WHERE i.column_name IS NULL
    ) d
    WHERE k."RID" = d."RID"
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_columns k
    SET
      column_num = v.column_num,
      type_rid = v.type_rid,
      not_null = v.not_null,
      column_default = v.column_default,
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_columns v
    WHERE k.table_rid = v.table_rid AND k.column_name = v.column_name
      AND ROW(k.column_num, k.type_rid, k.not_null, k.column_default, k.comment)
          IS DISTINCT FROM
	  ROW(v.column_num, v.type_rid, v.not_null, v.column_default, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_columns (table_rid, column_num, column_name, type_rid, not_null, column_default, comment)
    SELECT ic.table_rid, ic.column_num, ic.column_name, ic.type_rid, ic.not_null, ic.column_default, ic.comment
    FROM _ermrest.introspect_columns ic
    LEFT OUTER JOIN _ermrest.known_columns kc ON (ic.table_rid = kc.table_rid AND ic.column_num = kc.column_num)
    WHERE kc.column_num IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible keys
  WITH deleted AS (
    DELETE FROM _ermrest.known_keys k
    USING (
      SELECT schema_rid, constraint_name FROM _ermrest.known_keys
      EXCEPT SELECT schema_rid, constraint_name FROM _ermrest.introspect_keys
    ) d
    WHERE k.schema_rid = d.schema_rid AND k.constraint_name = d.constraint_name
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_keys k
    SET
      oid = v.oid,
      table_rid = v.table_rid,
      column_rids = v.column_rids,
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_keys v
    WHERE k.schema_rid = v.schema_rid AND k.constraint_name = v.constraint_name
      AND ROW(k.oid, k.table_rid, k.column_rids, k.comment)
          IS DISTINCT FROM
	  ROW(v.oid, v.table_rid, v.column_rids, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_keys (oid, schema_rid, constraint_name, table_rid, column_rids, comment)
    SELECT ik.oid, ik.schema_rid, ik.constraint_name, ik.table_rid, ik.column_rids, ik.comment
    FROM _ermrest.introspect_keys ik
    LEFT OUTER JOIN _ermrest.known_keys kk ON (ik.oid = kk.oid)
    WHERE kk.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible foreign keys
  WITH deleted AS (
    DELETE FROM _ermrest.known_fkeys k
    USING (
      SELECT schema_rid, constraint_name FROM _ermrest.known_fkeys
      EXCEPT SELECT schema_rid, constraint_name FROM _ermrest.introspect_fkeys
    ) d
    WHERE k.schema_rid = d.schema_rid AND k.constraint_name = d.constraint_name
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_fkeys k
    SET
      oid = v.oid,
      fk_table_rid = v.fk_table_rid,
      pk_table_rid = v.pk_table_rid,
      column_rid_map = v.column_rid_map,
      delete_rule = v.delete_rule,
      update_rule = v.update_rule,
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_fkeys v
    WHERE k.schema_rid = v.schema_rid AND k.constraint_name = v.constraint_name
      AND ROW(k.oid, k.fk_table_rid, k.pk_table_rid, k.column_rid_map, k.delete_rule, k.update_rule, k.comment)
          IS DISTINCT FROM
	  ROW(v.oid, v.fk_table_rid, v.pk_table_rid, v.column_rid_map, v.delete_rule, v.update_rule, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_fkeys (oid, schema_rid, constraint_name, fk_table_rid, pk_table_rid, column_rid_map, delete_rule, update_rule, comment)
    SELECT i.oid, i.schema_rid, i.constraint_name, i.fk_table_rid, i.pk_table_rid, i.column_rid_map, i.delete_rule, i.update_rule, i.comment
    FROM _ermrest.introspect_fkeys i
    LEFT OUTER JOIN _ermrest.known_fkeys kfk ON (i.oid = kfk.oid)
    WHERE kfk.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  PERFORM _ermrest.enable_table_histories(heal_existing);

  RETURN model_changed;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.rescan_introspect_by_name() RETURNS boolean AS $$
BEGIN
  RETURN _ermrest.rescan_introspect_by_name(False);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.model_version_bump() RETURNS void AS $$
DECLARE
  last_ts timestamptz;
BEGIN
  SELECT ts INTO last_ts FROM _ermrest.model_last_modified ORDER BY ts DESC LIMIT 1;
  IF last_ts > now() THEN
    -- paranoid integrity check in case we aren't using SERIALIZABLE isolation somehow...
    RAISE EXCEPTION serialization_failure USING MESSAGE = 'ERMrest model version clock reversal!';
  ELSIF last_ts = now() THEN
    RETURN;
  ELSE
    IF last_ts < now() THEN
      DELETE FROM _ermrest.model_last_modified;
    END IF;
    INSERT INTO _ermrest.model_last_modified (ts) VALUES (now());
    INSERT INTO _ermrest.model_modified (ts) VALUES (now());
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.model_change_event(heal_existing boolean) RETURNS void AS $$
BEGIN
  PERFORM _ermrest.rescan_introspect_by_name(heal_existing);
  PERFORM _ermrest.model_version_bump();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.model_change_event() RETURNS void AS $$
BEGIN
  PERFORM _ermrest.model_change_event(False);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.model_change_event_by_oid() RETURNS void AS $$
BEGIN
  PERFORM _ermrest.rescan_introspect_by_oid();
  PERFORM _ermrest.model_version_bump();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.amended_version_bump(during tstzrange) RETURNS void AS $$
DECLARE
  last_ts timestamptz;
BEGIN
  SELECT ts INTO last_ts FROM _ermrest.catalog_amended ORDER BY ts DESC LIMIT 1;
  IF last_ts > now() THEN
    -- paranoid integrity check in case we aren't using SERIALIZABLE isolation somehow...
    RAISE EXCEPTION serialization_failure USING MESSAGE = 'ERMrest amendment clock reversal!';
  ELSIF last_ts = now() THEN
    RETURN;
  ELSE
    INSERT INTO _ermrest.catalot_amended (ts, during) VALUES (now(), during);
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.data_change_event(tab_rid text) RETURNS void AS $$
DECLARE
  last_ts timestamptz;
BEGIN
  SELECT ts INTO last_ts FROM _ermrest.table_last_modified t WHERE t.table_rid = $1;
  IF last_ts > now() THEN
    -- paranoid integrity check in case we aren't using SERIALIZABLE isolation somehow...
    RAISE EXCEPTION serialization_failure USING MESSAGE = 'ERMrest table version clock reversal!';
  ELSIF last_ts = now() THEN
    RETURN;
  ELSE
    IF last_ts < now() THEN
      DELETE FROM _ermrest.table_last_modified t WHERE t.table_rid = $1;
    END IF;
    INSERT INTO _ermrest.table_last_modified (table_rid, ts) VALUES ($1, now());
    INSERT INTO _ermrest.table_modified (table_rid, ts) VALUES ($1, now());
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.data_change_event(sname text, tname text) RETURNS void AS $$
  SELECT _ermrest.data_change_event((
    SELECT t."RID"
    FROM _ermrest.known_tables t
    JOIN _ermrest.known_schemas s ON (t.schema_rid = s."RID")
    WHERE s.schema_name = $1 AND t.table_name = $2
  ));
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.create_aclbinding_invalidate_function(rname text) RETURNS text AS $def$
DECLARE
  fname text;
BEGIN
  fname = rname || '_acl_binding_invalidate';
  EXECUTE
    'CREATE OR REPLACE FUNCTION _ermrest.' || fname || '() RETURNS TRIGGER AS $$'
    'BEGIN'
    '  DELETE FROM _ermrest.known_' || rname || '_acl_bindings b WHERE b."RID" = OLD.binding_rid;'
    '  PERFORM _ermrest.model_version_bump();'
    '  RETURN NULL;'
    'END;'
    '$$ LANGUAGE plpgsql;';
  RETURN fname;
END;
$def$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.create_aclbinding_table(rname text, fkcname text, fkrname text) RETURNS void AS $def$
DECLARE
  tname1 text;
  tname2 text;
  tname3 text;
  tname4 text;
  fname text;
BEGIN
  tname1 := 'known_' || rname || '_acl_bindings';
  IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = tname1) IS NULL THEN
    EXECUTE
      'CREATE TABLE _ermrest.' || tname1 || '('
      '  "RID" ermrest_rid PRIMARY KEY DEFAULT nextval(''_ermrest.rid_seq''),'
      '  "RCT" ermrest_rct NOT NULL DEFAULT now(),'
      '  "RMT" ermrest_rmt NOT NULL DEFAULT now(),'
      '  "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),'
      '  "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),'
      '  ' || fkcname || '_rid text NOT NULL REFERENCES _ermrest.known_' || fkrname || '("RID") ON DELETE CASCADE,'
      '  binding_name text NOT NULL,'
      '  scope_members text[],'
      '  access_types text[],'
      '  projection_type text,'
      '  projection_column_rid text REFERENCES _ermrest.known_columns("RID"),'
      '  CHECK( (scope_members IS NOT NULL AND access_types IS NOT NULL AND projection_type IS NOT NULL AND projection_column_rid IS NOT NULL)'
      '        OR (scope_members IS NULL AND access_types IS NULL AND projection_type IS NULL AND projection_column_rid IS NULL) ),'
      '  UNIQUE(' || fkcname || '_rid, binding_name)'
      ');' ;
  END IF;

  fname := _ermrest.create_aclbinding_invalidate_function(rname);

  tname2 := 'known_' || rname || '_acl_binding_elems';
  IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = tname2) IS NULL THEN
    EXECUTE
      'CREATE TABLE _ermrest.' || tname2 || '('
      '  "RID" ermrest_rid PRIMARY KEY DEFAULT nextval(''_ermrest.rid_seq''),'
      '  "RCT" ermrest_rct NOT NULL DEFAULT now(),'
      '  "RMT" ermrest_rmt NOT NULL DEFAULT now(),'
      '  "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),'
      '  "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),'
      '  binding_rid text NOT NULL REFERENCES _ermrest.' || tname1 || '("RID") ON DELETE CASCADE,'
      '  position int4 NOT NULL,'
      '  context text,'
      '  alias text,'
      '  inbound boolean NOT NULL,'
      '  fkey_rid text REFERENCES _ermrest.known_fkeys("RID") ON DELETE CASCADE,'
      '  pseudo_fkey_rid text REFERENCES _ermrest.known_pseudo_fkeys("RID") ON DELETE CASCADE,'
      '  CHECK(fkey_rid IS NULL OR pseudo_fkey_rid IS NULL),'
      '  CHECK(fkey_rid IS NOT NULL OR pseudo_fkey_rid IS NOT NULL),'
      '  UNIQUE(binding_rid, position)'
      ');'
      'CREATE TRIGGER acl_binding_invalidate'
      '  AFTER DELETE ON _ermrest.' || tname2 ||
      '  FOR EACH ROW EXECUTE PROCEDURE _ermrest.' || fname || '();';
  END IF;

  tname3 := 'known_' || rname || '_acl_binding_combiners';
  IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = tname3) IS NULL THEN
    EXECUTE
      'CREATE TABLE _ermrest.' || tname3 || '('
      '  "RID" ermrest_rid PRIMARY KEY DEFAULT nextval(''_ermrest.rid_seq''),'
      '  "RCT" ermrest_rct NOT NULL DEFAULT now(),'
      '  "RMT" ermrest_rmt NOT NULL DEFAULT now(),'
      '  "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),'
      '  "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),'
      '  binding_rid text NOT NULL REFERENCES _ermrest.' || tname1 || '("RID") ON DELETE CASCADE,'
      '  parent_position int4,'
      '  position int4 NOT NULL,'
      '  combiner text NOT NULL,'
      '  negate boolean NOT NULL,'
      '  UNIQUE(binding_rid, position)'
      ');';
  END IF;

  tname4 := 'known_' || rname || '_acl_binding_filters';
  IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = tname4) IS NULL THEN
    EXECUTE
      'CREATE TABLE _ermrest.' || tname4 || '('
      '  "RID" ermrest_rid PRIMARY KEY DEFAULT nextval(''_ermrest.rid_seq''),'
      '  "RCT" ermrest_rct NOT NULL DEFAULT now(),'
      '  "RMT" ermrest_rmt NOT NULL DEFAULT now(),'
      '  "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),'
      '  "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),'
      '  binding_rid text NOT NULL REFERENCES _ermrest.' || tname1 || '("RID") ON DELETE CASCADE,'
      '  parent_position int4,'
      '  position int4 NOT NULL,'
      '  context text,'
      '  column_rid text NOT NULL REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE,'
      '  operator text,'
      '  operand text,'
      '  negate boolean NOT NULL,'
      '  UNIQUE(binding_rid, position)'
      ');'
      'CREATE TRIGGER acl_binding_invalidate'
      '  AFTER DELETE ON _ermrest.' || tname4 ||
      '  FOR EACH ROW EXECUTE PROCEDURE _ermrest.' || fname || '();';
  END IF;
END;
$def$ LANGUAGE plpgsql;

PERFORM _ermrest.create_aclbinding_table('table', 'table', 'tables');
PERFORM _ermrest.create_aclbinding_table('column', 'column', 'columns');
PERFORM _ermrest.create_aclbinding_table('fkey', 'fkey', 'fkeys');
PERFORM _ermrest.create_aclbinding_table('pseudo_fkey', 'fkey', 'pseudo_fkeys');

-- this is a helper function for the subsequent aclbinding_parse() function...
CREATE OR REPLACE FUNCTION _ermrest.aclbinding_filter_parse(next_pos integer, current_scope_table_rid text, env jsonb, doc jsonb, parent_pos integer default NULL) RETURNS jsonb AS $$
DECLARE
  projection_combiners jsonb;
  projection_filters jsonb;
  subresult jsonb;

  combiner text;
  children jsonb;
  child jsonb;
  negate jsonb;

  cname text;
  column_rid text;
  context_alias text;
  operator jsonb;
  operand jsonb;

  pos integer;
BEGIN
  projection_combiners := '[]';
  projection_filters := '[]';

  negate := doc->'negate';
  if jsonb_typeof(negate) = 'boolean' OR jsonb_typeof(negate) IS NULL THEN
    -- pass
  ELSE
    RAISE SQLSTATE '22000' USING DETAIL = negate, HINT = 'Invalid "negate" boolean value in ACL binding path.';
  END IF;

  pos := next_pos;
  next_pos := next_pos + 1;

  IF doc ?| '{and,or}' THEN
    IF doc ? 'and' THEN
      combiner := 'and';
    ELSE
      combiner := 'or';
    END IF;

    children = doc->combiner;

    IF jsonb_typeof(children) = 'array' THEN
      FOR child IN SELECT jsonb_array_elements(children) LOOP
        projection_combiners := projection_combiners || jsonb_build_object(
	  'position', pos,
	  'parent_position', parent_pos,
	  'combiner', combiner,
	  'negate', negate
	);
        subresult := _ermrest.aclbinding_filter_parse(next_pos, current_scope_table_rid, env, child, pos);
	next_pos := (subresult->>'next_pos')::integer;
	projection_combiners := projection_combiners || (subresult->'projection_combiners');
	projection_filters := projection_filters || (subresult->'projection_filters');
      END LOOP;
    ELSE
      RAISE SQLSTATE '22000' USING DETAIL = children, HINT = 'ACL binding logical combiner must provide an array of filters.';
    END IF;
  ELSE
    IF jsonb_typeof(doc->'filter') = 'array'
    AND jsonb_typeof((doc->'filter')->0) = 'string'
    AND jsonb_typeof((doc->'filter')->1) = 'string' THEN
      context_alias := (doc->'filter')->>0;
      cname := (doc->'filter')->>1;

      IF env ? context_alias THEN
        current_scope_table_rid = env->>context_alias;
      ELSE
        RAISE SQLSTATE '22000' USING DETAIL = context_alias, HINT = 'Reference to unbound context in ACL binding projection.';
      END IF;
    ELSIF jsonb_typeof(doc->'filter') = 'string' THEN
      context_alias := NULL;
      cname := doc->>'filter';
    ELSE
      RAISE SQLSTATE '22000' USING DETAIL = doc, HINT = 'ACL binding "filter" field must be a column name string or [alias, name] string pair.';
    END IF;

    SELECT c."RID" INTO column_rid
    FROM _ermrest.known_columns c
    WHERE c.column_name = cname
      AND c.table_rid = current_scope_table_rid;

    IF column_rid IS NULL THEN
      RAISE SQLSTATE '23000' USING DETAIL = cname, HINT = 'Filter column not found.';
    END IF;

    operator := doc->'operator';
    operand := doc->'operand';

    projection_filters := projection_filters || jsonb_build_object(
      'position', pos,
      'parent_position', parent_pos,
      'context', context_alias,
      'column_rid', column_rid,
      'operator', operator,
      'operand', operand,
      'negate', negate
    );
  END IF;

  RETURN jsonb_build_object(
    'next_pos', next_pos,
    'projection_combiners', projection_combiners,
    'projection_filters', projection_filters
  );
END;
$$ LANGUAGE plpgsql;

-- this generic function parses an ACL binding doc and returns a flattened version
-- ready for insertion into policy storage tables
CREATE OR REPLACE FUNCTION _ermrest.aclbinding_parse(binding_name text, env jsonb, doc jsonb) RETURNS jsonb AS $$
DECLARE
  scope_members jsonb;
  access_types jsonb;
  projection_type jsonb;

  projection_elems jsonb;
  projection_combiners jsonb;
  projection_filters jsonb;

  next_pos integer;
  current_scope_table_rid text;
  proj_column_rid text;
  proj_column_istext boolean;

  proj jsonb;
  proj_len integer;
  elem jsonb;
  elem_pos integer;
  context text;

  elem_fkeyname jsonb;
  elem_fkey_rid text;
  elem_fkt_rid text;
  elem_pkt_rid text;
  inbound boolean;
  ealias text;

  filters jsonb;
  tmp_a text[];
BEGIN
  IF jsonb_typeof(doc) = 'object' THEN
    scope_members = doc->'scope_acl';
    access_types = doc->'types';
    projection_type = doc->'projection_type';

    current_scope_table_rid := env->>'base';
    next_pos := 1;

    IF jsonb_typeof(doc->'projection') = 'array' THEN
      proj := doc->'projection';
    ELSIF jsonb_typeof(doc->'projection') = 'string' THEN
      proj := to_jsonb(ARRAY[ doc->'projection' ]);
    ELSE
      RAISE SQLSTATE '22000' USING DETAIL = doc->'projection', HINT = 'ACL binding projection must be a JSON array or a bare column name.';
    END IF;

    proj_len := jsonb_array_length(proj);

    projection_elems = '[]';
    projection_combiners = '[]';
    projection_filters = '[]';

    FOR idx IN 0 .. proj_len - 2 LOOP
      elem := proj->>idx;
      elem_pos := next_pos;

      IF jsonb_typeof(elem) = 'object' THEN
        IF jsonb_typeof(elem->'context') = 'string' THEN
	  context := elem->>'context';
	  IF env ? context THEN
	    current_scope_table_rid := env->context;
	  ELSE
	    RAISE SQLSTATE '22000' USING DETAIL = context, HINT = 'Reference to unbound context in ACL binding path.';
	  END IF;
	ELSIF elem ? 'context' THEN
	  RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'Invalid "context" name in ACL binding path element.';
	ELSE
	  context := NULL;
	END IF;

        IF elem ?| '{outbound,inbound}'::text[] THEN
	  -- this element is a joining table instance
          IF elem ? 'inbound' THEN
	    elem_fkeyname := elem->'inbound';
	    inbound := True;
	  ELSE
	    elem_fkeyname := elem->'outbound';
	    inbound := False;
	  END IF;

          IF jsonb_typeof(elem_fkeyname) = 'array' THEN
            IF jsonb_typeof(elem_fkeyname->1) = 'string' THEN
	      -- pass
	    ELSE
	      RAISE SQLSTATE '22000' USING DETAIL = elem_fkeyname, HINT = 'Foreign key names in ACL binding paths must contain two strings.';
	    END IF;

	    IF elem_fkeyname->0 = '""'::jsonb THEN
	      SELECT fk."RID", fk.fk_table_rid, fk.pk_table_rid
	      INTO elem_fkey_rid, elem_fkt_rid, elem_pkt_rid
	      FROM _ermrest.known_pseudo_fkeys fk
	      WHERE fk.constraint_name = elem_fkeyname->>1;
	    ELSE
              IF jsonb_typeof(elem_fkeyname->0) = 'string' THEN
  	        -- pass
	      ELSE
	        RAISE SQLSTATE '22000' USING DETAIL = elem_fkeyname, HINT = 'Foreign key names in ACL binding paths must contain two strings.';
	      END IF;
	      SELECT fk."RID", fk.fk_table_rid, fk.pk_table_rid
	      INTO elem_fkey_rid, elem_fkt_rid, elem_pkt_rid
	      FROM _ermrest.known_fkeys fk
	      JOIN _ermrest.known_schemas s ON (fk.schema_rid = s."RID")
	      WHERE fk.constraint_name = elem_fkeyname->>1
	        AND s.schema_name = elem_fkeyname->>0;
	    END IF;
	  ELSE
	    RAISE SQLSTATE '22000' USING DETAIL = elem_fkeyname, HINT = 'Foreign key names in ACL binding paths must be JSON arrays.';
	  END IF;

          IF elem_fkey_rid IS NULL THEN
	    RAISE SQLSTATE '23000' USING DETAIL = elem_fkeyname, HINT = 'Foreign key not found.';
	  END IF;

          IF inbound AND elem_pkt_rid = current_scope_table_rid THEN
	    current_scope_table_rid := elem_fkt_rid;
	  ELSIF (NOT inbound) AND elem_fkt_rid = current_scope_table_rid THEN
            current_scope_table_rid := elem_pkt_rid;
          ELSE
	    RAISE '22000' USING DETAIL = jsonb_build_object(
	      'elem', elem,
	      'inbound', inbound,
	      'current_scope_table_rid', current_scope_table_rid,
	      'elem_fkey_rid', elem_fkey_rid,
	      'elem_pkt_rid', elem_pkt_rid,
	      'elem_fkt_rid', elem_fkt_rid,
	      'elem_fkeyname->>1', elem_fkeyname->>1
	    ), HINT = 'Named foreign key does not have requested relationship to path context in ACL binding.';
	  END IF;

          IF jsonb_typeof(elem->'alias') = 'string' THEN
	    ealias := elem->>'alias';
	    IF env ? elias THEN
	      RAISE '22000' USING DETAIL = ealias, HINT = 'ACL binding path element "alias" collides with existing alias.';
	    END IF;
	    env := env || jsonb_build_object(ealias, current_scope_table_rid);
	  ELSIF elem ? 'alias' THEN
	    RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'Invalid "alias" name in ACL binding path element.';
	  ELSE
	    ealias := NULL;
	  END IF;

          projection_elems := projection_elems || jsonb_build_object(
	    'position', elem_pos,
	    'context', context,
	    'alias', ealias,
	    'inbound', inbound,
	    'fkey_rid', CASE WHEN elem_fkeyname->0 = '""' THEN NULL ELSE elem_fkey_rid END,
	    'pseudo_fkey_rid', CASE WHEN elem_fkeyname->0 = '""' THEN elem_fkey_rid ELSE NULL END
	  );

          next_pos := next_pos + 1;

	ELSIF elem ?| '{and,or,filter}'::text[] THEN

	  filters := _ermrest.aclbinding_filter_parse(next_pos, current_scope_table_rid, env, elem);
	  next_pos := (filters->>'next_pos')::integer;
	  projection_combiners := projection_combiners || (filters->'projection_combiners');
	  projection_filters := projection_filters || (filters->'projection_filters');

	ELSE
	  RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'ACL binding projection path element not understood.';
	END IF;
      ELSE
        RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'ACL binding projection inner path element must be a JSON object.';
      END IF;
    END LOOP;

    SELECT
      c."RID",
      ct.type_name = 'text' OR det.type_name = 'text' OR aet.type_name = 'text'
    INTO proj_column_rid, proj_column_istext
    FROM _ermrest.known_columns c
    JOIN _ermrest.known_types ct ON (c.type_rid = ct."RID")
    LEFT OUTER JOIN _ermrest.known_types det ON (ct.domain_element_type_rid = det."RID")
    LEFT OUTER JOIN _ermrest.known_types aet ON (ct.array_element_type_rid = aet."RID" OR det.array_element_type_rid = aet."RID")
    WHERE c.column_name = proj->>-1
      AND c.table_rid = current_scope_table_rid;

    IF proj_column_rid IS NULL THEN
      RAISE SQLSTATE '23000' USING DETAIL = proj->>-1, HINT = 'Projected column not found.';
    END IF;

    IF jsonb_typeof(scope_members) IS NULL OR jsonb_typeof(scope_members) = 'null' THEN
      scope_members := '["*"]';
    ELSIF jsonb_typeof(scope_members) = 'array' THEN
      SELECT array_agg(jsonb_typeof(e)) INTO tmp_a
      FROM jsonb_array_elements(scope_members) a(e);
      IF tmp_a != '{string}' THEN
        RAISE SQLSTATE '22000' USING DETAIL = scope_members, HINT = 'ACL binding "scope_acl" must be an array of strings.';
      END IF;
    ELSE
      RAISE SQLSTATE '22000' USING DETAIL = scope_members, HINT = 'ACL binding "scope_acl" must be an array of strings.';
    END IF;

    IF projection_type = '"acl"'::jsonb AND proj_column_istext THEN
      -- pass
    ELSIF projection_type = '"nonnull"'::jsonb THEN
      -- pass
    ELSIF projection_type IS NOT NULL THEN
      RAISE SQLSTATE '22000' USING DETAIL = projection_type, HINT = 'Invalid "projection_type" in ACL binding.';
    ELSE
      projection_type := CASE WHEN proj_column_istext THEN 'acl' ELSE 'nonnull' END;
    END IF;

    RETURN jsonb_build_object(
      'binding_name', binding_name,
      'scope_members', scope_members,
      'access_types', access_types,
      'projection_type', projection_type,
      'projection_column_rid', proj_column_rid,
      'projection_elems', projection_elems,
      'projection_combiners', projection_combiners,
      'projection_filters', projection_filters
    );
  ELSIF doc = 'false'::jsonb THEN
    RETURN jsonb_build_object(
      'binding_name', binding_name
    );
  ELSE
    RAISE SQLSTATE '22000' USING DETAIL = doc, HINT = 'Outer ACL binding document must be a JSON object.';
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.insert_aclbinding_generic(rname text, fkcname text, subject_rid text, base_rid text, binding_name text, binding jsonb) RETURNS text AS $$
DECLARE
  tname1 text;
  tname2 text;
  tname3 text;
  tname4 text;

  flattened jsonb;
  entry jsonb;

  binding_rid text;
BEGIN
  tname1 := 'known_' || rname || '_acl_bindings';
  tname2 := 'known_' || rname || '_acl_binding_elems';
  tname3 := 'known_' || rname || '_acl_binding_combiners';
  tname4 := 'known_' || rname || '_acl_binding_filters';

  flattened := jsonb_strip_nulls(_ermrest.aclbinding_parse(binding_name, jsonb_build_object('base', base_rid), binding));

  EXECUTE
    'INSERT INTO _ermrest.' || tname1 || '(' || fkcname || '_rid, binding_name, scope_members, access_types, projection_type, projection_column_rid)'
    'SELECT'
    '  ' || quote_literal(subject_rid) || ','
    '  $1->>''binding_name'','
    '  (SELECT array_agg(a.e ORDER BY a.n) FROM jsonb_array_elements_text($1->''scope_members'') WITH ORDINALITY a(e, n)),'
    '  (SELECT array_agg(a.e ORDER BY a.n) FROM jsonb_array_elements_text($1->''access_types'') WITH ORDINALITY a(e, n)),'
    '  $1->>''projection_type'','
    '  $1->>''projection_column_rid'''
    'RETURNING "RID";'
  INTO binding_rid
  USING flattened;

  FOR entry IN SELECT e FROM jsonb_array_elements(COALESCE(flattened->'projection_elems', '[]')) WITH ORDINALITY a(e, n) ORDER BY n LOOP
    EXECUTE
      'INSERT INTO _ermrest.' || tname2 || '(binding_rid, position, context, alias, inbound, fkey_rid, pseudo_fkey_rid)'
      'VALUES ('
      '  $1,'
      '  ($2->>''position'')::integer,'
      '  $2->>''context'','
      '  $2->>''alias'','
      '  ($2->>''inbound'')::boolean,'
      '  $2->>''fkey_rid'','
      '  $2->>''pseudo_fkey_rid'' );'
    USING binding_rid, entry;
  END LOOP;

  FOR entry IN SELECT e FROM jsonb_array_elements(COALESCE(flattened->'projection_combiners', '[]')) WITH ORDINALITY a(e, n) ORDER BY n LOOP
    EXECUTE
      'INSERT INTO _ermrest.' || tname3 || '(binding_rid, parent_position, position, combiner, negate)'
      'VALUES ('
      '  $1,'
      '  ($2->>''parent_position'')::integer,'
      '  ($2->>''position'')::integer,'
      '  $2->>''combiner'','
      '  COALESCE(($2->>''negate'')::boolean, False) );'
    USING binding_rid, entry;
  END LOOP;

  FOR entry IN SELECT e FROM jsonb_array_elements(COALESCE(flattened->'projection_filters', '[]')) WITH ORDINALITY a(e, n) ORDER BY n LOOP
    EXECUTE
      'INSERT INTO _ermrest.' || tname4 || '(binding_rid, parent_position, position, context, column_rid, operator, operand, negate)'
      'VALUES ('
      '  $1,'
      '  ($2->>''parent_position'')::integer,'
      '  ($2->>''position'')::integer,'
      '  $2->>''context'','
      '  $2->>''column_rid'','
      '  $2->>''operator'','
      '  $2->>''operand'','
      '  COALESCE(($2->>''negate'')::boolean, False) );'
    USING binding_rid, entry;
  END LOOP;

  RETURN binding_rid;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.insert_table_aclbinding(table_rid text, binding_name text, binding jsonb) RETURNS text AS $$
BEGIN
  RETURN _ermrest.insert_aclbinding_generic(
    'table',
    'table',
    table_rid,
    table_rid,
    binding_name,
    binding
  );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.insert_column_aclbinding(column_rid text, binding_name text, binding jsonb) RETURNS text AS $$
DECLARE
  table_rid text;
BEGIN
  SELECT c.table_rid INTO table_rid FROM _ermrest.known_columns c WHERE c."RID" = column_rid;

  RETURN _ermrest.insert_aclbinding_generic(
    'column',
    'column',
    column_rid,
    table_rid,
    binding_name,
    binding
  );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.insert_fkey_aclbinding(fkey_rid text, binding_name text, binding jsonb) RETURNS text AS $$
DECLARE
  table_rid text;
BEGIN
  SELECT pk_table_rid INTO table_rid FROM _ermrest.known_fkeys WHERE "RID" = fkey_rid;

  RETURN _ermrest.insert_aclbinding_generic(
    'fkey',
    'fkey',
    fkey_rid,
    table_rid,
    binding_name,
    binding
  );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.insert_pseudo_fkey_aclbinding(fkey_rid text, binding_name text, binding jsonb) RETURNS text AS $$
DECLARE
  table_rid text;
BEGIN
  SELECT pk_table_rid INTO table_rid FROM _ermrest.known_pseudo_fkeys WHERE "RID" = fkey_rid;

  RETURN _ermrest.insert_aclbinding_generic(
    'pseudo_fkey',
    'fkey',
    fkey_rid,
    table_rid,
    binding_name,
    binding
  );
END;
$$ LANGUAGE plpgsql;


-- this is by-name to handle possible dump/restore scenarios
-- a DBA who does many SQL DDL RENAME events and wants to link by OID rather than name
-- should call _ermrest.model_change_by_oid() **before** running ermrest-deploy
SET CONSTRAINTS ALL DEFERRED;
PERFORM _ermrest.model_change_event();
SET CONSTRAINTS ALL IMMEDIATE;

CREATE OR REPLACE FUNCTION _ermrest.column_name_from_rid(column_rid text, ts timestamptz default NULL) RETURNS text STABLE AS $$
DECLARE
  cname text;
BEGIN
  IF ts IS NULL THEN
    SELECT c.column_name
    INTO cname
    FROM _ermrest.known_columns c
    WHERE c."RID" = column_rid;
  ELSE
    SELECT (c.rowdata)->>'column_name'
    INTO cname
    FROM _ermrest_history.known_columns c
    WHERE c."RID" = column_rid
      AND c.during @> ts;
  END IF;
  RETURN cname;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.aclbinding_filter_serialize(part jsonb, parent_children_map jsonb, ts timestamptz default NULL) RETURNS jsonb AS $$
DECLARE
  child_list jsonb;
  cname jsonb;
BEGIN
  IF part ? 'combiner' THEN
    -- convert each child using this same serialization function recursively
    SELECT jsonb_agg(
      _ermrest.aclbinding_filter_serialize(c, parent_children_map, ts)
      ORDER BY s.n
    )
    INTO child_list
    FROM jsonb_array_elements(parent_children_map->(part->>'position')) WITH ORDINALITY s(c, n);

    RETURN jsonb_strip_nulls(jsonb_build_object(
      part->>'combiner', child_list,
      'negate', part->'negate' = 'true'::jsonb
    ));
  ELSE
    -- convert this leaf filter node as base case
    cname := to_jsonb(_ermrest.column_name_from_rid(part->>'column_rid', ts));

    IF part->'context_alias' != 'null'::jsonb THEN
      cname := to_jsonb(ARRAY[ part->'context_alias', cname ]);
    END IF;

    RETURN jsonb_strip_nulls(jsonb_build_object(
      'filter', cname,
      'operator', part->'operator',
      'operand', part->'operand',
      'negate', part->'negate' = 'true'::jsonb
    ));
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.fkey_name_from_rids(fkey_rid text, pseudo_fkey_rid text, ts timestamptz default NULL) RETURNS jsonb STABLE AS $$
DECLARE
  sname text;
  cname text;
BEGIN
  IF ts IS NULL THEN
    IF fkey_rid IS NOT NULL THEN
      SELECT s.schema_name, fk.constraint_name
      INTO sname, cname
      FROM _ermrest.known_fkeys fk
      JOIN _ermrest.known_schemas s ON (s."RID" = fk.schema_rid)
      WHERE fk."RID" = fkey_rid;
    ELSE
      SELECT '', fk.constraint_name
      INTO sname, cname
      FROM _ermrest.known_pseudo_fkeys fk
      WHERE fk."RID" = pseudo_fkey_rid;
    END IF;
  ELSE
    IF fkey_rid IS NOT NULL THEN
      SELECT (s.rowdata)->>'schema_name', (fk.rowdata)->>'constraint_name'
      INTO sname, cname
      FROM _ermrest_history.known_fkeys fk
      JOIN _ermrest_history.known_schemas s ON (s."RID" = (fk.rowdata)->>'schema_rid')
      WHERE fk."RID" = fkey_rid
        AND fk.during @> ts
	AND s.during @> ts;
    ELSE
      SELECT '', (fk.rowdata)->>'constraint_name'
      INTO sname, cname
      FROM _ermrest_history.known_pseudo_fkeys fk
      WHERE fk."RID" = pseudo_fkey_rid
        AND fk.during @> ts;
    END IF;

  END IF;
  RETURN to_jsonb( ARRAY[ sname, cname ]::text[] );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.aclbinding_serialize(binding_record jsonb, elems jsonb, combiners jsonb, filters jsonb, ts timestamptz default NULL) RETURNS jsonb AS $$
DECLARE
  projection jsonb;
  children jsonb;
BEGIN
  IF binding_record->'access_types' = 'null' THEN
    -- we NULL out required fields to represent a "false" binding mask
    RETURN 'false'::jsonb;
  END IF;

  -- build parent->children map needed below to reconstruct expressiont trees
  SELECT jsonb_object_agg(parent_pos, child_list)
  INTO children
  FROM (
    SELECT
      c->>'parent_position',
      COALESCE(jsonb_agg(c ORDER BY (c->>'position')::integer), '{}'::jsonb) AS child_list
    FROM (
      SELECT * FROM jsonb_array_elements(combiners) s(c)
      UNION ALL
      SELECT * FROM jsonb_array_elements(filters) s(c)
    ) s(c)
    WHERE COALESCE(c->'parent_position', 'null'::jsonb) != 'null'::jsonb
    GROUP BY c->>'parent_position'
  ) s(parent_pos, child_list);

  IF COALESCE(binding_record->'projection_type', 'null'::jsonb) = 'null'::jsonb THEN
    RETURN jsonb_build_object(
      'projection', 'false'::jsonb
    );
  END IF;

  -- rebuild projection path which is ordered roots of forest plus final column name
  SELECT COALESCE(jsonb_agg(
    CASE
      WHEN p ?| '{combiner,column_rid}' THEN _ermrest.aclbinding_filter_serialize(p, children, ts)
      ELSE jsonb_strip_nulls(jsonb_build_object(
        'context', p->'context',
	'alias', p->'alias',
	CASE
	  WHEN (p->>'inbound')::boolean
	  THEN 'inbound'
	  ELSE 'outbound'
	END::text,
	_ermrest.fkey_name_from_rids((s.p)->>'fkey_rid', (s.p)->>'pseudo_fkey-rid', ts)
      ))
    END
    ORDER BY (p->>'position')::integer
  ), '[]'::jsonb) || to_jsonb(_ermrest.column_name_from_rid(binding_record->>'projection_column_rid'))
  INTO projection
  FROM (
    SELECT * FROM jsonb_array_elements(elems) s(p)
    UNION ALL
    SELECT * FROM jsonb_array_elements(combiners) s(p)
    UNION ALL
    SELECT * FROM jsonb_array_elements(filters) s(p)
  ) s(p)
  WHERE COALESCE(p->'parent_position', 'null'::jsonb) = 'null'::jsonb;

  RETURN jsonb_build_object(
    'scope_acl', $1->'scope_members',
    'types', $1->'access_types',
    'projection_type', $1->'projection_type',
    'projection', projection
  );
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION _ermrest.create_historical_aclbinding_func(rname text, cname text) RETURNS void AS $def$
DECLARE
  s text;
BEGIN
  EXECUTE
    'CREATE OR REPLACE FUNCTION _ermrest.known_' || rname || '_acl_bindings(ts timestamptz default NULL)'
    'RETURNS TABLE (' || cname || ' text,' || 'binding_name text, binding jsonb) AS $$'
    'BEGIN'
    '  IF ts IS NULL THEN'
    '    RETURN QUERY'
    '    SELECT'
    '      b.' || cname || ','
    '      b.binding_name,'
    '      _ermrest.aclbinding_serialize('
    '        row_to_json(b.*)::jsonb,'
    '        COALESCE(e.parts, ''[]''::jsonb),'
    '        COALESCE(c.parts, ''[]''::jsonb),'
    '        COALESCE(f.parts, ''[]''::jsonb)'
    '      )'
    '    FROM _ermrest.known_' || rname || '_acl_bindings b'
    '    LEFT JOIN ('
    '      SELECT s.binding_rid, jsonb_agg(row_to_json(s.*))'
    '      FROM _ermrest.known_' || rname || '_acl_binding_elems s'
    '      GROUP BY s.binding_rid'
    '    ) e (binding_rid, parts) ON (b."RID" = e.binding_rid)'
    '    LEFT JOIN ('
    '      SELECT s.binding_rid, jsonb_agg(row_to_json(s.*))'
    '      FROM _ermrest.known_' || rname || '_acl_binding_combiners s'
    '      GROUP BY s.binding_rid'
    '    ) c (binding_rid, parts) ON (b."RID" = c.binding_rid)'
    '    LEFT JOIN ('
    '      SELECT s.binding_rid, jsonb_agg(row_to_json(s.*))'
    '      FROM _ermrest.known_' || rname || '_acl_binding_filters s'
    '      GROUP BY s.binding_rid'
    '    ) f (binding_rid, parts) ON (b."RID" = f.binding_rid);'
    '  ELSE'
    '    RETURN QUERY'
    '    SELECT'
    '      (b.rowdata)->>''' || cname || ''','
    '      (b.rowdata)->>''binding_name'','
    '      _ermrest.aclbinding_serialize('
    '        b.rowdata,'
    '        COALESCE(e.parts, ''[]''::jsonb),'
    '        COALESCE(c.parts, ''[]''::jsonb),'
    '        COALESCE(f.parts, ''[]''::jsonb)'
    '      )'
    '    FROM _ermrest_history.known_' || rname || '_acl_bindings b'
    '    LEFT JOIN ('
    '      SELECT (s.rowdata)->>''binding_rid'', jsonb_agg(s.rowdata)'
    '      FROM _ermrest_history.known_' || rname || '_acl_binding_elems s'
    '      WHERE s.during @> ts'
    '      GROUP BY (s.rowdata)->>''binding_rid'''
    '    ) e (binding_rid, parts) ON (b."RID" = e.binding_rid)'
    '    LEFT JOIN ('
    '      SELECT (s.rowdata)->>''binding_rid'', jsonb_agg(s.rowdata)'
    '      FROM _ermrest_history.known_' || rname || '_acl_binding_combiners s'
    '      WHERE s.during @> ts'
    '      GROUP BY (s.rowdata)->>''binding_rid'''
    '    ) c (binding_rid, parts) ON (b."RID" = c.binding_rid)'
    '    LEFT JOIN ('
    '      SELECT (s.rowdata)->>''binding_rid'', jsonb_agg(s.rowdata)'
    '      FROM _ermrest_history.known_' || rname || '_acl_binding_filters s'
    '      WHERE s.during @> ts'
    '      GROUP BY (s.rowdata)->>''binding_rid'''
    '    ) f (binding_rid, parts) ON (b."RID" = f.binding_rid)'
    '    WHERE b.during @> ts;'
    '  END IF;'
    'END;'
    '$$ LANGUAGE plpgsql;' ;
END;
$def$ LANGUAGE plpgsql;

PERFORM _ermrest.create_historical_aclbinding_func('table', 'table_rid');
PERFORM _ermrest.create_historical_aclbinding_func('column', 'column_rid');
PERFORM _ermrest.create_historical_aclbinding_func('fkey', 'fkey_rid');
PERFORM _ermrest.create_historical_aclbinding_func('pseudo_fkey', 'fkey_rid');

CREATE OR REPLACE FUNCTION _ermrest.known_catalogs(ts timestamptz)
RETURNS TABLE ("RID" text, acls jsonb, annotations jsonb) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.acls, s.annotations
  FROM _ermrest.known_catalogs s
  WHERE s."RID" = '0';
ELSE
  RETURN QUERY
  SELECT s."RID", sr.acls, sr.annotations
  FROM _ermrest_history.known_catalogs s,
  LATERAL jsonb_to_record(s.rowdata) sr (acls jsonb, annotations jsonb)
  WHERE s.during @> COALESCE($1, now())
    AND s."RID" = '0';
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_schemas(ts timestamptz)
RETURNS TABLE ("RID" text, schema_name text, comment text, acls jsonb, annotations jsonb) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.schema_name, s.comment, s.acls, s.annotations
  FROM _ermrest.known_schemas s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.schema_name, sr.comment, sr.acls, sr.annotations
  FROM _ermrest_history.known_schemas s,
  LATERAL jsonb_to_record(s.rowdata) sr (schema_name text, comment text, acls jsonb, annotations jsonb)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_types(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, type_name text, array_element_type_rid text, domain_element_type_rid text, domain_notnull boolean, domain_default text, comment text) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.schema_rid, s.type_name, s.array_element_type_rid, s.domain_element_type_rid, s.domain_notnull, s.domain_default, s.comment
  FROM _ermrest.known_types s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.schema_rid, sr.type_name, sr.array_element_type_rid, sr.domain_element_type_rid, sr.domain_notnull, sr.domain_default, sr.comment
  FROM _ermrest_history.known_types s,
  LATERAL jsonb_to_record(s.rowdata) sr (schema_rid text, type_name text, array_element_type_rid text, domain_element_type_rid text, domain_notnull boolean, domain_default text, comment text)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_columns(ts timestamptz)
RETURNS TABLE ("RID" text, table_rid text, column_num int, column_name text, type_rid text, not_null boolean, column_default text, comment text, acls jsonb, annotations jsonb) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.table_rid, s.column_num, s.column_name, s.type_rid, s.not_null, s.column_default, s.comment, s.acls, s.annotations
  FROM _ermrest.known_columns s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.table_rid, sr.column_num, sr.column_name, sr.type_rid, sr.not_null, sr.column_default, sr.comment, sr.acls, sr.annotations
  FROM _ermrest_history.known_columns s,
  LATERAL jsonb_to_record(s.rowdata) sr (table_rid text, column_num int, column_name text, type_rid text, not_null boolean, column_default text, comment text, acls jsonb, annotations jsonb)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_notnulls(ts timestamptz)
RETURNS TABLE ("RID" text, column_rid text) AS $$
BEGIN
IF ts is NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.column_rid
  FROM _ermrest.known_pseudo_notnulls s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.column_rid
  FROM _ermrest_history.known_pseudo_notnulls s,
  LATERAL jsonb_to_record(s.rowdata) sr (column_rid text)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_tables(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, table_name text, table_kind text, comment text, acls jsonb, annotations jsonb) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.schema_rid, s.table_name, s.table_kind, s.comment, s.acls, s.annotations
  FROM _ermrest.known_tables s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.schema_rid, sr.table_name, sr.table_kind, sr.comment, sr.acls, sr.annotations
  FROM _ermrest_history.known_tables s,
  LATERAL jsonb_to_record(s.rowdata) sr (schema_rid text, table_name text, table_kind text, comment text, acls jsonb, annotations jsonb)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_tables_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, table_name text, table_kind text, comment text, acls jsonb, annotations jsonb, columns jsonb[]) AS $$
SELECT
  t."RID",
  t.schema_rid,
  t.table_name,
  t.table_kind,
  t."comment",
  t.acls,
  t.annotations,
  COALESCE(c.columns, ARRAY[]::jsonb[]) AS columns
FROM _ermrest.known_tables($1) t
LEFT OUTER JOIN (
  SELECT
    c.table_rid,
    array_agg(to_jsonb(c.*) ORDER BY c.column_num)::jsonb[] AS columns
  FROM _ermrest.known_columns($1) c
  GROUP BY c.table_rid
) c ON (t."RID" = c.table_rid);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.record_new_table(schema_rid text, tname text, acls jsonb DEFAULT '{}', annotations jsonb DEFAULT '{}') RETURNS text AS $$
DECLARE
  t_rid text;
  s_name text;
BEGIN
  INSERT INTO _ermrest.known_tables (oid, schema_rid, table_name, table_kind, "comment", acls, annotations)
  SELECT t.oid, t.schema_rid, t.table_name, t.table_kind, t."comment", $3, $4
  FROM _ermrest.introspect_tables t
  WHERE t.schema_rid = $1 AND t.table_name = $2
  RETURNING "RID" INTO t_rid;

  INSERT INTO _ermrest.known_columns (table_rid, column_num, column_name, type_rid, not_null, column_default, "comment")
  SELECT c.table_rid, c.column_num, c.column_name, c.type_rid, c.not_null, c.column_default, c."comment"
  FROM _ermrest.introspect_columns c
  WHERE c.table_rid = t_rid;

  PERFORM _ermrest.enable_table_history(t_rid);
  PERFORM _ermrest.model_version_bump();
  PERFORM _ermrest.data_change_event(t_rid);

  SELECT s.schema_name INTO s_name
  FROM _ermrest.known_schemas s
  WHERE s."RID" = schema_rid;

  EXECUTE 'CREATE TRIGGER ermrest_syscols BEFORE INSERT OR UPDATE ON '
    || quote_ident(s_name) || '.' || quote_ident(tname)
    || ' FOR EACH ROW EXECUTE PROCEDURE _ermrest.maintain_row();';

  RETURN t_rid;
END;
$$ LANGUAGE plpgsql;

IF (SELECT True FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ermrest_client') IS NULL THEN
  CREATE TABLE public.ermrest_client (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    id text UNIQUE NOT NULL,
    display_name text,
    full_name text,
    email text,
    client_obj jsonb NOT NULL
  );
  PERFORM _ermrest.record_new_table(_ermrest.find_schema_rid('public'), 'ermrest_client');
  UPDATE _ermrest.known_tables
  SET acls = '{"insert": [], "update": [], "delete": [], "select": [], "enumerate": []}'
  WHERE "RID" = _ermrest.find_table_rid('public', 'ermrest_client');
END IF;

CREATE OR REPLACE FUNCTION _ermrest.known_keys(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, table_rid text, column_rids jsonb, comment text, annotations jsonb) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.schema_rid, s.constraint_name, s.table_rid, s.column_rids, s.comment, s.annotations
  FROM _ermrest.known_keys s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.schema_rid, sr.constraint_name, sr.table_rid, sr.column_rids, sr.comment, sr.annotations
  FROM _ermrest_history.known_keys s,
  LATERAL jsonb_to_record(s.rowdata) sr (schema_rid text, constraint_name text, table_rid text, column_rids jsonb, comment text, annotations jsonb)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_keys(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, table_rid text, column_rids jsonb, comment text, annotations jsonb) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.constraint_name, s.table_rid, s.column_rids, s.comment, s.annotations
  FROM _ermrest.known_pseudo_keys s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.constraint_name, sr.table_rid, sr.column_rids, sr.comment, sr.annotations
  FROM _ermrest_history.known_pseudo_keys s,
  LATERAL jsonb_to_record(s.rowdata) sr (constraint_name text, table_rid text, column_rids jsonb, comment text, annotations jsonb)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_keys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, table_rid text, column_rids text[], comment text, annotations jsonb) AS $$
SELECT
  k."RID",
  k.schema_rid,
  k.constraint_name,
  k.table_rid,
  kc.column_rids,
  k."comment",
  k.annotations
FROM _ermrest.known_keys($1) k
JOIN LATERAL (
  SELECT
    array_agg(kc.column_rid ORDER BY kc.column_rid)::text[] AS column_rids
  FROM jsonb_each(k.column_rids) kc(column_rid, null_value)
) kc ON (True)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_keys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, table_rid text, column_rids text[], comment text, annotations jsonb) AS $$
SELECT
  k."RID",
  k.constraint_name,
  k.table_rid,
  kc.column_rids,
  k."comment",
  k.annotations
FROM _ermrest.known_pseudo_keys($1) k
JOIN LATERAL (
  SELECT
    array_agg(kc.column_rid ORDER BY kc.column_rid)::text[] AS column_rids
  FROM jsonb_each(k.column_rids) kc(column_rid, null_value)
) kc ON (True)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_fkeys(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, fk_table_rid text, pk_table_rid text, column_rid_map jsonb, delete_rule text, update_rule text, comment text, acls jsonb, annotations jsonb) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.schema_rid, s.constraint_name, s.fk_table_rid, s.pk_table_rid, s.column_rid_map, s.delete_rule, s.update_rule, s.comment, s.acls, s.annotations
  FROM _ermrest.known_fkeys s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.schema_rid, sr.constraint_name, sr.fk_table_rid, sr.pk_table_rid, sr.column_rid_map, sr.delete_rule, sr.update_rule, sr.comment, sr.acls, sr.annotations
  FROM _ermrest_history.known_fkeys s,
  LATERAL jsonb_to_record(s.rowdata) sr (schema_rid text, constraint_name text, fk_table_rid text, pk_table_rid text, column_rid_map jsonb, delete_rule text, update_rule text, comment text, acls jsonb, annotations jsonb)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_fkeys(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, fk_table_rid text, pk_table_rid text, column_rid_map jsonb, comment text, acls jsonb, annotations jsonb) AS $$
BEGIN
IF ts IS NULL THEN
  RETURN QUERY
  SELECT s."RID"::text, s.constraint_name, s.fk_table_rid, s.pk_table_rid, s.column_rid_map, s.comment, s.acls, s.annotations
  FROM _ermrest.known_pseudo_fkeys s;
ELSE
  RETURN QUERY
  SELECT s."RID", sr.constraint_name, sr.fk_table_rid, sr.pk_table_rid, sr.column_rid_map, sr.comment, sr.acls, sr.annotations
  FROM _ermrest_history.known_pseudo_fkeys s,
  LATERAL jsonb_to_record(s.rowdata) sr (constraint_name text, fk_table_rid text, pk_table_rid text, column_rid_map jsonb, comment text, acls jsonb, annotations jsonb)
  WHERE s.during @> COALESCE($1, now());
END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.known_fkeys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, fk_table_rid text, fk_column_rids text[], pk_table_rid text, pk_column_rids text[], delete_rule text, update_rule text, comment text, acls jsonb, annotations jsonb) AS $$
SELECT
  fk."RID",
  fk.schema_rid,
  fk.constraint_name,
  fk.fk_table_rid,
  fkcp.fk_column_rids,
  fk.pk_table_rid,
  fkcp.pk_column_rids,
  fk.delete_rule,
  fk.update_rule,
  fk."comment",
  fk.acls,
  fk.annotations
FROM _ermrest.known_fkeys($1) fk
JOIN LATERAL (
  SELECT
    array_agg(fk_column_rid ORDER BY fkcp.fk_column_rid)::text[] AS fk_column_rids,
    array_agg(pk_column_rid ORDER BY fkcp.fk_column_rid)::text[] AS pk_column_rids
  FROM jsonb_each_text(fk.column_rid_map) fkcp (fk_column_rid, pk_column_rid)
) fkcp ON (True)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_fkeys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, fk_table_rid text, fk_column_rids text[], pk_table_rid text, pk_column_rids text[], comment text, acls jsonb, annotations jsonb) AS $$
SELECT
  fk."RID",
  fk.constraint_name,
  fk.fk_table_rid,
  fkcp.fk_column_rids,
  fk.pk_table_rid,
  fkcp.pk_column_rids,
  fk."comment",
  fk.acls,
  fk.annotations
FROM _ermrest.known_pseudo_fkeys($1) fk
JOIN LATERAL (
  SELECT
    array_agg(fk_column_rid ORDER BY fkcp.fk_column_rid)::text[] AS fk_column_rids,
    array_agg(pk_column_rid ORDER BY fkcp.fk_column_rid)::text[] AS pk_column_rids
  FROM jsonb_each_text(fk.column_rid_map) fkcp (fk_column_rid, pk_column_rid)
) fkcp ON (True)
$$ LANGUAGE SQL;

FOR looprow IN
SELECT s.schema_name, t.table_name
FROM _ermrest.known_tables t
JOIN _ermrest.known_schemas s ON (t.schema_rid = s."RID")
LEFT OUTER JOIN pg_catalog.pg_trigger tg ON (tg.tgrelid = t.oid AND tg.tgname = 'ermrest_syscols')
WHERE tg.tgrelid IS NULL
  AND s.schema_name NOT IN ('pg_catalog', '_ermrest_history')
  AND t.table_kind = 'r'
  AND (SELECT True FROM _ermrest.known_columns c WHERE c.table_rid = t."RID" AND c.column_name = 'RID')
LOOP
  EXECUTE 'CREATE TRIGGER ermrest_syscols BEFORE INSERT OR UPDATE ON '
    || quote_ident(looprow.schema_name) || '.' || quote_ident(looprow.table_name)
    || ' FOR EACH ROW EXECUTE PROCEDURE _ermrest.maintain_row();';
END LOOP;

-- disable one-time conversion that MAY have been done above
CREATE OR REPLACE FUNCTION _ermrest.htable_to_visible_entities(trid text, sname text, tname text, htname text) RETURNS void AS $$
BEGIN
  -- do nothing during normal operations...
  RETURN;
END;
$$ LANGUAGE plpgsql;

---------- Lazy service introspection support

CREATE OR REPLACE FUNCTION _ermrest.live_catalogs(roles text[])
RETURNS TABLE (acls jsonb, annotations jsonb, rights jsonb) AS $$
SELECT
  c.acls,
  c.annotations,
  to_jsonb(c_rights) AS rights
FROM _ermrest.known_catalogs c
JOIN LATERAL _ermrest.rights(_ermrest.to_acls(c.acls), $1) c_rights ON (True)
WHERE c."RID" = '0'
  AND c_rights."enumerate";
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.live_schema(sname text, roles text[])
RETURNS TABLE ("RID" text, schema_name text, comment text, acls jsonb, annotations jsonb, rights jsonb) AS $$
SELECT
  s."RID"::text,
  s.schema_name,
  s.comment,
  s.acls,
  s.annotations,
  to_jsonb(s_rights) AS rights
FROM _ermrest.known_schemas s
JOIN  _ermrest.known_catalogs c ON (c."RID" = '0')
JOIN LATERAL _ermrest.rights(_ermrest.to_acls(c.acls, s.acls), $2) s_rights ON (True)
-- catalog is enumerable or we wouldn't be running this!
WHERE s.schema_name = $1
  AND s_rights."enumerate";
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.live_table_columns(trid text, roles text[])
RETURNS TABLE ("RID" text, table_rid text, column_num int, column_name text, type_rid text, not_null boolean, column_default text, comment text, acls jsonb, annotations jsonb, rights jsonb) AS $$
SELECT
  c."RID"::text,
  c.table_rid,
  c.column_num,
  c.column_name,
  c.type_rid,
  c.not_null,
  c.column_default,
  c.comment,
  c.acls,
  c.annotations,
  to_jsonb(c_rights) AS rights
FROM _ermrest.known_tables t
JOIN _ermrest.known_schemas s ON (t.schema_rid = s."RID")
JOIN _ermrest.known_catalogs cat ON (cat."RID" = '0')
JOIN _ermrest.known_columns c ON (c.table_rid = t."RID")
JOIN LATERAL _ermrest.rights(_ermrest.to_acls(cat.acls, s.acls, t.acls, c.acls), $2) c_rights ON (True)
-- catalog, schema, and table are enumerable or we wouldn't be running this!
WHERE t."RID" = $1
  AND c_rights."enumerate";
$$ LANGUAGE SQL;



CREATE OR REPLACE FUNCTION _ermrest.live_table(srid text, tname text, roles text[])
RETURNS TABLE ("RID" text, schema_rid text, table_name text, table_kind text, comment text, coldocs jsonb[], acls jsonb, annotations jsonb, rights jsonb) AS $$
SELECT
  t."RID"::text,
  t.schema_rid,
  t.table_name,
  t.table_kind,
  t.comment,
  (SELECT COALESCE(array_agg(to_jsonb(col.*) ORDER BY col.column_num), ARRAY[]::jsonb[]) FROM _ermrest.live_table_columns(t."RID", $3) col),
  t.acls,
  t.annotations,
  to_jsonb(t_rights) AS rights
FROM _ermrest.known_tables t
JOIN _ermrest.known_schemas s ON (t.schema_rid = s."RID")
JOIN _ermrest.known_catalogs c ON (c."RID" = '0')
JOIN LATERAL _ermrest.rights(_ermrest.to_acls(c.acls, s.acls, t.acls), $3) t_rights ON (True)
-- catalog and schema are enumerable or we wouldn't be running this!
WHERE t.schema_rid = $1
  AND t.table_name = $2
  AND t_rights."enumerate";
$$ LANGUAGE SQL;


CREATE OR REPLACE FUNCTION _ermrest.past_catalogs(ts timestamptz, roles text[])
RETURNS TABLE (acls jsonb, annotations jsonb, rights jsonb) AS $$
SELECT
  (c.rowdata)->'acls',
  (c.rowdata)->'annotations',
  to_jsonb(c_rights) AS rights
FROM _ermrest_history.known_catalogs c
JOIN LATERAL _ermrest.rights(_ermrest.to_acls((c.rowdata)->'acls'), $2) c_rights ON (True)
WHERE c.during @> $1
  AND c."RID" = '0'
  AND c_rights."enumerate";
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.past_schema(sname text, ts timestamptz, roles text[])
RETURNS TABLE ("RID" text, schema_name text, comment text, acls jsonb, annotations jsonb, rights jsonb) AS $$
SELECT
  s."RID"::text,
  (s.rowdata)->>'schema_name',
  (s.rowdata)->>'comment',
  (s.rowdata)->'acls',
  (s.rowdata)->'annotations',
  to_jsonb(s_rights) AS rights
FROM _ermrest.past_catalogs($2, $3) c
JOIN _ermrest_history.known_schemas s ON True
JOIN LATERAL _ermrest.rights(_ermrest.to_acls(c.acls, (s.rowdata)->'acls'), $3) s_rights ON (True)
WHERE s.during @> $2
  AND (s.rowdata)->>'schema_name' = $1
  AND s_rights."enumerate";
$$ LANGUAGE SQL;

RAISE NOTICE 'Completed idempotent creation of standard ERMrest schema.';

END ermrest_schema;
$ermrest_schema$ LANGUAGE plpgsql;

