
import unittest
import common
import json

_schema = 'ctypes'

def setUpModule():
    url = 'schema/%s' % _schema
    r = common.primary_session.get(url)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times... :-(
        common.primary_session.post(url)

def add_etype_vk_wk_rk(klass, vk, wk, rk):
    def check_json(self):
        r = self.session.get(self._read_urls()[rk])
        self.assertHttp(r, 200, 'application/json')
        self.assertJsonEqual(r.json(), self._data(vk))
    setattr(klass, 'test_%s_%s_json_2_read_%s' % (vk, wk, rk), check_json)

    def check_csv(self):
        r = self.session.get(self._read_urls()[rk], headers={"Accept": "text/csv"})
        self.assertHttp(r, 200, 'text/csv')
        self.assertEqual(r.content, self._data_csv(vk))
    setattr(klass, 'test_%s_%s_csv_2_read_%s' % (vk, wk, rk), check_csv)

def add_etype_vk_wk(klass, vk, wk):
    def load_json(self):
        self.assertHttp(self.session.put(self._write_urls()[wk], json=self._data(vk)), 200)
    setattr(klass, 'test_%s_%s_json_1_load' % (vk, wk), load_json)

    def load_csv(self):
        self.assertHttp(
            self.session.put(
                self._write_urls()[wk],
                data=self._data_csv(vk),
                headers={'Content-Type': 'text/csv'}
            ), 200)
    setattr(klass, 'test_%s_%s_csv_1_load' % (vk, wk), load_csv)

    for rk in klass._read_urls().keys():
        add_etype_vk_wk_rk(klass, vk, wk, rk)

    def check_query(self):
        if self.etype == 'jsonb':
            r = self.session.get(self._query_url(self._values[vk]))
            self.assertHttp(r, 200, 'application/json')
            self.assertJsonEqual(r.json(), self._data(vk))
    setattr(klass, 'test_%s_%s_pred_3' % (vk, wk), check_query)

def add_etype_tests(klass):
    # generate a dense set of related tests by nested loops over value, write URL, read URL, and content-types
    for vk in klass._values.keys():
        for wk in klass._write_urls().keys():
            add_etype_vk_wk(klass, vk, wk)
    return klass
                                         
@add_etype_tests
class EtypeJson (common.ErmrestTest):
    etype = 'json'

    @classmethod
    def _table_name(cls):
        return 'test_%s' % cls.etype

    @classmethod
    def _table_def(cls):
        return {
            "kind": "table",
            "schema_name": _schema,
            "table_name": cls._table_name(),
            "column_definitions": [ 
                { "type": { "typename": "int8" }, "name": "id", "nullok": False },
                { "type": { "typename": "text" }, "name": "name" },
                { "type": { "typename": cls.etype }, "name": "payload" }
            ],
            "keys": [ { "unique_columns": [ "id" ] } ]
        }

    @classmethod
    def setUpClass(cls):
        common.primary_session.post('schema/%s/table' % _schema, json=cls._table_def()).raise_for_status()

    @classmethod
    def _write_urls(cls):
        return  {
            "1entity": 'entity/%s:%s' % (_schema, cls._table_name()),
            "2attributegroup": 'attributegroup/%s:%s/id;name,payload' % (_schema, cls._table_name())
        }

    def _query_url(self, value):
        return 'entity/%s:%s/payload=%s' % (_schema, self._table_name(), common.urlquote(json.dumps(value)))

    @classmethod
    def _read_urls(cls):
        return {
            k: v + '@sort(id)'
            for k, v in cls._write_urls().items() + [("attribute", 'attribute/%s:%s/id,name,payload' % (_schema, cls._table_name()))]
        }

    _values = {
        "number": 5,
        "string": "foo",
        "object": {"foo": "bar"},
        "numbers": [5, 6],
        "strings": ["foo", "bar"],
        "objects": [{"foo": "bar"}, {"foo": "bar"}],
        "null": None
    }

    def _data(self, key):
        return [
            {"id": 1, "name": "row1", "payload": self._values[key]}
        ]

    def _data_csv(self, key):
        val = json.dumps(self._values[key])
        if val.find('"') >= 0 or val.find(',') >= 0:
            val = '"%s"' % val.replace('"', '""')
        return """id,name,payload
1,row1,%s
""" % val

class EtypeJsonb (EtypeJson):
    etype = 'jsonb'


class CtypeText (common.ErmrestTest):
    ctype = 'text'
    cval = 'one'
    pattern = 'one'

    def _table_name(self):
        return 'test_%s' % self.ctype

    def _qual_table_name(self):
        return '%s:%s' % (_schema, self._table_name())
    
    def _entity_url(self):
        return 'entity/%s' % (self._qual_table_name())

    def _pattern_url(self, colname):
        return '%s/%s::regexp::%s' % (
            self._entity_url(),
            colname,
            self.pattern
        )

    def _table_def(self):
        return {
            "kind": "table",
            "schema_name": _schema,
            "table_name": self._table_name(),
            "column_definitions": [
                {"type": {"typename": "serial"}, "name": "sid", "nullok": False},
                {"type": {"typename": self.ctype}, "name": "column1"},
                {"type": {"typename": "text"}, "name": "column2"},
                {"type": {"typename": "%s[]" % self.ctype, "is_array": True, "base_type": {"typename": self.ctype}}, "name": "column3"}
            ],
            "keys": [ {"unique_columns": ["sid"]}, {"unique_columns": ["column1"]} ]
        }
    
    def _data(self):
        return [
            {"sid": 1, "column1": self.cval, "column2": "value1", "column3": None}, 
            {"sid": 2, "column1": None, "column2": "value2", "column3": [self.cval, self.cval]},
            {"sid": 3, "column1": None, "column2": "value3", "column3": []},
        ]
    
    def test_01_create(self):
        self.assertHttp(self.session.post('schema/%s/table' % _schema, json=self._table_def()), 201)

    def test_02_queryempty(self):
        self.assertHttp(self.session.get(self._entity_url()), 200, 'application/json')

    def test_03_introspect(self):
        r = self.session.get('schema/%s/table/%s' % (_schema, self._table_name()))
        self.assertHttp(r, 200, 'application/json')
        doc = r.json()
        self.assertEqual(doc['column_definitions'][1]['type']['typename'], self.ctype)

    def test_04_load(self):
        self.assertHttp(
            self.session.post(
                self._entity_url(),
                data=common.array_to_csv(self._data()),
                headers={"content-type": "text/csv"}
            ),
            200
        )
        self.assertHttp(self.session.put(self._entity_url(), json=self._data()), 200)

    def _pattern_check(self, colname, expected_count):
        r = self.session.get(self._pattern_url(colname))
        self.assertHttp(r, 200, 'application/json')
        got_count = len(r.json())
        self.assertEqual(
            got_count,
            expected_count,
            'Column %s should match %s %s times, not %s.\n%s\n' % (colname, self.pattern, expected_count, got_count, r.content)
        )
        
    def test_05a_patterns(self):
        self._pattern_check('column1', 1)
        self._pattern_check('column3', 1)
        self._pattern_check('*', 2)

    def test_05b_empty_array_input(self):
        # this test is useless but harmless for the subclasses that disable array storage for column3...
        r = self.session.get(self._entity_url() + '/sid=3')
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json()[0]["column3"], self._data()[2]["column3"])

    def test_06_retrieve(self):
        self.assertHttp(self.session.get(self._entity_url()), 200, 'application/json')
        self.assertHttp(self.session.get(self._entity_url(), headers={"Accept": "text/csv"}), 200, 'text/csv')

    def test_07_drop(self):
        self.assertHttp(self.session.delete('schema/%s/table/%s' % (_schema, self._table_name())), 204)

class CtypeBoolean (CtypeText):
    ctype = 'boolean'
    cval = 'True'
    pattern = 't'

class CtypeJsonb (CtypeText):
    ctype = 'jsonb'
    cval = {"foo": "bar"}
    pattern = 'foo.%2Abar'
    
    def _data(self):
        # override because we don't want to deal w/ test suite limitations
        # SQL NULL vs JSON null vs empty string for JSON vs CSV inputs
        return [
            {"sid": 1, "column1": self.cval, "column2": "value1", "column3": None}, 
            {"sid": 2, "column1": 5, "column2": "value2", "column3": [self.cval, self.cval]},
            {"sid": 3, "column1": 10, "column2": "value3", "column3": []},
        ]

class CtypeFloat4 (CtypeText):
    ctype = 'float4'
    cval = 1.0
    pattern = '1'

class CtypeFloat8 (CtypeFloat4): ctype = 'float8'

class CtypeInt2 (CtypeText):
    ctype = 'int2'
    cval = 1
    pattern = '1'

class CtypeInt4 (CtypeInt2): ctype = 'int4'

class CtypeInt8 (CtypeInt2): ctype = 'int8'

class CtypeTimestamptz (CtypeText):
    ctype = 'timestamptz'
    cval = '2015-03-11T11:32:56-0000'
    pattern = '56'

class CtypeTimestamp (CtypeTimestamptz):
    ctype = 'timestamp'
    cval = '2015-03-11T11:32:56'

class CtypeTimetz (CtypeTimestamptz):
    ctype = 'timetz'
    cval = '11:32:56-0000'

class CtypeTime (CtypeTimestamptz):
    ctype = 'time'
    cval = '11:32:56'

class CtypeDate (CtypeInt2):
    ctype = 'date'
    cval = '2015-03-11'

class CtypeUuid (CtypeInt2):
    ctype = 'uuid'
    cval = '2648a44e-c81d-11e4-b6d7-00221930f5cc'
    
class CtypeInterval (CtypeInt2):
    ctype = 'interval'
    cval = 'P1Y2M3DT4H5M6S'

class CtypeSerial2 (CtypeInt2):
    ctype = 'serial2'

    def _table_def(self):
        """Don't make arrays of this type."""
        doc = CtypeInt2._table_def(self)
        doc['column_definitions'][3] = {"type": {"typename": self.ctype}, "name": "column3"}
        return doc

    def _data(self):
        """Don't make arrays of this type."""
        return [
            {"sid": 1, "column1": None, "column2": "value1", "column3": self.cval },
            {"sid": 2, "column1": None, "column2": "value1", "column3": self.cval },
            {"sid": 3, "column1": None, "column2": "value2", "column3": self.cval },
            {"sid": 4, "column1": None, "column2": "value2", "column3": self.cval },
        ]
    
    def test_04_load(self):
        self.assertHttp(
            self.session.post(
                self._entity_url() + '?defaults=column1',
                data=common.array_to_csv(self._data()[0:3]),
                headers={"content-type": "text/csv"}
            ),
            200
        )
        self.assertHttp(
            self.session.post(
                self._entity_url() + '?defaults=column1',
                json=self._data()[3:]
            ),
            200
        )

    def test_05a_patterns(self):
        self._pattern_check('column1', 1)
        self._pattern_check('*', 4)

class CtypeSerial4 (CtypeSerial2): ctype = 'serial4'

class CtypeSerial8 (CtypeSerial2): ctype = 'serial8'

class CtypeLongtext (CtypeText):
    ctype = 'longtext'
    cval = 'oneoneone'

    def _table_def(self):
        """Don't make arrays of this type."""
        doc = CtypeText._table_def(self)
        doc['column_definitions'][3] = {"type": {"typename": self.ctype}, "name": "column3"}
        return doc

    def _data(self):
        """Don't make arrays of this type."""
        doc = CtypeText._data(self)
        doc[1]["column3"] = self.cval
        doc[2]["column3"] = None
        return doc
    
class CtypeMarkdown (CtypeLongtext):
    ctype = 'markdown'
    cval = '**one**'

if __name__ == '__main__':
    unittest.main(verbosity=2)
