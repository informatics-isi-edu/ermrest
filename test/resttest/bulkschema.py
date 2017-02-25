
import unittest
import common

class CyclicFkeys (common.ErmrestTest):
    _test_schema_doc = {
        "schemas": {
            "s1": {
                "schema_name": "s1",
                "tables": {
                    "A": {
                        "kind": "table",
                        "column_definitions": [
                            { 
                                "type": { "typename": "serial8"}, 
                                "name": "id", 
                                "nullok": False, 
                                "annotations": { "tag:misd.isi.edu,2015:test0": "value 0" } 
                            },
                            { "type": { "typename": "int8"}, "name": "rid" }
                        ],
                        "keys": [ { "unique_columns": [ "id" ], "annotations": { "tag:misd.isi.edu,2015:test0": "value 0" } } ],
                        "foreign_keys": [
                            { 
                                "foreign_key_columns": [ {"schema_name": "s1", "table_name": "A", "column_name": "rid"} ],
                                "referenced_columns": [ {"schema_name": "s2", "table_name": "A", "column_name": "id"} ], 
                                "annotations": { "tag:misd.isi.edu,2015:test0": "value 0" }
                            }
                        ],
                        "annotations": { "tag:misd.isi.edu,2015:test0": "value 0" }
                    }
                },
                "annotations": { "tag:misd.isi.edu,2015:test0": "value 0" }
            },
            "s2": {
                "comment": "schema s2 of model document",
                "tables": {
                    "A": {
                        "kind": "table",
                        "column_definitions": [
                            { "type": { "typename": "serial8"}, "name": "id", "nullok": False },
                            { "type": { "typename": "int8"}, "name": "rid" }
                        ],
                        "keys": [ { "unique_columns": [ "id" ] } ],
                        "foreign_keys": [
                            { 
                                "foreign_key_columns": [ {"schema_name": "s2", "table_name": "A", "column_name": "rid"} ],
                                "referenced_columns": [ {"schema_name": "s1", "table_name": "A", "column_name": "id"} ]
                            }
                        ]
                    }
                }
            }
        }
    }
    
    def test_1_doc(self):
        self.assertHttp(self.session.post('schema', json=self._test_schema_doc), 201)
        self.assertHttp(self.session.post('schema', json=self._test_schema_doc), 409)

    _test_schema_list = [
        {
            "schema_name": "s3"
        },
        {
            "schema_name": "s1",
            "table_name": "B",
            "kind": "table",
            "column_definitions": [
                { "type": { "typename": "serial8"}, "name": "id", "nullok": False },
                { "type": { "typename": "int8"}, "name": "rid" }
            ],
            "keys": [ { "unique_columns": [ "id" ] } ],
            "foreign_keys": [
                { 
                    "foreign_key_columns": [ {"schema_name": "s1", "table_name": "B", "column_name": "rid"} ],
                    "referenced_columns": [ {"schema_name": "s4", "table_name": "B", "column_name": "id"} ]
                }
            ]
        },
        {
            "schema_name": "s4",
            "comment": "schema s4 of model document"
        },
        {
            "kind": "table",
            "schema_name": "s4",
            "table_name": "B",
            "column_definitions": [
                { "type": { "typename": "serial8"}, "name": "id", "nullok": False },
                { "type": { "typename": "int8"}, "name": "rid" }
            ],
            "keys": [ { "unique_columns": [ "id" ] } ],
            "foreign_keys": [
                { 
                    "foreign_key_columns": [ {"schema_name": "s4", "table_name": "B", "column_name": "rid"} ],
                    "referenced_columns": [ {"schema_name": "s1", "table_name": "B", "column_name": "id"} ]
                }
            ]
        }
    ]
        
    def test_2_list(self):
        self.assertHttp(self.session.post('schema', json=self._test_schema_list), 201)

    def test_3_delete(self):
        self.assertHttp(self.session.delete('schema/s4/table/B'), 409)
        self.assertHttp(self.session.delete('schema/s1/table/B/foreignkey/rid/reference/s4:B/id'), 204)
        self.assertHttp(self.session.delete('schema/s4/table/B'), 204)

if __name__ == '__main__':
    unittest.main(verbosity=2)
