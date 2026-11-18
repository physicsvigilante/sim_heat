"""Static documentation parity and the documented read-only authoring recipe."""
from collections import Counter
from contextlib import redirect_stdout
import hashlib
from html.parser import HTMLParser
import io
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from tools.render_product_docs import DOCUMENTS, build, href, render

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags, self.attrs, self.links, self.document_links, self.code = [], [], [], [], []
        self.in_document = self.in_code = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.tags.append(tag); self.attrs.extend(attrs)
        if tag == 'article' and data.get('id') == 'document':
            self.in_document = True
        if tag == 'a':
            self.links.append(data['href'])
            if self.in_document:
                self.document_links.append(data['href'])
        if tag == 'code':
            self.in_code = True

    def handle_endtag(self, tag):
        if tag == 'article':
            self.in_document = False
        if tag == 'code':
            self.in_code = False

    def handle_data(self, text):
        if self.in_code:
            self.code.append(text)


class ProductDocsTests(unittest.TestCase):
    def test_committed_html_matches_canonical_markdown(self):
        build(ROOT, check=True)
        for name in DOCUMENTS:
            raw = (ROOT / 'docs' / (name + '.md')).read_bytes()
            page = (ROOT / 'docs' / (name + '.html')).read_text()
            self.assertIn(hashlib.sha256(raw).hexdigest(), page)

    def test_source_links_and_python_code_are_preserved(self):
        for name in DOCUMENTS:
            raw = (ROOT / 'docs' / (name + '.md')).read_bytes()
            page = Page(render(raw, name).decode())
            targets = re.findall(r'\]\(([^\s)]+)\)', raw.decode())
            self.assertEqual(Counter(page.document_links), Counter(href(x) for x in targets))
            for block in re.findall(r'```(?:python|sh)\n(.*?)\n```', raw.decode(), re.S):
                self.assertIn(block, page.code)

    def test_generated_local_links_and_fragments_resolve(self):
        for name in DOCUMENTS:
            path = ROOT / 'docs' / (name + '.html')
            page = Page(path.read_text())
            for target in page.links:
                url = urlsplit(target)
                if url.scheme:
                    self.assertEqual(url.scheme, 'https')
                    continue
                destination = (path.parent / unquote(url.path)).resolve() if url.path else path
                self.assertTrue(destination.is_relative_to(ROOT))
                self.assertTrue(destination.is_file(), target)
                if url.fragment:
                    self.assertIn(('id', url.fragment), Page(destination.read_text()).attrs)

    def test_generated_pages_are_static_with_table_navigation(self):
        for name in DOCUMENTS:
            text = (ROOT / 'docs' / (name + '.html')).read_text()
            page = Page(text)
            self.assertFalse(set(page.tags) & {'script', 'iframe', 'form', 'object', 'embed'})
            self.assertFalse([x for x, _ in page.attrs if x.lower().startswith('on')])
            self.assertNotRegex(text, r'url\s*\(')
            self.assertIn(('tabindex', '0'), page.attrs)
            self.assertEqual(page.tags.count('th'), page.attrs.count(('scope', 'col')))
            self.assertEqual(page.tags.count('table'), page.tags.count('caption'))

    def test_html_is_escaped_and_unsafe_link_schemes_refuse(self):
        page = render(b'# Test\n\n<script>alert(1)</script> & **bold** `a<b`\n', 'AUTHORING').decode()
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>', page)
        for bad in ('javascript:alert', 'data:text/html,test', '//example.com/a', 'file:///tmp/a', 'a\\b'):
            with self.subTest(link=bad), self.assertRaises(ValueError):
                href(bad)

    def test_invalid_document_blocks_refuse(self):
        for text in ('no title', '# Test\n\n```python\nunfinished', '# Test\n\n# Other',
                     '# Test\n\n## Repeat\n\n## Repeat', '# Test\n\n| a |\n| no |',
                     '# Test\n\n| a | b |\n|---|---|\n| one |'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                render(text.encode(), 'AUTHORING')

    def test_check_mode_detects_drift_without_repairing_it(self):
        with TemporaryDirectory() as d:
            root = Path(d); (root / 'docs').mkdir()
            for name in DOCUMENTS:
                (root / 'docs' / (name + '.md')).write_text('# Test\n')
            build(root)
            target = root / 'docs/CAPABILITIES.html'
            target.write_text('stale')
            with self.assertRaises(ValueError):
                build(root, check=True)
            self.assertEqual(target.read_text(), 'stale')

    def test_current_guide_and_historical_labels_are_explicit(self):
        entry = (ROOT / 'index.html').read_text()
        registry = (ROOT / 'docs/CAPABILITIES.md').read_text()
        guide = (ROOT / 'docs/AUTHORING.md').read_text()
        self.assertIn('href="docs/AUTHORING.html"', entry)
        self.assertIn('historical H1 foundation contract', entry)
        self.assertIn('Historical H1 foundation contract', registry)
        self.assertIn('Current authoring guide', registry)
        self.assertIn('not_computed', guide)
        self.assertIn('Stop before new native execution', guide)
        self.assertIn('href="viewer/source_preview/index.html"', entry)
        self.assertIn('not_computed', entry)
        self.assertIn('[generic H1 source-only inspector](../viewer/source_preview/index.html)', guide)
        self.assertIn('[Generic source-only inspector](../viewer/source_preview/index.html)', registry)

    def test_documented_walkthrough_executes_only_real_admission_cli(self):
        blocks = re.findall(r'```python\n(.*?)\n```', (ROOT / 'docs/AUTHORING.md').read_text(), re.S)
        self.assertEqual(len(blocks), 1)
        originals = [ROOT / 'h1/cases/D1/model.mo', ROOT / 'h1/cases/D1/study.json']
        before = [p.read_bytes() for p in originals]
        real_run, commands = subprocess.run, []
        def admission_only(command, **kwargs):
            self.assertEqual(command[:4], [sys.executable, '-B', '-m', 'h1'])
            self.assertEqual(command[5], '--root')
            self.assertEqual(len(command), 7)
            commands.append(command)
            return real_run(command, **kwargs)
        old_cwd = Path.cwd()
        output = io.StringIO()
        try:
            os.chdir(ROOT)
            with patch('subprocess.run', side_effect=admission_only), redirect_stdout(output):
                exec(compile(blocks[0], 'AUTHORING.md:walkthrough', 'exec'), {'__name__': '__main__'})
        finally:
            os.chdir(old_cwd)
        self.assertEqual(len(commands), 4)
        self.assertEqual(output.getvalue().count('PASS:'), 3)
        self.assertEqual(before, [p.read_bytes() for p in originals])
        self.assertTrue(all(not Path(cmd[4]).exists() for cmd in commands))


if __name__ == '__main__':
    unittest.main()
