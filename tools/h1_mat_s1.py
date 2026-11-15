"""Single native S1 MAT-v4 attempt; no retry and no native-acceptance label."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'h1_cloud_s1_attempt'
LIBRARY = ROOT / 'experiments/h1_spike/SimHeat.mo'
MODEL = ROOT / 'h1/cases/S1/model.mo'
STUDY = ROOT / 'h1/cases/S1/study.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def invoke(argv, label, timeout, cwd):
    save(OUT / (label + '.command.json'), {'argv': argv, 'cwd': str(cwd)})
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        (OUT / (label + '.stdout')).write_bytes(exc.stdout or b'')
        (OUT / (label + '.stderr')).write_bytes(exc.stderr or b'')
        raise RuntimeError(f'{label} timed out; no retry') from exc
    (OUT / (label + '.stdout')).write_bytes(p.stdout)
    (OUT / (label + '.stderr')).write_bytes(p.stderr)
    (OUT / (label + '.returncode')).write_text(str(p.returncode) + '\n')
    if p.returncode:
        raise RuntimeError(f'{label} exited {p.returncode}; no retry')
    return p


def execute():
    manifest_file = OUT / 'attempt.json'
    if not manifest_file.is_file():
        raise RuntimeError('Missing offline preflight evidence; no native execution')
    meta = json.loads(manifest_file.read_text())
    if meta.get('status') != 'preflight_passed':
        raise RuntimeError('Preflight did not pass')
    if os.environ.get('GITHUB_ACTIONS') != 'true' or \
            os.environ.get('GITHUB_REF') != 'refs/heads/experiment/h1-cloud-s1-matv4-once' or \
            os.environ.get('GITHUB_EVENT_NAME') != 'push' or \
            os.environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise RuntimeError('Unexpected execution host/ref/event/attempt')
    meta['status'] = 'native_running'
    meta['counts'] = {'explicitOmVersionQueries': 0, 'buildModel': 0, 'modelLaunches': 0}
    meta['adapterSha256'] = sha(ROOT / 'h1/matv4.py')
    meta['runnerSha256'] = sha(Path(__file__))
    save(manifest_file, meta)
    try:
        omc = shutil.which('omc')
        if not omc:
            raise RuntimeError('No OpenModelica executable')
        meta['omcPath'] = omc
        meta['omcSha256'] = sha(omc)
        meta['counts']['explicitOmVersionQueries'] = 1
        save(manifest_file, meta)
        p = invoke([omc, '--version'], 'omc-version', 30, OUT)
        version = p.stdout.decode('utf-8').strip()
        meta['omcVersion'] = version
        if version != 'OpenModelica 1.27.0':
            raise RuntimeError('Unexpected selected compiler version')
        def path_literal(p):
            return str(p.resolve()).replace('\\', '/').replace('"', '\\"')
        commands = '\n'.join([
            'loadModel(Modelica, {"4.0.0"});',
            'getVersion(Modelica);',
            f'loadFile("{path_literal(LIBRARY)}");',
            f'loadFile("{path_literal(MODEL)}");',
            'buildModel(H1_S1, startTime=0.0, stopTime=1.0, numberOfIntervals=1, '
            'tolerance=1e-8, method="dassl", fileNamePrefix="H1_S1", '
            'outputFormat="mat", variableFilter=".*");',
            'getErrorString();', '',
        ])
        (OUT/'build.mos').write_text(commands, encoding='utf-8')
        meta['counts']['buildModel'] = 1
        save(manifest_file, meta)
        p = invoke([omc, str(OUT/'build.mos')], 'build', 900, OUT)
        stdout = p.stdout.decode('utf-8', errors='replace') + p.stderr.decode('utf-8', errors='replace')
        exe = OUT / 'H1_S1'
        if 'Error:' in stdout or not exe.is_file() or not os.access(exe, os.X_OK):
            raise RuntimeError('Native build error or missing executable')
        if not (OUT / 'H1_S1_init.xml').is_file():
            raise RuntimeError('Native init XML missing')
        meta['executableSha256'] = sha(exe)
        meta['status'] = 'native_built'
        save(manifest_file, meta)
        meta['counts']['modelLaunches'] = 1
        save(manifest_file, meta)
        invoke([str(exe)], 'simulation', 120, OUT)
        meta['status'] = 'native_launched'
        save(manifest_file, meta)
        raw = OUT / 'H1_S1_res.mat'
        if not raw.is_file():
            raise RuntimeError('Native MAT result missing after successful launch')
        meta['rawMatSha256'] = sha(raw)
        from h1.matv4 import decode_mat_file
        from h1.model import internal_exports
        from h1.study import load_study
        from h1.verification import candidate_receipt
        study = load_study(STUDY, ROOT/'h1/cases')
        bundle = json.loads((OUT/'reference.bundle.json').read_text())
        expected_seal = (OUT/'reference.seal').read_text().strip()
        if bundle['seal'] != expected_seal or bundle['seal'] != meta['referenceSeal']:
            raise RuntimeError('Reference seal/manifest mismatch')
        exports = internal_exports(study.model)
        result = decode_mat_file(raw, exports, (0., 1.),
                                 maximum_shift=bundle['temporalPolicy']['maximumShift'])
        canonical = result.pop('canonicalCsv')
        decoded = result.pop('decoded')
        result['canonicalSamples'] = len(decoded['columns']['time'])
        result['duplicateRowsCollapsed'] = decoded['duplicateRowsCollapsed']
        result['nativeQualified'] = False
        csv_path = OUT/'H1_S1_normalized.csv'
        csv_path.write_bytes(canonical.encode('utf-8'))
        save(OUT/'H1_S1_mat_provenance.json', result)
        meta['normalizedCsvSha256'] = sha(csv_path)
        meta['matOutputCount'] = len(result['columnProvenance'])
        meta['status'] = 'mat_decoded_not_accepted'
        save(manifest_file, meta)
        receipt = candidate_receipt(study, bundle, canonical, evidence_kind='unattested_output')
        save(OUT/'candidate.receipt.json', receipt)
        p = invoke([sys.executable, '-B', '-m', 'h1.verify', 'check',
                    '--study', str(STUDY), '--root', str(ROOT/'h1/cases'),
                    '--bundle', str(OUT/'reference.bundle.json'), '--seal', expected_seal,
                    '--csv', str(csv_path), '--receipt', str(OUT/'candidate.receipt.json')],
                   'verification', 90, ROOT)
        verdict = json.loads(p.stdout.decode('utf-8'))
        save(OUT/'verification.json', verdict)
        if verdict.get('status') != 'checks_passed' or verdict.get('nativeQualified') is not False:
            raise RuntimeError('Numerical diagnostic checks incomplete/failed')
        meta['status'] = 'diagnostic_checks_passed_not_native_qualified'
    except Exception as exc:
        meta['error'] = repr(exc)
        meta['status'] = 'stopped_' + meta['status']
        raise
    finally:
        meta['finishedAt'] = datetime.now(timezone.utc).isoformat()
        meta['artifactSha256'] = {}
        for p in OUT.iterdir():
            if p.is_file() and p != manifest_file:
                meta['artifactSha256'][p.name] = sha(p)
        save(manifest_file, meta)


if __name__ == '__main__':
    try:
        execute()
    except Exception:
        if OUT.exists():
            (OUT / 'mat_attempt_error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
