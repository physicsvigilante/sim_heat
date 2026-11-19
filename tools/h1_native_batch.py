"""Pinned, bounded cloud batch adapter; study data selects models, not code paths.

No physics equations, reference-based export repair, automatic retries, or native
qualification verdict. Prepare seals every case before the first native build.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from h1 import reference
from h1.matv4 import decode_mat_file
from h1.model import internal_exports, require
from h1.study import load_study, report, strict_json
from h1.verification import bind_reference, candidate_receipt, check_candidate


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def confined(root: Path, name: str) -> Path:
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name,
            'plan', 'portable repository-relative path required')
    p = root / name
    require(not Path(name).is_absolute() and p.resolve().is_relative_to(root.resolve()) and
            not any(x.is_symlink() for x in (p, *p.parents)), 'plan', 'path escape/symlink')
    return p


def load_plan(root: Path, path: Path, pin: str) -> dict:
    require(path.is_file() and path.stat().st_size <= 65536,
            'plan', 'plan missing or oversized')
    # Hash and parse one immutable snapshot; never authenticate one read and
    # parse another. This only validates bytes, not native execution authority.
    raw = path.read_bytes()
    require(len(raw) <= 65536 and hashlib.sha256(raw).hexdigest() == pin,
            'plan', 'plan identity mismatch')
    plan = strict_json(raw.decode('utf-8'))
    require(set(plan) == {'schema','branch','caseRoot','library','output','compilerVersion',
                         'mslVersion','dependencies','pins','cases'}, 'plan', 'unexpected plan fields')
    require(plan['schema'] == 'sim_heat.native_batch/1' and plan['compilerVersion'] == 'OpenModelica 1.27.0'
            and plan['mslVersion'] == '4.0.0', 'plan', 'unsupported toolchain')
    require(isinstance(plan['cases'], list) and 1 <= len(plan['cases']) <= 2,
            'plan', 'only the bounded case list is executable')
    for slot in ('library','caseRoot','output'):
        confined(root, plan[slot])
    required_pins = {plan['library']}
    seen = set()
    for case in plan['cases']:
        require(isinstance(case, dict) and set(case) == {'study','reference'}, 'plan', 'case fields')
        for value in case.values():
            confined(root, value); required_pins.add(value)
        require(case['study'] not in seen, 'plan', 'duplicate case')
        seen.add(case['study'])
    require(isinstance(plan['pins'], dict) and required_pins <= set(plan['pins']),
            'plan', 'incomplete input pins')
    for name, digest in plan['pins'].items():
        p = confined(root, name)
        require(p.is_file() and sha(p) == digest, 'identity', 'source drift: '+name)
    return plan


def check_host(plan: dict) -> None:
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and
            os.environ.get('GITHUB_REF') == 'refs/heads/'+plan['branch'] and
            os.environ.get('GITHUB_EVENT_NAME') == 'push' and
            os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'host', 'unexpected host/ref/event/attempt')
    require(platform.python_version() == plan['dependencies']['python'], 'host', 'Python version drift')
    for package in ('numpy','scipy'):
        require(importlib.metadata.version(package) == plan['dependencies'][package], 'host', 'dependency drift')


def invoke(argv: list[str], cwd: Path, folder: Path, name: str, seconds: int, *, native=False) -> None:
    """One invocation, file-backed logs, process-group timeout; no shell or retry."""
    save(folder/(name+'.command.json'), {'argv':argv,'cwd':str(cwd),'timeoutSeconds':seconds})
    env = os.environ.copy()
    if native:
        # No GitHub credentials are passed into compiler/model subprocesses.
        env = {k:v for k,v in env.items() if k in {
            'PATH','HOME','LANG','LC_ALL','LD_LIBRARY_PATH','OPENMODELICAHOME','MODELICAPATH','TMPDIR'}}
    with (folder/(name+'.stdout')).open('wb') as out, (folder/(name+'.stderr')).open('wb') as err:
        proc = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err, env=env, start_new_session=True)
        try:
            code = proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            (folder/(name+'.timeout')).write_text(str(seconds)+'\n')
            raise RuntimeError(name+' timed out; no retry')
    (folder/(name+'.returncode')).write_text(str(code)+'\n')
    require(code == 0, 'execution', name+f' failed ({code}); no retry')


def settings(study) -> dict:
    if study.data['mode'] == 'steady':
        return {'startTime':0,'stopTime':1,'intervals':1,'solver':'dassl','tolerance':1e-8}
    return dict(study.data['analysis'])


def build_script(study, library: Path, model: Path) -> str:
    def quote(p):
        return json.dumps(str(p.resolve()).replace('\\','/'))
    a = settings(study)
    return '\n'.join([
        'if not loadModel(Modelica, {"4.0.0"}) then print(getErrorString()); exit(1); end if;',
        'if getVersion(Modelica) <> "4.0.0" then print("MSL_VERSION_MISMATCH"); exit(1); end if;',
        'writeFile("msl_version.txt", getVersion(Modelica));',
        'writeFile("msl_source.txt", getSourceFile(Modelica));',
        f'if not loadFile({quote(library)}) then print(getErrorString()); exit(1); end if;',
        f'if not loadFile({quote(model)}) then print(getErrorString()); exit(1); end if;',
        f'buildModel({study.model.name}, startTime={a["startTime"]!r}, stopTime={a["stopTime"]!r}, '
        f'numberOfIntervals={a["intervals"]}, tolerance={a["tolerance"]!r}, method="{a["solver"]}", '
        'fileNamePrefix="model", outputFormat="mat", variableFilter=".*");',
        'getErrorString();', ''])


def check_setup(path: Path, study) -> dict:
    """Validate reported settings, not the computed solution or XML start guesses."""
    root = ET.parse(path).getroot()
    require(root.attrib.get('modelName') == study.model.name, 'setup', 'wrong compiled model')
    experiment = root.find('DefaultExperiment')
    require(experiment is not None, 'setup', 'missing native experiment')
    a = settings(study); e = experiment.attrib
    for key in ('startTime','stopTime','tolerance'):
        require(float(e[key]) == a[key], 'setup', 'effective setting differs: '+key)
    step = (a['stopTime']-a['startTime'])/a['intervals']
    require(abs(float(e['stepSize'])-step) <= 1e-12*max(1.,abs(step)), 'setup', 'output interval mismatch')
    require(e.get('solver') == a['solver'] and e.get('outputFormat') == 'mat', 'setup', 'solver/format mismatch')
    return dict(e)


def prepare(root: Path, plan: dict, pin: str) -> None:
    out = confined(root, plan['output']); out.mkdir(exist_ok=False)
    state = {'schema':'sim_heat.native_batch_attempt/1','status':'preparing','planSha256':pin,
             'nativeQualified':False,'createdAt':datetime.now(timezone.utc).isoformat(),
             'counts':{'versionQueries':0,'buildModelCalls':0,'modelLaunches':0}, 'cases':[],
             'github':{k:os.environ.get(k) for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT')},
             'environment':{'python':platform.python_version(),'platform':platform.platform(),
                            **{p:importlib.metadata.version(p) for p in ('numpy','scipy')}},'pins':plan['pins']}
    save(out/'attempt.json', state)
    try:
        invoke([sys.executable,'-B','-m','unittest','discover','-s','h1/tests','-v'],root,out,'offline_tests',120)
        for i, entry in enumerate(plan['cases']):
            study = load_study(root/entry['study'],root/plan['caseRoot'])
            require(study.request_report['admitted'], 'study', 'refused requests')
            model_path = study.path.parent/study.data['model']['path']
            require(model_path.relative_to(root).as_posix() in plan['pins'], 'identity', 'model not pinned')
            folder = out/f'case_{i+1:02}'; folder.mkdir()
            spec = reference.read_reference(root/entry['reference']); bind_reference(study,spec)
            bundle = reference.prepare(spec)
            save(folder/'reference.bundle.json', bundle)
            save(folder/'admission.json',report(study))
            (folder/'model.mo').write_bytes(model_path.read_bytes())
            (folder/'SimHeat.mo').write_bytes((root/plan['library']).read_bytes())
            (folder/'study.json').write_bytes(study.path.read_bytes())
            state['cases'].append({'study':entry['study'],'model':study.model.name,'directory':folder.name,
                'status':'prepared','referenceSeal':bundle['seal'],
                'referenceFileSha256':sha(folder/'reference.bundle.json'),
                'analysis':settings(study),'exports':list(internal_exports(study.model))})
        state['status']='prepared'
    except Exception as exc:
        state['status']='preflight_failed';state['error']=repr(exc);raise
    finally:
        save(out/'attempt.json',state)


def execute(root: Path, plan: dict, pin: str) -> None:
    check_host(plan)
    out = confined(root,plan['output']); state = strict_json((out/'attempt.json').read_text())
    require(state['status']=='prepared' and state['planSha256']==pin and
            len(state['cases'])==len(plan['cases']), 'state', 'missing/consumed preparation')
    state['status']='executing'; save(out/'attempt.json',state)
    try:
        omc = shutil.which('omc');require(omc is not None,'host','compiler absent')
        state['compiler']={'path':omc,'sha256':sha(Path(omc))}
        state['counts']['versionQueries']+=1;save(out/'attempt.json',state)
        invoke([omc,'--version'],out,out,'compiler_version',30,native=True)
        require((out/'compiler_version.stdout').read_text().strip()==plan['compilerVersion'], 'host','wrong compiler')
        for entry, item in zip(plan['cases'],state['cases']):
            folder=out/item['directory']; study=load_study(root/entry['study'],root/plan['caseRoot'])
            require(sha(folder/'reference.bundle.json')==item['referenceFileSha256'] and
                    sha(folder/'model.mo')==study.model_sha256 and
                    sha(folder/'SimHeat.mo')==plan['pins'][plan['library']], 'identity','prepared input drift')
            bundle=strict_json((folder/'reference.bundle.json').read_text())
            (folder/'build.mos').write_text(build_script(study,folder/'SimHeat.mo',folder/'model.mo'))
            item['status']='building';state['counts']['buildModelCalls']+=1;save(out/'attempt.json',state)
            invoke([omc,str(folder/'build.mos')],folder,folder,'build',600,native=True)
            logs=(folder/'build.stdout').read_text(errors='replace')+(folder/'build.stderr').read_text(errors='replace')
            require('Error:' not in logs and (folder/'model').is_file(), 'build','compiler error/missing executable')
            item['effectiveSettings']=check_setup(folder/'model_init.xml',study)
            require((folder/'msl_version.txt').read_text().strip()==plan['mslVersion'], 'host','MSL mismatch')
            msl=Path((folder/'msl_source.txt').read_text().strip())
            require(msl.is_file(), 'host','missing MSL source identity')
            save(folder/'msl_manifest.json', {p.relative_to(msl.parent).as_posix():sha(p)
                 for p in sorted(msl.parent.rglob('*.mo')) if p.is_file()})
            item['status']='launching';item['executableSha256']=sha(folder/'model')
            state['counts']['modelLaunches']+=1;save(out/'attempt.json',state)
            invoke([str(folder/'model')],folder,folder,'simulation',120,native=True)
            item['status']='executed';save(out/'attempt.json',state)
            grid=tuple(study.grid) if study.data['mode']=='transient' else (0.,1.)
            decoded=decode_mat_file(folder/'model_res.mat',internal_exports(study.model),grid,
                                   maximum_shift=bundle['temporalPolicy']['maximumShift'])
            csv=decoded.pop('canonicalCsv');data=decoded.pop('decoded')
            decoded['samples']=len(data['columns']['time']);decoded['duplicateRowsCollapsed']=data['duplicateRowsCollapsed']
            (folder/'normalized.csv').write_bytes(csv.encode('utf-8'));save(folder/'mat_provenance.json',decoded)
            receipt=candidate_receipt(study,bundle,csv,'unattested_output');save(folder/'receipt.json',receipt)
            verdict=check_candidate(study,bundle,csv,receipt,item['referenceSeal']);save(folder/'verification.json',verdict)
            item.update(status=verdict['status'],rawMatSha256=decoded['rawMatSha256'],
                        canonicalSamples=decoded['samples'],checkCount=len(verdict['checks']),
                        maxRatio=max(c['maximumRatio'] for c in verdict['checks']))
            save(out/'attempt.json',state)
            require(verdict['status']=='checks_passed' and verdict['nativeQualified'] is False,
                    'verification','diagnostic failed; remaining cases not launched')
        state['status']='diagnostic_checks_passed_not_native_qualified'
    except Exception as exc:
        state['status']='stopped';state['error']=repr(exc)
        (out/'error.txt').write_text(traceback.format_exc());raise
    finally:
        state['finishedAt']=datetime.now(timezone.utc).isoformat()
        state['artifactSha256']={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*'))
                               if p.is_file() and p.name!='attempt.json'}
        save(out/'attempt.json',state)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','execute'));parser.add_argument('--plan',required=True)
    parser.add_argument('--pin',required=True);args=parser.parse_args()
    try:
        plan=load_plan(ROOT,confined(ROOT,args.plan),args.pin)
        (prepare if args.phase=='prepare' else execute)(ROOT,plan,args.pin)
        return 0
    except Exception:
        traceback.print_exc();return 1


if __name__=='__main__':
    raise SystemExit(main())
