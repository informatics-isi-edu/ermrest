
import unittest
import basics
import common
import data


_S = 'joins'
from data import _T1, _T2, _Tc2, _T2b
_defs = basics.defs(_S)
_table_defs = _defs['schemas'][_S]['tables']

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()
        common.primary_session.post('entity/%s:%s' % (_S, _T1), json=data.BasicKey._initial).raise_for_status()
        common.primary_session.post('entity/%s:%s' % (_S, _T2), json=data.ForeignKey.data).raise_for_status()

def add_join_tests(klass):
    # generate tests for combinations of tables and linking notations
    rtable = '%s:%s' % (_S, klass.table)
    dtable = '%s:%s' % (_S, _table_defs[klass.table]['foreign_keys'][0]['referenced_columns'][0]['table_name'])

    paths = klass.paths + [
        '%s/%s' % (dtable, rtable),
        '%s/%s' % (rtable, dtable),
    ]

    for fkey in _table_defs[klass.table]['foreign_keys']:
        parts = {
            'dtable': dtable,
            'rtable': rtable,
            'rcols': ','.join([ '%(column_name)s' % c for c in fkey['foreign_key_columns'] ]),
            'dcols': ','.join([ '%(column_name)s' % c for c in fkey['referenced_columns'] ]),
        }
        paths.extend([
            template % parts
            for template in [
                    '%(dtable)s/(%(dcols)s)',
                    'A:=%(dtable)s/(A:%(dcols)s)',
                    '%(dtable)s/(%(rtable)s:%(rcols)s)',
                    '%(rtable)s/(%(rcols)s)',
                    'A:=%(rtable)s/(A:%(rcols)s)',
                    '%(rtable)s/(%(dtable)s:%(dcols)s)',
            ]
        ])
        for joinmode in ['', 'left', 'right', 'full']:
            parts['join'] = joinmode
            paths.extend([
                template % parts
                for template in [
                        '%(dtable)s/%(join)s(%(dcols)s)=(%(rtable)s:%(rcols)s)',
                        'A:=%(dtable)s/%(join)s(A:%(dcols)s)=(%(rtable)s:%(rcols)s)',
                        '%(rtable)s/%(join)s(%(rcols)s)=(%(dtable)s:%(dcols)s)',
                        'A:=%(rtable)s/%(join)s(A:%(rcols)s)=(%(dtable)s:%(dcols)s)',
                ]
            ])

    for i in range(len(paths)):
        def test(self):
            self.assertHttp(self.session.get('entity/%s' % paths[i]), 200)
        setattr(klass, 'test_path_%02d' % i, test)
        
    return klass

@add_join_tests
class ParseLinksSimple (common.ErmrestTest):
    table = _T2
    paths = []

@add_join_tests
class ParseLinksComposite (common.ErmrestTest):
    table = _Tc2
    paths = []

@add_join_tests
class ParseLinksAmbiguous (common.ErmrestTest):
    table = _T2b
    paths = [
        '%s:%s/(level1_id)=(%s:%s:level1_id2)' % (_S, _T2, _S, _T2b)
    ]

def add_proj_tests(klass):
    join = "A:=%s/B:=%s/C:=%s" % (klass.table1, klass.table2, klass.table1)
    for api, proj, name in [
            ("attribute", "id,B:name", "unqual_qual"),
            ("attribute", "*", "star"),
            ("attribute", "A:*,B:*,C:*", "qualstars"),
            ("aggregate", "count:=cnt(id)", "unqual"),
            ("aggregate", "count:=cnt(*)", "star"),
            ("attributegroup", "id,B:name", "unqualg_quala"),
            ("attributegroup", "B:id;name", "qualg_unquala"),
            ("attributegroup", "A:*;B:*,C:*", "qualstars"),
    ]:
        path = '%s/%s/%s' % (api, join, proj)
        setattr(klass, 'test_%s_%s' % (api, name), lambda self: self.assertHttp(self.session.get(path), 200))
    return klass

def add_count_tests(klass):
    parts = {
        'T1': klass.table1,
        'T2': klass.table2,
    }
    template = "aggregate/A:=%(T1)s/%(join)s(id)=(%(T2)s:level1_id)/c:=%(proj)s"
    for expected, join, proj, name in [
            (3, "",      "cnt_d(A:id)", "distinct_id1"),
            (4, "left",  "cnt_d(A:id)", "distinct_id1"),
            (3, "right", "cnt_d(A:id)", "distinct_id1"),
            (4, "full",  "cnt_d(A:id)", "distinct_id1"),
            (4, "",      "cnt_d(id)", "distinct_id2"),
            (4, "left",  "cnt_d(id)", "distinct_id2"),
            (5, "right", "cnt_d(id)", "distinct_id2"),
            (5, "full",  "cnt_d(id)", "distinct_id2"),
            (4, "",      "cnt(*)", "star"),
            (5, "left",  "cnt(*)", "star"),
            (5, "right", "cnt(*)", "star"),
            (6, "full",  "cnt(*)", "star"),
    ]:
        parts.update({
            "join": join,
            "proj": proj,
            "name": name
        })
        setattr(klass, 'test_cnt_%(join)s_%(name)s' % parts, lambda self: self._check_c(template % parts, expected))
    return klass

@add_proj_tests
@add_count_tests
class JoinedProjections (common.ErmrestTest):
    table1 = '%s:%s' % (_S, _T1)
    table2 = '%s:%s' % (_S, _T2)

    def _check_c(self, path, expected):
        r = self.session.get(path)
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json()[0]['c'], expected)

class MultiKeyReference (common.ErmrestTest):
    def test_implicit_multi(self):
        # regression test for ermrest#160, internal server error with MultiKeyReference
        self.assertHttp(self.session.get('entity/%(S)s:%(T1)s/%(S)s:%(T2b)s' % {'T1': _T1, 'T2b': _T2b, 'S': _S}), 200)

if __name__ == '__main__':
    unittest.main(verbosity=2)
