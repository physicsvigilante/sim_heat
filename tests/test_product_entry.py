"""Navigation/inventory regressions only; never import a solver or native runner."""
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class EntryHTML(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links, self.tags, self.attrs = [], {}, [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.tags.append(tag)
        self.attrs.extend(attrs)
        if 'id' in data:
            self.ids.append(data['id'])
        if tag == 'a':
            self.links[data.get('id', f'link-{len(self.links)}')] = data.get('href', '')


def local_target(root, parent, href):
    url = urlsplit(href)
    if url.scheme or url.netloc:
        return None
    target = (parent / unquote(url.path)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('link escapes repository')
    return target


class ProductEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text(encoding='utf-8')
        cls.page = EntryHTML(cls.html)
        cls.registry = (ROOT / 'docs/CAPABILITIES.md').read_text(encoding='utf-8')
        cls.catalog = json.loads((ROOT / 'viewer/network/data/index.json').read_text())

    def test_primary_destinations_and_unique_ids(self):
        self.assertEqual(self.page.links['enter-explorer'], 'viewer/network/index.html')
        self.assertEqual(self.page.links['compare-saved'], 'viewer/network/compare.html')
        self.assertEqual(self.page.links['read-registry'], 'docs/CAPABILITIES.html')
        self.assertFalse([key for key, count in Counter(self.page.ids).items() if count > 1])

    def test_three_categories_and_unqualified_status_remain_explicit(self):
        for name in ('archived-native', 'analytical-checking', 'expected-only'):
            self.assertIn(name, self.page.ids)
        for text in (self.html, self.registry):
            self.assertIn('diagnostic_only', text)
            self.assertIn('nativeQualified=false', text)
            self.assertIn('uncomputed', text)

    def test_start_page_is_static_and_local(self):
        self.assertFalse(set(self.page.tags) & {'script', 'iframe', 'form', 'object', 'embed'})
        self.assertFalse([name for name, _ in self.page.attrs if name.startswith('on')])
        for href in self.page.links.values():
            self.assertIsNotNone(local_target(ROOT, ROOT, href), href)
        self.assertNotRegex(self.html, r'url\s*\(')

    def test_all_start_page_links_resolve(self):
        for href in self.page.links.values():
            target = local_target(ROOT, ROOT, href)
            self.assertTrue(target.exists(), href)
            if href.startswith('#'):
                self.assertIn(href[1:], self.page.ids)

    def test_registry_local_links_resolve(self):
        for href in re.findall(r'\]\(([^)]+)\)', self.registry):
            target = local_target(ROOT, ROOT / 'docs', href)
            if target is not None:
                self.assertTrue(target.is_file(), href)
            else:
                self.assertEqual(urlsplit(href).scheme, 'https')

    def test_registry_matches_catalog_without_duplicate_cases(self):
        ids = re.findall(r'^\| `([^`]+)` \|', self.registry, flags=re.M)
        actual = [item['id'] for item in self.catalog['cases']]
        self.assertCountEqual(ids, actual)
        self.assertEqual(len(ids), len(set(ids)))

    def test_published_bytes_and_evidence_labels_match_existing_catalog(self):
        for item in self.catalog['cases']:
            with self.subTest(case=item['id']):
                path = local_target(ROOT, ROOT / 'viewer/network', item['file'])
                raw = path.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
                source = json.loads(raw)['source']
                self.assertIs(source['nativeQualified'], False)
                self.assertEqual(source['publicRequestStatus'], 'diagnostic_only')
                self.assertEqual(source['evidenceKind'], 'historical_native_diagnostic')

    def test_link_resolution_refuses_parent_escape(self):
        with self.assertRaises(ValueError):
            local_target(ROOT, ROOT, '../outside.md')
        with self.assertRaises(ValueError):
            local_target(ROOT, ROOT, '%2e%2e/outside.md')


if __name__ == '__main__':
    unittest.main()
