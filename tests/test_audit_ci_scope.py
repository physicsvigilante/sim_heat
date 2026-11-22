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

from tools.verify_n1_plan_maintenance import BASELINE_COMMIT, verify as verify_n1

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

    def test_n1_maintenance_verifier_accepts_valid_plan_and_refuses_mutations(self):
        pins = json.loads((ROOT / 'qualification/h1_n1/SOURCE-PINS.json').read_text(encoding='utf-8'))
        git_agents = subprocess.run(
            ['git', '-C', str(ROOT), 'show', f'{BASELINE_COMMIT}:AGENTS.md'],
            capture_output=True, check=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            mirror = Path(tmp)
            shutil.copytree(ROOT / 'h1', mirror / 'h1')
            shutil.copytree(ROOT / 'qualification/h1_n1', mirror / 'qualification/h1_n1')
            for rel in pins['readonlySha256']:
                if rel == 'AGENTS.md':
                    continue
                dst = mirror / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                # Normalize CRLF to LF for Windows checkouts so pinned LF hashes match.
                dst.write_bytes((ROOT / rel).read_bytes().replace(b'\r\n', b'\n'))
            for rel in pins['inputSha256']:
                dst = mirror / rel
                dst.write_bytes((ROOT / rel).read_bytes().replace(b'\r\n', b'\n'))

            if git_agents.returncode == 0:
                agents_bytes = git_agents.stdout
            else:
                # Shallow CI clones without baseline history still exercise all live
                # plan, negative-control, and non-AGENTS source-pin checks.
                agents_bytes = b'historical AGENTS.md fixture\n'
                mirror_pins = mirror / 'qualification/h1_n1/SOURCE-PINS.json'
                updated = json.loads(mirror_pins.read_text(encoding='utf-8'))
                updated['readonlySha256']['AGENTS.md'] = sha256(agents_bytes).hexdigest()
                mirror_pins.write_text(json.dumps(updated, indent=2) + '\n', encoding='utf-8')

            if os.name == 'posix':
                ok = verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes)
                self.assertEqual(ok['planStructuralChecks'], 'PASS')
                self.assertFalse(ok['nativeExecuted'])
                self.assertFalse(ok['nativeQualified'])
                self.assertTrue(ok['maintenanceVerification']['livePlanAndNonAgentsPinsVerified'])

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
                        verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes)
                    plan_path.write_bytes(original_plan)

            # Mutating any non-AGENTS pinned file must fail closed with source drift.
            c1 = mirror / 'qualification/h1_c1/FREEZE.md'
            c1.write_bytes(c1.read_bytes() + b'tamper\n')
            with self.assertRaisesRegex(ValueError, 'source drift: qualification/h1_c1/FREEZE.md'):
                verify_n1(mirror, run_tests=False, agents_bytes=agents_bytes)


if __name__ == '__main__':
    unittest.main()
