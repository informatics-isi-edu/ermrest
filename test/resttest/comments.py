
import unittest
import common
import basics

_S = 'comments'
_T2b = basics._T2b

_defs = basics.defs(_S)
_table_defs = _defs['schemas'][_S]['tables']

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()

def add_comment_tests(klass):
    # generate comment API tests over many resources in table
    resources = basics.expand_table_resources(_S, _table_defs, klass.table)
    for i in range(len(resources)):
        def make_test_absent(i):
            def test_absent(self):
                r = self.session.get(resources[i])
                self.assertHttp(r, 200, 'application/json')
                d = r.json()
                if isinstance(d, list):
                    for x in d:
                        # foreign key resource returns a list of objects
                        self.assertEqual(x['comment'], None)
                else:
                    self.assertEqual(d['comment'], None)
                self.assertHttp(self.session.get('%s/comment' % resources[i]), 404)
            return test_absent
        setattr(klass, 'test_%02d_1_absent' % i, make_test_absent(i))

        def make_test_apply(i):
            newval = 'Comment on %s.' % resources[i]
            def test_apply(self):
                self.assertHttp(self.session.put('%s/comment' % resources[i], data=newval, headers={"Content-Type": "text/plain"}), 204)
            return test_apply
        setattr(klass, 'test_%02d_2_apply' % i, make_test_apply(i))

        def make_test_confirm(i):
            newval = 'Comment on %s.' % resources[i]
            def test_confirm(self):
                r = self.session.get(resources[i])
                self.assertHttp(r, 200, 'application/json')
                d = r.json()
                if isinstance(d, list):
                    for x in d:
                        # foreign key resource returns a list of objects
                        self.assertEqual(x['comment'], newval)
                else:
                    self.assertEqual(d['comment'], newval)
                r = self.session.get('%s/comment' % resources[i])
                self.assertHttp(r, 200, 'text/plain')
                # TODO: is this trailing newline a bug?
                self.assertEqual(r.text[0:-1], newval)
            return test_confirm
        setattr(klass, 'test_%02d_3_confirm' % i, make_test_confirm(i))

        def make_test_delete(i):
            def test_delete(self):
                self.assertHttp(self.session.delete('%s/comment' % resources[i]), 200)
                self.assertHttp(self.session.get('%s/comment' % resources[i]), 404)
            return test_delete
        setattr(klass, 'test_%02d_4_delete' % i, make_test_delete(i))

        def make_test_bad_apply(i):
            newval = [ 'Comment on %s.' % resources[i], ]
            def test_bad_apply(self):
                self.assertHttp(self.session.put('%s' % resources[i], json={"comment": newval}, headers={"Content-Type": "text/plain"}), 400)
            return test_bad_apply
        setattr(klass, 'test_%02d_5_bad_apply' % i, make_test_bad_apply(i))

    return klass

@add_comment_tests
class Comments (common.ErmrestTest):
    table = _T2b

if __name__ == '__main__':
    unittest.main(verbosity=2)
