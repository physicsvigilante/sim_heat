"""Read-only archived S1-style steady MAT/CSV evidence -> versioned viewer bundle.

No OpenModelica launch, reference-based reconstruction, or case-specific physics.
Refuses incomplete/failed native attempts rather than treating algebraic indices as time.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from h1.decoder import decode_csv
from h1.model import internal_exports, require
from h1.study import load_study, strict_json
from viewer.network.tools.build_case import owner_graph, sha, stable_json


def compile_steady(root: Path, study_rel: str, archive: Path,
                   archive_sha: str, case_slot: int, artifact_id: int,
                   title: str) -> dict:
    require(archive.is_file() and len(archive_sha) == 64 and
            sha(archive.read_bytes()) == archive_sha, 'steady_evidence',
            'archived ZIP digest mismatch')
    study = load_study(root / study_rel, root / 'h1/cases')
    require(study.request_report['admitted'] and study.data['mode'] == 'steady',
            'steady_study', 'steady admitted study required')
    require(1 <= case_slot <= 2 and artifact_id > 0,
            'steady_evidence', 'invalid case/artifact slot')
    folder = f'case_{case_slot:02}'
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None, 'steady_evidence', 'ZIP CRC failure')
        attempt_paths = [name for name in z.namelist()
                         if name == 'attempt.json' or name.endswith('/attempt.json')]
        require(len(attempt_paths) == 1, 'steady_evidence', 'ambiguous native attempt')
        base = attempt_paths[0][:-len('attempt.json')]
        def read(name: str) -> bytes:
            return z.read(base + name)
        attempt = strict_json(read('attempt.json').decode('utf-8'))
        require(attempt['status'] == 'diagnostic_checks_passed_not_native_qualified' and
                attempt['nativeQualified'] is False,
                'steady_evidence', 'native attempt not a completed diagnostic')
        require(attempt['counts']['versionQueries'] == 1 and
                attempt['counts']['buildModelCalls'] == len(attempt['cases']) and
                attempt['counts']['modelLaunches'] == len(attempt['cases']) and
                attempt['github']['GITHUB_RUN_ATTEMPT'] == '1',
                'steady_evidence', 'native attempt budget/provenance mismatch')
        require(len(attempt['cases']) >= case_slot,
                'steady_evidence', 'case absent from attempt')
        # Validate every pinned original artifact entry, not only the selected columns.
        for name, digest in attempt['artifactSha256'].items():
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
                read(folder+'/simulation.returncode').strip() == b'0',
                'steady_evidence', 'native execution did not succeed')
        csv_bytes = read(folder+'/normalized.csv')
        csv_sha = sha(csv_bytes)
        require(csv_sha == attempt['artifactSha256'][folder+'/normalized.csv'],
                'steady_evidence', 'native CSV identity mismatch')
        raw_mat_sha = sha(read(folder+'/model_res.mat'))
        require(raw_mat_sha == item['rawMatSha256'] ==
                attempt['artifactSha256'][folder+'/model_res.mat'],
                'steady_evidence', 'native MAT identity mismatch')
        provenance = strict_json(read(folder+'/mat_provenance.json').decode('utf-8'))
        require(provenance['rawMatSha256'] == raw_mat_sha and
                provenance['canonicalCsvSha256'] == csv_sha and
                provenance['samples'] == 2 and
                provenance['duplicateRowsCollapsed'] == 1 and
                provenance['nativeQualified'] is False,
                'steady_evidence', 'MAT/CSV provenance mismatch')
        verdict = strict_json(read(folder+'/verification.json').decode('utf-8'))
        require(verdict['status'] == 'checks_passed' and
                verdict['nativeQualified'] is False and
                verdict['nativeExecuted'] is False and
                verdict['evidenceKind'] == 'unattested_output' and
                verdict['timeMeaning'] == 'algebraic_evaluation_index' and
                verdict['modelSha256'] == study.model_sha256 and
                verdict['studySha256'] == study.sha256 and
                verdict['csvSha256'] == csv_sha and
                len(verdict['checks']) == item['checkCount'] and
                all(x['status'] == 'diagnostic_only' for x in verdict['requests']),
                'steady_evidence', 'unverified/mislabeled diagnostic receipt')
        decoded = decode_csv(csv_bytes.decode('utf-8'),
                             internal_exports(study.model), (0.0, 1.0))
        cols = decoded['columns']
        require(decoded['duplicateRowsCollapsed'] == 1 and
                len(cols['time']) == 2 and
                tuple(cols['time']) == (0.0, 1.0),
                'steady_evidence', 'not two native algebraic evaluations')
        native_run = int(attempt['github']['GITHUB_RUN_ID'])
        native_commit = attempt['github']['GITHUB_SHA']

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
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    data = compile_steady(a.root, a.study, a.archive, a.archive_sha,
                          a.case_slot, a.artifact_id, a.title)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(stable_json(data))
    print(json.dumps({'case': data['id'], 'schema': data['schema'],
                      'sha256': sha(a.out.read_bytes()), 'path': str(a.out),
                      'nodes': len(data['graph']['nodes']),
                      'edges': len(data['graph']['edges'])}))


if __name__ == '__main__':
    main()
