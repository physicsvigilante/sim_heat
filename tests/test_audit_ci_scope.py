"""Preserve first-introduction scope gates without forbidding future maintenance."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

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


if __name__ == '__main__':
    unittest.main()
