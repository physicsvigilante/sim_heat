"""Read-only first-attempt H1 admission + source-only preview receipt.

This evaluator never edits authored files, runs a native solver, or computes heat
trajectories. Nonadmission is an evidence outcome, not something to auto-repair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / 'experiments' / 'h1_t1_unsealed'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(case: str, out: Path) -> dict:
    model = CASES / case / 'model.mo'
    study = CASES / case / 'study.json'
    originals = {p.name: digest(p) for p in (model, study)}
    command = [sys.executable, '-B', '-m', 'h1', str(study), '--root', str(CASES)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
    (out / (case + '.admission.stdout.json')).write_text(result.stdout, encoding='utf-8')
    (out / (case + '.admission.stderr.txt')).write_text(result.stderr, encoding='utf-8')
    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        parsed = {'unparseableOutput': True}
    if result.returncode not in (0, 2) or parsed.get('nativeExecuted') is not False:
        raise RuntimeError(f'{case}: unexpected H1 stage, missing nativeExecuted=false, or subprocess error')
    if bool(parsed.get('admitted')) != (result.returncode == 0):
        raise RuntimeError(f'{case}: admission return code and report disagree')
    result_summary = {
        'case': case, 'originalModelSha256': originals['model.mo'],
        'originalStudySha256': originals['study.json'],
        'admissionExitCode': result.returncode, 'admitted': parsed['admitted'],
        'stage': parsed.get('stage'), 'refusalCode': parsed.get('code'),
        'nativeExecuted': False, 'firstAttemptUnmodified': True,
        'publicRequestStatus': 'not_computed' if parsed['admitted'] else 'refused_or_not_tested',
        'previewGenerated': False,
    }
    if parsed['admitted']:
        requests = parsed.get('requests', [])
        if not requests or any(r.get('status') != 'not_computed' for r in requests):
            raise RuntimeError(f'{case}: admitted with fabricated or absent request statuses')
        result_summary['requestCount'] = len(requests)
        preview_path = out / (case + '.source-only.json')
        preview_cmd = [sys.executable, '-B', '-m', 'h1.source_preview', str(study), '--root', str(CASES), '--out', str(preview_path)]
        preview_run = subprocess.run(preview_cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
        (out / (case + '.preview.stdout.txt')).write_text(preview_run.stdout, encoding='utf-8')
        (out / (case + '.preview.stderr.txt')).write_text(preview_run.stderr, encoding='utf-8')
        if preview_run.returncode != 0:
            raise RuntimeError(f'{case}: admitted H1 but source-only preview generator refused: {preview_run.stderr}')
        obj = json.loads(preview_path.read_bytes())
        meta = obj['source']
        if (obj.get('status') != 'admitted_source_only' or obj.get('studyId') != json.loads(study.read_bytes()).get('id')
                or obj.get('mode') not in ('steady', 'transient')
                or meta.get('evidenceKind') != 'authored_source_only'
                or meta.get('nativeExecuted') is not False or meta.get('nativeQualified') is not False
                or meta.get('sourceFidelityQualified') is not False or meta.get('publicRequestStatus') != 'not_computed'
                or meta.get('modelSha256') != originals['model.mo'] or meta.get('studySha256') != originals['study.json']
                or any(r.get('status') != 'not_computed' for r in obj['requests'])):
            raise RuntimeError(f'{case}: source-only preview provenance/identity/status violated')
        result_summary.update(previewGenerated=True, componentCount=len(obj['components']),
                              logicalNodeCount=len(obj['nodes']), rodCount=len(obj['rods']),
                              sourceOnlySha256=digest(preview_path))
    for p in (model, study):
        if digest(p) != originals[p.name]:
            raise RuntimeError(f'{case}: first-attempt source was modified by evaluation')
    return result_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cases = [run_case(case, out) for case in ('S','T')]
    receipt = {'schema':'sim_heat.h1_t1_unsealed_outcomes/1',
               'evidenceKind':'authored_source_only', 'precommittedKeyVerified': False,
               'keyState':'original_key_unavailable', 'scoringMode':'retrospective_public_task',
               'nativeExecuted':False, 'firstAttemptOnly':True,
               'cases':cases,
               'unsupportedX':'original REFUSAL.md preserved; no H1 model submitted for radiation'}
    (out / 'outcomes.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
