
import re
import unittest
import requests

import common

_S = 'indexing'
_T0 = 'minimal'
_T1 = 'alltypes'

from common import urlquote, RID, RCT, RMT, RCB, RMB, RidKey, \
    ModelDoc, SchemaDoc, TableDoc, ColumnDoc, KeyDoc, FkeyDoc

def defs(S):
    # these table definitions get reused in multiple test modules under different per-module schema
    return ModelDoc(
        [
            SchemaDoc(
                S,
                [
                    TableDoc(
                        _T0,
                        [ RID, RCT, RMT, RCB, RMB, ColumnDoc('value', common.Text) ],
                        [ RidKey ],
                        [],
                        {
                            "tag:isrd.isi.edu,2018:indexing-preferences": {
                                "btree": False,
                                "trgm": False,
                                "gin_array": False,
                            }
                        },
                    ),
                    TableDoc(
                        _T1,
                        [
                            RID, RCT, RMT, RCB, RMB,
                        ] + [
                            ColumnDoc(f"c_{typdoc['typename']}", typdoc)
                            for typdoc in [
                                    common.Text,
                                    common.Ermrest_uri,
                                    common.Int8,
                                    common.Serial8,
                                    common.Timestamptz,
                                    common.Json,
                                    common.Jsonb,
                                    common.Int4Array,
                                    common.TextArray,
                                    common.TimestamptzArray,
                                    common.JsonArray,
                                    common.JsonbArray,
                            ]
                        ] + [
                            ColumnDoc(f"was_{typdoc['typename']}", typdoc)
                            for typdoc in [
                                    common.Text,
                                    common.Ermrest_uri,
                                    common.Int8,
                                    common.Serial8,
                                    common.Timestamptz,
                                    common.Json,
                                    common.Jsonb,
                                    common.Int4Array,
                                    common.TextArray,
                                    common.TimestamptzArray,
                                    common.JsonArray,
                                    common.JsonbArray,
                            ]
                        ],
                        [ RidKey ],
                        [],
                        {
                            "tag:isrd.isi.edu,2018:indexing-preferences": {
                                "btree": True,
                                "trgm": True,
                                "gin_array": True,
                            }
                        },
                    ),
                ],
                {"tag:misd.isi.edu,2015:test0": "value 0"}
            )
        ],
        {"tag:misd.isi.edu,2015:test0": "value 0"}
    )

_defs = defs(_S)
_table_defs = _defs['schemas'][_S]['tables']
_T1_column_defs = _table_defs[_T1]['column_definitions']

_data_T0 = [
    {"value": v}
    for v in ["a", "b", "c", "one", "two", "three"]
]

_data_T1 = [
    {
        "c_text": f"text {i}",
        "c_ermrest_uri": f"https://example.com/id/{i}",
        "c_int8": f"{i}",
        # skip c_serial8
        "c_timestamptz": f"20210102T0304.0{i}+0000",
        "c_json": {"i": i},
        "c_jsonb": {"ib": i, "it": f"{i}"},
        "c_int4[]": [ i+c for c in range(10,100,10) ],
        "c_text[]": [ f"value {i+c}" for c in range(10,100,10) ],
        "c_timestamptz[]": [ f"20210102T0304.{c}{i}+0000" for c in range(10,60,10) ],
        "c_json[]": [ {"i": i+c} for c in range(10,100,10) ],
        "c_jsonb[]": [ {"ib": i+c, "it": f"{i+c}"} for c in range(10,100,10) ],
        #
        "was_text": f"text {i}",
        "was_ermrest_uri": f"https://example.com/id/{i}",
        "was_int8": f"{i}",
        # skip was_serial8
        "was_timestamptz": f"20210102T0304.0{i}+0000",
        "was_json": {"i": i},
        "was_jsonb": {"ib": i, "it": f"{i}"},
        "was_int4[]": [ i+c for c in range(10,100,10) ],
        "was_text[]": [ f"value {i+c}" for c in range(10,100,10) ],
        "was_timestamptz[]": [ f"20210102T0304.{c}{i}+0000" for c in range(10,60,10) ],
        "was_json[]": [ {"i": i+c} for c in range(10,100,10) ],
        "was_jsonb[]": [ {"ib": i+c, "it": f"{i+c}"} for c in range(10,100,10) ],
    }
    for i in range(10)
]

_model_schema = None
_model_T0_RID = None
_model_T0_col_RID = None
_model_T1_RID = None
_model_T1_col_RID = None
_model_T1_column_defs = None
_model_T1_column_defs_byname = None

def setUpModule():
    # this setup covers a bunch of indexing feature tests
    # but we put them here so they are shared fixtures for the rest of the detailed feature tests below...
    global _model_schema
    global _model_T0_RID
    global _model_T0_col_RID
    global _model_T1_RID
    global _model_T1_col_RID
    global _model_T1_column_defs
    global _model_T1_column_defs_byname
    if _model_schema is None:
        # idempotent because unittest can re-enter module several times...
        common.primary_session.post('schema', json=_defs).raise_for_status()
        common.primary_session.post(f"entity/{_S}:{_T0}", json=_data_T0).raise_for_status()
        common.primary_session.post(f"entity/{_S}:{_T1}?defaults=c_serial8,was_serial8", json=_data_T1).raise_for_status()

        # alter columns was_* -> to type text/text[]
        for cdef in _T1_column_defs:
            if cdef['name'].startswith('was_'):
                common.primary_session.put(
                    f"schema/{_S}/table/{_T1}/column/{urlquote(cdef['name'])}",
                    json={
                        "type": common.TextArray if cdef['name'].endswith('[]') else common.Text,
                        "comment": "column after altering to text type"
                    }
                ).raise_for_status()

        _model_schema = common.primary_session.get('schema/%s' % _S).json()
        _model_T0_RID = _model_schema['tables'][_T0]['RID']
        _model_T0_col_RID = _model_schema['tables'][_T0]['column_definitions'][0]["RID"]
        _model_T1_RID = _model_schema['tables'][_T1]['RID']
        _model_T1_col_RID = _model_schema['tables'][_T1]['column_definitions'][0]["RID"]
        _model_T1_column_defs = _model_schema['tables'][_T1]['column_definitions']
        _model_T1_column_defs_byname = {
            cdef['name']: cdef
            for cdef in _model_T1_column_defs
        }

def _is_special(idoc):
    return idoc["primary"] or idoc["unique"] or idoc["exclusion"]

def _find_special(idocs, cname='RID'):
    for doc in idocs:
        if _is_special(doc):
            return doc

class AsProvisioned (common.ErmrestTest):

    def test_api_basics(self):
        r = self.session.get(f"schema/{_S}/table/{_T0}/index/")
        self.assertHttp(r, 200, "application/json")
        d = r.json()
        self.assertIsInstance(d, list)

        with self.subTest(scenario="structure_check"):
            self.assertGreaterEqual(len(d), 1)
            for field in ["schemaname", "indexname", "primary", "unique", "exclusion", "sqldef"]:
                with self.subTest(field=field):
                    for doc in d:
                        self.assertIn(field, doc)

        pkey = _find_special(d)
        with self.subTest(scenario="pkey_present"):
            self.assertIsNotNone(pkey)

        with self.subTest(scenario="pkey_retrieval"):
            self.assertIsNotNone(pkey)
            r = self.session.get(f"schema/{_S}/table/{_T0}/index/{pkey['indexname']}")
            self.assertHttp(r, 200, "application/json")

    def test_history_api_basics(self):
        t0_rid = _model_schema["tables"][_T0]["RID"]
        d = None
        with self.subTest(scenario=f"history table index listing"):
            r = self.session.get(f"history/table/{t0_rid}/index/")
            self.assertHttp(r, 200, "application/json")
            d = r.json()
            self.assertIsInstance(d, list)
        if d:
            with self.subTest(scenario="history index retrieval"):
                iname = d[0]["indexname"]
                r = self.session.get(f"history/table/{t0_rid}/index/{iname}")
                self.assertHttp(r, 200, "application/json")

    def test_list_hinted_t0(self):
        # indexing-preferences hint is all false on T0
        r = self.session.get(f"schema/{_S}/table/{_T0}/index/")
        self.assertHttp(r, 200, "application/json")
        d = r.json()
        # expect only the RID key index
        self.assertEqual(len(d), 1)
        self.assertTrue(d[0]["unique"], d)

    def test_list_hinted_t1(self):
        # indexing-preferences hint is all true on T1
        r = self.session.get(f"schema/{_S}/table/{_T1}/index/")
        self.assertHttp(r, 200, "application/json")
        d = r.json()
        # examine the non-key indexes
        nonkeys = [ doc for doc in d if not _is_special(doc) ]
        # expect a lot, but don't be overly prescriptive
        self.assertGreater(len(nonkeys), 12)
        # check for different index types
        num_btree = 0
        num_gin_trgm = 0
        num_gin_array = 0
        for doc in nonkeys:
            if re.search("USING btree", doc["sqldef"]):
                num_btree += 1
            elif re.search("USING gin [(].*gin_trgm_ops.*[)]", doc["sqldef"]):
                num_gin_trgm += 1
            elif re.search("USING gin.*[(].*[[][]].*[)]", doc["sqldef"]):
                num_gin_array += 1
        with self.subTest(scenario='has_btree'):
            self.assertGreater(num_btree, 0)
        with self.subTest(scenario='has_trgm'):
            self.assertGreater(num_gin_trgm, 0)
        with self.subTest(scenario='has_gin_array'):
            self.assertGreater(num_gin_array, 0)

    def test_key_nondelete(self):
        r = self.session.get(f"schema/{_S}/table/{_T0}/index/")
        self.assertHttp(r, 200, "application/json")
        d = r.json()
        pkey = _find_special(d)
        r = self.session.delete(f"schema/{_S}/table/{_T0}/index/{pkey['indexname']}")
        self.assertHttp(r, 403)

    def test_nonkey_delete(self):
        r = self.session.get(f"schema/{_S}/table/{_T0}/index/")
        self.assertHttp(r, 200, "application/json")
        d = r.json()
        nonkeys = [ doc for doc in d if not _is_special(doc) ]
        for i in range(len(nonkeys)):
            with self.subTest(iname=nonkeys[i]["indexname"]):
                r = self.session.delete(f"schema/{_S}/table/{_T0}/index/{nonkeys[i]['indexname']}")
                self.assertHttp(r, 204)

    def test_key_nondelete_history(self):
        t0_rid = _model_schema["tables"][_T0]["RID"]
        r = self.session.get(f"history/table/{t0_rid}/index/")
        self.assertHttp(r, 200, "application/json")
        d = r.json()
        self.assertIsInstance(d, list)
        self.assertTrue(d)
        iname = d[0]["indexname"]
        r = self.session.delete(f"history/table/{t0_rid}/index/{iname}")
        self.assertHttp(r, 403)

class Explicit (common.ErmrestTest):

    good_defs = {
        f"{_T1}_btree_{cdef['name']}_idx": {"btree": cdef['name']}
        for cdef in _T1_column_defs
        if (
                cdef['name'].startswith('c_')
                and cdef['name'] not in ['c_json', 'c_json[]']
        )
    } | {
        f"{_T1}_btree_c_text_RID_idx": {"btree": ["c_text", "RID"]}
    } | {
        f"{_T1}_trgm_{cdef['name']}_idx": {"trgm": cdef['name']}
        for cdef in _T1_column_defs
        if cdef['name'].startswith('c_')
    } | {
        f"{_T1}_array_{cdef['name']}_idx": {"gin_array": cdef['name']}
        for cdef in _T1_column_defs
        if (
                cdef['name'].startswith('c_')
                and cdef['name'].endswith('[]')
                and cdef['name'] not in ['c_json', 'c_json[]']
        )
    }

    def test_absent(self):
        for iname in self.good_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.get(f"schema/{_S}/table/{_T1}/index/{iname}")
                self.assertHttp(r, 404)

    def test_create_good(self):
        for iname in self.good_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.put(f"schema/{_S}/table/{_T1}/index/{iname}", json=self.good_defs[iname])
                self.assertHttp(r, 200, "application/json")

    def test_create_key_overwrite_forbidden(self):
        # cannot use index name already active with a key constraint
        r = self.session.get(f"schema/{_S}/table/{_T0}/index/")
        pkey = _find_special(r.json())
        iname = pkey['indexname']
        idef = {"btree": "value"}
        r = self.session.put(f"schema/{_S}/table/{_T0}/index/{iname}", json=idef)
        self.assertHttp(r, 403)

    def test_create_nonlocal_conflict(self):
        # cannot use index name already active on a different table!
        iname = f"{_T1}_btree_c_text_idx"
        idef = {"btree": "value"}
        r = self.session.put(f"schema/{_S}/table/{_T0}/index/{iname}", json=idef)
        self.assertHttp(r, 409)

    def test_create_visible(self):
        for iname in self.good_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.get(f"schema/{_S}/table/{_T1}/index/{iname}")
                self.assertHttp(r, 200, "application/json")

    def test_delete_created(self):
        for iname in self.good_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.delete(f"schema/{_S}/table/{_T1}/index/{iname}")
                self.assertHttp(r, 204)

    bad_defs = {
        "nonobject_string": "foo",
        "nonobject_list": ["foo"],
        "unknown_index_type": {"foo": "RID"},
        "multi_index_type": {"btree": "RID", "trgm": "RID"},
        "btree_json": {"btree": "c_json"},
        "btree_json[]": {"btree": "c_json[]"},
        "btree_unknown": {"btree": "NOT A COLUMN"},
        "btree_compound_unknown": {"btree": ["RID", "NOT A COLUMN"]},
        "btree_empty_compound": {"btree": []},
        "trgm_compound": {"trgm": ["c_text", "RID"]},
        "array_nonarray": {"gin_array": "c_text"},
        "array_compound": {"gin_array": ["c_text[]", "c_int4[]"]},
        "array_json[]": {"gin_array": "c_json[]"},
    }

    def test_nocreate_bad(self):
        for iname in self.bad_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.put(f"schema/{_S}/table/{_T1}/index/{iname}")
                self.assertHttp(r, 400)

class ExplicitHistory (common.ErmrestTest):

    def good_defs(self):
        return {
            f"t{_model_T1_RID}_btree_{cdef['name']}_idx": {"btree": cdef['RID']}
            for cdef in _model_T1_column_defs
            if (
                    cdef['name'].startswith('c_')
                    and cdef['name'] not in ['c_json', 'c_json[]']
            )
        } |{
            f"t{_model_T1_RID}_btree_{cdef['name']}_idx": {"btree": cdef['RID']}
            for cdef in _model_T1_column_defs
            if (
                    cdef['name'].startswith('was_text')
            )
        } | {
            f"t{_model_T1_RID}_compound_btree_idx": {
                "btree": [
                    cdef["RID"]
                    for cdef in _model_T1_column_defs[0:10]
                ]
            }
        } | {
            f"t{_model_T1_RID}_trgm_{cdef['name']}_idx": {"trgm": cdef['RID']}
            for cdef in _model_T1_column_defs
            if cdef['name'].startswith('c_')
        } | {
            f"t{_model_T1_RID}_array_{cdef['name']}_idx": {"gin_array": cdef['RID']}
            for cdef in _model_T1_column_defs
            if (
                    cdef['name'].startswith('c_')
                    and cdef['name'].endswith('[]')
                    and cdef['name'] != 'c_json[]'
            )
        }

    def test_absent(self):
        good_defs = self.good_defs()
        for iname in good_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.get(f"history/table/{_model_T1_RID}/index/{iname}")
                self.assertHttp(r, 404)

    def test_create_good(self):
        good_defs = self.good_defs()
        for iname, idef in good_defs.items():
            with self.subTest(iname=iname):
                r = self.session.put(f"history/table/{_model_T1_RID}/index/{iname}", json=idef)
                self.assertHttp(r, 200, "application/json")

    def test_create_key_overwrite_forbidden(self):
        # cannot use index name already active with a key constraint
        r = self.session.get(f"history/table/{_model_T1_RID}/index/")
        pkey = _find_special(r.json())
        iname = pkey['indexname']
        idef = {"btree": _model_T1_col_RID}
        r = self.session.put(f"history/table/{_model_T1_RID}/index/{iname}", json=idef)
        self.assertHttp(r, 403)

    def test_create_nonlocal_conflict(self):
        # cannot use index name already active on a different table!
        r = self.session.get(f"history/table/{_model_T1_RID}/index/")
        pkey = _find_special(r.json())
        iname = pkey['indexname']
        idef = {"btree": _model_T0_col_RID}
        r = self.session.put(f"history/table/{_model_T0_RID}/index/{iname}", json=idef)
        self.assertHttp(r, 409)

    def test_create_visible(self):
        good_defs = self.good_defs()
        for iname in good_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.get(f"history/table/{_model_T1_RID}/index/{iname}")
                self.assertHttp(r, 200, "application/json")

    def test_delete_created(self):
        good_defs = self.good_defs()
        for iname in good_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.delete(f"history/table/{_model_T1_RID}/index/{iname}")
                self.assertHttp(r, 204)

    def test_nocreate_bad(self):
        bad_defs = {
            "nonobject_string": "foo",
            "nonobject_list": ["foo"],
            "unknown_index_type": {"foo": _model_T1_col_RID},
            "multi_index_type": {"btree": _model_T1_col_RID, "trgm": _model_T1_col_RID},
            "btree_json": {"btree": _model_T1_column_defs_byname["c_json"]["RID"]},
            "btree_json[]": {"btree": _model_T1_column_defs_byname["c_json[]"]["RID"]},
            "btree_unknown": {"btree": "NOT-A-COL-RID"},
            "btree_compound_unknown": {"btree": [_model_T1_col_RID, "NOT-A-COL-RID"]},
            "btree_empty_compound": {"btree": []},
            "trgm_compound": {"trgm": [_model_T1_col_RID]},
            "array_nonarray": {"gin_array": _model_T1_col_RID},
            "array_compound": {"gin_array": [
                _model_T1_column_defs_byname["c_text[]"]["RID"],
                _model_T1_column_defs_byname["c_int4[]"]["RID"],
            ]},
            "array_json[]": {"gin_array": _model_T1_column_defs_byname["c_json[]"]["RID"]},
        } | {
            f"btree_{cdef['name']}_idx": {"btree": cdef["RID"]}
            for cdef in _model_T1_column_defs
            if (
                    cdef['name'].startswith('was_')
                    and not cdef['name'].startswith('was_text')
            )
        } | {
            f"btree_{cdef['name']}_idx": {"trgm": cdef["RID"]}
            for cdef in _model_T1_column_defs
            if (
                    cdef['name'].startswith('was_')
                    and not cdef['name'].startswith('was_text')
            )
        } | {
            f"btree_{cdef['name']}_idx": {"gin_array": cdef["RID"]}
            for cdef in _model_T1_column_defs
            if (
                    cdef['name'].startswith('was_')
                    and cdef['name'].endswith('[]')
                    and not cdef['name'].startswith('was_text')
            )
        }

        for iname in bad_defs.keys():
            with self.subTest(iname=iname):
                r = self.session.put(f"history/table/{_model_T1_RID}/index/{iname}")
                self.assertHttp(r, (400, 409))

if __name__ == '__main__':
    unittest.main(verbosity=2)
