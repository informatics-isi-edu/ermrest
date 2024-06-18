
-- 
-- Copyright 2017-2024 University of Southern California
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

DO $registry_upgrade$
<< registry_upgrade >>
BEGIN

IF (SELECT True
    FROM information_schema.tables
    WHERE table_schema = 'ermrest'
      AND table_name = 'simple_registry') THEN

  -- port legacy content from simple_registry -> registry

  PERFORM setval('ermrest.registry_id_seq', nextval('ermrest.simple_registry_id_seq'));

  INSERT INTO ermrest.registry ("RCT", "RMT", id, is_catalog, deleted_on, owner, descriptor, alias_target)
  SELECT
    COALESCE(created_on, now()),
    now(),
    id,
    descriptor IS NOT NULL AND descriptor != 'null'::jsonb,
    deleted_on,
    id_owner,
    CASE WHEN descriptor = 'null'::jsonb THEN NULL::jsonb ELSE descriptor END,
    alias_target
  FROM ermrest.simple_registry
  ;

  DROP TABLE ermrest.simple_registry;
  DROP SEQUENCE IF EXISTS ermrest.simple_registry_id_seq;

END IF;

END registry_upgrade
$registry_upgrade$ LANGUAGE plpgsql;

