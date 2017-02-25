
# -*- coding: UTF-8 -*-

import unittest
import common
from common import urlquote

class KeysOnly (common.ErmrestTest):
    _schema = 'keysonly_schema'
    _table = 'keysonly_table'
    _entity_url = 'entity/%s:%s' % (_schema, _table)
    
    _table_doc = {
        "kind": "table",
        "schema_name": _schema,
        "table_name": _table,
        "column_definitions": [
            { "type": { "typename": "int8" }, "name": "key1" },
            { "type": { "typename": "text" }, "name": "key2" }
        ],
        "keys": [
            { "unique_columns": [ "key1" ] },
            { "unique_columns": [ "key2" ] }
        ]
    }
        
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
            self.session.post(self._entity_url + "?defaults=key1,key2", data=self._test_data, headers={"content-type": "text/csv"}),
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
        {
            "schema_name": sname
        },
        {
            "schema_name": sname,
            "table_name": tname,
            "column_definitions": [
                {"type": {"typename": "int8"}, "name": "id"},
                {"type": {"typename": "text"}, "name": cname}
            ],
            "keys": [
                {"unique_columns": ["id"]}
            ]
        }
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
                u"id",
                self.cname,
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
