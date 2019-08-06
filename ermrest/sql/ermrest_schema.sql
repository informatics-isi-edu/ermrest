
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

CREATE OR REPLACE FUNCTION _ermrest.table_exists(sname text, tname text) RETURNS boolean AS $$
SELECT COALESCE((SELECT True FROM information_schema.tables WHERE table_schema = $1 AND table_name = $2), False);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.column_exists(sname text, tname text, cname text) RETURNS boolean AS $$
SELECT COALESCE((SELECT True FROM information_schema.columns WHERE table_schema = $1 AND table_name = $2 AND column_name = $3), False);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.trigger_exists(sname text, tname text, tgname text, evname text) RETURNS boolean AS $$
SELECT COALESCE(
  (SELECT True
   FROM information_schema.triggers tg
   WHERE tg.event_object_schema = $1
     AND tg.event_object_table = $2
     AND tg.trigger_name = $3
     AND tg.event_manipulation = $4
   LIMIT 1),
  False
);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.model_deps(acl_bindings jsonb) RETURNS jsonb IMMUTABLE AS $$
SELECT jsonb_object_agg(dep, NULL)
FROM jsonb_each(acl_bindings) b(binding_name, binding)
JOIN LATERAL jsonb_each(b.binding->'model_deps') m(dep, nothing) ON (True);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.prune_acl_bindings(acl_bindings jsonb, dropped_rid text) RETURNS jsonb IMMUTABLE AS $$
SELECT COALESCE(
  (SELECT jsonb_object_agg(binding_name, binding)
   FROM jsonb_each(acl_bindings) b(binding_name, binding)
   WHERE NOT binding->'model_deps' ? dropped_rid),
  '{}'::jsonb
);
$$ LANGUAGE SQL;

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

IF NOT _ermrest.table_exists('_ermrest', 'model_last_modified') THEN
  CREATE TABLE _ermrest.model_last_modified (
    ts timestamptz PRIMARY KEY,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client()
  );
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'model_modified') THEN
  CREATE TABLE _ermrest.model_modified (
    ts timestamptz PRIMARY KEY,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client()
  );
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'catalog_amended') THEN
  CREATE TABLE _ermrest.catalog_amended (
    ts timestamptz PRIMARY KEY,
    during tstzrange NOT NULL,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client()
  );
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'known_catalogs') THEN
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
  INSERT INTO _ermrest.known_catalogs ("RID") VALUES ('0');
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'known_schemas') THEN
  CREATE TABLE _ermrest.known_schemas (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    oid oid UNIQUE DEFERRABLE NOT NULL,
    schema_name text UNIQUE DEFERRABLE NOT NULL,
    "comment" text,
    acls jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}'
  );
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'known_types') THEN
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

IF NOT _ermrest.table_exists('_ermrest', 'known_tables') THEN
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
    acls jsonb NOT NULL DEFAULT '{}',
    acl_bindings jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}',
    UNIQUE(schema_rid, table_name) DEFERRABLE
  );
  CREATE INDEX known_tables_model_deps_idx ON _ermrest.known_tables USING gin ( (_ermrest.model_deps(acl_bindings)) ) WHERE acl_bindings != '{}';
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'table_last_modified') THEN
  CREATE TABLE _ermrest.table_last_modified (
    table_rid text PRIMARY KEY REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    ts timestamptz,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client()
  );
  CREATE INDEX tlm_ts_rid ON _ermrest.table_last_modified (ts, table_rid);
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'table_modified') THEN
  CREATE TABLE _ermrest.table_modified (
    ts timestamptz,
    table_rid text,
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    PRIMARY KEY (ts, table_rid)
  );
END IF;

IF NOT _ermrest.table_exists('_ermrest_history', 'visible_entities') THEN
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

IF NOT _ermrest.table_exists('_ermrest', 'known_columns') THEN
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
    acl_bindings jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}',
    UNIQUE(table_rid, column_num) DEFERRABLE,
    UNIQUE(table_rid, column_name) DEFERRABLE
  );
  CREATE INDEX known_columns_model_deps_idx ON _ermrest.known_columns USING gin ( (_ermrest.model_deps(acl_bindings)) ) WHERE acl_bindings != '{}';
ELSE
  ALTER TABLE _ermrest.known_columns
    DROP CONSTRAINT known_columns_table_rid_column_name_key,
    DROP CONSTRAINT known_columns_table_rid_column_num_key,
    ADD CONSTRAINT known_columns_table_rid_column_name_key UNIQUE (table_rid, column_name) DEFERRABLE,
    ADD CONSTRAINT known_columns_table_rid_column_num_key UNIQUE (table_rid, column_num) DEFERRABLE;
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'known_pseudo_notnulls') THEN
  CREATE TABLE _ermrest.known_pseudo_notnulls (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    column_rid text NOT NULL UNIQUE REFERENCES _ermrest.known_columns("RID") ON DELETE CASCADE
  );
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'known_keys') THEN
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
    column_rids jsonb NOT NULL DEFAULT '{}', -- set of RIDs as {rid: null...} mapping
    "comment" text,
    annotations jsonb NOT NULL DEFAULT '{}',
    UNIQUE(schema_rid, constraint_name) DEFERRABLE
  );
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'known_pseudo_keys') THEN
  CREATE TABLE _ermrest.known_pseudo_keys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    constraint_name text UNIQUE DEFERRABLE,
    table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    column_rids jsonb NOT NULL DEFAULT '{}', -- set of RIDs as {rid: null...} mapping
    "comment" text,
    annotations jsonb NOT NULL DEFAULT '{}'
  );
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'known_fkeys') THEN
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
    fkc_pkc_rids jsonb NOT NULL DEFAULT '{}', -- map of {fkc_rid: pkc_rid...}
    delete_rule text NOT NULL,
    update_rule text NOT NULL,
    "comment" text,
    acls jsonb NOT NULL DEFAULT '{}',
    acl_bindings jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}',
    UNIQUE(schema_rid, constraint_name) DEFERRABLE
  );
  CREATE INDEX known_fkeys_model_deps_idx ON _ermrest.known_fkeys USING gin ( (_ermrest.model_deps(acl_bindings)) ) WHERE acl_bindings != '{}';
END IF;

IF NOT _ermrest.table_exists('_ermrest', 'known_pseudo_fkeys') THEN
  CREATE TABLE _ermrest.known_pseudo_fkeys (
    "RID" ermrest_rid PRIMARY KEY DEFAULT _ermrest.urlb32_encode(nextval('_ermrest.rid_seq')),
    "RCT" ermrest_rct NOT NULL DEFAULT now(),
    "RMT" ermrest_rmt NOT NULL DEFAULT now(),
    "RCB" ermrest_rcb DEFAULT _ermrest.current_client(),
    "RMB" ermrest_rmb DEFAULT _ermrest.current_client(),
    constraint_name text NOT NULL UNIQUE DEFERRABLE,
    fk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    pk_table_rid text NOT NULL REFERENCES _ermrest.known_tables("RID") ON DELETE CASCADE,
    fkc_pkc_rids jsonb NOT NULL DEFAULT '{}', -- map of {fkc_rid: pkc_rid...}
    "comment" text,
    acls jsonb NOT NULL DEFAULT '{}',
    acl_bindings jsonb NOT NULL DEFAULT '{}',
    annotations jsonb NOT NULL DEFAULT '{}'
  );
  CREATE INDEX known_pseudo_fkeys_model_deps_idx ON _ermrest.known_pseudo_fkeys USING gin ( (_ermrest.model_deps(acl_bindings)) ) WHERE acl_bindings != '{}';
END IF;

CREATE OR REPLACE FUNCTION _ermrest.refmap_invert(orig jsonb) RETURNS jsonb IMMUTABLE AS $$
SELECT jsonb_object_agg(v, k)
FROM jsonb_each_text(orig) s(k, v)
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.columns_invalidate() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    DELETE FROM _ermrest.known_keys v USING _ermrest_dropped_columns d WHERE v.column_rids ? d."RID";
    DELETE FROM _ermrest.known_pseudo_keys v USING _ermrest_dropped_columns d WHERE v.column_rids ? d."RID";
    DELETE FROM _ermrest.known_fkeys v USING _ermrest_dropped_columns d WHERE v.fkc_pkc_rids ? d."RID" OR _ermrest.refmap_invert(v.fkc_pkc_rids) ? d."RID";
    DELETE FROM _ermrest.known_pseudo_fkeys v USING _ermrest_dropped_columns d WHERE v.fkc_pkc_rids ? d."RID" OR _ermrest.refmap_invert(v.fkc_pkc_rids) ? d."RID";
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

IF NOT _ermrest.trigger_exists('_ermrest', 'known_columns', 'columns_invalidate', 'DELETE') THEN
  CREATE TRIGGER columns_invalidate
    AFTER DELETE ON _ermrest.known_columns
    REFERENCING OLD TABLE AS _ermrest_dropped_columns
    FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.columns_invalidate();
END IF;

CREATE OR REPLACE FUNCTION _ermrest.model_elements_invalidate() RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    UPDATE _ermrest.known_tables v SET acl_bindings = _ermrest.prune_acl_bindings(v.acl_bindings, d."RID")
    FROM _ermrest_dropped_model d WHERE _ermrest.model_deps(v.acl_bindings) ? d."RID" AND v.acl_bindings != '{}';

    UPDATE _ermrest.known_columns v SET acl_bindings = _ermrest.prune_acl_bindings(v.acl_bindings, d."RID")
    FROM _ermrest_dropped_model d WHERE _ermrest.model_deps(v.acl_bindings) ? d."RID" AND v.acl_bindings != '{}';

    UPDATE _ermrest.known_fkeys v SET acl_bindings = _ermrest.prune_acl_bindings(v.acl_bindings, d."RID")
    FROM _ermrest_dropped_model d WHERE _ermrest.model_deps(v.acl_bindings) ? d."RID" AND v.acl_bindings != '{}';

    UPDATE _ermrest.known_pseudo_fkeys v SET acl_bindings = _ermrest.prune_acl_bindings(v.acl_bindings, d."RID")
    FROM _ermrest_dropped_model d WHERE _ermrest.model_deps(v.acl_bindings) ? d."RID" AND v.acl_bindings != '{}';
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

IF NOT _ermrest.trigger_exists('_ermrest', 'known_tables', 'model_element_invalidate', 'DELETE') THEN
  CREATE TRIGGER model_element_invalidate
    AFTER DELETE ON _ermrest.known_tables
    REFERENCING OLD TABLE AS _ermrest_dropped_model
    FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.model_elements_invalidate();
END IF;

IF NOT _ermrest.trigger_exists('_ermrest', 'known_columns', 'model_element_invalidate', 'DELETE') THEN
  CREATE TRIGGER model_element_invalidate
    AFTER DELETE ON _ermrest.known_columns
    REFERENCING OLD TABLE AS _ermrest_dropped_model
    FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.model_elements_invalidate();
END IF;

IF NOT _ermrest.trigger_exists('_ermrest', 'known_fkeys', 'model_element_invalidate', 'DELETE') THEN
  CREATE TRIGGER model_element_invalidate
    AFTER DELETE ON _ermrest.known_fkeys
    REFERENCING OLD TABLE AS _ermrest_dropped_model
    FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.model_elements_invalidate();
END IF;

IF NOT _ermrest.trigger_exists('_ermrest', 'known_pseudo_fkeys', 'model_element_invalidate', 'DELETE') THEN
  CREATE TRIGGER model_element_invalidate
    AFTER DELETE ON _ermrest.known_pseudo_fkeys
    REFERENCING OLD TABLE AS _ermrest_dropped_model
    FOR EACH STATEMENT EXECUTE PROCEDURE _ermrest.model_elements_invalidate();
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
    jsonb_object_agg(kc."RID", 'null'::jsonb) AS column_rids
  FROM _ermrest.known_keys k
  JOIN (
    SELECT
      con.oid,
      unnest(con.conkey) AS attnum
    FROM pg_catalog.pg_constraint con
  ) ca ON (ca.oid = k.oid)
  JOIN _ermrest.known_columns kc ON (k.table_rid = kc."table_rid" AND ca.attnum = kc.column_num)
  GROUP BY k."RID"
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
    jsonb_object_agg(fk_kc."RID", to_jsonb(pk_kc."RID")) AS fkc_pkc_rids
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
  GROUP BY fk."RID"
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
  gist_idx_exists bool;
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
    idx.indexname IS NOT NULL,
    xc.conname IS NOT NULL
  INTO
    sname,
    tname,
    htable_exists,
    old_trigger_exists,
    new_trigger_exists,
    gist_idx_exists,
    old_exclusion_exists
  FROM _ermrest.known_tables t
  JOIN _ermrest.known_schemas s ON (t.schema_rid = s."RID")
  JOIN pg_catalog.pg_namespace hs ON (hs.nspname = '_ermrest_history')
  LEFT OUTER JOIN pg_catalog.pg_class it
    ON (it.relnamespace = hs.oid
        AND it.relname = CASE WHEN s.schema_name = '_ermrest' THEN t.table_name ELSE 't' || t."RID" END)
  LEFT OUTER JOIN pg_catalog.pg_indexes idx
    ON (idx.schemaname = '_ermrest_history'
        AND idx.tablename = it.relname
	AND idx.indexname = idx.tablename || '_during_gist_idx')
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

  IF NOT gist_idx_exists
  THEN
    EXECUTE
      'CREATE INDEX ' || quote_ident(htname || '_during_gist_idx')
        || ' ON _ermrest_history.' || quote_ident(htname)
        || ' USING GIST (during);';
    IF htname IN ('known_tables', 'known_columns', 'known_fkeys', 'known_pseudo_fkeys') THEN
      EXECUTE
      'CREATE INDEX ' || quote_ident(htname || '_during_gist_dynacl_idx')
        || ' ON _ermrest_history.' || quote_ident(htname)
        || ' USING GIST (during) WHERE (rowdata->''acl_bindings'') != ''{}'';';
    END IF;
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
  WITH updated AS (
    UPDATE _ermrest.known_keys k
    SET column_rids = i.column_rids
    FROM _ermrest.introspect_key_columns i
    WHERE k."RID" = i.key_rid AND k.column_rids != i.column_rids
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM updated;
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

  -- sync up known with currently visible key columns
  WITH updated AS (
    UPDATE _ermrest.known_fkeys k
    SET fkc_pkc_rids = i.fkc_pkc_rids
    FROM _ermrest.introspect_fkey_columns i
    WHERE k."RID" = i.fkey_rid AND k.fkc_pkc_rids != i.fkc_pkc_rids
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM updated;
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
  WITH updated AS (
    UPDATE _ermrest.known_keys k
    SET column_rids = i.column_rids
    FROM _ermrest.introspect_key_columns i
    WHERE k."RID" = i.key_rid AND k.column_rids != i.column_rids
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM updated;
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

  -- sync up known with currently visible key columns
  WITH updated AS (
    UPDATE _ermrest.known_fkeys k
    SET fkc_pkc_rids = i.fkc_pkc_rids
    FROM _ermrest.introspect_fkey_columns i
    WHERE k."RID" = i.fkey_rid AND k.fkc_pkc_rids != i.fkc_pkc_rids
    RETURNING "RID"
  ) SELECT count(*) INTO had_changes FROM updated;
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

-- this is by-name to handle possible dump/restore scenarios
-- a DBA who does many SQL DDL RENAME events and wants to link by OID rather than name
-- should call _ermrest.model_change_by_oid() **before** running ermrest-deploy
SET CONSTRAINTS ALL DEFERRED;
PERFORM _ermrest.model_change_event();
SET CONSTRAINTS ALL IMMEDIATE;

CREATE OR REPLACE FUNCTION _ermrest.compile_filter(aliases jsonb, ltable_rid text, filter jsonb) RETURNS jsonb STABLE AS $$
DECLARE
  lname jsonb;
  colrid text;
  combiner text;
  lalias text;
  mdeps jsonb;
BEGIN
  IF filter ?| ARRAY['and', 'or']::text[] THEN
    IF elem ? 'and' THEN
      combiner := 'and';
    ELSE
      combiner := 'or';
    END IF;

    SELECT
      jsonb_build_object(
        combiner,
        to_jsonb(array_agg(_ermrest.compile_filter(aliases, ltable_rid, a.e)))
      )
    INTO filter
    FROM jsonb_array_elements(filter->combiner) a(e);

    -- m.k for children w/ model_deps, filter for other children
    SELECT jsonb_object_agg(COALESCE(m.k, (a.e)->>'filter'), NULL)
    INTO mdeps
    FROM jsonb_array_elements(filter->combiner) a(e)
    LEFT JOIN LATERAL jsonb_each((a.e)->'model_deps') m(k, v) ON ((a.e) ? 'model_deps');

    filter := filter || jsonb_build_object('model_deps', mdeps);
  ELSIF filter ? 'filter' THEN
    lname := filter->'filter';

    IF jsonb_typeof(lname) = 'array' THEN
      IF jsonb_array_length(lname) = 1 THEN
        lname := lname->>0;
      ELSIF jsonb_array_length(lname) = 2 THEN
        lalias := lname->>0;
        lname := lname->>1;
      ELSE
        RAISE SQLSTATE '22000' USING DETAIL = filter, HINT = 'Invalid "filter" column specification.';
      END IF;
    END IF;

    IF aliases ? lalias THEN
      ltable_rid := aliases->>lalias;
    ELSIF lalias IS NOT NULL THEN
      RAISE SQLSTATE '22000' USING DETAIL = filter, HINT = 'Unknown table alias in "filter" column specification.';
    END IF;

    SELECT c."RID" INTO colrid
    FROM _ermrest.known_columns c
    WHERE c.table_rid = ltable_rid
      AND c.column_name = lname#>>'{}'; -- #>>'{}' extracts lname as text...

    IF colrid IS NULL THEN
      RAISE SQLSTATE '23000' USING DETAIL = filter, HINT = 'Column not found for "filter" column specification.';
    END IF;

    IF lalias IS NOT NULL THEN
      filter := filter || jsonb_build_object('context', lalias);
    END IF;

    filter := filter || jsonb_build_object('filter', colrid);
  ELSE
    RAISE SQLSTATE '22000' USING DETAIL = filter, HINT = 'Malformed filter specification.';
  END IF;
  RETURN filter;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.compile_acl_binding(bt_rid text, binding_name text, acl_binding jsonb) RETURNS jsonb STABLE AS $$
DECLARE
  proj jsonb;
  proj_compiled jsonb = '[]';
  deps jsonb;
  nelems int;
  elem jsonb;
  pos int;
  ltable_rid text;
  fkey_name jsonb;
  fkey_rid text;
  fkey_bound boolean;
  rtable_rid text;
  aliases jsonb;
  lalias text;
  ralias text;
  colrid text;
  direction text;
  combiner text;
BEGIN
  IF acl_binding = 'false'::jsonb THEN
    RETURN acl_binding;
  ELSE
    deps := jsonb_build_object(bt_rid, NULL);
    aliases := jsonb_build_object('base', bt_rid);

    proj := acl_binding->'projection';
    IF jsonb_typeof(proj) = 'string' THEN
      -- desugar bare column name as simple projection list
      proj = jsonb_build_array(proj);
    END IF;

    ltable_rid := bt_rid;
    nelems := jsonb_array_length(proj);

    FOR pos IN 0 .. (nelems - 2) -- loop over all but final proj element
    LOOP
      elem := proj->pos;
      IF elem ?| ARRAY['inbound', 'outbound']::text[] THEN
        -- compile a path joining element

        IF elem ? 'context' THEN
	  lalias := elem->>'context';
	  IF aliases ? lalias THEN
            ltable_rid := aliases->>lalias;
	  ELSE
	    RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'Unknown table alias in "context" field.';
          END IF;
	END IF;

        IF elem ? 'outbound' THEN
	  direction := 'outbound';
	  fkey_name := elem->'outbound';
	  IF jsonb_typeof(fkey_name) != 'array' THEN
	    RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'Invalid "outbound" fkey name.';
	  END IF;
	  SELECT fk."RID", fk.pk_table_rid, fk.fk_table_rid = ltable_rid
	  INTO fkey_rid, rtable_rid, fkey_bound
	  FROM _ermrest.known_fkeys fk
	  JOIN _ermrest.known_schemas s ON (fk.schema_rid = s."RID")
	  WHERE s.schema_name = fkey_name->>0
	    AND fk.constraint_name = fkey_name->>1;
	ELSE
	  direction := 'inbound';
	  fkey_name := elem->'inbound';
	  IF jsonb_typeof(fkey_name) != 'array' THEN
	    RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'Invalid "inbound" fkey name.';
	  END IF;
	  SELECT fk."RID", fk.fk_table_rid, fk.pk_table_rid = ltable_rid
	  INTO fkey_rid, rtable_rid, fkey_bound
	  FROM _ermrest.known_fkeys fk
	  JOIN _ermrest.known_schemas s ON (fk.schema_rid = s."RID")
	  WHERE s.schema_name = fkey_name->>0
	    AND fk.constraint_name = fkey_name->>1;
	END IF;

	IF fkey_rid IS NULL THEN
	  RAISE SQLSTATE '23000' USING DETAIL = fkey_name, HINT = 'Unknown foreign key constraint.';
	ELSIF NOT fkey_bound THEN
	  RAISE SQLSTATE '23000' USING DETAIL = elem, HINT = 'Named foreign key not connected to table.';
	END IF;

        -- replace fkey name with fkey RID, preserving context and/or alias
        elem := elem || jsonb_build_object(direction, fkey_rid);
	deps := deps || jsonb_build_object(fkey_rid, NULL, ltable_rid, NULL);

        IF elem ? 'alias' THEN
	  ralias := elem->>'alias';
	  IF aliases ? ralias THEN
	    RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'Duplicate "alias" in ACL binding path.';
	  END IF;
	  aliases := aliases || jsonb_object_build(ralias, rtable_rid);
	END IF;

        ltable_rid := rtable_rid;
      ELSE
        elem := _ermrest.compile_filter(aliases, ltable_rid, elem);
	deps := deps || COALESCE(elem->'model_deps', jsonb_build_object(elem->>'filter', NULL));
      END IF;

      proj_compiled := proj_compiled || jsonb_build_array(elem);
    END LOOP;

    -- compile final projection
    IF jsonb_typeof(proj->(nelems-1)) = 'string' THEN
      SELECT c."RID" INTO colrid
      FROM _ermrest.known_columns c
      WHERE c.table_rid = ltable_rid
        AND c.column_name = proj->>(nelems-1);
      IF colrid IS NULL THEN
        RAISE SQLSTATE '23000' USING DETAIL = proj, HINT = 'Final projection column not found.';
      END IF;
      elem := to_jsonb(colrid);
      deps := deps || jsonb_build_object(colrid, NULL);
    ELSE
      RAISE SQLSTATE '22000' USING DETAIL = proj->(nelems-1), HINT = 'Invalid final projection name.';
    END IF;

    proj_compiled := proj_compiled || jsonb_build_array(elem);

    RETURN acl_binding || jsonb_build_object(
      'projection', proj_compiled,
      'model_deps', deps
    );
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.decompile_filter(aliases jsonb, ltable_rid text, filter jsonb, ts timestamptz) RETURNS jsonb STABLE AS $$
DECLARE
  colrid text;
  colname text;
  tname text;
  combiner text;
BEGIN
  IF filter ?| ARRAY['and', 'or']::text[] THEN
    IF elem ? 'and' THEN
      combiner := 'and';
    ELSE
      combiner := 'or';
    END IF;

    SELECT
      (filter || jsonb_build_object(
        combiner,
        to_jsonb(array_agg(_ermrest.decompile_filter(aliases, ltable_rid, a.e, ts)))
       )) - 'model_deps'
    INTO filter
    FROM jsonb_array_elements(filter->combiner) a(e);
  ELSIF filter ? 'filter' THEN
    -- compiled filters are already desugared
    colrid := filter->>'filter';

    SELECT (c.rowdata)->>'column_name' INTO colname
    FROM _ermrest_history.known_columns c
    WHERE c."RID" = colrid
      AND c.during @> COALESCE(ts, now());

    IF colname IS NULL THEN
      RAISE SQLSTATE '23000' USING DETAIL = filter, HINT = 'Column not found for "filter" column specification.';
    END IF;

    IF filter ? 'context' THEN
      filter := (filter || jsonb_build_object('filter', jsonb_build_array(filter->>'context', colname))) - 'context';
    ELSE
      filter := filter || jsonb_build_object('filter', colname);
    END IF;
  ELSE
    RAISE SQLSTATE '22000' USING DETAIL = filter, HINT = 'Malformed filter specification.';
  END IF;
  RETURN filter;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.decompile_acl_binding(bt_rid text, binding_name text, acl_binding jsonb, ts timestamptz) RETURNS jsonb STABLE AS $$
DECLARE
  proj jsonb;
  proj_decompiled jsonb = '[]';
  nelems int;
  elem jsonb;
  pos int;
  ltable_rid text;
  fkey_name jsonb;
  fkey_rid text;
  fkey_bound boolean;
  rtable_rid text;
  aliases jsonb;
  lalias text;
  ralias text;
  colname text;
  direction text;
  combiner text;
BEGIN
  IF acl_binding = 'false'::jsonb THEN
    RETURN acl_binding;
  ELSE
    aliases := jsonb_build_object('base', bt_rid);

    -- compiled form is already de-sugared
    proj := acl_binding->'projection';
    ltable_rid := bt_rid;
    nelems := jsonb_array_length(proj);

    FOR pos IN 0 .. (nelems - 2) -- loop over all but final proj element
    LOOP
      elem := proj->pos;
      IF elem ?| ARRAY['inbound', 'outbound']::text[] THEN
        -- compile a path joining element

        IF elem ? 'context' THEN
	  lalias := elem->>'context';
	  IF aliases ? lalias THEN
            ltable_rid := aliases->>lalias;
	  ELSE
	    RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'Unknown table alias in "context" field.';
          END IF;
	END IF;

        IF elem ? 'outbound' THEN
	  direction := 'outbound';
	  fkey_rid := elem->>'outbound';
	  SELECT jsonb_build_array((s.rowdata)->>'schema_name', (fk.rowdata)->>'constraint_name'), (fk.rowdata)->>'pk_table_rid', t."RID" = ltable_rid
	  INTO fkey_name, rtable_rid
	  FROM _ermrest_history.known_fkeys fk
	  JOIN _ermrest_history.known_schemas s ON ((fk.rowdata)->>'schema_rid' = s."RID")
	  LEFT JOIN _ermrest_history.known_tables t ON ((fk.rowdata)->>'fk_table_rid' = t."RID")
	  WHERE fk."RID" = fkey_rid
	    AND (fk.rowdata)->>'fk_table_rid' = ltable_rid
	    AND fk.during @> COALESCE(ts, now())
	    AND s.during @> COALESCE(ts, now());
	ELSE
	  direction := 'inbound';
	  fkey_rid := elem->>'inbound';
	  SELECT jsonb_build_array((s.rowdata)->>'schema_name', (fk.rowdata)->>'constraint_name'), (fk.rowdata)->>'fk_table_rid', t."RID" = ltable_rid
	  INTO fkey_name, rtable_rid, fkey_bound
	  FROM _ermrest_history.known_fkeys fk
	  JOIN _ermrest_history.known_schemas s ON ((fk.rowdata)->>'schema_rid' = s."RID")
	  LEFT JOIN _ermrest_history.known_tables t ON ((fk.rowdata)->>'pk_table_rid' = t."RID")
	  WHERE fk."RID" = fkey_rid
	    AND fk.during @> COALESCE(ts, now())
	    AND s.during @> COALESCE(ts, now());
	END IF;

	IF fkey_name IS NULL THEN
	  RAISE SQLSTATE '23000' USING DETAIL = fkey_rid, HINT = 'Unknown foreign key constraint.';
	ELSIF NOT fkey_bound THEN
	  RAISE SQLSTATE '23000' USING DETAIL = elem, HINT = 'Named foreign key not connected to table.';
	END IF;

        -- replace fkey RID with fkey name, preserving context and/or alias
        elem := elem || jsonb_build_object(direction, fkey_name);

        IF elem ? 'alias' THEN
	  ralias := elem->>'alias';
	  IF aliases ? ralias THEN
	    RAISE SQLSTATE '22000' USING DETAIL = elem, HINT = 'Duplicate "alias" in ACL binding path.';
	  END IF;
	  aliases := aliases || jsonb_object_build(ralias, rtable_rid);
	END IF;

        ltable_rid := rtable_rid;
      ELSE
        elem := _ermrest.decompile_filter(aliases, ltable_rid, elem, ts);
      END IF;

      elem := elem - 'model_deps';
      proj_decompiled := proj_decompiled || jsonb_build_array(elem);
    END LOOP;

    -- decompile final projection
    IF jsonb_typeof(proj->(nelems-1)) = 'string' THEN
      SELECT c.column_name INTO colname
      FROM _ermrest.known_columns c
      WHERE c.table_rid = ltable_rid
        AND c."RID" = proj->>(nelems-1);
      IF colname IS NULL THEN
        RAISE SQLSTATE '23000' USING DETAIL = proj, HINT = 'Final projection column not found.';
      END IF;
      elem := to_jsonb(colname);
    ELSE
      RAISE SQLSTATE '22000' USING DETAIL = proj->(nelems-1), HINT = 'Invalid final projection name.';
    END IF;

    proj_decompiled := proj_decompiled || jsonb_build_array(elem);

    acl_binding := acl_binding - 'model_deps';
    RETURN acl_binding || jsonb_build_object(
      'projection', proj_decompiled
    );
  END IF;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION _ermrest.compile_acl_bindings(_ermrest.known_tables, acl_bindings jsonb) RETURNS jsonb STABLE AS $$
SELECT COALESCE(jsonb_object_agg(b.n, _ermrest.compile_acl_binding(($1)."RID", b.n, b.b)), '{}'::jsonb)
FROM jsonb_each(acl_bindings) b(n, b);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.compile_acl_bindings(_ermrest.known_columns, acl_bindings jsonb) RETURNS jsonb STABLE AS $$
SELECT COALESCE(jsonb_object_agg(b.n, _ermrest.compile_acl_binding(($1).table_rid, b.n, b.b)), '{}'::jsonb)
FROM jsonb_each(acl_bindings) b(n, b);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.compile_acl_bindings(_ermrest.known_fkeys, acl_bindings jsonb) RETURNS jsonb STABLE AS $$
SELECT COALESCE(jsonb_object_agg(b.n, _ermrest.compile_acl_binding(($1).pk_table_rid, b.n, b.b)), '{}'::jsonb)
FROM jsonb_each(acl_bindings) b(n, b);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.compile_acl_bindings(_ermrest.known_pseudo_fkeys, acl_bindings jsonb) RETURNS jsonb STABLE AS $$
SELECT COALESCE(jsonb_object_agg(b.n, _ermrest.compile_acl_binding(($1).pk_table_rid, b.n, b.b)), '{}'::jsonb)
FROM jsonb_each(acl_bindings) b(n, b);
$$ LANGUAGE SQL;


CREATE OR REPLACE FUNCTION _ermrest.decompile_acl_bindings(_ermrest_history.known_tables, ts timestamptz) RETURNS jsonb STABLE AS $$
SELECT COALESCE(jsonb_object_agg(b.n, _ermrest.decompile_acl_binding($1."RID", b.n, b.b, $2)), '{}'::jsonb)
FROM jsonb_each( ($1.rowdata)->'acl_bindings') b(n, b);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.decompile_acl_bindings(_ermrest_history.known_columns, ts timestamptz) RETURNS jsonb STABLE AS $$
SELECT COALESCE(jsonb_object_agg(b.n, _ermrest.decompile_acl_binding(($1.rowdata)->>'table_rid', b.n, b.b, $2)), '{}'::jsonb)
FROM jsonb_each( ($1.rowdata)->'acl_bindings') b(n, b);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.decompile_acl_bindings(_ermrest_history.known_fkeys, ts timestamptz) RETURNS jsonb STABLE AS $$
SELECT COALESCE(jsonb_object_agg(b.n, _ermrest.decompile_acl_binding(($1.rowdata)->>'pk_table_rid', b.n, b.b, $2)), '{}'::jsonb)
FROM jsonb_each( ($1.rowdata)->'acl_bindings') b(n, b);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.decompile_acl_bindings(_ermrest_history.known_pseudo_fkeys, ts timestamptz) RETURNS jsonb STABLE AS $$
SELECT COALESCE(jsonb_object_agg(b.n, _ermrest.decompile_acl_binding(($1.rowdata)->>'pk_table_rid', b.n, b.b, $2)), '{}'::jsonb)
FROM jsonb_each( ($1.rowdata)->'acl_bindings') b(n, b);
$$ LANGUAGE SQL;


CREATE OR REPLACE FUNCTION _ermrest.known_catalogs(ts timestamptz)
RETURNS TABLE ("RID" text, acls jsonb, annotations jsonb) AS $$
  SELECT s."RID", (s.rowdata)->'acls', (s.rowdata)->'annotations'
  FROM _ermrest_history.known_catalogs s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_catalog_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, annotations jsonb, acls jsonb) AS $$
SELECT
  "RID",
  annotations,
  acls
FROM _ermrest.known_catalogs($1) s
WHERE "RID" = '0'
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_schemas(ts timestamptz)
RETURNS TABLE ("RID" text, schema_name text, comment text, acls jsonb, annotations jsonb) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_name')::text AS "schema_name",
    (s.rowdata->>'comment')::text AS "comment",
    (s.rowdata)->'acls',
    (s.rowdata)->'annotations'
  FROM _ermrest_history.known_schemas s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_schemas_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_name text, comment text, annotations jsonb, acls jsonb) AS $$
SELECT
  s."RID",
  s.schema_name,
  s.comment,
  s.annotations,
  s.acls
FROM _ermrest.known_schemas($1) s
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

RETURNS TABLE ("RID" text, table_rid text, column_num int, column_name text, type_rid text, not_null boolean, column_default text, comment text, acls jsonb, acl_bindings jsonb, annotations jsonb) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'table_rid')::text AS "table_rid",
    (s.rowdata->>'column_num')::int AS "column_num",
    (s.rowdata->>'column_name')::text AS "column_name",
    (s.rowdata->>'type_rid')::text AS "type_rid",
    (s.rowdata->>'not_null')::boolean AS "not_null",
    (s.rowdata->>'column_default')::text AS "column_default",
    (s.rowdata->>'comment')::text AS "comment",
    (s.rowdata)->'acls',
    (s.rowdata)->'acl_bindings',
    (s.rowdata)->'annotations'
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
  c.annotations,
  c.acls
FROM _ermrest.known_columns($1) c
LEFT OUTER JOIN _ermrest.known_pseudo_notnulls($1) n ON (n.column_rid = c."RID")
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_tables(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, table_name text, table_kind text, comment text, acls jsonb, acl_bindings jsonb, annotations jsonb) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_rid')::text "schema_rid",
    (s.rowdata->>'table_name')::text "table_name",
    (s.rowdata->>'table_kind')::text "table_kind",
    (s.rowdata->>'comment')::text "comment",
    (s.rowdata)->'acls',
    (s.rowdata)->'acl_bindings',
    (s.rowdata)->'annotations'
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
  t.annotations,
  t.acls,
  COALESCE(c.columns, ARRAY[]::jsonb[]) AS columns
FROM _ermrest.known_tables($1) t
LEFT OUTER JOIN (
  SELECT
    c.table_rid,
    array_agg(to_jsonb(c.*) ORDER BY c.column_num)::jsonb[] AS columns
  FROM _ermrest.known_columns_denorm($1) c
  GROUP BY c.table_rid
) c ON (t."RID" = c.table_rid)
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

IF _ermrest.table_exists('public', 'ermrest_client') THEN
  ALTER TABLE public.ermrest_client RENAME TO "ERMrest_Client";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN id TO "ID";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN display_name TO "Display_Name";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN full_name TO "Full_Name";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN email TO "Email";
  ALTER TABLE public."ERMrest_Client" RENAME COLUMN client_obj TO "Client_Object";
ELSIF NOT _ermrest.table_exists('public', 'ERMrest_Client') THEN
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
  UPDATE _ermrest.known_tables
  SET acls = '{"insert": [], "update": [], "delete": [], "select": [], "enumerate": []}'
  WHERE "RID" = _ermrest.find_table_rid('public', 'ERMrest_Client');
END IF;

IF NOT _ermrest.table_exists('public', 'ERMrest_Group') THEN
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
  UPDATE _ermrest.known_tables
  SET acls = '{"insert": [], "update": [], "delete": [], "select": [], "enumerate": []}'
  WHERE "RID" = _ermrest.find_table_rid('public', 'ERMrest_Group');
END IF;

CREATE OR REPLACE FUNCTION _ermrest.known_keys(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, table_rid text, column_rids jsonb, comment text, annotations jsonb) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_rid')::text "schema_rid",
    (s.rowdata->>'constraint_name')::text "constraint_name",
    (s.rowdata->>'table_rid')::text "table_rid",
    (s.rowdata)->'column_rids',
    (s.rowdata->>'comment')::text "comment",
    (s.rowdata)->'annotations'
  FROM _ermrest_history.known_keys s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_keys(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, table_rid text, column_rids jsonb, comment text, annotations jsonb) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'constraint_name')::text "constraint_name",
    (s.rowdata->>'table_rid')::text "table_rid",
    (s.rowdata)->'column_rids',
    (s.rowdata->>'comment')::text "comment",
    (s.rowdata)->'annotations'
  FROM _ermrest_history.known_pseudo_keys s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_keys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, table_rid text, column_rids jsonb, comment text, annotations jsonb) AS $$
SELECT
  k."RID",
  k.schema_rid,
  k.constraint_name,
  k.table_rid,
  k.column_rids,
  k."comment",
  k.annotations
FROM _ermrest.known_keys($1) k
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_keys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, table_rid text, column_rids jsonb, comment text, annotations jsonb) AS $$
SELECT
  k."RID",
  k.constraint_name,
  k.table_rid,
  k.column_rids,
  k."comment",
  k.annotations
FROM _ermrest.known_pseudo_keys($1) k
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_fkeys(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, fk_table_rid text, pk_table_rid text, fkc_pkc_rids jsonb, delete_rule text, update_rule text, comment text, acls jsonb, acl_bindings jsonb, annotations jsonb) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'schema_rid')::text "schema_rid",
    (s.rowdata->>'constraint_name')::text "constraint_name",
    (s.rowdata->>'fk_table_rid')::text "fk_table_rid",
    (s.rowdata->>'pk_table_rid')::text "pk_table_rid",
    (s.rowdata)->'fkc_pkc_rids',
    (s.rowdata->>'delete_rule')::text "delete_rule",
    (s.rowdata->>'update_rule')::text "update_rule",
    (s.rowdata->>'comment')::text "comment",
    (s.rowdata)->'acls',
    (s.rowdata)->'acl_bindings',
    (s.rowdata)->'annotations'
  FROM _ermrest_history.known_fkeys s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_fkeys(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, fk_table_rid text, pk_table_rid text, fkc_pkc_rids jsonb, comment text, acls jsonb, acl_bindings jsonb, annotations jsonb) AS $$
  SELECT
    s."RID",
    (s.rowdata->>'constraint_name')::text "constraint_name",
    (s.rowdata->>'fk_table_rid')::text "fk_table_rid",
    (s.rowdata->>'pk_table_rid')::text "pk_table_rid",
    (s.rowdata)->'fkc_pkc_rids',
    (s.rowdata->>'comment')::text "comment",
    (s.rowdata)->'acls',
    (s.rowdata)->'acl_bindings',
    (s.rowdata)->'annotations'
  FROM _ermrest_history.known_pseudo_fkeys s
  WHERE s.during @> COALESCE($1, now());
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_fkeys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, schema_rid text, constraint_name text, fk_table_rid text, pk_table_rid text, fkc_pkc_rids jsonb, delete_rule text, update_rule text, comment text, annotations jsonb, acls jsonb) AS $$
SELECT
  fk."RID",
  fk.schema_rid,
  fk.constraint_name,
  fk.fk_table_rid,
  fk.pk_table_rid,
  fk.fkc_pkc_rids,
  fk.delete_rule,
  fk.update_rule,
  fk."comment",
  fk.annotations,
  fk.acls
FROM _ermrest.known_fkeys($1) fk
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.known_pseudo_fkeys_denorm(ts timestamptz)
RETURNS TABLE ("RID" text, constraint_name text, fk_table_rid text, pk_table_rid text, fkc_pkc_rids jsonb, comment text, annotations jsonb, acls jsonb) AS $$
SELECT
  fk."RID",
  fk.constraint_name,
  fk.fk_table_rid,
  fk.pk_table_rid,
  fk.fkc_pkc_rids,
  fk."comment",
  fk.annotations,
  fk.acls
FROM _ermrest.known_pseudo_fkeys($1) fk
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.create_historical_dynacl_func(rname text) RETURNS void AS $def$
BEGIN
  EXECUTE
    'CREATE OR REPLACE FUNCTION _ermrest.known_' || rname || '_dynacls(ts timestamptz)'
    'RETURNS TABLE ("RID" text,' || 'acl_bindings jsonb) AS $$'
    ' SELECT s."RID", _ermrest.decompile_acl_bindings(s, $1)'
    ' FROM _ermrest_history.known_' || rname || 's s'
    ' WHERE s.during @> COALESCE($1, now()) AND (s.rowdata->''acl_bindings'') != ''{}'';'
    '$$ LANGUAGE SQL;' ;
END;
$def$ LANGUAGE plpgsql;

PERFORM _ermrest.create_historical_dynacl_func('table');
PERFORM _ermrest.create_historical_dynacl_func('column');
PERFORM _ermrest.create_historical_dynacl_func('fkey');
PERFORM _ermrest.create_historical_dynacl_func('pseudo_fkey');

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

