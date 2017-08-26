
import unittest
import common
import basics

_S = 'anno'
_defs = basics.defs(_S)
_T1 = basics._T1
_T2b = basics._T2b

def setUpModule():
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()

def _merge(d1, d2):
    d = dict(d1)
    d.update(d2)
    return d

class AnnotationCatalog (common.ErmrestTest):
    uri = 'annotation'

    state0 = {}

    state1 = {
        'tag:misd.isi.edu,2015:test1': 'test 1',
        'tag:misd.isi.edu,2015:test2': 'test 2',
    }

    state2 = {
        'tag:misd.isi.edu,2015:test1': 'test 1',
        'tag:misd.isi.edu,2015:test2': 'test 2',
        'tag:misd.isi.edu,2015:test3': 'test 3',
    }

    def _set_bulk(self, newstate):
        self.assertHttp(self.session.put(self.uri, json=newstate), 204)

    def _set_each(self, newstate):
        for k, value in newstate.items():
            self.assertHttp(self.session.put('%s/%s' % (self.uri, common.urlquote(k)), json=value), [201, 204])

    def _check_bulk(self, state):
        r = self.session.get(self.uri)
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json(), state)

    def _check_each(self, state):
        for k, value in state.items():
            r = self.session.get('%s/%s' % (self.uri, common.urlquote(k)))
            self.assertHttp(r, 200, 'application/json')
            self.assertEqual(r.json(), value)

    def test_0_bulk_clear(self):
        self._set_bulk(self.state0)
        self._check_bulk(self.state0)

    def test_1_bulk_set(self):
        self._set_bulk(self.state1)
        self._check_bulk(self.state1)
        self._check_each(self.state1)

    def test_2_set_each(self):
        self._set_each(self.state2)
        self._check_bulk(_merge(self.state1, self.state2))
        self._check_bulk(_merge(self.state1, self.state2))

    def test_3_delete(self):
        for k in _merge(self.state1, self.state2):
            self.assertHttp(self.session.delete('%s/%s' % (self.uri, common.urlquote(k))), 204)
        self._check_bulk({})

class AnnotationSchema (AnnotationCatalog):
    uri = 'schema/%s/annotation' % (_S,)

class AnnotationTable (AnnotationCatalog):
    uri = 'schema/%s/table/%s/annotation' % (_S, _T2b)

class AnnotationColumn (AnnotationCatalog):
    uri = 'schema/%s/table/%s/column/id/annotation' % (_S, _T2b)

class AnnotationKey (AnnotationCatalog):
    uri = 'schema/%s/table/%s/key/id/annotation' % (_S, _T2b)

class AnnotationFKey (AnnotationCatalog):
    uri = 'schema/%s/table/%s/foreignkey/level1_id1/reference/%s:%s/id/annotation' % (_S, _T2b, _S, _T1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
