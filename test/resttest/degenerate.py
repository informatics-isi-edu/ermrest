
# -*- coding: UTF-8 -*-

import unittest
import common
import basics
from common import urlquote

from common import Int4, Int8, Text, Int4Array, TextArray, Timestamptz, \
    Ermrest_rid, Ermrest_rct, Ermrest_rmt, Ermrest_rcb, Ermrest_rmb, \
    RID, RCT, RMT, RCB, RMB, RidKey, \
    ModelDoc, SchemaDoc, TableDoc, ColumnDoc, KeyDoc, FkeyDoc

class LongIdentifiers (common.ErmrestTest):
    identifier = u'ǝɯɐuǝɯɐuǝɯǝɯɐuǝɯɐuǝɯɐuǝɯɐuǝɯɐuǝɯɐuɐu'
    utf8 = None
    urlcoded = None

    def sdef(self, sname, tname, cname, kname, fkname):
        return ModelDoc(
            [
                SchemaDoc(
                    sname,
                    [
                        TableDoc(
                            tname,
                            [
                                RID, RCT, RMT, RCB, RMB,
                                ColumnDoc("id", Text, nullok=False),
                                ColumnDoc(cname, Text),
                            ],
                            [ RidKey, KeyDoc(["id"]), KeyDoc([cname], names=[[sname, kname]]) ],
                            [
                                FkeyDoc(sname, tname, [cname], sname, tname, ["id"], names=[[sname, fkname]])
                            ]
                        )
                    ]
                )
            ]
        )

    @classmethod
    def setUpClass(cls):
        cls.utf8 = cls.identifier.encode('utf8')
        assert len(cls.utf8) == 63
        cls.urlcoded = urlquote(cls.utf8)

    def setUp(self):
        pass

    def test_1_schemaname(self):
        self.assertHttp(self.session.post('schema/x%s' % self.urlcoded), 400)
        self.assertHttp(self.session.post('schema/%s' % self.urlcoded), 201)
        self.assertHttp(self.session.delete('schema/%s' % self.urlcoded), 204)

    def test_2_schemaname(self):
        self.assertHttp(self.session.post('schema', json=self.sdef('x' + self.utf8, 'LIT2', 'LIT2', 'LIT2K', 'LIT2FK')), 400)
        self.assertHttp(self.session.post('schema', json=self.sdef(self.utf8, 'LIT2', 'LIT2', 'LIT2K', 'LIT2FK')), 201)

    def test_3_tablename(self):
        self.assertHttp(self.session.post('schema', json=self.sdef('LIT3', 'x' + self.utf8, 'LIT3', 'LIT3K', 'LIT3FK')), 400)
        self.assertHttp(self.session.post('schema', json=self.sdef('LIT3', self.utf8, 'LIT3', 'LIT3K', 'LIT3FK')), 201)

    def test_4_columnname(self):
        self.assertHttp(self.session.post('schema', json=self.sdef('LIT4', 'LIT4', 'x' + self.utf8, 'LIT4K', 'LIT4FK')), 400)
        self.assertHttp(self.session.post('schema', json=self.sdef('LIT4', 'LIT4', self.utf8, 'LIT4K', 'LIT4FK')), 201)

    def test_5_keyname(self):
        self.assertHttp(self.session.post('schema', json=self.sdef('LIT5', 'LIT5', 'LIT5', 'x' + self.utf8, 'LIT5FK')), 400)
        self.assertHttp(self.session.post('schema', json=self.sdef('LIT5', 'LIT5', 'LIT5', self.utf8, 'LIT5FK')), 201)

    def test_6_fkeyname(self):
        self.assertHttp(self.session.post('schema', json=self.sdef('LIT6', 'LIT6', 'LIT6', 'LIT6K', 'x' + self.utf8)), 400)
        self.assertHttp(self.session.post('schema', json=self.sdef('LIT6', 'LIT6', 'LIT6', 'LIT6K', self.utf8)), 201)

class ConstraintCollision (common.ErmrestTest):
    _S = 'CollisionSchema'
    _T1 = 'Base'
    _T2 = 'Refers'

    def defs(self, extra_keys=[], extra_fkeys=[]):
        return [
            SchemaDoc(self._S),
            TableDoc(
                self._T1,
                [ RID, RCT, RMT, RCB, RMB ],
                [ KeyDoc(['RID'], names=[[self._S, 'key1']]) ] + extra_keys,
                schema_name=self._S
            ),
            TableDoc(
                self._T2,
                [ RID, RCT, RMT, RCB, RMB, ColumnDoc('t1_rid', Text) ],
                [ RidKey ],
                [ FkeyDoc(self._S, self._T2, ['t1_rid'], self._S, self._T1, ['RID'], names=[[self._S, 'fkey1']]) ] + extra_fkeys,
                schema_name=self._S
            )
        ]

    _key_collide = KeyDoc(['RID'], names=[[_S, 'key2']])
    _fkey_collide = FkeyDoc(_S, _T2, ['t1_rid'], _S, _T1, ['RID'], names=[[_S, 'fkey2']])

    def test_1_redundant_keys(self):
        defs = self.defs([self._key_collide], [])
        self.assertHttp(self.session.post('schema', json=defs), 409)

    def test_2_redundant_fkeys(self):
        defs = self.defs([], [self._fkey_collide])
        self.assertHttp(self.session.post('schema', json=defs), 409)

    def test_3_setup(self):
        self.assertHttp(self.session.post('schema', json=self.defs()), 201)

    def test_4_keys_collide(self):
        self.assertHttp(self.session.post('schema/%s/table/%s/key/' % (self._S, self._T1), json=self._key_collide), 409)

    def test_5_fkeys_collide(self):
        self.assertHttp(self.session.post('schema/%s/table/%s/foreignkey/' % (self._S, self._T2), json=self._fkey_collide), 409)

class LacksSystemColumns (common.ErmrestTest):
    _S = 'LacksSystem'
    _T1 = 'Base'

    def defs(self):
        return [
            SchemaDoc(self._S),
            TableDoc(
                self._T1,
                [ RID, RCT, RMT, RCB, RMB ],
                [ RidKey ],
                schema_name=self._S
            ),
        ]

    def _coldelete_test(self, index):
        defs = self.defs()
        defs[1]["column_definitions"].__delitem__(index)
        self.assertHttp(self.session.post('schema', json=defs), 400)

    def test_01_no_rmb(self): self._coldelete_test(4)

    def test_02_no_rcb(self): self._coldelete_test(3)

    def test_03_no_rmt(self): self._coldelete_test(2)

    def test_04_no_rct(self): self._coldelete_test(1)

    def test_05_no_rid(self):
        defs = self.defs()
        defs[1]["column_definitions"].__delitem__(0)
        defs[1]["keys"].__delitem__(0)
        self.assertHttp(self.session.post('schema', json=defs), 400)

    def test_06_no_ridkey(self):
        defs = self.defs()
        defs[1]["keys"].__delitem__(0)
        self.assertHttp(self.session.post('schema', json=defs), 400)

    def test_07_rid_nullok(self):
        defs = self.defs()
        defs[1]["column_definitions"][0] = ColumnDoc("RID", Ermrest_rid)
        self.assertHttp(self.session.post('schema', json=defs), 400)

    def _wrongtype_test(self, index, wtype):
        defs = self.defs()
        c = defs[1]["column_definitions"][index]
        defs[1]["column_definitions"][index] = ColumnDoc(c["name"], wtype, c.get("nullok", True))
        self.assertHttp(self.session.post('schema', json=defs), 400)

    def test_08_rid_wrongtype(self): self._wrongtype_test(0, Int8)

    def test_09_rid_wrongtype(self): self._wrongtype_test(1, Timestamptz)

    def test_10_rid_wrongtype(self): self._wrongtype_test(2, Timestamptz)

    def test_11_rid_wrongtype(self): self._wrongtype_test(3, Text)

    def test_12_rid_wrongtype(self): self._wrongtype_test(4, Text)

class KeysOnly (common.ErmrestTest):
    _schema = 'keysonly_schema'
    _table = 'keysonly_table'
    _entity_url = 'entity/%s:%s' % (_schema, _table)
    
    _table_doc = TableDoc(
        _table,
        [
            RID, RCT, RMT, RCB, RMB,
            ColumnDoc("key1", Int8, nullok=False),
            ColumnDoc("key2", Text),
        ],
        [ RidKey, KeyDoc(["key1"]), KeyDoc(["key2"]), KeyDoc(["RID","RCT","RMT","RCB","RMB"]) ],
        schema_name=_schema,
    )

    _test_data="""key1,key2
1,name1
2,name2
3,name3
"""
        
    def test_1_create(self):
        self.assertHttp(self.session.post('schema/%s' % self._schema), 201)
        self.assertHttp(self.session.post('schema/%s/table' % self._schema, json=self._table_doc), 201)

    def test_2_load(self):
        self.assertHttp(
            self.session.post(self._entity_url, data=self._test_data, headers={"content-type": "text/csv"}),
            200
        )
        
    def test_3_conflict(self):
        self.assertHttp(
            self.session.post(self._entity_url, data=self._test_data, headers={"content-type": "text/csv"}),
            409
        )
        test_data="""key1,key2
1,name2
"""
        self.assertHttp(
            self.session.post(self._entity_url, data=test_data, headers={"content-type": "text/csv"}),
            409
        )
        
    def test_4_idempotent(self):
        self.assertHttp(
            self.session.put(self._entity_url, data=self._test_data, headers={"content-type": "text/csv"}),
            200
        )

    def test_5_alldefault(self):
        self.assertHttp(
            self.session.post(self._entity_url + "?defaults=RID,RCT,RMT,RCB,RMB,key1,key2", data=self._test_data, headers={"content-type": "text/csv"}),
            409
        )

class Unicode (common.ErmrestTest):
    sname = u"ɐɯǝɥɔs%"
    tname = u"ǝlqɐʇ%"
    cname = u"ǝɯɐu%"

    sname_url = urlquote(sname.encode('utf8'))
    tname_url = urlquote(tname.encode('utf8'))
    cname_url = urlquote(cname.encode('utf8'))
    
    defs = [
        SchemaDoc(sname),
        TableDoc(
            tname,
            [
                RID, RCT, RMT, RCB, RMB,
                ColumnDoc("id", Int8, nullok=False),
                ColumnDoc(cname, Text),
            ],
            [ RidKey, KeyDoc(["id"]) ],
            schema_name=sname
        )
    ]

    def test_1_create(self):
        self.assertHttp(self.session.post('schema', json=self.defs), 201)

    def test_2_introspect(self):
        self.assertHttp(
            self.session.get(
                'schema/%s' % self.sname_url
            ),
            200,
            'application/json'
        )
        self.assertHttp(
            self.session.get(
                'schema/%s/table/%s' % (self.sname_url, self.tname_url)
            ),
            200,
            'application/json'
        )
        self.assertHttp(
            self.session.get(
                'schema/%s/table/%s/column/%s' % (self.sname_url, self.tname_url, self.cname_url)
            ),
            200,
            'application/json'
        )

    def test_3_csv(self):
        self.assertHttp(
            self.session.post(
                'entity/%s:%s' % (self.sname_url, self.tname_url),
                data=u"""id,ǝɯɐu%
1,foo 1
2,foo 2
3,bar 1
4,baz 1
6,foo ǝɯɐu%
""".encode('utf8'),
                headers={"content-type": "text/csv"}
            ),
            200
        )

    def test_4_json(self):
        self.assertHttp(
            self.session.post(
                'entity/%s:%s' % (self.sname_url, self.tname_url),
                json=[
                    {"id": 5, self.cname: "baz 2"},
                    {"id": 7, self.cname: u"foo ǝɯɐu% 2"},
                ]
            ),
            200
        )

    def test_5_queryvals(self):
        url = 'attribute/%s:%s/%s=%s/id,%s' % (
            self.sname_url,
            self.tname_url,
            self.cname_url,
            urlquote(u"foo ǝɯɐu%".encode('utf8')),
            self.cname_url
        )
        self.assertHttp(self.session.get(url), 200, 'application/json')
        self.assertHttp(self.session.get(url, headers={"accept": "text/csv"}), 200, 'text/csv')

    def test_6_download(self):
        r = self.session.get('entity/%s:%s?download=%s' % (self.sname_url, self.tname_url, self.tname_url))
        self.assertHttp(r, 200)
        self.assertRegexpMatches(
            r.headers.get('content-disposition'),
            "attachment; filename[*]=UTF-8''%s.*" % self.tname_url
        )

    def test_7_badcsv(self):
        for hdr in [
                u"id,%s" % self.cname,
                u"id,%s" % self.tname
        ]:
            for row in [
                    u"10",
                    self.tname,
                    u"10,10,%s" % self.tname
            ]:
                self.assertHttp(
                    self.session.post(
                        'entity/%s:%s' % (self.sname_url, self.tname_url),
                        data=(u"%s\n%s" % (hdr, row)).encode('utf8'),
                        headers={"content-type": "text/csv"}
                    ),
                    [400, 409]
                )

    

if __name__ == '__main__':
    unittest.main(verbosity=2)
