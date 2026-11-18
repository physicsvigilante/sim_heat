"""Read-only P0 plan checks. No reference solver, compiler, installer or native process.

This checks a proposed plan, NOT executable readiness or future numerical results.
No function in this file changes executionReady or opens the native gate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from h1.model import internal_exports, Refusal
from h1.study import load_study, strict_json
from h1.reference import read_reference
from h1.verification import bind_reference

Q = ROOT / 'qualification/h1_n1'
BASE = 'f52613c39c539b2d4543a9838e5658d526fca10e'
TREE = '0c44961b473d23737b0c9f3b3f2cd3db65b9f264'
MODEL_SHA = '2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae'
STUDY_SHA = '12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a'
BLOCKERS = [
 'R2_PLAN_REVIEW_NOT_YET_COMPLETE',
 'EXACT_RUNTIME_IMAGE_BINARY_AND_MSL_MANIFEST_UNBOUND',
 'INDEPENDENT_100X_REFERENCE_ERROR_CERTIFICATE_NOT_IMPLEMENTED_OR_VERIFIED',
 'TARGET_HOST_ALL_THREE_NEW_REFERENCE_SEALS_AND_REPLAY_NOT_READY',
 'PRIMARY_ONLY_COMMON_TIME_COMPARATOR_NOT_IMPLEMENTED_OR_REVIEWED',
 'EXACT_EXECUTION_MANIFEST_SINGLE_USE_CONTROL_AND_COMPANION_BYTES_NOT_READY',
 'SEPARATE_EXPLICIT_NATIVE_OWNER_PERMISSION_NOT_GRANTED',
]


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return strict_json(path.read_text(encoding='utf-8'))


def validate_manifest(plan: dict) -> None:
    need(plan['schema'] == 'sim_heat.pre_native_plan/1', 'not a P0 plan')
    need(plan['kind'] == 'PLAN_ONLY_NOT_EXECUTABLE' and plan['executionReady'] is False,
         'plan must not open native execution')
    need(plan['baselineCommit'] == BASE and plan['baselineTree'] == TREE, 'wrong baseline')
    need(plan['modelSha256'] == MODEL_SHA and plan['studySha256'] == STUDY_SHA,
         'original T1-T identity changed')
    expected_authority = {'planningApproved': True, 'nativeExecutionApproved': False,
        'nativeVersionQueryApproved': False, 'nativeInstallationApproved': False,
        'productionMergeApproved': False, 'deployApproved': False}
    need(plan['authority'] == expected_authority, 'only planning authorized')
    need(plan['executionBlockers'] == BLOCKERS, 'unresolved gates omitted')
    limits=plan['limits']
    for field in ('observedNativeVersionQueries', 'observedBuilds', 'observedLaunches', 'maximumRetries'):
        need(type(limits[field]) is int and limits[field] == 0, 'no operations or retries authorized')
    for field in ('proposedCompilerVersionQueries', 'proposedFreshBuilds', 'proposedModelLaunches'):
        need(type(limits[field]) is int and limits[field] == 3, 'one case, three bounded invocations')
    need(limits['physicalModels'] == 1, 'only one physical model')
    need(limits['maximumMatBytes'] == 20*1024*1024 and limits['maximumNativeRows'] == 40002
         and limits['maximumNativeColumns'] == 4096, 'decoder limits changed')
    runs=plan['proposedRuns']
    expected=[('primary',2400,1e-8,2401,1), ('tight',2400,1e-10,2401,1),
              ('dense',4800,1e-8,4801,0.5)]
    need(len(runs)==3, 'three runs only')
    for r,(name,n,tol,samples,h) in zip(runs,expected):
        need((r['id'],r['intervals'],r['tolerance'],r['samples'],r['outputStepSeconds'])
             ==(name,n,tol,samples,h), 'run matrix differs')
        need(r['horizonSeconds']==2400 and r['solver']=='dassl', 'task horizon or solver changed')
        need(r['freshBuild'] is True and all(r[k]==1 for k in
             ('maxVersionQueries','maxBuilds','maxLaunches')), 'invocation budget changed')
    need(runs[0]['studyPolicy']=='EXACT_ORIGINAL_BYTES', 'primary must remain original')
    need(runs[1]['changes']=={'id':'H1T1TFirstAttemptV1_N1_TIGHT','analysis.tolerance':1e-10},
         'tight companion changes physical meaning')
    need(runs[2]['changes']=={'id':'H1T1TFirstAttemptV1_N1_DENSE','analysis.intervals':4800},
         'dense companion changes physical meaning')
    host=plan['host']
    need(host['desiredCompilerVersion']=='OpenModelica 1.27.0'
         and host['desiredMslVersion']=='4.0.0', 'incompatible runner versions')
    need(all(host[k] is None for k in ('actualImageDigest','actualCompilerBinarySha256',
         'actualMslManifestSha256')) and host['actualHostAttested'] is False,
         'unattested runtime cannot be invented')
    need(host['installationAllowedByThisPlan'] is False, 'no install authorized')
    runner=plan['runner']
    need(runner['caseCountPerInvocation']==1 and runner['automaticNativeWorkflowIncluded'] is False
         and runner['generatedRunnablePlansIncluded'] is False, 'no native launcher in P0')
    a=plan['acceptance']
    need((a['absoluteK'],a['absoluteW'],a['absoluteJ'],a['relativeToOwnReferenceScale'],
          a['initialTemperatureK'],a['referenceErrorFractionMaximum'])
         ==(1e-5,1e-6,1e-3,1e-6,1e-6,0.01), 'numerical bounds changed')
    need(a['referenceErrorCertificateRequired'] is True
         and a['referencePrecisionAgreementAloneSufficient'] is False
         and a['fullPrimaryAndDenseGridsRequired'] is True, 'reference proof weakened')
    need(a['companionDifferenceAllowance']=='PRIMARY_ONLY_NOT_SUM_NOT_WIDENED',
         'companion budget must not be widened')
    need(a['nativeQualifiedOutputMustRemainFalse'] is True
         and a['historicalOutputsMustNotBePromoted'] is True
         and a['historicalC1MustRemainUnchanged'] is True, 'qualification/history boundary changed')
    findings=plan['knownPreflightFindings']
    need(findings['legacyCompanionHelperApplicable'] is False
         and findings['primaryDenseAllowanceMismatchCount']==4
         and findings['referenceCertificateAvailable'] is False
         and findings['actualRuntimeBound'] is False, 'screening limitations hidden')


def check(root: Path = ROOT) -> dict:
    q=root/'qualification/h1_n1'
    p=read(q/'plan.json'); validate_manifest(p)
    pins=read(q/'SOURCE-PINS.json')
    need(pins['baselineCommit']==BASE and pins['baselineTree']==TREE, 'source manifest baseline')
    for mapping in ('readonlySha256','inputSha256'):
        for rel,digest in pins[mapping].items():
            path=root/rel
            need(not path.is_symlink() and path.resolve().is_relative_to(root.resolve())
                 and path.is_file() and sha(path)==digest, 'source drift: '+rel)
    study=load_study(q/'inputs/T/study.json',q/'inputs')
    need(study.model_sha256==MODEL_SHA and study.sha256==STUDY_SHA, 'original input hash differs')
    need(study.request_report['admitted'], 'original requests refused')
    # Use correspondence checking only. Never call reference.prepare/calculate or batch.execute.
    spec=read_reference(q/'reference-facts.json'); bind_reference(study,spec)
    need(len(spec['bodies'])==3 and len(spec['boundaries'])==2 and len(spec['rods'])==10
         and len(spec['nodes'])==7, 'wrong selected case')
    exports=list(internal_exports(study.model))
    need(len(exports)==77 and p['acceptance']['mandatoryExports']==exports, 'exports incomplete')
    need(p['acceptance']['publicRequestIds']==[r['id'] for r in study.data['requests']],
         'public request inventory changed')
    screen=read(q/'PLANNING-SCREENING.json')
    need(screen['referenceAccuracyCertified'] is False and screen['nativeExecuted'] is False,
         'screening is not certified or native')
    need(screen['primaryDenseAllowanceEquality'] is False
         and len(screen['mismatchedAllowanceFields'])==4, 'retained comparator issue missing')
    return {'schema':'sim_heat.pre_native_plan_check/1','planId':p['id'],
        'planStructuralChecks':'PASS','referenceFactsBinding':'PASS',
        'pinnedBaselineCommit':BASE,'pinnedBaselineTree':TREE,
        'originalModelSha256':MODEL_SHA,'originalStudySha256':STUDY_SHA,
        'mandatoryExports':len(exports),'publicRequests':len(study.data['requests']),
        'sourceFidelityClaim':'prior R2 H1-T1-UNSEALED review only; no native accuracy',
        'nativeExecuted':False,'nativeQualified':False,'nativeExecutionReady':False,
        'referenceAccuracyCertified':False,'nativeCallsThisCheck':0,
        'executionBlockers':list(BLOCKERS)}


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    result=check()
    text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.out:
        # Caller selects a new evidence file; never overwrite a historical record.
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.open('x',encoding='utf-8') as f: f.write(text)
    print(text,end='')
