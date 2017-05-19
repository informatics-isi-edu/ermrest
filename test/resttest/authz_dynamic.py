
import unittest
import common
import authz_static

_S = "AuthzDynamic"

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()

# catalog has these rights:
#  owner: [primary_client_id]
#  enumerate: ['*']
#  select: ['*']
#  else: []

def _merge(d1, d2):
    d1 = dict(d1)
    d1.update(d2)
    return d1

# some reusable ACL binding idioms
_member_owner_acl = {
    "types": ["owner"],
    "projection": "member",
    "projection_type": "acl"
}

_ACL_owner_acl = {
    "types": ["owner"],
    "projection": "ACL",
    "projection_type": "acl"
}

_datacid_member_owner_acl = {
    "types": ["owner"],
    "projection": [{"outbound": [_S, "fkey Data.c_id"]}, "member"],
    "projection_type": "acl"
}

_datacid_ACL_owner_acl = {
    "types": ["owner"],
    "projection": [{"outbound": [_S, "fkey Data.c_id"]}, "ACL"],
    "projection_type": "acl"
}

_assoccid_member_owner_acl = {
    "types": ["owner"],
    "projection": [{"outbound": [_S, "fkey Data_Category.c_id"]}, "member"],
    "projection_type": "acl"
}

_assoccid_ACL_owner_acl = {
    "types": ["owner"],
    "projection": [{"outbound": [_S, "fkey Data_Category.c_id"]}, "ACL"],
    "projection_type": "acl"
}

_assocdid_member_owner_acl = {
    "types": ["owner"],
    "projection": [{"outbound": [_S, "fkey Data_Category.d_id"]}, "member"],
    "projection_type": "acl"
}

_assocdid_ACL_owner_acl = {
    "types": ["owner"],
    "projection": [{"outbound": [_S, "fkey Data_Category.d_id"]}, "ACL"],
    "projection_type": "acl"
}

_extid_datacid_member_owner_acl = {
    "types": ["owner"],
    "projection": [{"outbound": [_S, "fkey Extension.id"]}, {"outbound": [_S, "fkey Data.c_id"]}, "member"],
    "projection_type": "acl"
}

_extid_datacid_ACL_owner_acl = {
    "types": ["owner"],
    "projection": [{"outbound": [_S, "fkey Extension.id"]}, {"outbound": [_S, "fkey Data.c_id"]}, "ACL"],
    "projection_type": "acl"
}

_id_owner_nonnull = {
    "types": ["owner"],
    "projection": "id",
    "projection_type": "nonnull"
}

_did_owner_nonnull = {
    "types": ["owner"],
    "projection": "d_id",
    "projection_type": "nonnull"
}

class Expectation (object):
    def __init__(self, status, content_type=None, response_check=None):
        self.status = status
        self.content_type = content_type
        self.response_check = response_check

    def check(self, test, response):
        test.assertHttp(response, self.status, self.content_type)
        if self.response_check is not None:
            self.response_check(test, response)

def expect_row_count(count):
    def check(test, response):
        test.assertEqual(len(response.json()), count, "Expected %d results, got IDs %r" % (count, map(lambda r: r['id'], response.json())))
    return check

class StaticHidden (common.ErmrestTest):
    acls = {
        "Data": {
            "enumerate": [],
            "select": []
        },
        "Extension": {
            "enumerate": [],
            "select": []
        },
        "Category": {
            "enumerate": [],
            "select": []
        },
        "Data_Category": {
            "enumerate": [],
            "select": []
        }
    }

    bindings = {
        "Data": { "member": _id_owner_nonnull },
        "Extension": { "member": _id_owner_nonnull },
        "Category": { "member": _id_owner_nonnull },
        "Data_Category": { "member": _did_owner_nonnull },
    }

    @classmethod
    def setUpClass(cls):
        for tname, acls in cls.acls.items():
            common.primary_session.put('schema/%s/table/%s/acl' % (_S, tname), json=acls).raise_for_status()
        for tname, bindings in cls.bindings.items():
            common.primary_session.put('schema/%s/table/%s/acl_binding' % (_S, tname), json=bindings).raise_for_status()

    def setUp(self):
        # reset data in case we have mutation test cases
        rdata = list(_data)
        rdata.reverse()
        for path, data in rdata:
            common.primary_session.delete(path)
        for path, data in _data:
            common.primary_session.put(path, data=data, headers={"Content-Type": "text/csv"}).raise_for_status()

    test_expectations = {
        'primary_get_data': Expectation(200, 'application/json', expect_row_count(16)),
        'secondary_get_data': Expectation(409),
        'anonymous_get_data': Expectation(409),
        'primary_get_extension': Expectation(200, 'application/json', expect_row_count(16)),
        'secondary_get_extension': Expectation(409),
        'anonymous_get_extension': Expectation(409),
        'primary_get_join1': Expectation(200, 'application/json', expect_row_count(16)),
        'secondary_get_join1': Expectation(409),
        'anonymous_get_join1': Expectation(409),
    }

    _get_data_urls = ['entity/%s:Data' % _S, 'attribute/%s:Data/*' % _S]

    def test_primary_get_data(self):
        expect = self.test_expectations['primary_get_data']
        for url in self._get_data_urls:
            expect.check(self, common.primary_session.get(url))

    @unittest.skipIf(common.secondary_session is None, "secondary authz test requires TEST_COOKIES2")
    def test_secondary_get_data(self):
        expect = self.test_expectations['secondary_get_data']
        for url in self._get_data_urls:
            expect.check(self, common.secondary_session.get(url))

    @unittest.skipIf(common.anonymous_session is None, "anonymous authz test requires ermrest_config permission")
    def test_anonymous_get_data(self):
        expect = self.test_expectations['anonymous_get_data']
        for url in self._get_data_urls:
            expect.check(self, common.anonymous_session.get(url))

    _get_extension_urls = ['entity/%s:Extension' % _S]

    def test_primary_get_extension(self):
        expect = self.test_expectations['primary_get_extension']
        for url in self._get_extension_urls:
            expect.check(self, common.primary_session.get(url))

    @unittest.skipIf(common.secondary_session is None, "secondary authz test requires TEST_COOKIES2")
    def test_secondary_get_extension(self):
        expect = self.test_expectations['secondary_get_extension']
        for url in self._get_extension_urls:
            expect.check(self, common.secondary_session.get(url))

    @unittest.skipIf(common.anonymous_session is None, "anonymous authz test requires ermrest_config permission")
    def test_anonymous_get_extension(self):
        expect = self.test_expectations['anonymous_get_extension']
        for url in self._get_extension_urls:
            expect.check(self, common.anonymous_session.get(url))

    _get_join1_url = 'entity/%(S)s:Data/%(S)s:Category/%(S)s:Data_Category/%(S)s:Data' % dict(S=_S)

    def test_primary_get_join1(self):
        expect = self.test_expectations['primary_get_join1']
        expect.check(self, common.primary_session.get(self._get_join1_url))

    @unittest.skipIf(common.secondary_session is None, "secondary authz test requires TEST_COOKIES2")
    def test_secondary_get_join1(self):
        expect = self.test_expectations['secondary_get_join1']
        expect.check(self, common.secondary_session.get(self._get_join1_url))

    @unittest.skipIf(common.anonymous_session is None, "anonymous authz test requires ermrest_config permission")
    def test_anonymous_get_join1(self):
        expect = self.test_expectations['anonymous_get_join1']
        expect.check(self, common.anonymous_session.get(self._get_join1_url))

class HiddenPolicy (StaticHidden):
    acls = {
        "Data": {
            "select": []
        },
        "Extension": {
            "enumerate": [],
            "select": []
        },
        "Category": {
            "enumerate": [],
            "select": []
        },
        "Data_Category": {
            "enumerate": [],
            "select": []
        }
    }

    test_expectations = _merge(
        StaticHidden.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', expect_row_count(16)),
            'anonymous_get_data': Expectation(200, 'application/json', expect_row_count(16)),
        }
    )

class StaticUnhidden (StaticHidden):
    acls = {
        "Data": {
            "select": []
        },
        "Extension": {
            "select": []
        },
        "Category": {
            "select": []
        },
        "Data_Category": {
            "select": []
        }
    }

    test_expectations = _merge(
        StaticHidden.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', expect_row_count(16)),
            'anonymous_get_data': Expectation(200, 'application/json', expect_row_count(16)),
            'secondary_get_extension': Expectation(200, 'application/json', expect_row_count(16)),
            'anonymous_get_extension': Expectation(200, 'application/json', expect_row_count(16)),
            'secondary_get_join1': Expectation(200, 'application/json', expect_row_count(16)),
            'anonymous_get_join1': Expectation(200, 'application/json', expect_row_count(16)),
        }
    )

class RowMemberOwner (StaticUnhidden):
    bindings = {
        "Data": { "member": _member_owner_acl },
        "Extension": { "member": _member_owner_acl },
        "Category": { "member": _member_owner_acl },
        "Data_Category": { "member": _assoccid_member_owner_acl }
    }

    test_expectations = _merge(
        StaticUnhidden.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', expect_row_count(8)),
            'anonymous_get_data': Expectation(200, 'application/json', expect_row_count(4)),
            'secondary_get_extension': Expectation(200, 'application/json', expect_row_count(8)),
            'anonymous_get_extension': Expectation(200, 'application/json', expect_row_count(4)),
            'secondary_get_join1': Expectation(200, 'application/json', expect_row_count(8)),
            'anonymous_get_join1': Expectation(200, 'application/json', expect_row_count(2)),
        }
    )

class Cat3Owner (StaticUnhidden):
    bindings = {
        "Data": {
            "cat3": {
                "types": ["owner"],
                "projection": [{"outbound": [_S, "fkey Data.c_id"]}, {"filter": "id", "operand": 3}, "id"],
                "projection_type": "nonnull"
            }
        },
        "Extension": {
            "cat3": {
                "types": ["owner"],
                "projection": [{"outbound": [_S, "fkey Extension.id"]}, {"outbound": [_S, "fkey Data.c_id"]}, {"filter": "id", "operand": 3}, "id"],
                "projection_type": "nonnull"
            }
        },
        "Category": {
            "cat3": {
                "types": ["owner"],
                "projection": [{"filter": "id", "operand": 3}, "id"],
                "projection_type": "nonnull"
            }
        },
        "Data_Category": {
            "cat3": {
                "types": ["owner"],
                "projection": [{"filter": "c_id", "operand": 3}, "c_id"],
                "projection_type": "nonnull"
            }
        }
    }

    test_expectations = _merge(
        RowMemberOwner.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', expect_row_count(4)),
            'secondary_get_extension': Expectation(200, 'application/json', expect_row_count(4)),
            'secondary_get_join1': Expectation(200, 'application/json', expect_row_count(4)),
            'anonymous_get_join1': Expectation(200, 'application/json', expect_row_count(4)),
        }
    )

class RowAclOwner (StaticUnhidden):
    bindings = {
        "Data": { "member": _ACL_owner_acl },
        "Extension": { "member": _ACL_owner_acl },
        "Category": { "member": _ACL_owner_acl },
        "Data_Category": { "member": _assoccid_ACL_owner_acl }
    }

    test_expectations = _merge(
        RowMemberOwner.test_expectations,
        {
            'secondary_get_join1': Expectation(200, 'application/json', expect_row_count(6)),
        }
    )

class RowCategoryMemberOwner (RowMemberOwner):
    bindings = {
        "Data": { "member1": _member_owner_acl, "member2": _datacid_member_owner_acl },
        "Extension": { "member1": _member_owner_acl, "member2": _extid_datacid_member_owner_acl },
        "Category": { "member1": _member_owner_acl },
        "Data_Category": { "memebr1": _assocdid_member_owner_acl, "member2": _assoccid_member_owner_acl }
    }

    test_expectations = _merge(
        RowMemberOwner.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', expect_row_count(12)),
            'anonymous_get_data': Expectation(200, 'application/json', expect_row_count(7)),
            'secondary_get_join1': Expectation(200, 'application/json', expect_row_count(12)),
            'anonymous_get_join1': Expectation(200, 'application/json', expect_row_count(5)),
        }
    )

class RowCategoryAclOwner (RowMemberOwner):
    bindings = {
        "Data": { "member1": _ACL_owner_acl, "member2": _datacid_ACL_owner_acl },
        "Extension": { "member1": _ACL_owner_acl, "member2": _extid_datacid_ACL_owner_acl },
        "Category": { "member1": _ACL_owner_acl },
        "Data_Category": { "member1": _assocdid_ACL_owner_acl, "member2": _assoccid_ACL_owner_acl }
    }

    test_expectations = _merge(
        RowCategoryMemberOwner.test_expectations,
        {
            'secondary_get_join1': Expectation(200, 'application/json', expect_row_count(10)),
        }
    )

class CategoryMemberOwnerHiddenPolicy (HiddenPolicy):
    bindings = {
        "Data": { "member2": _datacid_member_owner_acl },
        "Extension": { "member2": _extid_datacid_member_owner_acl },
        "Category": { },
        "Data_Category": { }
    }

    test_expectations = _merge(
        HiddenPolicy.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', expect_row_count(8)),
            'anonymous_get_data': Expectation(200, 'application/json', expect_row_count(4)),
        }
    )

class CategoryAclOwnerHiddenPolicy (HiddenPolicy):
    bindings = {
        "Data": { "member2": _datacid_ACL_owner_acl },
        "Extension": { "member2": _extid_datacid_ACL_owner_acl },
        "Category": { },
        "Data_Category": { }
    }

    test_expectations = CategoryMemberOwnerHiddenPolicy.test_expectations

class CategoriesAclOwnerHiddenPolicy (HiddenPolicy):
    bindings = {
        "Data": {
            "member2": {
                "types": ["owner"],
                "projection": [{"inbound": [_S, "fkey Data_Category.d_id"]}, {"outbound": [_S, "fkey Data_Category.c_id"]}, "ACL"],
                "projection_type": "acl"
            }
        },
        "Extension": {
            "member2": {
                "types": ["owner"],
                "projection": [{"outbound": [_S, "fkey Extension.id"]}, {"inbound": [_S, "fkey Data_Category.d_id"]}, {"outbound": [_S, "fkey Data_Category.c_id"]}, "ACL"],
                "projection_type": "acl"
            }
        },
        "Category": { },
        "Data_Category": { }
    }

    test_expectations = _merge(
        HiddenPolicy.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', expect_row_count(12)),
            'anonymous_get_data': Expectation(200, 'application/json', expect_row_count(8)),
        }
    )

_data = [
    (
        'entity/%s:Category' % _S,
        """id,name,ACL,member
1,public,"{""*""}",*
2,restricted group,"{""%(secondary)s"",""%(primary)s""}",%(primary)s
3,restricted member,"{""%(primary)s""}",%(secondary)s
4,private,"{""%(primary)s""}",%(primary)s
""" % dict(primary=common.primary_client_id, secondary=common.secondary_client_id)
    ),
    (
        'entity/%s:Data' % _S,
        """id,name,ACL,member,c_id
11,public 1,"{""*""}",*,1
12,public 2,"{""*""}",*,2
13,public 3,"{""*""}",*,3
14,public 4,"{""*""}",*,4
21,restricted group 1,"{""%(secondary)s"",""%(primary)s""}",%(primary)s,1
22,restricted group 2,"{""%(secondary)s"",""%(primary)s""}",%(primary)s,2
23,restricted group 3,"{""%(secondary)s"",""%(primary)s""}",%(primary)s,3
24,restricted group 4,"{""%(secondary)s"",""%(primary)s""}",%(primary)s,4
31,restricted member 1,"{""%(primary)s""}",%(secondary)s,1
32,restricted member 2,"{""%(primary)s""}",%(secondary)s,2
33,restricted member 3,"{""%(primary)s""}",%(secondary)s,3
34,restricted member 4,"{""%(primary)s""}",%(secondary)s,4
41,private 1,"{""%(primary)s""}",%(primary)s,1
42,private 2,"{""%(primary)s""}",%(primary)s,2
43,private 3,"{""%(primary)s""}",%(primary)s,3
44,private 4,"{""%(primary)s""}",%(primary)s,4
""" % dict(primary=common.primary_client_id, secondary=common.secondary_client_id)
    ),
    (
        'entity/%s:Extension' % _S,
        """id,value,ACL,member
11,AA,"{""*""}",*
12,AB,"{""%(secondary)s"",""%(primary)s""}",%(primary)s
13,AC,"{""%(primary)s""}",%(secondary)s
14,AD,"{""%(primary)s""}",%(primary)s
21,BA,"{""*""}",*
22,BB,"{""%(secondary)s"",""%(primary)s""}",%(primary)s
23,BC,"{""%(primary)s""}",%(secondary)s
24,BD,"{""%(primary)s""}",%(primary)s
31,CA,"{""*""}",*
32,CB,"{""%(secondary)s"",""%(primary)s""}",%(primary)s
33,CC,"{""%(primary)s""}",%(secondary)s
34,CD,"{""%(primary)s""}",%(primary)s
41,DA,"{""*""}",*
42,DB,"{""%(secondary)s"",""%(primary)s""}",%(primary)s
43,DC,"{""%(primary)s""}",%(secondary)s
44,DD,"{""%(primary)s""}",%(primary)s
""" % dict(primary=common.primary_client_id, secondary=common.secondary_client_id)
    ),
    (
        'entity/%s:Data_Category' % _S,
        """d_id,c_id
11,1
12,2
13,3
14,4
21,1
22,2
23,3
24,4
31,1
32,2
33,3
34,4
41,1
42,2
43,3
44,4
12,1
13,2
14,3
22,1
23,2
24,3
32,1
33,2
34,3
42,1
43,2
44,3
"""
    )
]

_defs = {
    "schemas": {
        _S: {
            "tables": {
                "Data": {
                    # data static ACLs get managed per test class...
                    "column_definitions": [
                        {
                            "name": "id",
                            "type": {"typename": "int"},
                            "nullok": False
                        },
                        {
                            "name": "name",
                            "type": {"typename": "text"}
                        },
                        {
                            "name": "ACL",
                            "type": {
                                "is_array": True,
                                "typename": "text[]",
                                "base_type": {
                                    "typename": "text"
                                }
                            }
                        },
                        {
                            "name": "member",
                            "type": {"typename": "text"}
                        },
                        {
                            "name": "c_id",
                            "type": {"typename": "int"}
                        }
                    ],
                    "keys": [ {"unique_columns": ["id"]} ],
                    "foreign_keys": [
                        {
                            "names": [ [_S, "fkey Data.c_id"] ],
                            "foreign_key_columns": [
                                {"column_name": "c_id"}
                            ],
                            "referenced_columns": [
                                {"table_name": "Category", "column_name": "id"}
                            ]
                        }
                    ]
                },
                "Extension": {
                    "column_definitions": [
                        {
                            "name": "id",
                            "type": {"typename": "int"},
                            "nullok": False
                        },
                        {
                            "name": "value",
                            "type": {"typename": "text"}
                        },
                        {
                            "name": "ACL",
                            "type": {
                                "is_array": True,
                                "typename": "text[]",
                                "base_type": {
                                    "typename": "text"
                                }
                            }
                        },
                        {
                            "name": "member",
                            "type": {"typename": "text"}
                        }
                    ],
                    "keys": [ {"unique_columns": ["id"]} ],
                    "foreign_keys": [
                        {
                            "names": [ [_S, "fkey Extension.id"] ],
                            "foreign_key_columns": [
                                {"column_name": "id"}
                            ],
                            "referenced_columns": [
                                {"table_name": "Data", "column_name": "id"}
                            ]
                        }
                    ]
                },
                "Category": {
                    "column_definitions": [
                        {
                            "name": "id",
                            "type": {"typename": "int"},
                            "nullok": False
                        },
                        {
                            "name": "name",
                            "type": {"typename": "text"}
                        },
                        {
                            "name": "ACL",
                            "type": {
                                "is_array": True,
                                "typename": "text[]",
                                "base_type": {
                                    "typename": "text"
                                }
                            }
                        },
                        {
                            "name": "member",
                            "type": {"typename": "text"}
                        }
                    ],
                    "keys": [ {"unique_columns": ["id"]} ]
                },
                "Data_Category": {
                    "column_definitions": [
                        {
                            "name": "d_id",
                            "type": {"typename": "int"},
                            "nullok": False
                        },
                        {
                            "name": "c_id",
                            "type": {"typename": "int"},
                            "nullok": False
                        }
                    ],
                    "keys": [ {"unique_columns": ["c_id", "d_id"]} ],
                    "foreign_keys": [
                        {
                            "names": [ [_S, "fkey Data_Category.c_id"] ],
                            "foreign_key_columns": [
                                {"column_name": "c_id"}
                            ],
                            "referenced_columns": [
                                {"table_name": "Category", "column_name": "id"}
                            ]
                        },
                        {
                            "names": [ [_S, "fkey Data_Category.d_id"] ],
                            "foreign_key_columns": [
                                {"column_name": "d_id"}
                            ],
                            "referenced_columns": [
                                {"table_name": "Data", "column_name": "id"}
                            ]
                        }
                    ]
                }
            }
        }
    }
}

if __name__ == '__main__':
    unittest.main(verbosity=2)
