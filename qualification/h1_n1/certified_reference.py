"""H1-N1 checking-only interval reference for the already sealed T1-T source.

NOT a native wrapper or runner. Oracle inputs come from independently stated
source facts, NOT parser graph, Modelica executable or native results.

All finite arithmetic intervals are integer-scaled and outward rounded.
The only transcendental constant, pi, has a rational alternating-series
Machin enclosure. A norm-based exact-rational remainder encloses exp(X).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction as F
from hashlib import sha256
import json
import math
from pathlib import Path

from qualification.h1_n1.check_plan import pi_enclosure

HERE = Path(__file__).resolve().parent
Q = 10 ** 64
N_TAYLOR = 18
REPO_ROOT = HERE.parents[1]
FACTS_SHA256 = '39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf'
MODEL_SHA256 = '2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae'
STUDY_SHA256 = '12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a'
DYNAMIC = ("R", "B", "P")
JUNCTIONS = ("J_Upper", "J_Lower")
BOUNDARIES = ("W", "K")
SOURCE_NODES = DYNAMIC + JUNCTIONS + BOUNDARIES
# These are source TASK identities, not native variable aliases.


def ceildiv(a: int, b: int) -> int:
    if b <= 0:
        raise ValueError("nonpositive divisor")
    return -((-a) // b)


@dataclass(frozen=True)
class I:
    lo: int
    hi: int

    def __post_init__(self):
        if self.lo > self.hi:
            raise ValueError("reversed interval")

    @classmethod
    def rational(cls, x):
        f = F(x)
        return cls(f.numerator * Q // f.denominator,
                   ceildiv(f.numerator * Q, f.denominator))

    def __add__(self, other):
        other = interval(other)
        return I(self.lo + other.lo, self.hi + other.hi)

    __radd__ = __add__

    def __neg__(self):
        return I(-self.hi, -self.lo)

    def __sub__(self, other):
        return self + -interval(other)

    def __rsub__(self, other):
        return interval(other) + -self

    def __mul__(self, other):
        other = interval(other)
        pairs = (self.lo * other.lo, self.lo * other.hi,
                 self.hi * other.lo, self.hi * other.hi)
        return I(min(pairs) // Q, ceildiv(max(pairs), Q))

    __rmul__ = __mul__

    def inv(self):
        if self.lo <= 0 <= self.hi:
            raise ValueError("interval contains zero")
        if self.hi < 0:
            return -(-self).inv()
        return I(Q * Q // self.hi, ceildiv(Q * Q, self.lo))

    def __truediv__(self, other):
        return self * interval(other).inv()

    def contains(self, x):
        f = F(x)
        return self.lo * f.denominator <= f.numerator * Q <= self.hi * f.denominator

    def bounds(self):
        return F(self.lo, Q), F(self.hi, Q)

    def center(self):
        return float(F(self.lo + self.hi, 2 * Q))

    def maxerr(self, center=None):
        if center is None:
            center = self.center()
        f = F.from_float(center)
        low, high = self.bounds()
        return max(abs(f-low), abs(f-high))

    def width(self):
        return F(self.hi-self.lo, Q)


def interval(x):
    return x if isinstance(x, I) else I.rational(x)


def matrix_mul(a, b):
    n, k, m = len(a), len(b), len(b[0])
    assert all(len(row) == k for row in a) and all(len(row) == m for row in b)
    return [[sum((a[i][p] * b[p][j] for p in range(k)), I.rational(0))
             for j in range(m)] for i in range(n)]


def matvec(a, v):
    return [sum((x * y for x, y in zip(row, v)), I.rational(0)) for row in a]


def identity(n):
    return [[I.rational(int(i == j)) for j in range(n)] for i in range(n)]


def exp_step(b, intervals):
    """Validated affine exp(B/intervals), only for an exactly zero last row.

    Overwriting the affine row with the identity is mathematically valid ONLY
    when B[-1,:] is exactly zero. Otherwise the helper must REFUSE instead
    of returning a nonconservative claimed matrix-exponential enclosure.
    """
    if type(intervals) is not int or intervals <= 0:
        raise ValueError('Taylor requires a positive integer grid')
    if not isinstance(b, (list, tuple)) or not (1 <= len(b) <= 7) or any(
        not isinstance(row, (list, tuple)) or len(row) != len(b) for row in b
    ):
        raise ValueError('Taylor requires a square matrix of dimension 1..7')
    if any(type(v) is not I or type(v.lo) is not int or type(v.hi) is not int
           for row in b for v in row):
        raise ValueError('Taylor matrix entries must be bounded intervals')
    if any(v.lo != 0 or v.hi != 0 for v in b[-1]):
        raise ValueError('Taylor requires exactly zero affine last row')
    x = [[e / intervals for e in row] for row in b]
    rho = max(sum((F(max(abs(v.lo), abs(v.hi)), Q) for v in row), F(0)) for row in x)
    if not (F(0) < rho <= F(1, 2)):
        raise ValueError("Taylor norm precondition refused")
    term, result = identity(len(b)), identity(len(b))
    for n in range(1, N_TAYLOR + 1):
        term = [[v / n for v in row] for row in matrix_mul(term, x)]
        result = [[a + y for a, y in zip(r, t)] for r, t in zip(result, term)]
    # ||X^k||_infty <= rho^k and the ratio of successive scalar terms
    # is <= rho/(N+2). This bounds each true matrix-entry tail.
    rem = rho ** (N_TAYLOR + 1) / math.factorial(N_TAYLOR + 1)
    rem /= 1 - rho / (N_TAYLOR + 2)
    rad = ceildiv(rem.numerator * Q, rem.denominator)
    result = [[I(v.lo-rad, v.hi+rad) for v in row] for row in result]
    # Last augmented coordinate is identically one: exact matrix structure.
    result[-1] = [I.rational(int(j == len(b)-1)) for j in range(len(b))]
    return result, {"matrixNormUpper": str(rho), "seriesTerms": N_TAYLOR,
                    "remainderBound": str(rem), "roundingScale": "1e-64"}


def source_fraction(x):
    if type(x) not in (Decimal, int):
        raise ValueError("source fact must be exact JSON number")
    return F(x)


def read_facts(path=HERE/'reference-facts.json'):
    # A case-specific reference *must not* silently consume altered facts.
    # The independent task's immutable original source is pinned by its digest.
    raw = Path(path).read_bytes()
    if sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError('reference source-facts byte identity mismatch')
    s = json.loads(raw.decode('utf8'), parse_float=Decimal)
    if s['modelSha256'] != MODEL_SHA256 or s['studySha256'] != STUDY_SHA256:
        raise ValueError('reference task/model identity mismatch')
    inputs = HERE/'inputs/T'
    if sha256((inputs/'model.mo').read_bytes()).hexdigest() != MODEL_SHA256 or \
       sha256((inputs/'study.json').read_bytes()).hexdigest() != STUDY_SHA256:
        raise ValueError('original authored source files changed')
    if s['id'] != 'H1T1TFirstAttemptV1' or s['mode'] != 'transient':
        raise ValueError("wrong source-task identity")
    if set(s['nodes']) != set(SOURCE_NODES):
        raise ValueError("unexpected source topology nodes")
    if set(s['rods']) != {f'T{i:02d}' for i in range(1,11)}:
        raise ValueError("unexpected rod identities")
    if len(s['bodies']) != 3 or len(s['boundaries']) != 2:
        raise ValueError("wrong body/boundary count")
    return s


def _same_pinned_fact_value(actual, expected):
    """Exact typed recursive equality, not mutable metadata hash assertions.

    This also checks fields which are not currently read by `construct`, such
    as the full analysis identity and source-attribution provenance. Lexical
    decimal precision is preserved (Decimal('95') != Decimal('95.0') here).
    A dict's insertion order is not physical data; list order is preserved.
    """
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (actual.keys() == expected.keys() and
                all(_same_pinned_fact_value(actual[k], v) for k, v in expected.items()))
    if type(expected) is list:
        return (len(actual) == len(expected) and
                all(_same_pinned_fact_value(x, y) for x, y in zip(actual, expected)))
    if type(expected) is Decimal:
        return actual.as_tuple() == expected.as_tuple()
    return actual == expected


def construct(s):
    """Independent exact-source interval conductances, graph, Schur reduction.

    No imports from H1 parser/reference; mathematical k*A/L assembled from
    separately published task-fact records with exact decimal rational values.
    """
    pl, ph = pi_enclosure(45)
    pi = I.rational(pl) + I(0, ceildiv((ph-pl).numerator*Q, (ph-pl).denominator))
    # Max upper rounding adjustment must include both source-Pi endpoints.
    assert pi.contains(pl) and pi.contains(ph)
    zero = I.rational(0)
    lap = [[zero for _ in SOURCE_NODES] for _ in SOURCE_NODES]
    index = {name:i for i,name in enumerate(SOURCE_NODES)}
    conductances, areas, capacities = {}, {}, {}
    for rid, r in sorted(s['rods'].items()):
        if r['kind'] == 'RodArea':
            area = interval(source_fraction(r['A']))
        else:
            d = source_fraction(r['d'])
            area = pi * interval(d * d / 4)
            areas[rid] = area
        g = interval(source_fraction(r['k'])) * area / interval(source_fraction(r['L']))
        if g.lo <= 0:
            raise ValueError('nonpositive conductance enclosure')
        conductances[rid] = g
        a, b = index[r['a']], index[r['b']]
        if a == b: raise ValueError('self-conducting rod')
        lap[a][a] = lap[a][a] + g
        lap[b][b] = lap[b][b] + g
        lap[a][b] = lap[a][b] - g
        lap[b][a] = lap[b][a] - g
    for name,c in sorted(s['bodies'].items()):
        capacities[name] = interval(source_fraction(c['m']) * source_fraction(c['c']))
    # Dynamic D first (R,B,P); algebraic J next; fixed F last.
    ljj = [[lap[i][j] for j in (3,4)] for i in (3,4)]
    det = ljj[0][0]*ljj[1][1] - ljj[0][1]*ljj[1][0]
    if det.lo <= 0: raise ValueError('Schur pivot cannot certify positive')
    inverse = [[ljj[1][1]/det, -ljj[0][1]/det],
               [-ljj[1][0]/det, ljj[0][0]/det]]
    # J_T = coeff*(T_D, T_F) = -L_JJ^-1 L_J,O
    lj_o = [[lap[j][o] for o in (0,1,2,5,6)] for j in (3,4)]
    transform = [[-e for e in row] for row in matrix_mul(inverse, lj_o)]
    # Temperature weights for node-normalized values [uR,uB,uP,1].
    weights = {
        'R': [interval(1),zero,zero,zero],
        'B': [zero,interval(1),zero,zero],
        'P': [zero,zero,interval(1),zero],
        'W': [zero,zero,zero,interval(1)],
        'K': [zero,zero,zero,zero]
    }
    for i,name in enumerate(JUNCTIONS):
        weights[name] = [*transform[i][:3], transform[i][3]]
    # Each node row must map all-ones physical equal-T mode to same T.
    # W is the only nonzero fixed U; K fixed U=0. Require unsimplified
    # Schur matrices reach exactly all-ones (including K contribution).
    other = matrix_mul(inverse, [[lap[j][6]] for j in (3,4)])
    for i in range(2):
        unity = sum(weights[JUNCTIONS[i]][:3],zero) + weights[JUNCTIONS[i]][3] - other[i][0]
        if not unity.contains(1):
            raise ValueError("Schur row fails constant-temperature consistency")
    mat = [[zero for _ in range(7)] for _ in range(7)]
    for j, node in enumerate(DYNAMIC):
        owner = next((nm for nm,c in s['bodies'].items() if c['node']==node), None)
        if owner is None: raise ValueError('missing dynamic body')
        cap = capacities[owner]
        for p in range(4):
            rhs = sum((lap[j][i] * weights[name][p] for i,name in enumerate(SOURCE_NODES)), zero)
            if p < 3: mat[j][p] = -interval(2400) * rhs / cap
            else: mat[j][-1] = -interval(2400) * rhs / cap
    for j in range(3): mat[j+3][j] = interval(1)
    start = [interval(F(source_fraction(next(c['T_initial'] for c in s['bodies'].values() if c['node']==node))-289,78)) for node in DYNAMIC]
    state0 = start + [zero,zero,zero,interval(1)]
    return {"matrix": mat, "nodeWeights": weights,
            "conductances":conductances,"areas":areas,"capacities":capacities,
            "state0":state0,"pi":pi,"source":s}


def node_values(model, state):
    unit = interval(1)
    dyn = state[:3]
    out = {}
    for node,row in model['nodeWeights'].items():
        u = sum((row[j]*dyn[j] for j in range(3)), interval(0)) + row[3]
        out[node] = interval(289) + interval(78)*u
    return out


def node_integral(model, state, time):
    # v=integral u d tau; 2400s*78K v gives integrated theta in K*s.
    v = state[3:6]
    out = {}
    for node,row in model['nodeWeights'].items():
        u_integral = sum((row[j]*v[j] for j in range(3)), interval(0)) + row[3] * interval(F(time,2400))
        out[node] = interval(289*time) + interval(78*2400)*u_integral
    return out


def exports_for(model, state, time, integrals=False):
    s = model['source']; t=node_values(model, state)
    tint=node_integral(model,state,time) if integrals else None
    out = {}; flowintegrals={}
    incoming = {n:interval(0) for n in SOURCE_NODES}
    integrated_in = {n:interval(0) for n in SOURCE_NODES}
    for name,c in sorted(s['rods'].items()):
        a,b=c['a'],c['b'];g=model['conductances'][name]
        flow=g*(t[a]-t[b])
        incoming[a] = incoming[a]-flow;incoming[b]=incoming[b]+flow
        if integrals:
            fint=g*(tint[a]-tint[b])
            integrated_in[a] = integrated_in[a]-fint
            integrated_in[b] = integrated_in[b]+fint
        for field,val in [('T_a',t[a]),('T_b',t[b]),('Q_flow',flow),('port_a.Q_flow',flow),('port_b.Q_flow',-flow),('G',g)]:
            out[f'{name}.{field}']=val
        if name in model['areas']:out[f'{name}.A']=model['areas'][name]
    for name,c in sorted(s['bodies'].items()):
        node=c['node'];cap=model['capacities'][name]
        out[f'{name}.T']=t[node]
        out[f'{name}.Q_in']=incoming[node]
        out[f'{name}.dU']=cap*(t[node]-interval(source_fraction(c['T_initial'])))
        out[f'{name}.C']=cap
        if integrals:flowintegrals[f'{name}.Q_in']=integrated_in[node]
    for name,c in sorted(s['boundaries'].items()):
        node=c['node'];out[f'{name}.T']=t[node]
        out[f'{name}.Q_to_network']=-incoming[node]
        if integrals:flowintegrals[f'{name}.Q_to_network']=-integrated_in[node]
    return out, flowintegrals


def unit_for(key):
    field=key.split('.')[-1]
    if field in ('T','T_a','T_b'):return 'K'
    if field in ('Q_in','Q_flow','Q_to_network'):return 'W'
    if field=='dU':return 'J'
    return {'G':'W/K','C':'J/K','A':'m2'}[field]


def safe_allowance(key, value, unit_override=None):
    # Conservative below the existing source's own-scale comparator allowances:
    # min temperature scale >=1, W/J sample max scale >=0.
    unit = unit_override or unit_for(key)
    if unit == 'K':return F.from_float(1e-5) + F.from_float(1e-6)
    if unit == 'W':return F.from_float(1e-6)
    if unit == 'J':return F.from_float(1e-3)
    return 64 * F.from_float(math.ulp(abs(value)))


def reqs_at(exports):
    return {
      't_ridge_temp':exports['T_Ridge.T'],
      't_collar_temp':exports['T_Collar.T'],
      't_plug_temp':exports['T_Plug.T'],
      't_ridge_energy':exports['T_Ridge.dU'],
      't_plug_energy':exports['T_Plug.dU'],
      't_collar_to_plug':exports['T06.Q_flow'],
      't_upper_lower_link':exports['T10.Q_flow'],
      't_upper_minus_cool':exports['T03.T_a']-exports['T_Cool.T']
    }


def certify(s, intervals=2400, *, output=None):
    # The CLI is not the only caller. Never certify a mutable, possibly
    # altered in-memory object while stamping the trusted FACTS_SHA256.
    # Compare every typed fact with a fresh, byte-verified source load, and
    # compute solely from THAT private snapshot (avoids caller TOCTOU edits).
    pinned=read_facts()
    if not _same_pinned_fact_value(s, pinned):
        raise ValueError('pinned source-facts object identity mismatch')
    s=pinned
    if intervals not in (2400,4800):raise ValueError('unsupported scope grid')
    if output is not None:
        output=Path(output).resolve()
        if output.is_relative_to(REPO_ROOT) or output.exists():
            raise ValueError('reference output must be a new outside-repository scratch directory')
    model=construct(s)
    step,proof=exp_step(model['matrix'],intervals)
    state=model['state0']
    columns={};reqs={};integrals={}
    maxima={}; widths={};epsilons={}
    reqmax={};reqeps={};intmax={};inteps={}
    energy_residual_max=F(0);junction_residual_max=F(0)
    quadrature_max={};quad_acc={};prev_flux={}
    proof_violations=[]
    N=intervals
    for i in range(N+1):
        # Uses exactly 0..2400 s for primary and dense. NO native time grid.
        time=F(2400*i, N)
        outs,ints=exports_for(model,state,time,integrals=True)
        req=reqs_at(outs)
        if i==0:
            columns={k:[] for k in sorted(outs)}
            reqs={k:[] for k in sorted(req)}
            integrals={k:[] for k in sorted(ints)}
            maxima={k:F(0) for k in columns}
            widths={k:F(0) for k in columns}
            epsilons={k:None for k in columns}
            if len(columns)!=77 or len(reqs)!=8 or len(integrals)!=5:
                raise ValueError('required exported quantity inventory differs')
            reqmax={k:F(0) for k in req};reqeps={k:None for k in req}
            intmax={k:F(0) for k in ints};inteps={k:None for k in ints}
            quadrature_max={k:F(0) for k in ints}
            quad_acc={k:F(0) for k in ints}
        for k,iv in outs.items():
            mid=iv.center();err=iv.maxerr(mid)
            e=safe_allowance(k,mid)
            if err > e/100:proof_violations.append((k,i,str(err/(e/100))))
            columns[k].append(mid)
            if err>maxima[k]:maxima[k]=err
            if iv.width()>widths[k]:widths[k]=iv.width()
            if epsilons[k] is None or e<epsilons[k]:epsilons[k]=e
        for k,iv in req.items():
            mid=iv.center(); err=iv.maxerr(mid)
            unit='J' if k.endswith('energy') else 'W' if k in ('t_collar_to_plug','t_upper_lower_link') else 'K'
            epsilon=safe_allowance(k,mid,unit)
            if err > epsilon/100:proof_violations.append((k,i,str(err/(epsilon/100))))
            reqs[k].append(mid)
            if err>reqmax[k]:reqmax[k]=err
            if reqeps[k] is None or epsilon<reqeps[k]:reqeps[k]=epsilon
        for k,iv in ints.items():
            mid=iv.center();err=iv.maxerr(mid)
            epsilon=safe_allowance(k,mid,'J')
            if err>epsilon/100:proof_violations.append((k,i,str(err/(epsilon/100))))
            integrals[k].append(mid)
            if err>intmax[k]:intmax[k]=err
            if inteps[k] is None or epsilon<inteps[k]:inteps[k]=epsilon
            flux=F.from_float(outs[k].center())
            if i:
                dt=F(2400,N)
                quad_acc[k] += dt*(prev_flux[k]+flux)/2
            prev_flux[k]=flux
            err_quad=max(abs(quad_acc[k]-bound) for bound in iv.bounds())
            quadrature_max[k]=max(quadrature_max[k],err_quad)
        # Algebraic conservation is checked from independent interval
        # reconstructions at each sample, never from native data.
        for node in JUNCTIONS:
            balance=I.rational(0)
            for rid,c in s['rods'].items():
                q=outs[f'{rid}.Q_flow']
                if c['a']==node:balance=balance-q
                if c['b']==node:balance=balance+q
            if not balance.contains(0):
                raise ValueError('junction energy balance failed: '+node)
            junction_residual_max=max(junction_residual_max, max(abs(x) for x in balance.bounds()))
        for name in s['bodies']:
            resid=outs[f'{name}.dU']-ints[f'{name}.Q_in']
            if not resid.contains(0):
                raise ValueError('body energy integral balance failed: '+name)
            energy_residual_max=max(energy_residual_max,max(abs(x) for x in resid.bounds()))
        net=sum((outs[f'{b}.dU'] for b in s['bodies']), I.rational(0))-sum((ints[f'{b}.Q_to_network'] for b in s['boundaries']),I.rational(0))
        if not net.contains(0):
            raise ValueError('whole-network energy integral balance failed')
        energy_residual_max=max(energy_residual_max,max(abs(x) for x in net.bounds()))
        if i<N:
            state=matvec(step,state)
            # The last coordinate equals one EXACTLY for every tau.
            state[-1]=interval(1)
    if proof_violations:
        raise ValueError('certified source reference budget refused: '+repr(proof_violations[:4]))
    # Original source's trapezoid diagnostic uses 1e-4*max(1, energyScale).
    # A uniform 1e-4 J check is even stricter than that rule for each output.
    if any(v > F(1,10_000) for v in quadrature_max.values()):
        raise ValueError('original-reference trapezoid grid adequacy refused')
    report={'schema':'sim_heat.h1_n1.interval_reference_candidate/1',
            'evidenceKind':'analytical_reference_only','nativeExecuted':False,
            'nativeQualified':False,'sourceFidelityQualified':False,
            'privateKeyVerified':False,
            'mathematicalIntervalSelfCheckPassed':True,
            'independentlyCertifiedReference':False,'runtimeReady':False,
            'originalCheckingCentresAdopted':False,
            'historicalReferenceRegenerated':False,
            'staticCheckingPhysical100xRefusalsRetained':
                ['T02.G','T06.A','T06.G','T07.G','T08.G','T10.G','T_Plug.C'],
            'referenceMethod':'exact-decimal source Laplacian, Schur elimination, outward fixed-point intervals, norm-bounded step Taylor and full-grid propagation',
            'refModelSha256':s['modelSha256'],'refStudySha256':s['studySha256'],
            'sourceFactsSha256':FACTS_SHA256,
            'originalAuthorFullCommentSha256':'fa96e40b24fe3b039e823a78f54546bdf0ed2400e0f3b1b9519bbeb764e3c893',
            'scoringMethod':'H1-T1-UNSEALED_RETROSPECTIVE_PUBLIC_TASK',
            'gridIntervals':intervals,'stopTime':2400,'samples':N+1,
            'staticExports':14,'allExports':len(columns),'requests':len(reqs),
            'flowIntegrals':len(integrals), 'proof':proof,
            'energyIntegralBalanceResidualMaxUpper':str(energy_residual_max),
            'ownerlessJunctionBalanceResidualMaxUpper':str(junction_residual_max),
            'margin':{k:{'maxErrorUpperRational':str(maxima[k]),'maxEnclosureWidthRational':str(widths[k]),
                         'conservativeNativeAllowanceLowerRational':str(epsilons[k]),
                         'maxErrorToAllowanceFractionUpper':float(maxima[k]/epsilons[k])}
                         for k in sorted(maxima)},
            'publicRequestMargins':{k:{'maxErrorUpperRational':str(reqmax[k]),
                             'conservativeAllowanceLowerRational':str(reqeps[k])} for k in sorted(reqmax)},
            'integralMargins':{k:{'maxErrorUpperRational':str(intmax[k]),
                              'conservativeAllowanceLowerRational':str(inteps[k]),
                              'trapezoidDifferenceUpperRational':str(quadrature_max[k])} for k in sorted(intmax)},
            'originalPublicRequestsNotComputed':True,
            'qualificationLimit':'offline mathematical checking oracle only: no native readout, runtime binding, independent reviewer, host reference seal or executable native permission'}
    if output is not None:
        output.mkdir(parents=True,exist_ok=False)
        # A fresh reference candidate, NOT old C1 bundle. Not recognized by native runner.
        full={'report':report,'grid':[float(F(2400*i,N)) for i in range(N+1)],
              'columns':columns,'requests':reqs,'integrals':integrals,
              'units':{k:unit_for(k) for k in sorted(columns)}}
        blob=json.dumps(full,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        (output/f'N1_T1T_reference_grid{N}.json').write_bytes(blob)
        report['fullTraceSha256']=sha256(blob).hexdigest()
        (output/f'N1_T1T_report_grid{N}.json').write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--facts',type=Path,default=HERE/'reference-facts.json')
    p.add_argument('--intervals',type=int,choices=(2400,4800),default=2400)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();report=certify(read_facts(a.facts),a.intervals,output=a.out)
    print(json.dumps({k:report[k] for k in ('schema','mathematicalIntervalSelfCheckPassed','independentlyCertifiedReference','runtimeReady','samples','allExports','requests','flowIntegrals','fullTraceSha256')},indent=2))


if __name__=='__main__':main()
