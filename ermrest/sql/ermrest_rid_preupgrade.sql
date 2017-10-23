
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

DO $rid_preupgrade$
<< rid_preupgrade >>
DECLARE
  rid_columns jsonb[];
  drop_views jsonb[];
  rid_fkeys jsonb[];
  entry jsonb;
  ridlike_column_keys jsonb[];
  history_tables jsonb[];
BEGIN
-- NOTE, we don't indent this block so editing below is easier...
-- We use a lot of conditionals rather than idempotent DDL to make successful operation quieter...

IF (SELECT True FROM information_schema.schemata WHERE schema_name = '_ermrest') IS NULL THEN
  CREATE SCHEMA _ermrest;
END IF;

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


IF (SELECT True FROM information_schema.sequences WHERE sequence_schema = '_ermrest' AND sequence_name = 'rid_seq') IS NULL THEN
  -- MAXVALUE 2**63 - 1 default
  CREATE SEQUENCE _ermrest.rid_seq NO CYCLE;
ELSE
  -- drop previous 2**53 - 1 max for javascript numbers
  ALTER SEQUENCE _ermrest.rid_seq NO MAXVALUE;
END IF;


IF (SELECT True
    FROM information_schema.domains d
    WHERE d.domain_schema = 'public'
      AND d.domain_name = 'ermrest_rid'
      AND d.data_type = 'bigint'
    )
THEN
  -- We need to upgrade development catalog to latest, converting int8 RIDs to text using urlb32_encode()

  -- DROP lots of stuff that will get redefined by subsequent ermrest_schema.sql step

  -- drop all  'ermrest_syscols' triggers
  -- drop all  'ermrest_table_change' triggers
  -- drop all  'ermrest_history' triggers
  -- drop all  _ermrest_history.maintain_* functions

  DROP FUNCTION IF EXISTS _ermrest.maintain_row() CASCADE;
  DROP FUNCTION IF EXISTS _ermrest.table_change() CASCADE;

  DROP FUNCTION IF EXISTS _ermrest.find_schema_rid(text) CASCADE;
  DROP FUNCTION IF EXISTS _ermrest.find_table_rid(text, text) CASCADE;
  DROP FUNCTION IF EXISTS _ermrest.find_column_rid(text, text, text) CASCADE;
  DROP FUNCTION IF EXISTS _ermrest.find_key_rid(text, text, text[]) CASCADE;
  DROP FUNCTION IF EXISTS _ermrest.find_fkey_rid(text, text, text[], text, text, text[]) CASCADE;

  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_fkeys_denorm(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_fkeys_denorm(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_fkey_columns(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_fkey_columns(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_fkeys(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_fkeys(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_keys_denorm(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_keys_denorm(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_key_columns(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_key_columns(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_keys(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_keys(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_tables_denorm(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_tables(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_columns_denorm(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_notnulls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_columns(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_types(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_schemas_denorm(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_schemas(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_catalog_denorm(timestamptz);

  DROP FUNCTION IF EXISTS _ermrest.known_catalog_annotations(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_schema_annotations(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_table_annotations(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_column_annotations(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_key_annotations(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_key_annotations(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_fkey_annotations(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_fkey_annotations(timestamptz);
  
  DROP FUNCTION IF EXISTS _ermrest.known_catalog_acls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_schema_acls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_table_acls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_column_acls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_fkey_acls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_fkey_acls(timestamptz);

  DROP FUNCTION IF EXISTS _ermrest.known_table_dynacls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_column_dynacls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_fkey_dynacls(timestamptz);
  DROP FUNCTION IF EXISTS _ermrest.known_pseudo_fkey_dynacls(timestamptz);

  DROP FUNCTION IF EXISTS _ermrest.create_historical_annotation_func(text, text);
  DROP FUNCTION IF EXISTS _ermrest.create_historical_dynacl_func(text, text);
  DROP FUNCTION IF EXISTS _ermrest.create_historical_acl_func(text, text);
  
  DROP FUNCTION IF EXISTS _ermrest.create_annotation_table(text, text, text);
  DROP FUNCTION IF EXISTS _ermrest.create_dynacl_table(text, text, text);
  DROP FUNCTION IF EXISTS _ermrest.create_acl_table(text, text, text);
  
  DROP FUNCTION IF EXISTS _ermrest.data_change_event(text, text);
  DROP FUNCTION IF EXISTS _ermrest.data_change_event(int8);
  DROP FUNCTION IF EXISTS _ermrest.amended_version_bump(tstzrange);
  DROP FUNCTION IF EXISTS _ermrest.model_change_event_by_oid();
  DROP FUNCTION IF EXISTS _ermrest.model_change_event();
  DROP FUNCTION IF EXISTS _ermrest.model_version_bump();
  DROP FUNCTION IF EXISTS _ermrest.rescan_introspect_by_name();
  DROP FUNCTION IF EXISTS _ermrest.rescan_introspect_by_oid();
  DROP FUNCTION IF EXISTS _ermrest.enable_table_histories();
  DROP FUNCTION IF EXISTS _ermrest.enable_table_history(int8);

  DROP VIEW IF EXISTS _ermrest.introspect_fkey_columns;
  DROP VIEW IF EXISTS _ermrest.introspect_fkeys;
  DROP VIEW IF EXISTS _ermrest.introspect_key_columns;
  DROP VIEW IF EXISTS _ermrest.introspect_keys;
  DROP VIEW IF EXISTS _ermrest.introspect_columns;
  DROP VIEW IF EXISTS _ermrest.introspect_tables;
  DROP VIEW IF EXISTS _ermrest.introspect_types;
  DROP VIEW IF EXISTS _ermrest.introspect_schemas;

  ALTER DOMAIN public.ermrest_rid RENAME TO ermrest_rid_int8;
  CREATE DOMAIN public.ermrest_rid AS text;

  SELECT
    array_agg(
      jsonb_build_object(
        'sname', c.table_schema,
	'tname', c.table_name,
	'cname', c.column_name,
	'default', to_jsonb(c.column_default)
      )
    ) INTO rid_columns
  FROM information_schema.columns c
  JOIN information_schema.tables t ON (c.table_schema = t.table_schema AND c.table_name = t.table_name)
  WHERE c.column_name = 'RID'
    AND t.table_type = 'BASE TABLE'
    AND t.table_schema NOT IN ('_ermrest_history');

/* t.table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
    AND t.table_schema !~ '^pg_(toast_)temp'
    AND t.table_type = 'BASE TABLE'
    AND c.domain_schema = 'public'
    AND c.domain_name = 'ermrest_rid_int8' ; */

  SELECT
    array_agg(
      jsonb_build_object('schema_view', vrw.ev_class::regclass::text)
    ) INTO drop_views
  FROM pg_catalog.pg_depend dep
  JOIN pg_catalog.pg_rewrite vrw ON (dep.objid = vrw.oid)
  JOIN pg_catalog.pg_attribute c ON (dep.refobjid = c.attrelid AND dep.refobjsubid = c.attnum)
  JOIN pg_catalog.pg_class r ON (c.attrelid = r.oid)
  WHERE r.relkind = 'r'
    AND c.attname = 'RID';

  -- drop all dependent views... DBA will need to restore somehow!
  FOREACH entry IN ARRAY COALESCE(drop_views, ARRAY[]::jsonb[])
  LOOP
    EXECUTE 'DROP VIEW IF EXISTS ' || (entry->>'schema_view') || ' CASCADE;' ;
  END LOOP;

  -- don't handle composite fkeys over RID...
  -- don't handle indirect fkeys over RID fkeys...
  SELECT
    array_agg(fkey) INTO rid_fkeys
  FROM (
    SELECT
      jsonb_build_object(
        'fkname', fk.constraint_name,
	'on_update', fk.update_rule,
	'on_delete', fk.delete_rule,
	'fsname', fkc.table_schema,
	'ftname', fkc.table_name,
	'fcnames', array_agg(fkc.column_name::text ORDER BY fkc.ordinal_position),
	'rsname', kc.table_schema,
	'rtname', kc.table_name,
	'rcnames', array_agg(kc.column_name::text ORDER BY fkc.ordinal_position)
      ) AS fkey
    FROM information_schema.referential_constraints fk
    JOIN information_schema.key_column_usage fkc
      ON (    fkc.constraint_schema = fk.constraint_schema
          AND fkc.constraint_name = fk.constraint_name)
    JOIN information_schema.key_column_usage kc
      ON (    kc.constraint_schema = fk.unique_constraint_schema
          AND kc.constraint_name = fk.unique_constraint_name
          AND fkc.position_in_unique_constraint = kc.ordinal_position)
    GROUP BY
      fk.constraint_name, fk.update_rule, fk.delete_rule,
      fkc.table_schema, fkc.table_name,
      kc.table_schema, kc.table_name
  ) s
  WHERE ARRAY[to_jsonb('RID'::text)] && (SELECT array_agg(e) FROM jsonb_array_elements(fkey->'rcnames') s(e));

  FOREACH entry IN ARRAY COALESCE(rid_fkeys, ARRAY[]::jsonb[])
  LOOP
    -- validate our assumptions
    IF array_length((SELECT array_agg(e) FROM jsonb_array_elements(entry->'rcnames') s(e)), 1) > 1
    THEN
      RAISE EXCEPTION 'We cannot handle a composite foreign key over a RID column.';
    END IF;

    -- drop foreign key constraints depending on RID
    EXECUTE 'ALTER TABLE '
      || quote_ident(entry->>'fsname') || '.' || quote_ident(entry->>'ftname')
      || ' DROP CONSTRAINT IF EXISTS ' || quote_ident(entry->>'fkname') || ';' ;
  END LOOP;

  IF (SELECT True FROM information_schema.schemata WHERE schema_name = '_ermrest_history')
  THEN
    SELECT
      array_agg(
        DISTINCT
	jsonb_build_object('htname', table_name::text)
      ) INTO history_tables
    FROM information_schema.tables it
    WHERE it.table_schema = '_ermrest_history';

    -- HACK: find all possible history keys that store RID data (bare column names or RIDs as JSONB)
    SELECT
      array_agg(
        DISTINCT
        CASE
          WHEN sb1.rowdata->'schema_name' = to_jsonb('_ermrest'::text)
  	    THEN c1.rowdata->'column_name'
          ELSE to_jsonb(c1."RID")
        END
      ) INTO ridlike_column_keys
    FROM _ermrest_history.known_columns c1
    JOIN _ermrest_history.known_types t1   ON (c1.rowdata->'type_rid' = to_jsonb(t1."RID") AND c1.during && t1.during)
    JOIN _ermrest_history.known_schemas s1 ON (t1.rowdata->'schema_rid' = to_jsonb(s1."RID") AND t1.during && s1.during)
    JOIN _ermrest_history.known_tables tb1 ON (c1.rowdata->'table_rid' = to_jsonb(tb1."RID") AND c1.during && tb1.during)
    JOIN _ermrest_history.known_schemas sb1 ON (tb1.rowdata->'schema_rid' = to_jsonb(sb1."RID") AND tb1.during && sb1.during)
    LEFT OUTER JOIN (
      SELECT * FROM _ermrest_history.known_fkey_columns
      UNION
      SELECT * FROM _ermrest_history.known_pseudo_fkey_columns
    ) fkc
      ON (fkc.rowdata->'fk_column_rid' = to_jsonb(c1."RID") AND fkc.during && c1.during)
    LEFT OUTER JOIN _ermrest_history.known_columns c2
      ON (fkc.rowdata->'pk_column_rid' = to_jsonb(c2."RID") AND fkc.during && c2.during)
    LEFT OUTER JOIN _ermrest_history.known_types t2   ON (c2.rowdata->'type_rid' = to_jsonb(t2."RID") AND c2.during && t2.during)
    LEFT OUTER JOIN _ermrest_history.known_schemas s2 ON (t2.rowdata->'schema_rid' = to_jsonb(s2."RID") AND t2.during && s2.during)
    WHERE t1.rowdata->'type_name' = to_jsonb('ermrest_rid'::text) AND s1.rowdata->'schema_name' = to_jsonb('public'::text)
       OR t2.rowdata->'type_name' = to_jsonb('ermrest_rid'::text) AND s2.rowdata->'schema_name' = to_jsonb('public'::text);

    FOREACH entry IN ARRAY COALESCE(history_tables, ARRAY[]::jsonb[])
    LOOP
      RAISE NOTICE 'Converting % . %  user=%', '_ermrest_history', entry->>'htname', entry->>'htname' ~ '^t[0-9]+$';

      EXECUTE 'DROP FUNCTION IF EXISTS _ermrest_history.'
        || quote_ident('maintain_' || (entry->>'htname'))
	|| '() CASCADE;';

      EXECUTE 'ALTER TABLE _ermrest_history.' || quote_ident(entry->>'htname')
        || ' ALTER COLUMN "RID" SET DATA TYPE ermrest_rid USING _ermrest.urlb32_encode("RID"::int8);' ;

      EXECUTE 'UPDATE _ermrest_history.' || quote_ident(entry->>'htname') || ' u'
        || ' SET rowdata = (SELECT jsonb_object_agg('
	|| (CASE WHEN entry->>'htname' ~ '^t[0-9]+$' THEN '_ermrest.urlb32_encode(m.k::text::int8)' ELSE 'm.k' END)::text || ','
	|| ' CASE WHEN to_jsonb(m.k) = ANY ($1) AND jsonb_typeof(m.v) = ''number'' THEN to_jsonb(_ermrest.urlb32_encode(m.v::text::int8)) ELSE v END'
	|| ' )'
	|| ' FROM jsonb_each(rowdata) m(k, v)) ;'
	USING ridlike_column_keys;

      IF entry->>'htname' ~ '^t[0-9]+$'
      THEN
        EXECUTE 'ALTER TABLE _ermrest_history.' || quote_ident(entry->>'htname')
          || ' RENAME TO '
	  || quote_ident( 't' || _ermrest.urlb32_encode(substring(entry->>'htname' from 2)::int8) )
	  || ';';
      END IF;
      
    END LOOP;

  END IF;

  -- convert referencing columns to base32 storage format
  FOREACH entry IN ARRAY COALESCE(rid_fkeys, ARRAY[]::jsonb[])
  LOOP
    RAISE NOTICE 'Converting % . % . %', entry->>'fsname', entry->>'ftname', entry->>'fcnames';
    
    EXECUTE 'ALTER TABLE '
      || quote_ident(entry->>'fsname') || '.' || quote_ident(entry->>'ftname')
      || ' ALTER COLUMN ' || quote_ident(entry->'fcnames'->>0) || ' DROP DEFAULT;' ;

    EXECUTE 'ALTER TABLE '
      || quote_ident(entry->>'fsname') || '.' || quote_ident(entry->>'ftname')
      || ' ALTER COLUMN ' || quote_ident(entry->'fcnames'->>0) || ' SET DATA TYPE text'
      || ' USING _ermrest.urlb32_encode(' || quote_ident(entry->'fcnames'->>0) || '::int8);' ;
  END LOOP;
  
  -- convert RIDs to base32 storage format
  FOREACH entry IN ARRAY COALESCE(rid_columns, ARRAY[]::jsonb[])
  LOOP
    RAISE NOTICE 'Converting % . % . "RID"', entry->>'sname', entry->>'tname';
    
    EXECUTE 'ALTER TABLE '
      || quote_ident(entry->>'sname') || '.' || quote_ident(entry->>'tname')
      || ' ALTER COLUMN "RID" DROP DEFAULT;' ;

    EXECUTE 'ALTER TABLE '
      || quote_ident(entry->>'sname') || '.' || quote_ident(entry->>'tname')
      || ' ALTER COLUMN "RID" SET DATA TYPE ermrest_rid USING _ermrest.urlb32_encode("RID"::int8);' ;

    IF entry->'default' != 'null'::jsonb
    THEN
      EXECUTE 'ALTER TABLE '
        || quote_ident(entry->>'sname') || '.' || quote_ident(entry->>'tname')
        || ' ALTER COLUMN "RID" SET DEFAULT _ermrest.urlb32_encode(nextval(''_ermrest.rid_seq''));' ;
    END IF;
  END LOOP;

  -- restore foreign keys we dropped above
  FOREACH entry IN ARRAY COALESCE(rid_fkeys, ARRAY[]::jsonb[])
  LOOP
    RAISE NOTICE 'Restoring fkey constraint % on table % . %', entry->>'fkname', entry->>'fsname', entry->>'ftname';
    EXECUTE 'ALTER TABLE '
      || quote_ident(entry->>'fsname') || '.' || quote_ident(entry->>'ftname')
      || ' ADD CONSTRAINT ' || quote_ident(entry->>'fkname')
      || ' FOREIGN KEY (' || quote_ident(entry->'fcnames'->>0) || ' ) REFERENCES '
      || quote_ident(entry->>'rsname') || '.' || quote_ident(entry->>'rtname')
      || ' (' || quote_ident(entry->'rcnames'->>0) || ' )'
      || ' ON DELETE ' || COALESCE(entry->>'on_delete', 'NO ACTION')
      || ' ON UPDATE ' || COALESCE(entry->>'on_update', 'NO ACTION') || ';' ;
  END LOOP;

  IF (SELECT True FROM information_schema.schemata WHERE schema_name = '_ermrest_history')
  THEN
    -- fudge history of type definitions to always have text-based ermrest_rid domain
    -- so it's consistent with data mangling we did above...
    UPDATE _ermrest_history.known_types
    SET rowdata = jsonb_set(rowdata, '{domain_element_type_rid}'::text[], to_jsonb((SELECT "RID" FROM _ermrest.known_types WHERE type_name = 'text')))
    WHERE rowdata->>'type_name' = 'ermrest_rid';
  END IF;

  RAISE NOTICE 'Completed conversion of int8 ermrest_rid to text ermrest_rid.';
END IF;
END rid_preupgrade;
$rid_preupgrade$ LANGUAGE plpgsql;

