
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

def _diff(d1, d2):
    d1 = d1.items()
    d1.sort()
    d1 = tuple(d1)
    d2 = d2.items()
    d2.sort()
    d2 = tuple(d2)
    return d1 != d2

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
        if type(self.response_check) in {list, set}:
            for response_check in self.response_check:
                response_check(test, response)
        elif self.response_check is not None:
            self.response_check(test, response)

def expect_row_count(count):
    def check(test, response):
        test.assertEqual(len(response.json()), count, "Expected %d results, got IDs %r" % (count, map(lambda r: r['id'], response.json())))
    return check

def expect_values(values):
    def check(test, response):
        test.assertEqual(set([ r['value'] for r in response.json() if r['value'] is not None ]), values)
        test.assertEqual(set([ r['values'][0] for r in response.json() if r['values'] is not None ]), values)
    return check

_put_row_data_primary = [
    {"id": 11, "c_id": 1, "name": "public 1 modified"},
    {"id": 12, "c_id": 2, "name": "public 2 modified"},
    {"id": 13, "c_id": 3, "name": "public 3 modified"},
    {"id": 14, "c_id": 4, "name": "public 4 modified"},
    {"id": 21, "c_id": 1, "name": "restricted group 1 modified"},
    {"id": 22, "c_id": 2, "name": "restricted group 2 modified"},
    {"id": 23, "c_id": 3, "name": "restricted group 3 modified"},
    {"id": 24, "c_id": 4, "name": "restricted group 4 modified"},
    {"id": 31, "c_id": 1, "name": "restricted member 1 modified"},
    {"id": 32, "c_id": 2, "name": "restricted member 2 modified"},
    {"id": 33, "c_id": 3, "name": "restricted member 3 modified"},
    {"id": 34, "c_id": 4, "name": "restricted member 4 modified"},
    {"id": 41, "c_id": 1, "name": "private 1 modified"},
    {"id": 42, "c_id": 2, "name": "private 2 modified"},
    {"id": 43, "c_id": 3, "name": "private 3 modified"},
    {"id": 44, "c_id": 4, "name": "private 4 modified"},
]

_put_row_data_secondary = [
    {"id": 11, "c_id": 1, "name": "public 1 modified"},
    {"id": 12, "c_id": 2, "name": "public 2 modified"},
    {"id": 21, "c_id": 1, "name": "restricted group 1 modified"},
    {"id": 22, "c_id": 2, "name": "restricted group 2 modified"},
    {"id": 31, "c_id": 1, "name": "restricted member 1 modified"},
    {"id": 32, "c_id": 2, "name": "restricted member 2 modified"},
]

_put_row_data_anonymous = [
    {"id": 11, "c_id": 1, "name": "public 1 modified"},
    {"id": 12, "c_id": 1, "name": "public 2 modified"},
]

def make_put_test(session, data, get_url, get_expect):
    test_session = getattr(common, '%s_session' % session)
    test_data = {
        'primary': _put_row_data_primary,
        'secondary': _put_row_data_secondary,
        'anonymous': _put_row_data_anonymous
    }[data]
    @unittest.skipIf(test_session is None, "%s authz test requires %s session" % (session, session))
    def test(self):
        get_expect(self, session, data).check(self, test_session.put(get_url(self), json=test_data))
    return test

def make_delete_test(session, data, get_url, get_expect):
    test_session = getattr(common, '%s_session' % session)
    test_data = {
        'primary': _put_row_data_primary,
        'secondary': _put_row_data_secondary,
        'anonymous': _put_row_data_anonymous
    }[data]
    @unittest.skipIf(test_session is None, "%s authz test requires %s session" % (session, session))
    def test(self):
        get_expect(self, session, data).check(self, test_session.delete(get_url(self, test_data)))
    return test

def _test_data_id_preds(test_data):
    return ';'.join([ "id=%d" % row['id'] for row in test_data ])

def add_data_update_tests(klass):
    for session in ['primary', 'secondary', 'anonymous']:
        for data in ['primary', 'secondary', 'anonymous']:

            setattr(
                klass,
                'test_%s_put_row_data_%s' % (session, data),
                make_put_test(
                    session,
                    data,
                    lambda self: self._put_row_data_url,
                    lambda self, session, data: self.test_expectations['%s_put_row_data_%s' % (session, data)]
                )
            )
            setattr(
                klass,
                'test_%s_put_name_data_%s' % (session, data),
                make_put_test(
                    session,
                    data,
                    lambda self: self._put_col_data_url,
                    lambda self, session, data: (
                        self.test_expectations.get(
                            '%s_put_col_data_%s' % (session, data),
                            self.test_expectations['%s_put_row_data_%s' % (session, data)]
                        )
                    )
                )
            )
            setattr(
                klass,
                'test_%s_delete_name_data_%s' % (session, data),
                make_delete_test(
                    session,
                    data,
                    lambda self, test_data: 'attribute/%s:Data/%s/name' % (_S, _test_data_id_preds(test_data)),
                    lambda self, session, data: (
                        self.test_expectations.get(
                            '%s_put_col_data_%s' % (session, data),
                            self.test_expectations['%s_put_row_data_%s' % (session, data)]
                        )
                    )
                )
            )
            setattr(
                klass,
                'test_%s_delete_value_data_%s' % (session, data),
                make_delete_test(
                    session,
                    data,
                    lambda self, test_data: 'attribute/%s:Data/%s/value' % (_S, _test_data_id_preds(test_data)),
                    lambda self, session, data: (
                        self.test_expectations.get(
                            '%s_put_value_data_%s' % (session, data),
                            self.test_expectations.get(
                                '%s_put_col_data_%s' % (session, data),
                                self.test_expectations['%s_put_row_data_%s' % (session, data)]
                            )
                        )
                    )
                )
            )

    return klass

@add_data_update_tests
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

    # for brevity, col_acls are applied as an update over default {"select": ["*"], "update": [common.secondary_client_id]}
    # so custom overrides be specified sparsely on a column-by-column basis
    col_acls = {
        "Data": {
            # "id": {}
        },
        "Extension": {},
        "Category": {},
        "Data_Category": {}
    }

    fkr_acls = {
        "schema/%s/table/Data/foreignkey/c_id/reference/Category/id" % _S: {
            "insert": ["*"],
            "update": ["*"],
        }
    }

    bindings = {
        "Data": { "member": _id_owner_nonnull },
        "Extension": { "member": _id_owner_nonnull },
        "Category": { "member": _id_owner_nonnull },
        "Data_Category": { "member": _did_owner_nonnull },
    }

    col_bindings = {
        # "schema/%s/table/Data/column/%s" % _S: {}
    }

    fkr_bindings = {
        # "schema/%s/table/Data/foreignkey/c_id/reference/Category/id" % _S: {}
    }

    @staticmethod
    def _setUpClass(cls):
        for tname, acls in cls.acls.items():
            common.primary_session.put('schema/%s/table/%s/acl' % (_S, tname), json=acls).raise_for_status()
        for tname, col_acls in cls.col_acls.items():
            for coldef in _defs['schemas'][_S]['tables'][tname]['column_definitions']:
                cname = coldef['name']
                col_acl = {
                    "select": ['*'],
                    "update": [common.secondary_client_id]
                }
                if cname in col_acls:
                    col_acl.update(col_acls[cname])
                aclurl = 'schema/%s/table/%s/column/%s/acl' % (_S, tname, cname)
                if _diff(
                        col_acl,
                        common.primary_session.get(aclurl).json()
                ):
                    common.primary_session.put(aclurl, json=col_acl).raise_for_status()
        for fkr_url_frag, fkr_acls in cls.fkr_acls.items():
            common.primary_session.put('%s/acl' % fkr_url_frag, json=fkr_acls).raise_for_status()
        for tname, bindings in cls.bindings.items():
            common.primary_session.put('schema/%s/table/%s/acl_binding' % (_S, tname), json=bindings).raise_for_status()
        for col_url_frag, bindings in cls.col_bindings.items():
            common.primary_session.put('%s/acl_binding' % col_url_frag, json=bindings).raise_for_status()
        for fkr_url_frag, bindings in cls.fkr_bindings.items():
            common.primary_session.put('%s/acl_binding' % fkr_url_frag, json=bindings).raise_for_status()

    @classmethod
    def setUpClass(cls):
        cls._setUpClass(cls)

    def setUp(self):
        # reset data in case we have mutation test cases
        rdata = list(_data)
        rdata.reverse()
        for path, data in rdata:
            common.primary_session.delete(path)
        for path, data in _data:
            common.primary_session.put(path, data=data, headers={"Content-Type": "text/csv"}).raise_for_status()

    test_expectations = {
        'primary_get_data': Expectation(200, 'application/json', {
            expect_row_count(16),
            expect_values({11,12,13,14,21,22,23,24,31,32,33,34,41,42,43,44})
        }),
        'secondary_get_data': Expectation(409),
        'anonymous_get_data': Expectation(409),
        'primary_put_row_data_primary': Expectation([200,204]),
        'primary_put_row_data_secondary': Expectation([200,204]),
        'primary_put_row_data_anonymous': Expectation([200,204]),
        'secondary_put_row_data_primary': Expectation(409),
        'secondary_put_row_data_secondary': Expectation(409),
        'secondary_put_row_data_anonymous': Expectation(409),
        'anonymous_put_row_data_primary': Expectation(409),
        'anonymous_put_row_data_secondary': Expectation(409),
        'anonymous_put_row_data_anonymous': Expectation(409),
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

    _put_row_data_url = 'entity/%s:Data' % _S
    _put_col_data_url = 'attributegroup/%s:Data/id;name' % _S
    # tests added by add_data_update_tests decorator...

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
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(16),
                expect_values({11,12,13,14,21,22,23,24,31,32,33,34,41,42,43,44})
            }),
            'anonymous_get_data': Expectation(200, 'application/json', {
                expect_row_count(16),
                expect_values({11,12,13,14,21,22,23,24,31,32,33,34,41,42,43,44})
            }),
            'secondary_put_row_data_primary': Expectation([200,204]),
            'secondary_put_row_data_secondary': Expectation([200,204]),
            'secondary_put_row_data_anonymous': Expectation([200,204]),
            'anonymous_put_row_data_primary': Expectation(401),
            'anonymous_put_row_data_secondary': Expectation(401),
            'anonymous_put_row_data_anonymous': Expectation(401),
        }
    )

class RestrictedFkr (HiddenPolicy):
    fkr_acls = {
        "schema/%s/table/Data/foreignkey/c_id/reference/Category/id" % _S: {
            "insert": [],
            "update": [],
        }
    }

    test_expectations = _merge(
        HiddenPolicy.test_expectations,
        {
            'secondary_put_row_data_primary': Expectation(403),
            'secondary_put_row_data_secondary': Expectation(403),
            'secondary_put_row_data_anonymous': Expectation(403),
            'anonymous_put_row_data_primary': Expectation(401),
            'anonymous_put_row_data_secondary': Expectation(401),
            'anonymous_put_row_data_anonymous': Expectation(401),

            'secondary_put_col_data_primary': Expectation([200, 204]),
            'secondary_put_col_data_secondary': Expectation([200, 204]),
            'secondary_put_col_data_anonymous': Expectation([200, 204]),
            'anonymous_put_col_data_primary': Expectation(401),
            'anonymous_put_col_data_secondary': Expectation(401),
            'anonymous_put_col_data_anonymous': Expectation(401),
        }
    )

class RestrictedFkrDomainAcl (RestrictedFkr):
    fkr_bindings = {
        "schema/%s/table/Data/foreignkey/c_id/reference/Category/id" % _S: {
            "aclowner": _ACL_owner_acl
        }
    }

    test_expectations = _merge(
        RestrictedFkr.test_expectations,
        {
            'secondary_put_row_data_secondary': Expectation([200, 204]),
            'secondary_put_row_data_anonymous': Expectation([200, 204]),
            'anonymous_put_row_data_anonymous': Expectation(401),
        }
)

class SelectOnly (HiddenPolicy):
    bindings = {
        "Data": {
            "member": {
                "types": ["select"],
                "projection": "id",
                "projection_type": "nonnull"
            }
        },
        "Extension": { "member": _id_owner_nonnull },
        "Category": { "member": _id_owner_nonnull },
        "Data_Category": { "member": _did_owner_nonnull },
    }

    test_expectations = _merge(
        HiddenPolicy.test_expectations,
        {
            'secondary_put_row_data_primary': Expectation(403),
            'secondary_put_row_data_secondary': Expectation(403),
            'secondary_put_row_data_anonymous': Expectation(403),
            'anonymous_put_row_data_primary': Expectation(401),
            'anonymous_put_row_data_secondary': Expectation(401),
            'anonymous_put_row_data_anonymous': Expectation(401),
        }
    )

class MemberColumnInherit (HiddenPolicy):
    col_acls = {
        "Data": {
            "value": {"select": [], "update": []},
            "values": {"select": [], "update": []}
        }
    }

class MemberColumnSelectUpdate (HiddenPolicy):
    col_acls = {
        "Data": {
            "value": {"select": [], "update": []},
            "values": {"select": [], "update": []}
        }
    }

    col_bindings = {
        "schema/%s/table/Data/column/value" % _S: {
            # test overriding inherited binding w/ different one
            "member": {
                "types": ["select", "update"],
                "projection": "member",
                "projection_type": "acl"
            }
        },
        "schema/%s/table/Data/column/values" % _S: {
            # test suppressing inherited binding
            "member": False,
            "member2": {
                "types": ["select", "update"],
                "projection": "member",
                "projection_type": "acl"
            }
        }
    }

    test_expectations = _merge(
        HiddenPolicy.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(16),
                expect_values({11,12,13,14,31,32,33,34})
            }),
            'anonymous_get_data': Expectation(200, 'application/json', {
                expect_row_count(16),
                expect_values({11,12,13,14})
            }),
            'primary_get_data_filtered': Expectation(200, 'application/json', {
                expect_row_count(16),
                expect_values({11,12,13,14,21,22,23,24,31,32,33,34,41,42,43,44})
            }),
            'secondary_get_data_filtered': Expectation(200, 'application/json', {
                expect_row_count(8),
                expect_values({11,12,13,14,31,32,33,34})
            }),
            'anonymous_get_data_filtered': Expectation(200, 'application/json', {
                expect_row_count(4),
                expect_values({11,12,13,14})
            }),
            'secondary_put_row_data_primary': Expectation(403),
            'secondary_put_row_data_secondary': Expectation(403),
            'secondary_put_col_data_primary': Expectation([200,204]),
            'secondary_put_col_data_secondary': Expectation([200,204]),
            'secondary_put_value_data_primary': Expectation(403),
            'secondary_put_value_data_secondary': Expectation(403),
            'anonymous_put_row_data_primary': Expectation(401),
            'anonymous_put_row_data_secondary': Expectation(401),
            'anonymous_put_col_data_primary': Expectation(401),
            'anonymous_put_col_data_secondary': Expectation(401),
            'anonymous_put_value_data_primary': Expectation(401),
            'anonymous_put_value_data_secondary': Expectation(401),
        }
    )

    _get_data_filtered_urls = [
        'entity/%s:Data/!value::null::' % _S,
        'attribute/%s:Data/!value::null::/*' % _S,
        'entity/%s:Data/!values::null::' % _S,
        'attribute/%s:Data/!values::null::/*' % _S,
    ]

    def test_primary_data_get_filtered(self):
        expect = self.test_expectations['primary_get_data_filtered']
        for url in self._get_data_filtered_urls:
            expect.check(self, common.primary_session.get(url))

    @unittest.skipIf(common.secondary_session is None, "secondary authz test requires TEST_COOKIES2")
    def test_secondary_data_get_filtered(self):
        expect = self.test_expectations['secondary_get_data_filtered']
        for url in self._get_data_filtered_urls:
            expect.check(self, common.secondary_session.get(url))

    @unittest.skipIf(common.anonymous_session is None, "anonymous authz test requires ermrest_config permission")
    def test_anonymous_data_get_filtered(self):
        expect = self.test_expectations['anonymous_get_data_filtered']
        for url in self._get_data_filtered_urls:
            expect.check(self, common.anonymous_session.get(url))

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
        HiddenPolicy.test_expectations,
        {
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
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(8),
                expect_values({11,12,13,14,31,32,33,34})
            }),
            'anonymous_get_data': Expectation(200, 'application/json', {
                expect_row_count(4),
                expect_values({11,12,13,14})
            }),
            'secondary_put_row_data_primary': Expectation(403),
            'secondary_put_row_data_secondary': Expectation(403),
            'anonymous_put_row_data_primary': Expectation(401),
            'anonymous_put_row_data_secondary': Expectation(401),
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
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(4),
                expect_values({13,23,33,43})
            }),
            'anonymous_get_data': Expectation(200, 'application/json', {
                expect_row_count(4),
                expect_values({13,23,33,43})
            }),
            'secondary_put_row_data_anonymous': Expectation(403),
            'anonymous_put_row_data_anonymous': Expectation(401),
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
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(8),
                expect_values({11,12,13,14,21,22,23,24})
            }),
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
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(12),
                expect_values({11,12,13,14,31,32,33,34,21,23,41,43})
            }),
            'anonymous_get_data': Expectation(200, 'application/json', {
                expect_row_count(7),
                expect_values({11,12,13,14,21,31,41})
            }),
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
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(12),
                expect_values({11,12,13,14,21,22,23,24,31,32,41,42})
            }),
            'secondary_put_row_data_secondary': Expectation([200,204]),
            'secondary_put_row_data_anonymous': Expectation([200,204]),
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
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(8),
                expect_values({11,13,21,23,31,33,41,43})
            }),
            'anonymous_get_data': Expectation(200, 'application/json', {
                expect_row_count(4),
                expect_values({11,21,31,41})
            }),
            'secondary_put_row_data_primary': Expectation(403),
            'secondary_put_row_data_secondary': Expectation(403),
            'secondary_put_row_data_anonymous': Expectation(403),
            'anonymous_put_row_data_primary': Expectation(401),
            'anonymous_put_row_data_secondary': Expectation(401),
            'anonymous_put_row_data_anonymous': Expectation(401),
        }
    )

class CategoryAclOwnerHiddenPolicy (HiddenPolicy):
    bindings = {
        "Data": { "member2": _datacid_ACL_owner_acl },
        "Extension": { "member2": _extid_datacid_ACL_owner_acl },
        "Category": { },
        "Data_Category": { }
    }

    test_expectations = _merge(
        CategoryMemberOwnerHiddenPolicy.test_expectations,
        {
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(8),
                expect_values({11,12,21,22,31,32,41,42})
            }),
            'secondary_put_row_data_secondary': Expectation([200,204]),
            'secondary_put_row_data_anonymous': Expectation([200,204]),
        }
    )

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
            'secondary_get_data': Expectation(200, 'application/json', {
                expect_row_count(12),
                expect_values({11,12,13,21,22,23,31,32,33,41,42,43})
            }),
            'anonymous_get_data': Expectation(200, 'application/json', {
                expect_row_count(8),
                expect_values({11,12,21,22,31,32,41,42})
            }),
            'secondary_put_row_data_primary': Expectation(403),
            'anonymous_put_row_data_primary': Expectation(401),
        }
    )

class ImplicitEnumeration (common.ErmrestTest):
    # Hack: this class steals part of StaticHidden but doesn't want all the data-api tests

    acls = dict(StaticHidden.acls)
    acls.update({
        "Data": {
            # TODO: revisit if we broaden the implicit-enumerate right for dynacls...
            "enumerate": ["*"],
            "select": [],
            "update": [],
        },
        "Category": {
            "select": ["*"],
        }
    })

    col_acls = dict(StaticHidden.col_acls)
    col_acls.update({
        "Data": {
            "id": {
                "select": [],
                "update": [],
            },
            "c_id": {
                "select": [],
                "update": [],
            }
        }
    })

    fkr_acls = {}

    bindings = dict(StaticHidden.bindings)

    col_bindings = {
        "schema/%s/table/Data/column/c_id" % _S: {
            'selectany': {
                "types": ["select"],
                "projection": ["id"],
                "projection_type": "nonnull"
            },
        }
    }
    fkr_bindings = {}

    @classmethod
    def setUpClass(cls):
        # Hack: borrow the policy setup...
        StaticHidden._setUpClass(cls)

    def _get_table_doc(self, tname):
        r = common.anonymous_session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        return r.json()['schemas'][_S]['tables'][tname]

    def test_id_visible(self):
        table = self._get_table_doc('Data')
        self.assertIn('id', [ col['name'] for col in table['column_definitions'] ])

    def test_fkc_visible(self):
        table = self._get_table_doc('Data')
        self.assertIn('c_id', [ col['name'] for col in table['column_definitions'] ])

    def test_key_visible(self):
        table = self._get_table_doc('Data')
        self.assertEqual(len(table['keys']), 1)

    def test_fkr_visible(self):
        table = self._get_table_doc('Data')
        self.assertEqual(len(table['foreign_keys']), 1)

class UnscopedBindings (ImplicitEnumeration):

    col_bindings = {
        "schema/%s/table/Data/column/c_id" % _S: {
            'selectany': {
                "types": ["select"],
                "projection": ["id"],
                "projection_type": "nonnull",
                "scope_acl": [common.primary_client_id],
            },
            "member": False,
        }
    }

    def test_fkc_no_select(self):
        table = self._get_table_doc('Data')
        col = { col['name']: col for col in table['column_definitions'] }['c_id']
        self.assertEqual(col['rights']['select'], False)

    def test_fkr_visible(self):
        table = self._get_table_doc('Data')
        self.assertEqual(len(table['foreign_keys']), 0)

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
        """id,name,ACL,member,c_id,value,values
11,public 1,"{""*""}",*,1,11,{11}
12,public 2,"{""*""}",*,2,12,{12}
13,public 3,"{""*""}",*,3,13,{13}
14,public 4,"{""*""}",*,4,14,{14}
21,restricted group 1,"{""%(secondary)s"",""%(primary)s""}",%(primary)s,1,21,{21}
22,restricted group 2,"{""%(secondary)s"",""%(primary)s""}",%(primary)s,2,22,{22}
23,restricted group 3,"{""%(secondary)s"",""%(primary)s""}",%(primary)s,3,23,{23}
24,restricted group 4,"{""%(secondary)s"",""%(primary)s""}",%(primary)s,4,24,{24}
31,restricted member 1,"{""%(primary)s""}",%(secondary)s,1,31,{31}
32,restricted member 2,"{""%(primary)s""}",%(secondary)s,2,32,{32}
33,restricted member 3,"{""%(primary)s""}",%(secondary)s,3,33,{33}
34,restricted member 4,"{""%(primary)s""}",%(secondary)s,4,34,{34}
41,private 1,"{""%(primary)s""}",%(primary)s,1,41,{41}
42,private 2,"{""%(primary)s""}",%(primary)s,2,42,{42}
43,private 3,"{""%(primary)s""}",%(primary)s,3,43,{43}
44,private 4,"{""%(primary)s""}",%(primary)s,4,44,{44}
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
                        },
                        {
                            "name": "value",
                            "type": {"typename": "int"},
                            "acl_bindings": {
                                "member2": {
                                    "types": ["select", "update"],
                                    "projection": "member",
                                    "projection_type": "acl"
                                }
                            }
                        },
                        {
                            "name": "values",
                            "type": {
                                "is_array": True,
                                "typename": "int[]",
                                "base_type": {
                                    "typename": "int"
                                }
                            },
                            "acl_bindings": {
                                "member2": {
                                    "types": ["select", "update"],
                                    "projection": "member",
                                    "projection_type": "acl"
                                }
                            }
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
