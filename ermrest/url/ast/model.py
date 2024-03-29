
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

"""ERMREST URL abstract syntax tree (AST) for model introspection resources.

"""

import json
import flask
from webauthn2.util import deriva_ctx, deriva_debug

from ... import exception
from ... import model
from .api import Api
from ...util import OrderedFrozenSet

def _post_commit(handler, resource, content_type='text/plain', transform=lambda v: v):
    handler.emit_headers()
    response = transform(resource)
    if (response is None or response == '') and deriva_ctx.deriva_response.status_code == 200:
        deriva_ctx.deriva_response.status_code = 204
        return deriva_ctx.deriva_response
    deriva_ctx.deriva_response.content_type = content_type
    deriva_ctx.deriva_response.response = [ response, ]
    return deriva_ctx.deriva_response

def _post_commit_json(handler, resource):
    def prejson(v):
        if hasattr(v, 'prejson'):
            return v.prejson()
        else:
            return v
    def to_json(resource):
        if isinstance(resource, list):
            resource = [ prejson(v) for v in resource ]
        else:
            resource = prejson(resource)
        return json.dumps(resource, indent=None, separators=(',', ':')) + '\n'
    return _post_commit(handler, resource, 'application/json', to_json)

def _GET(handler, thunk, _post_commit):
    def body(conn, cur):
        handler.enforce_right('enumerate')
        handler.set_http_etag( deriva_ctx.ermrest_catalog_model.etag() )
        handler.http_check_preconditions()
        return thunk(conn, cur)
    return handler.perform(body, lambda resource: _post_commit(handler, resource))

def _MODIFY(handler, thunk, _post_commit):
    def body(conn, cur):
        if deriva_ctx.ermrest_history_snaptime is not None:
            raise exception.Forbidden('modification to catalog at previous revision')
        if deriva_ctx.ermrest_history_snaprange is not None:
            # should not be possible bug check anyway...
            raise NotImplementedError('modification on %s with snaprange' % handler)
        # we need a private (uncached) copy of model because we mutate it optimistically
        # and this could corrupt a cached copy
        deriva_ctx.ermrest_catalog_model = handler.catalog.manager.get_model(cur, private=True)
        handler.set_http_etag( deriva_ctx.ermrest_catalog_model.etag() )
        handler.http_check_preconditions(method='PUT')
        result = thunk(conn, cur)
        handler.set_http_etag( deriva_ctx.ermrest_catalog_model.etag(cur) )
        return result
    return handler.perform(body, lambda resource: _post_commit(handler, resource))

def _MODIFY_with_json_input(handler, thunk, _post_commit):
    try:
        doc = json.loads(flask.request.stream.read().decode())
    except:
        raise exception.rest.BadRequest('Could not deserialize JSON input.')
    return _MODIFY(handler, lambda conn, cur: thunk(conn, cur, doc), _post_commit)

class Schemas (Api):
    """A schema set."""
    def __init__(self, catalog):
        Api.__init__(self, catalog)

    def GET_body(self, conn, cur):
        return deriva_ctx.ermrest_catalog_model
        
    def GET(self, uri):
        def _post_commit(handler, model):
            doc = model.prejson()
            if self.catalog.manager.alias_target is not None:
                doc['alias_target'] = self.catalog.manager.alias_target
            return _post_commit_json(handler, doc)
        return _GET(self, self.GET_body, _post_commit)

    def POST_body(self, conn, cur, doc):
        """Create schemas and/or tables."""
        # don't collide with model module...
        modelobj = deriva_ctx.ermrest_catalog_model

        deferred_fkeys = []
        
        def extract_fkeys(sname, tname, tabledoc):
            """Remove fkey sub-documents and defer to our own storage."""
            deferred_fkeys.append(
                (sname, tname, tabledoc.pop('foreign_keys', []))
            )

        def run_schema_pass1(sname, sdoc):
            """Create one schema and its tables while deferring fkeys."""
            if sname is None:
                # support use case w/o schema key from parent document
                sname = sdoc.get('schema_name')

            sname2 = sdoc.get('schema_name', sname)
            if sname != sname2:
                raise exception.BadData('Schema key %s and schema_name %s do not match.' % (sname, sname2))
            
            # support elision of schema_name when parent schema key is already specified
            sdoc['schema_name'] = sname
                
            for tname, tdoc in sdoc.get('tables', {}).items():
                extract_fkeys(sname, tname, tdoc)
            return model.Schema.create_fromjson(conn, cur, modelobj, sdoc, deriva_ctx.ermrest_config)

        def run_table_pass1(tdoc):
            """Create one table while deferring fkeys."""
            try:
                sname = tdoc['schema_name']
                tname = tdoc['table_name']
            except KeyError as e:
                raise exception.BadData('Each table document must have a %s field.' % e)
            extract_fkeys(sname, tname, tdoc)
            schema = modelobj.schemas[sname]
            return model.Table.create_fromjson(conn, cur, schema, tdoc, deriva_ctx.ermrest_config)

        def run_key(kdoc):
            """Create one key."""
            try:
                sname = kdoc['unique_columns'][0]['schema_name']
                tname = kdoc['unique_columns'][0]['table_name']
            except KeyError as e:
                raise exception.BadData('Each key document must have a %s field.' % e)
            except IndexError:
                raise exception.BadData('Each key document must have at least one unique_columns entry.')
            return modelobj.schemas[sname].tables[tname].add_unique(conn, cur, kdoc)
        
        def defer_fkey(fkdoc):
            """Defer fkey."""
            try:
                sname = fkdoc['foreign_key_columns'][0]['schema_name']
                tname = fkdoc['foreign_key_columns'][0]['table_name']
            except KeyError as e:
                raise exception.BadData('Each foreign key document must have a %s field.' % e)
            except IndexError:
                raise exception.BadData('Each foreign key document must have at least one foreign_key_columns entry.')
            deferred_fkeys.append(
                (sname, tname, [fkdoc])
            )

        def run_deferred_fkeys():
            """Create all deferred fkeys assuming tables now exist."""
            for sname, tname, fkeydocs in deferred_fkeys:
                for fkeydoc in fkeydocs:
                    for fkr in modelobj.schemas[sname].tables[tname].add_fkeyref(conn, cur, fkeydoc):
                        # need to drain this generating function
                        pass
        
        if isinstance(doc, dict):
            # top-level model document has schemas w/ nested tables
            schemasdoc = doc.get('schemas')
            if not isinstance(schemasdoc, dict):
                raise exception.BadData('Model document requires a "schemas" hash map.')

            schemas = []
            for sname, sdoc in schemasdoc.items():
                schemas.append(run_schema_pass1(sname, sdoc))

            run_deferred_fkeys()
            return dict(schemas={ s.name: s.prejson() for s in schemas })
        elif isinstance(doc, list):
            # polymorphic batch may have schemas and/or tables mixed together
            resources = []
            for rdoc in doc:
                if isinstance(rdoc, dict):
                    if 'table_name' in rdoc:
                        resources.append(run_table_pass1(rdoc))
                    elif 'foreign_key_columns' in rdoc:
                        defer_fkey(rdoc)
                    elif 'schema_name' in rdoc:
                        resources.append(run_schema_pass1(None, rdoc))
                    else:
                        exception.BadData('Each batch item must be an object/dictionary.')
                else:
                    raise exception.BadData('Each batch item must be a schema, table, or foreign-key document.')

            run_deferred_fkeys()
            return resources
        else:
            raise exception.BadData('JSON input is neither a schema set or a batch list of schemas and tables.')
    
    def POST(self, uri):
        """Create schemas and/or tables from JSON

           Input forms:
           1. A model like { "schemas": { sname: schemadoc }, ... }
           2. A batch list like [ item... ]  where item can be schemadoc or tabledoc

           The schemadoc inputs can have nested tabledocs which are also created.
        """
        def post_commit(self, resource):
            deriva_ctx.deriva_response.status_code = 201
            return _post_commit_json(self, resource)
        return _MODIFY_with_json_input(self, self.POST_body, post_commit)
    
class Schema (Api):
    """A specific schema by name."""
    def __init__(self, catalog, name):
        Api.__init__(self, catalog)
        self.schemas = Schemas(catalog)
        self.name = name

    def acls(self):
        """The ACL set for this schema."""
        return SchemaAcl(self)

    def comment(self):
        """The comment for this schema."""
        return SchemaComment(self)

    def annotations(self):
        return SchemaAnnotations(self)

    def tables(self):
        """The table set for this schema."""
        return Tables(self)

    def table(self, name):
        """A specific table for this schema."""
        return Table(self, name)

    def GET_body(self, conn, cur, final=False):
        try:
            return deriva_ctx.ermrest_catalog_model.schemas.get_enumerable(self.name)
        except exception.ConflictModel as e:
            if final:
                raise exception.NotFound(u'schema %s' % self.name)
            raise

    def GET(self, uri):
        return _GET(self, lambda conn, cur: self.GET_body(conn, cur, True), _post_commit_json)

    def POST_body(self, conn, cur):
        return deriva_ctx.ermrest_catalog_model.create_schema(conn, cur, self.name.one_str())

    def POST(self, uri):
        def post_commit(self, ignored):
            deriva_ctx.deriva_response.status_code = 201
            return _post_commit(self, '')
        return _MODIFY(self, self.POST_body, post_commit)

    def DELETE_body(self, conn, cur):
        schema = self.GET_body(conn, cur, True)
        deriva_ctx.ermrest_catalog_model.delete_schema(conn, cur, schema.name)
        return ''
            
    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

    def PUT_body(self, conn, cur, schemadoc):
        schemadoc['schema_name'] = schemadoc.get('schema_name', self.name.one_str())
        try:
            # handle alteration of existing schema
            schema = deriva_ctx.ermrest_catalog_model.schemas.get_enumerable(self.name)
            return schema.update(conn, cur, schemadoc, deriva_ctx.ermrest_config)
        except exception.ConflictModel as e:
            # handle creation of new schema, same as POST /schema/
            schemas = Schemas(self.catalog)
            return schemas.POST_body(conn, cur, schemadoc)

    def PUT(self, uri):
        def post_commit(self, table):
            return _post_commit_json(self, table)
        return _MODIFY_with_json_input(self, self.PUT_body, post_commit)

class Tables (Api):
    """A table set."""
    def __init__(self, schema):
        Api.__init__(self, schema.catalog)
        self.schema = schema

    def table(self, name):
        """A specific table for this schema."""
        return self.schema.table(name)

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
    
    def GET_body(self, conn, cur):
        return [ t for t in self.schema.GET_body(conn, cur).tables.values() if t.has_right('enumerate') ]

    def POST_body(self, conn, cur, tabledoc):
        schema = self.schema.GET_body(conn, cur)
        return model.Table.create_fromjson(conn, cur, schema, tabledoc, deriva_ctx.ermrest_config)

    def POST(self, uri):
        def post_commit(self, table):
            deriva_ctx.deriva_response.status_code = 201
            return _post_commit_json(self, table)
        return _MODIFY_with_json_input(self, self.POST_body, post_commit)

class AclCommon (Api):
    def __init__(self, catalog, subject):
        Api.__init__(self, catalog)
        self.subject = subject
        self.kind = 'ACL'
        self.key_kind = 'ACL name'

    def GET_subject(self, conn, cur):
        return self.subject.GET_body(conn, cur)

    def GET_container(self, subject):
        raise NotImplementedError()

    def GET_element_key(self):
        raise NotImplementedError()

    def GET_body(self, conn, cur):
        subject = self.GET_subject(conn, cur)
        subject.enforce_right('owner')
        container = self.GET_container(subject)
        key = self.GET_element_key()
        if key is not None:
            return container[key]
        else:
            return container

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def DELETE_body(self, cur, subject, key=None):
        raise NotImplementedError()

    def PUT_body(self, cur, subject, key, element):
        raise NotImplementedError()

    def validate_element(self, element):
        raise NotImplementedError

    def SET_body(self, conn, cur, data):
        subject = self.GET_subject(conn, cur)
        subject.enforce_right('owner')
        container = self.GET_container(subject)
        key = self.GET_element_key()
        if key is None:
            if data is None:
                self.DELETE_body(cur, subject)
            elif type(data) is dict:
                for existing_key in list(container):
                    if existing_key not in data:
                        self.DELETE_body(cur, subject, existing_key)
                for data_key, data_element in data.items():
                    self.PUT_body(cur, subject, data_key, self.validate_element(data_element))
            else:
                raise exception.BadData(
                    '%(kind)s set document must be an object with each %(kind)s keyed by %(key_kind)s.' % dict(
                        kind=self.kind,
                        key_kind=self.key_kind
                    )
                )
            return self.GET_container(subject)
        else:
            if data is None:
                self.DELETE_body(cur, subject, key)
            else:
                self.PUT_body(cur, subject, key, self.validate_element(data))
                return self.GET_container(subject).get(key)

    def PUT(self, uri):
        return _MODIFY_with_json_input(self, self.SET_body, _post_commit_json)

    def DELETE(self, uri):
        def post_commit(self, ignore):
            return _post_commit(self, '')
        return _MODIFY(self, lambda conn, cur: self.SET_body(conn, cur, None), post_commit)

class Acl (AclCommon):
    """A specific object's ACLs."""
    def __init__(self, catalog, subject):
        AclCommon.__init__(self, catalog, subject)
        self.aclname = None

    def acl(self, aclname):
        self.aclname = aclname
        return self

    def GET_container(self, subject):
        return subject.acls

    def GET_element_key(self):
        return self.aclname

    def DELETE_body(self, cur, subject, key=None):
        subject.delete_acl(cur, key)

    def PUT_body(self, cur, subject, key, element):
        subject.set_acl(cur, key, element)

    def validate_element(self, element):
        if type(element) is not list:
            raise exception.BadData('ACL representation must be an array.')
        for member in element:
            if not isinstance(member, str):
                raise exception.BadData('ACL member representation must be a string literal.')
        return element

class CatalogAcl (Acl):
    """A specific catalog's ACLs."""
    def __init__(self, catalog):
        Acl.__init__(self, catalog, catalog)

class SchemaAcl (Acl):
    """A specific schema's ACLs."""
    def __init__(self, schema):
        Acl.__init__(self, schema.catalog, schema)

class TableAcl (Acl):
    """A specific table's ACLs."""
    def __init__(self, table):
        Acl.__init__(self, table.schema.catalog, table)

class ColumnAcl (Acl):
    """A specific column's ACLs."""
    def __init__(self, column):
        Acl.__init__(self, column.table.schema.catalog, column)

class ForeignkeyReferenceAcl (Acl):
    """A specific keyref's ACLs."""
    def __init__(self, fkey):
        Acl.__init__(self, fkey.catalog, fkey)

    def PUT_body(self, cur, subject, key, element):
        subject.set_acl(cur, key, element, anon_mutation_ok=True)

    def GET_subject(self, conn, cur):
        fkrs = self.subject.GET_body(conn, cur)
        if len(fkrs) != 1:
            raise NotImplementedError('ForeignkeyReferenceAcls on %d fkrs' % len(fkrs))
        return fkrs[0]

class Dynacl (AclCommon):
    def __init__(self, catalog, subject):
        AclCommon.__init__(self, catalog, subject)
        self.bindingname = None

    def dynacl(self, name):
        self.bindingname = name
        return self

    def GET_container(self, subject):
        return subject.dynacls

    def GET_element_key(self):
        return self.bindingname

    def DELETE_body(self, cur, subject, key=None):
        subject.delete_dynacl(cur, key)

    def PUT_body(self, cur, subject, key, element):
        subject.set_dynacl(cur, key, element)

    def validate_element(self, element):
        if type(element) is not dict and element is not False:
            raise exception.BadData('Dynamic ACL binding representation must be an object or literal false value.')
        return element

class TableDynacl (Dynacl):
    """A specific table's dynamic ACLs."""
    def __init__(self, table):
        Dynacl.__init__(self, table.schema.catalog, table)

class ColumnDynacl (Dynacl):
    """A specific column's dynamic ACLs."""
    def __init__(self, column):
        Dynacl.__init__(self, column.table.schema.catalog, column)

class ForeignkeyReferenceDynacl (Dynacl):
    """A specific keyref's dynamic ACLs."""
    def __init__(self, fkey):
        Dynacl.__init__(self, fkey.catalog, fkey)

    def GET_subject(self, conn, cur):
        fkrs = self.subject.GET_body(conn, cur)
        if len(fkrs) != 1:
            raise NotImplementedError('ForeignkeyReferenceDynacls on %d fkrs' % len(fkrs))
        return fkrs[0]

class Comment (Api):
    """A specific object's comment.

       This is a hack to reuse code for Table and Column comment handling.
    """
    def __init__(self, catalog, subject):
        Api.__init__(self, catalog)
        self.subject = subject

    def GET_subject(self, conn, cur):
        return self.subject.GET_body(conn, cur)

    def GET_body(self, conn, cur):
        subject = self.GET_subject(conn, cur)
        if subject.comment is None:
            raise exception.rest.NotFound('comment on "%s"' % subject)
        return subject.comment + '\n'

    def GET(self, uri):
        return _GET(self, self.GET_body, lambda self, response: _post_commit(self, response, 'text/plain'))

    def SET_body(self, conn, cur, getresults, comment):
        subject = self.GET_subject(conn, cur)
        subject.set_comment(conn, cur, comment)

    def PUT(self, uri):
        def body(conn, cur):
            self.SET_body(conn, cur, self.GET_subject(conn, cur), flask.request.stream.read().decode())
            return ''
        return _MODIFY(self, body, _post_commit)
    
    def DELETE(self, uri):
        def body(conn, cur):
            self.SET_body(conn, cur, self.GET_subject(conn, cur), None)
            return None
        return _MODIFY(self, body, _post_commit)       

class SchemaComment (Comment):
    """A specific schema's comment."""
    def __init__(self, schema):
        Comment.__init__(self, schema.catalog, schema)

class TableComment (Comment):
    """A specific table's comment."""
    def __init__(self, table):
        Comment.__init__(self, table.schema.catalog, table)

class ColumnComment (Comment):
    """A specific column's comment."""
    def __init__(self, column):
        Comment.__init__(self, column.table.schema.catalog, column)

class KeyComment (Comment):
    """A specific key's comment."""
    def __init__(self, key):
        Comment.__init__(self, key.table.schema.catalog, key)

class ForeignkeyReferencesComment (Comment):
    """A specific fkey's comment."""
    def __init__(self, fkey):
        Comment.__init__(self, fkey.catalog, fkey)
    
    def GET_subject(self, conn, cur):
        fkrs = self.subject.GET_body(conn, cur)
        if len(fkrs) != 1:
            raise NotImplementedError('ForeignkeyReferencesComment on %d fkrs' % len(fkrs))
        return fkrs[0]

class Annotations (Api):
    def __init__(self, catalog, subject):
        Api.__init__(self, catalog)
        self.subject = subject
        self.key = None

    def annotation(self, key):
        self.key = key
        return self

    def GET_subject(self, conn, cur):
        return self.subject.GET_body(conn, cur)

    def GET_body(self, conn, cur):
        subject = self.GET_subject(conn, cur)
        if self.key is None:
            return subject.annotations
        else:
            return subject.annotations[self.key]

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def PUT_body(self, conn, cur, value):
        subject = self.GET_subject(conn, cur)
        if self.key is None:
            subject.set_annotations(conn, cur, value)
            return False
        else:
            oldval = subject.set_annotation(conn, cur, self.key, value)
            return oldval is None

    def PUT(self, uri):
        def post_commit(self, created):
            if created:
                deriva_ctx.deriva_response.status_code = 201
            return _post_commit(self, '')
        return _MODIFY_with_json_input(self, self.PUT_body, post_commit)
    
    def DELETE_body(self, conn, cur):
        if self.key is None:
            raise exception.rest.NoMethod('DELETE only supported on individually keyed annotations')
        subject = self.GET_subject(conn, cur)
        if self.key not in subject.annotations:
            raise exception.rest.NotFound('annotation "%s" on "%s"' % (self.key, subject))
        subject.delete_annotation(conn, cur, self.key)
        return ''

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

class CatalogAnnotations(Annotations):
    def __init__(self, catalog):
        Annotations.__init__(self, catalog, catalog)

class TableAnnotations (Annotations):
    def __init__(self, table):
        Annotations.__init__(self, table.schema.catalog, table)

class SchemaAnnotations (Annotations):
    def __init__(self, schema):
        Annotations.__init__(self, schema.catalog, schema)

class ColumnAnnotations (Annotations):
    def __init__(self, column):
        Annotations.__init__(self, column.table.schema.catalog, column)

class KeyAnnotations (Annotations):
    def __init__(self, key):
        Annotations.__init__(self, key.table.schema.catalog, key)

class ForeignkeyReferenceAnnotations (Annotations):
    def __init__(self, fkrs):
        Annotations.__init__(self, fkrs.catalog, fkrs)

    def GET_subject(self, conn, cur):
        fkrs = self.subject.GET_body(conn, cur)
        if len(fkrs) != 1:
            raise NotImplementedError('ForeignkeyReferencesAnnotations on %d fkrs' % len(fkrs))
        return fkrs[0]

class Table (Api):
    """A specific table by name."""
    def __init__(self, schema, name, catalog=None):
        if catalog is None:
            self.catalog = schema.catalog
        else:
            self.catalog = catalog
        Api.__init__(self, self.catalog)
        self.schema = schema
        self.name = name

    def acls(self):
        """The ACL set for this table."""
        return TableAcl(self)

    def dynacls(self):
        return TableDynacl(self)

    def comment(self):
        """The comment for this table."""
        return TableComment(self)

    def annotations(self):
        return TableAnnotations(self)

    def columns(self):
        """The column set for this table."""
        return Columns(self)

    def keys(self):
        """The key set for this table."""
        return Keys(self)

    def key(self, column_set):
        """A specific key for this table."""
        return Key(self, column_set, catalog=self.catalog)

    def foreignkeys(self):
        """The foreign key set for this table."""
        return Foreignkeys(self)

    def foreignkey(self, column_set):
        """A specific foreign key for this table."""
        return Foreignkey(self, column_set, catalog=self.catalog)

    def GET(self, uri):
        return _GET(self, lambda conn, cur: self.GET_body(conn, cur, True), _post_commit_json)
    
    def GET_body(self, conn, cur, final=False):
        if self.schema is not None:
            schema = self.schema.GET_body(conn, cur)
        try:
            if self.schema is not None:
                return schema.tables.get_enumerable(self.name)
            else:
                return deriva_ctx.ermrest_catalog_model.lookup_table(self.name)
        except exception.ConflictModel as e:
            if final:
                raise exception.NotFound(u"table %s in schema %s" % (self.name, schema.name))
            raise

    def POST(self, uri):
        # give more helpful error message
        raise exception.rest.NoMethod('create tables at the table collection resource instead')

    def DELETE_body(self, conn, cur):
        table = self.GET_body(conn, cur, True)
        table.schema.delete_table(conn, cur, self.name.one_str())
        return ''

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

    def PUT_body(self, conn, cur, tabledoc):
        tabledoc['table_name'] = tabledoc.get('table_name', self.name.one_str())
        schema = self.schema.GET_body(conn, cur)
        try:
            # handle alteration of existing table
            table = schema.tables.get_enumerable(self.name.one_str())
            return table.update(conn, cur, tabledoc, deriva_ctx.ermrest_config)
        except exception.ConflictModel as e:
            # handle creation of new table, same as POST /table/
            tables = Tables(self.schema)
            return tables.POST_body(conn, cur, tabledoc)

    def PUT(self, uri):
        def post_commit(self, table):
            return _post_commit_json(self, table)
        return _MODIFY_with_json_input(self, self.PUT_body, post_commit)
        
class Columns (Api):
    """A column set."""
    def __init__(self, table):
        Api.__init__(self, table.schema.catalog)
        self.table = table

    def column(self, name):
        """A specific column for this table."""
        return Column(self.table, name)

    def GET_body(self, conn, cur):
        return self.table.GET_body(conn, cur).columns_in_order()

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
    
    def POST_body(self, conn, cur, columndoc):
        table = self.table.GET_body(conn, cur)
        return table.add_column(conn, cur, columndoc, deriva_ctx.ermrest_config)

    def POST(self, uri):
        def post_commit(self, column):
            deriva_ctx.deriva_response.status_code = 201
            return _post_commit_json(self, column)
        return _MODIFY_with_json_input(self, self.POST_body, post_commit)

class Column (Api):
    """A specific column by name."""
    def __init__(self, table, name):
        Api.__init__(self, table.schema.catalog)
        self.table = table
        self.name = name

    def acls(self):
        """The ACL set for this column."""
        return ColumnAcl(self)

    def dynacls(self):
        """The ACL set for this column."""
        return ColumnDynacl(self)

    def comment(self):
        return ColumnComment(self)

    def annotations(self):
        return ColumnAnnotations(self)

    def GET_body(self, conn, cur, final=False):
        table = self.table.GET_body(conn, cur)
        try:
            return table.columns.get_enumerable(self.name)
        except exception.ConflictModel as e:
            raise exception.NotFound(u"column %s in table %s" % (self.name, table.name))
    
    def GET(self, uri):
        return _GET(self, lambda conn, cur: self.GET_body(conn, cur, True), _post_commit_json)
    
    def DELETE_body(self, conn, cur):
        column = self.GET_body(conn, cur, True)
        column.table.delete_column(conn, cur, str(self.name))
        return ''

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

    def PUT_body(self, conn, cur, columndoc):
        columndoc['name'] = columndoc.get('name', self.name.one_str())
        table = self.table.GET_body(conn, cur)
        try:
            # handle alteration of existing column
            column = table.columns.get_enumerable(self.name.one_str())
            return column.update(conn, cur, columndoc, deriva_ctx.ermrest_config)
        except exception.ConflictModel as e:
            # handle creation of new column, same as POST /column/
            columns = Columns(self.table)
            return columns.POST_body(conn, cur, columndoc)

    def PUT(self, uri):
        def post_commit(self, column):
            return _post_commit_json(self, column)
        return _MODIFY_with_json_input(self, self.PUT_body, post_commit)

class Keys (Api):
    """A set of keys."""
    def __init__(self, table, catalog=None):
        if catalog is None:
            catalog = table.schema.catalog
        Api.__init__(self, catalog)
        self.table = table

    def GET_body(self, conn, cur):
        return [ u for u in self.table.GET_body(conn, cur).uniques.values() if u.has_right('enumerate') ]

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)
        
    def POST_body(self, conn, cur, keydoc):
        table = self.table.GET_body(conn, cur)
        return list(table.add_unique(conn, cur, keydoc))

    def POST(self, uri):
        def post_commit(self, newkeys):
            deriva_ctx.deriva_response.status_code = 201
            return _post_commit_json(self, newkeys)
        return _MODIFY_with_json_input(self, self.POST_body, post_commit)

class Key (Api):
    """A specific key by column set."""
    def __init__(self, table, column_set, catalog=None):
        Api.__init__(self, catalog)
        self.table = table
        self.columns = column_set

    def comment(self):
        return KeyComment(self)

    def annotations(self):
        return KeyAnnotations(self)
        
    def GET_body(self, conn, cur, conflict_model=False):
        table = self.table.GET_body(conn, cur)
        cols = OrderedFrozenSet([ table.columns.get_enumerable(c) for c in self.columns ])
        if cols not in table.uniques:
            if conflict_model:
                raise exception.ConflictModel(u'key (%s)' % (u','.join([ str(c.name) for c in cols])))
            else:
                raise exception.rest.NotFound(u'key (%s)' % (u','.join([ str(c.name) for c in cols])))
        return table.uniques[cols]
        
    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def DELETE_body(self, conn, cur):
        key = self.GET_body(conn, cur)
        key.delete(conn, cur)
        return ''

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

    def PUT_body(self, conn, cur, keydoc):
        try:
            # handle alteration of existing constraint
            key = self.GET_body(conn, cur, conflict_model=True)
            return key.update(conn, cur, keydoc, deriva_ctx.ermrest_config)
        except exception.ConflictModel as e:
            # handle creation of new key, same as POST /key/
            keys = Keys(self.table)
            return keys.POST_body(conn, cur, keydoc)

    def PUT(self, uri):
        def post_commit(self, table):
            return _post_commit_json(self, table)
        return _MODIFY_with_json_input(self, self.PUT_body, post_commit)

class Foreignkeys (Api):
    """A set of foreign keys."""
    def __init__(self, table):
        Api.__init__(self, table.schema.catalog)
        self.table = table

    def GET_body(self, conn, cur):
        return [ fk for fk in self.table.GET_body(conn, cur).fkeys.values() if fk.has_right('enumerate') ]
        
    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def POST_body(self, conn, cur, keydoc):
        table = self.table.GET_body(conn, cur)
        return list(table.add_fkeyref(conn, cur, keydoc))

    def POST(self, uri):
        def post_commit(self, newrefs):
            deriva_ctx.deriva_response.status_code = 201
            return _post_commit_json(self, newrefs)
        return _MODIFY_with_json_input(self, self.POST_body, post_commit)

class Foreignkey (Api):
    """A specific foreign key by column set."""
    def __init__(self, table, column_set, catalog=None):
        if catalog is None:
            catalog = table.schema.catalog
        Api.__init__(self, catalog)
        self.table = table
        self.columns = column_set

    def references(self):
        """A set of foreign key references from this foreign key."""
        return ForeignkeyReferences(self.table.schema.catalog).with_from_key(self)

    def GET_body(self, conn, cur, final=False):
        table = self.table.GET_body(conn, cur)
        cols = frozenset([ table.columns.get_enumerable(str(c)) for c in self.columns ])
        try:
            return table.fkeys.get_enumerable(cols)
        except exception.ConflictModel as e:
            if final:
                raise exception.NotFound(u'foreign key %s in table %s' % (u",".join([ str(c) for c in cols]), table.name))
            raise
    
    def GET(self, uri):
        return _GET(self, lambda conn, cur: self.GET_body(conn, cur, True), _post_commit_json)
    
class ForeignkeyReferences (Api):
    """A set of foreign key references."""
    def __init__(self, catalog):
        Api.__init__(self, catalog)
        self.catalog = catalog
        self._from_table = None
        self._from_key = None
        self._to_table = None
        self._to_key = None

    # currently unused but might be useful to retain?
    def with_from_table(self, from_table):
        """Refine reference set with referencing table information."""
        self._from_table = from_table
        return self

    def with_from_table_name(self, from_table_name):
        """Refine reference set with referencing table information."""
        if len(from_table_name) == 2:
            sname, tname = from_table_name
        elif len(from_table_name) == 1:
            sname, tname = None, from_table_name
        else:
            raise ValueError('Invalid qualified table name: %s' % ':'.join(from_table_name))
        self._from_table = Table(sname, tname, catalog=self.catalog)
        return self

    def with_from_key(self, from_key):
        """Refine reference set with foreign key information."""
        self._from_key = from_key
        return self

    # currently unused but might be useful to retain?
    def with_from_columns(self, from_columns):
        """Refine reference set with foreign key column information."""
        assert self._from_table
        return self.with_from_key(self._from_table.foreignkey(from_columns))

    # currently unused but might be useful to retain?
    def with_to_table(self, to_table):
        """Refine reference set with referenced table information."""
        self._to_table = to_table
        return self

    def with_to_table_name(self, to_table_name):
        """Refine reference set with referenced table information."""
        if len(to_table_name) == 2:
            sname, tname = to_table_name
        elif len(to_table_name) == 1:
            sname, tname = None, to_table_name
        else:
            raise ValueError('Invalid qualified table name: %s' % ':'.join(to_table_name))
        self._to_table = Table(sname and Schema(self.catalog, sname), tname, catalog=self.catalog)
        return self

    def with_to_key(self, to_key):
        """Refine reference set with referenced key information."""
        self._to_key = to_key
        return self

    def with_to_columns(self, to_columns):
        """Refine reference set with referenced column information."""
        assert self._to_table
        return self.with_to_key( self._to_table.key(to_columns) )

    def acls(self):
        return ForeignkeyReferenceAcl(self)

    def dynacls(self):
        return ForeignkeyReferenceDynacl(self)

    def annotations(self):
        return ForeignkeyReferenceAnnotations(self)

    def comment(self):
        return ForeignkeyReferencesComment(self)

    def GET_body(self, conn, cur):
        from_table, from_key = None, None
        to_table, to_key = None, None

        # get real ermrest.model instances...
        if self._from_key:
            from_key = self._from_key.GET_body(conn, cur)
            from_table = from_key.table
        elif self._from_table:
            from_table = self._from_table.GET_body(conn, cur)

        if self._to_key:
            to_key = self._to_key.GET_body(conn, cur)
            to_table = to_key.table
        elif self._to_table:
            to_table = self._to_table.GET_body(conn, cur)

        # find matching foreign key references...
        if from_table:
            fkrs = []
            for fk in [ fk for fk in from_table.fkeys.values() if fk.has_right('enumerate') ]:
                for rt in [ rt for rt in fk.table_references.keys() if rt.has_right('enumerate') ]:
                    fkrs.extend( fk.table_references[rt] )

            if from_key:
                # filter by foreign key
                fkrs = [ fkr for fkr in fkrs if fkr.foreign_key == from_key and fkr.has_right('enumerate') ]

            if to_table:
                # filter by to_table
                fkrs = [ fkr for fkr in fkrs if fkr.unique.table == to_table and fkr.has_right('enumerate') ]
                if to_key:
                    # filter by to_key
                    fkrs = [ fkr for fkr in fkrs if fkr.unique == to_key ]

        else:
            # since from_table is absent, we must have to_table info...
            assert to_table
            fkrs = []
            for u in [ r for u in to_table.uniques.values() if u.has_right('enumerate') ]:
                for rt in u.table_references.keys():
                    fkrs.extend( u.table_references[rt] )

            if to_key:
                # filter by to_key
                fkrs = [ fkr for fkr in fkrs if fkr.unique == to_key if u.has_right('enumerate') ]

        return fkrs

    def GET(self, uri):
        return _GET(self, self.GET_body, _post_commit_json)

    def DELETE_body(self, conn, cur):
        fkrs = self.GET_body(conn, cur)
        for fkr in fkrs:
            fkr.delete(conn, cur)
        return ''

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

    def PUT_body(self, conn, cur, fkrdoc):
        fkrs = self.GET_body(conn, cur)
        if len(fkrs) == 1:
            # handle alteration of existing constraint
            fkr = fkrs[0]
            return fkr.update(conn, cur, fkrdoc, deriva_ctx.ermrest_config)
        elif len(fkrs) > 1:
            raise NotImplementedError('PUT found more than one FKR for %s -> %s' % (self._from_key, self._to_key))
        else:
            # handle creation of new fkey, same as POST /foreignkey/
            fkeys = ForeignKeys(self.table)
            return fkeys.POST_body(conn, cur, fkrdoc)

    def PUT(self, uri):
        if self._from_key and self._to_key:
            # only attempt PUT on full FKR URLs w/ from-key and to-key populated
            def post_commit(self, fkr):
                return _post_commit_json(self, fkr)
            return _MODIFY_with_json_input(self, self.PUT_body, post_commit)
        else:
            raise exception.rest.NoMethod()
