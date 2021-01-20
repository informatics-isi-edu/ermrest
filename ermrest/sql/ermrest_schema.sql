
-- 
-- Copyright 2012-2021 University of Southern California
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
PERFORM _ermrest.create_domain_if_not_exists('public', 'color_rgb_hex', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'uri', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'url', 'text');
PERFORM _ermrest.create_domain_if_not_exists('public', 'curie', 'text');

ALTER DOMAIN public.color_rgb_hex DROP CONSTRAINT IF EXISTS color_rgb_hex_format;
ALTER DOMAIN public.color_rgb_hex ADD CONSTRAINT color_rgb_hex_format CHECK (VALUE ~ '^#[0-9a-fA-F]{6}$');

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
    IF newj ? 'RID' THEN
      IF NEW."RID" IS NULL THEN
        NEW."RID" := _ermrest.urlb32_encode(nextval('_ermrest.rid_seq'));
      END IF;
    END IF;
    IF newj ? 'RCB' THEN
      IF NEW."RCB" IS NULL THEN
        NEW."RCB" := _ermrest.current_client();
      END IF;
    END IF;
    IF newj ? 'RCT' THEN
      IF NEW."RCT" IS NULL THEN
        NEW."RCT" := now();
      END IF;
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
	AND c.column_name IN ('URI', 'ID', 'uri', 'id')
	AND s2.schema_name = 'public'
    LOOP
      -- we can only handle these two standard column names
      -- because plpgsql doesn't provide computed field access like NEW[colname]
      IF colrow.column_name = 'uri' THEN
         val := NEW.uri;
      ELSIF colrow.column_name = 'id' THEN
         val := NEW.id;
      ELSIF colrow.column_name = 'URI' THEN
         val := NEW."URI";
      ELSIF colrow.column_name = 'ID' THEN
         val := NEW."ID";
      END IF;

      -- check whether supplied value looks like a template containing '{RID}' and expand it
      IF val ~ '[{]RID[}]' THEN
         val := regexp_replace(val, '[{]RID[}]', NEW."RID");
         IF colrow.column_name = 'uri' THEN
            NEW.uri := val;
         ELSIF colrow.column_name = 'id' THEN
            NEW.id := val;
         ELSIF colrow.column_name = 'URI' THEN
            NEW."URI" := val;
         ELSIF colrow.column_name = 'ID' THEN
            NEW."ID" := val;
	    
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

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_schemas') IS NULL THEN
  CREATE TABLE _ermrest.known_schemas (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE DEFERRABLE NOT NULL,
    schema_name text UNIQUE DEFERRABLE NOT NULL,
    "comment" text
  );
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_types') IS NULL THEN
  CREATE TABLE _ermrest.known_types (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE DEFERRABLE NOT NULL,
    schema_rid text NOT NULL REFERENCES _ermrest.known_schemas("RID") ON DELETE CASCADE,
    type_name text NOT NULL,
    array_element_type_rid text REFERENCES _ermrest.known_types("RID"),
    domain_element_type_rid text REFERENCES _ermrest.known_types("RID"),
    domain_notnull boolean,
    domain_default text,
    "comment" text,
    UNIQUE(schema_rid, type_name) DEFERRABLE,
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
    oid oid UNIQUE DEFERRABLE NOT NULL,
    schema_rid text NOT NULL REFERENCES _ermrest.known_schemas("RID") ON DELETE CASCADE,
    table_name text NOT NULL,
    table_kind text NOT NULL,
    "comment" text,
    UNIQUE(schema_rid, table_name) DEFERRABLE
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
    oid oid UNIQUE DEFERRABLE NOT NULL,
    schema_rid text NOT NULL REFERENCES _ermrest.known_schemas("RID") ON DELETE CASCADE,
    constraint_name text NOT NULL,
    table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    "comment" text,
    UNIQUE(schema_rid, constraint_name) DEFERRABLE
  );
END IF;

CREATE OR REPLACE FUNCTION _ermrest.key_invalidate() RETURNS TRIGGER AS $$
BEGIN
  DELETE FROM _ermrest.known_keys k WHERE k."RID" = OLD.key_rid;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_key_columns') IS NULL THEN
  CREATE TABLE _ermrest.known_key_columns (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    key_rid text NOT NULL REFERENCES _ermrest.known_keys("RID") ON DELETE CASCADE,
    column_rid text NOT NULL REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE,
    "ordinality" int4 NOT NULL,
    UNIQUE(key_rid, column_rid)
  );
ELSIF (SELECT True FROM information_schema.columns WHERE table_schema = '_ermrest' AND table_name = 'known_key_columns' AND column_name = 'ordinality') IS NULL THEN
  ALTER TABLE _ermrest.known_key_columns ADD COLUMN "ordinality" int4; -- this will be nullable/sparse for upgraded catalogs
END IF;

IF COALESCE(
     (SELECT False
      FROM information_schema.triggers tg
      WHERE tg.event_object_schema = '_ermrest'
        AND tg.event_object_table = 'known_key_columns'
        AND tg.trigger_name = 'key_invalidate'
        AND tg.event_manipulation = 'DELETE'),
     True) THEN
  CREATE TRIGGER key_invalidate
    AFTER DELETE ON _ermrest.known_key_columns
    FOR EACH ROW EXECUTE PROCEDURE _ermrest.key_invalidate();
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_pseudo_keys') IS NULL THEN
  CREATE TABLE _ermrest.known_pseudo_keys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    constraint_name text UNIQUE DEFERRABLE,
    table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    "comment" text
  );
END IF;

CREATE OR REPLACE FUNCTION _ermrest.pseudo_key_invalidate() RETURNS TRIGGER AS $$
BEGIN
  DELETE FROM _ermrest.known_pseudo_keys k WHERE k."RID" = OLD.key_rid;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_pseudo_key_columns') IS NULL THEN
  CREATE TABLE _ermrest.known_pseudo_key_columns (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    key_rid text NOT NULL REFERENCES _ermrest.known_pseudo_keys("RID") ON DELETE CASCADE,
    column_rid text NOT NULL REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE,
    "ordinality" int4 NOT NULL,
    UNIQUE(key_rid, column_rid)
  );
ELSIF (SELECT True FROM information_schema.columns WHERE table_schema = '_ermrest' AND table_name = 'known_pseudo_key_columns' AND column_name = 'ordinality') IS NULL THEN
  ALTER TABLE _ermrest.known_pseudo_key_columns ADD COLUMN "ordinality" int4; -- this will be nullable/sparse for upgraded catalogs
END IF;

IF COALESCE(
     (SELECT False
      FROM information_schema.triggers tg
      WHERE tg.event_object_schema = '_ermrest'
        AND tg.event_object_table = 'known_pseudo_key_columns'
        AND tg.trigger_name = 'pseudo_key_invalidate'
        AND tg.event_manipulation = 'DELETE'),
     True) THEN
  CREATE TRIGGER pseudo_key_invalidate
    AFTER DELETE ON _ermrest.known_pseudo_key_columns
    FOR EACH ROW EXECUTE PROCEDURE _ermrest.pseudo_key_invalidate();
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_fkeys') IS NULL THEN
  CREATE TABLE _ermrest.known_fkeys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE DEFERRABLE NOT NULL,
    schema_rid text NOT NULL REFERENCES _ermrest.known_schemas("RID") ON DELETE CASCADE,
    constraint_name text NOT NULL,
    fk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    pk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    delete_rule text NOT NULL,
    update_rule text NOT NULL,
    "comment" text,
    UNIQUE(schema_rid, constraint_name) DEFERRABLE
  );
END IF;

CREATE OR REPLACE FUNCTION _ermrest.fkey_invalidate() RETURNS TRIGGER AS $$
BEGIN
  DELETE FROM _ermrest.known_fkeys k WHERE k."RID" = OLD.fkey_rid;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_fkey_columns') IS NULL THEN
  CREATE TABLE _ermrest.known_fkey_columns (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    fkey_rid text NOT NULL REFERENCES _ermrest.known_fkeys("RID") ON DELETE CASCADE,
    fk_column_rid text NOT NULL REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE,
    pk_column_rid text NOT NULL REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE,
    UNIQUE(fkey_rid, fk_column_rid)
  );
END IF;

IF COALESCE(
     (SELECT False
      FROM information_schema.triggers tg
      WHERE tg.event_object_schema = '_ermrest'
        AND tg.event_object_table = 'known_fkey_columns'
        AND tg.trigger_name = 'fkey_invalidate'
        AND tg.event_manipulation = 'DELETE'),
     True) THEN
  CREATE TRIGGER fkey_invalidate
    AFTER DELETE ON _ermrest.known_fkey_columns
    FOR EACH ROW EXECUTE PROCEDURE _ermrest.fkey_invalidate();
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_pseudo_fkeys') IS NULL THEN
  CREATE TABLE _ermrest.known_pseudo_fkeys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    constraint_name text NOT NULL UNIQUE DEFERRABLE,
    fk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    pk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    "comment" text
  );
END IF;

CREATE OR REPLACE FUNCTION _ermrest.pseudo_fkey_invalidate() RETURNS TRIGGER AS $$
BEGIN
  DELETE FROM _ermrest.known_pseudo_fkeys k WHERE k."RID" = OLD.fkey_rid;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'known_pseudo_fkey_columns') IS NULL THEN
  CREATE TABLE _ermrest.known_pseudo_fkey_columns (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    fkey_rid text NOT NULL REFERENCES _ermrest.known_pseudo_fkeys("RID") ON DELETE CASCADE,
    fk_column_rid text NOT NULL REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE,
    pk_column_rid text NOT NULL REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE,
    UNIQUE(fkey_rid, fk_column_rid)
  );
END IF;

IF COALESCE(
     (SELECT False
      FROM information_schema.triggers tg
      WHERE tg.event_object_schema = '_ermrest'
        AND tg.event_object_table = 'known_pseudo_fkey_columns'
        AND tg.trigger_name = 'pseudo_fkey_invalidate'
        AND tg.event_manipulation = 'DELETE'),
     True) THEN
  CREATE TRIGGER pseudo_fkey_invalidate
    AFTER DELETE ON _ermrest.known_pseudo_fkey_columns
    FOR EACH ROW EXECUTE PROCEDURE _ermrest.pseudo_fkey_invalidate();
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
    obj_description(con.oid)::text AS comment
  FROM pg_constraint con
  JOIN _ermrest.known_schemas ks ON (ks.oid = con.connamespace)
  JOIN pg_class pkcl ON (con.conrelid = pkcl.oid AND con.contype = ANY (ARRAY['u'::"char",'p'::"char"]))
  JOIN _ermrest.known_tables kt ON (pkcl.oid = kt.oid)
  WHERE has_table_privilege(pkcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
     OR has_any_column_privilege(pkcl.oid, 'INSERT, UPDATE, REFERENCES'::text)
;

CREATE OR REPLACE VIEW _ermrest.introspect_key_columns AS
  SELECT
    k."RID" AS key_rid,
    kc."RID" AS column_rid,
    ca.attord AS "ordinality"
  FROM _ermrest.known_keys k
  JOIN (
    SELECT
      con.oid,
      a.attnum,
      a.attord
    FROM pg_catalog.pg_constraint con
    JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS a(attnum, attord) ON (True)
  ) ca ON (ca.oid = k.oid)
  JOIN _ermrest.known_columns kc ON (k.table_rid = kc."table_rid" AND ca.attnum = kc.column_num)
;

CREATE OR REPLACE VIEW _ermrest.introspect_fkeys AS
  SELECT
    con.oid AS "oid",
    s."RID" AS schema_rid,
    con.conname::information_schema.sql_identifier::text AS constraint_name,
    fk_kt."RID" AS fk_table_rid,
    pk_kt."RID" AS pk_table_rid,
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
  WHERE con.contype = 'f'::"char"
    AND (   pg_has_role(kcl.relowner, 'USAGE'::text) 
         OR has_table_privilege(kcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
         OR has_any_column_privilege(kcl.oid, 'INSERT, UPDATE, REFERENCES'::text))
    AND (   pg_has_role(fkcl.relowner, 'USAGE'::text) 
         OR has_table_privilege(fkcl.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text)
         OR has_any_column_privilege(fkcl.oid, 'INSERT, UPDATE, REFERENCES'::text))
;

CREATE OR REPLACE VIEW _ermrest.introspect_fkey_columns AS
  SELECT
    fk."RID" AS fkey_rid,
    fk_kc."RID" AS fk_column_rid,
    pk_kc."RID" AS pk_column_rid
  FROM _ermrest.known_fkeys fk
  JOIN (
    SELECT
      con.oid,
      unnest(con.conkey) AS fk_attnum,
      unnest(con.confkey) AS pk_attnum
    FROM pg_constraint con
  ) ca ON (fk.oid = ca.oid)
  JOIN _ermrest.known_columns fk_kc ON (fk.fk_table_rid = fk_kc.table_rid AND ca.fk_attnum = fk_kc.column_num)
  JOIN _ermrest.known_columns pk_kc ON (fk.pk_table_rid = pk_kc.table_rid AND ca.pk_attnum = pk_kc.column_num)
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
  history_capture jsonb;
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
    xc.conname IS NOT NULL,
    COALESCE(ta.annotation_value, 'true'::jsonb)
  INTO
    sname,
    tname,
    htable_exists,
    old_trigger_exists,
    new_trigger_exists,
    old_exclusion_exists,
    history_capture
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
  LEFT OUTER JOIN _ermrest.known_table_annotations ta
    ON (ta.table_rid = t."RID"
        AND ta.annotation_uri = 'tag:isrd.isi.edu,2020:history-capture')
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

  -- avoid doing dynamic SQL during every trigger event by generating a custom function per table here...
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

  IF NOT new_trigger_exists AND history_capture = 'true'::jsonb
  THEN
    -- create triggers if absent and we want to collect history
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
  ELSIF new_trigger_exists AND history_capture != 'true'::jsonb
  THEN
     -- remove triggers when we don't want to collect history
     EXECUTE 'DROP TRIGGER IF EXISTS ermrest_history_insert ON ' || quote_ident(sname) || '.' || quote_ident(tname) ;

     EXECUTE 'DROP TRIGGER IF EXISTS ermrest_history_update ON ' || quote_ident(sname) || '.' || quote_ident(tname) ;

     EXECUTE 'DROP TRIGGER IF EXISTS ermrest_history_delete ON ' || quote_ident(sname) || '.' || quote_ident(tname) ;
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
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_keys v
    WHERE k.oid = v.oid
      AND ROW(k.schema_rid, k.constraint_name, k.table_rid, k.comment)
          IS DISTINCT FROM
	  ROW(v.schema_rid, v.constraint_name, v.table_rid, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_keys (oid, schema_rid, constraint_name, table_rid, comment)
    SELECT ik.oid, ik.schema_rid, ik.constraint_name, ik.table_rid, ik.comment
    FROM _ermrest.introspect_keys ik
    LEFT OUTER JOIN _ermrest.known_keys kk ON (ik.oid = kk.oid)
    WHERE kk.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible key columns
  WITH deleted AS (
    DELETE FROM _ermrest.known_key_columns k
    USING (
      SELECT key_rid, column_rid FROM _ermrest.known_key_columns
      EXCEPT SELECT key_rid, column_rid FROM _ermrest.introspect_key_columns
    ) d
    WHERE k.key_rid = d.key_rid AND k.column_rid = d.column_rid
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_key_columns k
    SET "ordinality" = i."ordinality"
    FROM _ermrest.introspect_key_columns i
    WHERE k.key_rid = i.key_rid AND k.column_rid = i.column_rid
      AND k."ordinality" IS DISTINCT FROM i."ordinality"
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;

  WITH inserted AS (
    INSERT INTO _ermrest.known_key_columns (key_rid, column_rid, "ordinality")
    SELECT i.key_rid, i.column_rid, i."ordinality"
    FROM _ermrest.introspect_key_columns i
    LEFT JOIN _ermrest.known_key_columns k USING (key_rid, column_rid)
    WHERE k."RID" is NULL
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
      delete_rule = v.delete_rule,
      update_rule = v.update_rule,
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_fkeys v
    WHERE k.oid = v.oid
      AND ROW(k.schema_rid, k.constraint_name, k.fk_table_rid, k.pk_table_rid, k.delete_rule, k.update_rule, k.comment)
          IS DISTINCT FROM
	  ROW(v.schema_rid, v.constraint_name, v.fk_table_rid, v.pk_table_rid, v.delete_rule, v.update_rule, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_fkeys (oid, schema_rid, constraint_name, fk_table_rid, pk_table_rid, delete_rule, update_rule, comment)
    SELECT i.oid, i.schema_rid, i.constraint_name, i.fk_table_rid, i.pk_table_rid, i.delete_rule, i.update_rule, i.comment
    FROM _ermrest.introspect_fkeys i
    LEFT OUTER JOIN _ermrest.known_fkeys kfk ON (i.oid = kfk.oid)
    WHERE kfk.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible fkey columns
  WITH deleted AS (
    DELETE FROM _ermrest.known_fkey_columns k
    USING (
      SELECT fkey_rid, fk_column_rid, pk_column_rid FROM _ermrest.known_fkey_columns
      EXCEPT SELECT fkey_rid, fk_column_rid, pk_column_rid FROM _ermrest.introspect_fkey_columns
    ) d
    WHERE k.fkey_rid = d.fkey_rid
      AND k.fk_column_rid = d.fk_column_rid
      AND k.pk_column_rid = d.pk_column_rid
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_fkey_columns (fkey_rid, fk_column_rid, pk_column_rid)
    SELECT fkey_rid, fk_column_rid, pk_column_rid FROM _ermrest.introspect_fkey_columns
    EXCEPT SELECT fkey_rid, fk_column_rid, pk_column_rid FROM _ermrest.known_fkey_columns
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
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_keys v
    WHERE k.schema_rid = v.schema_rid AND k.constraint_name = v.constraint_name
      AND ROW(k.oid, k.table_rid, k.comment)
          IS DISTINCT FROM
	  ROW(v.oid, v.table_rid, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_keys (oid, schema_rid, constraint_name, table_rid, comment)
    SELECT ik.oid, ik.schema_rid, ik.constraint_name, ik.table_rid, ik.comment
    FROM _ermrest.introspect_keys ik
    LEFT OUTER JOIN _ermrest.known_keys kk ON (ik.oid = kk.oid)
    WHERE kk.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible key columns
  WITH deleted AS (
    DELETE FROM _ermrest.known_key_columns k
    USING (
      SELECT key_rid, column_rid FROM _ermrest.known_key_columns
      EXCEPT SELECT key_rid, column_rid FROM _ermrest.introspect_key_columns
    ) d
    WHERE k.key_rid = d.key_rid AND k.column_rid = d.column_rid
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH updated AS (
    UPDATE _ermrest.known_key_columns k
    SET "ordinality" = i."ordinality"
    FROM _ermrest.introspect_key_columns i
    WHERE k.key_rid = i.key_rid AND k.column_rid = i.column_rid
      AND k."ordinality" IS DISTINCT FROM i."ordinality"
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;

  WITH inserted AS (
    INSERT INTO _ermrest.known_key_columns (key_rid, column_rid, "ordinality")
    SELECT i.key_rid, i.column_rid, i."ordinality"
    FROM _ermrest.introspect_key_columns i
    LEFT JOIN _ermrest.known_key_columns k USING (key_rid, column_rid)
    WHERE k."RID" IS NULL
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
      delete_rule = v.delete_rule,
      update_rule = v.update_rule,
      "comment" = v."comment",
      "RMB" = DEFAULT,
      "RMT" = DEFAULT
    FROM _ermrest.introspect_fkeys v
    WHERE k.schema_rid = v.schema_rid AND k.constraint_name = v.constraint_name
      AND ROW(k.oid, k.fk_table_rid, k.pk_table_rid, k.delete_rule, k.update_rule, k.comment)
          IS DISTINCT FROM
	  ROW(v.oid, v.fk_table_rid, v.pk_table_rid, v.delete_rule, v.update_rule, v.comment)
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM updated;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_fkeys (oid, schema_rid, constraint_name, fk_table_rid, pk_table_rid, delete_rule, update_rule, comment)
    SELECT i.oid, i.schema_rid, i.constraint_name, i.fk_table_rid, i.pk_table_rid, i.delete_rule, i.update_rule, i.comment
    FROM _ermrest.introspect_fkeys i
    LEFT OUTER JOIN _ermrest.known_fkeys kfk ON (i.oid = kfk.oid)
    WHERE kfk.oid IS NULL
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM inserted;
  model_changed := model_changed OR had_changes > 0;

  -- sync up known with currently visible fkey columns
  WITH deleted AS (
    DELETE FROM _ermrest.known_fkey_columns k
    USING (
      SELECT fkey_rid, fk_column_rid, pk_column_rid FROM _ermrest.known_fkey_columns
      EXCEPT SELECT fkey_rid, fk_column_rid, pk_column_rid FROM _ermrest.introspect_fkey_columns
    ) d
    WHERE k.fkey_rid = d.fkey_rid
      AND k.fk_column_rid = d.fk_column_rid
      AND k.pk_column_rid = d.pk_column_rid
    RETURNING k."RID"
  ) SELECT count(*) INTO had_changes FROM deleted;
  model_changed := model_changed OR had_changes > 0;

  WITH inserted AS (
    INSERT INTO _ermrest.known_fkey_columns (fkey_rid, fk_column_rid, pk_column_rid)
    SELECT fkey_rid, fk_column_rid, pk_column_rid FROM _ermrest.introspect_fkey_columns
    EXCEPT SELECT fkey_rid, fk_column_rid, pk_column_rid FROM _ermrest.known_fkey_columns
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
  INSERT INTO _ermrest.table_modified (table_rid, ts) VALUES ($1, now())
  ON CONFLICT (ts, table_rid) DO NOTHING
  RETURNING ts INTO last_ts;

  IF last_ts IS NULL THEN
    RETURN;
  END IF;
  
  INSERT INTO _ermrest.table_last_modified AS t (table_rid, ts) VALUES ($1, now())
  ON CONFLICT (table_rid) DO UPDATE SET ts = EXCLUDED.ts WHERE t.ts < EXCLUDED.ts
  RETURNING ts INTO last_ts;
    
  IF last_ts IS NULL THEN
    -- paranoid integrity check in case we aren't using SERIALIZABLE isolation somehow...
    RAISE EXCEPTION serialization_failure USING MESSAGE = 'ERMrest table version clock reversal!';
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

CREATE OR REPLACE FUNCTION _ermrest.create_acl_table(rname text, fkcname text, fkrname text) RETURNS void AS $$
DECLARE
  tname text;
BEGIN
  tname := 'known_' || rname || '_acls';
  IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = tname) IS NULL THEN
    EXECUTE
      'CREATE TABLE _ermrest.' || tname || '('
      '  "RID" ermrest_rid PRIMARY KEY DEFAULT nextval(''_ermrest.rid_seq''),'
      '  "RCT" ermrest_rct NOT NULL DEFAULT now(),'
      '  "RMT" ermrest_rmt NOT NULL DEFAULT now(),'
      '  "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),'
      '  "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),'
      || COALESCE(fkcname || '_rid text NOT NULL REFERENCES _ermrest.known_' || fkrname || '("RID") ON DELETE CASCADE,', '') ||
      '  acl text NOT NULL,'
      '  members text[] NOT NULL,'
      '  UNIQUE(' || COALESCE(fkcname || '_rid, ', '') || 'acl)'
      ');' ;
  END IF;
END;
$$ LANGUAGE plpgsql;

PERFORM _ermrest.create_acl_table('catalog', NULL, NULL);
PERFORM _ermrest.create_acl_table('schema', 'schema', 'schemas');
PERFORM _ermrest.create_acl_table('table', 'table', 'tables');
PERFORM _ermrest.create_acl_table('column', 'column', 'columns');
PERFORM _ermrest.create_acl_table('fkey', 'fkey', 'fkeys');
PERFORM _ermrest.create_acl_table('pseudo_fkey', 'fkey', 'pseudo_fkeys');

CREATE OR REPLACE FUNCTION _ermrest.create_dynacl_table(rname text, fkcname text, fkrname text) RETURNS void AS $$
DECLARE
  tname text;
BEGIN
  tname := 'known_' || rname || '_dynacls';
  IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = tname) IS NULL THEN
    EXECUTE
      'CREATE TABLE _ermrest.' || tname || '('
      '  "RID" ermrest_rid PRIMARY KEY DEFAULT nextval(''_ermrest.rid_seq''),'
      '  "RCT" ermrest_rct NOT NULL DEFAULT now(),'
      '  "RMT" ermrest_rmt NOT NULL DEFAULT now(),'
      '  "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),'
      '  "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),'
      || fkcname || '_rid text NOT NULL REFERENCES _ermrest.known_' || fkrname || '("RID") ON DELETE CASCADE,' ||
      '  binding_name text NOT NULL,'
      '  binding jsonb NOT NULL,'
      '  UNIQUE (' || fkcname || '_rid, binding_name)'
      ');' ;
  END IF;
END;
$$ LANGUAGE plpgsql;

PERFORM _ermrest.create_dynacl_table('table', 'table', 'tables');
PERFORM _ermrest.create_dynacl_table('column', 'column', 'columns');
PERFORM _ermrest.create_dynacl_table('fkey', 'fkey', 'fkeys');
PERFORM _ermrest.create_dynacl_table('pseudo_fkey', 'fkey', 'pseudo_fkeys');

CREATE OR REPLACE FUNCTION _ermrest.create_annotation_table(rname text, fkcname text, fkrname text) RETURNS void AS $$
DECLARE
  tname text;
BEGIN
  tname := 'known_' || rname || '_annotations';
  IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = tname) IS NULL THEN
    EXECUTE
      'CREATE TABLE _ermrest.' || tname || '('
      '  "RID" ermrest_rid PRIMARY KEY DEFAULT nextval(''_ermrest.rid_seq''),'
      '  "RCT" ermrest_rct NOT NULL DEFAULT now(),'
      '  "RMT" ermrest_rmt NOT NULL DEFAULT now(),'
      '  "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),'
      '  "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),'
      || COALESCE(fkcname || '_rid text NOT NULL REFERENCES _ermrest.known_' || fkrname || '("RID") ON DELETE CASCADE,', '') ||
      '  annotation_uri text NOT NULL,'
      '  annotation_value jsonb NOT NULL,'
      '  UNIQUE(' || COALESCE(fkcname || '_rid, ', '') || 'annotation_uri)'
      ');' ;
  END IF;
END;
$$ LANGUAGE plpgsql;

PERFORM _ermrest.create_annotation_table('catalog', NULL, NULL);
PERFORM _ermrest.create_annotation_table('schema', 'schema', 'schemas');
PERFORM _ermrest.create_annotation_table('table', 'table', 'tables');
PERFORM _ermrest.create_annotation_table('column', 'column', 'columns');
PERFORM _ermrest.create_annotation_table('key', 'key', 'keys');
PERFORM _ermrest.create_annotation_table('pseudo_key', 'key', 'pseudo_keys');
PERFORM _ermrest.create_annotation_table('fkey', 'fkey', 'fkeys');
PERFORM _ermrest.create_annotation_table('pseudo_fkey', 'fkey', 'pseudo_fkeys');

CREATE OR REPLACE FUNCTION _ermrest.track_history_capture_annotation() RETURNS TRIGGER AS $$
DECLARE
  record record;
BEGIN
  IF TG_OP = 'DELETE' THEN
    FOR record IN
      SELECT *
      FROM old_table_annotations
      WHERE annotation_uri = 'tag:isrd.isi.edu,2020:history-capture'
        AND annotation_value != 'true'::jsonb
    LOOP
      PERFORM _ermrest.enable_table_history(record.table_rid, true);
    END LOOP;

  ELSIF TG_OP = 'UPDATE' THEN
    FOR record IN
      SELECT o.table_rid
      FROM old_table_annotations o
      JOIN new_table_annotations n ON (o.table_rid = n.table_rid AND o.annotation_uri = n.annotation_uri)
      WHERE o.annotation_uri = 'tag:isrd.isi.edu,2020:history-capture'
        AND o.annotation_value != n.annotation_value
    LOOP
      PERFORM _ermrest.enable_table_history(record.table_rid, true);
    END LOOP;

  ELSIF TG_OP = 'INSERT' THEN
    FOR record IN
      SELECT *
      FROM new_table_annotations
      WHERE annotation_uri = 'tag:isrd.isi.edu,2020:history-capture'
        AND annotation_value != 'true'::jsonb
    LOOP
      PERFORM _ermrest.enable_table_history(record.table_rid, true);
    END LOOP;

  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

IF COALESCE(
  (SELECT False
   FROM information_schema.triggers tg
   WHERE tg.event_object_schema = '_ermrest'
     AND tg.event_object_table = 'known_table_annotations'
     AND tg.trigger_name = 'history_capture_insert'
     AND tg.event_manipulation = 'INSERT'),
   True)
THEN
  CREATE TRIGGER history_capture_insert AFTER INSERT ON _ermrest.known_table_annotations
    REFERENCING NEW TABLE AS new_table_annotations
    FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.track_history_capture_annotation();

  CREATE TRIGGER history_capture_update AFTER UPDATE ON _ermrest.known_table_annotations
    REFERENCING NEW TABLE AS new_table_annotations OLD TABLE AS old_table_annotations
    FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.track_history_capture_annotation();

  CREATE TRIGGER history_capture_delete AFTER DELETE ON _ermrest.known_table_annotations
    REFERENCING OLD TABLE AS old_table_annotations
    FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.track_history_capture_annotation();
END IF;

-- this is by-name to handle possible dump/restore scenarios
-- a DBA who does many SQL DDL RENAME events and wants to link by OID rather than name
-- should call _ermrest.model_change_by_oid() **before** running ermrest-deploy
SET CONSTRAINTS ALL DEFERRED;
PERFORM _ermrest.model_change_event();
SET CONSTRAINTS ALL IMMEDIATE;

CREATE OR REPLACE FUNCTION _ermrest.create_historical_annotation_func(rname text, cname text) RETURNS void AS $def$
BEGIN
  EXECUTE
    'CREATE OR REPLACE FUNCTION _ermrest.known_' || rname || '_annotations(ts timestamptz)'
    'RETURNS TABLE (' || COALESCE(cname || ' text,', '') || 'annotation_uri text, annotation_value jsonb) AS $$'
    '  SELECT ' || COALESCE('(s.rowdata->>' || quote_literal(cname) || ')::text,', '') || 's.rowdata->>''annotation_uri'', s.rowdata->''annotation_value'''
    '  FROM _ermrest_history.known_' || rname || '_annotations s'
    '  WHERE s.during @> COALESCE(ts, now());'
    '$$ LANGUAGE SQL;' ;
END;
$def$ LANGUAGE plpgsql;

PERFORM _ermrest.create_historical_annotation_func('catalog', NULL);
PERFORM _ermrest.create_historical_annotation_func('schema', 'schema_rid');
PERFORM _ermrest.create_historical_annotation_func('table', 'table_rid');
PERFORM _ermrest.create_historical_annotation_func('column', 'column_rid');
PERFORM _ermrest.create_historical_annotation_func('key', 'key_rid');
PERFORM _ermrest.create_historical_annotation_func('fkey', 'fkey_rid');
PERFORM _ermrest.create_historical_annotation_func('pseudo_key', 'key_rid');
PERFORM _ermrest.create_historical_annotation_func('pseudo_fkey', 'fkey_rid');

CREATE OR REPLACE FUNCTION _ermrest.create_historical_acl_func(rname text, cname text) RETURNS void AS $def$
BEGIN
  EXECUTE
    'CREATE OR REPLACE FUNCTION _ermrest.known_' || rname || '_acls(ts timestamptz)'
    'RETURNS TABLE (' || COALESCE(cname || ' text,', '') || 'acl text, members jsonb) AS $$'
    '  SELECT ' || COALESCE('(s.rowdata->>' || quote_literal(cname) || ')::text,', '') || 's.rowdata->>''acl'', s.rowdata->''members'''
    '  FROM _ermrest_history.known_' || rname || '_acls s'
    '  WHERE s.during @> COALESCE(ts, now());'
    '$$ LANGUAGE SQL;' ;
END;
$def$ LANGUAGE plpgsql;

PERFORM _ermrest.create_historical_acl_func('catalog', NULL);
PERFORM _ermrest.create_historical_acl_func('schema', 'schema_rid');
PERFORM _ermrest.create_historical_acl_func('table', 'table_rid');
PERFORM _ermrest.create_historical_acl_func('column', 'column_rid');
PERFORM _ermrest.create_historical_acl_func('fkey', 'fkey_rid');
PERFORM _ermrest.create_historical_acl_func('pseudo_fkey', 'fkey_rid');

CREATE OR REPLACE FUNCTION _ermrest.create_historical_dynacl_func(rname text, cname text) RETURNS void AS $def$
BEGIN
  EXECUTE
    'CREATE OR REPLACE FUNCTION _ermrest.known_' || rname || '_dynacls(ts timestamptz)'
    'RETURNS TABLE (' || cname || ' text,' || 'binding_name text, binding jsonb) AS $$'
    '  SELECT ' || '(s.rowdata->>' || quote_literal(cname) || ')::text,' || 's.rowdata->>''binding_name'', s.rowdata->''binding'''
    '  FROM _ermrest_history.known_' || rname || '_dynacls s'
    '  WHERE s.during @> COALESCE(ts, now());'
    '$$ LANGUAGE SQL;' ;
END;
$def$ LANGUAGE plpgsql;

PERFORM _ermrest.create_historical_dynacl_func('table', 'table_rid');
PERFORM _ermrest.create_historical_dynacl_func('column', 'column_rid');
PERFORM _ermrest.create_historical_dynacl_func('fkey', 'fkey_rid');
PERFORM _ermrest.create_historical_dynacl_func('pseudo_fkey', 'fkey_rid');

CREATE OR REPLACE FUNCTION _ermrest.known_catalog_denorm(ts timestamptz)
RETURNS TABLE (annotations jsonb, acls jsonb) AS $$
SELECT
  COALESCE((SELECT jsonb_object_agg(a.annotation_uri, a.annotation_value)
            FROM _ermrest.known_catalog_annotations($1) a),
	   '{}'::jsonb) AS annotations,
  COALESCE((SELECT jsonb_object_agg(a.acl, a.members)
            FROM _ermrest.known_catalog_acls($1) a),
	   '{}'::jsonb) AS acls
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_schemas(ts timestamptz)
RETURNS TABLE ("RID" text, schema_name text, comment text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_name')::text AS "schema_name",
    (s.rowdata->>'comment')::text AS "comment"
  FROM _ermrest_history.known_schemas s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_schemas_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_name text, comment text, annotations jsonb, acls jsonb) AS $$
SELECT
  s."RID",
  s.schema_name,
  s.comment,
  COALESCE(anno.annotations, '{}'::jsonb) AS annotations,
  COALESCE(acls.acls, '{}'::jsonb) AS acls
FROM _ermrest.known_schemas($1) s
LEFT OUTER JOIN (
  SELECT
    a.schema_rid,
    jsonb_object_agg(a.annotation_uri, a.annotation_value) AS annotations
  FROM _ermrest.known_schema_annotations($1) a
  GROUP BY a.schema_rid
) anno ON (s."RID" = anno.schema_rid)
LEFT OUTER JOIN (
  SELECT
    a.schema_rid,
    jsonb_object_agg(a.acl, a.members) AS acls
  FROM _ermrest.known_schema_acls($1) a
  GROUP BY a.schema_rid
) acls ON (s."RID" = acls.schema_rid)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_types(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, type_name text, array_element_type_rid text, domain_element_type_rid text, domain_notnull boolean, domain_default text, comment text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_rid')::text AS "schema_rid",
    (s.rowdata->>'type_name')::text AS "type_name",
    (s.rowdata->>'array_element_type_rid')::text AS "array_element_type_rid",
    (s.rowdata->>'domain_element_type_rid')::text AS "domain_element_type_rid",
    (s.rowdata->>'domain_notnull')::boolean AS "domain_notnull",
    (s.rowdata->>'domain_default')::text AS "domain_default",
    (s.rowdata->>'comment')::text AS "comment"
  FROM _ermrest_history.known_types s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_columns(ts timestamptz)
RETURNS TABLE ("RID" text, table_rid text, column_num int, column_name text, type_rid text, not_null boolean, column_default text, comment text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'table_rid')::text AS "table_rid",
    (s.rowdata->>'column_num')::int AS "column_num",
    (s.rowdata->>'column_name')::text AS "column_name",
    (s.rowdata->>'type_rid')::text AS "type_rid",
    (s.rowdata->>'not_null')::boolean AS "not_null",
    (s.rowdata->>'column_default')::text AS "column_default",
    (s.rowdata->>'comment')::text AS "comment"
  FROM _ermrest_history.known_columns s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_notnulls(ts timestamptz)
RETURNS TABLE ("RID" text, column_rid text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'column_rid') AS "column_rid"
  FROM _ermrest_history.known_pseudo_notnulls s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_columns_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, table_rid text, column_num int, column_name text, type_rid text, not_null boolean, column_default text, comment text, annotations jsonb, acls jsonb) AS $$
SELECT
  c."RID",
  c.table_rid,
  c.column_num,
  c.column_name,
  c.type_rid,
  n.column_rid IS NOT NULL OR c.not_null AS not_null,
  c.column_default,
  c."comment",
  COALESCE(anno.annotations, '{}'::jsonb) AS annotations,
  COALESCE(acls.acls, '{}'::jsonb) AS acls
FROM _ermrest.known_columns($1) c
LEFT OUTER JOIN _ermrest.known_pseudo_notnulls($1) n ON (n.column_rid = c."RID")
LEFT OUTER JOIN (
  SELECT
    a.column_rid,
    jsonb_object_agg(a.annotation_uri, a.annotation_value) AS annotations
  FROM _ermrest.known_column_annotations($1) a
  GROUP BY a.column_rid
) anno ON (c."RID" = anno.column_rid)
LEFT OUTER JOIN (
  SELECT
    a.column_rid,
    jsonb_object_agg(a.acl, a.members) AS acls
  FROM _ermrest.known_column_acls($1) a
  GROUP BY a.column_rid
) acls ON (c."RID" = acls.column_rid)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_tables(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, table_name text, table_kind text, comment text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_rid')::text "schema_rid",
    (s.rowdata->>'table_name')::text "table_name",
    (s.rowdata->>'table_kind')::text "table_kind",
    (s.rowdata->>'comment')::text "comment"
  FROM _ermrest_history.known_tables s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_tables_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, table_name text, table_kind text, comment text, annotations jsonb, acls jsonb, columns jsonb[]) AS $$
SELECT
  t."RID",
  t.schema_rid,
  t.table_name,
  t.table_kind,
  t."comment",
  COALESCE(anno.annotations, '{}'::jsonb) AS annotations,
  COALESCE(acls.acls, '{}'::jsonb) AS acls,
  COALESCE(c.columns, ARRAY[]::jsonb[]) AS columns
FROM _ermrest.known_tables($1) t
LEFT OUTER JOIN (
  SELECT
    c.table_rid,
    array_agg(to_jsonb(c.*) ORDER BY c.column_num)::jsonb[] AS columns
  FROM _ermrest.known_columns_denorm($1) c
  GROUP BY c.table_rid
) c ON (t."RID" = c.table_rid)
LEFT OUTER JOIN (
  SELECT
    a.table_rid,
    jsonb_object_agg(a.annotation_uri, a.annotation_value) AS annotations
  FROM _ermrest.known_table_annotations($1) a
  GROUP BY a.table_rid
) anno ON (t."RID" = anno.table_rid)
LEFT OUTER JOIN (
  SELECT
    a.table_rid,
    jsonb_object_agg(a.acl, a.members) AS acls
  FROM _ermrest.known_table_acls($1) a
  GROUP BY a.table_rid
) acls ON (t."RID" = acls.table_rid)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.record_new_table(schema_rid text, tname text) RETURNS text AS $$
DECLARE
  t_rid text;
  s_name text;
BEGIN
  INSERT INTO _ermrest.known_tables (oid, schema_rid, table_name, table_kind, "comment")
  SELECT t.oid, t.schema_rid, t.table_name, t.table_kind, t."comment"
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

IF (SELECT True FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ermrest_client') THEN
  ALTER TABLE public.ermrest_client RENAME TO "ERMrest_Client";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN id TO "ID";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN display_name TO "Display_Name";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN full_name TO "Full_Name";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN email TO "Email";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN client_obj TO "Client_Object";
ELSIF (SELECT True FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ERMrest_Client') IS NULL THEN
  CREATE TABLE public."ERMrest_Client" (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    "ID" text UNIQUE NOT NULL,
    "Display_Name" text,
    "Full_Name" text,
    "Email" text,
    "Client_Object" jsonb NOT NULL
  );
  PERFORM _ermrest.record_new_table(_ermrest.find_schema_rid('public'), 'ERMrest_Client');
  INSERT INTO _ermrest.known_table_acls (table_rid, acl, members)
  VALUES
    (_ermrest.find_table_rid('public', 'ERMrest_Client'), 'insert', ARRAY[]::text[]),
    (_ermrest.find_table_rid('public', 'ERMrest_Client'), 'update', ARRAY[]::text[]),
    (_ermrest.find_table_rid('public', 'ERMrest_Client'), 'delete', ARRAY[]::text[]),
    (_ermrest.find_table_rid('public', 'ERMrest_Client'), 'select', ARRAY[]::text[]),
    (_ermrest.find_table_rid('public', 'ERMrest_Client'), 'enumerate', ARRAY[]::text[]);
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ERMrest_Group') IS NULL THEN
  CREATE TABLE public."ERMrest_Group" (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    "ID" text UNIQUE NOT NULL,
    "URL" text,
    "Display_Name" text,
    "Description" text
  );
  PERFORM _ermrest.record_new_table(_ermrest.find_schema_rid('public'), 'ERMrest_Group');
  INSERT INTO _ermrest.known_table_acls (table_rid, acl, members)
  VALUES
    (_ermrest.find_table_rid('public', 'ERMrest_Group'), 'insert', ARRAY[]::text[]),
    (_ermrest.find_table_rid('public', 'ERMrest_Group'), 'update', ARRAY[]::text[]),
    (_ermrest.find_table_rid('public', 'ERMrest_Group'), 'delete', ARRAY[]::text[]),
    (_ermrest.find_table_rid('public', 'ERMrest_Group'), 'select', ARRAY[]::text[]),
    (_ermrest.find_table_rid('public', 'ERMrest_Group'), 'enumerate', ARRAY[]::text[]);
END IF;

CREATE OR REPLACE FUNCTION _ermrest.known_keys(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, table_rid text, comment text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_rid')::text "schema_rid",
    (s.rowdata->>'constraint_name')::text "constraint_name",
    (s.rowdata->>'table_rid')::text "table_rid",
    (s.rowdata->>'comment')::text "comment"
  FROM _ermrest_history.known_keys s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_keys(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, table_rid text, comment text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'constraint_name')::text "constraint_name",
    (s.rowdata->>'table_rid')::text "table_rid",
    (s.rowdata->>'comment')::text "comment"
  FROM _ermrest_history.known_pseudo_keys s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_key_columns(ts timestamptz)
RETURNS TABLE ("RID" text, key_rid text, column_rid text, "ordinality" int4) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'key_rid')::text "key_rid",
    (s.rowdata->>'column_rid')::text "column_rid",
    (s.rowdata->>'ordinality')::int4 "ordinality" -- this will be NULL for pre-upgrade snapshots
  FROM _ermrest_history.known_key_columns s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_key_columns(ts timestamptz)
RETURNS TABLE ("RID" text, key_rid text, column_rid text, "ordinality" int4) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'key_rid')::text "key_rid",
    (s.rowdata->>'column_rid')::text "column_rid",
    (s.rowdata->>'ordinality')::int4 "ordinality" -- this will be NULL for pre-upgrade snapshots
  FROM _ermrest_history.known_pseudo_key_columns s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_keys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, table_rid text, column_rids text[], comment text, annotations jsonb) AS $$
SELECT
  k."RID",
  k.schema_rid,
  k.constraint_name,
  k.table_rid,
  kc.column_rids,
  k."comment",
  COALESCE(anno.annotations, '{}'::jsonb) AS annotations
FROM _ermrest.known_keys($1) k
JOIN (
  SELECT
    kc.key_rid,
    array_agg(kc.column_rid ORDER BY kc."ordinality", kc.column_rid)::text[] AS column_rids
  FROM _ermrest.known_key_columns($1) kc
  GROUP BY kc.key_rid
) kc ON (k."RID" = kc.key_rid)
LEFT OUTER JOIN (
  SELECT
    key_rid,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_key_annotations($1)
  GROUP BY key_rid
) anno ON (k."RID" = anno.key_rid)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_keys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, table_rid text, column_rids text[], comment text, annotations jsonb) AS $$
SELECT
  k."RID",
  k.constraint_name,
  k.table_rid,
  kc.column_rids,
  k."comment",
  COALESCE(anno.annotations, '{}'::jsonb) AS annotations
FROM _ermrest.known_pseudo_keys($1) k
LEFT OUTER JOIN (
  SELECT
    kc.key_rid,
    array_agg(kc.column_rid ORDER BY kc."ordinality", kc.column_rid)::text[] AS column_rids
  FROM _ermrest.known_pseudo_key_columns($1) kc
  GROUP BY kc.key_rid
) kc ON (k."RID" = kc.key_rid)
LEFT OUTER JOIN (
  SELECT
    key_rid,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_pseudo_key_annotations($1)
  GROUP BY key_rid
) anno ON (k."RID" = anno.key_rid)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_fkeys(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, fk_table_rid text, pk_table_rid text, delete_rule text, update_rule text, comment text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_rid')::text "schema_rid",
    (s.rowdata->>'constraint_name')::text "constraint_name",
    (s.rowdata->>'fk_table_rid')::text "fk_table_rid",
    (s.rowdata->>'pk_table_rid')::text "pk_table_rid",
    (s.rowdata->>'delete_rule')::text "delete_rule",
    (s.rowdata->>'update_rule')::text "update_rule",
    (s.rowdata->>'comment')::text "comment"
  FROM _ermrest_history.known_fkeys s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_fkeys(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, fk_table_rid text, pk_table_rid text, comment text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'constraint_name')::text "constraint_name",
    (s.rowdata->>'fk_table_rid')::text "fk_table_rid",
    (s.rowdata->>'pk_table_rid')::text "pk_table_rid",
    (s.rowdata->>'comment')::text "comment"
  FROM _ermrest_history.known_pseudo_fkeys s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_fkey_columns(ts timestamptz)
RETURNS TABLE ("RID" text, fkey_rid text, fk_column_rid text, pk_column_rid text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'fkey_rid')::text "fkey_rid",
    (s.rowdata->>'fk_column_rid')::text "fk_column_rid",
    (s.rowdata->>'pk_column_rid')::text "pk_column_rid"
  FROM _ermrest_history.known_fkey_columns s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_fkey_columns(ts timestamptz)
RETURNS TABLE ("RID" text, fkey_rid text, fk_column_rid text, pk_column_rid text) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'fkey_rid')::text "fkey_rid",
    (s.rowdata->>'fk_column_rid')::text "fk_column_rid",
    (s.rowdata->>'pk_column_rid')::text "pk_column_rid"
  FROM _ermrest_history.known_pseudo_fkey_columns s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_fkeys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, fk_table_rid text, fk_column_rids text[], pk_table_rid text, pk_column_rids text[], delete_rule text, update_rule text, comment text, annotations jsonb, acls jsonb) AS $$
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
  COALESCE(anno.annotations, '{}'::jsonb) AS annotations,
  COALESCE(acl.acls, '{}'::jsonb) AS acls
FROM _ermrest.known_fkeys($1) fk
LEFT OUTER JOIN (
  SELECT
    fkey_rid,
    array_agg(fk_column_rid ORDER BY fkcp.fk_column_rid)::text[] AS fk_column_rids,
    array_agg(pk_column_rid ORDER BY fkcp.fk_column_rid)::text[] AS pk_column_rids
  FROM _ermrest.known_fkey_columns($1) fkcp
  GROUP BY fkcp.fkey_rid
) fkcp ON (fk."RID" = fkcp.fkey_rid)
LEFT OUTER JOIN (
  SELECT
    fkey_rid,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_fkey_annotations($1)
  GROUP BY fkey_rid
) anno ON (fk."RID" = anno.fkey_rid)
LEFT OUTER JOIN (
  SELECT
    fkey_rid,
    jsonb_object_agg(acl, members) AS acls
  FROM _ermrest.known_fkey_acls($1)
  GROUP BY fkey_rid
) acl ON (fk."RID" = acl.fkey_rid)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_fkeys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, fk_table_rid text, fk_column_rids text[], pk_table_rid text, pk_column_rids text[], comment text, annotations jsonb, acls jsonb) AS $$
SELECT
  fk."RID",
  fk.constraint_name,
  fk.fk_table_rid,
  fkcp.fk_column_rids,
  fk.pk_table_rid,
  fkcp.pk_column_rids,
  fk."comment",
  COALESCE(anno.annotations, '{}'::jsonb) AS annotations,
  COALESCE(acl.acls, '{}'::jsonb) AS acls
FROM _ermrest.known_pseudo_fkeys($1) fk
LEFT OUTER JOIN (
  SELECT
    fkey_rid,
    array_agg(fk_column_rid ORDER BY fkcp.fk_column_rid)::text[] AS fk_column_rids,
    array_agg(pk_column_rid ORDER BY fkcp.fk_column_rid)::text[] AS pk_column_rids
  FROM _ermrest.known_pseudo_fkey_columns($1) fkcp
  GROUP BY fkcp.fkey_rid
) fkcp ON (fk."RID" = fkcp.fkey_rid)
LEFT OUTER JOIN (
  SELECT
    fkey_rid,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_pseudo_fkey_annotations($1)
  GROUP BY fkey_rid
) anno ON (fk."RID" = anno.fkey_rid)
LEFT OUTER JOIN (
  SELECT
    fkey_rid,
    jsonb_object_agg(acl, members) AS acls
  FROM _ermrest.known_pseudo_fkey_acls($1)
  GROUP BY fkey_rid
) acl ON (fk."RID" = acl.fkey_rid)
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

RAISE NOTICE 'Completed idempotent creation of standard ERMrest schema.';

END ermrest_schema;
$ermrest_schema$ LANGUAGE plpgsql;

