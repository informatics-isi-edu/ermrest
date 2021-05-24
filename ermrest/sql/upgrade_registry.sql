
-- 
-- Copyright 2017, 2021 University of Southern California
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

DROP INDEX IF EXISTS ermrest.simple_registry_id_deleted_on_idx;

DO $$
BEGIN

IF (SELECT True
    FROM information_schema.columns
    WHERE table_schema = 'ermrest'
      AND table_name = 'simple_registry'
      AND column_name = 'alias_target') IS NULL THEN

  -- perform catalog naming feature upgrade
  ALTER TABLE ermrest.simple_registry
    ALTER COLUMN id TYPE text,
    ADD COLUMN id_owner text[],
    ADD COLUMN alias_target text,
    ADD CONSTRAINT simple_registry_alias_target_fkey
      FOREIGN KEY (alias_target) REFERENCES ermrest.simple_registry(id)
      ON UPDATE CASCADE ON DELETE SET NULL;

END IF;

END;
$$ LANGUAGE plpgsql;
