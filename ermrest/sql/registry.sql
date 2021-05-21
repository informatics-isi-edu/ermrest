
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

CREATE SCHEMA IF NOT EXISTS ermrest;

CREATE SEQUENCE IF NOT EXISTS ermrest.simple_registry_id_seq;

CREATE TABLE IF NOT EXISTS ermrest.simple_registry (
  id text PRIMARY KEY DEFAULT (nextval('ermrest.simple_registry_id_seq')::text),
  id_owner text[],
  descriptor jsonb,
  alias_target text,
  created_on timestamp with time zone DEFAULT (now()),
  deleted_on timestamp with time zone DEFAULT NULL,
  CONSTRAINT simple_registry_alias_target_fkey
    FOREIGN KEY (alias_target) REFERENCES ermrest.simple_registry(id)
    ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS simple_registry_deleted_on_idx    ON ermrest.simple_registry (deleted_on);
CREATE INDEX IF NOT EXISTS simple_registry_created_on_idx    ON ermrest.simple_registry (created_on);
CREATE INDEX IF NOT EXISTS simple_registry_id_notdeleted_idx ON ermrest.simple_registry (id) WHERE deleted_on IS NULL;
CREATE INDEX IF NOT EXISTS simple_registry_id_target_notdeleted_idx ON ermrest.simple_registry (id, alias_target) WHERE deleted_on IS NULL;
