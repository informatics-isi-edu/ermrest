
import sys
import json
import unittest
import common
import basics
from common import urlquote

_S = 'data'
_T0 = basics._T0
_T1 = basics._T1
_T2 = basics._T2
_T2b = basics._T2b
_Tc1 = basics._Tc1
_Tc2 = basics._Tc2
_defs = basics.defs(_S)
_table_defs = _defs['schemas'][_S]['tables']

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.put('schema/public/table/ERMrest_RID_Lease/acl/insert', json=[common.secondary_client_id])
        common.primary_session.post('schema', json=_defs).raise_for_status()
        common.primary_session.put('schema/%s/table/%s/acl/insert' % (_S, _T1), json=[common.secondary_client_id])

class Minimal (common.ErmrestTest):
    table = _T0
    _initial = [
        {"value": "foo1"},
        {"value": "foo2"}
    ]

    def test_data_0_post(self):
        self.assertHttp(self.session.post("entity/%s:%s?defaults=RID" % (_S, self.table), json=self._initial), 200)

class BasicKey (common.ErmrestTest):
    table = _T1

    _initial = [
        {"id": 1, "name": "foo", "a_int4": [0, 1], "a_text": ["one", "foo", "BAR", "BAZ"]},
        {"id": 2, "name": "bar", "a_int4": [0, 2], "a_text": ["two", "FOO", "bar", "BAZ"]},
        {"id": 3, "name": "baz", "a_int4": [0, 3], "a_text": ["three", "FOO", "BAR", "baz"]},
        {"id": 4, "name": "unreferenced"},
    ]

    _upsert = [
        {"id": 4, "name": "unreferenced2"},
        {"id": 5},
    ]

    _badnulls = [
        [ {"id": None, "name": "unreferenced3"} ],
        [ {"name": "unreferenced3"} ],
        [ {} ],
    ]

    _set_RID = [
        {"RID": "AAAAA2", "id": 162, "name": "custom RID AAAAA2"},
        {"RID": "AAAAA4", "id": 164, "name": "custom RID AAAAA4"},
        {"RID": "AAAAA6", "id": 166, "name": "custom RID AAAAA6"},
    ]

    def test_data_0_post(self):
        self.assertHttp(self.session.post("entity/%s:%s" % (_S, self.table), json=self._initial), 200)

    def test_data_1_conflict(self):
        self.assertHttp(self.session.post("entity/%s:%s" % (_S, self.table), json=self._initial), 409)
    
    def test_data_2_reput(self):
        self.assertHttp(self.session.put("entity/%s:%s" % (_S, self.table), json=self._initial), 200)

    def test_data_3_upsert(self):
        self.assertHttp(self.session.put("entity/%s:%s" % (_S, self.table), json=self._upsert), 200)

    def test_data_4_badnull(self):
        for x in self._badnulls:
            self.assertHttp(self.session.put("entity/%s:%s" % (_S, self.table), json=x), 409)

    def test_data_5_set_RID(self):
        self.assertHttp(self.session.post("entity/%s:%s?nondefaults=RID" % (_S, self.table), json=self._set_RID), 200)
        r = self.session.get("attributegroup/%s:%s/name::regexp::custom/RID;id,name@sort(RID)" % (_S, self.table))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json(), self._set_RID)

    def test_data_5_set_RID_allocated(self):
        r = common.secondary_session.post("entity/public:ERMrest_RID_Lease", json=[ {}, ])
        self.assertHttp(r, (200, 201), 'application/json')
        lease = r.json()[0]["RID"]
        r = common.secondary_session.post(
            "entity/%s:%s?nondefaults=RID" % (_S, self.table),
            json=[ {"RID": lease, "id": 1162, "name": "allocated RID %s" % (lease,)} ]
        )
        self.assertHttp(r, (200, 201), 'application/json')
        self.assertEqual(r.json()[0]["RID"], lease)

    def test_data_5_set_RID_forbidden(self):
        r = common.secondary_session.post(
            "entity/%s:%s?nondefaults=RID" % (_S, self.table),
            json=[ {"RID": 'AAAAZ4', "id": 1164, "name": "allocated RID AAAZ4"} ]
        )
        self.assertHttp(r, 403)

    def test_data_6_set_RMT_forbidden(self):
        self.assertHttp(self.session.post("entity/%s:%s?nondefaults=RMT" % (_S, self.table), json=[]), 403)

    def test_data_7_quantlist_predicates(self):
        def test_quant(filt, ids):
            r = self.session.get("aggregate/%s:%s/%s/ids:=array_d(id)" % (_S, self.table, filt))
            self.assertHttp(r, 200, 'application/json')
            got = r.json()[0]["ids"]
            if got is None:
                got = set()
            else:
                got = set(got)
            self.assertEqual(got, ids)

        #r = self.session.get("entity/%s:%s" % (_S, self.table))
        #sys.stderr.write(json.dumps(r.json(), indent=2))

        test_quant("id=any(1,2,3,4)", {1,2,3,4})
        test_quant("id=all(1,2,3,4)", set())
        test_quant("a_int4=any(0,1)", {1,2,3})
        test_quant("a_int4=all(0,1)", {1,})
        test_quant("a_text=any(foo,bar)", {1,2})
        test_quant("a_text=all(foo,bar)", set())
        test_quant("name::regexp::any(oo,bar)", {1,2})
        test_quant("a_text::ciregexp::any(foo,bar)", {1,2,3})
        test_quant("*::ciregexp::any(foo,bar)", {1,2,3})

    def test_download(self):
        r = self.session.get('entity/%s:%s?download=%s' % (_S, self.table, self.table))
        self.assertHttp(r, 200)
        self.assertRegex(
            r.headers.get('content-disposition'),
            "attachment; filename[*]=UTF-8''%s.*" % self.table
        )
        
class CompositeKey (BasicKey):
    table = _Tc1

    _initial = [
        {"id": 1, "last_update": "2010-01-01", "name": "Foo", "site": 1},
        {"id": 1, "last_update": "2010-01-02", "name": "Foo", "site": 2, "a_int4": [0, 1], "a_text": ["one", "foo", "BAR", "BAZ"]},
        {"id": 2, "last_update": "2010-01-03", "name": "Foo", "site": 1},
        {"id": 2, "last_update": "2010-01-04", "name": "Foo", "site": 2, "a_int4": [0, 2], "a_text": ["two", "FOO", "bar", "BAZ"]},
    ]

    _upsert = [
        {"id": 1, "last_update": "2010-01-01", "name": "Foo1", "site": 1},
        {"id": 2, "last_update": "2010-01-04", "name": "Foo1", "site": 1},
        {"id": 3, "site": 2, "a_int4": [0, 3], "a_text": ["three", "FOO", "BAR", "baz", "BAZ"]},
        {"id": 4, "site": 2},
    ]

    _badnulls = [
        [ {"id": 1, "last_update": "2010-01-01", "name": "FooN", "site": None} ],
        [ {"id": 1, "last_update": "2010-01-01", "name": "FooN"} ],
        [ {"id": None, "last_update": "2010-01-01", "name": "FooN", "site": 1} ],
        [ {"last_update": "2010-01-01", "name": "FooN", "site": 1} ],
    ]

    # these inherited test won't work with this table, so prune it
    def test_data_5_set_RID(self): pass
    def test_data_5_set_RID_allocated(self): pass
    def test_data_5_set_RID_forbidden(self): pass

class DataLoad (common.ErmrestTest):
    table = _T2b

    data1 = """id,name,level1_id1,level1_id2
1,foo 1,1,1
2,foo 2,1,2
3,bar 1,2,3
4,baz 1,3,1
"""
    data2 = """old,new
foo 1,foo 1B
foo 2,foo 2B
bar 1,bar 1B
"""
    data3 = [
        {"old": "foo 1B", "new": "foo 1C"},
        {"old": "foo 2B", "new": "foo 2C"},
        {"old": "bar 1B", "new": "bar 1B"}
    ]
    
    def test_1_post(self):
        self.assertHttp(
            self.session.post(
                'entity/%s:%s' % (_S, self.table),
                data=self.data1,
                headers={'content-type': 'text/csv'}
            ),
            200
        )

    def test_2_put_aliased_csv(self):
        self.assertHttp(
            self.session.put(
                'attributegroup/%s:%s/old:=name;new:=name' % (_S, self.table),
                data=self.data2,
                headers={'content-type': 'text/csv'}
            ),
            200
        )

    def test_3_put_aliased_json(self):
        self.assertHttp(
            self.session.put(
                'attributegroup/%s:%s/old:=name;new:=name' % (_S, self.table),
                json=self.data3
            ),
            200
        )

class ForeignKey (common.ErmrestTest):
    table = _T2
    data = [
        {"id": 1, "name": "foo 1", "level1_id": 1},
        {"id": 2, "name": "foo 2", "level1_id": 1},
        {"id": 3, "name": "bar 1", "level1_id": 2},
        {"id": 4, "name": "baz 1", "level1_id": 3},
        {"id": 5, "name": "disconnected", "level1_id": None},
    ]

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
        self.assertHttp(self.session.get(self._fkey_url(5)), 409)

    def test_2_recreate_fkey(self):
        self.assertHttp(self.session.post(self._fkey_url(1), json=_table_defs[self.table]['foreign_keys'][0]), 201)
        self.assertHttp(self.session.get(self._fkey_url(5)), 200, 'application/json')

    def test_3_load(self):
        self.assertHttp(self.session.post(self._entity_url(), json=self.data), 200)

class ForeignKeyComposite (ForeignKey):
    table = _Tc2
    data = [
        row
        for row in CompositeKey._initial
    ]

class ZTextFacet (common.ErmrestTest):
    # spelled this to run it very late in the sequence...
    def test_textfacet(self):
        for pattern in ['foo', 'bar', 'foo.*']:
            self.assertHttp(self.session.get('textfacet/%s' % urlquote(pattern)), 200)

class OnconflictSkip (common.ErmrestTest):
    @classmethod
    def setUpClass(cls):
        common.primary_session.post(
            'schema/public/table/ERMrest_Client/key',
            json={"unique_columns": ["ID", "Full_Name", "Display_Name"]}
        ).raise_for_status()

    @classmethod
    def tearDownClass(cls):
        common.primary_session.delete(
            'schema/public/table/ERMrest_Client/key/ID,Full_Name,Display_Name'
        ).raise_for_status()

    def test_onconflict_skip_basic(self):
        existing = self.session.get('entity/public:ERMrest_Client').json()
        self.assertHttp(self.session.post('entity/public:ERMrest_Client?onconflict=skip', json=existing), 200)

    def test_onconflict_skip_multikey(self):
        existing = self.session.get('entity/public:ERMrest_Client').json()
        existing[0]["Full_Name"] = "Different Value"
        self.assertHttp(self.session.post('entity/public:ERMrest_Client?onconflict=skip', json=existing), 200)

if __name__ == '__main__':
    unittest.main(verbosity=2)
