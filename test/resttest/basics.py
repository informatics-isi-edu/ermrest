
import unittest
import common

_S = 'basics'
_T1 = 'basictable1'
_T2 = 'basictable2'
_T2b = 'ambiguous2'
_Tc1 = 'composite1'
_Tc2 = 'composite2'

def defs(S):
    # these table definitions get reused in multiple test modules under different per-module schema
    return {
        "schemas": { S: { "tables": {
        _T1: {
            "kind": "table",
            "column_definitions": [ 
                { "type": { "typename": "int8" }, "name": "id", "nullok": False },
                { "type": { "typename": "text" }, "name": "name" }
            ],
            "keys": [ { "unique_columns": [ "id" ] } ]
        },
        _T2:{
            "kind": "table",
            "column_definitions": [ 
                { "type": { "typename": "int8" }, "name": "id" },
                { "type": { "typename": "int8" }, "name": "level1_id"},
                { "type": { "typename": "text" }, "name": "name" }
            ],
            "keys": [ { "unique_columns": [ "id" ] } ],
            "foreign_keys": [
                { 
                    "foreign_key_columns": [{"schema_name": S, "table_name": _T2, "column_name": "level1_id"}],
                    "referenced_columns":  [{"schema_name": S, "table_name": _T1, "column_name": "id"}]
                }
            ]
        },
        _T2b: {
            "kind": "table",
            "column_definitions": [
                { "type": {"typename": "int8" }, "name": "id", "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}},
                { "type": {"typename": "int8" }, "name": "level1_id1", "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}},
                { "type": {"typename": "int8" }, "name": "level1_id2", "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}},
                { "type": {"typename": "text" }, "name": "name", "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}}
            ],
            "keys": [ {"unique_columns": [ "id" ], "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}} ],
            "foreign_keys": [
                {
                    "foreign_key_columns": [{"schema_name": S, "table_name": _T2b, "column_name": "level1_id1"}],
                    "referenced_columns":  [{"schema_name": S, "table_name": _T1, "column_name": "id"}],
                    "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}
                },
                {
                    "foreign_key_columns": [{"schema_name": S, "table_name": _T2b, "column_name": "level1_id2"}],
                    "referenced_columns":  [{"schema_name": S, "table_name": _T1, "column_name": "id"}],
                    "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}
                }
            ],
            "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}
        },
        _Tc1: {
            "kind": "table",
            "column_definitions": [ 
                { "type": { "typename": "int8" }, "name": "id", "nullok": False },
                { "type": { "typename": "timestamptz" }, "name": "last_update" },
                { "type": { "typename": "text" }, "name": "name", "nullok": True },
                { "type": { "typename": "int8" }, "name": "site", "nullok": False }
            ],
            "keys": [ 
                { "unique_columns": [ "id", "site" ] } 
            ]
        },
        _Tc2: {
            "kind": "table",
            "column_definitions": [ 
                { "type": { "typename": "int8" }, "name": "id", "nullok": False },
                { "type": { "typename": "timestamptz" }, "name": "last_update" },
                { "type": { "typename": "text" }, "name": "name", "nullok": True },
                { "type": { "typename": "int8" }, "name": "site", "nullok": False }
            ],
            "keys": [ 
                { "unique_columns": [ "id", "site" ] } 
            ],
            "foreign_keys": [
                { 
                    "foreign_key_columns": [
                        {"schema_name": S, "table_name": _Tc2, "column_name": "id"},
                        {"schema_name": S, "table_name": _Tc2, "column_name": "site"}
                        
                    ],
                    "referenced_columns": [
                        {"schema_name": S, "table_name": _Tc1, "column_name": "id"},
                        {"schema_name": S, "table_name": _Tc1, "column_name": "site"}
                    ]
                }
            ]
        }
    }, "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"} }  },
    "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}
    }

_defs = defs(_S)
_table_defs = _defs['schemas'][_S]['tables']

def expand_table_resources(S, table_defs, table): 
    resources = [
        'schema/%s' % S,
        'schema/%s/table/%s' % (S, table)
    ]
    for coldef in table_defs[table]['column_definitions']:
        resources.append('%s/column/%s' % (resources[1], coldef['name']))

    for keydef in table_defs[table]['keys']:
        resources.append('%s/key/%s' % (resources[1], ','.join(keydef['unique_columns'])))

    for fkeydef in table_defs[table]['foreign_keys']:
        resources.append(
            '%s/foreignkey/%s/reference/%s/%s' % (
                resources[1],
                ','.join([ "%(column_name)s" % c for c in fkeydef['foreign_key_columns']]),
                "%(schema_name)s:%(table_name)s" % fkeydef['referenced_columns'][0],
                ','.join([ "%(column_name)s" % c for c in fkeydef['referenced_columns']]),
            )
        )
    return resources

def setUpModule():
    # this setup covers a bunch of basic table-creation feature tests
    # but we put them here so they are shared fixtures for the rest of the detailed feature tests below...
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()

class BasicColumn (common.ErmrestTest):
    table = _T2b
    column = 'name'
    coldef = {
        "type": { "typename": "text" },
        "name": "name",
        "annotations": {"tag:misd.isi.edu,2015:test0": "value 0"}
    }
    
    def _cols_url(self): return 'schema/%s/table/%s/column' % (_S, self.table)

    def test_get_all(self):
        self.assertHttp(self.session.get(self._cols_url()), 200, 'application/json')

    def test_get_one(self):
        self.assertHttp(self.session.get('%s/%s' % (self._cols_url(), self.column)), 200, 'application/json')

    def test_mutate_1_delete(self):
        self.assertHttp(self.session.delete('%s/%s' % (self._cols_url(), self.column)), 204)
        self.assertHttp(self.session.get('%s/%s' % (self._cols_url(), self.column)), 404)

    def test_mutate_3_recreate(self):
        self.assertHttp(self.session.post(self._cols_url(), json=self.coldef), 201)
        self.test_get_one()

class BasicKey (common.ErmrestTest):
    table = _T1
    key = 'id'
    newkey = 'id,name'
    newkeydef = {"unique_columns": ["id", "name"]}
    
    def _keys_url(self): return 'schema/%s/table/%s/key' % (_S, self.table)

    def test_get_keys(self):
        self.assertHttp(self.session.get(self._keys_url()), 200, 'application/json')

    def test_get_key(self):
        self.assertHttp(self.session.get('%s/%s' % (self._keys_url(), self.key)), 200, 'application/json')

    def test_newkey_absent(self):
        self.assertHttp(self.session.get('%s/%s' % (self._keys_url(), self.newkey)), 404)

    def test_newkey_create(self):
        self.assertHttp(self.session.post(self._keys_url(), json=self.newkeydef), 201, 'application/json')
        self.assertHttp(self.session.get('%s/%s' % (self._keys_url(), self.newkey)), 200)

    def test_newkey_delete(self):
        self.assertHttp(self.session.delete('%s/%s' % (self._keys_url(), self.newkey)), 204)

class CompositeKey (BasicKey):
    table = _Tc1
    key = 'id,site'

def add_fkey_gets(klass):
    # generate tests for each level of foreignkey rest path hierarchy
    for depth in range(1,6):
        def test(self):
            self.assertHttp(self.session.get(self._fkey_url(depth)))
        setattr(klass, 'test_0_access_fkey_depth%d' % depth, test)
    return klass

@add_fkey_gets
class ForeignKey (common.ErmrestTest):
    table = _T2

    def _entity_url(self):
        return 'entity/%s:%s' % (_S, self.table)
    
    def _fkey_url(self, depth=1):
        fkey = _table_defs[self.table]['foreign_keys'][0]
        parts = [
            'schema/%s/table/%s/foreignkey' % (_S, self.table),
            ','.join([ c['column_name'] for c in fkey['foreign_key_columns']]),
            'reference',
            '%(schema_name)s:%(table_name)s' % fkey['referenced_columns'][0],
            ','.join([ c['column_name'] for c in fkey['referenced_columns']])
        ]
        return '/'.join(parts[0:depth])

    def test_1_delete_fkey(self):
        self.assertHttp(self.session.delete(self._fkey_url(5)), 204)
        self.assertHttp(self.session.get(self._fkey_url(5)), 404)

    def test_2_recreate_fkey(self):
        self.assertHttp(self.session.post(self._fkey_url(1), json=_table_defs[self.table]['foreign_keys'][0]), 201)
        self.assertHttp(self.session.get(self._fkey_url(5)), 200, 'application/json')

class ForeignKeyComposite (ForeignKey):
    table = _Tc2
        
def add_url_parse_tests(klass):
    # generate tests for combinations of API, filter, projection
    filters = {
        "unfiltered": "",
        "number": "/id=4",
        "text": "/name=foo",
        "empty": "/name=",
        "null": "/name::null::",
        "regexp": "/name::regexp::x.%2A",
    }
    apis = [ "entity", "attribute", "attributegroup", "aggregate" ]
    good_projections = {
        "entity": "",
        "attribute": "/id,name",
        "attributegroup": "/id;name",
        "aggregate": "/n:=cnt(id)"
    }
    bad_projections = {
        "entity": "/id,name",
        "attribute": "/id;name",
        "attributegroup": "",
        "aggregate": ""
    }
    
    for api in apis:
        for fk in filters:

            def goodproj(self):
                url = '%s%s%s%s' % (api, self.base, filters[fk], good_projections[api])
                self.assertHttp(self.session.get(url), self.base and 200 or 400)

            def badproj(self):
                url = '%s%s%s%s' % (api, self.base, filters[fk], bad_projections[api])
                self.assertHttp(self.session.get(url), 400)

            setattr(klass, 'test_%s_%s_proj' % (api, fk), goodproj)
            setattr(klass, 'test_%s_%s_badproj' % (api, fk), badproj)

    return klass

@add_url_parse_tests
class ParseTable (common.ErmrestTest): base = '/%s:%s' % (_S, _T1)
class ParseNoTable (ParseTable): base = ''

class ConstraintNameNone (common.ErmrestTest):
    table = 'test_constr_names'
    keynames = None
    fkeynames = None
    status = 201

    def defs(self):
        return [
            {
                "schema_name": _S,
                "table_name": self.table,
                "column_definitions": [
                    { "type": { "typename": "int8" }, "name": "id" },
                    { "type": { "typename": "int8" }, "name": "level1_id1"},
                    { "type": { "typename": "text" }, "name": "name" }
                ],
                "keys": [
                    { "unique_columns": [ "id" ], "names": self.keynames }
                ],
                "foreign_keys": [
                    {
                        "names": self.fkeynames,
                        "foreign_key_columns": [{"schema_name": _S, "table_name": self.table, "column_name": "level1_id1"}],
                        "referenced_columns": [{"schema_name": _S, "table_name": _T1, "column_name": "id"}]
                    }
                ]
            }
        ]
    
    def test_1_create(self):
        self.assertHttp(self.session.post('schema', json=self.defs()), self.status)
        if self.status == 201:
            r = self.session.get('schema/%s/table/%s' % (_S, self.table))
            self.assertHttp(r, 200)
            if self.keynames:
                self.assertIn(self.keynames[0], r.json()['keys'][0]['names'])
            if self.fkeynames:
                self.assertIn(self.fkeynames[0], r.json()['foreign_keys'][0]['names'])

    def tearDown(self):
        if self.status == 201:
            self.session.delete('schema/%s/table/%s' % (_S, self.table))

class ConstraintNameEmpty (ConstraintNameNone):
    keynames = []
    fkeynames = []

class ConstraintNameCustom (ConstraintNameNone):
    keynames = [[_S, "mykey"]]
    fkeynames = [[_S, "myfkey"]]

class KeyNamesNumber (ConstraintNameNone):
    keynames = [[_S, 5]]
    status = 400

class FKeyNamesNumber (ConstraintNameNone):
    fkeynames = [[_S, 5]]
    status = 400

class KeyNamesNonlist (ConstraintNameNone):
    keynames = [5]
    status = 400

class FKeyNamesNonlist (ConstraintNameNone):
    fkeynames = [5]
    status = 400

class KeyNameTooLong (ConstraintNameNone):
    keynames = [[_S, "mykey", "extra"]]
    status = 400

class FKeyNameTooLong (ConstraintNameNone):
    fkeynames = [[_S, "mykey", "extra"]]
    status = 400

if __name__ == '__main__':
    unittest.main(verbosity=2)
