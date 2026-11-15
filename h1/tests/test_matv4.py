"""Synthetic MATv4 byte-level semantics; never native exporter qualification."""
import csv
import io
import json
from pathlib import Path
import unittest

import numpy as np
from scipy.io import savemat

from h1.matv4 import decode_mat_bytes
from h1.model import Refusal, internal_exports
from h1.study import load_study
from h1.reference import read_reference, prepare
from h1.verification import check_candidate, candidate_receipt

ROOT = Path(__file__).resolve().parents[2]


def chars(lines):
    width = max(len(s) for s in lines)
    a = np.full((len(lines), width), b'\x00', dtype='S1')
    for row, text in enumerate(lines):
        a[row, :len(text)] = [bytes([ord(c)]) for c in text]
    return a


def make_mat(names, inf, d1, d2, trans=False, v5=False, native_layout=False):
    ac = chars(['Atrajectory', '1.1', '', 'binTrans' if trans else 'binNormal'])
    data = {'Aclass': ac, 'name': chars(names), 'description': chars(['native result'] * len(names)),
            'dataInfo': np.array(inf, dtype=np.int32),
            'data_1': np.array(d1, dtype=np.float64),
            'data_2': np.array(d2, dtype=np.float64)}
    if trans:
        # OMC 1.27.0 observed: Aclass already has four logical rows, while
        # only name/description/dataInfo are transposed; numeric arrays are
        # already canonical in SciPy. Older/synthetic layouts may transpose all.
        keys = ('name', 'description', 'dataInfo') if native_layout else tuple(data)
        data = {k: (v.T if k in keys else v) for k, v in data.items()}
    stream = io.BytesIO()
    savemat(stream, data, format='5' if v5 else '4')
    return stream.getvalue()


NAMES = ['time', 'boundary.T', 'rod.A', 'rod.Q_flow', 'rod.port_a.Q_flow', 'rod.port_b.Q_flow']
INFO = [[0, 1, 0, -1], [1, 1, 0, -1], [1, 2, 0, -1],
        [2, 2, 0, -1], [2, 2, 0, -1], [2, -2, 0, -1]]
D1 = [[373.15, 373.15], [0.001, 0.001]]
D2 = [[0, 1, 1], [2.0, 2.0, 2.0]]
REQUIRED = tuple(NAMES[1:])


class MATv4Decoding(unittest.TestCase):
    def test_normal_and_transposed_deduplicate(self):
        for trans, native_layout in ((False, False), (True, False), (True, True)):
            with self.subTest(trans=trans, native_layout=native_layout):
                result = decode_mat_bytes(make_mat(NAMES, INFO, D1, D2, trans=trans,
                                                   native_layout=native_layout), REQUIRED, (0., 1.))
                self.assertEqual(result['matOrientation'], 'binTrans' if trans else 'binNormal')
                self.assertEqual(result['decoded']['duplicateRowsCollapsed'], 1)
                self.assertEqual(result['decoded']['columns']['rod.port_b.Q_flow'], (-2.0, -2.0))
                self.assertEqual(result['decoded']['columns']['boundary.T'], (373.15, 373.15))
                provenance = result['columnProvenance']
                self.assertEqual(provenance['boundary.T']['origin'], 'mat_parameter')
                self.assertEqual(provenance['rod.port_b.Q_flow']['matTable'], 'data_2')
                self.assertTrue(provenance['rod.port_b.Q_flow']['negatedAlias'])
                self.assertFalse(provenance['rod.port_a.Q_flow']['channelIsIndependentMeasurement'])
                self.assertEqual(provenance['rod.port_b.Q_flow']['sharedChannelNames'],
                                 ['rod.Q_flow', 'rod.port_a.Q_flow', 'rod.port_b.Q_flow'])
                self.assertFalse(result['nativeQualified'])
                self.assertEqual(result['rawMatSha256'], __import__('hashlib').sha256(
                    make_mat(NAMES, INFO, D1, D2, trans=trans,
                             native_layout=native_layout)).hexdigest())

    def assert_refused(self, data, expected=None, required=REQUIRED, grid=(0., 1.)):
        with self.assertRaises(Refusal) as err:
            decode_mat_bytes(data, required, grid)
        if expected:
            self.assertEqual(err.exception.code, expected)

    def test_missing_value_no_formula_fallback(self):
        self.assert_refused(make_mat(NAMES[:-1], INFO[:-1], D1, D2), 'result_schema')

    def test_reject_single_precision_parameter_storage(self):
        data = {'Aclass': chars(['Atrajectory','1.1','','binNormal']),
                'name': chars(NAMES), 'description': chars(['native result']*len(NAMES)),
                'dataInfo': np.array(INFO, dtype=np.int32),
                'data_1': np.array(D1, dtype=np.float32),
                'data_2': np.array(D2, dtype=np.float64)}
        stream = io.BytesIO(); savemat(stream, data, format='4')
        self.assert_refused(stream.getvalue(), 'mat_precision')

    def test_bad_signed_alias_index(self):
        info = [x[:] for x in INFO]; info[-1][1] = -9
        self.assert_refused(make_mat(NAMES, info, D1, D2), 'mat_schema')

    def test_zero_based_alias_index_refused(self):
        info = [x[:] for x in INFO]; info[-1][1] = 0
        self.assert_refused(make_mat(NAMES, info, D1, D2), 'mat_schema')

    def test_data1_first_row_time_bounds_are_not_a_parameter(self):
        info = [x[:] for x in INFO]
        info[1][1] = 2
        info[2][1] = 3
        data1 = [[0., 1.], *D1]
        result = decode_mat_bytes(make_mat(NAMES, info, data1, D2), REQUIRED, (0., 1.))
        self.assertEqual(result['decoded']['columns']['boundary.T'], (373.15, 373.15))
        self.assertEqual(result['columnProvenance']['boundary.T']['oneBasedRow'], 2)

    def test_parameter_endpoints_disagree(self):
        self.assert_refused(make_mat(NAMES, INFO, [[373.15, 373.14], D1[1]], D2), 'parameter_inconsistent')

    def test_time_duplicates_inconsistent_required_values(self):
        self.assert_refused(make_mat(NAMES, INFO, D1, [[0, 1, 1], [2, 2, 2.01]]), 'ambiguous_output')

    def test_wrong_mat_version_refused(self):
        self.assert_refused(make_mat(NAMES, INFO, D1, D2, v5=True), 'mat_schema')

    def test_invalid_time_association_refused(self):
        self.assert_refused(make_mat(NAMES, INFO, D1, [[0, 0.999, 0.999], [2,2,2]]), 'time_grid')

    def test_unexpected_schema_group_refused(self):
        inp = io.BytesIO(make_mat(NAMES, INFO, D1, D2))
        self.assert_refused(inp.getvalue() + b'trailing bad', 'mat_schema')

    def test_truncated_file_refused(self):
        inp = make_mat(NAMES, INFO, D1, D2)
        self.assert_refused(inp[:50], 'mat_schema')

    def test_inconsistent_orientation_refused(self):
        ac = chars(['Atrajectory','1.1','','binTrans'])
        mat = {'Aclass': ac,'name':chars(NAMES),'description':chars(['desc']*len(NAMES)),
               'dataInfo': np.array(INFO,dtype=np.int32), 'data_1':np.array(D1), 'data_2':np.array(D2)}
        b = io.BytesIO();savemat(b,mat,format='4')
        self.assert_refused(b.getvalue(), 'result_schema')

    def test_complete_synthetic_s1_passes_existing_checker(self):
        study = load_study(ROOT/'h1/cases/S1/study.json', ROOT/'h1/cases')
        refspec = read_reference(ROOT/'h1/reference_cases/S1.json')
        bundle = prepare(refspec)
        required = internal_exports(study.model)
        self.assertEqual(len(required), 18)
        names = ['time'] + list(required)
        info = [[0,1,0,-1]]
        data1 = []
        data2 = [[0.,1.]]
        for name in required:
            values = bundle['columns'][name]
            if name.split('.')[-1] in ('A','G','T') and name not in ('copper.T_b','steel.T_a'):
                data1.append([values[0],values[-1]])
                info.append([1,len(data1),0,-1])
            else:
                data2.append(list(values))
                info.append([2,len(data2),0,-1])
        if not data1:
            data1 = [[0,0]]
        decoded = decode_mat_bytes(make_mat(names,info,data1,data2),required,(0.,1.),
                                   maximum_shift=bundle['temporalPolicy']['maximumShift'])
        receipt = candidate_receipt(study,bundle,decoded['canonicalCsv'],'synthetic')
        result = check_candidate(study,bundle,decoded['canonicalCsv'],receipt,bundle['seal'])
        self.assertEqual(result['status'], 'checks_passed')
        self.assertFalse(result['nativeQualified'])
        self.assertEqual(result['requests'][0]['status'], 'diagnostic_only')
        self.assertEqual(decoded['columnProvenance']['copper.A']['origin'],'mat_parameter')


if __name__ == '__main__':
    unittest.main()
