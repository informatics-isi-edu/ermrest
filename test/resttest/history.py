
import unittest
import common
from common import catalog_initial_version, primary_client_id, urlquote
import basics
import data
from data import _T1, _T2, _Tc2, _T2b
import json

_S = 'history_read'
_defs = basics.defs(_S)
_table_defs = _defs['schemas'][_S]['tables']
_model = None

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
    global _model
    r = common.primary_session.get('schema/%s' % _S)
    if r.status_code == 404:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()
        common.primary_session.post('entity/%s:%s' % (_S, _T1), json=data.BasicKey._initial).raise_for_status()
        common.primary_session.post('entity/%s:%s' % (_S, _T2), json=data.ForeignKey.data).raise_for_status()
        _data_t0_version = common.primary_session.get('').json()['snaptime']
        common.primary_session.delete('schema/%s/table/%s/column/name' % (_S, _T1)).raise_for_status()
        _data_t1_version = common.primary_session.get('').json()['snaptime']
        common.primary_session.delete('schema/%s/table/%s/column/name' % (_S, _T2)).raise_for_status()
        _data_t2_version = common.primary_session.get('').json()['snaptime']
        common.primary_session.delete('entity/%s:%s' % (_S, _T2)).raise_for_status()
        _data_t3_version = common.primary_session.get('').json()['snaptime']
        common.primary_session.delete('entity/%s:%s' % (_S, _T1)).raise_for_status()
        _data_t4_version = common.primary_session.get('').json()['snaptime']
        r = common.primary_session.get('schema')
        r.raise_for_status()
        _model = r.json()

class CatalogWhen (common.ErmrestTest):
    container_resource = ''
    annotation_resource = 'annotation'
    
    latest = None

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
        cls.latest = r.json()['snaptime']

    def test_at_latest(self):
        r = self.session.get((self.latest, self.container_resource))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(self.latest, r.json()['snaptime'])
        return r

    def test_at_earliest(self):
        r = self.session.get((catalog_initial_version, self.container_resource))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(catalog_initial_version, r.json()['snaptime'])
        return r

    def test_no_put_annotation(self):
        self.assertHttp(self.session.put((catalog_initial_version, '%s/HISTORY' % self.annotation_resource), json=[]), 403)

    def test_no_delete_annotation(self):
        self.assertHttp(self.session.delete((catalog_initial_version, '%s/HISTORY' % self.annotation_resource)), 403)

class ModelWhen (CatalogWhen):
    container_resource = 'schema'
    
    def test_annotation_at_latest(self):
        r = self.test_at_latest()
        self.assertIn('HISTORY', r.json()['annotations'])

    def test_annotation_at_earliest(self):
        r = self.test_at_earliest()
        self.assertNotIn('HISTORY', r.json()['annotations'])

    def test_no_post_schema(self):
        self.assertHttp(self.session.post((catalog_initial_version, self.container_resource), json=[]), 403)

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

def _add_history_probes(klass):
    ridfuncs = {
        'catalog': lambda m: None,
        'schema': lambda m: m['schemas'][_S]['RID'],
        'table': lambda m: m['schemas'][_S]['tables'][_T2b]['RID'],
        'ridcol': lambda m: m['schemas'][_S]['tables'][_T2b]['column_definitions'][0]['RID'],
        'namecol': lambda m: m['schemas'][_S]['tables'][_T2b]['column_definitions'][8]['RID'],
        'key': lambda m: m['schemas'][_S]['tables'][_T2b]['keys'][0]['RID'],
        'fkey': lambda m: m['schemas'][_S]['tables'][_T2b]['foreign_keys'][0]['RID'],
    }

    def _add_good_probe(phase, api, ridkey):
        def _test(self):
            self._probe_test(api, ridfuncs[ridkey](_model))
        setattr(klass, 'test_phase%d_probe_%s_%s' % (phase, ridkey, api or 'history'), _test)

    def _add_good_amendment(phase, api, ridkey, amendment):
        def _test(self):
            self._amend_test(api, ridfuncs[ridkey](_model), amendment)
        setattr(klass, 'test_phase%d_amend_%s_%s' % (phase, ridkey, api), _test)

    def _add_good_redaction(phase, cridkey, fridkey, fval):
        def _test(self):
            self._redact_test(ridfuncs[cridkey](_model), ridfuncs[fridkey](_model) if fridkey else None, fval)
        setattr(klass, 'test_phase%d_redact_t%s_f%s' % (phase, cridkey, fridkey or 'all'), _test)

    def _add_conflict_amendment(phase, api, ridkey, amendment):
        def _test(self):
            r = self.session.get(self.url(api, ridfuncs[ridkey](_model)))
            r_from, r_until = r.json()['snaprange']
            self.assertHttp(self.session.put(self.url(api, ridfuncs[ridkey](_model), r_from, r_until), json=amendment), 409)
        setattr(klass, 'test_phase%d_amendconflict_%s_%s' % (phase, ridkey, api), _test)

    def _add_bad_amendment(phase, api, ridkey, amendment):
        def _test(self):
            r = self.session.get(self.url(api, ridfuncs[ridkey](_model)))
            r_from, r_until = r.json()['snaprange']
            self.assertHttp(self.session.put(self.url(api, ridfuncs[ridkey](_model), r_from, r_until), json=amendment), 400)
        setattr(klass, 'test_phase%d_amendbad_%s_%s' % (phase, ridkey, api), _test)

    def _add_conflict_redaction(phase, cridkey):
        def _test(self):
            self._redact_test(ridfuncs[cridkey](_model), ridfuncs[fridkey](_model) if fridkey else None, fval, 409)
        setattr(klass, 'test_phase%d_redactconflict_t%s' % (phase, cridkey), _test)

    # phase 0: good probes
    _add_good_probe(0, None, 'catalog')

    for ridkey in ['catalog', 'schema', 'table', 'ridcol', 'namecol', 'key', 'fkey']:
        _add_good_probe(0, 'annotation', ridkey)

    for ridkey in ['catalog', 'schema', 'table', 'ridcol', 'namecol', 'fkey']:
        _add_good_probe(0, 'acl', ridkey)

    for ridkey in ['table', 'ridcol', 'namecol', 'fkey']:
        _add_good_probe(0, 'acl_binding', ridkey)

    # phase 1: bad modifications
    for ridkey in ['catalog', 'schema', 'table', 'ridcol', 'namecol', 'key', 'fkey']:
        _add_bad_amendment(1, 'annotation', ridkey, "not an annotations object")

    for ridkey in ['catalog', 'schema', 'table', 'ridcol', 'namecol', 'fkey']:
        _add_conflict_amendment(1, 'acl', ridkey, {"nonacl": []})

    for ridkey in ['catalog', 'schema', 'table', 'ridcol', 'namecol', 'fkey']:
        _add_bad_amendment(1, 'acl', ridkey, "not an ACL object")

    for ridkey in ['table', 'ridcol', 'namecol', 'fkey']:
        _add_bad_amendment(1, 'acl_binding', ridkey, "not an ACL bindings object")

    _add_conflict_redaction(1, 'ridcol')

    # phase 2: good amendments
    for ridkey in ['catalog', 'schema', 'table', 'ridcol', 'namecol', 'key', 'fkey']:
        _add_good_amendment(2, 'annotation', ridkey, {"URI1": False, "URI2": "amended string"})

    for ridkey in ['catalog', 'schema', 'table']:
        _add_good_amendment(2, 'acl', ridkey, {"owner": [primary_client_id], "select": ["*"]})

    for ridkey in ['ridcol', 'namecol']:
        _add_good_amendment(2, 'acl', ridkey, {"write": [primary_client_id], "select": ["*"]})

    _add_good_amendment(2, 'acl', 'fkey',  {"write": [primary_client_id]})

    for ridkey in ['table', 'ridcol', 'namecol', 'fkey']:
        _add_good_amendment(2, 'acl_binding', ridkey, {'amendeddynacl': False})

    # phase 3: good redactions
    for fridkey, fval in [ ('namecol', "foo"), ('ridcol', 5000), (None, None) ]:
        _add_good_redaction(3, 'namecol', fridkey, fval)

    return klass

@_add_history_probes
class ZHistory (common.ErmrestTest):
    # Z prefix to run test class last in alphabetic order...

    @staticmethod
    def url(api=None, rid=None, hfrom=None, huntil=None, suffix=''):
        url = 'history/%s,%s' % (hfrom or '', huntil or '')
        if api is not None:
            url += '/%s' % api
            if rid is not None:
                url += '/%s' % rid
        return url + suffix

    def _probe_test(self, api, rid):
        self.assertHttp(common.secondary_session.get(self.url(api, rid, None, None)), 403)
        r = self.session.get(self.url(api, rid, None, None))
        self.assertHttp(r, 200, 'application/json')
        h = r.json()
        self.assertEqual(h['amendver'], None)
        r_from, r_until = h['snaprange']
        r = self.session.get(self.url(api, rid, r_from, r_until))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(r.json()['snaprange'], [r_from, r_until])

    def _amend_test(self, api, rid, amendment):
        r = self.session.get(self.url(api, rid, None, None))
        self.assertHttp(r, 200, 'application/json')
        r_from, r_until = r.json()['snaprange']
        self.assertHttp(common.secondary_session.put(self.url(api, rid, r_from, r_until), json=amendment), 403)
        self.assertHttp(self.session.put(self.url(api, rid, r_from, r_until), json=amendment), 204)

    def _redact_test(self, crid, frid, fval, status=204):
        r = self.session.get(self.url('attribute', crid, None, None))
        self.assertHttp(r, 200, 'application/json')
        r1 = r.json()['snaprange']
        if frid is not None:
            r = self.session.get(self.url('attribute', frid, None, None))
            self.assertHttp(r, 200, 'application/json')
            r2 = r.json()['snaprange']
            r_from = max(r1[0], r2[0])
            r_until = min(r1[1], r2[1])
            suffix = '/%s=%s' % (frid, urlquote(json.dumps(fval)))
        else:
            r_from, r_until = r1
            suffix = ''
        self.assertHttp(common.secondary_session.delete(self.url('attribute', crid, r_from, r_until, suffix)), 403)
        self.assertHttp(self.session.delete(self.url('attribute', crid, r_from, r_until, suffix)), status)

    def test_phase4_truncate(self):
        r = self.session.get(self.url())
        when = r.json()['snaprange'][1]
        when = when[0:-4] + '0000'
        self.assertHttp(self.session.delete(self.url(huntil=when)), 204)
        self.assertHttp(self.session.delete(self.url(huntil=when)), (404, 409))

if __name__ == '__main__':
    unittest.main(verbosity=2)
