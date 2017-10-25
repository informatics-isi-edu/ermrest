
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
DECLARE
  proc record;

  pkey record;
  pk_rid text;
  t_rid text;
  
  pfkey record;
  ridmatch record;
  fk1_rid text;
  fk2_rid text;
  t1_rid text;
  t2_rid text;
BEGIN
-- NOTE, we don't indent this block so editing below is easier...

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_version') THEN
  DROP TABLE _ermrest.model_version;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'data_version') THEN
  DROP TABLE _ermrest.data_version;
END IF;

-- heal any newly created data version tracking
INSERT INTO _ermrest.table_last_modified (table_rid, ts)
SELECT t."RID", now() FROM _ermrest.known_tables t WHERE t.table_kind = 'r'
ON CONFLICT (table_rid) DO NOTHING;

-- helpers for converting old model decorations

CREATE OR REPLACE FUNCTION _ermrest.find_key_rid(sname text, tname text, cnames text[], OUT rid text, OUT is_physical boolean) AS $$
DECLARE
  t_rid text;
  c_rids text[];
BEGIN
  t_rid := _ermrest.find_table_rid($1, $2);

  SELECT array_agg(c."RID"::text ORDER BY c."RID") INTO c_rids
  FROM (SELECT unnest($3)) a (column_name)
  JOIN _ermrest.known_columns c ON (c.column_name = a.column_name AND c.table_rid = t_rid);

  SELECT k.key_rid INTO rid
  FROM (
    SELECT
      kc.key_rid,
      array_agg(kc.column_rid::text ORDER BY kc.column_rid) AS column_rids
    FROM _ermrest.known_key_columns kc JOIN _ermrest.known_keys k ON (kc.key_rid = k."RID")
    WHERE k.table_rid = t_rid
    GROUP BY kc.key_rid
  ) k
  WHERE k.column_rids = c_rids;
  IF rid IS NOT NULL THEN
    is_physical := True;
    RETURN;
  END IF;

  SELECT k.key_rid INTO rid
  FROM (
    SELECT
      kc.key_rid,
      array_agg(kc.column_rid::text ORDER BY kc.column_rid) AS column_rids
    FROM _ermrest.known_pseudo_key_columns kc JOIN _ermrest.known_pseudo_keys k ON (kc.key_rid = k."RID")
    WHERE k.table_rid = t_rid
    GROUP BY kc.key_rid
  ) k
  WHERE k.column_rids = c_rids;
  IF rid IS NOT NULL THEN
    is_physical := False;
    RETURN;
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION _ermrest.find_fkey_rid(fk_sname text, fk_tname text, fk_cnames text[], pk_sname text, pk_tname text, pk_cnames text[], OUT rid text, OUT is_physical boolean) AS $$
DECLARE
  fkt_rid text;
  pkt_rid text;
  fkc_rids text[];
  pkc_rids text[];
BEGIN
  fkt_rid := _ermrest.find_table_rid($1, $2);
  pkt_rid := _ermrest.find_table_rid($4, $5);

  SELECT array_agg(c."RID"::text ORDER BY c."RID") INTO fkc_rids
  FROM (SELECT unnest($3)) a (column_name)
  JOIN _ermrest.known_columns c ON (c.column_name = a.column_name AND c.table_rid = fkt_rid);

  SELECT array_agg(c."RID"::text ORDER BY c."RID") INTO pkc_rids
  FROM (SELECT unnest($6)) a (column_name)
  JOIN _ermrest.known_columns c ON (c.column_name = a.column_name AND c.table_rid = pkt_rid);

  SELECT fk.fkey_rid INTO rid
  FROM (
    SELECT
      fkc.fkey_rid,
      array_agg(fkc.fk_column_rid::text ORDER BY fkc.fk_column_rid) AS fk_column_rids,
      array_agg(fkc.pk_column_rid::text ORDER BY fkc.fk_column_rid) AS pk_column_rids
    FROM _ermrest.known_fkey_columns fkc
    JOIN _ermrest.known_fkeys fk ON (fkc.fkey_rid = fk."RID")
    WHERE fk.fk_table_rid = fkt_rid
      AND fk.pk_table_rid = pkt_rid
    GROUP BY fkc.fkey_rid
  ) fk
  WHERE fk.fk_column_rids = fkc_rids AND fk.pk_column_rids = pkc_rids;
  IF rid IS NOT NULL THEN
    is_physical := True;
    RETURN;
  END IF;

  SELECT fk.fkey_rid INTO rid
  FROM (
    SELECT
      fkc.fkey_rid,
      array_agg(fkc.fk_column_rid::text ORDER BY fkc.fk_column_rid) AS fk_column_rids,
      array_agg(fkc.pk_column_rid::text ORDER BY fkc.fk_column_rid) AS pk_column_rids
    FROM _ermrest.known_pseudo_fkey_columns fkc
    JOIN _ermrest.known_pseudo_fkeys fk ON (fkc.fkey_rid = fk."RID")
    WHERE fk.fk_table_rid = fkt_rid
      AND fk.pk_table_rid = pkt_rid
    GROUP BY fkc.fkey_rid
  ) fk
  WHERE fk.fk_column_rids = fkc_rids AND fk.pk_column_rids = pkc_rids;
  IF rid IS NOT NULL THEN
    is_physical := False;
    RETURN;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- convert legacy catalog "meta" policy to catalog ACLs
IF (SELECT True
    FROM information_schema.tables
    WHERE table_schema = '_ermrest' AND table_name = 'meta') THEN
  INSERT INTO _ermrest.known_catalog_acl (acl, members)
  SELECT
    CASE
      WHEN key = 'owner' THEN 'owner'
      WHEN key = 'read_user' THEN 'enumerate'
      WHEN key = 'content_read_user' THEN 'select'
      WHEN key = 'content_write_user' THEN 'write'
      WHEN key = 'schema_write_user' THEN 'create'
    END AS key,
    array_agg(value) AS members
  FROM _ermrest.meta
  WHERE key IN ('owner', 'read_user', 'content_read_user', 'content_write_user', 'schema_write_user')
  GROUP BY key;
  DROP TABLE _ermrest.meta;
END IF;

-- port legacy pseudo not-nulls
IF (SELECT True
    FROM information_schema.tables
    WHERE table_schema = '_ermrest' AND table_name = 'model_pseudo_notnull') THEN
  INSERT INTO _ermrest.known_pseudo_notnulls (column_rid)
  SELECT c."RID"
  FROM _ermrest.model_pseudo_notnull o
  JOIN _ermrest.known_schemas s ON (o.schema_name = s.schema_name)
  JOIN _ermrest.known_tables t  ON (o.table_name = t.table_name AND t.schema_rid = s."RID")
  JOIN _ermrest.known_columns c ON (o.column_name = c.column_name AND c.table_rid = t."RID");
  DROP TABLE _ermrest.model_pseudo_notnull;
END IF;

-- port legacy pseudo keys
IF (SELECT True
    FROM information_schema.tables
    WHERE table_schema = '_ermrest' AND table_name = 'model_pseudo_key') THEN
  FOR pkey IN SELECT * FROM _ermrest.model_pseudo_key LOOP
    t_rid := _ermrest.find_table_rid(pkey.schema_name, pkey.table_name);

    INSERT INTO _ermrest.known_pseudo_keys (constraint_name, table_rid, "comment")
    VALUES (COALESCE(pkey.name, 'fake_constraint_name_' || pkey.id), t_rid, pkey.comment)
    RETURNING "RID" INTO pk_rid;
	
    INSERT INTO _ermrest.known_pseudo_key_columns (key_rid, column_rid)
    SELECT pk_rid, c."RID"
    FROM (SELECT unnest(pkey.column_names)) kc (column_name)
    JOIN _ermrest.known_columns c ON (kc.column_name = c.column_name)
    WHERE c.table_rid = t_rid;
  END LOOP;
  DROP TABLE _ermrest.model_pseudo_key;
END IF;

-- port legacy pseudo foreign keys
IF (SELECT True
    FROM information_schema.tables
    WHERE table_schema = '_ermrest' AND table_name = 'model_pseudo_keyref') THEN

  FOR pfkey IN SELECT * FROM _ermrest.model_pseudo_keyref LOOP

    t1_rid := _ermrest.find_table_rid(pfkey.from_schema_name, pfkey.from_table_name);
    t2_rid := _ermrest.find_table_rid(pfkey.to_schema_name, pfkey.to_table_name);

    INSERT INTO _ermrest.known_pseudo_fkeys (constraint_name, fk_table_rid, pk_table_rid, "comment")
    VALUES (COALESCE(pfkey.name, 'fake_constraint_name_' || pfkey.id), t1_rid, t2_rid, pfkey.comment)
    RETURNING "RID" INTO fk1_rid;
	
    INSERT INTO _ermrest.known_pseudo_fkey_columns (fkey_rid, fk_column_rid, pk_column_rid)
    SELECT fk1_rid, c1."RID", c2."RID"
    FROM (
      SELECT unnest(pfkey.from_column_names), unnest(pfkey.to_column_names)
    ) fkc (from_column_name, to_column_name)
    JOIN _ermrest.known_columns c1 ON (fkc.from_column_name = c1.column_name)
    JOIN _ermrest.known_columns c2 ON (fkc.to_column_name = c2.column_name)
    WHERE c1.table_rid = t1_rid
      AND c2.table_rid = t2_rid;

  END LOOP;
  DROP TABLE _ermrest.model_pseudo_keyref;
END IF;

-- now port legacy model decorations

-- catalog-level
IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_catalog_acl') THEN
  INSERT INTO _ermrest.known_catalog_acls (acl, members)
  SELECT acl, members
  FROM _ermrest.model_catalog_acl
  WHERE members IS NOT NULL;
  DROP TABLE _ermrest.model_catalog_acl;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_catalog_annotation') THEN
  INSERT INTO _ermrest.known_catalog_annotations (annotation_uri, annotation_value)
  SELECT annotation_uri, COALESCE(annotation_value, 'null'::json)
  FROM _ermrest.model_catalog_annotation;
  DROP TABLE _ermrest.model_catalog_annotation;
END IF;

-- schema-level
IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_schema_acl') THEN
  INSERT INTO _ermrest.known_schema_acls (schema_rid, acl, members)
  SELECT _ermrest.find_schema_rid(a.schema_name), a.acl, a.members
  FROM _ermrest.model_schema_acl a WHERE a.members IS NOT NULL;
  DROP TABLE _ermrest.model_schema_acl;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_schema_annotation') THEN
  INSERT INTO _ermrest.known_schema_annotations (schema_rid, annotation_uri, annotation_value)
  SELECT _ermrest.find_schema_rid(a.schema_name), a.annotation_uri, COALESCE(a.annotation_value, 'null'::json)
  FROM _ermrest.model_schema_annotation a;
  DROP TABLE _ermrest.model_schema_annotation;
END IF;

-- table-level
IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_table_acl') THEN
  INSERT INTO _ermrest.known_table_acls (table_rid, acl, members)
  SELECT _ermrest.find_table_rid(a.schema_name, a.table_name), a.acl, a.members
  FROM _ermrest.model_table_acl a WHERE a.members IS NOT NULL;
  DROP TABLE _ermrest.model_table_acl;
END IF;
  
IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_table_dynacl') THEN
  INSERT INTO _ermrest.known_table_dynacls (table_rid, binding_name, binding)
  SELECT _ermrest.find_table_rid(a.schema_name, a.table_name), a.binding_name, a.binding
  FROM _ermrest.model_table_dynacl a;
  DROP TABLE _ermrest.model_table_dynacl;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_table_annotation') THEN
  INSERT INTO _ermrest.known_table_annotations (table_rid, annotation_uri, annotation_value)
  SELECT _ermrest.find_table_rid(a.schema_name, a.table_name), a.annotation_uri, COALESCE(a.annotation_value, 'null'::json)
  FROM _ermrest.model_table_annotation a;
  DROP TABLE _ermrest.model_table_annotation;
END IF;
  
-- column-level
IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_column_acl') THEN
  INSERT INTO _ermrest.known_column_acls (column_rid, acl, members)
  SELECT _ermrest.find_column_rid(a.schema_name, a.table_name, a.column_name), a.acl, a.members
  FROM _ermrest.model_column_acl a WHERE a.members IS NOT NULL;
  DROP TABLE _ermrest.model_column_acl;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_column_dynacl') THEN
  INSERT INTO _ermrest.known_column_dynacls (column_rid, binding_name, binding)
  SELECT _ermrest.find_column_rid(a.schema_name, a.table_name, a.column_name), a.binding_name, a.binding
  FROM _ermrest.model_column_dynacl a;
  DROP TABLE _ermrest.model_column_dynacl;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_column_annotation') THEN
  INSERT INTO _ermrest.known_column_annotations (column_rid, annotation_uri, annotation_value)
  SELECT _ermrest.find_column_rid(a.schema_name, a.table_name, a.column_name), a.annotation_uri, COALESCE(a.annotation_value, 'null'::json)
  FROM _ermrest.model_column_annotation a;
  DROP TABLE _ermrest.model_column_annotation;
END IF;

-- key-level
IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_key_annotation') THEN
  FOR pfkey IN SELECT * FROM _ermrest.model_key_annotation LOOP
    ridmatch := _ermrest.find_key_rid(pfkey.schema_name, pfkey.table_name, pfkey.column_names);
    IF ridmatch.is_physical THEN
      INSERT INTO _ermrest.known_key_annotations (key_rid, annotation_uri, annotation_value)
      VALUES (ridmatch.rid, pfkey.annotation_uri, COALESCE(pfkey.annotation_value, 'null'::json));
    ELSIF NOT ridmatch.is_physical THEN
      INSERT INTO _ermrest.known_pseudo_key_annotations (key_rid, annotation_uri, annotation_value)
      VALUES (ridmatch.rid, pfkey.annotation_uri, COALESCE(pfkey.annotation_value, 'null'::json));
    ELSE
      RAISE EXCEPTION 'Could not match key annotation %', pfkey;
    END IF;
  END LOOP;
  DROP TABLE _ermrest.model_key_annotation;
END IF;
  
-- fkey-level
IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_keyref_acl') THEN
  FOR pfkey IN SELECT * FROM _ermrest.model_keyref_acl LOOP
      ridmatch := _ermrest.find_fkey_rid(pfkey.from_schema_name, pfkey.from_table_name, pfkey.from_column_names, pfkey.to_schema_name, pfkey.to_table_name, pfkey.to_column_names);
    IF ridmatch.is_physical THEN
      INSERT INTO _ermrest.known_fkey_acls (fkey_rid, acl, members) VALUES (ridmatch.rid, pfkey.acl, pfkey.members);
    ELSIF NOT ridmatch.is_physical THEN
      INSERT INTO _ermrest.known_pseudo_fkey_acls (fkey_rid, acl, members) VALUES (ridmatch.rid, pfkey.acl, pfkey.members);
    ELSE
      RAISE EXCEPTION 'Could not match fkey ACL %', pfkey;
    END IF;
  END LOOP;
  DROP TABLE _ermrest.model_keyref_acl;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_keyref_dynacl') THEN
  FOR pfkey IN SELECT * FROM _ermrest.model_keyref_dynacl LOOP
    ridmatch := _ermrest.find_fkey_rid(pfkey.from_schema_name, pfkey.from_table_name, pfkey.from_column_names, pfkey.to_schema_name, pfkey.to_table_name, pfkey.to_column_names);
    IF ridmatch.is_physical THEN
      INSERT INTO _ermrest.known_fkey_dynacls (fkey_rid, binding_name, binding)
      VALUES (ridmatch.rid, pfkey.binding_name, pfkey.binding);
    ELSIF NOT ridmatch.is_physical THEN
      INSERT INTO _ermrest.known_pseudo_fkey_dynacls (fkey_rid, binding_name, binding)
      VALUES (ridmatch.rid, pfkey.binding_name, pfkey.binding);
    ELSE
      RAISE EXCEPTION 'Could not match fkey ACL binding %', pfkey;
    END IF;
  END LOOP;
  DROP TABLE _ermrest.model_keyref_dynacl;
END IF;

IF (SELECT True FROM information_schema.tables WHERE table_schema = '_ermrest' AND table_name = 'model_keyref_annotation') THEN
  FOR pfkey IN SELECT * FROM _ermrest.model_keyref_annotation LOOP
    ridmatch := _ermrest.find_fkey_rid(pfkey.from_schema_name, pfkey.from_table_name, pfkey.from_column_names, pfkey.to_schema_name, pfkey.to_table_name, pfkey.to_column_names);

    IF ridmatch.is_physical THEN
      INSERT INTO _ermrest.known_fkey_annotations (fkey_rid, annotation_uri, annotation_value)
      VALUES (ridmatch.rid, pfkey.annotation_uri, COALESCE(pfkey.annotation_value, 'null'::json));
    ELSIF NOT ridmatch.is_physical THEN
      INSERT INTO _ermrest.known_pseudo_fkey_annotations (fkey_rid, annotation_uri, annotation_value)
      VALUES (ridmatch.rid, pfkey.annotation_uri, COALESCE(pfkey.annotation_value, 'null'::json));
    ELSE
      RAISE EXCEPTION 'Could not match fkey annotation %', pfkey;
    END IF;
  END LOOP;
  DROP TABLE _ermrest.model_keyref_annotation;
END IF;

RAISE NOTICE 'Completed translating any legacy schema to current ERMrest schema.';

END upgrade_schema;
$upgrade$ LANGUAGE plpgsql;

