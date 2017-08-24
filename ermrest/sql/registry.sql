
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

DO $$
BEGIN

IF (SELECT True FROM information_schema.schemata WHERE schema_name = 'ermrest') IS NULL THEN
  CREATE SCHEMA ermrest;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = 'ermrest' AND table_name = 'simple_registry') IS NULL THEN
  CREATE TABLE ermrest.simple_registry (
    id bigserial PRIMARY KEY,
    descriptor text,
    deleted_on timestamp with time zone DEFAULT NULL,
    created_on timestamp with time zone DEFAULT (now())
  );
  CREATE INDEX IF NOT EXISTS simple_registry_deleted_on_idx    ON ermrest.simple_registry (deleted_on);
  CREATE INDEX IF NOT EXISTS simple_registry_id_notdeleted_idx ON ermrest.simple_registry (id) WHERE deleted_on IS NULL;
  CREATE INDEX IF NOT EXISTS simple_registry_created_on_idx    ON ermrest.simple_registry (created_on);
END IF;

END;
$$ LANGUAGE plpgsql;
