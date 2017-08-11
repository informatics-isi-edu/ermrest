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
from .misc import frozendict, annotatable_classes, hasacls_classes, hasdynacls_classes
from .schema import Model, Schema
from .type import build_type, text_type
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

    # Dicts for quick lookup
    schemas  = dict()
    types    = dict()
    tables   = dict()
    columns  = dict()
    pkeys    = dict()
    fkeys    = dict()
    fkeyrefs = dict()

    version = current_model_version(cur)
    
    model = Model(version)

    #
    # Introspect schemas, tables, columns
    #
    
    # get schemas (including empty ones)
    cur.execute("SELECT * FROM _ermrest.known_schemas;")
    for oid, schema_name, comment in cur:
        schemas[oid] = Schema(model, sname, scomment)

    # get possible column types (including unused ones)
    cur.execute("SELECT * FROM _ermrest.known_types ORDER BY array_element_type_oid NULLS FIRST, domain_element_type_oid NULLS FIRST;")
    for oid, schema_oid, type_name, array_element_type_oid, domain_element_type_oid, domain_notnull, domain_default, comment in cur:
        # TODO: track schema and comments?
        if domain_element_type_oid is not None:
            # TODO: track extra domain properties?
            types[oid] = DomainType(base_type=types[domain_element_type_oid], typename=type_name)
        elif array_element_type_oid is not None:
            types[oid] = ArrayType(base_type=types[array_element_type_oid])
        else:
            types[oid] = Type(typename=type_name)

    # get tables, views, etc. (including empty zero-column ones)
    cur.execute("""
SELECT t.*, c.columns
FROM _ermrest.known_tables t
LEFT OUTER JOIN (
SELECT
  table_oid,
  array_agg(to_jsonb(c.*) ORDER BY column_num) AS columns
FROM _ermrest.known_columns c
GROUP BY table_oid
) c ON (t.oid = c.table_oid)
;
""")
    for oid, schema_oid, table_name, table_kind, comment, coldocs in cur:
        tcols = []
        for i in range(len(coldocs)):
            cdoc = coldocs[i]
            ctype = types[cdoc['type_oid']]
            try:
                default = ctype.default_value(cdoc['column_default'])
            except ValueError:
                default = None
            col = Column(cdoc['column_name'].decode('utf8'), i, ctype, default, not cdoc['not_null'], cdoc['comment'])
            tcols.append(col)
            columns[(oid, cdoc['column_num'])] = col

        tables[oid] = Table(schemas[schema_oid], table_name, tcols, table_kind, comment)

    # Introspect psuedo not-null constraints
    cur.execute("SELECT * FROM _ermrest.known_psuedo_notnulls")
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

    cur.execute("SELECT * FROM _ermrest.known_keys")
    for oid, schema_oid, constraint_name, table_oid, column_nums, comment in cur:
        _introspect_pkey(
            table_oid, column_nums, comment,
            lambda pk_colset: Unique(pk_colset, (schemas[schema_oid].name, constraint_name), comment)
        )

    cur.execute("SELECT * FROM _ermrest.known_psuedo_keys")
    for pk_id, constraint_name, table_oid, column_nums, comment in cur:
        _introspect_pkey(
            table_oid, column_nums, comment,
            lambda pk_colset: PsuedoUnique(pk_colset, pk_id, ("", (constraint_name if constraint_name is not None else pk_id)), comment)
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

    cur.execute("SELECT * FROM _ermrest.known_fkeys")
    for oid, schema_oid, constraint_name, fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, delete_rule, update_rule, comment in cur:
        _introspect_fkr(
            fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, comment,
            lambda fk, pk, fk_ref_map: KeyReference(fk, pk, fk_ref_map, on_delete, on_update, (schemas[schema_oid].name, constraint_name), comment=comment)
        )

    cur.execute("SELECT * FROM _ermrest.known_pseudo_fkeys")
    for fk_id, constraint_name, fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, comment in cur:
        _introspect_fkr(
            fk_table_oid, fk_column_nums, pk_table_oid, pk_column_nums, comment,
            lambda fk, pk, fk_ref_map: PsuedoKeyReference(fk, pk, fk_ref_map, ("", (constraint_name if constraint_name is not None else fk_id)), comment=comment)
        )

    #
    # Introspect ERMrest model overlay annotations
    #
    for klass in annotatable_classes:
        if hasattr(klass, 'introspect_helper'):
            klass.introspect_helper(cur, model)

    # introspect ERMrest model ACLs
    for klass in hasacls_classes:
        if hasattr(klass, 'introspect_acl_helper'):
            klass.introspect_acl_helper(cur, model)

    # introspect ERMrest model ACLs
    for klass in hasdynacls_classes:
        if hasattr(klass, 'introspect_dynacl_helper'):
            klass.introspect_dynacl_helper(cur, model)

    # save our private schema in case we want to unhide it later...
    model.ermrest_schema = model.schemas['_ermrest']
    del model.schemas['_ermrest']

    model.check_primary_keys(web.ctx.ermrest_config.get('require_primary_keys', True))

    return model

