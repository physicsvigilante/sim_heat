"""Offline R2-admission tests with fully re-pinned SYNTHETIC campaign ZIPs.

All fixture bytes are TEST ONLY. The positive control uses a checking reference
to manufacture a synthetic CSV, plus a deliberately fake MAT placeholder. It
never runs OpenModelica or creates public viewer data. For an optional locally
supplied *authentic* original archive, this test reads the original bytes and
repackages only separate explicitly SYNTHETIC mutations; it never overwrites
the real artifact or asserts that a re-pinned ZIP was executed on GitHub.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from h1 import reference
from h1.model import Refusal
from h1.study import load_study
from h1.verification import candidate_receipt, check_candidate
from viewer.network.tools.build_case import sha, stable_json
from viewer.network.tools.build_campaign_case import compile_campaign_case

ROOT = Path(__file__).resolve().parents[3]
TEST_RUN_ID = 99999999
TEST_COMMIT = 'a' * 40
BRANCH = 'experiment/synthetic-test-only'
TEST_ARTIFACT_ID = 99999999
STUDY = 'h1/cases/D2_K2/study.json'
CASE = 'batch_1/case_01/'
STUDY_SNAPSHOT = 'synthetic_campaign/inputs/cases/D2_K2/study.json'
ORIGINAL_SHA = 'dc32a0a36a27f031ce7a13da83ebdd26a3dd6ac1d14612fa597b36cb439f4843'


def synthetic_bundle():
    """Make a fully internally consistent test-only archive, never a native one."""
    study = load_study(ROOT / STUDY, ROOT / 'h1/cases')
    # Serialize/deserialize BEFORE checking: stable_json sorts dictionary keys,
    # and the historical checker preserves its incoming body iteration order.
    bundle = json.loads(stable_json(reference.prepare(
        reference.read_reference(ROOT / 'h1/reference_cases/D2_K2.json'))))
    names = sorted(bundle['columns'])
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['time', *names])
    for i, t in enumerate(bundle['grid']):
        writer.writerow([format(float(t), '.17g'),
                         *(format(float(bundle['columns'][n][i]), '.17g') for n in names)])
    writer.writerow([format(float(bundle['grid'][-1]), '.17g'),
                     *(format(float(bundle['columns'][n][-1]), '.17g') for n in names)])
    csv_text = out.getvalue()
    receipt = candidate_receipt(study, bundle, csv_text, 'unattested_output')
    verdict = check_candidate(study, bundle, csv_text, receipt, bundle['seal'])
    assert verdict['status'] == 'checks_passed' and len(verdict['checks']) == 34
    assert all(c['passed'] is True for c in verdict['checks'])
    mat = b'FAKE MAT PLACEHOLDER: SYNTHETIC / TEST ONLY; NO OMC EXECUTION\n'
    plan_bytes = stable_json({'branch': BRANCH, 'cases': [{'study': STUDY_SNAPSHOT}]})
    files = {
        'plan_1.json': plan_bytes,
        'inputs/cases/D2_K2/study.json': (ROOT / STUDY).read_bytes(),
        CASE+'model.mo': (ROOT / 'h1/cases/D2_K2/model.mo').read_bytes(),
        CASE+'study.json': (ROOT / STUDY).read_bytes(),
        CASE+'model_res.mat': mat,
        CASE+'normalized.csv': csv_text.encode('utf-8'),
        CASE+'mat_provenance.json': stable_json({
            'rawMatSha256': sha(mat),
            'canonicalCsvSha256': sha(csv_text.encode('utf-8')),
            'samples': 1001, 'duplicateRowsCollapsed': 1,
            'nativeQualified': False,
        }),
        CASE+'reference.bundle.json': stable_json(bundle),
        CASE+'receipt.json': stable_json(receipt),
        CASE+'verification.json': stable_json(verdict),
        CASE+'build.returncode': b'0\n',
        CASE+'simulation.returncode': b'0\n',
        'batch_1/compiler_version.returncode': b'0\n',
        'batch_1/offline_tests.returncode': b'0\n',
    }
    attempt = {
        'schema': 'sim_heat.native_batch_attempt/1',
        'status': 'diagnostic_checks_passed_not_native_qualified',
        'nativeQualified': False,
        'planSha256': sha(plan_bytes),
        'github': {'GITHUB_SHA': TEST_COMMIT, 'GITHUB_RUN_ID': str(TEST_RUN_ID),
                   'GITHUB_RUN_ATTEMPT': '1'},
        'counts': {'versionQueries': 1, 'buildModelCalls': 1, 'modelLaunches': 1},
        'cases': [{
            'directory': 'case_01', 'study': STUDY_SNAPSHOT,
            'model': study.model.name, 'status': 'checks_passed',
            'canonicalSamples': len(study.grid), 'rawMatSha256': sha(mat),
            'referenceFileSha256': sha(files[CASE+'reference.bundle.json']),
            'referenceSeal': bundle['seal'],
            'checkCount': len(verdict['checks']),
            'maxRatio': max(c['maximumRatio'] for c in verdict['checks']),
        }],
    }
    files['campaign.json'] = stable_json({
        'schema': 'sim_heat.resolution_attempt/1',
        'status': 'diagnostic_checks_passed_not_native_qualified',
        'nativeQualified': False,
        'batches': [{
            'output': 'synthetic_campaign/batch_1',
            'plan': 'synthetic_campaign/plan_1.json',
            'sha256': sha(plan_bytes),
        }],
    })
    return files, attempt


def edit_json(files, name, edit):
    obj = json.loads(files[name].decode('utf-8'))
    edit(obj)
    files[name] = stable_json(obj)


def repack(destination: Path, base_files: dict, base_attempt: dict, *,
           change_files=None, change_attempt=None, change_manifest=None,
           exclude=(), extra=None, duplicate=None):
    """Refresh all retained selected-batch member SHA values and outer ZIP hash."""
    files = dict(base_files)
    if change_files:
        change_files(files)
    for name in exclude:
        files.pop(name)
    if extra:
        files.update(extra)
    attempt = deepcopy(base_attempt)
    attempt['artifactSha256'] = {
        name.removeprefix('batch_1/'): sha(data)
        for name, data in files.items() if name.startswith('batch_1/')
    }
    if change_manifest:
        change_manifest(attempt['artifactSha256'])
    if change_attempt:
        change_attempt(attempt)
    files['batch_1/attempt.json'] = stable_json(attempt)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                z.writestr(duplicate, files[duplicate])
    return sha(destination.read_bytes())


class FullyRepinnedCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.attempt = synthetic_bundle()

    def check(self, path, digest, **overrides):
        pins = dict(expected_run_id=TEST_RUN_ID, expected_commit_sha=TEST_COMMIT,
                    expected_branch=BRANCH)
        pins.update(overrides)
        return compile_campaign_case(
            ROOT, STUDY, path, digest, 1, 1, TEST_ARTIFACT_ID,
            'SYNTHETIC TEST ONLY — NOT NATIVE', **pins)

    def test_synthetic_internal_positive_control_is_never_public_native_evidence(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'SYNTHETIC-positive.zip'
            result = self.check(path, repack(path, self.files, self.attempt))
            self.assertEqual(result['source']['runId'], TEST_RUN_ID)
            self.assertEqual(result['source']['compiledSourceCommit'], TEST_COMMIT)
            self.assertEqual(result['source']['nativeQualified'], False)
            self.assertEqual(result['source']['checksPassed'], 34)
            self.assertEqual(len(result['samples']), 21)
            self.assertEqual((result['samples'][0][0], result['samples'][-1][0]), (0, 9375))
            self.assertEqual([e['id'] for e in result['graph']['edges']], ['rod'])

    def test_rehashed_check_result_source_reference_and_manifest_tampers_refuse(self):
        def verdict(edit):
            return lambda files: edit_json(files, CASE+'verification.json', edit)
        cases = {
            'all-checks-false': dict(change_files=verdict(
                lambda v: [c.__setitem__('passed', False) for c in v['checks']])),
            'fabricated-request-values': dict(change_files=verdict(
                lambda v: v['requests'][0].__setitem__('values', 9999))),
            'forged-check-ratio': dict(change_files=verdict(
                lambda v: v['checks'][0].__setitem__('maximumRatio', 9999))),
            'changed-model-bytes': dict(change_files=lambda fs: fs.__setitem__(
                CASE+'model.mo', fs[CASE+'model.mo']+b'// TEST ONLY\n')),
            'changed-study-bytes': dict(change_files=lambda fs: fs.__setitem__(
                CASE+'study.json', fs[CASE+'study.json']+b' ')),
            'reference-payload-change': dict(change_files=lambda fs: edit_json(
                fs, CASE+'reference.bundle.json',
                lambda b: b['columns']['hot.T'].__setitem__(0, 999))),
            'reference-seal-change': dict(change_files=lambda fs: edit_json(
                fs, CASE+'reference.bundle.json', lambda b: b.__setitem__('seal', 'f'*64))),
            'verdict-seal-change': dict(change_files=verdict(
                lambda v: v.__setitem__('referenceSeal', 'f'*64))),
            'receipt-seal-change': dict(change_files=lambda fs: edit_json(
                fs, CASE+'receipt.json', lambda r: r.__setitem__('referenceSeal', 'f'*64))),
            'attempt-seal-change': dict(change_attempt=lambda a:
                a['cases'][0].__setitem__('referenceSeal', 'f'*64)),
            'reference-file-hash-change': dict(change_attempt=lambda a:
                a['cases'][0].__setitem__('referenceFileSha256', 'f'*64)),
            'manifest-entry-removed': dict(change_manifest=lambda m:
                m.pop('case_01/model_res.mat')),
            'extra-manifest-entry': dict(change_manifest=lambda m:
                m.__setitem__('invented.out', '0'*64)),
            'attempt-plan-hash-change': dict(change_attempt=lambda a:
                a.__setitem__('planSha256', '0'*64)),
            'campaign-plan-hash-change': dict(change_files=lambda fs: edit_json(
                fs, 'campaign.json', lambda c:
                c['batches'][0].__setitem__('sha256', '0'*64))),
            'plan-branch-change': dict(change_files=lambda fs: edit_json(
                fs, 'plan_1.json', lambda p:
                p.__setitem__('branch', 'experiment/other'))),
            'attempt-run-id-change': dict(change_attempt=lambda a:
                a['github'].__setitem__('GITHUB_RUN_ID', '1')),
            'attempt-commit-change': dict(change_attempt=lambda a:
                a['github'].__setitem__('GITHUB_SHA', '0'*40)),
            'attempt-qualified-falsely': dict(change_attempt=lambda a:
                a.__setitem__('nativeQualified', True)),
        }
        with TemporaryDirectory() as td:
            for name, change in cases.items():
                with self.subTest(name=name):
                    p = Path(td)/(name+'.zip')
                    digest = repack(p, self.files, self.attempt, **change)
                    with self.assertRaises(Refusal, msg=name) as caught:
                        self.check(p, digest)
                    self.assertEqual(caught.exception.code, 'campaign_evidence')

    def test_rehashed_missing_duplicate_and_unsafe_zip_members_refuse(self):
        cases = {
            'missing-MAT': dict(exclude=(CASE+'model_res.mat',)),
            'missing-reference': dict(exclude=(CASE+'reference.bundle.json',)),
            'unsafe-external': dict(extra={'../ignored.txt': b'TEST ONLY'}),
            'unsafe-internal': dict(extra={'batch_1/../evil.txt': b'TEST ONLY'}),
            'absolute-name': dict(extra={'/absolute.txt': b'TEST ONLY'}),
            'duplicate-name': dict(duplicate=CASE+'model.mo'),
        }
        with TemporaryDirectory() as td:
            for name, change in cases.items():
                with self.subTest(name=name):
                    p = Path(td)/(name+'.zip')
                    digest = repack(p, self.files, self.attempt, **change)
                    with self.assertRaises(Refusal, msg=name) as caught:
                        self.check(p, digest)
                    self.assertEqual(caught.exception.code, 'campaign_evidence')

    @unittest.skipUnless(os.environ.get('SIMHEAT_ORIGINAL_CAMPAIGN_ZIP'),
                         'Original external artifact not supplied; synthetic tests still run')
    def test_optional_original_native_archive_and_fully_rehashed_test_only_mutants(self):
        source = Path(os.environ['SIMHEAT_ORIGINAL_CAMPAIGN_ZIP'])
        self.assertEqual(sha(source.read_bytes()), ORIGINAL_SHA)
        with zipfile.ZipFile(source) as z:
            self.assertIsNone(z.testzip())
            files = {name: z.read(name) for name in z.namelist()}
        attempt = json.loads(files.pop('batch_1/attempt.json'))
        pins = dict(expected_run_id=43693191224,
                    expected_commit_sha='52b1635932a3e4519b91f3bf093c0c21b0248d91',
                    expected_branch='experiment/h1-cloud-resolution-once')
        original = compile_campaign_case(ROOT, STUDY, source, ORIGINAL_SHA, 1, 1,
                                         14153251022, 'Original D2-K2', **pins)
        self.assertFalse(original['source']['nativeQualified'])
        mutants = {
            'false-checks': dict(change_files=lambda fs: edit_json(
                fs, CASE+'verification.json',
                lambda v: [c.__setitem__('passed', False) for c in v['checks']])),
            'fake-public-request': dict(change_files=lambda fs: edit_json(
                fs, CASE+'verification.json',
                lambda v: v['requests'][0].__setitem__('values', {'TEST_ONLY': 9999}))),
            'changed-model': dict(change_files=lambda fs: fs.__setitem__(
                CASE+'model.mo', fs[CASE+'model.mo']+b'// TEST ONLY\n')),
            'wrong-reference-seal': dict(change_files=lambda fs: edit_json(
                fs, CASE+'reference.bundle.json',
                lambda v: v.__setitem__('seal', 'f'*64))),
            'omitted-MAT-manifest-entry': dict(change_manifest=lambda m:
                m.pop('case_01/model_res.mat')),
            'wrong-plan-branch': dict(change_files=lambda fs: edit_json(
                fs, 'plan_1.json',
                lambda p: p.__setitem__('branch', 'experiment/not-real'))),
            'unlisted-added-member': dict(
                extra={'batch_1/TEST_ONLY_ADDED': b'TEST ONLY'},
                change_manifest=lambda m: m.pop('TEST_ONLY_ADDED')),
        }
        with TemporaryDirectory() as td:
            for name, change in mutants.items():
                with self.subTest(mutation=name):
                    path = Path(td)/('SYNTHETIC-'+name+'.zip')
                    digest = repack(path, files, attempt, **change)
                    self.assertNotEqual(digest, ORIGINAL_SHA)
                    with self.assertRaises(Refusal, msg=name) as caught:
                        compile_campaign_case(ROOT, STUDY, path, digest, 1, 1,
                                              14153251022, 'TEST ONLY', **pins)
                    self.assertEqual(caught.exception.code, 'campaign_evidence')
        self.assertEqual(sha(source.read_bytes()), ORIGINAL_SHA)

    def test_external_trust_limit_is_explicit_and_not_native_authentication(self):
        with TemporaryDirectory() as td:
            path = Path(td)/'SYNTHETIC-identities.zip'
            digest = repack(path, self.files, self.attempt)
            for overrides in ({'expected_run_id': 1},
                              {'expected_commit_sha': '0'*40},
                              {'expected_branch': 'experiment/different'}):
                with self.subTest(overrides=overrides), self.assertRaises(Refusal) as caught:
                    self.check(path, digest, **overrides)
                self.assertEqual(caught.exception.code, 'campaign_evidence')
            # Deliberately prove that newly invented matching external pins are
            # NOT authenticated by internal SHA consistency alone.
            fake = 'b'*40
            fabricated = Path(td)/'SYNTHETIC-self-pinned.zip'
            digest2 = repack(fabricated, self.files, self.attempt,
                             change_attempt=lambda a: a['github'].update(
                                 GITHUB_SHA=fake, GITHUB_RUN_ID='1'))
            data = self.check(fabricated, digest2, expected_run_id=1,
                              expected_commit_sha=fake)
            self.assertEqual(data['source']['runId'], 1)
            self.assertFalse(data['source']['nativeQualified'])


if __name__ == '__main__':
    unittest.main()
