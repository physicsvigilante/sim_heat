"""Read-only P0 plan checks. No reference solver, compiler, installer or native process.

This checks a proposed plan, NOT executable readiness or future numerical results.
No function in this file changes executionReady or opens the native gate.
"""
from __future__ import annotations
import argparse
import hashlib
from fractions import Fraction
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
 'STATIC_CHECKING_CENTRES_FAIL_PHYSICAL_100X_BOUND',
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


# F-01 DESIGN/REFUSAL probes only. These do not certify a trajectory, inspect a
# native result or prepare/save a reference bundle. Fractions represent exact
# rational values; neither NumPy nor the H1 reference functions form this oracle.

def power_two(exponent: int) -> Fraction:
    return Fraction(2**exponent) if exponent >= 0 else Fraction(1, 2**(-exponent))


def floor_log2(value: Fraction) -> int:
    need(value > 0, 'positive arithmetic target required')
    e = value.numerator.bit_length() - value.denominator.bit_length()
    return e - 1 if value < power_two(e) else e


def round_binary64(value: Fraction) -> Fraction:
    """Exact positive IEEE binary64 RN-even, no hardware float operations.

    Bounded checker: finite nonnegative inputs only; overflow refuses. Gradual
    underflow is included so tests can check ties and the normal boundary.
    """
    need(isinstance(value, Fraction) and value >= 0, 'invalid rational target')
    if value == 0:
        return value
    e = floor_log2(value)
    need(e <= 1023, 'binary64 overflow')
    quantum = power_two(max(e - 52, -1074))
    scaled = value / quantum
    n, remainder = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * remainder
    if twice > scaled.denominator or (twice == scaled.denominator and n % 2):
        n += 1
    result = n * quantum
    need(result <= (2 - power_two(-52)) * power_two(1023), 'binary64 overflow')
    return result


def binary64_ulp(value: Fraction) -> Fraction:
    need(value >= 0 and round_binary64(value) == value, 'not a represented number')
    return power_two(max(floor_log2(value) - 52, -1074)) if value else power_two(-1074)


def pi_enclosure(terms: int = 40) -> tuple[Fraction, Fraction]:
    """Machin identity; each alternating arctan remainder is bounded exactly."""
    need(type(terms) is int and 1 <= terms <= 100, 'bounded Pi series required')
    def atan_bounds(denominator):
        x = Fraction(1, denominator)
        partial = sum(((-1)**i * x**(2*i+1) / (2*i+1) for i in range(terms)), Fraction())
        next_term = (-1)**terms * x**(2*terms+1) / (2*terms+1)
        return min(partial, partial+next_term), max(partial, partial+next_term)
    l5,h5 = atan_bounds(5); l239,h239 = atan_bounds(239)
    return 16*l5-4*h239, 16*h5-4*l239


# These are independently pinned source-expression interpretations, never
# selected from output. A Modelica apparent-order hypothesis is NOT an OMC claim.
ARITHMETIC_FORMS = {
    'body_capacity': ('J/K', 'm*c', 'RN(RN(m)*RN(c))', 'RN(RN(m)*RN(c))'),
    'area_conductance': ('W/K', 'k*A/L', 'RN(RN(RN(k)*RN(A))/RN(L))',
                        'RN(RN(RN(k)*RN(A))/RN(L))'),
    'circular_area': ('m2', 'pi*d*d/4',
        'RN(PI64*RN(RN(RN(d)/2)*RN(RN(d)/2)))',
        'RN(RN(RN(PI64*RN(d))*RN(d))/4)'),
    'circular_conductance': ('W/K', 'k*(pi*d*d/4)/L',
        'RN(RN(RN(k)*CHECKING_AREA)/RN(L))',
        'RN(RN(RN(k)*SOURCE_ORDER_AREA)/RN(L))'),
}


def constant_targets(entry: dict, pi_bounds: tuple[Fraction, Fraction]):
    """Physical real enclosure, exact checking-rounding target, source hypothesis."""
    inputs = entry['exactInputs']
    need(all(type(v) is str for v in inputs.values()), 'exact source strings required')
    x = {k: Fraction(v) for k,v in inputs.items()}
    need(all(v > 0 for v in x.values()), 'positive source arithmetic required')
    r = {k: round_binary64(v) for k,v in x.items()}
    rn = round_binary64
    plo,phi = pi_bounds
    pi64 = rn(plo)
    need(pi64 == rn(phi), 'Pi enclosure does not select one binary64 value')
    need(float(pi64).hex() == '0x1.921fb54442d18p+1', 'unexpected nearest Pi')
    kind=entry['family']
    if kind == 'body_capacity':
        p=x['m']*x['c']; op=rn(r['m']*r['c'])
        return (p,p), op, op
    if kind == 'area_conductance':
        p=x['k']*x['A']/x['L']; op=rn(rn(r['k']*r['A'])/r['L'])
        return (p,p), op, op
    need(kind in ('circular_area','circular_conductance'), 'unknown constant family')
    exact_area=(plo*x['d']**2/4, phi*x['d']**2/4)
    radius=rn(r['d']/2)
    check_area=rn(pi64*rn(radius*radius))
    source_area=rn(rn(rn(pi64*r['d'])*r['d'])/4)
    if kind == 'circular_area':
        return exact_area,check_area,source_area
    return (tuple(p*x['k']/x['L'] for p in exact_area),
            rn(rn(r['k']*check_area)/r['L']),rn(rn(r['k']*source_area)/r['L']))


def physical_certificate(value: Fraction, enclosure: tuple[Fraction, Fraction],
                         epsilon: Fraction) -> tuple[bool, Fraction]:
    """The mandatory gate NEVER swaps physical target for rounding agreement."""
    lo,hi=enclosure
    need(lo <= hi and epsilon > 0, 'invalid physical enclosure/budget')
    delta=max(abs(value-lo),abs(value-hi))
    return delta <= epsilon/100, delta


def arithmetic_diagnostics(plan: dict, facts_path: Path) -> dict:
    ledger=plan['constantArithmeticLedger']
    # This design record fixes all fourteen static C/G/A exports, not a whitelist
    # of convenient constants. Other exported quantities keep physical enclosures.
    need(ledger['schema']=='sim_heat.h1_n1_constant_arithmetic/1'
         and ledger['mandatory100xTarget']=='EXACT_SOURCE_MATHEMATICS_ENCLOSURE'
         and ledger['representationTarget']=='PREDECLARED_RN_EVEN_BINARY64_OPERATION_TREES',
         'arithmetic target changed')
    for key in ('representationPassMayReplacePhysical100x','constantExemptionsAllowed',
                'postOutputTargetSelectionAllowed','sourceOrderIsNativeObservation',
                'fusedOrReassociatedOperationsAllowedWithoutNewReview'):
        need(ledger[key] is False, 'arithmetic boundary weakened: '+key)
    need(ledger['nativeComparisonUlpMultiplier']==64 and ledger['referenceErrorDivisor']==100
         and ledger['roundingRule']=='nearest_ties_to_even_binary64', 'constant policy changed')
    pi=ledger['pi']
    need(pi['termsPerArctangent']==40 and pi['binary64Hex']=='0x1.921fb54442d18p+1'
         and pi['compilerMslValueAttested'] is False, 'Pi/native identity not established')
    witness=ledger['correctlyRoundedPhysicalWitness']
    need(witness['rule']=='RN_EVEN_OF_PHYSICAL_ENCLOSURE_ONLY_IF_BOTH_ENDPOINTS_ROUND_IDENTICALLY'
         and witness['adoptedAsCheckingValue'] is False
         and witness['mayRewriteCurrentOrHistoricalReferences'] is False
         and witness['futureNewCheckingVersionAndBoundRunnerRequired'] is True,
         'a feasibility witness is not an adopted reference')
    facts=json.loads(facts_path.read_text(),parse_float=Fraction,parse_int=Fraction)
    expected={}
    for name,b in facts['bodies'].items():
        expected[name+'.C']=('body_capacity',{k:b[k] for k in ('m','c')})
    for name,r in facts['rods'].items():
        circle=r['kind']=='RodCircular'
        if circle: expected[name+'.A']=('circular_area',{'d':r['d']})
        expected[name+'.G']=('circular_conductance' if circle else 'area_conductance',
                             {k:r[k] for k in (('k','L','d') if circle else ('k','L','A'))})
    entries=ledger['entries']
    need(len(entries)==14 and len({e['export'] for e in entries})==14
         and {e['export'] for e in entries}==set(expected),'static ledger coverage')
    static_inventory={n for n in plan['acceptance']['mandatoryExports']
                      if n.rsplit('.',1)[-1] in ('C','G','A')}
    need(static_inventory==set(expected),'static/mandatory export inventories differ')
    rows=[];bounds=pi_enclosure(40)
    for entry in entries:
        name=entry['export']; family,values=expected[name]
        need(entry['family']==family and {k:Fraction(v) for k,v in entry['exactInputs'].items()}==values,
             'constant fact drift: '+name)
        need((entry['unit'],entry['physicalFormula'],entry['checkingOperationTree'],
              entry['sourceOrderHypothesis'])==ARITHMETIC_FORMS[family],
             'constant operation tree drift: '+name)
        physical,op,source=constant_targets(entry,bounds)
        # A pre-native fixed bit pattern, NOT an adaptively chosen target.
        actual=Fraction.from_float(float.fromhex(entry['unchangedCheckingHex']))
        need(actual==op,'unchanged checking bits do not match declared rounding: '+name)
        epsilon=64*binary64_ulp(actual)
        ok,delta=physical_certificate(actual,physical,epsilon)
        nearest=round_binary64(physical[0])
        need(nearest==round_binary64(physical[1]),'physical nearest centre unresolved: '+name)
        witness_ok,witness_delta=physical_certificate(nearest,physical,64*binary64_ulp(nearest))
        rows.append({'export':name,'checkingHex':entry['unchangedCheckingHex'],
            'physicalEnclosure':[str(x) for x in physical],
            'epsilonExact':str(epsilon),'deltaExactUpper':str(delta),
            'deltaOverBudgetUpper':float(delta/(epsilon/100)),
            'physical100x':'PASS' if ok else 'REFUSED',
            'roundingConsistency':'EXACT_MATCH_NOT_PHYSICAL_CERTIFICATION',
            'sourceOrderHypothesisHex':float(source).hex(),
            'sourceVsCheckingUlp':float(abs(source-actual)/binary64_ulp(actual)),
            'correctlyRoundedPhysicalWitnessHex':float(nearest).hex(),
            'witnessPhysical100x':witness_ok,'witnessDeltaUpperExact':str(witness_delta),
            'witnessAdopted':False,'nativeObserved':False})
    failures=[r['export'] for r in rows if r['physical100x']=='REFUSED']
    need('T10.G' in failures,'original exact-physical T10 refusal must remain visible')
    return {'scope':'STATIC_ARITHMETIC_DESIGN_DIAGNOSTICS_NOT_FULL_CERTIFICATE',
            'physical100xTarget':'EXACT_SOURCE_MATHEMATICS_ENCLOSURE',
            'arithmeticGate':'REFUSED_UNCHANGED_CHECKING_CENTRES',
            'staticExports':len(rows),'physical100xFailures':failures,
            'nativeObserved':False,'referenceBundleWritten':False,'rows':rows}



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
    need(a['constant100xTarget']=='EXACT_SOURCE_MATHEMATICS_ENCLOSURE',
         'constants must not evade physical accuracy')
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
    arithmetic=arithmetic_diagnostics(p,q/'reference-facts.json')
    return {'schema':'sim_heat.pre_native_plan_check/1','planId':p['id'],
        'planStructuralChecks':'PASS','referenceFactsBinding':'PASS',
        'pinnedBaselineCommit':BASE,'pinnedBaselineTree':TREE,
        'originalModelSha256':MODEL_SHA,'originalStudySha256':STUDY_SHA,
        'mandatoryExports':len(exports),'publicRequests':len(study.data['requests']),
        'sourceFidelityClaim':'prior R2 H1-T1-UNSEALED review only; no native accuracy',
        'nativeExecuted':False,'nativeQualified':False,'nativeExecutionReady':False,
        'referenceAccuracyCertified':False,'nativeCallsThisCheck':0,
        'constantArithmetic':arithmetic,
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
