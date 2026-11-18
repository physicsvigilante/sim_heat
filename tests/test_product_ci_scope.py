"""Product CI triggers and protected-source admission; never invokes a solver."""
from fnmatch import fnmatchcase
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/product-entry-ci.yml'


def product_pr_paths(text):
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
        self.assertNotIn('docs/**', self.paths)

    def test_current_checkout_base_guard_and_protected_paths(self):
        text = self.workflow
        self.assertIn('if [ "${{ matrix.kind }}" = candidate ]; then', text)
        # A PR event can carry a stale base SHA despite the actual synthetic
        # merge already using new main. Always trust and validate the checkout.
        self.assertIn('scope_base="$(git rev-parse HEAD^1)"', text)
        self.assertIn('candidate_parent="$(git rev-parse HEAD^2)"', text)
        self.assertIn('test "$candidate_parent" = "${{ github.event.pull_request.head.sha }}"', text)
        self.assertIn('scope_base="$(git merge-base HEAD origin/main)"', text)
        self.assertIn('git diff --exit-code "$scope_base" HEAD -- h1 experiments qualification viewer', text)
        self.assertIn('git diff --name-status "$scope_base" HEAD > product_evidence/source-diff.txt', text)
        self.assertIn('scope-base-sha.txt', text)
        self.assertIn('13260a62eb36d58802878c4d3dfb534ad1621f91', text)
        self.assertNotIn('scope_base="${{ github.event.pull_request.base.sha }}"', text)
        self.assertIn('tools/render_product_docs.py --check', text)
        self.assertIn('browser_product_docs.py', text)
        self.assertIn('browser_source_preview.py', text)

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
            old = git('rev-parse', 'HEAD').stdout.strip()
            (repo / 'h1' / 'physics.py').write_text('already integrated source\n')
            self.assertEqual(git('add', '.').returncode, 0)
            self.assertEqual(git('commit', '-qm', 'integrated prior H1 source').returncode, 0)
            current = git('rev-parse', 'HEAD').stdout.strip()
            (repo / 'README.md').write_text('product-only edit\n')
            self.assertEqual(git('add', '.').returncode, 0)
            self.assertEqual(git('commit', '-qm', 'product').returncode, 0)
            args = ('diff', '--exit-code', current, 'HEAD', '--',
                    'h1', 'experiments', 'qualification', 'viewer')
            self.assertEqual(git(*args).returncode, 0)
            self.assertEqual(git('diff', '--exit-code', old, 'HEAD', '--','h1').returncode, 1)
            (repo / 'h1' / 'physics.py').write_text('physically changed source again\n')
            self.assertEqual(git('add', '.').returncode, 0)
            self.assertEqual(git('commit', '-qm', 'not product only').returncode, 0)
            self.assertEqual(git(*args).returncode, 1)


if __name__ == '__main__':
    unittest.main()
