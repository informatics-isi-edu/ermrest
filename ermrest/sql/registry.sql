
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
  is_persistent boolean NOT NULL DEFAULT True,
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

-- to help with dev servers running earlier draft of code
ALTER TABLE ermrest.registry
  ADD COLUMN IF NOT EXISTS is_persistent boolean NOT NULL DEFAULT True;

CREATE INDEX IF NOT EXISTS registry_deleted_on_idx    ON ermrest.registry (deleted_on);
CREATE INDEX IF NOT EXISTS registry_id_notdeleted_idx ON ermrest.registry (id) WHERE deleted_on IS NULL;
CREATE INDEX IF NOT EXISTS registry_id_target_notdeleted_idx ON ermrest.registry (id, alias_target) WHERE deleted_on IS NULL;

COMMENT ON COLUMN "ermrest"."registry"."id" IS 'Catalog identifier or alias used in URLs';
COMMENT ON COLUMN "ermrest"."registry"."name" IS 'Short, human-readable label for entry';
COMMENT ON COLUMN "ermrest"."registry"."description" IS 'Human-readable description of entry';
COMMENT ON COLUMN "ermrest"."registry"."is_catalog" IS 'True for catalog entries with backing database storage';
COMMENT ON COLUMN "ermrest"."registry"."is_persistent" IS 'False for catalog entries which should auto-expire';
COMMENT ON COLUMN "ermrest"."registry"."alias_target" IS 'Catalog to which this alias entry is bound';
COMMENT ON COLUMN "ermrest"."registry"."clone_source" IS 'Catalog from which content was copied';
COMMENT ON COLUMN "ermrest"."registry"."deleted_on" IS 'Catalog soft-deletion timestamp';
COMMENT ON COLUMN "ermrest"."registry"."owner" IS 'Owner ACL for catalog management APIs';

-- ADD SELF-REFERENCE
INSERT INTO ermrest.registry ("RCT", "RMT", id, is_catalog, is_persistent, owner, descriptor, "name", description) VALUES
  (now(), now(), '0', True, True, ARRAY[]::text[], '{"dbname":"ermrest"}', 'ERMrest Registry', 'Tracking database for all dynamically provisioned ERMrest catalogs.')
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
  (_ermrest.find_table_rid('ermrest', 'registry'), 'select', ARRAY['*']::text[]),
  (_ermrest.find_table_rid('public', 'ERMrest_Client'), 'select', ARRAY['*']::text[])
  ON CONFLICT DO NOTHING;

-- hide columns that could leak internal operational info
INSERT INTO _ermrest.known_column_acls (column_rid, acl, members) VALUES
  (_ermrest.find_column_rid('ermrest', 'registry', 'descriptor'), 'enumerate', ARRAY[]::text[]),
  (_ermrest.find_column_rid('ermrest', 'registry', 'descriptor'), 'select', ARRAY[]::text[]),
  (_ermrest.find_column_rid('ermrest', 'registry', 'owner'), 'select', ARRAY[]::text[]),
  (_ermrest.find_column_rid('public', 'ERMrest_Client', 'Email'), 'enumerate', ARRAY[]::text[]),
  (_ermrest.find_column_rid('public', 'ERMrest_Client', 'Email'), 'select', ARRAY[]::text[]),
  (_ermrest.find_column_rid('public', 'ERMrest_Client', 'Client_Object'), 'enumerate', ARRAY[]::text[]),
  (_ermrest.find_column_rid('public', 'ERMrest_Client', 'Client_Object'), 'select', ARRAY[]::text[]),
  (_ermrest.find_column_rid('public', 'ERMrest_Client', 'Full_Name'), 'enumerate', ARRAY[]::text[]),
  (_ermrest.find_column_rid('public', 'ERMrest_Client', 'Full_Name'), 'select', ARRAY[]::text[])
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
    AND column_name NOT IN ('name', 'description', 'clone_source', 'is_persistent')
  ON CONFLICT DO NOTHING;

INSERT INTO _ermrest.known_column_dynacls (column_rid, binding_name, binding) VALUES
  (_ermrest.find_column_rid('ermrest', 'registry', 'owner'), 'view_by_owner',
   '{"types": ["select"], "projection": ["owner"], "projection_type": "acl", "scope_acl": ["*"]}'::jsonb)
  ON CONFLICT DO NOTHING;

-- SET DEFAULT PRESENTATION HINTS
INSERT INTO _ermrest.known_catalog_annotations (annotation_uri, annotation_value) VALUES
  ( 'tag:isrd.isi.edu,2019:chaise-config',
    $${
      "defaultTable": {
        "schema": "ermrest",
        "table": "registry"
      },
      "displayDefaultExport": false
    }$$::jsonb
  )
  ON CONFLICT DO NOTHING;

INSERT INTO _ermrest.known_schema_annotations (schema_rid, annotation_uri, annotation_value) VALUES
  ( _ermrest.find_schema_rid('ermrest'),
    'tag:misd.isi.edu,2015:display',
    $${
      "name_style": {
        "underline_space": true,
        "title_case": true
      }
    }$$::jsonb
  ),
  ( _ermrest.find_schema_rid('public'),
    'tag:misd.isi.edu,2015:display',
    $${
      "name_style": {
        "underline_space": true,
        "title_case": true
      }
    }$$::jsonb
  )
  ON CONFLICT DO NOTHING;

INSERT INTO _ermrest.known_table_annotations (table_rid, annotation_uri, annotation_value) VALUES
  ( _ermrest.find_table_rid('public', 'ERMrest_Client'),
    'tag:isrd.isi.edu,2016:table-display',
    $${
        "row_name": {
          "row_markdown_pattern": "{{{Display_Name}}}"
        }
    }$$::jsonb
  ),
  ( _ermrest.find_table_rid('ermrest', 'registry'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "ERMrest Registry" }$$
  ),
   ( _ermrest.find_table_rid('ermrest', 'registry'),
    'tag:isrd.isi.edu,2019:source-definitions',
    $${
        "columns": true,
        "sources": {
          "S_RCB": {
            "source": [{"outbound": ["ermrest", "registry_rcb_fkey"]}, "RID"],
            "comment": "Client who created this entry"
          },
          "S_RMB": {
            "source": [{"outbound": ["ermrest", "registry_rmb_fkey"]}, "RID"],
            "comment": "Client who last modified this entry"
          },
          "S_clone_source": {
            "source": [{"outbound": ["ermrest", "registry_clone_source_fkey"]}, "RID"],
            "comment": "Catalog from which content was copied"
          },
          "S_alias_target": {
            "source": [{"outbound": ["ermrest", "registry_alias_target_fkey"]}, "RID"],
            "comment": "Catalog to which the alias entry resolves"
          },
          "S_aliases": {
            "source": [{"inbound": ["ermrest", "registry_alias_target_fkey"]}, "RID"],
            "comment": "Alias entries resolving to this catalog"
          },
          "S_clones": {
            "source": [{"inbound": ["ermrest", "registry_clone_source_fkey"]}, "RID"],
            "comment": "Catalogs with content copied from this catalog"
          }
        }
    }$$
  ),
  ( _ermrest.find_table_rid('ermrest', 'registry'),
    'tag:isrd.isi.edu,2016:visible-columns',
    $${
        "compact": [
          "id",
          {
            "markdown_name": "Description",
            "comment": "Name and description content",
            "display": {
              "template_engine": "handlebars",
              "markdown_pattern": "{{#if name}}#### {{{name}}} \n{{/if}}{{#if description}}{{{description}}}{{/if}}"
            }
          },
          {
            "markdown_name": "Status",
            "comment": "Status or mode of registry entry",
            "display": {
              "template_engine": "handlebars",
              "markdown_pattern": "{{#if _is_catalog}}{{#if _deleted_on}}Soft-deleted{{else}}{{#if _is_persistent}}Persistent{{else}}Ephemeral{{/if}}{{/if}} database{{#if clone_source}}\nClone of: {{{clone_source}}}{{/if}}{{else}}{{#if alias_target}}Alias for: {{{alias_target}}}{{else}}Reserved identifier{{/if}}{{/if}}"
            }
          },
          "RCT"
        ],
        "*": [
          "id",
          "name",
          "description",
          "is_catalog",
          "is_persistent",
          {"sourcekey": "S_alias_target"},
          {"sourcekey": "S_clone_source"},
          "owner",
          "RCT",
          {"sourcekey": "S_RCB"},
          "RMT",
          {"sourcekey": "S_RMB"},
          "deleted_on"
        ],
        "entry": [
          "id",
          "is_catalog",
          "is_persistent",
          {"sourcekey": "S_clone_source"},
          "name",
          "description"
        ],
        "filter": { "and": [
          {
            "markdown_name": "Has Name?",
            "comment": "Is the entry name field populated?",
            "source": "name",
            "ux_mode": "check_presence"
          },
          {
            "markdown_name": "Has Description?",
            "comment": "Is the entry description field populated?",
            "source": "description",
            "ux_mode": "check_presence"
          },
          {"source": "is_catalog"},
          {"source": "is_persistent"},
          {
            "markdown_name": "Is Deleted?",
            "comment": "Is the entry marked as deleted?",
            "source": "deleted_on",
            "ux_mode": "check_presence"
          },
          {"sourcekey": "S_alias_target"},
          {
            "markdown_name": "Has Aliases?",
            "comment": "Is the entry referenced as an alias target?",
            "sourcekey": "S_aliases",
            "ux_mode": "check_presence"
          },
          {"sourcekey": "S_clone_source"},
          {
            "markdown_name": "Has Clones?",
            "comment": "Is the entry referenced as a clone source?",
            "sourcekey": "S_clones",
            "ux_mode": "check_presence"
          },
          {"source": "RCT"},
          {"sourcekey": "S_RCB"},
          {"source": "RMT"},
          {"sourcekey": "S_RMB"},
          {"source": "deleted_on"}
        ]}
    }$$::jsonb
  ),
  ( _ermrest.find_table_rid('ermrest', 'registry'),
    'tag:isrd.isi.edu,2016:visible-foreign-keys',
    $${
         "*": [
           {"sourcekey": "S_aliases"},
           {"sourcekey": "S_clones"}
         ]
    }$$
  )
  ON CONFLICT DO NOTHING;

INSERT INTO _ermrest.known_column_annotations (column_rid, annotation_uri, annotation_value) VALUES
  ( _ermrest.find_column_rid('ermrest', 'registry', 'RCT'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Creation Time" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'RMT'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Last Modified Time" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'RMB'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Last Modified By" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'id'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "ID" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'id'),
    'tag:isrd.isi.edu,2016:column-display',
    $${
      "*": {
        "template_engine": "handlebars",
        "markdown_pattern": "[{{{id}}}](/chaise/recordset/#{{#encode _id}}{{/encode}})"
      }
    }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'name'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Name" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'description'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Description" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'deleted_on'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Deletion Time" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'owner'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Owner ACL" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'is_catalog'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Is Catalog?" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'clone_source'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Clone Source" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'alias_target'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Alias Target" }$$
  ),
  ( _ermrest.find_column_rid('ermrest', 'registry', 'is_persistent'),
    'tag:misd.isi.edu,2015:display',
    $${ "name": "Is Persistent?" }$$
  )
  ON CONFLICT DO NOTHING;

INSERT INTO _ermrest.known_fkey_annotations (fkey_rid, annotation_uri, annotation_value) VALUES
  ( _ermrest.find_fkey_rid('ermrest', 'registry_clone_source_fkey'),
    'tag:isrd.isi.edu,2016:foreign-key',
    $${
        "to_name": "Clone Source",
        "to_comment": "Catalog from which content was copied",
        "from_name": "Clone",
        "from_comment": "Catalog to which content was copied"
    }$$
  ),
  ( _ermrest.find_fkey_rid('ermrest', 'registry_alias_target_fkey'),
    'tag:isrd.isi.edu,2016:foreign-key',
    $${
        "to_name": "Alias Target",
        "to_comment": "Catalog to which this alias entry resolves",
        "from_name": "Alias",
        "from_comment": "Alias entry resolving to this catalog"
    }$$
  ),
  ( _ermrest.find_fkey_rid('ermrest', 'registry_rcb_fkey'),
    'tag:isrd.isi.edu,2016:foreign-key',
    $${
        "to_name": "Created By",
        "to_comment": "Client who created this entry",
        "from_name": "Created Registry Entry",
        "from_comment": "Registry entry created by this client"
    }$$
  ),
  ( _ermrest.find_fkey_rid('ermrest', 'registry_rmb_fkey'),
    'tag:isrd.isi.edu,2016:foreign-key',
    $${
        "to_name": "Last Modified By",
        "to_comment": "Client who last modified this entry",
        "from_name": "Last Modified Registry Entry",
        "from_comment": "Registry entry last modified by this client"
    }$$
  )
  ON CONFLICT DO NOTHING;
