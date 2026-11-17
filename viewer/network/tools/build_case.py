"""H2-02 read-only adapter: archived native H1 evidence -> generic viewer case.

This runs OFFLINE on original ZIP evidence, checks source input bytes and the
existing decode policy, and generates selection-only JSON. It does not solve
physics, verify native qualification, or repair missing observations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from h1.decoder import decode_csv
from h1.model import internal_exports, require
from h1.study import load_study, strict_json
from h1.verification import candidate_receipt, check_candidate
from h1 import reference as reference_check


def sha(bytes_: bytes) -> str:
    return hashlib.sha256(bytes_).hexdigest()


def stable_json(obj: object) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode('utf-8')


def owner_graph(study):
    model, top = study.model, study.topology
    node_names = {}
    nodes = []
    # Source component IDs are user authored. Reserve every one of them before
    # naming synthetic ideal junctions, including components encountered later.
    used_names = set(model.components)
    for i, ports in enumerate(top.nodes):
        owners = sorted(p.split('.')[0] for p in ports
                        if model.components[p.split('.')[0]].kind in ('Body','FixedTemperature'))
        require(len(owners) <= 1, 'viewer_topology', 'multiple node owners')
        if owners:
            name = owners[0]
            kind = 'body' if model.components[name].kind == 'Body' else 'boundary'
            temperature = name+'.T'
        else:
            base_name = 'junction_'+str(i)
            name = base_name
            suffix = 1
            while name in used_names:
                name = base_name+'_'+str(suffix)
                suffix += 1
            used_names.add(name)
            kind = 'junction'
            # No measured junction state: use the native temperature of a connected rod end.
            ends = sorted(p for p in ports if p.endswith(('.port_a','.port_b')))
            require(bool(ends), 'viewer_topology', 'junction lacks native endpoint')
            end = ends[0]
            rod, side = end.rsplit('.',1)
            temperature = rod + ('.T_a' if side == 'port_a' else '.T_b')
        node_names[i] = name
        item = {'id':name,'kind':kind,'temperature':temperature,'ports':list(ports)}
        if kind == 'body': item['energy'] = name+'.dU'
        if kind == 'boundary': item['power'] = name+'.Q_to_network'
        nodes.append(item)
    edges = [{'id':name, 'from':node_names[a], 'to':node_names[b], 'flow':name+'.Q_flow'}
             for name,a,b,_ in top.edges]
    return nodes,edges


def pick_indices(cols: dict, edges: list, intervals: int, max_regular=20) -> list[int]:
    indices=set(range(0,intervals+1,max(1,math.ceil(intervals/max_regular))))
    indices.add(intervals)
    for edge in edges:
        q=cols[edge['flow']]
        for i in range(1,len(q)):
            if (q[i-1]<0 and q[i]>=0) or (q[i-1]>0 and q[i]<=0):
                indices.update((i-1,i))
    return sorted(indices)


def archive_reader(z: zipfile.ZipFile):
    """Read original native bytes from root or a single CI-artifact subtree.

    The caller must separately pin the original *whole* ZIP; no repacking,
    invented root metadata or altered member bytes is permitted.
    """
    members=z.namelist()
    sizes=[entry.file_size for entry in z.infolist()]
    require(sizes and len(members)<=4096 and max(sizes)<=128*1024*1024
            and sum(sizes)<=512*1024*1024,
            'viewer_evidence','archive expansion exceeds bounded inspection')
    require(all(n and not n.startswith('/') and '\\' not in n
                and '..' not in PurePosixPath(n).parts for n in members),
            'viewer_evidence','unsafe ZIP member path')
    require(len(members)==len(set(members)),'viewer_evidence','duplicate ZIP member')
    attempt_paths=[n for n in members if n=='attempt.json' or n.endswith('/attempt.json')]
    require(len(attempt_paths)==1,'viewer_evidence','missing/ambiguous native attempt')
    prefix=attempt_paths[0][:-len('attempt.json')]
    require(not prefix.startswith('/') and '..' not in prefix.split('/') and
            '\\' not in prefix,'viewer_evidence','unsafe attempt directory')
    def original(name: str) -> bytes:
        try:
            return z.read(prefix+name)
        except KeyError:
            require(False,'viewer_evidence','missing original native member: '+name)
    original.member_names={n[len(prefix):] for n in members if n.startswith(prefix)}
    return original


def verify_recorded_case(root, original, study, folder, attempt, item):
    """Replay saved analytical checks, never regenerate a reference or run OMC.

    This verifies internal consistency with the caller-pinned original ZIP.
    It cannot authenticate an arbitrary repacked ZIP or a human owner. The
    expected ZIP SHA must come from independently checked original evidence.
    """
    manifest=attempt.get('artifactSha256')
    require(type(manifest) is dict and manifest and all(
            type(n) is str and type(d) is str and re.fullmatch('[0-9a-f]{64}',d)
            for n,d in manifest.items()), 'viewer_evidence','invalid full SHA manifest')
    require(original.member_names==set(manifest)|{'attempt.json'},
            'viewer_evidence','archive members differ from full manifest')
    for name,digest in manifest.items():
        require(sha(original(name))==digest,'viewer_evidence','archived member drift: '+name)
    counts=attempt.get('counts',{})
    required={'versionQueries':1,'buildModelCalls':len(attempt['cases']),
              'modelLaunches':len(attempt['cases'])}
    require(stable_json(counts)==stable_json(required),
            'viewer_evidence','native command counts must be exact integers')
    require(attempt.get('schema')=='sim_heat.native_batch_attempt/1'
            and attempt['github'].get('GITHUB_RUN_ATTEMPT')=='1',
            'viewer_evidence','invalid original attempt identity/schema')
    for name in ('compiler_version.returncode','offline_tests.returncode'):
        require(original(name).strip()==b'0','viewer_evidence','original preflight failed')
    require(original(folder+'/SimHeat.mo')==
            (root/'experiments/h1_spike/SimHeat.mo').read_bytes(),
            'viewer_evidence','archived physical library differs from supported source')
    raw=original(folder+'/reference.bundle.json')
    require(sha(raw)==item['referenceFileSha256'],
            'viewer_evidence','saved checking-reference file hash differs')
    bundle=strict_json(raw.decode('utf-8'))
    receipt=strict_json(original(folder+'/receipt.json').decode('utf-8'))
    verdict=strict_json(original(folder+'/verification.json').decode('utf-8'))
    require(bundle['seal']==item['referenceSeal']==receipt['referenceSeal']==verdict['referenceSeal']
            and reference_check.fingerprint({k:v for k,v in bundle.items() if k!='seal'})
            ==item['referenceSeal'],'viewer_evidence','saved reference seals disagree')
    csv=original(folder+'/normalized.csv')
    text=csv.decode('utf-8')
    require(stable_json(receipt)==stable_json(candidate_receipt(study,bundle,text,'unattested_output')),
            'viewer_evidence','candidate receipt differs from saved source/data')
    checked=check_candidate(study,bundle,text,receipt,item['referenceSeal'])
    require(stable_json(checked)==stable_json(verdict)
            and checked['status']=='checks_passed'
            and checked['nativeQualified'] is False
            and all(c['passed'] is True for c in checked['checks'])
            and all(r['status']=='diagnostic_only' for r in checked['requests'])
            and type(item['checkCount']) is int
            and len(checked['checks'])==item['checkCount']
            and max(c['maximumRatio'] for c in checked['checks'])==item['maxRatio'],
            'viewer_evidence','published diagnostic report contradicts saved H1 checker')
    provenance=strict_json(original(folder+'/mat_provenance.json').decode('utf-8'))
    require(provenance['rawMatSha256']==sha(original(folder+'/model_res.mat'))
            and provenance['canonicalCsvSha256']==sha(csv)
            and type(provenance['samples']) is int
            and provenance['samples']==len(study.grid)
            and type(provenance['duplicateRowsCollapsed']) is int
            and provenance['duplicateRowsCollapsed']==1
            and provenance['nativeQualified'] is False,
            'viewer_evidence','archived MAT/CSV provenance contradicts source grid')


def compile_case(root:Path, study_rel:str, archive:Path, expected_artifact_sha:str,
                 archive_case:int, artifact_id:int, display_title:str, *,
                 expected_run_id:int, expected_commit_sha:str) -> dict:
    require(archive.is_file() and archive.stat().st_size<=64*1024*1024
            and sha(archive.read_bytes())==expected_artifact_sha,
            'viewer_evidence','archived ZIP digest mismatch')
    require(type(expected_run_id) is int and expected_run_id>0
            and type(artifact_id) is int and artifact_id>0
            and type(expected_commit_sha) is str
            and re.fullmatch('[0-9a-f]{40}',expected_commit_sha),
            'viewer_evidence','externally checked run/commit/artifact identity required')
    study=load_study(root/study_rel,root/'h1/cases')
    require(study.request_report['admitted'] and study.data['mode']=='transient',
            'viewer_study','admitted transient study required')
    require(type(archive_case) is int and 1<=archive_case<=2,
            'viewer_evidence','invalid archive slot')
    folder=f'case_{archive_case:02}'
    with zipfile.ZipFile(archive) as z:
        original=archive_reader(z) # bounds before decompressing to check CRC
        require(z.testzip() is None,'viewer_evidence','archive CRC failed')
        attempt=strict_json(original('attempt.json').decode('utf-8'))
        require(attempt['status']=='diagnostic_checks_passed_not_native_qualified',
                'viewer_evidence','native attempt not successful diagnostic')
        require(attempt.get('nativeQualified') is False,'viewer_evidence','nativeQualified cannot be true')
        require(str(attempt['github']['GITHUB_RUN_ID'])==str(expected_run_id)
                and attempt['github']['GITHUB_SHA']==expected_commit_sha,
                'viewer_evidence','archive identity differs from externally checked run/commit')
        require(len(attempt['cases'])>=archive_case,'viewer_evidence','missing selected case')
        item=attempt['cases'][archive_case-1]
        require(item['directory']==folder and item['study']==study_rel and
                item['model']==study.model.name and item['status']=='checks_passed'
                and type(item.get('canonicalSamples')) is int,
                'viewer_evidence','case/study mismatch')
        require(original(folder+'/model.mo')==(study.path.parent/study.data['model']['path']).read_bytes(),
                'viewer_evidence','native compiled model bytes differ')
        require(original(folder+'/study.json')==study.path.read_bytes(),
                'viewer_evidence','native study bytes differ')
        verify_recorded_case(root,original,study,folder,attempt,item)
        csvbytes=original(folder+'/normalized.csv')
        csv_sha=sha(csvbytes)
        require(attempt['artifactSha256'][folder+'/normalized.csv']==csv_sha,
                'viewer_evidence','archived manifest CSV mismatch')
        verdict=strict_json(original(folder+'/verification.json').decode('utf-8'))
        require(verdict['status']=='checks_passed' and verdict['nativeQualified'] is False and
                verdict['csvSha256']==csv_sha and verdict['studySha256']==study.sha256 and
                verdict['modelSha256']==study.model_sha256 and
                len(verdict['checks'])==item['checkCount'] and
                all(x['status']=='diagnostic_only' for x in verdict['requests']),
                'viewer_evidence','invalid native candidate checking record')
        require(original(folder+'/build.returncode').strip()==b'0' and
                original(folder+'/simulation.returncode').strip()==b'0',
                'viewer_evidence','native build/launch did not exit successfully')
        rawmat=sha(original(folder+'/model_res.mat'))
        require(rawmat==item['rawMatSha256'] and
                rawmat==attempt['artifactSha256'][folder+'/model_res.mat'],
                'viewer_evidence','raw native MAT drift')
        decoded=decode_csv(csvbytes.decode('utf-8'),internal_exports(study.model),tuple(study.grid))
        require(decoded['duplicateRowsCollapsed']==1 and
                len(decoded['columns']['time'])==len(study.grid)==item['canonicalSamples'],
                'viewer_evidence','native canonical grid mismatch')
        native_run=int(attempt['github']['GITHUB_RUN_ID'])
        native_commit=attempt['github']['GITHUB_SHA']
    nodes,edges=owner_graph(study)
    cols=decoded['columns']
    names=['time']+list(dict.fromkeys(
        [n['temperature'] for n in nodes]+
        [n['energy'] for n in nodes if 'energy' in n]+
        [n['power'] for n in nodes if 'power' in n]+
        [e['flow'] for e in edges]
    ))
    require(all(k in cols for k in names),'viewer_evidence','missing native viewer channel')
    indices=pick_indices(cols,edges,len(study.grid)-1)
    rows=[[cols[k][i] for k in names] for i in indices]
    graph={'nodes':nodes,'edges':edges}
    return {'schema':'sim_heat.viewer.native_case/1','id':study.data['id'],
            'title':display_title,'modelName':study.model.name,
            'source':{'runId':native_run,'artifactId':artifact_id,'artifactSha256':expected_artifact_sha,
                'modelSha256':study.model_sha256,'studySha256':study.sha256,
                'compiledSourceCommit':native_commit,'csvSha256':csv_sha,'rawMatSha256':rawmat,
                'archiveEntry':folder+'/normalized.csv',
                'evidenceKind':'historical_native_diagnostic','nativeQualified':False,
                'verificationStatus':'checks_passed','publicRequestStatus':'diagnostic_only',
                'checksPassed':item['checkCount'],'canonicalSamples':item['canonicalSamples'],
                'duplicateRowsCollapsed':decoded['duplicateRowsCollapsed']},
            'analysis':{'start':float(study.grid[0]),'stop':float(study.grid[-1]),
                        'intervals':len(study.grid)-1},'graph':graph,
            'columns':names,'samples':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--study',required=True)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--archive-sha',required=True)
    p.add_argument('--case-slot',type=int,required=True)
    p.add_argument('--artifact-id',type=int,required=True)
    p.add_argument('--expected-run-id',type=int,required=True)
    p.add_argument('--expected-commit-sha',required=True)
    p.add_argument('--title',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    item=compile_case(a.root,a.study,a.archive,a.archive_sha,a.case_slot,a.artifact_id,a.title,
                      expected_run_id=a.expected_run_id,expected_commit_sha=a.expected_commit_sha)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes(stable_json(item))
    print(json.dumps({'case':item['id'],'samples':len(item['samples']),
                      'nodes':len(item['graph']['nodes']),'edges':len(item['graph']['edges']),
                      'sha256':sha(a.out.read_bytes()),'path':str(a.out)}))

if __name__=='__main__': main()
