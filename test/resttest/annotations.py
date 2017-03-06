
import unittest
import common
import basics

_S = 'annotations'
_T2b = basics._T2b

_defs = basics.defs(_S)
_table_defs = _defs['schemas'][_S]['tables']

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()

def add_annotation_tests(klass):
    # generate annotation API tests over many resources in table
    resources = basics.expand_table_resources(_S, _table_defs, klass.table) + [
        # annotations on catalog itself...
        ''
    ]

    tags = [
        'tag:misd.isi.edu,2015:test0',
        'tag:misd.isi.edu,2015:test1',
        'tag:misd.isi.edu,2015:test2'
    ]

    configs = [
        ('value 0', 'value 0'),
        (None, 'value 1'),
        (None, 'value 2')
    ]

    for r in range(len(resources)):
        res = resources[r]
        for k in range(3):
            tag = tags[k]
            before, after = configs[k]

            setattr(klass, 'test_r%02d_tag%d_before' % (r, k), lambda self: self._check(res, tag, before))
            setattr(klass, 'test_r%02d_tag%d_change' % (r, k), lambda self: self._change(res, tag, after))
            setattr(klass, 'test_r%02d_tag%d_delete' % (r, k), lambda self: self._change(res, tag, None))

    return klass

@add_annotation_tests
class Annotations (common.ErmrestTest):
    table = _T2b

    def _check(self, resource, key, value=None):
        if resource != '':
            resource += '/'
        r = self.session.get('%sannotation' % resource)
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json().get(key), value)
        r = self.session.get('%sannotation/%s' % (resource, common.urlquote(key)))
        if value is None:
            self.assertHttp(r, 404)
        else:
            self.assertHttp(r, 200, 'application/json')
            self.assertEqual(r.json(), value)

    def _change(self, resource, key, value=None):
        if resource != '':
            resource += '/'
        if value is None:
            self.assertHttp(
                self.session.delete('%sannotation/%s' % (resource, common.urlquote(key))),
                204
            )
            self._check(resource, key, value)
        else:
            self.assertHttp(
                self.session.put('%sannotation/%s' % (resource, common.urlquote(key)), json=value),
                201
            )
            self._check(resource, key, value)

if __name__ == '__main__':
    unittest.main(verbosity=2)
