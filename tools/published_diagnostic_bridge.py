"""Select one existing archived native *diagnostic* pair by admitted source identity.

This is a read-only adapter over already published offline source-pair metadata.
It does not evaluate physics, authenticate GitHub, invoke OpenModelica or
promote `diagnostic_only` / `nativeQualified=False` to a qualified result.
Browser-imported source-only JSON must NEVER decide which result is served.
"""
from __future__ import annotations

import hashlib
from html import escape
import json
from pathlib import Path

from h1.model import Refusal
from h1.study import strict_json
from viewer.network.tools.build_case import stable_json
from viewer.network.tools.build_compare_index import compile_pair_index, safe_file

ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / 'viewer' / 'network'
CASE_INDEX = NETWORK / 'data' / 'index.json'
PAIR_INDEX = NETWORK / 'data' / 'compare_index.json'
SOURCE_MANIFEST = NETWORK / 'data' / 'compare_sources.json'
COMPARE_ROUTE = '/viewer/network/compare.html'


def published_diagnostic_pair(baseline: dict, successor: dict):
    """Return (allowlisted public diagnostic resources, immutable link label).

    Missing/inconsistent archived evidence simply means NO link. Source-only
    admission remains usable; it must never fall back to checking/reference
    calculations as though they were measured output.
    """
    if successor is None:
        return {}, None
    try:
        # Rebuild the fixed source-linked pair; refuse even a semantically
        # identical but byte-different reserialization of the published index.
        # Source-relative byte integrity is NOT external owner authentication.
        generated = compile_pair_index(ROOT, SOURCE_MANIFEST, CASE_INDEX)
        if stable_json(generated) != safe_file(PAIR_INDEX, ROOT):
            return {}, None
        matching = [p for p in generated['pairs']
                    if p['baseline'] == baseline['studyId']
                    and p['successor'] == successor['studyId']
                    and p['revision']['parentModelSha256'] == baseline['source']['modelSha256']
                    and p['revision']['parentStudySha256'] == baseline['source']['studySha256']
                    and p['revision']['childModelSha256'] == successor['source']['modelSha256']
                    and p['revision']['childStudySha256'] == successor['source']['studySha256']]
        if len(matching) != 1:
            return {}, None
        pair = matching[0]
        catalog = strict_json(safe_file(CASE_INDEX, ROOT).decode('utf-8'))
        selected = [c for c in catalog['cases'] if c['id'] in (pair['baseline'], pair['successor'])]
        if len(selected) != 2:
            return {}, None
        resources = {}
        for entry in selected:
            # compile_pair_index already checked original bytes and hash;
            # independently re-read once and pin the actual bytes served.
            raw = safe_file(NETWORK / entry['file'], ROOT)
            if hashlib.sha256(raw).hexdigest() != entry['sha256']:
                return {}, None
            resources['/viewer/network/' + entry['file']] = (raw, 'application/json; charset=utf-8')
        resources.update({
            '/viewer/network/data/index.json': (
                stable_json({'schema': catalog['schema'], 'cases': selected}),
                'application/json; charset=utf-8'),
            '/viewer/network/data/compare_index.json': (
                stable_json({'schema': generated['schema'], 'pairs': [pair]}),
                'application/json; charset=utf-8'),
        })
        # Reuse exact, independently reviewed archived native viewer JS. The
        # network explorer and unrelated archive cases remain inaccessible.
        for file in ('compare.mjs', 'compare_core.mjs', 'core.mjs'):
            resources['/viewer/network/' + file] = (
                safe_file(NETWORK / file, ROOT), 'text/javascript; charset=utf-8')
        original = safe_file(NETWORK / 'compare.html', ROOT).decode('utf-8')
        nav = '<a href="./index.html">Open network explorer</a>'
        if original.count(nav) != 1:
            return {}, None
        resources[COMPARE_ROUTE] = (
            original.replace(nav, '<a href="/viewer/source_preview/">Return to admitted source inputs</a>').encode('utf-8'),
            'text/html; charset=utf-8')
        # A stable, server-only label identifies the ORIGINAL preadmitted pair.
        # It is not selected by uploaded browser preview JSON or graph state.
        label = {'pairId': pair['id'], 'baselineStudy': pair['baseline'],
                 'successorStudy': pair['successor'],
                 'baselineStudySha256': baseline['source']['studySha256'],
                 'successorStudySha256': successor['source']['studySha256']}
        return resources, label
    except (Refusal, OSError, UnicodeError, ValueError, KeyError, TypeError,
            RecursionError, json.JSONDecodeError):
        return {}, None


def published_link_markup(label: dict | None, *, compared: bool = False) -> str:
    if label is None:
        if not compared:
            return ''
        return (
            '<aside id="no-published-diagnostic" class="panel" '
            'aria-label="No recorded results for this source pair">'
            '<div class="eyebrow">07 · historical results</div>'
            '<h2>No matching published diagnostic for these original sources</h2>'
            '<p>Both authored studies were admitted for source comparison, '
            'but there is no source-identity-matched recorded result pair in '
            'the existing published catalog. No simulation was run, and '
            'checking/reference data are never substituted for missing native results.</p>'
            '</aside>'
        )
    a, b = escape(label['baselineStudy']), escape(label['successorStudy'])
    return (
        '<aside id="published-diagnostic-link" class="panel" aria-label="Original published diagnostic only">'
        '<div class="eyebrow">07 · separately recorded native diagnostics</div>'
        '<h2>Explore the historical recorded comparison</h2>'
        f'<p>Only the <strong>original server-admitted {a} → {b} source pair</strong> '
        'matches an already published, internally source-linked diagnostic. '
        'This link NEVER follows a subsequently imported browser scenario.</p>'
        f'<p><a href="{COMPARE_ROUTE}" id="open-recorded-diagnostic">'
        'Open original saved temperature and heat-flow histories</a></p>'
        '<p class="small">Existing OpenModelica archive only: '
        '<code>diagnostic_only</code>, <code>nativeQualified=false</code>. '
        'These are recorded historical samples, NOT new calculations, current OpenModelica '
        'execution, independently authenticated original source or qualified reference data. '
        'For a different source pair with no published diagnostic, no recorded results are available.</p>'
        '</aside>'
    )
