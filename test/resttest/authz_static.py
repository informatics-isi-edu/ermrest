
import unittest
import common

_S = "AuthzStatic"
_S2 = "AuthzStatic2"

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()
        for path, data in _data:
            common.primary_session.put(path, json=data).raise_for_status()

# catalog has these rights:
#  owner: [primary_client_id]
#  enumerate: ['*']
#  else: []

class Authz (common.ErmrestTest):
    # authz tests will use secondary_session to drop implicit ownership-based rights
    session = common.secondary_session

    schema = {}
    schema2 = {}
    T1 = {
        "select": ["*"]
    }
    T1_id = {
        'select': ['*']
    }
    T1_name = {}
    T1_value = {}
    T2 = {
        "select": ["*"]
    }
    T2_id = {}
    T2_name = {}
    T2_value = {}
    T2_t1id = {}
    T2_fkey = {}
    T3 = {
        "select": ["*"]
    }
    T3_id = {}
    T3_name = {}
    T3_t1id = {}
    T3_fkey = {}

    @classmethod
    def setUpClass(cls):
        common.primary_session.put('schema/%s/acl' % _S, json=cls.schema)
        common.primary_session.put('schema/%s/acl' % _S2, json=cls.schema2)

        common.primary_session.put('schema/%s/table/T1/acl' % _S, json=cls.T1)
        common.primary_session.put('schema/%s/table/T1/column/id/acl' % _S, json=cls.T1_id)
        common.primary_session.put('schema/%s/table/T1/column/name/acl' % _S, json=cls.T1_name)
        common.primary_session.put('schema/%s/table/T1/column/value/acl' % _S, json=cls.T1_value)

        common.primary_session.put('schema/%s/table/T2/column/id/acl' % _S, json=cls.T2_id)
        common.primary_session.put('schema/%s/table/T2/column/name/acl' % _S, json=cls.T2_name)
        common.primary_session.put('schema/%s/table/T2/column/value/acl' % _S, json=cls.T2_value)
        common.primary_session.put('schema/%s/table/T2/column/t1id/acl' % _S, json=cls.T2_t1id)
        common.primary_session.put('schema/%s/table/T2/foreignkey/t1id/reference/%s/id/acl' % (_S, _S), json=cls.T2_fkey)

        common.primary_session.put('schema/%s/table/T3/column/id/acl' % _S2, json=cls.T3_id)
        common.primary_session.put('schema/%s/table/T3/column/name/acl' % _S2, json=cls.T3_name)
        common.primary_session.put('schema/%s/table/T3/column/t1id/acl' % _S2, json=cls.T3_t1id)
        common.primary_session.put('schema/%s/table/T3/foreignkey/t1id/reference/%s/id/acl' % (_S2, _S), json=cls.T3_fkey)

    def _hidden_in_model(self, get_collection, key):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        collection = get_collection(r.json())
        self.assertNotIn(key, collection)

    def test_get_data_T1_ent(self):
        r = self.session.get('entity/%s:T1' % _S)
        self.assertHttp(r, 200, 'application/json')
        self.assertIn('id', r.json()[0])
        
    def test_put_data_T1_ent(self):
        self.assertHttp(self.session.put('entity/%s:T1' % _S, json=_data[0][1]), 403)
        
    def test_delete_data_T1_ent(self):
        self.assertHttp(self.session.delete('entity/%s:T1' % _S), 403)
        
    def test_get_data_T1(self):
        self.assertHttp(self.session.get('attribute/%s:T1/name,value' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('attributegroup/%s:T1/name;value' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('aggregate/%s:T1/c:=cnt(*)' % _S), 200, 'application/json')

        self.assertHttp(self.session.get('attribute/A:=%s:T1/(name)=(%s:T3:name)/$A/name,value' % (_S, _S2)), 200, 'application/json')
        self.assertHttp(self.session.get('attributegroup/A:=%s:T1/(name)=(%s:T3:name)/$A/name;value' % (_S, _S2)), 200, 'application/json')
        self.assertHttp(self.session.get('aggregate/A:=%s:T1/(name)=(%s:T3:name)/$A/c:=cnt(*)' % (_S, _S2)), 200, 'application/json')

    def test_put_data_T1(self):
        self.assertHttp(self.session.put('attributegroup/%s:T1/name;value' % _S, json=_data[0][1]), 403)

    def test_delete_data_T1(self):
        self.assertHttp(self.session.delete('attribute/%s:T1/name,value' % _S), 403)
        self.assertHttp(self.session.delete('attribute/A:=%s:T1/(name)=(%s:T3:name)/$A/name,value' % (_S, _S2)), 403)

    def test_get_data_T1_id(self):
        self.assertHttp(self.session.get('entity/%s:T1/id=1' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('attribute/%s:T1/name,value' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('attribute/%s:T1/id,name,value' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('attributegroup/%s:T1/id,name;value' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('aggregate/%s:T1/c:=cnt(id)' % _S), 200, 'application/json')

        self.assertHttp(self.session.get('attribute/A:=%s:T1/%s:T3/id,name' % (_S, _S2)), 200, 'application/json')
        self.assertHttp(self.session.get('attributegroup/A:=%s:T1/%s:T3/id;name' % (_S, _S2)), 200, 'application/json')
        self.assertHttp(self.session.get('aggregate/A:=%s:T1/%s:T3/c:=cnt(*)' % (_S, _S2)), 200, 'application/json')

    def test_put_data_T1_id(self):
        self.assertHttp(self.session.put('attributegroup/%s:T1/id,name;value' % _S, json=_data[0][1]), 403)
        self.assertHttp(self.session.put('attributegroup/%s:T1/name;id' % _S, json=_data[0][1]), 403)

    def test_delete_data_T1_id(self):
        self.assertHttp(self.session.delete('entity/%s:T1/id=1' % _S), 403)
        self.assertHttp(self.session.delete('attribute/%s:T1/id,name,value' % _S), 403)
        self.assertHttp(self.session.delete('attribute/A:=%s:T1/%s:T3/id,name' % (_S, _S2)), 403)

    def test_get_data_T2(self):
        self.assertHttp(self.session.get('entity/%s:T2' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('attribute/%s:T2/id,name,value' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('attributegroup/%s:T2/id,name;value' % _S), 200, 'application/json')
        self.assertHttp(self.session.get('aggregate/%s:T2/c:=cnt(*)' % _S), 200, 'application/json')

    def test_put_data_T2(self):
        self.assertHttp(self.session.put('entity/%s:T2' % _S, json=_data[1][1]), 403)
        self.assertHttp(self.session.put('attributegroup/%s:T2/id,name;value' % _S, json=_data[1][1]), 403)

    def test_delete_data_T2(self):
        self.assertHttp(self.session.delete('entity/%s:T2' % _S), 403)
        self.assertHttp(self.session.delete('attribute/%s:T2/id,name,value' % _S), 403)

    def test_get_data_T3(self):
        self.assertHttp(self.session.get('entity/%s:T3' % _S2), 200, 'application/json')
        self.assertHttp(self.session.get('attribute/%s:T3/id,name' % _S2), 200, 'application/json')
        self.assertHttp(self.session.get('attributegroup/%s:T3/id;name' % _S2), 200, 'application/json')
        self.assertHttp(self.session.get('aggregate/%s:T3/c:=cnt(*)' % _S2), 200, 'application/json')

    def test_put_data_T3(self):
        self.assertHttp(self.session.put('entity/%s:T3' % _S2, json=_data[2][1]), 403)
        self.assertHttp(self.session.put('attributegroup/%s:T3/id;name' % _S2, json=_data[2][1]), 403)

    def test_delete_data_T3(self):
        self.assertHttp(self.session.delete('entity/%s:T3' % _S2), 403)
        self.assertHttp(self.session.delete('attribute/%s:T3/id,name' % _S2), 403)

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzHideT1id (Authz):
    T1_id = {
        'select': [],
        'enumerate': []
    }

    def test_hidden_in_model(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        self.assertNotIn(
            'id',
            [ c['name'] for c in r.json()['schemas'][_S]['tables']['T1']['column_definitions'] ]
        )
        self._hidden_in_model(lambda schema: schema['schemas'][_S]['tables']['T2'].get('foreign_keys', []), 0)
        self._hidden_in_model(lambda schema: schema['schemas'][_S2]['tables']['T3'].get('foreign_keys', []), 0)

    def test_S(self):
        self.assertHttp(self.session.get('schema/%s' % _S), 200, 'application/json')
        self.assertHttp(self.session.delete('schema/%s' % _S), 403)

    def test_T1(self):
        self.assertHttp(self.session.get('schema/%s/table/T1' % _S), 200, 'application/json')
        self.assertHttp(self.session.delete('schema/%s/table/T1' % _S), 403)

    def test_T1id(self):
        self.assertHttp(self.session.get('schema/%s/table/T1/column/id' % _S), 404)
        self.assertHttp(self.session.delete('schema/%s/table/T1/column/id' % _S), 404)

    def test_T1name(self):
        self.assertHttp(self.session.get('schema/%s/table/T1/column/name' % _S), 200, 'application/json')
        self.assertHttp(self.session.delete('schema/%s/table/T1/column/name' % _S), 403)

    def test_T2(self):
        self.assertHttp(self.session.get('schema/%s/table/T2' % _S), 200, 'application/json')
        self.assertHttp(self.session.delete('schema/%s/table/T2' % _S), 403)

    def test_T3(self):
        self.assertHttp(self.session.get('schema/%s/table/T3' % _S2), 200, 'application/json')
        self.assertHttp(self.session.delete('schema/%s/table/T3' % _S2), 403)

    def test_T2_fkeys(self):
        r = self.session.get('schema/%s/table/T2/foreignkey' % _S)
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(len(r.json()), 0, "Foreign keys %s should be empty" % (r.json(),))

    def test_T2_fkey(self):
        self.assertHttp(self.session.get('schema/%s/table/T2/foreignkey/t1id' % _S), 404)

    def test_T2_fkeyref(self):
        # referenced table hidden...
        self.assertHttp(self.session.get('schema/%s/table/T2/foreignkey/t1id/reference/%s:T1' % (_S, _S)), 409)
        self.assertHttp(self.session.get('schema/%s/table/T2/foreignkey/t1id/reference/%s:T1/id' % (_S, _S)), 409)
        self.assertHttp(self.session.delete('schema/%s/table/T2/foreignkey/t1id/reference/%s:T1/id' % (_S, _S)), 409)

    def test_T3_fkeys(self):
        r = self.session.get('schema/%s/table/T3/foreignkey' % _S2)
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(len(r.json()), 0, "Foreign keys %s should be empty" % (r.json(),))

    def test_T3_fkey(self):
        self.assertHttp(self.session.get('schema/%s/table/T3/foreignkey/t1id' % _S2), 404)

    def test_T3_fkeyref(self):
        # referenced table hidden...
        self.assertHttp(self.session.get('schema/%s/table/T3/foreignkey/t1id/reference/%s:T1' % (_S2, _S)), 409)
        self.assertHttp(self.session.get('schema/%s/table/T3/foreignkey/t1id/reference/%s:T1/id' % (_S2, _S)), 409)
        self.assertHttp(self.session.delete('schema/%s/table/T3/foreignkey/t1id/reference/%s:T1/id' % (_S2, _S)), 409)

    def test_get_data_T1_ent(self):
        r = self.session.get('entity/%s:T1' % _S)
        self.assertHttp(r, 200, 'application/json')
        self.assertNotIn('id', r.json()[0])
        
    def test_get_data_T1_id(self):
        self.assertHttp(self.session.get('entity/%s:T1/id=1' % _S), 409)
        self.assertHttp(self.session.get('attribute/%s:T1/id,name,value' % _S), 409)
        self.assertHttp(self.session.get('attributegroup/%s:T1/id,name;value' % _S), 409)
        self.assertHttp(self.session.get('aggregate/%s:T1/c:=cnt(id)' % _S), 409)

        self.assertHttp(self.session.get('attribute/A:=%s:T1/%s:T3/id,name' % (_S, _S2)), 409)
        self.assertHttp(self.session.get('attributegroup/A:=%s:T1/%s:T3/id;name' % (_S, _S2)), 409)
        self.assertHttp(self.session.get('aggregate/A:=%s:T1/%s:T3/c:=cnt(*)' % (_S, _S2)), 409)

    def test_put_data_T1_id(self):
        self.assertHttp(self.session.put('attributegroup/%s:T1/id,name;value' % _S, json=_data[0][1]), 409)
        self.assertHttp(self.session.put('attributegroup/%s:T1/name;id' % _S, json=_data[0][1]), 409)

    def test_delete_data_T1_id(self):
        self.assertHttp(self.session.delete('entity/%s:T1/id=1' % _S), 409)
        self.assertHttp(self.session.delete('attribute/%s:T1/id,name,value' % _S), 409)
        self.assertHttp(self.session.delete('attribute/A:=%s:T1/%s:T3/id,name' % (_S, _S2)), 409)

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzHideT1 (AuthzHideT1id):
    # modify policy scenario and override some tests from superclass...
    T1 = {
        'select': [],
        'enumerate': []
    }
    T1_id = {
        'select': ['*']
    }

    def test_hidden_in_model(self):
        self._hidden_in_model(lambda schema: schema['schemas'][_S]['tables'], "T1")
        self._hidden_in_model(lambda schema: schema['schemas'][_S]['tables']['T2'].get('foreign_keys', []), 0)

    def test_get_data_T1_entity(self):
        self.assertHttp(self.session.get('entity/%s:T1' % _S), 409)

    def test_T1(self):
        self.assertHttp(self.session.get('schema/%s/table/T1' % _S), 404)
        self.assertHttp(self.session.delete('schema/%s/table/T1' % _S), 404)

    def test_T1id(self):
        self.assertHttp(self.session.get('schema/%s/table/T1/column/name' % _S), 409)
        self.assertHttp(self.session.delete('schema/%s/table/T1/column/name' % _S), 409)

    def test_T1name(self):
        self.assertHttp(self.session.get('schema/%s/table/T1/column/id' % _S), 409)
        self.assertHttp(self.session.delete('schema/%s/table/T1/column/id' % _S), 409)

    def test_get_data_T1_ent(self):
        self.assertHttp(self.session.get('entity/%s:T1' % _S), 409)
        
    def test_put_data_T1_ent(self):
        self.assertHttp(self.session.put('entity/%s:T1' % _S, json=_data[0][1]), 409)
        
    def test_delete_data_T1_ent(self):
        self.assertHttp(self.session.delete('entity/%s:T1' % _S), 409)
        
    def test_get_data_T1(self):
        self.assertHttp(self.session.get('attribute/%s:T1/id,name,value' % _S), 409)
        self.assertHttp(self.session.get('attributegroup/%s:T1/id,name;value' % _S), 409)
        self.assertHttp(self.session.get('aggregate/%s:T1/c:=cnt(*)' % _S), 409)

    def test_put_data_T1(self):
        self.assertHttp(self.session.put('attributegroup/%s:T1/name;value' % _S, json=_data[0][1]), 409)

    def test_delete_data_T1(self):
        self.assertHttp(self.session.delete('attribute/%s:T1/name,value' % _S), 409)
        self.assertHttp(self.session.get('attribute/A:=%s:T1/(name)=(%s:T3:name)/$A/name,value' % (_S, _S2)), 409)

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzHideSchema (AuthzHideT1):
    # modify policy scenario and override some tests from superclass...
    schema = {
        'select': [],
        'enumerate': []
    }
    T1 = {
        'select': ['*']
    }

    def test_hidden_in_model(self):
        self._hidden_in_model(lambda schema: schema['schemas'], _S)

    def test_S(self):
        self.assertHttp(self.session.get('schema/%s' % _S), 404)
        self.assertHttp(self.session.delete('schema/%s' % _S), 404)

    def test_T1(self):
        self.assertHttp(self.session.get('schema/%s/table/T1' % _S), 409)
        self.assertHttp(self.session.delete('schema/%s/table/T1' % _S), 409)

    def test_T2(self):
        self.assertHttp(self.session.get('schema/%s/table/T2' % _S), 409)
        self.assertHttp(self.session.delete('schema/%s/table/T2' % _S), 409)

    def test_T2_fkey(self):
        self.assertHttp(self.session.get('schema/%s/table/T2/foreignkey/t1id' % _S), 409)

    def test_T2_fkeys(self):
        self.assertHttp(self.session.get('schema/%s/table/T2/foreignkey' % _S), 409)

    def test_get_data_T2(self):
        self.assertHttp(self.session.get('entity/%s:T2' % _S), 409)
        self.assertHttp(self.session.get('attribute/%s:T2/id,name,value' % _S), 409)
        self.assertHttp(self.session.get('attributegroup/%s:T2/id,name;value' % _S), 409)
        self.assertHttp(self.session.get('aggregate/%s:T2/c:=cnt(*)' % _S), 409)

    def test_put_data_T2(self):
        self.assertHttp(self.session.put('entity/%s:T2' % _S, json=_data[1][1]), 409)
        self.assertHttp(self.session.put('attributegroup/%s:T2/id,name;value' % _S, json=_data[1][1]), 409)

    def test_delete_data_T2(self):
        self.assertHttp(self.session.delete('entity/%s:T2' % _S), 409)
        self.assertHttp(self.session.delete('attribute/%s:T2/id,name,value' % _S), 409)

_data = [
    (
        "entity/%s:T1" % _S,
        [
            {"id": 1, "name": "t1.1", "value": "foo"},
            {"id": 2, "name": "t1.2", "value": "bar"},
            {"id": 3, "name": "t1.3", "value": "baz"},
        ]
    ),
    (
        "entity/%s:T2" % _S,
        [
            {"id": 5, "name": "t2.5", "value": "FOO", "t1id": 1},
            {"id": 6, "name": "t2.6", "value": "BAR", "t1id": 2},
            {"id": 7, "name": "t2.7", "value": "BAR", "t1id": None},
        ]
    ),
    (
        "entity/%s:T3" % _S2,
        [
            {"id": 8, "name": "t3.8", "t1id": 1},
            {"id": 9, "name": "t3.9", "t1id": 2},
            {"id": 10, "name": "t3.10", "t1id": None},
        ]
    ),
]
        
_defs = {
    "schemas": {
        _S: {
            "tables": {
                "T1": {
                    "column_definitions": [
                        {
                            "name": "id", 
                            "type": {"typename": "int8"},
                            "nullok": False
                        },
                        {
                            "name": "name",
                            "type": {"typename": "text"},
                            "nullok": False
                        },
                        {
                            "name": "value",
                            "type": {"typename": "text"}
                        }
                    ],
                    "keys": [
                        {"unique_columns": ["id"]},
                        {"unique_columns": ["name"]}
                    ]
                },
                "T2": {
                    "column_definitions": [
                        {
                            "name": "id", 
                            "type": {"typename": "int8"},
                            "nullok": False
                        },
                        {
                            "name": "name",
                            "type": {"typename": "text"},
                            "nullok": False
                        },
                        {
                            "name": "value",
                            "type": {"typename": "text"}
                        },
                        {
                            "name": "t1id",
                            "type": {"typename": "int8"}
                        }
                    ],
                    "keys": [
                        {"unique_columns": ["id"]},
                        {"unique_columns": ["name"]}
                    ],
                    "foreign_keys": [
                        {
                            "foreign_key_columns": [{"schema_name": _S, "table_name": "T2", "column_name": "t1id"}],
                            "referenced_columns": [{"schema_name": _S, "table_name": "T1", "column_name": "id"}]
                        }
                    ]
                }
            }
        },
        _S2: {
            "tables": {
                "T3": {
                    "column_definitions": [
                        {
                            "name": "id", 
                            "type": {"typename": "int8"},
                            "nullok": False
                        },
                        {
                            "name": "name",
                            "type": {"typename": "text"},
                            "nullok": False
                        },
                        {
                            "name": "t1id",
                            "type": {"typename": "int8"}
                        }
                    ],
                    "keys": [
                        {"unique_columns": ["id"]},
                        {"unique_columns": ["name"]}
                    ],
                    "foreign_keys": [
                        {
                            "foreign_key_columns": [{"schema_name": _S2, "table_name": "T3", "column_name": "t1id"}],
                            "referenced_columns": [{"schema_name": _S, "table_name": "T1", "column_name": "id"}]
                        }
                    ]
                }
            }
        }
    }
}


if __name__ == '__main__':
    unittest.main(verbosity=2)
