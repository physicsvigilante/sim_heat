"""Read original whole multi-batch H1 native campaign archive into viewer data.

Never runs OpenModelica, invents readings, changes H1 reference policy or
repacks the original GitHub artifact. Original model/study and all diagnostic
receipts must match; externally verified run/artifact/commit pins are required.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from h1 import reference as reference_check
from h1.decoder import decode_csv
from h1.model import internal_exports, require
from h1.study import load_study, strict_json
from h1.verification import candidate_receipt, check_candidate
from viewer.network.tools.build_case import owner_graph, pick_indices, sha, stable_json

SHA = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')


def compile_campaign_case(root: Path, study_rel: str, archive: Path,
                          artifact_sha: str, batch: int, slot: int,
                          artifact_id: int, title: str, *,
                          expected_run_id: int, expected_commit_sha: str,
                          expected_branch: str) -> dict:
    """Select one recorded batch/case; keep the original outer ZIP identity.

    The caller must independently verify the run, commit, artifact ID and ZIP
    SHA via trusted GitHub evidence. This function checks internal agreement,
    not external host attestation or independent measurement accuracy.
    """
    require(type(batch) is int and 1 <= batch <= 999 and type(slot) is int and 1 <= slot <= 2,
            'campaign_evidence', 'invalid original batch or case selector')
    require(type(artifact_id) is int and artifact_id > 0 and
            type(expected_run_id) is int and expected_run_id > 0 and
            isinstance(expected_commit_sha, str) and COMMIT.fullmatch(expected_commit_sha) and
            isinstance(expected_branch, str) and expected_branch.startswith('experiment/') and
            len(expected_branch) <= 128,
            'campaign_evidence', 'externally checked source identity required')
    require(archive.is_file() and isinstance(artifact_sha, str) and
            SHA.fullmatch(artifact_sha) and sha(archive.read_bytes()) == artifact_sha and
            zipfile.is_zipfile(archive), 'campaign_evidence', 'original full ZIP mismatch')
    study = load_study(root/study_rel, root/'h1/cases')
    require(study.request_report['admitted'] and study.data['mode'] == 'transient',
            'campaign_evidence', 'admitted transient source study required')
    prefix = f'batch_{batch}/'
    folder = f'case_{slot:02}'
    with zipfile.ZipFile(archive) as z:
        members = z.namelist()
        require(len(members) == len(set(members)) and len(members) < 4000 and
                all(not n.startswith('/') and '\\' not in n and
                    '..' not in PurePosixPath(n).parts for n in members),
                'campaign_evidence', 'unsafe or duplicate original ZIP members')
        require(z.testzip() is None, 'campaign_evidence', 'original ZIP CRC mismatch')
        require(prefix+'attempt.json' in members, 'campaign_evidence', 'selected native batch absent')

        def read(name: str) -> bytes:
            try:
                return z.read(prefix+name)
            except KeyError:
                require(False, 'campaign_evidence', 'missing original native member: '+name)

        campaign = strict_json(z.read('campaign.json').decode('utf-8'))
        require(campaign['schema'] == 'sim_heat.resolution_attempt/1' and
                campaign['status'] == 'diagnostic_checks_passed_not_native_qualified' and
                campaign['nativeQualified'] is False and
                1 <= batch <= len(campaign['batches']),
                'campaign_evidence', 'invalid original campaign record')
        batch_record = campaign['batches'][batch-1]
        require(batch_record['output'].endswith('/'+prefix[:-1]) and
                batch_record['plan'].endswith('/plan_'+str(batch)+'.json'),
                'campaign_evidence', 'wrong recorded batch path')
        plan_member = batch_record['plan'].split('/')[-1]
        plan_bytes = z.read(plan_member)
        require(sha(plan_bytes) == batch_record['sha256'],
                'campaign_evidence', 'original batch plan SHA mismatch')
        plan = strict_json(plan_bytes.decode('utf-8'))
        attempt = strict_json(read('attempt.json').decode('utf-8'))
        require(attempt['schema'] == 'sim_heat.native_batch_attempt/1' and
                attempt['status'] == 'diagnostic_checks_passed_not_native_qualified' and
                attempt['nativeQualified'] is False and
                attempt['planSha256'] == batch_record['sha256'] and
                attempt['github']['GITHUB_SHA'] == expected_commit_sha and
                int(attempt['github']['GITHUB_RUN_ID']) == expected_run_id and
                str(attempt['github']['GITHUB_RUN_ATTEMPT']) == '1',
                'campaign_evidence', 'incorrect recorded native identity/status')
        require(attempt['counts'] == {'versionQueries':1,'buildModelCalls':len(attempt['cases']),
                                     'modelLaunches':len(attempt['cases'])} and
                1 <= slot <= len(attempt['cases']),
                'campaign_evidence', 'unexpected native command counts')
        manifest = attempt['artifactSha256']
        require(isinstance(manifest, dict) and manifest and
                all(isinstance(name,str) and isinstance(digest,str) and SHA.fullmatch(digest)
                    for name,digest in manifest.items()),
                'campaign_evidence', 'invalid original archive manifest')
        native_files = {n[len(prefix):] for n in members if n.startswith(prefix)}
        require(native_files == set(manifest) | {'attempt.json'},
                'campaign_evidence', 'unlisted or absent original native member')
        for name,digest in manifest.items():
            require(sha(read(name)) == digest, 'campaign_evidence', 'native file SHA mismatch: '+name)

        item = attempt['cases'][slot-1]
        require(item['directory'] == folder and item['status'] == 'checks_passed' and
                item['model'] == study.model.name and item['canonicalSamples'] == len(study.grid),
                'campaign_evidence', 'selected native case/study mismatch')
        require(plan['cases'][slot-1]['study'] == item['study'] and
                plan['branch'] == expected_branch and
                item['study'].startswith(str(PurePosixPath(batch_record['output']).parent)+'/inputs/cases/') and
                item['study'].endswith('/study.json'),
                'campaign_evidence', 'recorded original study location mismatch')
        recorded_study = item['study'].removeprefix(str(PurePosixPath(batch_record['output']).parent)+'/')
        require(z.read(recorded_study) == study.path.read_bytes() and
                read(folder+'/study.json') == study.path.read_bytes() and
                read(folder+'/model.mo') == (study.path.parent/study.data['model']['path']).read_bytes(),
                'campaign_evidence', 'executed model/study differs from current admitted source')
        require(read(folder+'/build.returncode').strip() == b'0' and
                read(folder+'/simulation.returncode').strip() == b'0' and
                read('compiler_version.returncode').strip() == b'0' and
                read('offline_tests.returncode').strip() == b'0',
                'campaign_evidence', 'native execution/preflight return code failed')
        mat_digest = sha(read(folder+'/model_res.mat'))
        csv_bytes = read(folder+'/normalized.csv')
        csv_digest = sha(csv_bytes)
        require(mat_digest == item['rawMatSha256'],
                'campaign_evidence', 'native MAT identity mismatch')
        provenance = strict_json(read(folder+'/mat_provenance.json').decode('utf-8'))
        require(provenance['rawMatSha256'] == mat_digest and
                provenance['canonicalCsvSha256'] == csv_digest and
                provenance['samples'] == len(study.grid) and
                provenance['duplicateRowsCollapsed'] == 1 and
                provenance['nativeQualified'] is False,
                'campaign_evidence', 'native MAT/CSV provenance invalid')

        bundle_bytes = read(folder+'/reference.bundle.json')
        require(sha(bundle_bytes) == item['referenceFileSha256'],
                'campaign_evidence', 'checking reference hash mismatch')
        bundle = strict_json(bundle_bytes.decode('utf-8'))
        receipt = strict_json(read(folder+'/receipt.json').decode('utf-8'))
        verdict = strict_json(read(folder+'/verification.json').decode('utf-8'))
        require(bundle['seal'] == item['referenceSeal'] == receipt['referenceSeal'] ==
                verdict['referenceSeal'] and
                reference_check.fingerprint({k:v for k,v in bundle.items() if k!='seal'}) ==
                item['referenceSeal'], 'campaign_evidence', 'checking reference seals disagree')
        csv_text = csv_bytes.decode('utf-8')
        require(receipt == candidate_receipt(study,bundle,csv_text,'unattested_output'),
                'campaign_evidence', 'original native candidate receipt mismatch')
        checked = check_candidate(study,bundle,csv_text,receipt,item['referenceSeal'])
        require(checked == verdict and checked['status'] == 'checks_passed' and
                len(checked['checks']) == item['checkCount'] and
                all(c['passed'] is True for c in checked['checks']) and
                all(r['status'] == 'diagnostic_only' for r in checked['requests']),
                'campaign_evidence', 'original native checking report contradiction')
        decoded = decode_csv(csv_text,internal_exports(study.model),tuple(study.grid))
        require(decoded['duplicateRowsCollapsed'] == 1 and
                len(decoded['columns']['time']) == len(study.grid),
                'campaign_evidence', 'incorrect original physical time grid')

    nodes,edges = owner_graph(study)
    cols = decoded['columns']
    fields = ['time']+list(dict.fromkeys(
        [n['temperature'] for n in nodes] +
        [n['energy'] for n in nodes if 'energy' in n] +
        [n['power'] for n in nodes if 'power' in n] +
        [e['flow'] for e in edges]))
    require(all(n in cols for n in fields), 'campaign_evidence', 'missing native viewer observation')
    picks = pick_indices(cols,edges,len(study.grid)-1)
    return {
        'schema':'sim_heat.viewer.native_case/1','id':study.data['id'],
        'title':title,'modelName':study.model.name,
        'source':{'runId':expected_run_id,'artifactId':artifact_id,
                  'artifactSha256':artifact_sha,'modelSha256':study.model_sha256,
                  'studySha256':study.sha256,'compiledSourceCommit':expected_commit_sha,
                  'csvSha256':csv_digest,'rawMatSha256':mat_digest,
                  'archiveEntry':folder+'/normalized.csv',
                  'evidenceKind':'historical_native_diagnostic',
                  'nativeQualified':False,'verificationStatus':'checks_passed',
                  'publicRequestStatus':'diagnostic_only',
                  'checksPassed':item['checkCount'],'canonicalSamples':len(study.grid),
                  'duplicateRowsCollapsed':1},
        'analysis':{'start':study.grid[0],'stop':study.grid[-1],
                    'intervals':len(study.grid)-1},
        'graph':{'nodes':nodes,'edges':edges},'columns':fields,
        'samples':[[float(cols[name][i]) for name in fields] for i in picks]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--study',required=True)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--archive-sha',required=True)
    p.add_argument('--batch',type=int,required=True)
    p.add_argument('--case-slot',type=int,required=True)
    p.add_argument('--artifact-id',type=int,required=True)
    p.add_argument('--expected-run-id',type=int,required=True)
    p.add_argument('--expected-commit-sha',required=True)
    p.add_argument('--expected-branch',required=True)
    p.add_argument('--title',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=compile_campaign_case(a.root,a.study,a.archive,a.archive_sha,
                                 a.batch,a.case_slot,a.artifact_id,a.title,
                                 expected_run_id=a.expected_run_id,
                                 expected_commit_sha=a.expected_commit_sha,
                                 expected_branch=a.expected_branch)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes(stable_json(result))
    print(json.dumps({'case':result['id'],'sha256':sha(a.out.read_bytes()),
                      'samples':len(result['samples']),'path':str(a.out)}))

if __name__=='__main__': main()
