"""Offline-only S1 steady adapter tests; no compiler or model launch."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from h1.model import Refusal
from h1.study import load_study
from viewer.network.tools.build_case import owner_graph
from viewer.network.tools.build_steady_case import compile_steady, sha

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT/'viewer/network/data/S1.json'
NATIVE_CSV = ROOT/'viewer/network/tests/fixtures/S1-native-normalized.csv'


class SteadyAdapterTests(unittest.TestCase):
    def test_existing_s1_study_derives_three_native_owner_nodes_and_two_oriented_rods(self):
        study=load_study(ROOT/'h1/cases/S1/study.json',ROOT/'h1/cases')
        self.assertTrue(study.request_report['admitted'])
        self.assertEqual(study.data['mode'],'steady')
        nodes,edges=owner_graph(study)
        payload=json.loads(DATA.read_text())
        self.assertEqual(payload['graph'],{'nodes':nodes,'edges':edges})
        self.assertEqual({n['kind'] for n in nodes},{'boundary','junction'})
        junction=next(n for n in nodes if n['kind']=='junction')
        self.assertEqual(junction['temperature'],'copper.T_b')
        self.assertEqual({n['id'] for n in nodes if n['kind']=='boundary'},
                         {'hot','cold'})
        self.assertEqual([(x['from'],x['to']) for x in edges],
                         [('hot','junction_2'),('junction_2','cold')])

    def test_original_native_csv_fixture_is_source_pinned_and_not_transient(self):
        payload=json.loads(DATA.read_text())
        source=NATIVE_CSV.read_bytes()
        self.assertEqual(sha(source),payload['source']['csvSha256'])
        self.assertEqual(payload['source']['rawMatSha256'],
                         '1d5ae021cf87eda8c14418b638e5cc3c353877358b52585deb7a0f7d375a0672')
        self.assertEqual(payload['source']['runId'],43820600508)
        self.assertFalse(payload['source']['nativeQualified'])
        self.assertEqual(payload['source']['publicRequestStatus'],'diagnostic_only')
        self.assertEqual(payload['schema'],'sim_heat.viewer.steady_case/1')
        self.assertNotIn('analysis',payload)
        self.assertNotIn('samples',payload)
        self.assertNotIn('time',payload['columns'])
        rows=list(csv.DictReader(io.StringIO(source.decode('utf-8'))))
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['time'],'0')
        self.assertEqual(rows[1]['time'],'1')
        self.assertEqual(rows[2],rows[1])
        for name,value in zip(payload['columns'],payload['values']):
            self.assertEqual(float(rows[1][name]),value,name)

    def test_builder_rejects_forged_success_and_stale_archive(self):
        with TemporaryDirectory() as td:
            archive=Path(td)/'synthetic-refusal-only.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('synthetic/attempt.json',
                           json.dumps({'status':'stopped','nativeQualified':False}))
            checksum=sha(archive.read_bytes())
            arguments=(ROOT,'h1/cases/S1/study.json',archive,checksum,1,1,'synthetic refusal')
            with self.assertRaises(Refusal):
                compile_steady(*arguments)
            with self.assertRaises(Refusal):
                compile_steady(ROOT,'h1/cases/S1/study.json',archive,'0'*64,1,1,'bad hash')
            with self.assertRaises(Refusal):
                compile_steady(ROOT,'h1/cases/D1/study.json',archive,checksum,1,1,'transient refused')

    def test_steady_builder_remains_data_only_without_apparatus_dispatch(self):
        source=(ROOT/'viewer/network/tools/build_steady_case.py').read_text()
        for token in ('H1_S1','copper.T_b','Illustration 123','subprocess.',
                      'buildModel(', 'simulate(', 'nativeQualified=True'):
            self.assertNotIn(token,source)


if __name__ == '__main__':
    unittest.main()
