
import unittest
import common

import urllib

_Sd = "AclBindingDefault"
_Se = "AclBindingExplicit"

_fkey_T2_T1 = [_Sd, "fkey T2 to T1"]
_fkey_T3_T1 = [_Se, "fkey T3 to T1"]

def setUpModule():
    r = common.primary_session.get('schema/%s' % _Sd)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()

catalog_acls = dict(common.catalog_acls)
catalog_acls['owner'] = [common.primary_client_id]

class AclBindingT1 (common.ErmrestTest):
    resource = 'schema/%s/table/T1' % _Sd

    supported_dynacl_types = {
        'owner',
        'update',
        'delete',
        'select'
    }

    initial_dynacls = {}

    additional_dynacls = {
        'my binding 2': {
            'types': ['owner'],
            'projection': 'name',
            'projection_type': 'acl'
        }
    }

    replacement_dynacls = {
        'my binding 3': {
            'types': ['owner', 'update'],
            'projection': [{"inbound": _fkey_T2_T1}, 'name'],
            'projection_type': 'acl'
        },
        'my binding 4': {
            'types': ['owner', 'update'],
            'projection': [{"inbound": _fkey_T3_T1}, 'name'],
            'projection_type': 'acl'
        }
    }

    replacement_conflicts = {
        'unknown column': {
            'types': ['owner', 'update'],
            'projection': ['owner']
        },
        'wrong sided fkey': {
            'types': ['owner', 'update'],
            'projection': [{"outbound": _fkey_T2_T1}, 'name']
        }
    }

    def _url(self, binding_name=None):
        url = '%s/acl_binding' % self.resource
        if binding_name is None:
            return url
        else:
            return '%s/%s' % (url, urllib.quote(binding_name))

    def _check(self, expected):
        r = self.session.get(self._url())
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json(), expected)
        for binding_name, binding in expected.items():
            r = self.session.get(self._url(binding_name))
            self.assertHttp(r, 200, 'application/json')
            self.assertEqual(r.json(), binding)

        r = self.session.get(self.resource)
        self.assertHttp(r, 200, 'application/json')
        if type(r.json()) is list:
            # for fkeyref...
            assert len(r.json()) == 1
            self.assertEqual(r.json()[0]['acl_bindings'], expected)
        else:
            self.assertEqual(r.json()['acl_bindings'], expected)
            
    def test_1_initial(self):
        self._check(self.initial_dynacls)

    def test_2_addition(self):
        for binding_name, binding in self.additional_dynacls.items():
            self.assertHttp(self.session.put(self._url(binding_name), json=binding), 200)
        expected = self.initial_dynacls.copy()
        expected.update(self.additional_dynacls)
        self._check(expected)

    def test_3_pruning(self):
        expected = self.initial_dynacls.copy()
        expected.update(self.additional_dynacls)
        for binding_name, binding in self.additional_dynacls.items():
            self.assertHttp(self.session.delete(self._url(binding_name)), 200)
            del expected[binding_name]
            self._check(expected)

    def test_4_replacement(self):
        self.assertHttp(self.session.put(self._url(), json=self.additional_dynacls), 200)
        self._check(self.additional_dynacls)
        self.assertHttp(self.session.put(self._url(), json=self.replacement_dynacls), 200)
        self._check(self.replacement_dynacls)

    def test_5_deletion(self):
        self.assertHttp(self.session.delete(self._url()), 200)
        self._check({})

    def test_6_conflicts(self):
        for binding_name, binding in self.replacement_conflicts.items():
            self.assertHttp(self.session.put(self._url(binding_name), json=binding), 409)

class AclBindingT2 (AclBindingT1):
    resource = 'schema/%s/table/T2' % _Sd

    replacement_dynacls = {
        'my binding 3': {
            'types': ['owner', 'update'],
            'projection': [{"outbound": _fkey_T2_T1}, 'name'],
            'projection_type': 'acl'
        }
    }

    replacement_conflicts = {
        'unknown column': {
            'types': ['owner', 'update'],
            'projection': ['owner']
        },
        'disconnected fkey': {
            'types': ['owner', 'update'],
            'projection': [{"inbound": _fkey_T3_T1}, 'name']
        },
        'wrong sided fkey': {
            'types': ['owner', 'update'],
            'projection': [{"inbound": _fkey_T2_T1}, 'name']
        }
    }

class AclBindingT2ColName (AclBindingT2):
    resource = 'schema/%s/table/T2/column/name' % _Sd

class AclBindingT2Fkey (AclBindingT1):
    resource = 'schema/%s/table/T2/foreignkey/t1id/reference/%s:T1/id' % (_Sd, _Sd)

    supported_dynacl_types = {
        'owner',
        'insert',
        'update'
    }

class AclBindingT3 (AclBindingT1):
    resource = 'schema/%s/table/T3' % _Se
   
    initial_dynacls = {
        'my binding 1': {
            'types': ['owner'],
            'projection': 'owner',
            'projection_type': 'acl'
        }
    }

    replacement_dynacls = {
        'my binding 3': {
            'types': ['owner', 'update'],
            'projection': [{"outbound": _fkey_T3_T1}, 'name'],
            'projection_type': 'acl'
        }
    }

    replacement_conflicts = {
        'unknown column': {
            'types': ['owner', 'update'],
            'projection': ['badcol']
        },
        'disconnected fkey A1': {
            'types': ['owner', 'update'],
            'projection': [{"outbound": _fkey_T2_T1}, 'name']
        },
        'disconnected fkey A2': {
            'types': ['owner', 'update'],
            'projection': [{"inbound": _fkey_T2_T1}, 'name']
        },
        'wrong sided fkey': {
            'types': ['owner', 'update'],
            'projection': [{"inbound": _fkey_T3_T1}, 'name']
        }
    }

class AclBindingT3ColName (AclBindingT3):
    resource = 'schema/%s/table/T3/column/name' % _Se

class AclBindingT3Fkey (AclBindingT2Fkey):
    resource = 'schema/%s/table/T3/foreignkey/t1id/reference/%s:T1/id' % (_Se, _Sd)

    initial_dynacls = {
        'my binding 1': {
            'types': ['owner'],
            'projection': 'name',
            'projection_type': 'acl'
        }
    }

_defs = {
    "schemas": {
        _Sd: {
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
                            "names": [ _fkey_T2_T1 ],
                            "foreign_key_columns": [{"schema_name": _Sd, "table_name": "T2", "column_name": "t1id"}],
                            "referenced_columns": [{"schema_name": _Sd, "table_name": "T1", "column_name": "id"}]
                        }
                    ]
                }
            }
        },
        _Se: {
            "tables": {
                "T3": {
                    "acl_bindings": AclBindingT3.initial_dynacls,
                    "column_definitions": [
                        {
                            "name": "id", 
                            "type": {"typename": "int8"},
                            "nullok": False
                        },
                        {
                            "acl_bindings": AclBindingT3ColName.initial_dynacls,
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
                        },
                        {
                            "name": "owner",
                            "type": {"typename": "text"}
                        }
                    ],
                    "keys": [
                        {"unique_columns": ["id"]},
                        {"unique_columns": ["name"]}
                    ],
                    "foreign_keys": [
                        {
                            "names": [ _fkey_T3_T1 ],
                            "acl_bindings": AclBindingT3Fkey.initial_dynacls,
                            "foreign_key_columns": [{"schema_name": _Se, "table_name": "T3", "column_name": "t1id"}],
                            "referenced_columns": [{"schema_name": _Sd, "table_name": "T1", "column_name": "id"}]
                        }
                    ]
                }
            }
        }
    }
}


if __name__ == '__main__':
    unittest.main(verbosity=2)
