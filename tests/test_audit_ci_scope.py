"""Preserve first-introduction scope gates without forbidding future maintenance."""
from hashlib import sha256
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tools.verify_n1_plan_maintenance import (
    AUTHORIZED_STUDY_NEW_LINE,
    AUTHORIZED_STUDY_OLD_LINE,
    BASELINE_COMMIT,
    HISTORICAL_DRIFT_EXEMPT,
    SOURCE_PINS_SHA256,
    prepare_stage,
    verify as verify_n1,
)

ROOT = Path(__file__).resolve().parents[1]


class AuditCIScopeTests(unittest.TestCase):
    def test_original_introduction_guards_are_branch_scoped(self):
        for name, branch in (
            ('source-preview-ci.yml', 'product/novel-source-preview'),
            ('authoring-workbench-ci.yml', 'product/local-authoring-workbench'),
        ):
            with self.subTest(workflow=name):
                source = (ROOT/'.github/workflows'/name).read_text()
                self.assertIn('SOURCE_BRANCH: ${{ github.head_ref || github.ref_name }}', source)
                self.assertIn(f"if os.environ['SOURCE_BRANCH'] == '{branch}':", source)
                self.assertIn(f'if [ "$SOURCE_BRANCH" = "{branch}" ]; then', source)
                self.assertIn('git diff --exit-code "$scope_base" HEAD', source)
                block = source.split("          python - <<'PY'\n", 1)[1].split('\n          PY', 1)[0]
                block = textwrap.dedent(block)
                evidence = ('source_preview_evidence' if name.startswith('source')
                            else 'local_authoring_evidence')
                with tempfile.TemporaryDirectory() as tmp:
                    folder = Path(tmp)/evidence
                    folder.mkdir()
                    (folder/'source-diff.txt').write_text('M\th1/source_preview.py\n')
                    for actual_branch, should_pass in (('audit/project-health', True), (branch, False)):
                        run = subprocess.run([sys.executable, '-c', block], cwd=tmp,
                                             env=os.environ | {'SOURCE_BRANCH': actual_branch},
                                             capture_output=True, text=True, timeout=10)
                        self.assertEqual(run.returncode == 0, should_pass, run.stderr)

    def test_maintenance_keeps_all_invariant_tests_archives_and_browser_checks(self):
        for name in ('source-preview-ci.yml', 'authoring-workbench-ci.yml'):
            source = (ROOT/'.github/workflows'/name).read_text()
            for required in ('unittest discover -s h1/tests', 'unittest discover -s tests',
                             'node --test', 'replay_published_archives.py',
                             'browser_source_preview.py', 'actions/upload-artifact@'):
                with self.subTest(workflow=name, command=required):
                    self.assertIn(required, source)
            self.assertIn('git rev-parse HEAD^1', source)
            self.assertIn('github.event.pull_request.head.sha', source)

    def test_h1_n1_plan_and_product_entry_introduction_guards_are_branch_scoped(self):
        n1 = (ROOT / '.github/workflows/h1-n1-plan-ci.yml').read_text(encoding='utf-8')
        self.assertIn('SOURCE_BRANCH: ${{ github.head_ref || github.ref_name }}', n1)
        self.assertIn('if [ "$SOURCE_BRANCH" = "planning/h1-n1-t1t" ]; then', n1)
        # On non-introduction branches (including main), N1 plan + negative controls MUST execute.
        self.assertIn('else\n            python -B tools/verify_n1_plan_maintenance.py --run-tests', n1)
        self.assertIn('unittest discover -s h1/tests', n1)
        self.assertIn('tools/render_product_docs.py --check', n1)

        prod = (ROOT / '.github/workflows/product-entry-ci.yml').read_text(encoding='utf-8')
        self.assertIn('SOURCE_BRANCH: ${{ github.head_ref || github.ref_name }}', prod)
        self.assertIn(
            'if [ "$SOURCE_BRANCH" = "product/authoring-guide" ] || [ "$SOURCE_BRANCH" = "product/explorer-entry" ]; then',
            prod,
        )
        for required in ('unittest discover -s h1/tests', 'unittest discover -s tests',
                         'node --test', 'replay_published_archives.py',
                         'browser_product_docs.py', 'tools/render_product_docs.py --check'):
            self.assertIn(required, prod)

        qual = (ROOT / '.github/workflows/qualification-offline-ci.yml').read_text(encoding='utf-8')
        self.assertIn('branches: [main]', qual)
        self.assertIn('tools/verify_n1_plan_maintenance.py --run-tests', qual)
        for idx in range(2, 13):
            self.assertIn(f'qualification/h1_n{idx}/tests', qual)
        self.assertIn('qualification/h1_n13/test_conduction.py', qual)
        self.assertNotIn('apt-get', qual.lower())
        self.assertNotIn('docker', qual.lower())

        main_ci = (ROOT / '.github/workflows/main-offline-acceptance-ci.yml').read_text(encoding='utf-8')
        self.assertIn('push:\n    branches: [main]', main_ci)
        self.assertIn('pull_request:\n    branches: [main]', main_ci)
        self.assertNotIn('github.event.pull_request.head.sha', main_ci)
        for required in (
            'unittest discover -s tests',
            'unittest discover -s h1/tests',
            'unittest discover -s experiments/h1_spike/checks',
            'unittest discover -s viewer/network/tests',
            'node --test',
            'tools/verify_n1_plan_maintenance.py --run-tests',
            'qualification/h1_n13/test_conduction.py',
            'actions/upload-artifact@',
        ):
            self.assertIn(required, main_ci)
        for idx in range(2, 13):
            self.assertIn(f'qualification/h1_n{idx}/tests', main_ci)
        self.assertNotIn('apt-get', main_ci.lower())
        self.assertNotIn('docker', main_ci.lower())

    def test_n1_maintenance_verifier_accepts_valid_plan_and_refuses_mutations(self):
        pins_src = ROOT / 'qualification/h1_n1/SOURCE-PINS.json'
        pins_lf = pins_src.read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(sha256(pins_lf).hexdigest(), SOURCE_PINS_SHA256)
        pins = json.loads(pins_lf.decode('utf-8'))
        git_agents = subprocess.run(
            ['git', '-C', str(ROOT), 'show', f'{BASELINE_COMMIT}:AGENTS.md'],
            capture_output=True, check=False,
        )
        git_study = subprocess.run(
            ['git', '-C', str(ROOT), 'show', f'{BASELINE_COMMIT}:h1/study.py'],
            capture_output=True, check=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            mirror = Path(tmp) / 'mirror'
            stage_check = Path(tmp) / 'stage-check'
            shutil.copytree(ROOT / 'h1', mirror / 'h1')
            shutil.copytree(ROOT / 'qualification/h1_n1', mirror / 'qualification/h1_n1')
            # Normalize CRLF to LF for Windows checkouts so pinned LF hashes match
            # (keep h1/study.py normalized in the scratch mirror per N-02).
            mirror_pins = mirror / 'qualification/h1_n1/SOURCE-PINS.json'
            mirror_pins.write_bytes(pins_lf)
            for rel in pins['readonlySha256']:
                if rel == 'AGENTS.md':
                    continue
                dst = mirror / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes((ROOT / rel).read_bytes().replace(b'\r\n', b'\n'))
            for rel in pins['inputSha256']:
                dst = mirror / rel
                dst.write_bytes((ROOT / rel).read_bytes().replace(b'\r\n', b'\n'))

            agents_bytes = git_agents.stdout if git_agents.returncode == 0 else None
            study_bytes = git_study.stdout if git_study.returncode == 0 else None
            self.assertIsNotNone(agents_bytes)
            self.assertIsNotNone(study_bytes)

            expected_study_pin = pins['readonlySha256']['h1/study.py']
            expected_live_study = study_bytes.replace(AUTHORIZED_STUDY_OLD_LINE, AUTHORIZED_STUDY_NEW_LINE, 1)
            expected_live_sha = sha256(expected_live_study).hexdigest()

            # G3 stage-hash inspection (both POSIX and Windows): staged h1/study.py has historical pin bytes
            # while live mirror/h1/study.py matches the bounded authorized F-06 delta.
            prepare_stage(
                mirror,
                stage_check,
                pins,
                historical_agents=agents_bytes,
                historical_study=study_bytes,
            )
            self.assertEqual(sha256((stage_check / 'h1/study.py').read_bytes()).hexdigest(), expected_study_pin)
            self.assertEqual(sha256((mirror / 'h1/study.py').read_bytes()).hexdigest(), expected_live_sha)

            if os.name == 'posix':
                ok = verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes)
                self.assertEqual(ok['planStructuralChecks'], 'PASS')
                self.assertFalse(ok['nativeExecuted'])
                self.assertFalse(ok['nativeQualified'])
                mv = ok['maintenanceVerification']
                self.assertEqual(mv['sourcePinsManifestSha256Verified'], SOURCE_PINS_SHA256)
                self.assertEqual(mv['historicalPinnedFile'], 'AGENTS.md')
                self.assertEqual(mv['historicalPinnedFiles'], list(HISTORICAL_DRIFT_EXEMPT))
                self.assertEqual(mv['historicalStudySha256Verified'], expected_study_pin)
                self.assertEqual(mv['liveStudySha256'], expected_live_sha)
                self.assertTrue(mv['liveStudyMatchesAuthorizedDelta'])
                self.assertTrue(mv['liveStudyDiffersFromPin'])
                self.assertTrue(mv['livePlanAndNonAgentsPinsVerified'])
            else:
                # Documented Windows stop: live pin & bounded-delta checks pass, then frozen
                # check_plan.py:310 executes staged historical h1/study.py (G3) which hits F-06.
                with self.assertRaisesRegex(ValueError, r'Refusal: path: portable relative path required'):
                    verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes)

            # (e) Existing plan-mutation probes (fail in check_plan.py before load_study).
            plan_path = mirror / 'qualification/h1_n1/plan.json'
            original_plan = plan_path.read_bytes()
            for label, mutate, expected_err in (
                ('native_permission', lambda p: p['authority'].__setitem__('nativeExecutionApproved', True),
                 'only planning authorized'),
                ('missing_blocker', lambda p: p['executionBlockers'].pop(), 'unresolved gates omitted'),
                ('weakened_margin', lambda p: p['acceptance'].__setitem__('referenceErrorFractionMaximum', 0.02),
                 'numerical bounds'),
            ):
                with self.subTest(mutation=label):
                    data = json.loads(original_plan.decode('utf-8'))
                    mutate(data)
                    plan_path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, expected_err):
                        verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes)
                    plan_path.write_bytes(original_plan)

            # (c) Historical h1/study.py not matching its pin (injected bytes) must be refused.
            with self.assertRaisesRegex(ValueError, f'historical h1/study.py at {BASELINE_COMMIT} does not match'):
                verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes + b'\n')

            # (d) Live h1/study.py altered beyond the authorized 1-line F-06 delta must be refused.
            live_study = mirror / 'h1/study.py'
            original_live_study = live_study.read_bytes()
            live_study.write_bytes(original_live_study + b'# extra\n')
            with self.assertRaisesRegex(ValueError, 'source drift: h1/study.py beyond the authorized F-06 delta'):
                verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes)
            live_study.write_bytes(original_live_study)

            # (a) Mutating another pinned file (h1/model.py and FREEZE.md) must fail closed with source drift.
            model_py = mirror / 'h1/model.py'
            original_model = model_py.read_bytes()
            model_py.write_bytes(original_model + b'# tamper\n')
            with self.assertRaisesRegex(ValueError, 'source drift: h1/model.py'):
                verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes)
            model_py.write_bytes(original_model)

            c1 = mirror / 'qualification/h1_c1/FREEZE.md'
            original_c1 = c1.read_bytes()
            tampered_c1 = original_c1 + b'tamper\n'
            c1.write_bytes(tampered_c1)
            with self.assertRaisesRegex(ValueError, 'source drift: qualification/h1_c1/FREEZE.md'):
                verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes)

            # (b) Dual tamper: altering BOTH a protected file AND updating SOURCE-PINS.json
            # to match must still fail closed on manifest digest drift.
            rehashed = json.loads(pins_lf.decode('utf-8'))
            rehashed['readonlySha256']['qualification/h1_c1/FREEZE.md'] = sha256(tampered_c1).hexdigest()
            mirror_pins.write_text(json.dumps(rehashed, indent=2) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source drift: qualification/h1_n1/SOURCE-PINS.json'):
                verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes)

            # Removing a protected entry from SOURCE-PINS.json must also fail closed.
            c1.write_bytes(original_c1)
            pruned = json.loads(pins_lf.decode('utf-8'))
            del pruned['readonlySha256']['qualification/h1_c1/FREEZE.md']
            mirror_pins.write_text(json.dumps(pruned, indent=2) + '\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source drift: qualification/h1_n1/SOURCE-PINS.json'):
                verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes, study_bytes=study_bytes)

    def test_f06_live_study_differs_from_baseline_by_exact_single_line(self):
        git_study = subprocess.run(
            ['git', '-C', str(ROOT), 'show', f'{BASELINE_COMMIT}:h1/study.py'],
            capture_output=True, check=False,
        )
        self.assertEqual(git_study.returncode, 0, git_study.stderr.decode(errors='replace'))
        historical = git_study.stdout
        live = (ROOT / 'h1/study.py').read_bytes()
        self.assertEqual(historical.count(AUTHORIZED_STUDY_OLD_LINE), 1)
        hist_lines = historical.splitlines(keepends=True)
        live_lines = live.splitlines(keepends=True)
        self.assertEqual(len(hist_lines), len(live_lines))
        diffs = [(i + 1, a, b) for i, (a, b) in enumerate(zip(hist_lines, live_lines)) if a != b]
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0][1], AUTHORIZED_STUDY_OLD_LINE)
        self.assertEqual(diffs[0][2], AUTHORIZED_STUDY_NEW_LINE)
        self.assertEqual(live, historical.replace(AUTHORIZED_STUDY_OLD_LINE, AUTHORIZED_STUDY_NEW_LINE, 1))

    def test_f09_ci_workflow_map_and_main_acceptance_smoke_fixtures(self):
        main_ci = (ROOT / '.github/workflows/main-offline-acceptance-ci.yml').read_text(encoding='utf-8')
        ci_map = (ROOT / 'docs/CI_WORKFLOW_MAP.md').read_text(encoding='utf-8')
        main_row = next(line for line in ci_map.splitlines() if '`main-offline-acceptance-ci.yml`' in line)
        self.assertNotIn('render_product_docs.py --check', main_row)

        smoke_specs = (
            ('tools.multiport_thermal_network', 'tests/fixtures/m02_smoke/multiport_smoke.json',
             'sim_heat.offline_multiport_network/1'),
            ('tools.staged_phase_body_network', 'tests/fixtures/m02_smoke/staged_smoke.json',
             'sim_heat.offline_staged_phase_body/1'),
            ('tools.multibody_phase_network', 'tests/fixtures/m02_smoke/multibody_smoke.json',
             'sim_heat.offline_multibody_phase_network/1'),
        )
        flags = ('nativeExecuted', 'nativeQualified', 'independentlyCertifiedReference', 'runnerConsumable')
        for module, fixture_rel, expected_schema in smoke_specs:
            with self.subTest(module=module):
                self.assertIn(f'-m {module} --request {fixture_rel}', main_ci)
                fixture_path = ROOT / fixture_rel
                self.assertTrue(fixture_path.is_file(), f'missing smoke fixture {fixture_rel}')
                run = subprocess.run(
                    [sys.executable, '-B', '-m', module, '--request', str(fixture_path)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(run.returncode, 0, run.stderr)
                out = json.loads(run.stdout)
                self.assertEqual(out['schema'], expected_schema)
                for flag in flags:
                    self.assertIs(out[flag], False)
                    self.assertIs(out['evidence'][flag], False)


if __name__ == '__main__':
    unittest.main()
