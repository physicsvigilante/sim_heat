"""Offline-only steady adapter checks. Test ZIPs are SYNTHETIC, never native evidence.

The immutable original S1 CSV is reused as a numeric fixture. The test-generated
MAT bytes, status records and ZIPs are deliberately synthetic and never claimed
as a new OpenModelica run. Cases adversarially re-pin member and full ZIP hashes.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from h1 import reference
from h1.model import Refusal
from h1.study import load_study
from h1.verification import candidate_receipt, check_candidate
from viewer.network.tools.build_case import owner_graph, sha, stable_json
from viewer.network.tools.build_steady_case import compile_steady

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT/'viewer/network/data/S1.json'
NATIVE_CSV = ROOT/'viewer/network/tests/fixtures/S1-native-normalized.csv'
RUN_ID = 43820600508
COMMIT = '337ef554fb40da9408485bda8f2a4024c84720f6'
ARCHIVE_ARTIFACT_ID = 14204656273
CASE_TITLE = 'S1 · Copper and steel in series (steady)'


def make_test_only_members():
    """Build consistent synthetic validation receipts, never a native output."""
    study=load_study(ROOT/'h1/cases/S1/study.json',ROOT/'h1/cases')
    spec=reference.read_reference(ROOT/'h1/reference_cases/S1.json')
    reference_bundle=reference.prepare(spec)
    csv_bytes=NATIVE_CSV.read_bytes()
    receipt=candidate_receipt(study,reference_bundle,csv_bytes.decode('utf-8'),
                              'unattested_output')
    verdict=check_candidate(study,reference_bundle,csv_bytes.decode('utf-8'),
                            receipt,reference_bundle['seal'])
    assert verdict['status']=='checks_passed' and len(verdict['checks'])==56
    mat=b'TEST-ONLY: no real MAT or OpenModelica execution\n'
    folder='case_01/'
    files={
        folder+'model.mo': (ROOT/'h1/cases/S1/model.mo').read_bytes(),
        folder+'study.json': (ROOT/'h1/cases/S1/study.json').read_bytes(),
        folder+'SimHeat.mo': (ROOT/'experiments/h1_spike/SimHeat.mo').read_bytes(),
        folder+'reference.bundle.json':stable_json(reference_bundle),
        folder+'receipt.json':stable_json(receipt),
        folder+'verification.json':stable_json(verdict),
        folder+'mat_provenance.json':stable_json({
            'rawMatSha256':sha(mat),'canonicalCsvSha256':sha(csv_bytes),
            'samples':2,'duplicateRowsCollapsed':1,'nativeQualified':False}),
        folder+'normalized.csv':csv_bytes,
        folder+'model_res.mat':mat,
        folder+'build.mos':b'TEST-ONLY: no executable statements or build\n',
        folder+'build.returncode':b'0\n',
        folder+'simulation.returncode':b'0\n',
        folder+'model_init.xml':b'<test-only />\n',
        folder+'admission.json':b'TEST ONLY\n',
        'compiler_version.stdout':b'TEST-ONLY: not a real compiler version\n',
        'compiler_version.returncode':b'0\n',
        'offline_tests.returncode':b'0\n',
    }
    case={
        'directory':'case_01', 'study':'h1/cases/S1/study.json',
        'model':study.model.name, 'status':'checks_passed',
        'canonicalSamples':2, 'rawMatSha256':sha(mat),
        'referenceSeal':reference_bundle['seal'],
        'referenceFileSha256':sha(files[folder+'reference.bundle.json']),
        'checkCount':len(verdict['checks']),
        'maxRatio':max(x['maximumRatio'] for x in verdict['checks']),
    }
    attempt={
        'status':'diagnostic_checks_passed_not_native_qualified',
        'nativeQualified':False,
        'counts':{'versionQueries':1,'buildModelCalls':1,'modelLaunches':1},
        'github':{'GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':str(RUN_ID),
                  'GITHUB_SHA':COMMIT},
        'cases':[case]
    }
    return files,attempt


def zip_test_only(destination: Path, files: dict, attempt: dict, *, missing_manifest=(),
                  missing_members=(), duplicate=None):
    """Recompute *all* member SHA values and the outer ZIP SHA for each mutant."""
    attempt=deepcopy(attempt)
    attempt['artifactSha256']={name:sha(content) for name,content in sorted(files.items())
                               if name not in missing_manifest}
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('test-only/attempt.json',stable_json(attempt))
        for name,content in sorted(files.items()):
            if name not in missing_members:
                archive.writestr('test-only/'+name,content)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                archive.writestr('test-only/'+duplicate,files[duplicate])
    return sha(destination.read_bytes())


class SteadyAdapterTests(unittest.TestCase):
    def compile(self, archive: Path, digest: str, **overrides):
        options={'expected_run_id':RUN_ID,'expected_commit_sha':COMMIT}
        options.update(overrides)
        return compile_steady(ROOT,'h1/cases/S1/study.json',archive,digest,
                              1,ARCHIVE_ARTIFACT_ID,CASE_TITLE,**options)

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
        self.assertEqual(payload['source']['runId'],RUN_ID)
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

    def test_synthetic_repacked_positive_and_external_binding(self):
        with TemporaryDirectory() as tmp:
            archive=Path(tmp)/'test-only.zip'
            files,attempt=make_test_only_members()
            digest=zip_test_only(archive,files,attempt)
            data=self.compile(archive,digest)
            self.assertEqual(data['values'],json.loads(DATA.read_text())['values'])
            self.assertEqual(data['source']['runId'],RUN_ID)
            self.assertEqual(data['source']['compiledSourceCommit'],COMMIT)
            for overrides in ({'expected_run_id':1},
                              {'expected_commit_sha':'0'*40},
                              {'expected_commit_sha':'not-a-commit'},
                              {'expected_run_id':True}):
                with self.subTest(overrides=overrides),self.assertRaises(Refusal):
                    self.compile(archive,digest,**overrides)
            with self.assertRaises(Refusal):
                self.compile(archive,'0'*64)

    def test_reconciled_hashes_cannot_hide_invalid_checker_status_or_reference_seals(self):
        failures={
            'all_checks_false': lambda fs,a: self._alter_json(fs,'case_01/verification.json',
                lambda v: [c.__setitem__('passed',False) for c in v['checks']]),
            'reference_seal_item': lambda fs,a: a['cases'][0].__setitem__('referenceSeal','0'*64),
            'reference_seal_verdict': lambda fs,a: self._alter_json(fs,'case_01/verification.json',
                lambda v: v.__setitem__('referenceSeal','1'*64)),
            'reference_file_sha': lambda fs,a: a['cases'][0].__setitem__('referenceFileSha256','2'*64),
            'request_value_fabricated': lambda fs,a: self._alter_json(fs,'case_01/verification.json',
                lambda v: v['requests'][0].__setitem__('values',9999)),
            'request_status_invalid': lambda fs,a: self._alter_json(fs,'case_01/verification.json',
                lambda v: v['requests'][0].__setitem__('status','not_computed')),
            'check_ratio_fabricated': lambda fs,a: self._alter_json(fs,'case_01/verification.json',
                lambda v: v['checks'][0].__setitem__('maximumRatio',9999)),
            'case_check_count_false': lambda fs,a: a['cases'][0].__setitem__('checkCount',55),
            'case_max_ratio_false': lambda fs,a: a['cases'][0].__setitem__('maxRatio',9999),
            'reference_bundle_seal_false': lambda fs,a: self._alter_json(fs,'case_01/reference.bundle.json',
                lambda v: v.__setitem__('seal','f'*64)),
            'receipt_reference_seal_false': lambda fs,a: self._alter_json(fs,'case_01/receipt.json',
                lambda v: v.__setitem__('referenceSeal','a'*64)),
            'receipt_csv_false': lambda fs,a: self._alter_json(fs,'case_01/receipt.json',
                lambda v: v.__setitem__('csvSha256','a'*64)),
            'attempt_run_id_false': lambda fs,a: a['github'].__setitem__('GITHUB_RUN_ID','1'),
            'attempt_commit_false': lambda fs,a: a['github'].__setitem__('GITHUB_SHA','0'*40),
        }
        with TemporaryDirectory() as tmp:
            for name,alter in failures.items():
                with self.subTest(mutation=name):
                    files,attempt=make_test_only_members()
                    alter(files,attempt)
                    archive=Path(tmp)/(name+'.zip')
                    digest=zip_test_only(archive,files,attempt)
                    with self.assertRaises(Refusal) as error:
                        self.compile(archive,digest)
                    self.assertEqual(error.exception.code,'steady_evidence')

    @staticmethod
    def _alter_json(files,name,mutate):
        value=json.loads(files[name].decode('utf-8'))
        mutate(value)
        files[name]=stable_json(value)

    def test_manifest_missing_member_and_missing_archive_files_are_structured_refusals(self):
        files,attempt=make_test_only_members()
        with TemporaryDirectory() as tmp:
            for filename in ('case_01/build.mos', 'case_01/model_res.mat',
                             'case_01/normalized.csv','case_01/study.json',
                             'case_01/verification.json',
                             'case_01/reference.bundle.json'):
                for mode in ('omit_manifest','omit_member','omit_both'):
                    with self.subTest(filename=filename,mode=mode):
                        zip_path=Path(tmp)/(filename.replace('/','_')+'_'+mode+'.zip')
                        digest=zip_test_only(zip_path,files,attempt,
                            missing_manifest=[filename] if mode in ('omit_manifest','omit_both') else (),
                            missing_members=[filename] if mode in ('omit_member','omit_both') else ())
                        with self.assertRaises(Refusal) as error:
                            self.compile(zip_path,digest)
                        self.assertEqual(error.exception.code,'steady_evidence')
            zip_path=Path(tmp)/'duplicate.zip'
            digest=zip_test_only(zip_path,files,attempt,duplicate='case_01/model.mo')
            with self.assertRaises(Refusal) as error:
                self.compile(zip_path,digest)
            self.assertEqual(error.exception.code,'steady_evidence')

    def test_builder_rejects_forged_success_and_stale_archive(self):
        with TemporaryDirectory() as td:
            archive=Path(td)/'synthetic-refusal-only.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('synthetic/attempt.json',
                           json.dumps({'status':'stopped','nativeQualified':False}))
            checksum=sha(archive.read_bytes())
            with self.assertRaises(Refusal):
                self.compile(archive,checksum)
            with self.assertRaises(Refusal):
                self.compile(archive,'0'*64)
            with self.assertRaises(Refusal):
                compile_steady(ROOT,'h1/cases/D1/study.json',archive,checksum,1,1,
                               'transient refused',expected_run_id=RUN_ID,
                               expected_commit_sha=COMMIT)

    def test_steady_builder_remains_data_only_without_apparatus_dispatch(self):
        source=(ROOT/'viewer/network/tools/build_steady_case.py').read_text()
        for token in ('H1_S1','copper.T_b','Illustration 123','subprocess.',
                      'buildModel(', 'simulate(', 'nativeQualified=True'):
            self.assertNotIn(token,source)


if __name__ == '__main__':
    unittest.main()
