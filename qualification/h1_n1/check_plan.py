"""Read-only N1 design checks and NEW analytical screening; NEVER native execution.

No shell, compiler probe, build, launch, network call or historical-reference write.
A successful exit means the plan is internally checked, NOT execution-ready.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from h1 import reference
from h1.model import Refusal, internal_exports
from h1.study import load_study
from h1.verification import bind_reference
from tools.h1_compare_companions import compare


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def enforce(plan: dict) -> None:
    if (plan['schema'] != 'sim_heat.h1_n1_pre_native_design/1'
            or plan['state'] != 'PLAN_ONLY_NOT_EXECUTION_READY'
            or plan['nativeExecutionAuthorized'] is not False
            or any(plan['nativeOperationsPerformed'].values())
            or any(plan['executionGates'].values())
            or plan['coverage']['nativeQualifiedMayBecomeTrue'] is not False
            or plan['coverage']['referenceErrorFractionMaximum'] != .01
            or plan['futureMaximumBudget']['automaticRetries'] != 0
            or plan['futureMaximumBudget']['installationCommands'] != 0):
        raise ValueError('Plan-only authority or evidence boundary changed')
    expected = [('primary', 2400, 1e-8), ('tight', 2400, 1e-10), ('dense', 4800, 1e-8)]
    if [(r['label'], r['intervals'], r['tolerance']) for r in plan['variants']] != expected:
        raise ValueError('Unreviewed run settings')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--author-source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    folder = Path(__file__).resolve().parent
    plan = json.loads((folder / 'plan.json').read_text())
    enforce(plan)
    protected = {p: digest(ROOT / p) for p in plan['protectedSha256']}
    if protected != plan['protectedSha256']:
        raise ValueError('Pinned physics/reference/runner changed')
    author = args.author_source.resolve()
    root = author / plan['authorEvidence']['caseRoot']
    case = root / 'T'
    if any(p.is_symlink() for p in (case, root, author)):
        raise ValueError('Symlink source refused')
    before = {p.name: digest(p) for p in case.iterdir() if p.is_file()}
    if (before['model.mo'] != plan['authorEvidence']['modelSha256']
            or before['study.json'] != plan['authorEvidence']['studySha256']):
        raise ValueError('Original T1-T input changed')
    study = load_study(case / 'study.json', root)
    facts = reference.read_reference(folder / 'reference-facts.json')
    bind_reference(study, facts)
    exports = internal_exports(study.model)
    if len(exports) != 77 or len(study.grid) != 2401 or len(study.data['requests']) != 8:
        raise ValueError('Original observation/export/time coverage changed')
    controls = []
    for label, mutation in (
        ('stale_model_sha', lambda s: s.update(modelSha256='0' * 64)),
        ('changed_conductivity', lambda s: s['rods']['T01'].update(k=66)),
        ('reversed_rod_ports', lambda s: s['rods']['T01'].update(a='J_Upper', b='W')),
    ):
        bad = deepcopy(facts)
        mutation(bad)
        try:
            bind_reference(study, bad)
        except Refusal as exc:
            controls.append({'name': label, 'refused': True, 'code': exc.code})
        else:
            raise AssertionError('Negative source control admitted: ' + label)
    bad_plan = deepcopy(plan)
    bad_plan['nativeExecutionAuthorized'] = True
    try:
        enforce(bad_plan)
    except ValueError:
        controls.append({'name': 'native_authorization_in_plan', 'refused': True})
    else:
        raise AssertionError('Plan gained execution authority')

    # NEW N1 temporary diagnostics ONLY. Do not save a reference bundle or touch
    # h1/reference_cases or qualification/h1_c1. Same-author float64 algorithms
    # are not the independent >=100x accuracy certificate the plan requires.
    primary = reference.prepare(facts)
    dense_facts = deepcopy(facts)
    dense_facts['analysis']['intervals'] = 4800
    dense_study = deepcopy(study.data)
    dense_study['id'] += '_N1_DENSE'
    dense_study['analysis']['intervals'] = 4800
    dense_bytes = (json.dumps(dense_study, sort_keys=True, indent=2) + '\n').encode()
    dense_facts['id'] = dense_study['id']
    dense_facts['studySha256'] = hashlib.sha256(dense_bytes).hexdigest()
    dense_facts['provenance'] += ' New N1 hypothetical analysis-only dense successor; not authored original.'
    dense = reference.prepare(dense_facts)
    mismatches = {k: {'primary': a, 'dense': dense['allowances'][k]}
                  for k, a in primary['allowances'].items() if a != dense['allowances'][k]}
    if not mismatches:
        raise AssertionError('Observed comparator blocker changed; investigate, do not assume solved')
    try:
        compare(primary['columns'], primary, dense['columns'], dense)
    except Refusal as exc:
        if exc.code != 'comparison' or 'allowance differs' not in str(exc):
            raise
        comparator = {'status': 'REFUSED_AS_EXPECTED', 'code': exc.code, 'message': str(exc)}
    else:
        raise AssertionError('Existing comparator unexpectedly accepted unequal allowances')
    if before != {p.name: digest(p) for p in case.iterdir() if p.is_file()}:
        raise AssertionError('Original author inputs modified')
    if protected != {p: digest(ROOT / p) for p in protected}:
        raise AssertionError('Protected file changed')
    result = {
        'schema': 'sim_heat.h1_n1_plan_checks/1', 'planChecksPassed': True,
        'executionReady': False, 'nativeExecuted': False, 'nativeQualified': False,
        'referenceAccuracyCertified': False, 'referenceBundlePersisted': False,
        'scope': 'NEW_N1_ANALYTICAL_PLANNING_DIAGNOSTIC_ONLY',
        'python': platform.python_version(), 'planSha256': digest(folder / 'plan.json'),
        'referenceFactsSha256': digest(folder / 'reference-facts.json'),
        'sourceFactBinding': 'PASS; same-author source facts still require independent review',
        'originalInputHashes': before, 'mandatoryExports': len(exports),
        'primarySamples': len(study.grid), 'denseSamples': len(dense['grid']),
        'negativeControls': controls,
        'existingCompanionComparator': comparator,
        'gridAllowanceMismatches': mismatches,
        'originalsAndProtectedFilesUnchanged': True,
        'openExecutionGates': list(plan['executionGates']),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, sort_keys=True, allow_nan=False)
        output.write('\n')
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
