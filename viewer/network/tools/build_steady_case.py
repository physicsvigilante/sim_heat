"""Read-only archived steady MAT/CSV evidence -> versioned viewer bundle.

A source-relative ZIP digest alone cannot authenticate a simulation. Verify the
complete archived attempt, presealed reference and the original H1 numerical
checker receipt. Do not recompute native physics in the viewer, run OMC, or
repair missing observations from reference values.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from h1.decoder import decode_csv
from h1.model import internal_exports, require
from h1.study import load_study, strict_json
from h1.verification import candidate_receipt, check_candidate
from h1 import reference as reference_check
from viewer.network.tools.build_case import owner_graph, sha, stable_json


# These files are produced by the existing unchanged generic runner for every
# successfully executed case. Other member files vary by solver/compiler; all
# those extras must still be listed and hashed by the attempt manifest.
MANDATORY_ROOT = frozenset((
    'compiler_version.stdout', 'compiler_version.returncode',
    'offline_tests.returncode',
))
MANDATORY_CASE = frozenset((
    'model.mo', 'study.json', 'SimHeat.mo', 'reference.bundle.json',
    'receipt.json', 'verification.json', 'admission.json',
    'mat_provenance.json', 'normalized.csv', 'model_res.mat',
    'build.mos', 'build.returncode', 'simulation.returncode',
    'model_init.xml',
))
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
COMMIT_SHA = re.compile(r'[0-9a-f]{40}\Z')


def compile_steady(root: Path, study_rel: str, archive: Path,
                   archive_sha: str, case_slot: int, artifact_id: int,
                   title: str, *, expected_run_id: int,
                   expected_commit_sha: str) -> dict:
    """Require caller's independently checked GitHub identity as separate input.

    This does not itself contact or authenticate GitHub. A trusted person or
    process must verify the run, artifact and commit outside the archive.
    """
    require(archive.is_file() and isinstance(archive_sha, str) and
            SHA256.fullmatch(archive_sha) is not None and
            sha(archive.read_bytes()) == archive_sha, 'steady_evidence',
            'archived ZIP digest mismatch')
    require(type(expected_run_id) is int and expected_run_id > 0 and
            isinstance(expected_commit_sha, str) and
            COMMIT_SHA.fullmatch(expected_commit_sha) is not None and
            type(artifact_id) is int and artifact_id > 0,
            'steady_evidence', 'externally checked native run/commit/artifact identity required')
    study = load_study(root / study_rel, root / 'h1/cases')
    require(study.request_report['admitted'] and study.data['mode'] == 'steady',
            'steady_study', 'steady admitted study required')
    require(type(case_slot) is int and 1 <= case_slot <= 2, 'steady_evidence', 'invalid case slot')
    require(zipfile.is_zipfile(archive), 'steady_evidence', 'invalid ZIP archive')
    folder = f'case_{case_slot:02}'
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        require(len(names) == len(set(names)) and all(
                name and not name.startswith('/') and '\\' not in name and
                '..' not in PurePosixPath(name).parts for name in names),
                'steady_evidence', 'duplicate/unsafe ZIP member')
        require(z.testzip() is None, 'steady_evidence', 'ZIP CRC failure')
        attempt_paths = [name for name in names
                         if name == 'attempt.json' or name.endswith('/attempt.json')]
        require(len(attempt_paths) == 1, 'steady_evidence', 'ambiguous native attempt')
        base = attempt_paths[0][:-len('attempt.json')]

        def read(name: str) -> bytes:
            try:
                return z.read(base + name)
            except KeyError:
                require(False, 'steady_evidence', 'missing native archive member: ' + name)

        attempt = strict_json(read('attempt.json').decode('utf-8'))
        require(attempt['status'] == 'diagnostic_checks_passed_not_native_qualified' and
                attempt['nativeQualified'] is False,
                'steady_evidence', 'native attempt not a completed diagnostic')
        require(all(type(attempt['counts'].get(k)) is int for k in
                    ('versionQueries','buildModelCalls','modelLaunches')) and
                attempt['counts']['versionQueries'] == 1 and
                attempt['counts']['buildModelCalls'] == len(attempt['cases']) and
                attempt['counts']['modelLaunches'] == len(attempt['cases']) and
                attempt['github']['GITHUB_RUN_ATTEMPT'] == '1',
                'steady_evidence', 'native attempt budget/provenance mismatch')
        require(str(attempt['github']['GITHUB_RUN_ID']) == str(expected_run_id) and
                attempt['github']['GITHUB_SHA'] == expected_commit_sha,
                'steady_evidence', 'archive run/commit differs from externally checked identity')
        require(len(attempt['cases']) >= case_slot,
                'steady_evidence', 'case absent from attempt')

        # Validate the full original file manifest. A repinned manifest cannot
        # silently omit a file that remains in the ZIP, nor a mandatory file.
        manifest = attempt['artifactSha256']
        require(isinstance(manifest, dict) and manifest and all(
                isinstance(name, str) and isinstance(digest, str) and
                SHA256.fullmatch(digest) is not None for name, digest in manifest.items()),
                'steady_evidence', 'invalid native archive SHA manifest')
        actual_members = {name[len(base):] for name in names if name.startswith(base)}
        require(actual_members == set(manifest) | {'attempt.json'},
                'steady_evidence', 'native archive file list differs from full SHA manifest')
        mandatory = MANDATORY_ROOT | {folder + '/' + name for name in MANDATORY_CASE}
        require(mandatory <= set(manifest),
                'steady_evidence', 'mandatory native archive member absent from manifest')
        for name, digest in manifest.items():
            require(sha(read(name)) == digest, 'steady_evidence',
                    'native archived file drift: ' + name)

        item = attempt['cases'][case_slot - 1]
        require(item['directory'] == folder and item['study'] == study_rel and
                item['model'] == study.model.name and item['status'] == 'checks_passed' and
                item['canonicalSamples'] == 2,
                'steady_evidence', 'model/study/case mismatch')
        require(read(folder+'/model.mo') ==
                (study.path.parent / study.data['model']['path']).read_bytes() and
                read(folder+'/study.json') == study.path.read_bytes(),
                'steady_evidence', 'native executed source bytes differ')
        require(read(folder+'/build.returncode').strip() == b'0' and
                read(folder+'/simulation.returncode').strip() == b'0' and
                read('compiler_version.returncode').strip() == b'0' and
                read('offline_tests.returncode').strip() == b'0',
                'steady_evidence', 'native build/launch/preflight did not succeed')
        csv_bytes = read(folder+'/normalized.csv')
        csv_sha = sha(csv_bytes)
        raw_mat_sha = sha(read(folder+'/model_res.mat'))
        require(raw_mat_sha == item['rawMatSha256'],
                'steady_evidence', 'native MAT identity mismatch')
        provenance = strict_json(read(folder+'/mat_provenance.json').decode('utf-8'))
        require(provenance['rawMatSha256'] == raw_mat_sha and
                provenance['canonicalCsvSha256'] == csv_sha and
                provenance['samples'] == 2 and
                provenance['duplicateRowsCollapsed'] == 1 and
                provenance['nativeQualified'] is False,
                'steady_evidence', 'MAT/CSV provenance mismatch')

        # Historical reference sealed before the native build, never a source
        # of replacement native values.
        reference_bytes = read(folder+'/reference.bundle.json')
        require(sha(reference_bytes) == item['referenceFileSha256'],
                'steady_evidence', 'reference bundle bytes differ from prepared reference')
        bundle = strict_json(reference_bytes.decode('utf-8'))
        receipt = strict_json(read(folder+'/receipt.json').decode('utf-8'))
        verdict = strict_json(read(folder+'/verification.json').decode('utf-8'))
        require(bundle['seal'] == item['referenceSeal'] ==
                receipt['referenceSeal'] == verdict['referenceSeal'] and
                reference_check.fingerprint({k: v for k, v in bundle.items()
                                             if k != 'seal'}) == item['referenceSeal'],
                'steady_evidence', 'mismatched/unsealed checking reference')
        csv_text = csv_bytes.decode('utf-8')
        require(stable_json(receipt) == stable_json(candidate_receipt(study, bundle, csv_text, 'unattested_output')),
                'steady_evidence', 'candidate receipt does not bind original native data')

        # Verify ALL saved numerical checks and public observations against the
        # unchanged H1 checker, not supplied status/count labels alone.
        verified = check_candidate(study, bundle, csv_text, receipt, item['referenceSeal'])
        require(stable_json(verified) == stable_json(verdict) and verified['status'] == 'checks_passed' and
                verified['nativeQualified'] is False and
                type(item['checkCount']) is int and
                len(verified['checks']) == item['checkCount'] and
                all(c['passed'] is True for c in verified['checks']) and
                all(r['status'] == 'diagnostic_only' for r in verified['requests']) and
                max(c['maximumRatio'] for c in verified['checks']) == item['maxRatio'],
                'steady_evidence', 'published diagnostic receipt contradicts H1 checker')
        decoded = decode_csv(csv_text, internal_exports(study.model), (0.0, 1.0))
        cols = decoded['columns']
        require(decoded['duplicateRowsCollapsed'] == 1 and
                len(cols['time']) == 2 and
                tuple(cols['time']) == (0.0, 1.0),
                'steady_evidence', 'not two native algebraic evaluations')
        native_run = expected_run_id
        native_commit = expected_commit_sha

    nodes, edges = owner_graph(study)
    require(all(node['kind'] != 'body' for node in nodes),
            'steady_evidence', 'steady body storage is not supported')
    names = list(dict.fromkeys(
        [n['temperature'] for n in nodes] +
        [n['power'] for n in nodes if 'power' in n] +
        [e['flow'] for e in edges]))
    require(all(name in cols for name in names),
            'steady_evidence', 'missing native steady observation')
    values = [float(cols[name][1]) for name in names]  # saved evaluation index 1, never time
    return {
        'schema': 'sim_heat.viewer.steady_case/1',
        'mode': 'steady', 'id': study.data['id'], 'title': title,
        'modelName': study.model.name,
        'source': {
            'runId': native_run, 'artifactId': artifact_id,
            'artifactSha256': archive_sha,
            'modelSha256': study.model_sha256,
            'studySha256': study.sha256,
            'compiledSourceCommit': native_commit,
            'csvSha256': csv_sha, 'rawMatSha256': raw_mat_sha,
            'archiveEntry': folder+'/normalized.csv',
            'evidenceKind': 'historical_native_diagnostic',
            'nativeQualified': False, 'verificationStatus': 'checks_passed',
            'publicRequestStatus': 'diagnostic_only',
            'checksPassed': item['checkCount'],
            'algebraicEvaluations': 2,
            'selectedEvaluationIndex': 1,
            'evaluationMeaning': 'algebraic_evaluation_index',
            'duplicateRowsCollapsed': decoded['duplicateRowsCollapsed']
        },
        'graph': {'nodes': nodes, 'edges': edges},
        'columns': names, 'values': values
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--study', required=True)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--archive-sha', required=True)
    p.add_argument('--case-slot', type=int, required=True)
    p.add_argument('--artifact-id', type=int, required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--expected-run-id', type=int, required=True,
                   help='Run ID independently checked on GitHub, not inferred from ZIP')
    p.add_argument('--expected-commit-sha', required=True,
                   help='Executed commit independently checked on GitHub, not inferred from ZIP')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    data = compile_steady(a.root, a.study, a.archive, a.archive_sha,
                          a.case_slot, a.artifact_id, a.title,
                          expected_run_id=a.expected_run_id,
                          expected_commit_sha=a.expected_commit_sha)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(stable_json(data))
    print(json.dumps({'case': data['id'], 'schema': data['schema'],
                      'sha256': sha(a.out.read_bytes()), 'path': str(a.out),
                      'nodes': len(data['graph']['nodes']),
                      'edges': len(data['graph']['edges'])}))


if __name__ == '__main__':
    main()
