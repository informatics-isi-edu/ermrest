
-- 
-- Copyright 2018 University of Southern California
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

--DEALLOCATE PREPARE ALL;

PREPARE ermrest_current_request_snaptime AS SELECT now();

PREPARE ermrest_current_catalog_snaptime AS
  SELECT GREATEST(
    (SELECT ts FROM _ermrest.model_last_modified ORDER BY ts DESC LIMIT 1),
    (SELECT ts FROM _ermrest.table_last_modified ORDER BY ts DESC LIMIT 1)
  );

PREPARE ermrest_current_catalog_snaptime_encoded AS
  SELECT _ermrest.tstzencode(
    GREATEST(
      (SELECT ts FROM _ermrest.model_last_modified ORDER BY ts DESC LIMIT 1),
      (SELECT ts FROM _ermrest.table_last_modified ORDER BY ts DESC LIMIT 1)
    )
  );

PREPARE ermrest_current_model_snaptime AS
  SELECT ts FROM _ermrest.model_last_modified ORDER BY ts DESC LIMIT 1;

PREPARE ermrest_normalized_history_snaptime (timestamptz) AS
  SELECT GREATEST(
    (SELECT ts FROM _ermrest.model_modified WHERE ts <= $1 ORDER BY ts DESC LIMIT 1),
    (SELECT ts FROM _ermrest.table_modified WHERE ts <= $1 ORDER BY ts DESC LIMIT 1)
  );

PREPARE ermrest_current_history_amendver (timestamptz) AS
  SELECT GREATEST(
    $1,
    (SELECT ts FROM _ermrest.catalog_amended WHERE during @> $1 ORDER BY ts DESC LIMIT 1)
  );

PREPARE ermrest_introspect_catalogs (timestamptz) AS
  SELECT acls, annotations FROM _ermrest.known_catalogs($1);

PREPARE ermrest_introspect_types (timestamptz) AS
  SELECT * FROM _ermrest.known_types($1)
  ORDER BY array_element_type_rid NULLS FIRST, domain_element_type_rid NULLS FIRST;

PREPARE ermrest_introspect_tables (timestamptz) AS
  SELECT * FROM _ermrest.known_tables_denorm($1);

PREPARE ermrest_introspect_keys (timestamptz) AS
  SELECT * FROM _ermrest.known_keys_denorm($1);

PREPARE ermrest_introspect_pseudo_keys (timestamptz) AS
  SELECT * FROM _ermrest.known_pseudo_keys_denorm($1);

PREPARE ermrest_introspect_fkeys (timestamptz) AS
  SELECT * FROM _ermrest.known_fkeys_denorm($1);

PREPARE ermrest_introspect_pseudo_fkeys (timestamptz) AS
  SELECT * FROM _ermrest.known_pseudo_fkeys_denorm($1);

PREPARE ermrest_introspect_table_acl_bindings (timestamptz) AS
  SELECT
    table_rid,
    jsonb_object_agg(a.binding_name, a.binding) AS dynacls
  FROM _ermrest.known_table_acl_bindings($1) a
  GROUP BY a.table_rid ;

PREPARE ermrest_introspect_column_acl_bindings (timestamptz) AS
  SELECT
    column_rid,
    jsonb_object_agg(a.binding_name, a.binding) AS dynacls
  FROM _ermrest.known_column_acl_bindings($1) a
  GROUP BY a.column_rid ;

PREPARE ermrest_introspect_fkey_acl_bindings (timestamptz) AS
  SELECT
    fkey_rid,
    jsonb_object_agg(a.binding_name, a.binding) AS dynacls
  FROM _ermrest.known_fkey_acl_bindings($1) a
  GROUP BY a.fkey_rid ;

PREPARE ermrest_introspect_pseudo_fkey_acl_bindings (timestamptz) AS
  SELECT
    fkey_rid,
    jsonb_object_agg(a.binding_name, a.binding) AS dynacls
  FROM _ermrest.known_pseudo_fkey_acl_bindings($1) a
  GROUP BY a.fkey_rid ;

