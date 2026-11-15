"""Case-specific checking evidence only; never a production trajectory solver.

Independently encoded two-state closed-form modes from the precommitted task.
No imports from h1, NumPy, SciPy, or the production/reference implementation.
Both intended decimal facts and exact binary input values are evaluated.
The supplied bundle is compared, never rewritten. This is same-author evidence,
not independent-person review or formal interval arithmetic certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import mpmath as mp

LOCAL_REFERENCE_SEAL = 'd644302bebfa877e1739a70850a0b8f3bb878ef7bed93158b431ec2189f73ce2'
ROOT = Path(__file__).resolve().parents[2]
PINS = {
    'experiments/dev_bridge/TASK.md': '3f9a1e11af69227a2ffaf3353a2a59662cbb150a63bbae3da5fa9a889361873c',
    'h1/cases/DEV_BRIDGE/model.mo': 'a18b56dbf748bff1c6609970d0812489f800a46d2154d90921f3cb14cb933b2e',
    'h1/cases/DEV_BRIDGE/study.json': 'ec359796e1c1c8daa85a5d518dec658dadedd15470885ccf1f978c0ed6a2318f',
    'experiments/dev_bridge/reference/DEV_BRIDGE.json': 'b316d55727671755423c1c45145b6c0db41da0149b05bef9010bdc500c85d255',
}
# Re-entered from TASK.md, not copied out of h1.reference.calculate matrices.
BODIES = {'left': ('1.3', '520', '298.15'), 'right': ('1.8', '680', '328.15')}
BOUNDARIES = {'heated': '353.15', 'cooled': '283.15'}
RODS = {
    'supplyLeft': ('heated', 'left', '80', '0.4', '0.001'),
    'supplyRight': ('heated', 'right', '40', '0.5', '0.001'),
    'rejectLeft': ('left', 'cooled', '60', '0.5', '0.001'),
    'rejectRight': ('right', 'cooled', '100', '0.5', '0.001'),
    'bridge': ('left', 'right', '120', '0.6', '0.001'),
}


def need(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def validate(bundle: dict, attempt: dict, bundle_path: Path) -> None:
    for rel, pin in PINS.items():
        need(sha(ROOT / rel) == pin, 'fixed input changed: ' + rel)
    payload = {k: v for k, v in bundle.items() if k != 'seal'}
    need(hashlib.sha256(canonical(payload)).hexdigest() == bundle['seal'],
         'reference payload seal mismatch')
    # Bind to the artifact sealed by the frozen runner in THIS preparation.
    # A same-version numerical library is not a cross-host bitwise promise.
    need(attempt['status'] == 'prepared' and attempt['nativeQualified'] is False
         and attempt['counts'] == {'buildModelCalls': 0, 'modelLaunches': 0, 'versionQueries': 0}
         and len(attempt['cases']) == 1, 'not an unused pre-native preparation')
    item = attempt['cases'][0]
    need(item['study'] == 'h1/cases/DEV_BRIDGE/study.json'
         and item['model'] == 'DevThermalBridge'
         and item['referenceSeal'] == bundle['seal']
         and item['referenceFileSha256'] == sha(bundle_path), 'prepared reference binding mismatch')
    need(all(attempt['pins'].get(rel) == pin for rel, pin in PINS.items()),
         'prepared physical source pins mismatch')
    need(bundle['method']['implementationSha256'] == sha(ROOT / 'h1/reference.py')
         and bundle['method']['temporalImplementationSha256'] == sha(ROOT / 'h1/temporal.py')
         and bundle['method']['numpy'] == '2.3.5' and bundle['method']['scipy'] == '1.17.0',
         'reference implementation/dependency identity mismatch')
    spec = bundle['spec']
    original = json.loads((ROOT / 'experiments/dev_bridge/reference/DEV_BRIDGE.json').read_bytes())
    need(spec == original, 'bundle reference input differs from fixed facts')
    need(set(spec['nodes']) == {'left', 'right', 'heated', 'cooled'}, 'wrong nodes')
    need(set(spec['bodies']) == set(BODIES) and set(spec['boundaries']) == set(BOUNDARIES)
         and set(spec['rods']) == set(RODS), 'wrong component identities')
    for name, (mass, heat, temp) in BODIES.items():
        need(spec['bodies'][name] == {'node': name, 'm': float(mass), 'c': float(heat),
                                     'T_initial': float(temp)}, 'body fact mismatch')
    for name, temp in BOUNDARIES.items():
        need(spec['boundaries'][name] == {'node': name, 'T': float(temp)}, 'boundary mismatch')
    for name, (a, b, k, length, area) in RODS.items():
        need(spec['rods'][name] == {'kind': 'RodArea', 'a': a, 'b': b, 'k': float(k),
                                  'L': float(length), 'A': float(area)}, 'rod fact mismatch')
    need(spec['analysis'] == {'startTime': 0, 'stopTime': 20000, 'intervals': 2000,
                             'solver': 'dassl', 'tolerance': 1e-8}, 'analysis changed')
    need(bundle['grid'] == [20000.0 * (i / 2000) for i in range(2001)], 'planned grid changed')


class ClosedForm:
    def __init__(self, interpretation: str):
        def n(s: str):
            return mp.mpf(s) if interpretation == 'decimal_facts' else mp.mpf(float(s))
        self.cap = {name: n(m) * n(c) for name, (m, c, _) in BODIES.items()}
        self.initial = {name: n(t) for name, (_, _, t) in BODIES.items()}
        self.fixed = {name: n(t) for name, t in BOUNDARIES.items()}
        self.g = {name: n(k) * n(area) / n(length) for name, (_, _, k, length, area) in RODS.items()}
        g = self.g; c1 = self.cap['left']; c2 = self.cap['right']
        k1 = g['supplyLeft'] + g['rejectLeft'] + g['bridge']
        k2 = g['supplyRight'] + g['rejectRight'] + g['bridge']
        cross = g['bridge']; determinant = k1 * k2 - cross**2
        f1 = g['supplyLeft'] * self.fixed['heated'] + g['rejectLeft'] * self.fixed['cooled']
        f2 = g['supplyRight'] * self.fixed['heated'] + g['rejectRight'] * self.fixed['cooled']
        self.eq = ((k2 * f1 + cross * f2) / determinant, (cross * f1 + k1 * f2) / determinant)
        a, b, c, d = k1/c1, -cross/c1, -cross/c2, k2/c2
        gap = mp.sqrt((a-d)**2 + 4*b*c)
        self.slow, self.fast = (a+d-gap)/2, (a+d+gap)/2
        need(self.fast > self.slow > 0, 'unsupported modal degeneracy')
        v = (self.initial['left']-self.eq[0], self.initial['right']-self.eq[1])
        self.us = (((self.fast-a)*v[0]-b*v[1])/gap,
                   (-c*v[0]+(self.fast-d)*v[1])/gap)
        self.uf = (v[0]-self.us[0], v[1]-self.us[1])

    def values(self, time: float):
        t = mp.mpf(time)
        es, ef = mp.exp(-self.slow*t), mp.exp(-self.fast*t)
        ps, pf = -mp.expm1(-self.slow*t)/self.slow, -mp.expm1(-self.fast*t)/self.fast
        temp = dict(self.fixed); tint = {k: v*t for k, v in self.fixed.items()}
        for i, name in enumerate(('left', 'right')):
            temp[name] = self.eq[i] + self.us[i]*es + self.uf[i]*ef
            tint[name] = self.eq[i]*t + self.us[i]*ps + self.uf[i]*pf
        qin = dict.fromkeys(temp, mp.mpf(0)); integrated = dict(qin); out = {}
        for name, (a, b, *_rest) in RODS.items():
            q = self.g[name]*(temp[a]-temp[b]); iq = self.g[name]*(tint[a]-tint[b])
            qin[a] -= q; qin[b] += q; integrated[a] -= iq; integrated[b] += iq
            out.update({name+'.T_a': temp[a], name+'.T_b': temp[b], name+'.G': self.g[name],
                        name+'.Q_flow': q, name+'.port_a.Q_flow': q, name+'.port_b.Q_flow': -q})
        integrals = {}
        for name in BODIES:
            out.update({name+'.T': temp[name], name+'.C': self.cap[name], name+'.Q_in': qin[name],
                        name+'.dU': self.cap[name]*(temp[name]-self.initial[name])})
            integrals[name+'.Q_in'] = integrated[name]
        for name in BOUNDARIES:
            out.update({name+'.T': temp[name], name+'.Q_to_network': -qin[name]})
            integrals[name+'.Q_to_network'] = -integrated[name]
        return out, integrals


def evaluate(bundle: dict, interpretation: str, digits: int, indices: list[int]):
    with mp.workdps(digits):
        calc = ClosedForm(interpretation)
        checks = {key: {'maximumRatio': mp.mpf(0), 'maximumAbsoluteError': mp.mpf(0), 'worstIndex': 0}
                  for key in bundle['columns']}
        integrals = {key: {'maximumRatio': mp.mpf(0), 'maximumAbsoluteError': mp.mpf(0), 'worstIndex': 0}
                     for key in bundle['flowIntegrals']}
        expected_samples = {}
        for i in indices:
            out, it = calc.values(bundle['grid'][i])
            need(set(out) == set(checks) and set(it) == set(integrals), 'missing high-precision observable')
            expected_samples[i] = {k: mp.nstr(v, 110) for k, v in out.items()}
            for k, val in out.items():
                error = abs(mp.mpf(bundle['columns'][k][i])-val)
                ratio = error / (mp.mpf(bundle['allowances'][k])/100)
                if ratio > checks[k]['maximumRatio']:
                    checks[k].update(maximumRatio=ratio, maximumAbsoluteError=error, worstIndex=i)
            for k, val in it.items():
                # Same predeclared local integrated-reference budget as reference.prepare.
                scale = max(abs(v) for v in bundle['flowIntegrals'][k])
                allowance = (mp.mpf('0.001') + mp.mpf('0.000001')*mp.mpf(scale))/100
                error = abs(mp.mpf(bundle['flowIntegrals'][k][i])-val); ratio = error/allowance
                if ratio > integrals[k]['maximumRatio']:
                    integrals[k].update(maximumRatio=ratio, maximumAbsoluteError=error, worstIndex=i)
        for group in (checks, integrals):
            for record in group.values():
                record['passed'] = bool(record['maximumRatio'] <= 1)
                record['maximumRatio'] = float(record['maximumRatio'])
                record['maximumAbsoluteError'] = float(record['maximumAbsoluteError'])
        root = mp.findroot(lambda t: calc.values(t)[0]['bridge.Q_flow'], (mp.mpf(1700), mp.mpf(1800)))
        observed = {
            'slowTimeConstantSeconds': mp.nstr(1/calc.slow, 35),
            'fastTimeConstantSeconds': mp.nstr(1/calc.fast, 35),
            'hLambdaFast': mp.nstr(10*calc.fast, 35),
            'horizonInSlowTimeConstants': mp.nstr(20000*calc.slow, 35),
            'leftAsymptoticK': mp.nstr(calc.eq[0], 35), 'rightAsymptoticK': mp.nstr(calc.eq[1], 35),
            'bridgeZeroSeconds': mp.nstr(root, 35),
            'initialBridgeW': mp.nstr(calc.values(0)[0]['bridge.Q_flow'], 35),
            'finalBridgeW': mp.nstr(calc.values(20000)[0]['bridge.Q_flow'], 35),
        }
        return {'inputInterpretation': interpretation, 'digits': digits, 'sampleCount': len(indices),
                'quantities': checks, 'flowIntegrals': integrals, 'predictionOnly': observed,
                'passed': all(r['passed'] for r in [*checks.values(), *integrals.values()])}, expected_samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_bytes())
    attempt = json.loads(args.attempt.read_bytes())
    validate(bundle, attempt, args.bundle)
    primary, samples = evaluate(bundle, 'decimal_facts', 80, list(range(2001)))
    binary, _ = evaluate(bundle, 'exact_binary_input_facts', 80, list(range(2001)))
    selected = [0, 1, 100, 170, 173, 174, 200, 500, 1000, 2000]
    higher, hi_samples = evaluate(bundle, 'decimal_facts', 100, selected)
    with mp.workdps(100):
        precision_difference = max(abs(mp.mpf(samples[i][k])-mp.mpf(hi_samples[i][k]))
                                   for i in selected for k in samples[i])
    record = {'schema': 'sim_heat.bridge_accuracy_evidence/1',
              'status': 'passed' if primary['passed'] and binary['passed'] and higher['passed'] else 'failed',
              'authorIndependence': False, 'nativeExecuted': False, 'nativeQualified': False,
              'method': 'independently encoded two-by-two closed-form modal projectors and exact exponential integrals',
              'referenceSeal': bundle['seal'], 'bundleSha256': sha(args.bundle),
              'preparedAttemptSha256': sha(args.attempt), 'localReferenceSealForContextOnly': LOCAL_REFERENCE_SEAL,
              'scriptSha256': sha(Path(__file__)), 'sourceSha256': PINS,
              'python': platform.python_version(), 'mpmath': mp.__version__,
              'runs': [primary, binary, higher], 'selected100DigitExpectedSamples': hi_samples,
              'maximum80Versus100DigitDifference': mp.nstr(precision_difference, 15),
              'limitations': ['same implementation author, not independent human review',
                             'high-precision comparison, not an outward-rounded interval proof',
                             'does not change any production reference or native value',
                             'full sampled reference accuracy only for this fixed case and grid']}
    with args.out.open('x', encoding='utf-8') as f:
        f.write(json.dumps(record, sort_keys=True, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': record['status'], 'seal': bundle['seal'],
                      'maximumParameterAndValueRatio': max(r['maximumRatio'] for r in primary['quantities'].values()),
                      **primary['predictionOnly']}))
    return 0 if record['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
