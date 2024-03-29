
# 
# Copyright 2013-2023 University of Southern California
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

from webauthn2.util import deriva_ctx, deriva_debug

from .. import exception
from ..util import table_exists, view_exists, column_exists, sql_literal, sql_identifier, OrderedFrozenSet
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
    annotations, acls = cur.fetchone()
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

        pk_colset = OrderedFrozenSet(pk_cols)

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
    pruned_any = False
    for rid, constraint_name, table_rid, column_rids, comment, annotations in cur:
        name_pair = ("", (constraint_name if constraint_name is not None else rid))
        try:
            _introspect_pkey(
                constraint_name,
                table_rid, column_rids, comment,
                lambda pk_colset: PseudoUnique(pk_colset, rid, name_pair, comment, annotations)
            )
        except ValueError as te:
            msg = 'Pruning invalid pseudo key %s on %s due to error: %s. Was this invalidated by a previous model change?' % (
                constraint_name,
                tables[table_rid],
                te
            )
            try:
                deriva_ctx.ermrest_request_trace(msg)
            except:
                deriva_debug(msg)
            cur.execute("""
DELETE FROM _ermrest.known_pseudo_keys
WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % {
    'rid': sql_literal(rid),
})
            cur.fetchall()
            pruned_any = True

    #
    # Introspect foreign keys references, aggregated by reference constraint
    #
    def _introspect_fkr(
            constraint_name,
            fk_table_rid, fk_column_rids, pk_table_rid, pk_column_rids, fk_comment,
            fkr_factory
    ):
        if not fk_column_rids or not pk_column_rids:
            raise ValueError('Foreign key constraint %s lacks any columns.' % constraint_name)

        try:
            fk_cols = [ columns[fk_column_rids[i]] for i in range(len(fk_column_rids)) ]
            pk_cols = [ columns[pk_column_rids[i]] for i in range(len(pk_column_rids)) ]
        except KeyError:
            return

        if len(fk_column_rids) != len(pk_column_rids):
            raise ValueError('Foreign key constraint %s has mismatched column list lengths.' % constraint_name)

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
    for rid, schema_rid, constraint_name, fk_table_rid, fk_col_rids, pk_table_rid, pk_col_rids, \
        delete_rule, update_rule, comment, annotations, acls in cur:
        name_pair = (schemas[schema_rid].name, constraint_name)
        fkeyrefs[rid] = _introspect_fkr(
            constraint_name,
            fk_table_rid, fk_col_rids, pk_table_rid, pk_col_rids, comment,
            lambda fk, pk, fk_ref_map: KeyReference(fk, pk, fk_ref_map, delete_rule, update_rule, name_pair, annotations, comment, acls, rid=rid)
        )

    cur.execute("SELECT * FROM _ermrest.known_pseudo_fkeys_denorm(%s);" % sql_literal(snapwhen))
    for rid, constraint_name, fk_table_rid, fk_col_rids, pk_table_rid, pk_col_rids, \
        comment, annotations, acls in cur:
        name_pair = ("", (constraint_name if constraint_name is not None else rid))
        try:
            pfkeyrefs[rid] = _introspect_fkr(
                constraint_name,
                fk_table_rid, fk_col_rids, pk_table_rid, pk_col_rids, comment,
                lambda fk, pk, fk_ref_map: PseudoKeyReference(fk, pk, fk_ref_map, rid, name_pair, annotations, comment, acls)
            )
        except ValueError as te:
            msg = 'Pruning invalid pseudo foreign key %s on %s due to error: %s. Was this invalidated by a previous model change?' % (
                constraint_name,
                tables[fk_table_rid],
                te
            )
            try:
                deriva_ctx.ermrest_request_trace(msg)
            except:
                deriva_debug(msg)
            cur.execute("""
DELETE FROM _ermrest.known_pseudo_fkeys
WHERE "RID" = %(rid)s;
SELECT _ermrest.model_version_bump();
""" % {
    'rid': sql_literal(rid),
})
            cur.fetchall()
            pruned_any = True

    # AclBinding constructor needs whole model to validate binding projections...
    for resourceset, sqlfunc, grpcol in [
            (tables, 'known_table_dynacls', 'table_rid'),
            (columns, 'known_column_dynacls', 'column_rid'),
            (fkeyrefs, 'known_fkey_dynacls', 'fkey_rid'),
            (pfkeyrefs, 'known_pseudo_fkey_dynacls', 'fkey_rid'),
    ]:
        cur.execute("""
SELECT 
  %(grpcol)s,
  jsonb_object_agg(a.binding_name, a.binding) AS dynacls
FROM _ermrest.%(sqlfunc)s(%(when)s) a 
GROUP BY a.%(grpcol)s ;
""" % {
    'sqlfunc': sqlfunc,
    'grpcol': grpcol,
    'when': sql_literal(snapwhen),
})
        rows = list(cur) # pre-fetch the result in case we use cursor in constructor code below...
        for rid, dynacls in rows:
            resource = resourceset[rid]
            new_dynacls = {}
            for binding_name, binding_doc in dynacls.items():
                try:
                    new_dynacls[binding_name] = AclBinding(model, resource, binding_name, binding_doc) if binding_doc else binding_doc
                except (exception.ConflictModel, exception.BadData) as te:
                    msg = 'Pruning invalid dynamic ACL binding %s on %s due to error: %s.' % (
                        binding_name,
                        resource,
                        te
                    )
                    try:
                        deriva_ctx.ermrest_request_trace(msg)
                    except:
                        deriva_debug(msg)
                    cur.execute("""
DELETE FROM _ermrest.%(binding_table)s
WHERE %(resource_col)s = %(resource_rid)s
  AND binding_name = %(binding_name)s;
SELECT _ermrest.model_version_bump();
""" % {
    'binding_table': sql_identifier(sqlfunc),
    'resource_col': sql_identifier(grpcol),
    'resource_rid': sql_literal(rid),
    'binding_name': sql_literal(binding_name),
})
                    cur.fetchall()
                    pruned_any = True
                except Exception as te:
                    # server is likely broken at this point! allow investigation, don't blindly prune on any unknown error...
                    deriva_debug('BUG: Got other exception while introspecting ACL binding %s on %s: %s (%s)' % (binding_name, resource, te, type(te)))
                    raise
            resource.dynacls.update(new_dynacls)

    if pruned_any:
        # this fires when we've done any of the pseudo constraint or acl binding DELETE cleanups above...
        cur.connection.commit()
        raise exception.rest.ServiceUnavailable('Model introspection failed due to a transient condition. Please try again')
    # save our private schema in case we want to unhide it later...
    model.ermrest_schema = model.schemas['_ermrest']
    model.pg_catalog_schema = model.schemas['pg_catalog']
    del model.schemas['_ermrest']
    del model.schemas['pg_catalog']

    try:
        model.check_primary_keys(deriva_ctx.ermrest_config.get('require_primary_keys', True), deriva_ctx.ermrest_config.get('warn_missing_system_columns', True))
    except exception.ConflictModel as te:
        raise exception.rest.RuntimeError(te)

    return model

