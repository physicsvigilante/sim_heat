"""One-shot, pinned H1 S1 native smoke on an ephemeral GitHub Actions host.

This is an execution-evidence adapter, NOT a general Modelica code runner or
native H1 acceptance. It never edits model data, retries, changes tolerances,
or treats diagnostic verification as qualification.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
ATTEMPT = ROOT / 'h1_cloud_s1_attempt'
S1 = ROOT / 'h1/cases/S1'
MODEL = S1 / 'model.mo'
STUDY = S1 / 'study.json'
LIBRARY = ROOT / 'experiments/h1_spike/SimHeat.mo'
REFERENCE = ROOT / 'h1/reference_cases/S1.json'
PINS = {
    'experiments/h1_spike/SimHeat.mo': 'e57955b6c32cb34321a6b1908306c4ea9a63ae259b95a5fd48c7e8d3b4da10ea',
    'h1/cases/S1/model.mo': '3228323714b2f886279aa90c46c1c49c9143e2d8b9c6de032389c750b6848f1c',
    'h1/cases/S1/study.json': '83bb6badc19e55008455083cde64adc2d53ba32c1d5f009d5b1b3594bd5f2405',
    'h1/reference_cases/S1.json': '47b1d9035230cb252a992a3fdcdbdf6fbefd350f901aacaaae9dae37b561635a',
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def run_once(command: list[str], *, cwd: Path, timeout: int, log_name: str) -> subprocess.CompletedProcess:
    # One command; no shell expansion, retries, or fallback. Preserve stdout/stderr.
    (ATTEMPT / f'{log_name}.command.json').write_text(json.dumps(command, indent=2) + '\n')
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout,
                                   env=os.environ.copy(), check=False)
    except subprocess.TimeoutExpired as exc:
        (ATTEMPT / f'{log_name}.stdout').write_bytes(exc.stdout or b'')
        (ATTEMPT / f'{log_name}.stderr').write_bytes(exc.stderr or b'')
        raise RuntimeError(f'{log_name}: timeout after {timeout}s; no retry') from exc
    (ATTEMPT / f'{log_name}.stdout').write_bytes(completed.stdout)
    (ATTEMPT / f'{log_name}.stderr').write_bytes(completed.stderr)
    (ATTEMPT / f'{log_name}.returncode.txt').write_text(str(completed.returncode) + '\n')
    if completed.returncode != 0:
        raise RuntimeError(f'{log_name}: exit code {completed.returncode}; no retry')
    return completed


def preflight():
    ATTEMPT.mkdir(exist_ok=False)
    manifest = {'stage': 'preflight', 'status': 'in_progress', 'executionBudget': {'buildModelCalls': 1, 'modelLaunches': 1},
                'nativeQualified': False, 'time': datetime.now(timezone.utc).isoformat(),
                'github': {'sha': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
                           'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'), 'ref': os.environ.get('GITHUB_REF')},
                'environment': {'python': sys.version, 'os': platform.platform(),
                                'numpy': importlib.metadata.version('numpy'),
                                'scipy': importlib.metadata.version('scipy')},
                'inputs': {}}
    write_json(ATTEMPT / 'attempt.json', manifest)
    try:
        for rel, expected in PINS.items():
            p = ROOT / rel
            observed = sha(p)
            manifest['inputs'][rel] = {'sha256': observed}
            if not observed == expected:
                raise RuntimeError(f'Pinned input mismatch: {rel}')
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            # A one-shot workflow must never be silently run on a different ref.
            if os.environ.get('GITHUB_REF') != 'refs/heads/experiment/h1-cloud-s1-1270-once' or \
                    os.environ.get('GITHUB_EVENT_NAME') != 'push' or os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
                raise RuntimeError('Refused unexpected event/branch/attempt; no run')
        run_once([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'h1/tests', '-q'],
                 cwd=ROOT, timeout=90, log_name='offline-tests')
        offline = run_once([sys.executable, '-B', '-m', 'h1', str(STUDY), '--root', str(ROOT / 'h1/cases')],
                           cwd=ROOT, timeout=30, log_name='admission')
        report = json.loads(offline.stdout.decode('utf-8'))
        if not report.get('admitted') or report.get('nativeExecuted'):
            raise RuntimeError('Offline study admission failed / invalid stage label')
        (ATTEMPT / 'admission.json').write_bytes(offline.stdout)
        seal = run_once([sys.executable, '-B', '-m', 'h1.verify', 'prepare',
                         '--study', str(STUDY), '--root', str(ROOT / 'h1/cases'),
                         '--reference', str(REFERENCE), '--out', str(ATTEMPT / 'reference.bundle.json')],
                        cwd=ROOT, timeout=60, log_name='reference-prepare')
        prepared = json.loads(seal.stdout.decode('utf-8'))
        bundle = json.loads((ATTEMPT / 'reference.bundle.json').read_text())
        if prepared.get('seal') != bundle['seal']:
            raise RuntimeError('Reference seal mismatch')
        (ATTEMPT / 'reference.seal').write_text(bundle['seal'] + '\n')
        manifest['referenceSeal'] = bundle['seal']
        manifest['status'] = 'preflight_passed'
    except Exception as exc:
        manifest['status'] = 'preflight_failed'
        manifest['error'] = repr(exc)
        raise
    finally:
        write_json(ATTEMPT / 'attempt.json', manifest)


def execute():
    manifest_path = ATTEMPT / 'attempt.json'
    if not manifest_path.exists():
        raise RuntimeError('Missing preflight; do not start native execution')
    manifest = json.loads(manifest_path.read_text())
    if manifest['status'] != 'preflight_passed':
        raise RuntimeError('Preflight not passed')
    manifest['status'] = 'native_running'
    manifest['counts'] = {'compilerVersionQueries': 0, 'buildModelCalls': 0, 'modelLaunches': 0}
    write_json(manifest_path, manifest)
    try:
        omc = shutil.which('omc')
        if not omc:
            raise RuntimeError('OpenModelica compiler not installed on runner')
        manifest['omcResolved'] = omc
        manifest['omcSha256'] = sha(Path(omc))
        # Exactly one explicit compiler version query. Setup action may perform its
        # own package-manager probes; they are distinct from this qualification.
        manifest['counts']['compilerVersionQueries'] = 1
        run_once([omc, '--version'], cwd=ATTEMPT, timeout=30, log_name='omc-version')
        def modelica_literal(p: Path) -> str:
            return str(p.resolve()).replace('\\', '/').replace('"', '\\"')
        # Modelica 4.0.0 is pinned; allowlist model inputs are byte-identical to
        # the admitted source. Steady t=0..1 is an algebraic export interval.
        mos = '\n'.join([
            'loadModel(Modelica, {"4.0.0"});',
            'getVersion(Modelica);',
            f'loadFile("{modelica_literal(LIBRARY)}");',
            f'loadFile("{modelica_literal(MODEL)}");',
            'buildModel(H1_S1, startTime=0.0, stopTime=1.0, numberOfIntervals=1, '
            'tolerance=1e-8, method="dassl", fileNamePrefix="H1_S1", '
            'outputFormat="csv", variableFilter=".*");',
            'getErrorString();',
            '',
        ])
        (ATTEMPT / 'build.mos').write_text(mos, encoding='utf-8')
        manifest['counts']['buildModelCalls'] = 1
        write_json(manifest_path, manifest)
        run_once([omc, str(ATTEMPT / 'build.mos')], cwd=ATTEMPT, timeout=900, log_name='build')
        exe = ATTEMPT / 'H1_S1'
        if not exe.is_file() or not os.access(exe, os.X_OK):
            raise RuntimeError('No executable from the one build; do not launch')
        if not (ATTEMPT / 'H1_S1_init.xml').exists():
            raise RuntimeError('Missing native initialization XML; do not launch')
        compile_log = (ATTEMPT / 'build.stdout').read_text(errors='replace') + \
                      (ATTEMPT / 'build.stderr').read_text(errors='replace')
        if 'Error:' in compile_log:
            raise RuntimeError('Compiler reported Error:; do not launch')
        manifest['executableSha256'] = sha(exe)
        manifest['status'] = 'build_succeeded'
        write_json(manifest_path, manifest)
        # Exactly ONE model executable launch, never via simulate() and never retried.
        manifest['counts']['modelLaunches'] = 1
        write_json(manifest_path, manifest)
        run_once([str(exe)], cwd=ATTEMPT, timeout=120, log_name='simulation')
        manifest['status'] = 'model_executed'
        write_json(manifest_path, manifest)
        csv_path = ATTEMPT / 'H1_S1_res.csv'
        if not csv_path.is_file() or csv_path.stat().st_size > 20*1024*1024:
            raise RuntimeError('Missing/oversized raw CSV result; no post hoc export repair')
        data = csv_path.read_bytes()
        manifest['csvSha256'] = hashlib.sha256(data).hexdigest()
        with csv_path.open(newline='', encoding='utf-8') as source:
            reader = csv.reader(source)
            header = next(reader)
            manifest['csvHeader'] = header
        # All 18 mandatory exports must be available as raw native columns.
        # We do NOT synthesize missing port flows, parameters or alias constants.
        bundle = json.loads((ATTEMPT / 'reference.bundle.json').read_text())
        missing = sorted(set(bundle['columns']) - set(header))
        manifest['missingRequiredExports'] = missing
        if missing:
            raise RuntimeError(f'Native CSV export schema incomplete: {missing}')
        from h1.study import load_study
        from h1.verification import candidate_receipt
        study = load_study(STUDY, ROOT / 'h1/cases')
        receipt = candidate_receipt(study, bundle, data.decode('utf-8'), evidence_kind='unattested_output')
        write_json(ATTEMPT / 'candidate.receipt.json', receipt)
        # 'check' returns diagnostic_only observations and nativeQualified=false;
        # real compilation alone does not upgrade those evidence labels.
        verdict = run_once([sys.executable, '-B', '-m', 'h1.verify', 'check',
                            '--study', str(STUDY), '--root', str(ROOT / 'h1/cases'),
                            '--bundle', str(ATTEMPT / 'reference.bundle.json'),
                            '--seal', manifest['referenceSeal'], '--csv', str(csv_path),
                            '--receipt', str(ATTEMPT / 'candidate.receipt.json')],
                           cwd=ROOT, timeout=90, log_name='verification')
        verification = json.loads(verdict.stdout.decode('utf-8'))
        write_json(ATTEMPT / 'verification.json', verification)
        if verification.get('status') != 'checks_passed' or verification.get('nativeQualified') is not False:
            raise RuntimeError('Candidate verification did not pass / unsafe status')
        manifest['status'] = 'smoke_checks_passed_not_native_qualified'
    except Exception as exc:
        manifest['error'] = repr(exc)
        manifest['status'] = 'stopped_' + manifest['status']
        raise
    finally:
        manifest['finalized'] = datetime.now(timezone.utc).isoformat()
        manifest['artifactSha256'] = {}
        for p in ATTEMPT.iterdir():
            if p.is_file() and p.name != 'attempt.json':
                try:
                    manifest['artifactSha256'][p.name] = sha(p)
                except OSError:
                    pass
        write_json(manifest_path, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('preflight', 'execute'))
    phase = parser.parse_args().phase
    try:
        (preflight if phase == 'preflight' else execute)()
        return 0
    except Exception:
        if ATTEMPT.exists():
            (ATTEMPT / 'uncaught_error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
