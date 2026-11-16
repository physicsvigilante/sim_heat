"""Read-only source provenance compiler for H1 one-rod conductivity revisions.

A compare-index row is admitted only when:
 * both H1 studies/models pass the *unchanged* public grammar and source hashes;
 * the child links directly to the parent and changes exactly one existing rod.k;
 * all other physical bindings, topology, requests and time grid remain identical;
 * both native viewer cases match their immutable source catalog SHA, physical
   owner graph, model/study SHA, record grids and explicitly pinned evidence IDs.

Never executes OpenModelica, constructs trajectories or authenticates GitHub.
The original run/artifact/ZIP/commit pins must be externally verified before
adopting a new pair. A re-pinned fabricated matching pair is NOT native proof.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from h1.model import require
from h1.study import load_study, strict_json
from viewer.network.tools.build_case import owner_graph, sha, stable_json

PAIR_SCHEMA = 'sim_heat.viewer.compare_sources/1'
INDEX_SCHEMA = 'sim_heat.viewer.compare_index/2'
NATIVE_SCHEMA = 'sim_heat.viewer.native_case/1'
CASE_INDEX_SCHEMA = 'sim_heat.viewer.case_index/1'
EVIDENCE_KEYS = frozenset((
    'runId', 'artifactId', 'artifactSha256', 'compiledSourceCommit',
    'archiveEntry', 'csvSha256', 'rawMatSha256',
))
SHA = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')
IDENT = re.compile(r'[A-Za-z][A-Za-z0-9_]*\Z')
STUDY_PATH = re.compile(r'h1/cases/[A-Za-z][A-Za-z0-9_]*/study\.json\Z')
CASE_PATH = re.compile(r'data/[A-Za-z0-9_]+\.json\Z')


def check_keys(value, fields, label):
    require(type(value) is dict and set(value) == set(fields),
            'pair_provenance', label+' unexpected/missing fields')


def safe_file(path: Path, root: Path) -> bytes:
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(root.resolve()) and
            path.stat().st_size <= 4_000_000,
            'pair_provenance', 'absent, escaped or oversized source file: '+str(path))
    return path.read_bytes()


def native_source(source):
    check_keys(source, EVIDENCE_KEYS, 'externally pinned native evidence')
    require(type(source['runId']) is int and source['runId'] > 0 and
            type(source['artifactId']) is int and source['artifactId'] > 0 and
            SHA.fullmatch(source['artifactSha256']) and
            COMMIT.fullmatch(source['compiledSourceCommit']) and
            SHA.fullmatch(source['csvSha256']) and
            SHA.fullmatch(source['rawMatSha256']) and
            isinstance(source['archiveEntry'], str) and
            re.fullmatch(r'case_[0-9]{2}/normalized\.csv', source['archiveEntry']),
            'pair_provenance', 'unusable externally pinned native identity')
    return dict(source)


def check_source_relation(a, b):
    # Distinct *case result selectors* are necessary; different GitHub runs
    # are NOT mandatory. One run can archive two models in distinct slots.
    # GitHub artifact IDs are global: two cases citing the same artifact ID
    # must agree on its run and exact original ZIP SHA.
    same_artifact = a['artifactId'] == b['artifactId']
    if same_artifact:
        require(a['runId'] == b['runId'] and
                a['artifactSha256'] == b['artifactSha256'],
                'pair_provenance', 'same original artifact ID has conflicting host/ZIP identity')
    require((a['runId'], a['artifactId'], a['archiveEntry']) !=
            (b['runId'], b['artifactId'], b['archiveEntry']),
            'pair_provenance', 'both sides point to one native result slot')


def read_catalog(root: Path, catalog_path: Path):
    raw = strict_json(safe_file(catalog_path, root).decode('utf-8'))
    check_keys(raw, {'schema', 'cases'}, 'source case catalog')
    require(raw['schema'] == CASE_INDEX_SCHEMA and isinstance(raw['cases'], list) and
            1 <= len(raw['cases']) <= 32,
            'pair_provenance', 'unsupported source catalog')
    cases = {}
    for entry in raw['cases']:
        check_keys(entry, {'id', 'file', 'title', 'sha256'}, 'case catalog entry')
        require(isinstance(entry['id'], str) and IDENT.fullmatch(entry['id']) and
                entry['id'] not in cases and isinstance(entry['file'], str) and
                CASE_PATH.fullmatch(entry['file']) and
                isinstance(entry['sha256'], str) and SHA.fullmatch(entry['sha256']),
                'pair_provenance', 'duplicate/unsafe case catalog')
        case_bytes = safe_file(catalog_path.parent.parent / entry['file'], root)
        require(sha(case_bytes) == entry['sha256'],
                'pair_provenance', 'source case SHA-256 disagrees with catalog')
        case = strict_json(case_bytes.decode('utf-8'))
        require(case.get('id') == entry['id'] and case.get('title') == entry['title'],
                'pair_provenance', 'source case identity/title mismatch')
        cases[entry['id']] = case
    return cases


def compile_pair_index(root: Path, source_plan: Path,
                       catalog_path: Path | None = None) -> dict:
    root = root.resolve(strict=True)
    catalog_path = catalog_path or root/'viewer/network/data/index.json'
    inputs = strict_json(safe_file(source_plan, root).decode('utf-8'))
    check_keys(inputs, {'schema', 'pairs'}, 'pair source manifest')
    require(inputs['schema'] == PAIR_SCHEMA and isinstance(inputs['pairs'], list)
            and 1 <= len(inputs['pairs']) <= 20,
            'pair_provenance', 'unsupported pair source manifest')
    cases = read_catalog(root, catalog_path)
    pairs, ids = [], set()
    for item in inputs['pairs']:
        check_keys(item, {'id', 'title', 'baseline', 'successor',
                          'baselineStudy', 'successorStudy', 'expectedNative'},
                   'source pair')
        require(type(item['id']) is str and IDENT.fullmatch(item['id']) and
                item['id'] not in ids and
                type(item['title']) is str and 0 < len(item['title']) <= 120 and
                all(type(item[key]) is str and IDENT.fullmatch(item[key])
                    for key in ('baseline', 'successor')) and
                item['baseline'] != item['successor'] and
                item['baseline'] in cases and item['successor'] in cases,
                'pair_provenance', 'missing, invalid or duplicate pair case')
        ids.add(item['id'])
        check_keys(item['expectedNative'], {'baseline', 'successor'}, 'native pair')
        expected_a = native_source(item['expectedNative']['baseline'])
        expected_b = native_source(item['expectedNative']['successor'])
        check_source_relation(expected_a, expected_b)
        paths = []
        for key in ('baselineStudy', 'successorStudy'):
            value = item[key]
            require(type(value) is str and STUDY_PATH.fullmatch(value),
                    'pair_provenance', 'unsafe H1 source-study path')
            paths.append(root/value)
        parent = load_study(paths[0], root/'h1/cases')
        child = load_study(paths[1], root/'h1/cases') # enforces narrow revision semantics
        require(parent.path != child.path and
                parent.request_report['admitted'] and child.request_report['admitted'] and
                parent.data['id'] == item['baseline'] and
                child.data['id'] == item['successor'] and
                parent.data['mode'] == child.data['mode'] == 'transient' and
                'revision' not in parent.data and 'revision' in child.data,
                'pair_provenance', 'comparison is not an admitted root and direct successor')
        rev = child.data['revision']
        require((child.path.parent / rev['parentStudyPath']).resolve() == parent.path and
                rev['parentStudySha256'] == parent.sha256 and
                rev['parentModelSha256'] == parent.model_sha256 and
                parent.data['requests'] == child.data['requests'] and
                parent.data['analysis'] == child.data['analysis'] and
                parent.grid == child.grid,
                'pair_provenance', 'changed requests, analysis or unrelated parent')
        rod, field = rev['target'].split('.')
        require(field == 'k' and rod in parent.model.components and
                parent.model.components[rod].kind.startswith('Rod'),
                'pair_provenance', 'non-rod or wrong revision field')
        before = parent.model.components[rod].value('k')
        after = child.model.components[rod].value('k')
        require(all(type(x) in (float,int) and math.isfinite(x) and x>0
                    for x in (before,after)) and before != after,
                'pair_provenance', 'no effective positive single conductivity change')

        native_cases = []
        for label, study, evidence in (
                ('baseline', parent, expected_a),
                ('successor', child, expected_b)):
            case = cases[item[label]]
            require(case.get('schema') == NATIVE_SCHEMA and
                    case.get('modelName') == study.model.name and
                    case.get('source', {}).get('modelSha256') == study.model_sha256 and
                    case.get('source', {}).get('studySha256') == study.sha256 and
                    case.get('source', {}).get('nativeQualified') is False and
                    case.get('source', {}).get('verificationStatus') == 'checks_passed' and
                    case.get('source', {}).get('publicRequestStatus') == 'diagnostic_only' and
                    case.get('source', {}).get('evidenceKind') == 'historical_native_diagnostic' and
                    case.get('source', {}).get('canonicalSamples') == len(study.grid) and
                    all(case['source'].get(k) == v for k,v in evidence.items()),
                    'pair_provenance', 'case has untrusted or wrong published native provenance')
            nodes, edges = owner_graph(study)
            require(case.get('graph') == {'nodes':nodes,'edges':edges} and
                    case.get('analysis') == {
                        'start':study.grid[0], 'stop':study.grid[-1],
                        'intervals':len(study.grid)-1},
                    'pair_provenance', 'viewer graph or analysis is not the actual H1 study')
            columns, samples = case.get('columns'), case.get('samples')
            required = {'time'} | {n['temperature'] for n in nodes} | {
                n['energy'] for n in nodes if 'energy' in n} | {
                n['power'] for n in nodes if 'power' in n} | {
                e['flow'] for e in edges}
            require(type(columns) is list and len(columns) == len(set(columns)) and
                    set(columns) == required and columns[0] == 'time' and
                    type(samples) is list and len(samples) >= 2 and
                    all(type(row) is list and len(row) == len(columns) and
                        all(type(x) in (float, int) and math.isfinite(x) for x in row)
                        for row in samples),
                    'pair_provenance', 'missing/invalid native saved columns or samples')
            saved = {float(t) for t in study.grid}
            times = [row[0] for row in samples]
            require(times[0] == study.grid[0] and times[-1] == study.grid[-1] and
                    all(t in saved for t in times) and
                    all(a < b for a,b in zip(times,times[1:])),
                    'pair_provenance', 'case uses fabricated/unsaved physical time')
            native_cases.append(case)
        a, b = native_cases
        require(a['graph'] == b['graph'] and
                a['columns'] == b['columns'] and
                a['analysis'] == b['analysis'] and
                [row[0] for row in a['samples']] == [row[0] for row in b['samples']],
                'pair_provenance', 'physical topology/observations/saved time mismatch')
        for node in a['graph']['nodes']:
            if node['kind'] in ('body', 'boundary'):
                field_name = node['temperature']
                j = a['columns'].index(field_name)
                require(a['samples'][0][j] == b['samples'][0][j],
                        'pair_provenance', 'changed initial/maintained temperature')
                if node['kind'] == 'body':
                    energy_col = a['columns'].index(node['energy'])
                    require(abs(a['samples'][0][energy_col]) <= 1e-8 and
                            abs(b['samples'][0][energy_col]) <= 1e-8,
                            'pair_provenance', 'initial body energy is not relative to zero')
        require(any(e['id'] == rod and e['flow'] == rod+'.Q_flow'
                    for e in a['graph']['edges']),
                'pair_provenance', 'revised source rod missing from native graph')
        pairs.append({
            'id':item['id'], 'title':item['title'],
            'baseline':item['baseline'], 'successor':item['successor'],
            'revision':{
                'target':rev['target'], 'before':float(before), 'after':float(after),
                'unit':'W/(m·K)', 'origin':rev['origin'], 'reason':rev['reason'],
                'parentStudySha256':parent.sha256,
                'childStudySha256':child.sha256,
                'parentModelSha256':parent.model_sha256,
                'childModelSha256':child.model_sha256,
            },
            'sources':{'baseline':expected_a, 'successor':expected_b},
        })
    return {'schema':INDEX_SCHEMA, 'pairs':pairs}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--sources', type=Path,
                   default=ROOT/'viewer/network/data/compare_sources.json')
    p.add_argument('--catalog', type=Path, default=None)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    result = compile_pair_index(args.root, args.sources, args.catalog)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(stable_json(result))
    print({'schema': result['schema'], 'pairs':len(result['pairs']),
           'sha256':sha(args.out.read_bytes()), 'path':str(args.out)})


if __name__ == '__main__':
    main()
