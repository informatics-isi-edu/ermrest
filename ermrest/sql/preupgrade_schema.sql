
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

DO $preupgrade$
<< preupgrade >>
BEGIN
-- NOTE, we don't indent this block so editing below is easier...
-- We use a lot of conditionals rather than idempotent DDL to make successful operation quieter...
IF (SELECT True FROM information_schema.schemata WHERE schema_name = '_ermrest') THEN

-- DROP lots of stuff that may get redefined by subsequent ermrest_schema.sql step
-- because we don't always maintain a stable internal schema to allow in-place redefinitions

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

CREATE OR REPLACE FUNCTION _ermrest.table_exists(sname text, tname text) RETURNS boolean AS $$
SELECT COALESCE((SELECT True FROM information_schema.tables WHERE table_schema = $1 AND table_name = $2), False);
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION _ermrest.column_exists(sname text, tname text, cname text) RETURNS boolean AS $$
SELECT COALESCE((SELECT True FROM information_schema.columns WHERE table_schema = $1 AND table_name = $2 AND column_name = $3), False);
$$ LANGUAGE SQL;

-- ALTER existing live tables to upgrade to latest expected structure

-- known_catalogs did not exist in any prior form so we can skip for now

IF _ermrest.table_exists('_ermrest', 'known_schemas')
   AND NOT _ermrest.column_exists('_ermrest', 'known_schemas', 'acls') THEN
  DROP TRIGGER IF EXISTS ermrest_history_delete ON _ermrest.known_schemas;
  DROP TRIGGER IF EXISTS ermrest_history_insert ON _ermrest.known_schemas;
  DROP TRIGGER IF EXISTS ermrest_history_update ON _ermrest.known_schemas;
  ALTER TABLE _ermrest.known_schemas
    ADD COLUMN acls jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN annotations jsonb NOT NULL DEFAULT '{}';
  UPDATE _ermrest.known_schemas v
  SET
    acls = COALESCE(
      (SELECT jsonb_object_agg(acl, to_jsonb(members)) FROM _ermrest.known_schema_acls s WHERE s.schema_rid = v."RID"),
      '{}'::jsonb
    ),
    annotations = COALESCE(
      (SELECT jsonb_object_agg(annotation_uri, to_jsonb(annotation_value)) FROM _ermrest.known_schema_annotations s WHERE s.schema_rid = v."RID"),
      '{}'::jsonb
    );
  DROP TABLE _ermrest.known_schema_acls;
  DROP TABLE _ermrest.known_schema_annotations;
END IF;

IF _ermrest.table_exists('_ermrest', 'known_tables')
   AND NOT _ermrest.column_exists('_ermrest', 'known_tables', 'acls') THEN
  DROP TRIGGER IF EXISTS ermrest_history_delete ON _ermrest.known_tables;
  DROP TRIGGER IF EXISTS ermrest_history_insert ON _ermrest.known_tables;
  DROP TRIGGER IF EXISTS ermrest_history_update ON _ermrest.known_tables;
  ALTER TABLE _ermrest.known_tables
    ADD COLUMN acls jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN acl_bindings jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN annotations jsonb NOT NULL DEFAULT '{}';
  UPDATE _ermrest.known_tables v
  SET
    acls = COALESCE(
      (SELECT jsonb_object_agg(acl, to_jsonb(members)) FROM _ermrest.known_table_acls s WHERE s.table_rid = v."RID"),
      '{}'::jsonb
    ),
    acl_bindings = COALESCE(
      (SELECT jsonb_object_agg(binding_name, binding) FROM _ermrest.known_table_dynacls s WHERE s.table_rid = v."RID"),
      '{}'::jsonb
    ),
    annotations = COALESCE(
      (SELECT jsonb_object_agg(annotation_uri, to_jsonb(annotation_value)) FROM _ermrest.known_table_annotations s WHERE s.table_rid = v."RID"),
      '{}'::jsonb
    );
  DROP TABLE _ermrest.known_table_acls;
  DROP TABLE _ermrest.known_table_dynacls;
  DROP TABLE _ermrest.known_table_annotations;
END IF;

IF _ermrest.table_exists('_ermrest', 'known_columns')
   AND NOT _ermrest.column_exists('_ermrest', 'known_columns', 'acls') THEN
   DROP TRIGGER IF EXISTS ermrest_history_delete ON _ermrest.known_columns;
   DROP TRIGGER IF EXISTS ermrest_history_insert ON _ermrest.known_columns;
   DROP TRIGGER IF EXISTS ermrest_history_update ON _ermrest.known_columns;
  ALTER TABLE _ermrest.known_columns
    ADD COLUMN acls jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN acl_bindings jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN annotations jsonb NOT NULL DEFAULT '{}';
  UPDATE _ermrest.known_columns v
  SET
    acls = COALESCE(
      (SELECT jsonb_object_agg(acl, to_jsonb(members)) FROM _ermrest.known_column_acls s WHERE s.column_rid = v."RID"),
      '{}'::jsonb
    ),
    acl_bindings = COALESCE(
      (SELECT jsonb_object_agg(binding_name, binding) FROM _ermrest.known_column_dynacls s WHERE s.column_rid = v."RID"),
      '{}'::jsonb
    ),
    annotations = COALESCE(
      (SELECT jsonb_object_agg(annotation_uri, to_jsonb(annotation_value)) FROM _ermrest.known_column_annotations s WHERE s.column_rid = v."RID"),
      '{}'::jsonb
    );
  DROP TABLE _ermrest.known_column_acls;
  DROP TABLE _ermrest.known_column_dynacls;
  DROP TABLE _ermrest.known_column_annotations;
END IF;

IF _ermrest.table_exists('_ermrest', 'known_keys')
   AND NOT _ermrest.column_exists('_ermrest', 'known_keys', 'annotations') THEN
   DROP TRIGGER IF EXISTS ermrest_history_delete ON _ermrest.known_keys;
   DROP TRIGGER IF EXISTS ermrest_history_insert ON _ermrest.known_keys;
   DROP TRIGGER IF EXISTS ermrest_history_update ON _ermrest.known_keys;
  ALTER TABLE _ermrest.known_keys
    ADD COLUMN column_rids jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN annotations jsonb NOT NULL DEFAULT '{}';
  UPDATE _ermrest.known_keys v
  SET
    column_rids = COALESCE(
      (SELECT jsonb_object_agg(s.column_rid, NULL) FROM _ermrest.known_key_columns s WHERE s.key_rid = v."RID"),
      '{}'::jsonb
    ),
    annotations = COALESCE(
      (SELECT jsonb_object_agg(annotation_uri, to_jsonb(annotation_value)) FROM _ermrest.known_key_annotations s WHERE s.key_rid = v."RID"),
      '{}'::jsonb
    );
  DROP TABLE _ermrest.known_key_columns;
  DROP TABLE _ermrest.known_key_annotations;
END IF;

IF _ermrest.table_exists('_ermrest', 'known_pseudo_keys')
   AND NOT _ermrest.column_exists('_ermrest', 'known_pseudo_keys', 'annotations') THEN
   DROP TRIGGER IF EXISTS ermrest_history_delete ON _ermrest.known_pseudo_keys;
   DROP TRIGGER IF EXISTS ermrest_history_insert ON _ermrest.known_pseudo_keys;
   DROP TRIGGER IF EXISTS ermrest_history_update ON _ermrest.known_pseudo_keys;
  ALTER TABLE _ermrest.known_pseudo_keys
    ADD COLUMN column_rids jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN annotations jsonb NOT NULL DEFAULT '{}';
  UPDATE _ermrest.known_pseudo_keys v
  SET
    column_rids = COALESCE(
      (SELECT jsonb_object_agg(s.column_rid, NULL) FROM _ermrest.known_pseudo_key_columns s WHERE s.key_rid = v."RID"),
      '{}'::jsonb
    ),
    annotations = COALESCE(
      (SELECT jsonb_object_agg(annotation_uri, to_jsonb(annotation_value)) FROM _ermrest.known_pseudo_key_annotations s WHERE s.key_rid = v."RID"),
      '{}'::jsonb
    );
  DROP TABLE _ermrest.known_pseudo_key_columns;
  DROP TABLE _ermrest.known_pseudo_key_annotations;
END IF;

IF _ermrest.table_exists('_ermrest', 'known_fkeys')
   AND NOT _ermrest.column_exists('_ermrest', 'known_fkeys', 'acls') THEN
   DROP TRIGGER IF EXISTS ermrest_history_delete ON _ermrest.known_fkeys;
   DROP TRIGGER IF EXISTS ermrest_history_insert ON _ermrest.known_fkeys;
   DROP TRIGGER IF EXISTS ermrest_history_update ON _ermrest.known_fkeys;
  ALTER TABLE _ermrest.known_fkeys
    ADD COLUMN fkc_pkc_rids jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN acls jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN acl_bindings jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN annotations jsonb NOT NULL DEFAULT '{}';
  UPDATE _ermrest.known_fkeys v
  SET
    fkc_pkc_rids = COALESCE(
      (SELECT jsonb_object_agg(fk_column_rid, pk_column_rid) FROM _ermrest.known_fkey_columns s WHERE s.fkey_rid = v."RID"),
      '{}'::jsonb
    ),
    acls = COALESCE(
      (SELECT jsonb_object_agg(acl, to_jsonb(members)) FROM _ermrest.known_fkey_acls s WHERE s.fkey_rid = v."RID"),
      '{}'::jsonb
    ),
    acl_bindings = COALESCE(
      (SELECT jsonb_object_agg(binding_name, binding) FROM _ermrest.known_fkey_dynacls s WHERE s.fkey_rid = v."RID"),
      '{}'::jsonb
    ),
    annotations = COALESCE(
      (SELECT jsonb_object_agg(annotation_uri, to_jsonb(annotation_value)) FROM _ermrest.known_fkey_annotations s WHERE s.fkey_rid = v."RID"),
      '{}'::jsonb
    );
  DROP TABLE _ermrest.known_fkey_columns;
  DROP TABLE _ermrest.known_fkey_acls;
  DROP TABLE _ermrest.known_fkey_dynacls;
  DROP TABLE _ermrest.known_fkey_annotations;
END IF;

IF _ermrest.table_exists('_ermrest', 'known_pseudo_fkeys')
   AND NOT _ermrest.column_exists('_ermrest', 'known_pseudo_fkeys', 'acls') THEN
   DROP TRIGGER IF EXISTS ermrest_history_delete ON _ermrest.known_pseudo_fkeys;
   DROP TRIGGER IF EXISTS ermrest_history_insert ON _ermrest.known_pseudo_fkeys;
   DROP TRIGGER IF EXISTS ermrest_history_update ON _ermrest.known_pseudo_fkeys;
  ALTER TABLE _ermrest.known_pseudo_fkeys
    ADD COLUMN fkc_pkc_rids jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN acls jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN acl_bindings jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN annotations jsonb NOT NULL DEFAULT '{}';
  UPDATE _ermrest.known_pseudo_fkeys v
  SET
    fkc_pkc_rids = COALESCE(
      (SELECT jsonb_object_agg(fk_column_rid, pk_column_rid) FROM _ermrest.known_pseudo_fkey_columns s WHERE s.fkey_rid = v."RID"),
      '{}'::jsonb
    ),
    acls = COALESCE(
      (SELECT jsonb_object_agg(acl, to_jsonb(members)) FROM _ermrest.known_pseudo_fkey_acls s WHERE s.fkey_rid = v."RID"),
      '{}'::jsonb
    ),
    acl_bindings = COALESCE(
      (SELECT jsonb_object_agg(binding_name, binding) FROM _ermrest.known_pseudo_fkey_dynacls s WHERE s.fkey_rid = v."RID"),
      '{}'::jsonb
    ),
    annotations = COALESCE(
      (SELECT jsonb_object_agg(annotation_uri, to_jsonb(annotation_value)) FROM _ermrest.known_pseudo_fkey_annotations s WHERE s.fkey_rid = v."RID"),
      '{}'::jsonb
    );
  DROP TABLE _ermrest.known_pseudo_fkey_columns;
  DROP TABLE _ermrest.known_pseudo_fkey_acls;
  DROP TABLE _ermrest.known_pseudo_fkey_dynacls;
  DROP TABLE _ermrest.known_pseudo_fkey_annotations;
END IF;

END IF;
END preupgrade;
$preupgrade$ LANGUAGE plpgsql;

