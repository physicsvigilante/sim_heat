"""Offline regression replay of six published diagnostic fixtures, not a runner.

Downloads are a separate caller/CI operation. Original artifact identities below
are checked against the tracked catalog bundles and full ZIP hashes. This script
never calls a compiler, prepares a reference, or changes the tracked preview data.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from viewer.network.tools.build_case import compile_case,sha,stable_json
from viewer.network.tools.build_steady_case import compile_steady
from viewer.network.tools.build_campaign_case import compile_campaign_case

# Reproduction inventory of existing fixtures, NOT apparatus-specific engine logic.
CASES=(('D1',14152886226,1),('D2',14152886226,2),
       ('DEV_BRIDGE',14155084346,1),('TEACH_RING4',14215520616,1),
       ('S1',14204656273,1),('D2_K2',14153251022,1))

def replay(archives:Path):
    results=[]
    for name,artifact,slot in CASES:
        original=(ROOT/'viewer/network/data'/f'{name}.json').read_bytes()
        saved=json.loads(original);source=saved['source']
        archive=archives/f'artifact-{artifact}.zip'
        if source['artifactId']!=artifact or sha(archive.read_bytes())!=source['artifactSha256']:
            raise ValueError('Original full ZIP identity differs: '+name)
        args=(ROOT,f'h1/cases/{name}/study.json',archive,source['artifactSha256'])
        identity={'expected_run_id':source['runId'],
                  'expected_commit_sha':source['compiledSourceCommit']}
        if name=='S1':
            report=compile_steady(*args,slot,artifact,saved['title'],**identity)
        elif name=='D2_K2':
            report=compile_campaign_case(*args,1,slot,artifact,saved['title'],**identity,
                expected_branch='experiment/h1-cloud-resolution-once')
        else:
            report=compile_case(*args,slot,artifact,saved['title'],**identity)
        actual=stable_json(report)
        if actual!=original:
            raise ValueError('Published diagnostic preview changed: '+name)
        results.append({'case':name,'status':'BYTE_IDENTICAL','artifactId':artifact,
                        'originalZipSha256':source['artifactSha256'],
                        'previewSha256':sha(actual),'nativeExecutedByReplay':False})
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archives',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(replay(args.archives),indent=2))
