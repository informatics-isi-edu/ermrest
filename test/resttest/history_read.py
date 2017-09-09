
import unittest
import common
from common import catalog_initial_version
import basics
import data
from data import _T1, _T2, _Tc2, _T2b

_S = 'history_read'
_defs = basics.defs(_S)
_table_defs = _defs['schemas'][_S]['tables']

_data_t0_version = None
_data_t1_version = None
_data_t2_version = None
_data_t3_version = None
_data_t4_version = None

def setUpModule():
    global _data_t0_version
    global _data_t1_version
    global _data_t2_version
    global _data_t3_version
    global _data_t4_version
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()
        common.primary_session.post('entity/%s:%s' % (_S, _T1), json=data.BasicKey._initial).raise_for_status()
        common.primary_session.post('entity/%s:%s' % (_S, _T2), json=data.ForeignKey.data).raise_for_status()
        _data_t0_version = common.primary_session.get('').json()['version']
        common.primary_session.delete('schema/%s/table/%s/column/name' % (_S, _T1)).raise_for_status()
        _data_t1_version = common.primary_session.get('').json()['version']
        common.primary_session.delete('schema/%s/table/%s/column/name' % (_S, _T2)).raise_for_status()
        _data_t2_version = common.primary_session.get('').json()['version']
        common.primary_session.delete('entity/%s:%s' % (_S, _T2)).raise_for_status()
        _data_t3_version = common.primary_session.get('').json()['version']
        common.primary_session.delete('entity/%s:%s' % (_S, _T1)).raise_for_status()
        _data_t4_version = common.primary_session.get('').json()['version']

class CatalogWhen (common.ErmrestTest):
    container_resource = ''
    annotation_resource = 'annotation'
    
    latest = None
    earliest = catalog_initial_version

    @classmethod
    def setUpClass(cls):
        # make sure catalog version is higher now
        common.primary_session.put(
            '%s/HISTORY' % cls.annotation_resource,
            json=cls.container_resource
        ).raise_for_status()
        # bootstrap catalog version info
        r = common.primary_session.get('')
        r.raise_for_status()
        cls.latest = r.json()['version']

    def test_at_latest(self):
        r = self.session.get((self.latest, self.container_resource))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(self.latest, r.json()['version'])
        return r

    def test_at_earliest(self):
        r = self.session.get((self.earliest, self.container_resource))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(self.earliest, r.json()['version'])
        return r

    def test_no_put_annotation(self):
        self.assertHttp(self.session.put((self.earliest, '%s/HISTORY' % self.annotation_resource), json=[]), 403)

    def test_no_delete_annotation(self):
        self.assertHttp(self.session.delete((self.earliest, '%s/HISTORY' % self.annotation_resource)), 403)

class ModelWhen (CatalogWhen):
    container_resource = 'schema'
    
    def test_annotation_at_latest(self):
        r = self.test_at_latest()
        self.assertIn('HISTORY', r.json()['annotations'])

    def test_annotation_at_earliest(self):
        r = self.test_at_earliest()
        self.assertNotIn('HISTORY', r.json()['annotations'])

    def test_no_post_schema(self):
        self.assertHttp(self.session.post((self.earliest, self.container_resource), json=[]), 403)

class TableWhen (common.ErmrestTest):
    _entity_T1 = 'entity/%s:%s' % (_S, _T1)
    _entity_T2 = 'entity/%s:%s' % (_S, _T2)

    def _test_name_col(self, version, entity, expected_len, has_name_col):
        if expected_len:
            r = self.session.get((version, entity))
            self.assertHttp(r, 200, 'application/json')
            if has_name_col:
                self.assertIn('name', r.json()[0], 'name column missing at snapshot %s' % version)
            else:
                self.assertNotIn('name', r.json()[0])

    def _test_numrows(self, version, entity, expected_len):
        r = self.session.get((version, entity))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(expected_len, len(r.json()))

    def _test_snapshot(self, version, t1_expected_len, t2_expected_len, join_expected_len, t1_has_name, t2_has_name):
        self._test_numrows(version, self._entity_T1, t1_expected_len)
        self._test_numrows(version, self._entity_T2, t2_expected_len)
        self._test_name_col(version, self._entity_T1, t1_expected_len, t1_has_name)
        self._test_name_col(version, self._entity_T2, t2_expected_len, t2_has_name)

        r = self.session.get((version, 'aggregate/%s:%s/%s:%s/c:=cnt(*)' % (_S, _T1, _S, _T2)))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(join_expected_len, r.json()[0]['c'])

    def test_no_entity_post(self):
        self.assertHttp(self.session.post((_data_t0_version, self._entity_T1), json=[{}]), 403)

    def test_no_entity_put(self):
        self.assertHttp(self.session.put((_data_t0_version, self._entity_T1), json=[{}]), 403)

    def test_no_entity_delete(self):
        self.assertHttp(self.session.delete((_data_t0_version, self._entity_T1)), 403)

    def test_no_attributegroup_put(self):
        self.assertHttp(self.session.put((_data_t0_version, 'attributegroup/%s:%s/id;name' % (_S, _T1)), json=[{}]), 403)

    def test_no_attribute_delete(self):
        self.assertHttp(self.session.delete((_data_t0_version, 'attribute/%s:%s/name' % (_S, _T1))), 403)

    def test_initial_filled(self):
        self._test_snapshot(_data_t0_version, 4, 5, 4, True, True)

    def test_T1col_deleted(self):
        self._test_snapshot(_data_t1_version, 4, 5, 4, False, True)

    def test_T2col_deleted(self):
        self._test_snapshot(_data_t2_version, 4, 5, 4, False, False)

    def test_one_emptied(self):
        self._test_snapshot(_data_t3_version, 4, 0, 0, False, False)

    def test_both_emptied(self):
        self._test_snapshot(_data_t4_version, 0, 0, 0, False, False)

    def test_schema_not_found(self):
        self.assertHttp(self.session.get((catalog_initial_version, 'entity/%s:%s' % (_S, _T1))), 409)

if __name__ == '__main__':
    unittest.main(verbosity=2)
