
import unittest
import common

import urllib

_Sd = "AclBindingDefault"
_Se = "AclBindingExplicit"

_fkey_T2_T1 = [_Sd, "fkey T2 to T1"]
_fkey_T3_T1 = [_Se, "fkey T3 to T1"]
_fkey_T4_T3 = [_Se, "fkey T4 to T3"]

from common import Int8, Text, Timestamptz, \
    RID, RCT, RMT, RCB, RMB, RidKey, \
    ModelDoc, SchemaDoc, TableDoc, ColumnDoc, KeyDoc, FkeyDoc

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
            'projection_type': 'acl',
            'scope_acl': ['*'],
        }
    }

    replacement_dynacls = {
        'my binding 3': {
            'types': ['owner', 'update'],
            'projection': [{"inbound": _fkey_T2_T1}, 'name'],
            'projection_type': 'acl',
            'scope_acl': ['*'],
        },
        'my binding 4': {
            'types': ['owner', 'update'],
            'projection': [{"inbound": _fkey_T3_T1}, 'name'],
            'projection_type': 'acl',
            'scope_acl': ['*'],
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
            return '%s/%s' % (url, urllib.parse.quote(binding_name))

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
            self.assertHttp(self.session.delete(self._url(binding_name)), 204)
            del expected[binding_name]
            self._check(expected)

    def test_4_replacement(self):
        self.assertHttp(self.session.put(self._url(), json=self.additional_dynacls), 200)
        self._check(self.additional_dynacls)
        self.assertHttp(self.session.put(self._url(), json=self.replacement_dynacls), 200)
        self._check(self.replacement_dynacls)

    def test_5_deletion(self):
        self.assertHttp(self.session.delete(self._url()), 204)
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
            'projection_type': 'acl',
            'scope_acl': ['*'],
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
            'projection_type': 'acl',
            'scope_acl': ['*'],
        }
    }

    replacement_dynacls = {
        'my binding 3': {
            'types': ['owner', 'update'],
            'projection': [{"outbound": _fkey_T3_T1}, 'name'],
            'projection_type': 'acl',
            'scope_acl': ['*'],
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
            'projection_type': 'acl',
            'scope_acl': ['*'],
        }
    }

class AclBindingT4Prune (common.ErmrestTest):
    initial_dynacls = {
        'binding1': {
            'types': ['owner'],
            'projection': [ {"outbound": _fkey_T4_T3}, 'RCB' ],
            'projection_type': 'acl',
            'scope_acl': ['*'],
        }
    }

    binding1_url = 'schema/%s/table/T4/acl_binding/binding1' % _Se
    fkey_url = 'schema/%s/table/T4/foreignkey/t3_id/reference/%s:T3/id' % (_Se, _Se)

    def test_pruning(self):
        self.assertHttp(self.session.get(self.binding1_url), 200, 'application/json')
        self.assertHttp(self.session.delete(self.fkey_url), 204)
        self.assertHttp(self.session.get(self.binding1_url), 404)

_defs = ModelDoc(
    [
        SchemaDoc(
            _Sd,
            [
                TableDoc(
                    "T1",
                    [
                        RID, RCT, RMT, RCB, RMB,
                        ColumnDoc("id", Int8, nullok=False),
                        ColumnDoc("name", Text, nullok=False),
                        ColumnDoc("value", Text),
                    ],
                    [ RidKey, KeyDoc(["id"]), KeyDoc(["name"]) ],
                ),
                TableDoc(
                    "T2",
                    [
                        RID, RCT, RMT, RCB, RMB,
                        ColumnDoc("id", Int8, nullok=False),
                        ColumnDoc("name", Text, nullok=False),
                        ColumnDoc("value", Text),
                        ColumnDoc("t1id", Int8),
                    ],
                    [ RidKey, KeyDoc(["id"]), KeyDoc(["name"]) ],
                    [
                        FkeyDoc(_Sd, "T2", ["t1id"], _Sd, "T1", ["id"], names=[_fkey_T2_T1]),
                    ]
                )
            ]
        ),
        SchemaDoc(
            _Se,
            [
                TableDoc(
                    "T3",
                    [
                        RID, RCT, RMT, RCB, RMB,
                        ColumnDoc("id", Int8, nullok=False),
                        ColumnDoc(
                            "name", Text, nullok=False,
                            acl_bindings=AclBindingT3ColName.initial_dynacls,
                        ),
                        ColumnDoc("value", Text),
                        ColumnDoc("t1id", Int8),
                        ColumnDoc("owner", Text),
                    ],
                    [ RidKey, KeyDoc(["id"]), KeyDoc(["name"]) ],
                    [
                        FkeyDoc(
                            _Se, "T3", ["t1id"], _Sd, "T1", ["id"],
                            acl_bindings=AclBindingT3Fkey.initial_dynacls,
                            names=[_fkey_T3_T1],
                        ),
                    ],
                    acl_bindings=AclBindingT3.initial_dynacls,
                ),
                TableDoc(
                    "T4",
                    [
                        RID, RCT, RMT, RCB, RMB,
                        ColumnDoc("t3_id", Int8, nullok=False),
                    ],
                    [ RidKey ],
                    [
                        FkeyDoc(_Se, "T4", ["t3_id"], _Se, "T3", ["id"], names=[_fkey_T4_T3]),
                    ],
                    acl_bindings=AclBindingT4Prune.initial_dynacls,
                )
            ]
        )
    ]
)

if __name__ == '__main__':
    unittest.main(verbosity=2)
