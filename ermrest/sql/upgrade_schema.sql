
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

-- help transition a legacy catalog to current schema
DO $upgrade$
<< upgrade_schema >>
-- DECLARE
BEGIN
-- NOTE, we don't indent this block so editing below is easier...

-- heal any newly created data version tracking
INSERT INTO _ermrest.table_last_modified (table_rid, ts)
SELECT t."RID", now() FROM _ermrest.known_tables t WHERE t.table_kind = 'r'
ON CONFLICT (table_rid) DO NOTHING;

-- RAISE NOTICE 'Completed translating any legacy schema to current ERMrest schema.';

END upgrade_schema;
$upgrade$ LANGUAGE plpgsql;

