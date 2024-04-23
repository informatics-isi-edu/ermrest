
-- 
-- Copyright 2012-2024 University of Southern California
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

CREATE SCHEMA IF NOT EXISTS ermrest;

CREATE SEQUENCE IF NOT EXISTS ermrest.registry_id_seq;

CREATE TABLE IF NOT EXISTS ermrest.registry (
  "RID" ermrest_rid UNIQUE NOT NULL DEFAULT (_ermrest.urlb32_encode(nextval('_ermrest.rid_seq'))),
  "RCT" ermrest_rct NOT NULL DEFAULT (now()),
  "RMT" ermrest_rmt NOT NULL DEFAULT (now()),
  "RCB" ermrest_rcb DEFAULT (_ermrest.current_client()),
  "RMB" ermrest_rmb DEFAULT (_ermrest.current_client()),
  id text PRIMARY KEY DEFAULT (nextval('ermrest.registry_id_seq')::text),
  is_catalog boolean NOT NULL DEFAULT True,
  deleted_on timestamp with time zone DEFAULT NULL,
  owner text[],
  descriptor jsonb,
  alias_target text,
  clone_source text,
  "name" text,
  description markdown,
  CONSTRAINT registry_catalog_needs_descriptor
    CHECK ((NOT is_catalog) OR (descriptor IS NOT NULL)),
  CONSTRAINT registry_catalog_blocks_alias_target
    CHECK ((NOT is_catalog) OR (alias_target IS NULL)),
  CONSTRAINT registry_alias_blocks_clone_source
    CHECK (is_catalog OR (clone_source IS NULL)),
  CONSTRAINT registry_alias_target_fkey
    FOREIGN KEY (alias_target) REFERENCES ermrest.registry(id)
    ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT registry_clone_source_fkey
    FOREIGN KEY (clone_source) REFERENCES ermrest.registry(id)
    ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT registry_rcb_fkey
    FOREIGN KEY ("RCB") REFERENCES public."ERMrest_Client"("ID")
    ON UPDATE CASCADE ON DELETE NO ACTION,
  CONSTRAINT registry_rmb_fkey
    FOREIGN KEY ("RMB") REFERENCES public."ERMrest_Client"("ID")
    ON UPDATE CASCADE ON DELETE NO ACTION
);

-- ADD SELF-REFERENCE
INSERT INTO ermrest.registry ("RCT", "RMT", id, is_catalog, owner, descriptor, "name", description) VALUES
  (now(), now(), '0', True, ARRAY[]::text[], '{"dbname":"ermrest"}', 'ERMrest Registry', 'Tracking database for all dynamically provisioned ERMrest catalogs.')
  ON CONFLICT DO NOTHING;

-- SET DEFAULT POLICY
INSERT INTO _ermrest.known_catalog_acls (acl, members) VALUES
  ('enumerate', ARRAY['*']::text[]),
  ('owner', ARRAY[]::text[]),
  ('select', ARRAY[]::text[]),
  ('insert', ARRAY[]::text[]),
  ('update', ARRAY[]::text[]),
  ('delete', ARRAY[]::text[])
  ON CONFLICT DO NOTHING;

SELECT _ermrest.model_change_event();

-- HACK: all entries can be listed by public?
INSERT INTO _ermrest.known_table_acls (table_rid, acl, members) VALUES
  (_ermrest.find_table_rid('ermrest', 'registry'), 'select', ARRAY['*']::text[])
  ON CONFLICT DO NOTHING;

-- NOTE: hide descriptor column which could leak internal ops data
INSERT INTO _ermrest.known_column_acls (column_rid, acl, members) VALUES
  (_ermrest.find_column_rid('ermrest', 'registry', 'descriptor'), 'enumerate', ARRAY[]::text[]),
  (_ermrest.find_column_rid('ermrest', 'registry', 'descriptor'), 'select', ARRAY[]::text[])
  ON CONFLICT DO NOTHING;

-- allow entry owners to do basic editing of their entries
INSERT INTO _ermrest.known_table_dynacls (table_rid, binding_name, binding) VALUES
  (_ermrest.find_table_rid('ermrest', 'registry'), 'update_by_owner',
   '{"types": ["update"], "projection": ["owner"], "projection_type": "acl", "scope_acl": ["*"]}'::jsonb)
  ON CONFLICT DO NOTHING;

-- suppress owner-based editing for most columns
INSERT INTO _ermrest.known_column_dynacls (column_rid, binding_name, binding)
  SELECT "RID", 'update_by_owner', 'false'::jsonb
  FROM _ermrest.known_columns
  WHERE table_rid = _ermrest.find_table_rid('ermrest', 'registry')
    AND column_name NOT IN ('name', 'description', 'clone_source')
  ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS registry_deleted_on_idx    ON ermrest.registry (deleted_on);
CREATE INDEX IF NOT EXISTS registry_id_notdeleted_idx ON ermrest.registry (id) WHERE deleted_on IS NULL;
CREATE INDEX IF NOT EXISTS registry_id_target_notdeleted_idx ON ermrest.registry (id, alias_target) WHERE deleted_on IS NULL;
