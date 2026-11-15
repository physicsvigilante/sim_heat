"""Local numerical checks on candidate data; never awards native acceptance.

Synthetic data may test this path, but cannot qualify a Modelica exporter. A
reference seal binds bytes, not author independence or execution authenticity.
"""
import hashlib
import math
import numpy as np

from . import reference as ref
from .decoder import decode_csv
from .model import require, Refusal, internal_exports
from .policy import local_allowance
from .study import Study


def bind_reference(study: Study, spec: dict) -> None:
    """Compare separately prepared facts/port partitions, not computed answers.

    The reference computation has no dependency on this integration function.
    Mismatch refuses; neither side is changed to match the other.
    """
    ref.validate(spec)
    require(spec['modelSha256'] == study.model_sha256 and spec['studySha256'] == study.sha256,
            'reference_identity', 'reference belongs to another model/study')
    require(spec['id'] == study.data['id'] and spec['mode'] == study.data['mode']
            and spec['analysis'] == study.data['analysis'], 'reference_binding', 'reference experiment differs')
    groups = {'Body': 'bodies', 'FixedTemperature': 'boundaries', 'RodArea': 'rods', 'RodCircular': 'rods'}
    all_ids = set(spec['bodies']) | set(spec['boundaries']) | set(spec['rods'])
    require(all_ids == set(study.model.components), 'reference_binding', 'reference component identities differ')
    for name, c in study.model.components.items():
        expected = spec[groups[c.kind]].get(name)
        require(expected is not None, 'reference_binding', 'reference component type differs')
        if c.kind.startswith('Rod'):
            require(expected['kind'] == c.kind, 'reference_binding', 'reference rod input form differs')
        for field, binding in c.fields.items():
            a, b = binding.value, expected[field]
            # Only alternate floating-point expression rounding is allowed here.
            epsilon = 32 * max(math.ulp(float(a)), math.ulp(float(b)))
            require(abs(a-b) <= epsilon, 'reference_binding', f'reference fact differs: {name}.{field}')
    require(tuple(sorted(ref.memberships(spec).values())) == study.topology.nodes,
            'reference_binding', 'reference physical connectivity differs')


def _verify_bundle(study, bundle, expected_seal):
    require(isinstance(bundle, dict) and isinstance(expected_seal, str), 'reference_identity', 'reference bundle/pin required')
    data = {k: v for k, v in bundle.items() if k != 'seal'}
    try:
        actual = ref.fingerprint(data)
    except (ValueError, TypeError, OverflowError) as exc:
        raise Refusal('reference_identity', 'noncanonical reference bundle') from exc
    require(bundle.get('seal') == actual == expected_seal, 'reference_identity', 'unsealed/stale reference data')
    require(bundle.get('schema') == 'sim_heat.reference_bundle/1'
            and bundle.get('origin') == 'analytical_reference_only'
            and bundle.get('nativeQualified') is False, 'reference_identity', 'invalid reference evidence label')
    spec = bundle['spec']
    require(ref.fingerprint(spec) == bundle.get('specSha256'), 'reference_identity', 'reference specification changed')
    bind_reference(study, spec)
    grid = tuple(study.grid) if study.data['mode'] == 'transient' else (0., 1.)
    require(bundle['grid'] == list(grid), 'reference_binding', 'reference grid differs')
    required = internal_exports(study.model)
    require(set(bundle['columns']) == set(required), 'reference_binding', 'reference mandatory outputs differ')
    for k in required:
        values = bundle['columns'][k]
        require(isinstance(values, list) and len(values) == len(grid) and all(ref.number(x) for x in values),
                'reference_schema', 'invalid reference samples: ' + k)
        epsilon = bundle['allowances'].get(k)
        require(ref.number(epsilon, True), 'reference_schema', 'invalid reference allowance')
    return spec, grid, required


def candidate_receipt(study, bundle, csv_text, evidence_kind='synthetic'):
    """Metadata convenience for tests/manual diagnostics, NOT an attestation."""
    return {'schema': 'sim_heat.candidate/1', 'modelSha256': study.model_sha256,
            'studySha256': study.sha256, 'referenceSeal': bundle['seal'],
            'csvSha256': hashlib.sha256(csv_text.encode('utf-8')).hexdigest(),
            'evidenceKind': evidence_kind, 'dataComplete': True}


def check_candidate(study: Study, bundle: dict, csv_text: str, receipt: dict,
                    expected_reference_seal: str) -> dict:
    """Check all mandatory values and local balances, even with no public requests.

    The caller must obtain expected_reference_seal before inspecting candidate
    outputs. This API cannot establish that chronology or native provenance.
    No option promotes its result to native qualification.
    """
    require(study.request_report['admitted'], 'request', 'study contains refused requests')
    spec, grid, required = _verify_bundle(study, bundle, expected_reference_seal)
    fields = {'schema', 'modelSha256', 'studySha256', 'referenceSeal', 'csvSha256', 'evidenceKind', 'dataComplete'}
    require(isinstance(receipt, dict) and set(receipt) == fields, 'candidate_identity', 'candidate metadata fields')
    require(receipt['schema'] == 'sim_heat.candidate/1' and receipt['evidenceKind'] in ('synthetic', 'unattested_output'),
            'candidate_identity', 'native-qualified label not supported')
    require(receipt['dataComplete'] is True, 'incomplete_output', 'candidate explicitly incomplete')
    require(receipt['modelSha256'] == study.model_sha256 and receipt['studySha256'] == study.sha256
            and receipt['referenceSeal'] == expected_reference_seal
            and receipt['csvSha256'] == hashlib.sha256(csv_text.encode('utf-8')).hexdigest(),
            'candidate_identity', 'stale/mismatched candidate identity')
    decoded = decode_csv(csv_text, required, grid)
    values = {k: np.array(v, dtype=float) for k, v in decoded['columns'].items()}
    expected = {k: np.array(v, dtype=float) for k, v in bundle['columns'].items()}
    eps = bundle['allowances']; t = np.array(grid); checks = []

    def assess(name, residual, allowance, unit):
        r = np.broadcast_to(np.abs(np.asarray(residual, dtype=float)), (len(grid),))
        a = np.broadcast_to(np.asarray(allowance, dtype=float), r.shape)
        require(bool(np.isfinite(r).all() and np.isfinite(a).all() and (a > 0).all()),
                'numerical_domain', 'nonfinite check residual/allowance: ' + name)
        ratios = r/a
        require(bool(np.isfinite(ratios).all()), 'numerical_domain', 'overflowing error ratio')
        worst = int(np.argmax(ratios))
        checks.append({'check': name, 'passed': bool((r <= a).all()), 'unit': unit,
                       'maximumError': float(np.max(r)), 'maximumRatio': float(ratios[worst]),
                       'worstSample': worst, 'allowanceAtWorst': float(a[worst])})

    def port_key(port):
        name, member = port.split('.')
        return name + ('.T_a' if member == 'port_a' else '.T_b' if member == 'port_b' else '.T')

    for key in required:
        assess('reference:' + key, values[key]-expected[key], eps[key], bundle['units'][key])
        if bundle['units'][key] == 'K':
            lo, hi = bundle['networkEnvelopes'][bundle['owners'][key]]
            assess('envelope:' + key, np.maximum(lo-values[key], np.maximum(values[key]-hi, 0)), eps[key], 'K')
    for name, c in spec['rods'].items():
        q, a, b = (name+s for s in ('.Q_flow', '.port_a.Q_flow', '.port_b.Q_flow'))
        assess('rod_conservation:' + name, values[a]+values[b], eps[a]+eps[b], 'W')
        assess('rod_orientation_a:' + name, values[a]-values[q], eps[a]+eps[q], 'W')
        assess('rod_orientation_b:' + name, values[b]+values[q], eps[b]+eps[q], 'W')
        ta, tb, g = name+'.T_a', name+'.T_b', ref.conductance(c)
        assess('rod_law:' + name, values[q]-g*(values[ta]-values[tb]),
               eps[q]+g*(eps[ta]+eps[tb]), 'W')
    for node, ports in ref.memberships(spec).items():
        temperatures = [port_key(p) for p in ports]
        for k in temperatures[1:]:
            assess('node_temperature:' + node + ':' + k, values[k]-values[temperatures[0]],
                   eps[k]+eps[temperatures[0]], 'K')
        terms = []
        for port in ports:
            name, member = port.split('.')
            if name in spec['bodies']:
                terms.append((name+'.Q_in', 1))
            elif name in spec['boundaries']:
                terms.append((name+'.Q_to_network', -1))
            else:
                terms.append((name+'.'+member+'.Q_flow', 1))
        assess('node_balance:' + node, sum(sign*values[k] for k, sign in terms),
               math.fsum(eps[k] for k, _ in terms), 'W')
    for name, c in spec['bodies'].items():
        temp, energy, q = name+'.T', name+'.dU', name+'.Q_in'
        assess('initial:' + name, abs(values[temp][0]-c['T_initial']), 1e-6, 'K')
        cap = c['m']*c['c']
        assess('energy_ownership:' + name, values[energy]-cap*(values[temp]-c['T_initial']),
               eps[energy]+cap*eps[temp], 'J')
        if spec['mode'] == 'transient':
            quad = np.array(bundle['quadratureAllowances'][q])
            assess('body_integral:' + name, values[energy]-ref.trapezoids(t, values[q]),
                   eps[energy]+quad+t*eps[q], 'J')
    if spec['mode'] == 'transient':
        for i, nodes in enumerate(ref.networks(spec)):
            bodies = [name+'.dU' for name, c in spec['bodies'].items() if c['node'] in nodes]
            supplies = [name+'.Q_to_network' for name, c in spec['boundaries'].items() if c['node'] in nodes]
            energy = sum((values[k] for k in bodies), np.zeros(len(t)))
            supplied = sum((ref.trapezoids(t, values[k]) for k in supplies), np.zeros(len(t)))
            allowance = sum(eps[k] for k in bodies)
            allowance += sum((np.array(bundle['quadratureAllowances'][k])+t*eps[k] for k in supplies), np.zeros(len(t)))
            # A conductor-only disconnected subnetwork has zero stored energy;
            # its supplies still carry strictly positive local allowances.
            assess('network_energy:' + str(i), energy-supplied, allowance, 'J')
    else:
        for key in required:
            assess('steady_consistency:' + key, values[key]-values[key][0], 2*eps[key], bundle['units'][key])

    passed = all(c['passed'] for c in checks)
    observations = []
    for r in study.data['requests']:
        entry = {'id': r['id'], 'status': 'not_computed', 'reason': 'candidate checks failed'}
        if passed:
            op = r['op']
            if op == 'temperatureDifference':
                a, b = port_key(r['a']), port_key(r['b'])
                v = values[a]-values[b]
                ref_delta = expected[a]-expected[b]
                allowance = local_allowance('K', float(np.max(np.abs(ref_delta))))
                assess('observation:' + r['id'], v-ref_delta, allowance, 'K')
                unit, origin = 'K', 'derived_from_candidate'
            else:
                key = port_key(r['target']) if op == 'temperature' else r['target']+('.Q_flow' if op == 'heatFlow' else '.dU')
                v, unit, origin = values[key], bundle['units'][key], 'candidate_column'
            entry = {'id': r['id'], 'status': 'diagnostic_only', 'unit': unit,
                     'origin': origin, 'evidenceKind': receipt['evidenceKind'],
                     'values': v.tolist() if spec['mode'] == 'transient' else float(v[0])}
        observations.append(entry)
    passed = all(c['passed'] for c in checks)
    if not passed:
        observations = [{'id': r['id'], 'status': 'not_computed', 'reason': 'candidate checks failed'} for r in study.data['requests']]
    return {'stage': 'offline_candidate_verification', 'status': 'checks_passed' if passed else 'checks_failed',
            'evidenceKind': receipt['evidenceKind'], 'nativeQualified': False, 'nativeExecuted': False,
            'modelSha256': study.model_sha256, 'studySha256': study.sha256,
            'referenceSeal': expected_reference_seal, 'csvSha256': receipt['csvSha256'],
            'timeMeaning': 'physical_time' if spec['mode'] == 'transient' else 'algebraic_evaluation_index',
            'duplicateRowsCollapsed': decoded['duplicateRowsCollapsed'], 'checks': checks, 'requests': observations,
            'limits': ['no native provenance or compiler/export qualification', 'same-author reference data requires review',
                       'sampled algorithm cross-check is not a certified reference error bound',
                       'passing synthetic values do not establish any simulated trajectory']}
