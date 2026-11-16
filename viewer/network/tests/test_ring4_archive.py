"""Data-only fifth network and generic original-archive layout regressions.

All generated ZIP fixtures here are SYNTHETIC structural tests; the genuine
Ring4 native result remains the separate SHA-pinned GitHub Actions artifact.
No OpenModelica build or native-result synthesis occurs.
"""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
import io
import json
import unittest
import zipfile

from h1.model import Refusal
from h1.study import load_study
from viewer.network.tools.build_case import archive_reader, owner_graph

ROOT=Path(__file__).resolve().parents[3]
VIEW=ROOT/'viewer/network'
CASE=VIEW/'data/TEACH_RING4.json'
EXPECTED_ORIGINAL='0bc1433be66df2827f8907d100ca264f6a721fe8ad40644b962500b97fa9b8b2'


class Ring4EvidenceTests(unittest.TestCase):
    def test_fifth_case_is_existing_h1_grammar_and_origin_pinned(self):
        study=load_study(ROOT/'h1/cases/TEACH_RING4/study.json',ROOT/'h1/cases')
        data=json.loads(CASE.read_text())
        catalog=json.loads((VIEW/'data/index.json').read_text())['cases']
        self.assertEqual([x['id'] for x in catalog[:5]],
                         ['H1_D1','H1_D2','DEV_BRIDGE','H1_S1','TEACH_RING4'])
        import hashlib
        self.assertEqual(hashlib.sha256(CASE.read_bytes()).hexdigest(),
                         next(x['sha256'] for x in catalog if x['id']=='TEACH_RING4'))
        self.assertTrue(study.request_report['admitted'])
        self.assertEqual(len(study.data['requests']),15)
        self.assertEqual(data['schema'],'sim_heat.viewer.native_case/1')
        self.assertEqual(data['source']['artifactSha256'],EXPECTED_ORIGINAL)
        self.assertEqual(data['source']['compiledSourceCommit'],
                         '39b2067c9b6ea5f903dc4c360a78241b24df7c09')
        self.assertEqual(data['source']['checksPassed'],126)
        self.assertIs(data['source']['nativeQualified'],False)
        self.assertEqual(data['source']['publicRequestStatus'],'diagnostic_only')
        self.assertEqual(data['source']['canonicalSamples'],2001)
        self.assertEqual(data['graph'],
                         dict(zip(('nodes','edges'),owner_graph(study))))
        self.assertEqual((len(data['graph']['nodes']),len(data['graph']['edges'])),(5,6))
        self.assertEqual(len(data['samples']),29)
        self.assertEqual((data['samples'][0][0],data['samples'][-1][0]),(0,24000))
        self.assertEqual(len(data['columns']),17)

    def test_archived_original_zip_root_and_nested_readers(self):
        with TemporaryDirectory() as tmp:
            for prefix in ('','original_native_attempt/'):
                with self.subTest(prefix=prefix):
                    f=Path(tmp)/('original' if not prefix else 'nested')
                    with zipfile.ZipFile(f,'w') as z:
                        z.writestr(prefix+'attempt.json','test-only-attempt')
                        z.writestr(prefix+'case_01/normalized.csv','test-only-csv')
                        if prefix:z.writestr('unrelated-external-ci-log','test-only-log')
                    with zipfile.ZipFile(f) as z:
                        original=archive_reader(z)
                        self.assertEqual(original('attempt.json'),b'test-only-attempt')
                        self.assertEqual(original('case_01/normalized.csv'),b'test-only-csv')
                        with self.assertRaises(Refusal):
                            original('case_01/missing.mat')

    def test_missing_ambiguous_duplicate_and_unsafe_attempt_entries_refuse(self):
        with TemporaryDirectory() as tmp:
            for name,members in [
                ('none',{'unrelated-file':'test-only'}),
                ('ambiguous',{'attempt.json':'A','old/attempt.json':'B'}),
                ('traversal',{'../evil/attempt.json':'A'}),
            ]:
                with self.subTest(name=name):
                    f=Path(tmp)/(name+'.zip')
                    with zipfile.ZipFile(f,'w') as z:
                        for member,val in members.items():z.writestr(member,val)
                    with zipfile.ZipFile(f) as z,self.assertRaises(Refusal):
                        archive_reader(z)
            f=Path(tmp)/'duplicate.zip'
            with zipfile.ZipFile(f,'w') as z:
                z.writestr('attempt.json','A')
                with __import__('warnings').catch_warnings():
                    __import__('warnings').simplefilter('ignore',UserWarning)
                    z.writestr('attempt.json','B')
            with zipfile.ZipFile(f) as z,self.assertRaises(Refusal):
                archive_reader(z)


if __name__=='__main__':
    unittest.main()
