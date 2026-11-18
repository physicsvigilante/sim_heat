"""Prospective product-only CI trigger/guard checks. Never invokes a simulator."""

from fnmatch import fnmatchcase
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/product-entry-ci.yml'


def product_pr_paths(text):
    # Parse only this workflow's small literal PR path list, without a YAML
    # parser dependency or interpreting GitHub's expression language.
    block = text.split('  pull_request:\n', 1)[1].split('\npermissions:', 1)[0]
    block = block.split('    paths:\n', 1)[1]
    return tuple(line.strip()[2:].strip("'\"") for line in block.splitlines()
                 if line.strip().startswith('- '))


class ProductCIScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding='utf-8')
        cls.paths = product_pr_paths(cls.workflow)

    def test_pr_trigger_covers_product_ownership_not_all_tests(self):
        for path in (
            'index.html', 'README.md', 'docs/CAPABILITIES.md',
            'docs/CAPABILITIES.html', 'docs/AUTHORING.md',
            'docs/AUTHORING.html', 'tools/render_product_docs.py',
            'tests/test_product_entry.py', 'tests/test_product_docs.py',
            'tests/test_product_ci_scope.py', 'tests/browser_product_entry.py',
            'tests/browser_product_docs.py', '.github/workflows/product-entry-ci.yml',
        ):
            with self.subTest(owned=path):
                self.assertTrue(any(fnmatchcase(path, pattern) for pattern in self.paths))
        for path in (
            'tests/test_source_preview.py', 'tests/browser_source_preview.py',
            'h1/source_preview.py', 'viewer/source_preview/core.mjs',
            'experiments/teacher_split3/TASK.md', 'qualification/h1_c1/FREEZE.md',
        ):
            with self.subTest(unrelated=path):
                self.assertFalse(any(fnmatchcase(path, pattern) for pattern in self.paths))
        self.assertNotIn('tests/**', self.paths)

    def test_product_guard_uses_pr_base_and_checks_protected_paths(self):
        self.assertIn('github.event.pull_request.base.sha', self.workflow)
        self.assertIn('if [ "${{ matrix.kind }}" = candidate ]; then', self.workflow)
        self.assertIn('git diff --exit-code "$scope_base" HEAD -- h1 experiments qualification viewer',
                      self.workflow)
        self.assertIn('git diff --name-status "$scope_base" HEAD > product_evidence/source-diff.txt',
                      self.workflow)
        self.assertIn('scope-base-sha.txt', self.workflow)
        self.assertIn('4162c3d47016150076b226ebe2585073a785547a', self.workflow)

    def test_protected_source_diff_guard_accepts_product_edit_refuses_h1_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            env = os.environ | {
                'GIT_AUTHOR_NAME': 'CI fixture',
                'GIT_AUTHOR_EMAIL': 'ci-fixture@example.invalid',
                'GIT_COMMITTER_NAME': 'CI fixture',
                'GIT_COMMITTER_EMAIL': 'ci-fixture@example.invalid',
            }
            def git(*args):
                return subprocess.run(('git', '-C', str(repo), *args), env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, check=False)
            self.assertEqual(git('init', '-q').returncode, 0)
            (repo / 'h1').mkdir()
            (repo / 'h1' / 'physics.py').write_text('original source\n')
            (repo / 'README.md').write_text('original README\n')
            self.assertEqual(git('add', '.').returncode, 0)
            self.assertEqual(git('commit', '-qm', 'baseline').returncode, 0)
            base = git('rev-parse', 'HEAD').stdout.strip()
            self.assertEqual(len(base), 40)
            (repo / 'README.md').write_text('product-only edit\n')
            self.assertEqual(git('add', '.').returncode, 0)
            self.assertEqual(git('commit', '-qm', 'product').returncode, 0)
            args = ('diff', '--exit-code', base, 'HEAD', '--',
                    'h1', 'experiments', 'qualification', 'viewer')
            self.assertEqual(git(*args).returncode, 0)
            (repo / 'h1' / 'physics.py').write_text('physically changed source\n')
            self.assertEqual(git('add', '.').returncode, 0)
            self.assertEqual(git('commit', '-qm', 'not product only').returncode, 0)
            self.assertEqual(git(*args).returncode, 1)


if __name__ == '__main__':
    unittest.main()
