# 
# Copyright 2013-2017 University of Southern California
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
A database introspection layer.

At present, the capabilities of this module are limited to introspection of an 
existing database model. This module does not attempt to capture all of the 
details that could be found in an entity-relationship model or in the standard 
information_schema of a relational database. It represents the model as 
needed by other modules of the ermrest project.
"""

import web

from .. import exception
from ..util import table_exists, view_exists, column_exists
from .misc import frozendict, annotatable_classes, hasacls_classes, hasdynacls_classes, AclBinding
from .schema import Model, Schema
from .type import TypesEngine
from .column import Column
from .table import Table
from .key import Unique, ForeignKey, KeyReference, PseudoUnique, PseudoKeyReference

def current_model_version(cur):
    cur.execute("""
SELECT COALESCE((SELECT mlm.ts FROM _ermrest.model_last_modified mlm ORDER BY mlm.ts DESC LIMIT 1), now());
""")
    return cur.next()[0]

def introspect(cur, config=None):
    """Introspects a Catalog (i.e., a database).
    
    This function (currently) does not attempt to catch any database 
    (or other) exceptions.
    
    The 'conn' parameter must be an open connection to a database.
    
    Returns the introspected Model instance.
    """
    # Dicts to re-use singleton objects
    schemas  = dict()
    typesengine = TypesEngine(config)
    tables   = dict()
    columns  = dict()
    pkeys    = dict()
    fkeys    = dict()
    fkeyrefs  = dict()
    pfkeyrefs = dict()

    version = current_model_version(cur)
    cur.execute("""
SELECT
  COALESCE((SELECT jsonb_object_agg(a.annotation_uri, a.annotation_value) FROM _ermrest.known_catalog_annotations a), '{}'::jsonb),
  COALESCE((SELECT jsonb_object_agg(a.acl, a.members) FROM _ermrest.known_catalog_acls a), '{}'::jsonb)
;
""")
    annotations, acls = cur.next()
    model = Model(version, annotations, acls)

    #
    # Introspect schemas, tables, columns
    #
    
    # get schemas (including empty ones)
    cur.execute("""
SELECT
  s.oid,
  s.schema_name,
  s.comment,
  COALESCE(anno.annotations, '{}'::jsonb),
  COALESCE(acls.acls, '{}'::jsonb)
FROM _ermrest.known_schemas s
LEFT OUTER JOIN (
  SELECT
    schema_oid AS oid,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_schema_annotations
  GROUP BY schema_oid
) anno ON (s.oid = anno.oid)
LEFT OUTER JOIN (
  SELECT
    schema_oid AS oid,
    jsonb_object_agg(acl, members) AS acls
  FROM _ermrest.known_schema_acls
  GROUP BY schema_oid
) acls ON (s.oid = acls.oid)
;
"""
    )
    for oid, schema_name, comment, annotations, acls in cur:
        schemas[oid] = Schema(model, schema_name, comment, annotations, acls, oid)

    # get possible column types (including unused ones)
    cur.execute("SELECT * FROM _ermrest.known_types ORDER BY array_element_type_oid NULLS FIRST, domain_element_type_oid NULLS FIRST;")
    for oid, schema_oid, type_name, array_element_type_oid, domain_element_type_oid, domain_notnull, domain_default, comment in cur:
        # TODO: track schema and comments?
        if domain_element_type_oid is not None:
            typesengine.add_domain_type(oid, type_name, domain_element_type_oid, domain_default, domain_notnull, comment)
        elif array_element_type_oid is not None:
            typesengine.add_array_type(oid, type_name, array_element_type_oid, comment)
        else:
            typesengine.add_base_type(oid, type_name, comment)

    # get tables, views, etc. (including empty zero-column ones)
    cur.execute("""
SELECT
  t.oid,
  t.schema_oid,
  t.table_name,
  t.table_kind,
  t."comment",
  COALESCE(anno.annotations, '{}'::jsonb),
  COALESCE(acls.acls, '{}'::jsonb),
  COALESCE(c.columns, ARRAY[]::jsonb[])
FROM _ermrest.known_tables t
LEFT OUTER JOIN (
  SELECT
    a.table_oid AS oid,
    jsonb_object_agg(a.annotation_uri, a.annotation_value) AS annotations
  FROM _ermrest.known_table_annotations a
  GROUP BY a.table_oid
) anno ON (t.oid = anno.oid)
LEFT OUTER JOIN (
  SELECT
    a.table_oid AS oid,
    jsonb_object_agg(a.acl, a.members) AS acls
  FROM _ermrest.known_table_acls a
  GROUP BY a.table_oid
) acls ON (t.oid = acls.oid)
LEFT OUTER JOIN (
  SELECT
    c.table_oid,
    array_agg(to_jsonb(c.*) ORDER BY column_num) AS columns
  FROM (
    SELECT
      c.*, 
      COALESCE(anno.annotations, '{}'::jsonb) AS annotations,
      COALESCE(acls.acls, '{}'::jsonb) AS acls
    FROM _ermrest.known_columns c
    LEFT OUTER JOIN (
      SELECT
        a.table_oid,
        a.column_num,
        jsonb_object_agg(a.annotation_uri, a.annotation_value) AS annotations
      FROM _ermrest.known_column_annotations a
      GROUP BY a.table_oid, a.column_num
    ) anno ON (c.table_oid = anno.table_oid AND c.column_num = anno.column_num)
    LEFT OUTER JOIN (
      SELECT
        a.table_oid,
        a.column_num,
        jsonb_object_agg(a.acl, a.members) AS acls
      FROM _ermrest.known_column_acls a
      GROUP BY a.table_oid, a.column_num
    ) acls ON (c.table_oid = acls.table_oid AND c.column_num = acls.column_num)
  ) c
  GROUP BY c.table_oid
) c ON (t.oid = c.table_oid)
;
""")
    for oid, schema_oid, table_name, table_kind, comment, annotations, acls, coldocs in cur:
        tcols = []
        for i in range(len(coldocs)):
            cdoc = coldocs[i]
            ctype = typesengine.lookup(int(cdoc['type_oid']), cdoc['column_default'], True) # to_json turns OID type into string...
            try:
                default = ctype.default_value(cdoc['column_default'])
            except ValueError:
                default = None
            cnum = cdoc['column_num']
            canno = cdoc['annotations']
            cacl = cdoc['acls']
            col = Column(cdoc['column_name'], i, ctype, default, not cdoc['not_null'], cdoc['comment'], cnum, canno, cacl)
            tcols.append(col)
            columns[(oid, cnum)] = col

        tables[oid] = Table(schemas[schema_oid], table_name, tcols, table_kind, comment, annotations, acls, oid=oid)

    # Introspect pseudo not-null constraints
    cur.execute("SELECT * FROM _ermrest.known_pseudo_notnulls")
    for table_oid, column_num in cur:
        columns[(table_oid, column_num)].nullok = False

    #
    # Introspect uniques / primary key references, aggregated by constraint
    #
    def _introspect_pkey(table_oid, pk_column_nums, pk_comment, pk_factory):
        try:
            pk_cols = [
                columns[(table_oid, pk_column_num)]
                for pk_column_num in pk_column_nums
            ]
        except KeyError:
            return

        pk_colset = frozenset(pk_cols)

        # each constraint implies a pkey but might be duplicate
        pk = pk_factory(pk_colset)
        if pk_colset not in pkeys:
            pkeys[pk_colset] = pk
        else:
            pkeys[pk_colset].constraints.add(pk)
            if pk_comment:
                # save at least one comment in case multiple constraints have same key columns
                pkeys[pk_colset].comment = pk_comment

    cur.execute("""
SELECT
  k.oid,
  k.schema_oid,
  k.constraint_name,
  k.table_oid,
  k.column_nums,
  k."comment",
  COALESCE(anno.annotations, '{}'::jsonb)
FROM _ermrest.known_keys k
LEFT OUTER JOIN (
  SELECT
    key_oid AS oid,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_key_annotations
  GROUP BY key_oid
) anno ON (k.oid = anno.oid)
;
""")
    for oid, schema_oid, constraint_name, table_oid, column_nums, comment, annotations in cur:
        name_pair = (schemas[schema_oid].name, constraint_name)
        _introspect_pkey(
            table_oid, column_nums, comment,
            lambda pk_colset: Unique(pk_colset, name_pair, comment, annotations, oid)
        )

    cur.execute("""
SELECT
  k.id,
  k.constraint_name,
  k.table_oid,
  k.column_nums,
  k."comment",
  COALESCE(anno.annotations, '{}'::jsonb)
FROM _ermrest.known_pseudo_keys k
LEFT OUTER JOIN (
  SELECT
    pkey_id AS id,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_pseudo_key_annotations
  GROUP BY pkey_id
) anno ON (k.id = anno.id)
;
""")
    for pk_id, constraint_name, table_oid, column_nums, comment, annotations in cur:
        name_pair = ("", (constraint_name if constraint_name is not None else pk_id))
        _introspect_pkey(
            table_oid, column_nums, comment,
            lambda pk_colset: PseudoUnique(pk_colset, pk_id, name_pair, comment, annotations)
        )

    #
    # Introspect foreign keys references, aggregated by reference constraint
    #
    def _introspect_fkr(
            fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, fk_comment,
            fkr_factory
    ):
        try:
            fk_cols = [ columns[(fk_table_oid, fk_column_nums[i])] for i in range(len(fk_column_nums)) ]
            pk_cols = [ columns[(pk_table_oid, pk_column_nums[i])] for i in range(len(pk_column_nums)) ]
        except KeyError:
            return

        fk_colset = frozenset(fk_cols)
        pk_colset = frozenset(pk_cols)
        fk_ref_map = frozendict(dict([ (fk_cols[i], pk_cols[i]) for i in range(len(fk_cols)) ]))

        # each reference constraint implies a foreign key but might be duplicate
        if fk_colset not in fkeys:
            fkeys[fk_colset] = ForeignKey(fk_colset)

        fk = fkeys[fk_colset]
        pk = pkeys[pk_colset]

        # each reference constraint implies a foreign key reference but might be duplicate
        fkr = fkr_factory(fk, pk, fk_ref_map)
        if fk_ref_map not in fk.references:
            fk.references[fk_ref_map] = fkr
        else:
            fk.references[fk_ref_map].constraints.add(fkr)
            if fk_comment:
                # save at least one comment in case multiple csontraints have same key mapping
                fk.references[fk_ref_map].comment = fk_comment

        return fkr

    cur.execute("""
SELECT
  fk.oid,
  fk.schema_oid,
  fk.constraint_name,
  fk.fk_table_oid,
  fk.fk_column_nums,
  fk.pk_table_oid,
  fk.pk_column_nums,
  fk.delete_rule,
  fk.update_rule,
  fk."comment",
  COALESCE(anno.annotations, '{}'::jsonb),
  COALESCE(acl.acls, '{}'::jsonb)
FROM _ermrest.known_fkeys fk
LEFT OUTER JOIN (
  SELECT
    fkey_oid AS oid,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_fkey_annotations
  GROUP BY fkey_oid
) anno ON (fk.oid = anno.oid)
LEFT OUTER JOIN (
  SELECT
    fkey_oid AS oid,
    jsonb_object_agg(acl, members) AS acls
  FROM _ermrest.known_fkey_acls
  GROUP BY fkey_oid
) acl ON (fk.oid = acl.oid);
""")
    for oid, schema_oid, constraint_name, \
        fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, delete_rule, update_rule, comment, \
        annotations, acls in cur:
        name_pair = (schemas[schema_oid].name, constraint_name)
        fkeyrefs[oid] = _introspect_fkr(
            fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, comment,
            lambda fk, pk, fk_ref_map: KeyReference(fk, pk, fk_ref_map, delete_rule, update_rule, name_pair, annotations, comment, acls, oid=oid)
        )

    cur.execute("""
SELECT
  fk.id,
  fk.constraint_name,
  fk.fk_table_oid,
  fk.fk_column_nums,
  fk.pk_table_oid,
  fk.pk_column_nums,
  fk."comment",
  COALESCE(anno.annotations, '{}'::jsonb),
  COALESCE(acl.acls, '{}'::jsonb)
FROM _ermrest.known_pseudo_fkeys fk
LEFT OUTER JOIN (
  SELECT
    pfkey_id AS id,
    jsonb_object_agg(annotation_uri, annotation_value) AS annotations
  FROM _ermrest.known_pseudo_fkey_annotations
  GROUP BY pfkey_id
) anno ON (fk.id = anno.id)
LEFT OUTER JOIN (
  SELECT
    pfkey_id AS id,
    jsonb_object_agg(acl, members) AS acls
  FROM _ermrest.known_pseudo_fkey_acls
  GROUP BY pfkey_id
) acl ON (fk.id = acl.id)
;
""")
    for fk_id, constraint_name, \
        fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, comment, \
        annotations, acls in cur:
        name_pair = ("", (constraint_name if constraint_name is not None else fk_id))
        _introspect_fkr(
            fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, comment,
            lambda fk, pk, fk_ref_map: PseudoKeyReference(fk, pk, fk_ref_map, fk_id, name_pair, annotations, comment, acls)
        )

    # AclBinding constructor needs whole model to validate binding projections...
    cur.execute("""
SELECT
  a.table_oid AS oid,
  jsonb_object_agg(a.binding_name, a.binding) AS dynacls
FROM _ermrest.known_table_dynacls a
GROUP BY a.table_oid;
""")
    for oid, dynacls in cur:
        table = tables[oid]
        table.dynacls.update({
            binding_name: AclBinding(model, table, binding_name, binding_doc) if binding_doc else binding_doc
            for binding_name, binding_doc in dynacls.items()
        })

    cur.execute("""
SELECT
  a.table_oid,
  a.column_num,
  jsonb_object_agg(a.binding_name, a.binding) AS dynacls
FROM _ermrest.known_column_dynacls a
GROUP BY a.table_oid, a.column_num;
""")
    for table_oid, column_num, dynacls in cur:
        column = columns[(table_oid, column_num)]
        column.dynacls.update({
            binding_name: AclBinding(model, column, binding_name, binding_doc) if binding_doc else binding_doc
            for binding_name, binding_doc in dynacls.items()
        })

    cur.execute("""
SELECT
  fkey_oid AS oid,
  jsonb_object_agg(binding_name, binding) AS dynacls
FROM _ermrest.known_fkey_dynacls
GROUP BY fkey_oid;
""")
    for oid, dynacls in cur:
        fkr = fkeyrefs[oid]
        fkr.dynacls.update({
            binding_name: AclBinding(model, fkr, binding_name, binding_doc) if binding_doc else binding_doc
            for binding_name, binding_doc in dynacls.items()
        })

    cur.execute("""
SELECT
  pfkey_id AS id,
  jsonb_object_agg(binding_name, binding) AS dynacls
FROM _ermrest.known_pseudo_fkey_dynacls
GROUP BY pfkey_id;
""")
    for id, dynacls in cur:
        fkr = pfkeyrefs[id]
        fkr.dynacls.update({
            binding_name: AclBinding(model, fkr, binding_name, binding_doc) if binding_doc else binding_doc
            for binding_name, binding_doc in dynacls.items()
        })

    # save our private schema in case we want to unhide it later...
    model.ermrest_schema = model.schemas['_ermrest']
    del model.schemas['_ermrest']

    model.check_primary_keys(web.ctx.ermrest_config.get('require_primary_keys', True))

    return model

