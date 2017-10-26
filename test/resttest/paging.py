
import unittest
import common

_S = 'paging'
_T = 'pagedata'
_defs = {
    "schemas": {
        _S: {
            "tables": {
                _T: {
                    "kind": "table",
                    "column_definitions": [ 
                        { "type": { "typename": "serial4" }, "name": "id", "nullok": False },
                        { "type": { "typename": "text" }, "name": "name" },
                        { "type": { "typename": "int4" }, "name": "value" }
                    ],
                    "keys": [ { "unique_columns": [ "id" ] } ]
                }
            }
        }
    }
}
_data = [
    {"name": "bar", "value": v}
    for v in range(5)
] + [
    {"name": "bar"}
] + [
    {"name": "baz", "value": v}
    for v in range(5)
] + [
    {"name": "baz"}
] + [
    {"name": "foo", "value": v}
    for v in range(5)
] + [
    {"name": "foo"},
    {"value": 5},
    {}
]

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()
        common.primary_session.post('entity/%s:%s?defaults=id' % (_S, _T), json=_data).raise_for_status()

def add_paging_tests(klass):
    # generate many paging variants
    valid = [
        (20, "A_empty_num", "@sort(name,value)@after(,4)"),
        (16, "A_str_num",   "@sort(name,value)@after(bar,3)"),
        (14, "A_str_NULL",  "@sort(name,value)@after(bar,::null::)"),
        (0,  "A_NULL_NULL", "@sort(name,value)@after(::null::,::null::)"),
        (2,  "A_NULL_num",  "@sort(value,id)@after(::null::,12)"),
        (0,  "B_empty_num", "@sort(name,value)@before(,4)?limit=50"),
        (3,  "B_str_num",   "@sort(name,value)@before(bar,3)?limit=50"),
        (5,  "B_str_NULL",  "@sort(name,value)@before(bar,::null::)?limit=50"),
        (19, "B_NULL_NULL", "@sort(name,value)@before(::null::,::null::)?limit=50"),
        (17, "B_NULL_num",  "@sort(value,id)@before(::null::,12)?limit=50"),
        (18, "C_all_str",   "@sort(name)@after(aaa)@before(::null::)"),
        (16, "C_all_num",   "@sort(value)@after(-1)@before(::null::)"),
        (20, "C_all_id",    "@sort(id)@after(0)@before(::null::)"),
        (10, "C_half_id",   "@sort(id)@after(0)@before(::null::)?limit=10"),
        (12, "C_bxx_str",   "@sort(name)@after(aaa)@before(ccc)?limit=15"),
    ]
    
    invalid = [
        ("A_nosort", "@after(bar)"),
        ("B_nosort", "@before(bar)"),
        ("A1_sort2", "@sort(name,value)@after(bar)"),
        ("B1_sort2", "@sort(name,value)@before(bar)"),
        ("C1_nolimit", "@sort(name)@before(bar)"),
    ]

    queries = [
        (True, "entity",    "entity/pagedata"),
	(True, "attribute", "attribute/pagedata/id,name,value"),
	(True, "group",     "attributegroup/pagedata/id;name,value"),
	(True, "groupagg",  "attributegroup/pagedata/id;name,value,c:=cnt(*),c_d:=cnt_d(id),a:=array(*)"),
        (False, "agg",      "aggregate/pagedata/id:=cnt(id),name:=cnt(name),value:=cnt(*)"),
    ]

    def add_good(qname, query, pname, page, expected):
        path = '%s%s' % (query, page)
        setattr(
            klass,
            'test_good_%s_%s' % (qname, pname),
            lambda self: self._check_valid(path, expected)
        )

    def add_bad(qname, query, pname, page):
        path = '%s%s' % (query, page)
        setattr(
            klass,
            'test_bad_%s_%s' % (qname, pname),
            lambda self: self._check_invalid(path)
        )

    for canpage, qname, query in queries:

        for expected, pname, page in valid:
            if canpage:
                add_good(qname, query, pname, page, expected)
            else:
                add_bad(qname, query, pname, page)

        for pname, page in invalid:
            add_bad(qname, query, pname, page)

    # test for aggregates which change effective type of page boundary values
    canpage, qname, query = queries[3]

    add_good(qname, query, 'A_cntnum', '@sort(c)@after(0)', 20)
    add_good(qname, query, 'B_cntnum', '@sort(c)@before(2)?limit=50', 20)
    add_good(qname, query, 'A_cntnull', '@sort(c)@after(::null::)', 0)
    add_good(qname, query, 'B_cntnull', '@sort(c)@before(::null::)?limit=50', 20)

    add_good(qname, query, 'A_cntdnum', '@sort(c_d)@after(0)', 20)
    add_good(qname, query, 'B_cntdnum', '@sort(c_d)@before(2)?limit=50', 20)
    add_good(qname, query, 'A_cntdnull', '@sort(c_d)@after(::null::)', 0)
    add_good(qname, query, 'B_cntdnull', '@sort(c_d)@before(::null::)?limit=50', 20)

    add_good(qname, query, 'A_jsonval', '@sort(a)@after(%5B%5D)', 20)
    add_good(qname, query, 'B_jsonval', '@sort(a)@before(%7B%7D)?limit=50', 20)
    add_good(qname, query, 'A_jsonnull', '@sort(a)@after(::null::)', 0)
    add_good(qname, query, 'B_jsonnull', '@sort(a)@before(::null::)?limit=50', 20)

    return klass

@add_paging_tests
class PagingJson (common.ErmrestTest):
    content_type = 'application/json'
    
    def _get(self, path):
        return self.session.get(path, headers={"Accept": self.content_type})

    def _check_valid(self, path, expected):
        r = self._get(path)
        self.assertHttp(r, 200, self.content_type)
        actual = self._count(r)
        self.assertEqual(
            actual, expected,
            "Actual %d != Expected %d\n%s\n%s\n%s\n" % (
                actual, expected,
                path,
                r.headers,
                r.content
            )
        )

    def _check_invalid(self, path):
        self.assertHttp(self._get(path), 400)

    def _count(self, r):
        return len(r.json())

class PagingJsonStream (PagingJson):
    content_type = 'application/x-json-stream'
    def _count(self, r):
        return len(list(r.iter_lines()))

class PagingCsv (PagingJsonStream):
    content_type = 'text/csv'
    def _count(self, r):
        return len(list(r.iter_lines())) - 1
        
if __name__ == '__main__':
    unittest.main(verbosity=2)
