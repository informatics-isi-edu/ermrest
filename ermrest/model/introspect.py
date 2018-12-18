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
from ..util import table_exists, view_exists, column_exists, sql_literal, sql_identifier
from .misc import frozendict, annotatable_classes, hasacls_classes, hasdynacls_classes, AclBinding, current_model_snaptime
from .schema import Model, Schema
from .type import TypesEngine
from .column import Column
from .table import Table
from .key import Unique, ForeignKey, KeyReference, PseudoUnique, PseudoKeyReference

def introspect(cur, config=None, snapwhen=None, amendver=None):
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

    if snapwhen is None:
        snapwhen = current_model_snaptime(cur)
        assert amendver is None
    else:
        assert amendver is not None

    cur.execute("SELECT * FROM _ermrest.known_catalog_denorm(%s);" % sql_literal(snapwhen))
    ignore_rid, annotations, acls = cur.next()
    model = Model(snapwhen, amendver, annotations, acls)

    #
    # Introspect schemas, tables, columns
    #
    
    # get schemas (including empty ones)
    cur.execute("SELECT * FROM _ermrest.known_schemas_denorm(%s)" % sql_literal(snapwhen))
    for rid, schema_name, comment, annotations, acls in cur:
        schemas[rid] = Schema(model, schema_name, comment, annotations, acls, rid)

    # get possible column types (including unused ones)
    cur.execute("""
SELECT * FROM _ermrest.known_types(%s)
ORDER BY array_element_type_rid NULLS FIRST, domain_element_type_rid NULLS FIRST;
""" % sql_literal(snapwhen))
    for rid, schema_rid, type_name, array_element_type_rid, domain_element_type_rid, domain_notnull, domain_default, comment in cur:
        # TODO: track schema and comments?
        if domain_element_type_rid is not None:
            typesengine.add_domain_type(rid, type_name, domain_element_type_rid, domain_default, domain_notnull, comment)
        elif array_element_type_rid is not None:
            typesengine.add_array_type(rid, type_name, array_element_type_rid, comment)
        else:
            typesengine.add_base_type(rid, type_name, comment)

    # get tables, views, etc. (including empty zero-column ones)
    cur.execute("SELECT * FROM _ermrest.known_tables_denorm(%s)" % sql_literal(snapwhen))
    for rid, schema_rid, table_name, table_kind, comment, annotations, acls, coldocs in cur:
        tcols = []
        for i in range(len(coldocs)):
            cdoc = coldocs[i]
            cname = cdoc['column_name']
            try:
                ctype = typesengine.lookup(cdoc['type_rid'], cdoc['column_default'], True)
            except ValueError:
                raise ValueError('Disallowed type "%s" requested for column "%s"."%s"."%s"' % (
                    typesengine.disallowed_by_rid[cdoc['type_rid']],
                    schemas[schema_rid].name,
                    table_name,
                    cname,
                ))
            try:
                default = ctype.default_value(cdoc['column_default'])
            except ValueError:
                default = None
            try:
                col = Column.fromjson_single(
                    {
                        'name': cdoc['column_name'],
                        'comment': cdoc['comment'],
                        'annotations': cdoc['annotations'],
                        'acls': cdoc['acls'],
                        # dynacls are handled later during introspection
                        'nullok': not cdoc['not_null'],
                        'default': default,
                        'type': ctype
                    },
                    i,
                    config
                )
            except Exception as te:
                raise ValueError('Introspection of column "%s"."%s"."%s" failed.\n%s' % (
                    schemas[schema_rid].name, table_name, cname, te
                ))
            col.rid = cdoc['RID']
            col.column_num = cdoc['column_num']
            tcols.append(col)
            columns[col.rid] = col

        tables[rid] = Table(schemas[schema_rid], table_name, tcols, table_kind, comment, annotations, acls, rid=rid)

    #
    # Introspect uniques / primary key references, aggregated by constraint
    #
    def _introspect_pkey(constraint_name, table_rid, pk_column_rids, pk_comment, pk_factory):
        if not pk_column_rids:
            raise ValueError('Key constraint %s lacks any columns.' % constraint_name)
        try:
            pk_cols = [
                columns[pk_column_rid]
                for pk_column_rid in pk_column_rids
            ]
        except KeyError:
            return

        pk_colset = frozenset(pk_cols)

        # each constraint implies a pkey but might be duplicate
        pk = pk_factory(pk_colset)
        if pk_colset in pkeys:
            raise ValueError('Duplicate constraint %s collides with %s.' % (
                constraint_name,
                pkeys[pk_colset].constraint_name,
            ))
        pkeys[pk_colset] = pk

    cur.execute("SELECT * FROM _ermrest.known_keys_denorm(%s);" % sql_literal(snapwhen))
    for rid, schema_rid, constraint_name, table_rid, column_rids, comment, annotations in cur:
        name_pair = (schemas[schema_rid].name, constraint_name)
        _introspect_pkey(
            constraint_name, 
            table_rid, column_rids, comment,
            lambda pk_colset: Unique(pk_colset, name_pair, comment, annotations, rid)
        )

    cur.execute("SELECT * FROM _ermrest.known_pseudo_keys_denorm(%s);" % sql_literal(snapwhen))
    for rid, constraint_name, table_rid, column_rids, comment, annotations in cur:
        name_pair = ("", (constraint_name if constraint_name is not None else rid))
        _introspect_pkey(
            constraint_name,
            table_rid, column_rids, comment,
            lambda pk_colset: PseudoUnique(pk_colset, rid, name_pair, comment, annotations)
        )

    #
    # Introspect foreign keys references, aggregated by reference constraint
    #
    def _introspect_fkr(
            constraint_name,
            fk_table_rid, pk_table_rid, fkc_pkc_rids, fk_comment,
            fkr_factory
    ):
        if not fkc_pkc_rids:
            raise ValueError('Foreign key constraint %s lacks any columns.' % constraint_name)

        try:
            fk_cols = [ columns[fkc_rid] for fkc_rid in fkc_pkc_rids ]
            pk_cols = [ columns[fkc_pkc_rids[c.rid]] for c in fk_cols ]
        except KeyError:
            return

        fk_colset = frozenset(fk_cols)
        pk_colset = frozenset(pk_cols)
        fk_ref_map = frozendict({
            fk_col: pk_col
            for fk_col, pk_col in zip(fk_cols, pk_cols)
        })

        # each reference constraint implies a foreign key but might be duplicate
        if fk_colset not in fkeys:
            fkeys[fk_colset] = ForeignKey(fk_colset)

        fk = fkeys[fk_colset]
        pk = pkeys[pk_colset]

        # each reference constraint implies a foreign key reference but might be duplicate
        fkr = fkr_factory(fk, pk, fk_ref_map)
        if fk_ref_map in fk.references:
            raise ValueError('Duplicate constraint %s collides with %s.' % (
                constraint_name,
                fk.references[fk_ref_map].constraint_name
            ))
        fk.references[fk_ref_map] = fkr
        return fkr

    cur.execute("SELECT * FROM _ermrest.known_fkeys_denorm(%s);" % sql_literal(snapwhen))
    for rid, schema_rid, constraint_name, fk_table_rid, pk_table_rid, fkc_pkc_rids, \
        delete_rule, update_rule, comment, annotations, acls in cur:
        name_pair = (schemas[schema_rid].name, constraint_name)
        fkeyrefs[rid] = _introspect_fkr(
            constraint_name,
            fk_table_rid, pk_table_rid, fkc_pkc_rids, comment,
            lambda fk, pk, fk_ref_map: KeyReference(fk, pk, fk_ref_map, delete_rule, update_rule, name_pair, annotations, comment, acls, rid=rid)
        )

    cur.execute("SELECT * FROM _ermrest.known_pseudo_fkeys_denorm(%s);" % sql_literal(snapwhen))
    for rid, constraint_name, fk_table_rid, pk_table_rid, fkc_pkc_rids, \
        comment, annotations, acls in cur:
        name_pair = ("", (constraint_name if constraint_name is not None else rid))
        pfkeyrefs[rid] = _introspect_fkr(
            constraint_name,
            fk_table_rid, pk_table_rid, fkc_pkc_rids, comment,
            lambda fk, pk, fk_ref_map: PseudoKeyReference(fk, pk, fk_ref_map, rid, name_pair, annotations, comment, acls)
        )

    # AclBinding constructor needs whole model to validate binding projections...
    for resourceset, sqlfunc, restype in [
            (tables, 'known_table_dynacls', 'table'),
            (columns, 'known_column_dynacls', 'column'),
            (fkeyrefs, 'known_fkey_dynacls', 'fkey'),
            (pfkeyrefs, 'known_pseudo_fkey_dynacls', 'pseudo_fkey'),
    ]:
        cur.execute("""
SELECT 
  "RID",
  acl_bindings
FROM _ermrest.%(sqlfunc)s(%(when)s) a;
""" % {
    'sqlfunc': sqlfunc,
    'when': sql_literal(snapwhen),
})
        rows = list(cur) # pre-fetch the result in case we use cursor in constructor code below...
        for rid, dynacls in rows:
            resource = resourceset[rid]
            new_dynacls = {}
            for binding_name, binding_doc in dynacls.items():
                new_dynacls[binding_name] = AclBinding(model, resource, binding_name, binding_doc) if binding_doc else binding_doc
            resource.dynacls.update(new_dynacls)

    # save our private schema in case we want to unhide it later...
    model.ermrest_schema = model.schemas['_ermrest']
    model.pg_catalog_schema = model.schemas['pg_catalog']
    del model.schemas['_ermrest']
    del model.schemas['pg_catalog']

    try:
        model.check_primary_keys(web.ctx.ermrest_config.get('require_primary_keys', True))
    except exception.ConflictModel as te:
        raise exception.rest.RuntimeError(te)

    return model

