"""Fixed experiment-data preparation around the unchanged two-case batch runner.

No physics, new solver, tolerance fitting, or native retries. Every reference is
sealed before any new build. Numerical companions preserve original model bytes.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from h1.model import require
from h1.study import load_study, strict_json
from h1 import reference
from h1.verification import bind_reference
from tools import h1_native_batch as batch


def dump(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def create(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(dump(value))


def companion(study: dict, spec: dict, kind: str) -> tuple[dict, dict]:
    """Analysis-only successor. Physical composition/provenance/revision stay intact."""
    require(kind in ('tight', 'dense'), 'campaign', 'unknown companion')
    require(study['analysis']['tolerance'] == 1e-8 and study['analysis']['intervals'] == 1000,
            'campaign', 'unexpected primary settings')
    s, r = deepcopy(study), deepcopy(spec)
    s['id'] += '_'+kind.upper()
    if kind == 'tight':
        s['analysis']['tolerance'] = 1e-10
    else:
        s['analysis']['intervals'] = 2000
    r['id'], r['analysis'] = s['id'], deepcopy(s['analysis'])
    r['studySha256'] = hashlib.sha256(dump(s)).hexdigest()
    # Reference physical facts/topology stay separate and unchanged. This note
    # records the derivation of analysis settings, not a new source interpretation.
    r['provenance'] += ' Analysis-only '+kind+' companion; physical facts unchanged.'
    return s, r


def validate_config(root: Path, path: Path, pin: str) -> tuple[dict, dict]:
    require(path.is_file() and batch.sha(path) == pin, 'campaign', 'config identity mismatch')
    config = strict_json(path.read_text())
    require(set(config) == {'schema','branch','output','basePlan','basePlanSha256',
                           'extraPins','cases','groups','budget'}, 'campaign', 'config fields')
    require(config['schema'] == 'sim_heat.resolution_campaign/1', 'campaign', 'schema')
    base_path = batch.confined(root, config['basePlan'])
    base = batch.load_plan(root, base_path, config['basePlanSha256'])
    require(config['budget'] == {'builds':7,'launches':7,'versionQueries':4}, 'campaign', 'budget drift')
    require(isinstance(config['cases'], dict) and len(config['cases']) == 3,
            'campaign', 'three existing base cases required')
    pins = dict(base['pins']); pins.update(config['extraPins'])
    for name, digest in pins.items():
        p = batch.confined(root, name)
        require(p.is_file() and batch.sha(p) == digest, 'campaign', 'source drift: '+name)
    members = [item for group in config['groups'] for item in group]
    require(len(config['groups']) == 4 and all(1 <= len(g) <= 2 for g in config['groups'])
            and len(members) == 7 and len(set(members)) == 7, 'campaign', 'batch membership/budget')
    require(sum(item.endswith(':primary') for item in members) == 1,
            'campaign', 'only one new primary permitted')
    for label, case in config['cases'].items():
        require(set(case) == {'study','reference'}, 'campaign', 'case fields')
        for name in case.values():
            require(name in pins, 'campaign', 'unpinned case')
        s = load_study(root/case['study'], root/base['caseRoot'])
        r = reference.read_reference(root/case['reference']); bind_reference(s,r)
        require(s.data['mode'] == 'transient' and s.data['analysis']['intervals'] == 1000
                and s.data['analysis']['tolerance'] == 1e-8, 'campaign', 'base analysis drift')
        require(s.path.parent.joinpath(s.data['model']['path']).relative_to(root).as_posix() in pins,
                'campaign', 'unpinned model')
        require(label+':tight' in members and label+':dense' in members,
                'campaign', 'missing planned companion')
    for item in members:
        label,kind = item.split(':')
        require(label in config['cases'] and kind in ('primary','tight','dense'),
                'campaign', 'unsupported campaign entry')
    batch.confined(root, config['output'])
    return config, base


def generate(root: Path, config: dict, base: dict, pin: str) -> dict:
    out = batch.confined(root, config['output']); out.mkdir(exist_ok=False)
    inputs = dict(base['pins']); inputs.update(config['extraPins'])
    entries, derivations = {}, []
    for label, original in config['cases'].items():
        s = strict_json((root/original['study']).read_text())
        r = reference.read_reference(root/original['reference'])
        # Disposable, byte-identical copies keep generated experiments out of
        # the original fixture inventory; parent revision paths stay relative.
        case_dir = out/'inputs/cases'/Path(original['study']).parent.name
        case_dir.mkdir(parents=True,exist_ok=True)
        for name in ('study.json', s['model']['path']):
            src = (root/original['study']).parent/name
            dst = case_dir/name
            with dst.open('xb') as f: f.write(src.read_bytes())
            inputs[dst.relative_to(root).as_posix()] = batch.sha(dst)
        ref_path = out/'inputs/reference'/Path(original['reference']).name
        ref_path.parent.mkdir(parents=True,exist_ok=True)
        with ref_path.open('xb') as f: f.write((root/original['reference']).read_bytes())
        inputs[ref_path.relative_to(root).as_posix()] = batch.sha(ref_path)
        entries[label+':primary'] = {'study':(case_dir/'study.json').relative_to(root).as_posix(),
                                     'reference':ref_path.relative_to(root).as_posix()}
        for kind in ('tight','dense'):
            child, spec = companion(s,r,kind)
            sp = (case_dir/('study_resolution_'+kind+'.json')).relative_to(root)
            rp = ref_path.with_name(ref_path.stem+'_resolution_'+kind+'.json').relative_to(root)
            create(root/sp, child); create(root/rp,spec)
            loaded = load_study(root/sp, out/'inputs/cases'); bind_reference(loaded,spec)
            inputs[sp.as_posix()] = batch.sha(root/sp); inputs[rp.as_posix()] = batch.sha(root/rp)
            entries[label+':'+kind] = {'study':sp.as_posix(),'reference':rp.as_posix()}
            derivations.append({'baseStudy':original['study'],'baseStudySha256':inputs[original['study']],
                'baseReference':original['reference'],'modelSha256':loaded.model_sha256,
                'kind':kind,**entries[label+':'+kind], 'studySha256':loaded.sha256})
    state = {'schema':'sim_heat.resolution_attempt/1','configSha256':pin,'status':'generated',
             'nativeQualified':False,'budget':config['budget'],'batches':[], 'derivations':derivations,
             'createdAt':datetime.now(timezone.utc).isoformat()}
    for i, group in enumerate(config['groups'],1):
        plan = deepcopy(base)
        plan.update(branch=config['branch'], output=config['output']+'/batch_'+str(i),
                    caseRoot=config['output']+'/inputs/cases',
                    cases=[entries[k] for k in group], pins=inputs)
        path = out/('plan_'+str(i)+'.json');create(path,plan)
        digest = batch.sha(path);batch.load_plan(root,path,digest)
        state['batches'].append({'plan':path.relative_to(root).as_posix(),'sha256':digest,
                                 'members':group,'output':plan['output']})
    batch.save(out/'campaign.json',state)
    return state


def run(root: Path, config_path: Path, pin: str, phase: str) -> None:
    config, base = validate_config(root,config_path,pin)
    out = root/config['output']
    if phase == 'prepare':
        state = generate(root,config,base,pin)
    else:
        batch.check_host({**base,'branch':config['branch']})
        state = strict_json((out/'campaign.json').read_text())
        require(state['status'] == 'prepared' and state['configSha256'] == pin,
                'campaign', 'missing/consumed campaign preparation')
        require([b['members'] for b in state['batches']] == config['groups'], 'campaign', 'groups drift')
    state['status'] = 'preparing' if phase == 'prepare' else 'executing'
    batch.save(out/'campaign.json',state)
    try:
        for b in state['batches']:
            plan = batch.load_plan(root,root/b['plan'],b['sha256'])
            (batch.prepare if phase == 'prepare' else batch.execute)(root,plan,b['sha256'])
        state['status'] = 'prepared' if phase == 'prepare' else 'diagnostic_checks_passed_not_native_qualified'
    except Exception as exc:
        state['status'] = 'stopped';state['error'] = repr(exc)
        (out/'campaign_error.txt').write_text(traceback.format_exc())
        raise
    finally:
        counts = {'versionQueries':0,'buildModelCalls':0,'modelLaunches':0}
        for b in state['batches']:
            p = root/b['output']/'attempt.json'
            if p.is_file():
                for k,v in json.loads(p.read_text())['counts'].items(): counts[k] += v
        state['counts'] = counts
        state['updatedAt'] = datetime.now(timezone.utc).isoformat()
        batch.save(out/'campaign.json',state)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=('prepare','execute'));p.add_argument('--config',required=True)
    p.add_argument('--pin',required=True);a=p.parse_args()
    run(ROOT,batch.confined(ROOT,a.config),a.pin,a.phase)
