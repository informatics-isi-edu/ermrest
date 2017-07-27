
import unittest
import common
import basics

_S = 'preconditions'
_T1 = basics._T1
_defs = basics.defs(_S)
_table_defs = _defs['schemas'][_S]['tables']

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()

class Precondition (common.ErmrestTest):
    resource = None

    @classmethod
    def get_etag(cls):
        r = cls.session.get(cls.resource)
        r.raise_for_status()
        return r.headers['etag']

    def _convert(self, value):
        if value == '*':
            return '*'
        elif value == 'wrong':
            return '"wrong-etag"'
        elif value == 'etag':
            return self.etag
        else:
            return value

    def setUp(self):
        self.etag = self.get_etag()
    
    def _get_check(self, status=None, match=None, nomatch=None):
        hdrs = {}
        if match is not None:
            hdrs['if-match'] = ', '.join([ self._convert(v) for v in match ])
        if nomatch is not None:
            hdrs['if-none-match'] = ', '.join([ self._convert(v) for v in nomatch ])
        self.assertHttp(self.session.get(self.resource, headers=hdrs), status)

class PreconditionSchema (Precondition):
    resource = 'schema'

    def test_1_post(self):
        self.assertHttp(self.session.post('schema/DOES_NOT_EXIST', headers={'if-none-match': self.etag}), 412)
        r = self.session.post('schema/DOES_NOT_EXIST', headers={'if-match': self.etag})
        self.assertHttp(r, 201)
        self.assertNotEqual(r.headers['etag'], self.etag)
        self.etag = self.get_etag()
        self.assertEqual(r.headers['etag'], self.etag)

    def test_2_delete(self):
        self.assertHttp(self.session.delete('schema/DOES_NOT_EXIST', headers={'if-match': '"broken"'}), 412)
        self.assertHttp(self.session.delete('schema/DOES_NOT_EXIST', headers={'if-none-match': self.etag}), 412)
        self.assertHttp(self.session.delete('schema/DOES_NOT_EXIST', headers={'if-match': self.etag}), 204)

def add_get_tests(klass):
    for status, match, tags in [
            (200, True, ['*']),
            (304, False, ['*']),
            (200, True, ['etag']),
            (304, False, ['etag']),
            (304, True, ['wrong']),
            (200, False, ['wrong']),
            (200, True, ['etag', 'wrong']),
            (304, False, ['etag', 'wrong'])
    ]:
        name = 'test_1_get_%s_%s' % (
            'match' if match else 'nomatch',
            '_'.join(tags)
        )
        setattr(klass, name, lambda self: self._get_check(status, match=tags if match else None, nomatch=tags if not match else None))
    
    return klass

@add_get_tests
class PreconditionTable (Precondition):
    resource = 'schema/%s/table/%s' % (_S, _T1)

def add_mutate_tests(klass):
    setattr(klass, 'test_2_post', lambda self: self._mutate_check(lambda hdrs: self.session.post(self.resource, json=self.data, headers=hdrs), 200))
    setattr(klass, 'test_3_put', lambda self: self._mutate_check(lambda hdrs: self.session.put(self.resource, json=self.data, headers=hdrs), 200))
    setattr(klass, 'test_4_delete', lambda self: self._mutate_check(lambda hdrs: self.session.delete(self.resource + '/id=%d' % self.data[0]['id'], json=self.data, headers=hdrs), 204))
    return klass

@add_mutate_tests
class PreconditionData1 (PreconditionTable):
    resource = 'entity/%s:%s' % (_S, _T1)
    data = [{"id": 47, "name": "foo 47"}]

    def _mutate_check(self, mutator, status):
        self.assertHttp(mutator({'if-match': '"broken"'}), 412)
        self.assertHttp(mutator({'if-none-match': self.etag}), 412)
        r = mutator({'if-match': self.etag})
        self.assertHttp(r, status)
        self.etag = self.get_etag()
        self.assertEqual(r.headers['etag'], self.etag)
        self._get_check(304, nomatch=['etag'])

class PreconditionData2 (PreconditionData1):
    # run this whole sequence twice...
    pass

if __name__ == '__main__':
    unittest.main(verbosity=2)
