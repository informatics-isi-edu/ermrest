
import unittest
import common

from common import Int4, Int8, Serial8, Text, Int4Array, TextArray, Timestamptz, \
    RID, RCT, RMT, RCB, RMB, RidKey, \
    ModelDoc, SchemaDoc, TableDoc, ColumnDoc, KeyDoc, FkeyDoc

class CyclicFkeys (common.ErmrestTest):
    _test_schema_doc = ModelDoc(
        [
            SchemaDoc(
                "s1",
                [
                    TableDoc(
                        "A",
                        [
                            RID, RCT, RMT, RCB, RMB,
                            ColumnDoc("id", Serial8, nullok=False, annotations={"tag:misd.isi.edu,2015:test0": "value 0"}),
                            ColumnDoc("rid", Int8),
                        ],
                        [ RidKey, KeyDoc(["id"], {"tag:misd.isi.edu,2015:test0": "value 0"}) ],
                        [
                            FkeyDoc("s1", "A", ["rid"], "s2", "A", ["id"], {"tag:misd.isi.edu,2015:test0": "value 0"}),
                        ],
                        {"tag:misd.isi.edu,2015:test0": "value 0"}
                    ),
                ],
                {"tag:misd.isi.edu,2015:test0": "value 0"}
            ),
            SchemaDoc(
                "s2",
                [
                    TableDoc(
                        "A",
                        [
                            RID, RCT, RMT, RCB, RMB,
                            ColumnDoc("id", Serial8, nullok=False),
                            ColumnDoc("rid", Int8),
                        ],
                        [ RidKey, KeyDoc(["id"]) ],
                        [
                            FkeyDoc("s2", "A", ["rid"], "s1", "A", ["id"]),
                        ]
                    ),
                ],
                comment="schema s2 of model document",
            )
        ]
    )
    
    def test_1_doc(self):
        self.assertHttp(self.session.post('schema', json=self._test_schema_doc), 201)
        self.assertHttp(self.session.post('schema', json=self._test_schema_doc), 409)

    _test_schema_list = [
        SchemaDoc("s3"),
        TableDoc(
            "B",
            [
                RID, RCT, RMT, RCB, RMB,
                ColumnDoc("id", Serial8, nullok=False),
                ColumnDoc("rid", Int8),
            ],
            [ RidKey, KeyDoc(["id"]) ],
            [
                FkeyDoc("s1", "B", ["rid"], "s4", "B", ["id"]),
            ],
            schema_name="s1",
        ),
        SchemaDoc("s4", comment="schema s4 of model document"),
        TableDoc(
            "B",
            [
                RID, RCT, RMT, RCB, RMB,
                ColumnDoc("id", Serial8, nullok=False),
                ColumnDoc("rid", Int8),
            ],
            [ RidKey, KeyDoc(["id"]) ],
            [
                FkeyDoc("s4", "B", ["rid"], "s1", "B", ["id"]),
            ],
            schema_name="s4",
        )
    ]
        
    def test_2_list(self):
        self.assertHttp(self.session.post('schema', json=self._test_schema_list), 201)

    def test_3_delete(self):
        self.assertHttp(self.session.delete('schema/s4/table/B'), 409)
        self.assertHttp(self.session.delete('schema/s1/table/B/foreignkey/rid/reference/s4:B/id'), 204)
        self.assertHttp(self.session.delete('schema/s4/table/B'), 204)

if __name__ == '__main__':
    unittest.main(verbosity=2)
