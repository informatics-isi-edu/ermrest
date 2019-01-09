
import unittest
import common
import json
import re

_schema = 'ctypes'

from common import Int4, Int8, Text, Int4Array, TextArray, Timestamptz, TypeDoc, ArrayDoc, \
    RID, RCT, RMT, RCB, RMB, RidKey, \
    ModelDoc, SchemaDoc, TableDoc, ColumnDoc, KeyDoc, FkeyDoc

def setUpModule():
    url = 'schema/%s' % _schema
    r = common.primary_session.get(url)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times... :-(
        common.primary_session.post(url)

def json_strip_system_cols(d):
    return [
        {
            k: v
            for k, v in row.items()
            if k not in {'RID','RCT','RMT','RCB','RMB'}
        }
        for row in d
    ]

def csv_strip_system_cols(d):
    inlines = d.split('\n')
    if inlines[0].find('RID,RCT,RMT,RCB,RMB,') == 0:
        return '\n'.join([
            re.sub('^([^,]+,){5}', '', line)
            for line in inlines
        ])
    else:
        return d

def add_etype_vk_wk_rk(klass, vk, wk, rk):
    def check_json(self):
        r = self.session.get(self._read_urls()[rk])
        self.assertHttp(r, 200, 'application/json')
        self.assertJsonEqual(json_strip_system_cols(r.json()), self._data(vk))
    setattr(klass, 'test_%s_%s_json_2_read_%s' % (vk, wk, rk), check_json)

    def check_csv(self):
        r = self.session.get(self._read_urls()[rk], headers={"Accept": "text/csv"})
        self.assertHttp(r, 200, 'text/csv')
        self.assertEqual(csv_strip_system_cols(r.text), self._data_csv(vk))
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
            self.assertJsonEqual(json_strip_system_cols(r.json()), self._data(vk))
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
        return TableDoc(
            cls._table_name(),
            [
                RID, RCT, RMT, RCB, RMB,
                ColumnDoc("id", Int8, nullok=False),
                ColumnDoc("name", Text),
                ColumnDoc("payload", TypeDoc(cls.etype)),
            ],
            [ RidKey, KeyDoc(["id"]) ]
        )

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
            for k, v in list(cls._write_urls().items()) + [("3attribute", 'attribute/%s:%s/id,name,payload' % (_schema, cls._table_name()))]
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

class VocabCols (common.ErmrestTest):
    table_name = 'Vocab'

    def _table_def(self):
        return TableDoc(
            self.table_name,
            [
                RID, RCT, RMT, RCB, RMB,
                ColumnDoc("id", TypeDoc("ermrest_curie"), nullok=False, default='PREFIX:{RID}'),
                ColumnDoc("uri", TypeDoc("ermrest_uri"), nullok=False, default='https://server.example.org/id/{RID}'),
                ColumnDoc("name", Text, nullok=False),
            ],
            [ RidKey, KeyDoc(["id"]), KeyDoc(["uri"]) ],
        )

    def test_01_table(self):
        self.assertHttp(self.session.post('schema/%s/table' % _schema, json=self._table_def()), 201)

    custom_data = [
        {"name": "A", "id": "PREFIX2:A", "uri": "https://server2.example.org/id/A"},
        {"name": "B", "id": "PREFIX2:B", "uri": "https://server2.example.org/id/B"},
    ]

    def test_02_custom_load(self):
        self.assertHttp(self.session.post('entity/%s:%s?defaults=RID' % (_schema, self.table_name), json=self.custom_data), 200)

    def test_03_custom_check(self):
        r = self.session.get('attributegroup/%s:%s/name=A;name=B/name;id,uri@sort(name)' % (_schema, self.table_name))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json(), self.custom_data)

    default_data = [
        {"name": "C"},
        {"name": "D"},
    ]

    def test_04_default_load(self):
        self.assertHttp(self.session.post('entity/%s:%s?defaults=RID,id,uri' % (_schema, self.table_name), json=self.default_data), 200)

    def test_05_default_check(self):
        r = self.session.get('attributegroup/%s:%s/name=C;name=D/name;RID,id,uri@sort(name)' % (_schema, self.table_name))
        self.assertHttp(r, 200, 'application/json')
        for row in r.json():
            self.assertEqual(row['id'], 'PREFIX:%s' % row['RID'])
            self.assertEqual(row['uri'], 'https://server.example.org/id/%s' % row['RID'])

class CtypeText (common.ErmrestTest):
    ctype = 'text'
    cval = 'one'
    pattern = 'one'

    test_agg_order = True
    test_agg_array = True

    @property
    def cval_url(self):
        return common.urlquote(str(self.cval))

    def _table_name(self):
        return 'test_%s' % self.ctype

    def _qual_table_name(self):
        return '%s:%s' % (_schema, self._table_name())
    
    def _entity_url(self):
        return 'entity/%s' % (self._qual_table_name())

    def _aggfunc_url(self, aggfunc, column):
        return 'attributegroup/%s/RMB;agg:=%s(%s)' % (
            self._qual_table_name(),
            aggfunc,
            column
        )

    def _pattern_url(self, colname, op=None, rval=None):
        return '%s/%s%s%s' % (
            self._entity_url(),
            colname,
            '::regexp::' if op is None else op,
            self.pattern if rval is None else rval,
        )

    def _table_def(self):
        return TableDoc(
            self._table_name(),
            [
                RID, RCT, RMT, RCB, RMB,
                ColumnDoc("sid", TypeDoc("serial"), nullok=False),
                ColumnDoc("column1", TypeDoc(self.ctype)),
                ColumnDoc("column2", Text),
                ColumnDoc("column3", ArrayDoc("%s[]" % self.ctype, TypeDoc(self.ctype))),
            ],
            [ RidKey, KeyDoc(["sid"]), KeyDoc(["column1"]) ]
        )
    
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
        self.assertEqual(doc['column_definitions'][6]['type']['typename'], self.ctype)

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

    def _pattern_check(self, colname, expected_count, op=None, rval=None):
        r = self.session.get(self._pattern_url(colname, op=op, rval=rval))
        self.assertHttp(r, 200, 'application/json')
        got_count = len(r.json())
        self.assertEqual(
            got_count,
            expected_count,
            'Column %s should %s match %s %s times, not %s.\n%s\n' % (colname, op, self.pattern, expected_count, got_count, r.text)
        )

    def _check_aggfunc(self, aggfunc, column, resultval=None, resultmembers=None):
        r = self.session.get(self._aggfunc_url(aggfunc, column))
        self.assertHttp(r, 200, 'application/json')
        doc = r.json()
        self.assertEqual(len(doc), 1)
        if resultval is not None:
            self.assertEqual(doc[0]['agg'], resultval)
        if resultmembers is not None:
            def key(v):
                def typekey(v):
                    categories = [
                        type(None),
                        list,
                        dict,
                        bool,
                        (int, float),
                        str,
                    ]
                    for i in range(len(categories)):
                        if isinstance(v, categories[i]):
                            return i
                    return hash(type(v))
                return (typekey(v), v if v is not None else False)
            self.assertEqual(sorted(doc[0]['agg'], key=key), sorted(resultmembers, key=key))

    def test_05a_agg_arrays(self):
        if not self.test_agg_array:
            return
        self._check_aggfunc('array', 'column1', resultmembers=[None, None, self.cval])
        self._check_aggfunc('array', '*')
        self._check_aggfunc('array_d', 'column1', resultmembers=[None, self.cval])

        self._check_aggfunc('array', 'column3', resultmembers=[None, [], [self.cval, self.cval]])
        self._check_aggfunc('array_d', 'column3', resultmembers=[None, [], [self.cval, self.cval]])

    def test_05a_agg_counts(self):
        self._check_aggfunc('cnt', 'column1', 1)
        self._check_aggfunc('cnt', '*', 3)
        self._check_aggfunc('cnt_d', 'column1', 1)

        self._check_aggfunc('cnt', 'column3', 2)
        self._check_aggfunc('cnt_d', 'column3', 2)
        
    def test_05a_agg_order(self):
        if not self.test_agg_order:
            return
        self._check_aggfunc('min', 'column1', self.cval)
        self._check_aggfunc('max', 'column1', self.cval)

        self._check_aggfunc('min', 'column3', [])
        self._check_aggfunc('max', 'column3', [self.cval, self.cval])

    def test_05a_patterns(self):
        self._pattern_check('column1', 1)
        self._pattern_check('column3', 1)
        self._pattern_check('column3', 1, op='=', rval=self.cval_url)
        #self._pattern_check('*', ???)  this varies due to new timestamp system columns

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

class CtypeSystem (CtypeText):
    # test aggregates on the system columns once too... just to make sure these domain types don't break
    def test_05a_agg_arrays(self):
        self._check_aggfunc('array', 'RID')
        self._check_aggfunc('array_d', 'RID')
        self._check_aggfunc('array', 'RCT')
        self._check_aggfunc('array_d', 'RCT')
        self._check_aggfunc('array', 'RMB')
        self._check_aggfunc('array_d', 'RMB')

    def test_05a_agg_counts(self):
        self._check_aggfunc('cnt', 'RID', 3)
        self._check_aggfunc('cnt', 'RCT', 3)
        self._check_aggfunc('cnt', 'RMB', 3)

        self._check_aggfunc('cnt_d', 'RID', 3)
        self._check_aggfunc('cnt_d', 'RCT', 1)
        self._check_aggfunc('cnt_d', 'RMB', 1)

    def test_05a_agg_order(self):
        self._check_aggfunc('min', 'RID')
        self._check_aggfunc('max', 'RID')
        self._check_aggfunc('min', 'RCT')
        self._check_aggfunc('max', 'RCT')
        self._check_aggfunc('min', 'RMB')
        self._check_aggfunc('max', 'RMB')

class CtypeBoolean (CtypeText):
    ctype = 'boolean'
    cval = True
    pattern = 't'
    test_agg_order = False

class CtypeJsonb (CtypeText):
    ctype = 'jsonb'
    cval = {"foo": "bar"}
    pattern = 'foo.%2Abar'
    test_agg_order = False
    
    @property
    def cval_url(self):
        return common.urlquote(json.dumps(self.cval))

    def _data(self):
        # override because we don't want to deal w/ test suite limitations
        # SQL NULL vs JSON null vs empty string for JSON vs CSV inputs
        return [
            {"sid": 1, "column1": self.cval, "column2": "value1", "column3": None}, 
            {"sid": 2, "column1": 5, "column2": "value2", "column3": [self.cval, self.cval]},
            {"sid": 3, "column1": 10, "column2": "value3", "column3": []},
        ]

    def test_05a_agg_arrays(self):
        self._check_aggfunc('array', 'column1', resultmembers=[5, 10, self.cval])
        self._check_aggfunc('array', '*')
        self._check_aggfunc('array_d', 'column1', resultmembers=[5, 10, self.cval])

        self._check_aggfunc('array', 'column3', resultmembers=[None, [], [self.cval, self.cval]])
        self._check_aggfunc('array_d', 'column3', resultmembers=[None, [], [self.cval, self.cval]])

    def test_05a_agg_counts(self):
        self._check_aggfunc('cnt', 'column1', 3)
        self._check_aggfunc('cnt', '*', 3)
        self._check_aggfunc('cnt_d', 'column1', 3)

        self._check_aggfunc('cnt', 'column3', 2)
        self._check_aggfunc('cnt_d', 'column3', 2)

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
    test_agg_order = False
    test_agg_array = False

class CtypeTimestamp (CtypeTimestamptz):
    ctype = 'timestamp'
    cval = '2015-03-11T11:32:56'

class CtypeTimetz (CtypeTimestamptz):
    ctype = 'timetz'
    cval = '11:32:56-0000'
    test_agg_order = False
    test_agg_array = False

class CtypeTime (CtypeTimestamptz):
    ctype = 'time'
    cval = '11:32:56'

class CtypeDate (CtypeInt2):
    ctype = 'date'
    cval = '2015-03-11'

class CtypeUuid (CtypeInt2):
    ctype = 'uuid'
    cval = '2648a44e-c81d-11e4-b6d7-00221930f5cc'
    test_agg_order = False
    
class CtypeInterval (CtypeInt2):
    ctype = 'interval'
    cval = 'P1Y2M3DT4H5M6S'
    test_agg_order = False
    test_agg_array = False

class CtypeSerial2 (CtypeInt2):
    ctype = 'serial2'
    test_agg_order = False
    test_agg_array = False

    def _table_def(self):
        """Don't make arrays of this type."""
        doc = CtypeInt2._table_def(self)
        doc['column_definitions'][8] = {"type": {"typename": self.ctype}, "name": "column3"}
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

    def test_05a_agg_counts(self):
        self._check_aggfunc('cnt', 'column1', 4)
        self._check_aggfunc('cnt', '*', 4)
        self._check_aggfunc('cnt_d', 'column1', 4)

        self._check_aggfunc('cnt', 'column3', 4)
        self._check_aggfunc('cnt_d', 'column3', 1)

    def test_05a_patterns(self):
        self._pattern_check('column1', 1)
        # self._pattern_check('*', ???) this varies due to new timestamp system columns

class CtypeSerial4 (CtypeSerial2): ctype = 'serial4'

class CtypeSerial8 (CtypeSerial2): ctype = 'serial8'

class CtypeLongtext (CtypeText):
    ctype = 'longtext'
    cval = 'oneoneone'

    def _table_def(self):
        """Don't make arrays of this type."""
        doc = CtypeText._table_def(self)
        doc['column_definitions'][8] = {"type": {"typename": self.ctype}, "name": "column3"}
        return doc

    def _data(self):
        """Don't make arrays of this type."""
        doc = CtypeText._data(self)
        doc[1]["column3"] = self.cval
        doc[2]["column3"] = None
        return doc
    
    def test_05a_agg_arrays(self):
        if not self.test_agg_array:
            return
        self._check_aggfunc('array', 'column1', resultmembers=[None, None, self.cval])
        self._check_aggfunc('array', '*')
        self._check_aggfunc('array_d', 'column1', resultmembers=[None, self.cval])

    def test_05a_agg_counts(self):
        self._check_aggfunc('cnt', 'column1', 1)
        self._check_aggfunc('cnt', '*', 3)
        self._check_aggfunc('cnt_d', 'column1', 1)

    def test_05a_agg_order(self):
        if not self.test_agg_order:
            return
        self._check_aggfunc('min', 'column1', self.cval)
        self._check_aggfunc('max', 'column1', self.cval)

class CtypeMarkdown (CtypeLongtext):
    ctype = 'markdown'
    cval = '**one**'

class DefaultValue (common.ErmrestTest):
    ctype = None
    defaults = []

    @classmethod
    def _table_name(cls):
        return 'test_default_%s' % cls.ctype

    @classmethod
    def _table_def(cls):
        return TableDoc(
            cls._table_name(),
            [
                RID, RCT, RMT, RCB, RMB,
            ] + [
                ColumnDoc("col_%s" % val, TypeDoc(cls.ctype), default=val)
                for val in cls.defaults
            ],
            [ RidKey ]
        )

    def test_defaults(self):
        self.assertHttp(self.session.post('schema/%s/table' % _schema, json=self._table_def()), 201)
        r = self.session.get('schema/%s/table/%s' % (_schema, self._table_name()))
        self.assertHttp(r, 200, 'application/json')
        columns = r.json()['column_definitions']
        for i in range(0, len(self.defaults)):
            self.assertEqual(columns[i+5]['default'], self.defaults[i])

class DefaultText (DefaultValue):
    ctype = 'text'
    defaults = ['0', 'foo', '1', ' ', '', None]

class DefaultInt8 (DefaultValue):
    ctype = 'int8'
    defaults = [1, -1, 0, None]

class DefaultBool (DefaultValue):
    ctype = 'boolean'
    defaults = [True, False, None]

class DefaultJson (DefaultValue):
    ctype = 'json'
    defaults = [True, 1, "one", {"foo": 1}, [1], [0], False, 0, "", {}, [], None]

class DefaultJsonb (DefaultJson):
    ctype = 'jsonb'

if __name__ == '__main__':
    unittest.main(verbosity=2)
