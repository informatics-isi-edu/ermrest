
import unittest
import common

_S = "AuthzStatic"
_S2 = "AuthzStatic2"

from common import Int8, Text, Timestamptz, \
    RID, RCT, RMT, RCB, RMB, RidKey, \
    ModelDoc, SchemaDoc, TableDoc, ColumnDoc, KeyDoc, FkeyDoc

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

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
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

    rights_C = {
        u"owner": False,
        u"create": False,
    }
    rights_S1 = {
        u"insert": False,
        u"update": False,
        u"delete": False,
        u"select": True,
    }
    rights_S2 = {
        u"insert": False,
        u"update": False,
        u"delete": False,
        u"select": True,
    }
    rights_T1 = {
        u"select": True
    }
    rights_T1_id = {}
    rights_T2 = {
        u"select": True
    }
    rights_T3 = {
        u"select": True
    }
    rights_T3_t1id = {}
    rights_T3_fkey = {
        u"insert": False,
        u"update": False,
    }

    def test_rights_catalog(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json()['rights'], self.rights_C)

    def test_rights_S1(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        expected = self.rights_C.copy()
        expected.update(self.rights_S1)
        schemas = r.json()['schemas']
        if expected.get('enumerate') is False:
            self.assertNotIn(_S, schemas)
            return
        expected_S = {
            aclname: right
            for aclname, right in expected.items()
            if aclname in {"owner", "create"}
        }
        self.assertEqual(schemas[_S]['rights'], expected_S)

    def test_rights_S2(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        expected = self.rights_C.copy()
        expected.update(self.rights_S2)
        expected_S = {
            aclname: right
            for aclname, right in expected.items()
            if aclname in {"owner", "create"}
        }
        self.assertEqual(r.json()['schemas'][_S2]['rights'], expected_S)

    def test_rights_T1(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        expected = self.rights_C.copy()
        expected.update(self.rights_S1)
        schemas = r.json()['schemas']
        if expected.get('enumerate') is False:
            self.assertNotIn(_S, schemas)
            return
        expected.update(self.rights_T1)
        tables = schemas[_S]['tables']
        if expected.get('enumerate') is False:
            self.assertNotIn('T1', tables)
            return
        expected_T = {
            aclname: right
            for aclname, right in expected.items()
            if aclname in {"owner", "write", "insert", "update", "delete", "select"}
        }
        self.assertEqual(tables['T1']['rights'], expected_T)

    def test_rights_T3(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        expected = self.rights_C.copy()
        expected.update(self.rights_S2)
        schemas = r.json()['schemas']
        if expected.get('enumerate') is False:
            self.assertNotIn(_S2, schemas)
            return
        expected.update(self.rights_T3)
        tables = schemas[_S2]['tables']
        if expected.get('enumerate') is False:
            self.assertNotIn('T3', tables)
            return
        expected_T = {
            aclname: right
            for aclname, right in expected.items()
            if aclname in {"owner", "write", "insert", "update", "delete", "select"}
        }
        self.assertEqual(tables['T3']['rights'], expected_T)

    def test_rights_T1_id(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        expected = self.rights_C.copy()
        expected.update(self.rights_S1)
        schemas = r.json()['schemas']
        if expected.get('enumerate') is False:
            self.assertNotIn(_S, schemas)
            return
        expected.update(self.rights_T1)
        tables = schemas[_S]['tables']
        if expected.get('enumerate') is False:
            self.assertNotIn('T1', tables)
            return
        expected.update(self.rights_T1_id)
        cols = tables['T1']['column_definitions']
        if expected.get('enumerate') is False:
            self.assertNotEqual(cols[5]['name'], 'id')
            return
        self.assertEqual(cols[5]['name'], 'id')
        expected_c = {
            aclname: right
            for aclname, right in expected.items()
            if aclname in {"select", "update", "insert", "delete"}
        }
        self.assertEqual(cols[5]['rights'], expected_c)

    def test_rights_T3_fkey(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        expected = self.rights_C.copy()
        expected.update(self.rights_S1)
        schemas = r.json()['schemas']
        if expected.get('enumerate') is False:
            self.assertEqual(
                len(schemas[_S2]['tables']['T3']['foreign_keys']),
                0
            )
            return
        expected.update(self.rights_T1)
        tables = schemas[_S]['tables']
        if expected.get('enumerate') is False:
            self.assertEqual(
                len(schemas[_S2]['tables']['T3']['foreign_keys']),
                0
            )
            return
        expected.update(self.rights_T1_id)
        if expected.get('enumerate') is False or self.get_T3_fkey_status == 404:
            self.assertEqual(
                len(schemas[_S2]['tables']['T3']['foreign_keys']),
                0
            )
            return
        # T1.id is visible or we would have exited already!
        # now start over looking at T3 fkey
        expected = self.rights_C.copy()
        expected.update(self.rights_S2)
        expected.update(self.rights_T3)
        expected.update(self.rights_T3_t1id)
        expected.update(self.rights_T3_fkey)
        expected = {
            aclname: right
            for aclname, right in expected.items()
            if aclname in {"insert", "update"}
        }
        self.assertEqual(
            schemas[_S2]['tables']['T3']['foreign_keys'][0]['rights'],
            expected
        )

    @classmethod
    def setUpClass(cls):
        common.primary_session.put('schema/%s/acl' % _S, json=cls.schema).raise_for_status()
        common.primary_session.put('schema/%s/acl' % _S2, json=cls.schema2).raise_for_status()

        common.primary_session.put('schema/%s/table/T1/acl' % _S, json=cls.T1).raise_for_status()
        common.primary_session.put('schema/%s/table/T1/column/id/acl' % _S, json=cls.T1_id).raise_for_status()
        common.primary_session.put('schema/%s/table/T1/column/name/acl' % _S, json=cls.T1_name).raise_for_status()
        common.primary_session.put('schema/%s/table/T1/column/value/acl' % _S, json=cls.T1_value).raise_for_status()

        common.primary_session.put('schema/%s/table/T2/acl' % _S, json=cls.T2).raise_for_status()
        common.primary_session.put('schema/%s/table/T2/column/id/acl' % _S, json=cls.T2_id).raise_for_status()
        common.primary_session.put('schema/%s/table/T2/column/name/acl' % _S, json=cls.T2_name).raise_for_status()
        common.primary_session.put('schema/%s/table/T2/column/value/acl' % _S, json=cls.T2_value).raise_for_status()
        common.primary_session.put('schema/%s/table/T2/column/t1id/acl' % _S, json=cls.T2_t1id).raise_for_status()
        common.primary_session.put('schema/%s/table/T2/foreignkey/t1id/reference/%s:T1/id/acl' % (_S, _S), json=cls.T2_fkey).raise_for_status()

        common.primary_session.put('schema/%s/table/T3/acl' % _S2, json=cls.T3).raise_for_status()
        common.primary_session.put('schema/%s/table/T3/column/id/acl' % _S2, json=cls.T3_id).raise_for_status()
        common.primary_session.put('schema/%s/table/T3/column/name/acl' % _S2, json=cls.T3_name).raise_for_status()
        common.primary_session.put('schema/%s/table/T3/column/t1id/acl' % _S2, json=cls.T3_t1id).raise_for_status()
        common.primary_session.put('schema/%s/table/T3/foreignkey/t1id/reference/%s:T1/id/acl' % (_S2, _S), json=cls.T3_fkey).raise_for_status()

    def setUp(self):
        rdata = list(_data)
        rdata.reverse()
        for path, data in rdata:
            common.primary_session.delete(path)
        for path, data in _data:
            common.primary_session.put(path, json=data).raise_for_status()

    def _hidden_in_model(self, get_collection, key):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        collection = get_collection(r.json())
        self.assertNotIn(key, collection)

    def _json_check(self, response, status):
        self.assertHttp(response, status, 'application/json' if response.status_code in {200, 201} else None)
        return response
        
    get_S_status = 200
    delete_S_status = 403
    def test_S(self):
        self._json_check(self.session.get('schema/%s' % _S), self.get_S_status)
        self._json_check(self.session.delete('schema/%s' % _S), self.delete_S_status)

    get_T1_status = 200
    delete_T1_status = 403
    def test_T1(self):
        self._json_check(self.session.get('schema/%s/table/T1' % _S), self.get_T1_status)
        self._json_check(self.session.delete('schema/%s/table/T1' % _S), self.delete_T1_status)

    get_T1id_status = 200
    delete_T1id_status = 403
    get_T1name_status = 200
    delete_T1name_status = 403
    def test_T1id(self):
        self._json_check(self.session.get('schema/%s/table/T1/column/id' % _S), self.get_T1id_status)
        self._json_check(self.session.delete('schema/%s/table/T1/column/id' % _S), self.delete_T1id_status)

    def test_T1name(self):
        self._json_check(self.session.get('schema/%s/table/T1/column/name' % _S), self.get_T1name_status)
        self._json_check(self.session.delete('schema/%s/table/T1/column/name' % _S), self.delete_T1name_status)

    get_T2_status = 200
    delete_T2_status = 403
    def test_T2(self):
        self._json_check(self.session.get('schema/%s/table/T2' % _S), self.get_T2_status)
        self._json_check(self.session.delete('schema/%s/table/T2' % _S), self.delete_T2_status)

    def test_T3(self):
        self._json_check(self.session.get('schema/%s/table/T3' % _S2), 200)
        self._json_check(self.session.delete('schema/%s/table/T3' % _S2), 403)

    get_T2_fkeys_count = 1
    get_T2_fkeys_status = 200
    get_T2_fkey_status = 200
    get_T2_fkeyref_status = 200
    delete_T2_fkeyref_status = 403
    def test_T2_fkeys(self):
        r = self._json_check(self.session.get('schema/%s/table/T2/foreignkey' % _S), self.get_T2_fkeys_status)
        if r.status_code == 200:
            self.assertEqual(len(r.json()), self.get_T2_fkeys_count)

    def test_T2_fkey(self):
        self._json_check(self.session.get('schema/%s/table/T2/foreignkey/t1id' % _S), self.get_T2_fkey_status)

    def test_T2_fkeyref(self):
        self._json_check(self.session.get('schema/%s/table/T2/foreignkey/t1id/reference/%s:T1' % (_S, _S)), self.get_T2_fkeyref_status)
        self._json_check(self.session.get('schema/%s/table/T2/foreignkey/t1id/reference/%s:T1/id' % (_S, _S)), self.get_T2_fkeyref_status)
        self._json_check(self.session.delete('schema/%s/table/T2/foreignkey/t1id/reference/%s:T1/id' % (_S, _S)), self.delete_T2_fkeyref_status)

    get_T3_fkeys_count = 1
    get_T3_fkeys_status = 200
    get_T3_fkey_status = 200
    get_T3_fkeyref_status = 200
    delete_T3_fkeyref_status = 403
    def test_T3_fkeys(self):
        r = self._json_check(self.session.get('schema/%s/table/T3/foreignkey' % _S2), self.get_T3_fkeys_status)
        if r.status_code == 200:
            self.assertEqual(len(r.json()), self.get_T3_fkeys_count)

    def test_T3_fkey(self):
        self._json_check(self.session.get('schema/%s/table/T3/foreignkey/t1id' % _S2), self.get_T3_fkey_status)

    def test_T3_fkeyref(self):
        self._json_check(self.session.get('schema/%s/table/T3/foreignkey/t1id/reference/%s:T1' % (_S2, _S)), self.get_T3_fkeyref_status)
        self._json_check(self.session.get('schema/%s/table/T3/foreignkey/t1id/reference/%s:T1/id' % (_S2, _S)), self.get_T3_fkeyref_status)
        self._json_check(self.session.delete('schema/%s/table/T3/foreignkey/t1id/reference/%s:T1/id' % (_S2, _S)), self.delete_T3_fkeyref_status)

    get_data_T1_ent_is_in = True
    get_data_T1_ent_status = 200
    put_data_T1_ent_status = 403
    delete_data_T1_ent_status = 403
    def test_get_data_T1_ent(self):
        r = self._json_check(self.session.get('entity/%s:T1' % _S), self.get_data_T1_ent_status)
        if r.status_code == 200:
            self.assertEqual('id' in r.json()[0], self.get_data_T1_ent_is_in)

    def test_put_data_T1_ent(self):
        self._json_check(self.session.put('entity/%s:T1' % _S, json=_data[0][1]), self.put_data_T1_ent_status)

    def test_delete_data_T1_ent(self):
        self._json_check(self.session.delete('entity/%s:T1' % _S), self.delete_data_T1_ent_status)

    get_data_T1_status = 200
    get_data_T1T3_status = 200
    put_data_T1_status = 403
    post_data_T1_status = 403
    delete_data_T1_status = 403
    def test_get_data_T1(self):
        for url in [
                'attribute/%s:T1/name,value' % _S,
                'attributegroup/%s:T1/name;value' % _S,
                'aggregate/%s:T1/c:=cnt(*)' % _S,
        ]:
            self._json_check(self.session.get(url), self.get_data_T1_status)

    def test_get_data_T1T3(self):
        for url in [
                'attribute/A:=%s:T1/(name)=(%s:T3:name)/$A/name,value' % (_S, _S2),
                'attributegroup/A:=%s:T1/(name)=(%s:T3:name)/$A/name;value' % (_S, _S2),
                'aggregate/A:=%s:T1/(name)=(%s:T3:name)/$A/c:=cnt(*)' % (_S, _S2),
        ]:
            self._json_check(self.session.get(url), self.get_data_T1T3_status)

    def test_put_data_T1(self):
        self._json_check(self.session.put('attributegroup/%s:T1/name;value' % _S, json=_data[0][1]), self.put_data_T1_status)

    def test_post_data_T1(self):
        self._json_check(self.session.post('entity/%s:T1' % _S, json=_extra_post_data_1['T1']), self.post_data_T1_status)

    def test_delete_data_T1(self):
        self._json_check(self.session.delete('attribute/%s:T1/name,value' % _S), self.delete_data_T1_status)
        self._json_check(self.session.delete('attribute/A:=%s:T1/(name)=(%s:T3:name)/$A/name,value' % (_S, _S2)), self.delete_data_T1_status)

    get_data_T1_id_status = 200
    get_data_T1T3_id_status = 200
    get_data_T1_id_ctype = 'application/json'
    def test_get_data_T1_id(self):
        for url in [
                'entity/%s:T1/id=1' % _S,
                'attribute/%s:T1/id,name,value' % _S,
                'attributegroup/%s:T1/id,name;value' % _S,
                'aggregate/%s:T1/c:=cnt(id)' % _S,
        ]:
            self._json_check(self.session.get(url), self.get_data_T1_id_status)

    def test_wildcard_query(self):
        self.assertHttp(self.session.get('entity/%s:T1/*::regexp::foo' % _S), self.get_data_T1_status)

    def test_get_data_T1T3_id(self):
        for url in [
                'attribute/A:=%s:T1/%s:T3/id,name' % (_S, _S2),
                'attributegroup/A:=%s:T1/%s:T3/id;name' % (_S, _S2),
                'aggregate/A:=%s:T1/%s:T3/c:=cnt(*)' % (_S, _S2),
        ]:
            self._json_check(self.session.get(url), self.get_data_T1T3_id_status)

    put_data_T1_id_status = 403
    def test_put_data_T1_id(self):
        self._json_check(self.session.put('attributegroup/%s:T1/id,name;value' % _S, json=_data[0][1]), self.put_data_T1_id_status)
        self._json_check(self.session.put('attributegroup/%s:T1/name;id' % _S, json=_data[0][1]), self.put_data_T1_id_status)

    post_data_T1_default_id_status = 403
    def test_post_data_T1_default_id(self):
        self._json_check(self.session.post('entity/%s:T1?defaults=id' % _S, json=_extra_post_data_2['T1']), self.post_data_T1_default_id_status)

    delete_data_T1_id_status = 403
    def test_delete_data_T1_id(self):
        self._json_check(self.session.delete('entity/%s:T1/id=1' % _S), self.delete_data_T1_id_status)
        self._json_check(self.session.delete('attribute/%s:T1/id,name,value' % _S), self.delete_data_T1_id_status)
        self._json_check(self.session.delete('attribute/A:=%s:T1/%s:T2/id,name' % (_S, _S)), self.delete_data_T1_id_status)

    get_data_T2_status = 200
    put_data_T2_status = 403
    delete_data_T2_status = 403
    def test_get_data_T2(self):
        for url in [
                'entity/%s:T2' % _S,
                'attribute/%s:T2/id,name,value' % _S,
                'attributegroup/%s:T2/id,name;value' % _S,
                'aggregate/%s:T2/c:=cnt(*)' % _S,
        ]:
            self._json_check(self.session.get(url), self.get_data_T2_status)

    def test_put_data_T2(self):
        self._json_check(self.session.put('entity/%s:T2' % _S, json=_data[1][1]), self.put_data_T2_status)
        self._json_check(self.session.put('attributegroup/%s:T2/id,name;value' % _S, json=_data[1][1]), self.put_data_T2_status)

    def test_delete_data_T2(self):
        self._json_check(self.session.delete('entity/%s:T2' % _S), self.delete_data_T2_status)
        self._json_check(self.session.delete('attribute/%s:T2/id,name,value' % _S), self.delete_data_T2_status)

    # basic table access
    get_data_T3_status = 200
    update_data_T3_status = 403
    delete_data_T3_status = 403

    # table access involving NULL t1id column writes (bypass fkey restrictions)
    insert_data_T3_t1id_status = 403
    update_data_T3_t1id_status = 403
    write_data_T3_t1id_status = 403

    # table access involving non-NULL fkey writes
    insert_data_T3_fkey_status = 403
    update_data_T3_fkey_status = 403
    write_data_T3_fkey_status = 403

    def test_get_data_T3(self):
        self._json_check(self.session.get('entity/%s:T3' % _S2), self.get_data_T3_status)
        self._json_check(self.session.get('attribute/%s:T3/id,name' % _S2), self.get_data_T3_status)
        self._json_check(self.session.get('attributegroup/%s:T3/id;name' % _S2), self.get_data_T3_status)
        self._json_check(self.session.get('aggregate/%s:T3/c:=cnt(*)' % _S2), self.get_data_T3_status)

    basic_data_T3 = [
        {"id": 8, "name": "t3.8b", "t1id": None},
        {"id": 9, "name": "t3.9b", "t1id": None},
    ]

    fkey_data_T3 = [
        {"id": 8, "name": "t3.8f", "t1id": 1},
        {"id": 9, "name": "t3.9f", "t1id": 2},
    ]

    def test_insert_data_T3(self):
        self.assertHttp(common.primary_session.delete('entity/%s:T3' % _S2), [204, 404])
        self._json_check(self.session.post('entity/%s:T3' % _S2, json=self.basic_data_T3), self.insert_data_T3_t1id_status)
        self.assertHttp(common.primary_session.delete('entity/%s:T3' % _S2), [204, 404])
        self._json_check(self.session.post('entity/%s:T3' % _S2, json=self.fkey_data_T3), self.insert_data_T3_fkey_status)

    def test_write_data_T3(self):
        self.assertHttp(common.primary_session.delete('entity/%s:T3' % _S2), [204, 404])
        self._json_check(self.session.put('entity/%s:T3' % _S2, json=self.basic_data_T3), self.write_data_T3_t1id_status)
        self.assertHttp(common.primary_session.delete('entity/%s:T3' % _S2), [204, 404])
        self._json_check(self.session.put('entity/%s:T3' % _S2, json=self.fkey_data_T3), self.write_data_T3_fkey_status)

    def test_update_data_T3(self):
        self._json_check(self.session.put('attributegroup/%s:T3/id;name' % _S2, json=self.basic_data_T3), self.update_data_T3_status)
        self._json_check(self.session.put('attributegroup/%s:T3/id;t1id' % _S2, json=self.basic_data_T3), self.update_data_T3_t1id_status)
        self._json_check(self.session.put('attributegroup/%s:T3/id;t1id' % _S2, json=self.fkey_data_T3), self.update_data_T3_fkey_status)
        self._json_check(self.session.delete('attribute/%s:T3/value' % _S2), self.update_data_T3_status)
        self._json_check(self.session.delete('attribute/%s:T3/t1id' % _S2), self.update_data_T3_t1id_status)

    def test_delete_data_T3(self):
        r = self._json_check(self.session.delete('entity/%s:T3' % _S2), self.delete_data_T3_status)
        if r.status_code == 204:
            # repair the damage we just did to class-wide state
            common.primary_session.post('entity/%s:T3' % _S2, json=_data[2][1]).raise_for_status()

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzHideT1id (Authz):
    T1_id = {
        'select': [],
        'enumerate': []
    }

    rights_T1_id = {
        u'enumerate': False
    }

    def test_hidden_in_model(self):
        r = self.session.get('schema')
        self.assertHttp(r, 200, 'application/json')
        self.assertNotIn(
            'id',
            [ c['name'] for c in r.json()['schemas'][_S]['tables']['T1']['column_definitions'] ]
        )
        self.assertNotIn(
            ('id',),
            {
                tuple(sorted(keydoc['unique_columns']))
                for keydoc in r.json()['schemas'][_S]['tables']['T1'].get('keys', [])
            }
        )
        self._hidden_in_model(lambda schema: schema['schemas'][_S]['tables']['T2'].get('foreign_keys', []), 0)
        self._hidden_in_model(lambda schema: schema['schemas'][_S2]['tables']['T3'].get('foreign_keys', []), 0)

    get_T1id_status = 404
    delete_T1id_status = 404

    get_T2_fkeys_count = 0
    get_T2_fkey_status = 404
    get_T2_fkeyref_status = 409
    delete_T2_fkeyref_status = 409

    get_T3_fkeys_count = 0
    get_T3_fkey_status = 404
    get_T3_fkeyref_status = 409
    delete_T3_fkeyref_status = 409

    get_data_T1_ent_is_in = False

    get_data_T1_id_status = 409
    get_data_T1T3_id_status = 409
    put_data_T1_id_status = 409
    post_data_T1_default_id_status = 409
    delete_data_T1_id_status = 409

def _merge(d1, d2):
    d1 = dict(d1)
    d1.update(d2)
    return d1

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzCreate (common.ErmrestTest):
    session = common.secondary_session

    C = _merge(
        common.catalog_acls,
        {
            "create": [common.secondary_client_id],
        }
    )

    @classmethod
    def setUpClass(cls):
        common.primary_session.put('acl', json=cls.C).raise_for_status()
        common.primary_session.post('schema', json=[SchemaDoc("S4")]).raise_for_status()

    @classmethod
    def tearDownClass(cls):
        common.primary_session.put('acl', json=common.catalog_acls).raise_for_status()
        common.primary_session.delete('schema/S4').raise_for_status()

    rights_C = {
        "owner": False,
        "create": True,
    }
    rights_TC = {
        "owner": True,
        "insert": True,
        "update": True,
        "delete": True,
        "select": True,
    }

    create_S3_status = 201
    delete_S3_status = 204
    def test_S3_create_schema(self):
        self.assertHttp(
            self.session.post('schema/S3'),
            self.create_S3_status,
        )
        self.assertHttp(
            self.session.delete('schema/S3'),
            self.delete_S3_status,
        )

    def test_S3_create_fromjson(self):
        self.assertHttp(
            self.session.post('schema', json=[{"schema_name": "S3"}]),
            self.create_S3_status,
        )
        self.assertHttp(
            self.session.delete('schema/S3'),
            self.delete_S3_status,
        )

    _table_doc = TableDoc("TC", [ RID, RCT, RMT, RCB, RMB ], [ RidKey ])

    create_TC_status = 201
    delete_TC_status = 204
    def test_TC(self):
        self.assertHttp(
            self.session.post('schema/S4/table', json=self._table_doc),
            self.create_TC_status,
        )

        if self.create_TC_status == 201:
            # check table rights only if we could create TC
            r = self.session.get('schema/S4/table/TC')
            self.assertHttp(r, 200, 'application/json')
            rights = r.json()['rights']
            self.assertEqual(rights, self.rights_TC)

        self.assertHttp(
            self.session.delete('schema/S4/table/TC'),
            self.delete_TC_status,
        )

class AuthzCreateDisallowed (AuthzCreate):
    C = common.catalog_acls

    rights_C = _merge(
        AuthzCreate.rights_C,
        {
            "create": False
        }
    )
    rights_TC = None

    create_S3_status = 403
    delete_S3_status = 404

    create_TC_status = 403
    delete_TC_status = 404

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT1Insert (Authz):
    T1 = {
        "insert": [common.secondary_client_id],
        "select": ["*"],
    }
    T1_id = {
        "insert": [],
        "select": ["*"],
    }

    post_data_T1_status = 403
    post_data_T1_default_id_status = 200

    rights_T1 = {
        "select": True,
        "insert": True,
    }
    rights_T1_id = {
        "select": True,
        "insert": False,
    }

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT1InsertId (AuthzT1Insert):
    T1_id = {
        "insert": [common.secondary_client_id],
        "select": ["*"],
    }

    post_data_T1_status = 200

    rights_T1_id = {
        "select": True,
        "insert": True,
    }

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

    rights_T1 = {
        u'select': False,
        u'enumerate': False,
    }

    def test_hidden_in_model(self):
        self._hidden_in_model(lambda schema: schema['schemas'][_S]['tables'], "T1")
        self._hidden_in_model(lambda schema: schema['schemas'][_S]['tables']['T2'].get('foreign_keys', []), 0)

    get_T1_status = 404
    delete_T1_status = 404

    get_T1id_status = 409
    delete_T1id_status = 409

    get_T1name_status = 409
    delete_T1name_status = 409

    get_data_T1_ent_status = 409
    put_data_T1_ent_status = 409
    delete_data_T1_ent_status = 409

    get_data_T1_status = 409
    get_data_T1T3_status = 409
    put_data_T1_status = 409
    post_data_T1_status = 409
    delete_data_T1_status = 409

    post_data_T1_default_id_status = 409

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

    rights_S1 = {
        u'select': False,
        u'enumerate': False,
    }

    def test_hidden_in_model(self):
        self._hidden_in_model(lambda schema: schema['schemas'], _S)

    get_S_status = 404
    delete_S_status = 404

    get_T1_status = 409
    delete_T1_status = 409

    get_T2_status = 409
    delete_T2_status = 409

    get_T2_fkeys_status = 409
    get_T2_fkey_status = 409

    get_data_T2_status = 409
    put_data_T2_status = 409
    delete_data_T2_status = 409

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3InsertSelectFkeyInsert (Authz):
    T3 = {
        "insert": [common.secondary_client_id],
        "select": ["*"],
    }
    T3_fkey = {
        "insert": ["*"],
        "update": []
    }

    rights_T3 = {
        u"insert": True
    }
    rights_T3_fkey = {
        u"insert": True,
        u"update": False
    }

    insert_data_T3_t1id_status = 200
    insert_data_T3_fkey_status = 200

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3InsertSelectFkeyUpdateOnly (AuthzT3InsertSelectFkeyInsert):
    T3_fkey = {
        "insert": [],
        "update": ["*"]
    }

    rights_T3_fkey = {
        u"insert": False,
        u"update": False,
    }

    insert_data_T3_fkey_status = 403

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3InsertOnly (AuthzT3InsertSelectFkeyInsert):
    T3 = {
        "insert": [common.secondary_client_id],
        "select": []
    }

    rights_T3 = {
        "insert": True,
        "select": False
    }

    get_data_T3_status = 403
    get_data_T1T3_status = 403
    get_data_T1T3_id_status = 409
    get_T3_fkey_status = 404
    get_T3_fkeys_count = 0
    get_T3_fkeyref_status = 409
    delete_T3_fkeyref_status = 409

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3Update (Authz):
    T3 = {
        "update": [common.secondary_client_id]
    }

    rights_T3 = {
        "select": True,
        "update": True,
    }
    rights_T3_fkey = {
        u"update": True
    }

    update_data_T3_status = [200,204]
    update_data_T3_t1id_status = [200,204]
    update_data_T3_fkey_status = 200

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3Write (AuthzT3Update):
    T3 = {
        "write": [common.secondary_client_id]
    }

    rights_T3 = {
        "select": True,
        "update": True,
        "insert": True,
        "delete": True,
    }
    rights_T3_fkey = {
        u"insert": True,
        u"update": True,
    }

    delete_data_T3_status = 204
    insert_data_T3_t1id_status = 200
    insert_data_T3_fkey_status = 200
    write_data_T3_t1id_status = 200
    write_data_T3_fkey_status = 200

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3WriteFkeyInsert (AuthzT3Write):
    T3_fkey = {
        "insert": ["*"],
        "update": [],
        "write": []
    }

    rights_T3_fkey = {
        u"insert": True,
        u"update": False
    }

    write_data_T3_fkey_status = 403
    update_data_T3_fkey_status = 403

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3WriteFkeyUpdate (AuthzT3Write):
    T3_fkey = {
        "insert": [],
        "update": ["*"],
        "write": []
    }

    rights_T3_fkey = {
        u"insert": False,
        u"update": True
    }

    write_data_T3_fkey_status = 403
    insert_data_T3_fkey_status = 403

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3WriteCt1idInsert (AuthzT3Write):
    T3 = {
        "write": [common.secondary_client_id]
    }
    T3_t1id = {
        "write": [],
        "update": [],
        "insert": [common.secondary_client_id],
    }

    rights_T3 = {
        "select": True,
        "update": True,
        "insert": True,
        "delete": True,
    }

    rights_T3_fkey = {
        u"insert": True,
        u"update": False,
    }

    update_data_T3_t1id_status = 403
    write_data_T3_t1id_status = 403
    update_data_T3_fkey_status = 403
    write_data_T3_fkey_status = 403

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3WriteCt1idUpdate (AuthzT3Write):
    T3 = {
        "write": [common.secondary_client_id]
    }
    T3_t1id = {
        "write": [],
        "update": [common.secondary_client_id],
        "insert": [],
    }

    rights_T3 = {
        "select": True,
        "update": True,
        "insert": True,
        "delete": True,
    }

    rights_T3_fkey = {
        u"insert": False,
        u"update": True,
    }

    insert_data_T3_t1id_status = 403
    write_data_T3_t1id_status = 403
    insert_data_T3_fkey_status = 403
    write_data_T3_fkey_status = 403

@unittest.skipIf(common.secondary_session is None, "Authz test requires TEST_COOKIES2")
class AuthzT3WriteCt1idWrite (AuthzT3Write):
    T3 = {
        "write": [common.secondary_client_id]
    }
    T3_t1id = {
        "write": [common.secondary_client_id],
        "update": [],
        "insert": [],
    }

    rights_T3 = {
        "select": True,
        "update": True,
        "insert": True,
        "delete": True,
    }
    rights_T3_fkey = {
        u"insert": True,
        u"update": True,
    }

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

_extra_post_data_1 = {
    "T1": [
        {"id": 100, "name": "t1.100", "value": "foo"},
        {"id": 200, "name": "t1.200", "value": "bar"},
        {"id": 300, "name": "t1.300", "value": "baz"},
    ],
}

_extra_post_data_2 = {
    "T1": [
        {"name": "t1.1.null", "value": "foo"},
        {"name": "t1.2.null", "value": "bar"},
        {"name": "t1.3.null", "value": "baz"},
    ],
}

_defs = ModelDoc(
    [
        SchemaDoc(
            _S,
            [
                TableDoc(
                    "T1",
                    [
                        RID, RCT, RMT, RCB, RMB,
                        ColumnDoc("id", Int8, nullok=True),
                        ColumnDoc("name", Text, nullok=False),
                        ColumnDoc("value", Text),
                    ],
                    [ RidKey, KeyDoc(["id"]), KeyDoc(["name"]) ],
                ),
                TableDoc(
                    "T2",
                    [
                        RID, RCT, RMT, RCB, RMB,
                        ColumnDoc("id", Int8),
                        ColumnDoc("name", Text, nullok=False),
                        ColumnDoc("value", Text),
                        ColumnDoc("t1id", Int8),
                    ],
                    [ RidKey, KeyDoc(["id"]), KeyDoc(["name"]) ],
                    [
                        FkeyDoc(_S, "T2", ["t1id"], _S, "T1", ["id"]),
                    ]
                )
            ]
        ),
        SchemaDoc(
            _S2,
            [
                TableDoc(
                    "T3",
                    [
                        RID, RCT, RMT, RCB, RMB,
                        ColumnDoc("id", Int8),
                        ColumnDoc("name", Text, nullok=False),
                        ColumnDoc("value", Text),
                        ColumnDoc("t1id", Int8),
                    ],
                    [ RidKey, KeyDoc(["id"]), KeyDoc(["name"]) ],
                    [
                        FkeyDoc(_S2, "T3", ["t1id"], _S, "T1", ["id"]),
                    ]
                )
            ]
        )
    ]
)

if __name__ == '__main__':
    unittest.main(verbosity=2)
