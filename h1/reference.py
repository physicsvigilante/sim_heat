"""Checking-only thermal network reference; never imports the production parser.

Inputs are separately authored SI facts/topology, not native answers. expm and a
symmetric spectral calculation cross-check sampled outputs; their agreement is
not a certified error bound, source-fidelity review, or native qualification.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import scipy
from scipy.linalg import expm, eigh


class ReferenceError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise ReferenceError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def number(x, positive=False):
    try:
        return type(x) in (int, float) and math.isfinite(x) and (not positive or x > 0)
    except OverflowError:
        return False


def read_reference(path):
    """No code execution, path expansion, default material, or parser reuse."""
    p = Path(path)
    need(p.is_file() and p.stat().st_size <= 262144, 'reference file missing or too large')
    need(not any(q.is_symlink() for q in (p, *p.parents)), 'reference symlink refused')
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate reference JSON key')
            out[k] = v
        return out
    try:
        value = json.loads(p.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                           parse_constant=lambda x: (_ for _ in ()).throw(ReferenceError('nonfinite JSON')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReferenceError('invalid reference JSON') from exc
    validate(value)
    return value


def validate(s):
    need(isinstance(s, dict) and set(s) == {'schema', 'id', 'mode', 'modelSha256', 'studySha256',
         'analysis', 'provenance', 'nodes', 'bodies', 'boundaries', 'rods'}, 'reference fields')
    need(s['schema'] == 'sim_heat.reference/1' and s['mode'] in ('steady', 'transient'), 'reference schema/mode')
    ident = lambda x: isinstance(x, str) and re.fullmatch('[A-Za-z][A-Za-z0-9_]*', x) is not None
    need(ident(s['id']) and isinstance(s['provenance'], str) and bool(s['provenance'].strip()), 'reference identity/provenance')
    for k in ('modelSha256', 'studySha256'):
        need(isinstance(s[k], str) and re.fullmatch('[0-9a-f]{64}', s[k]) is not None, 'reference hash')
    need(isinstance(s['nodes'], list) and 0 < len(s['nodes']) <= 64 and all(ident(n) for n in s['nodes']), 'reference nodes')
    need(len(set(s['nodes'])) == len(s['nodes']), 'duplicate reference node')
    seen, occupied, used = set(), set(), set()
    for group, maximum in (('bodies', 8), ('boundaries', 8), ('rods', 32)):
        records = s[group]
        need(isinstance(records, dict) and len(records) <= maximum, 'reference component limit')
        for name, c in records.items():
            need(ident(name) and name not in seen and isinstance(c, dict), 'reference component identity')
            seen.add(name)
            if group == 'bodies':
                fields, numeric = {'node', 'm', 'c', 'T_initial'}, ('m', 'c', 'T_initial')
            elif group == 'boundaries':
                fields, numeric = {'node', 'T'}, ('T',)
            else:
                need(c.get('kind') in ('RodArea', 'RodCircular'), 'reference rod kind')
                geom = 'A' if c['kind'] == 'RodArea' else 'd'
                fields, numeric = {'kind', 'a', 'b', 'k', 'L', geom}, ('k', 'L', geom)
            need(set(c) == fields and all(number(c[f], True) for f in numeric), 'reference physical fields')
            if group != 'rods':
                node = c['node']
                need(isinstance(node, str) and node in s['nodes'] and node not in occupied, 'reference node owner')
                occupied.add(node); used.add(node)
                if group == 'bodies':
                    need(number(c['m'] * c['c'], True), 'reference capacity overflow/underflow')
            else:
                need(isinstance(c['a'], str) and isinstance(c['b'], str) and c['a'] in s['nodes']
                     and c['b'] in s['nodes'] and c['a'] != c['b'], 'reference rod endpoints')
                used.update((c['a'], c['b']))
                need(number(area(c), True) and number(conductance(c), True), 'reference conductance overflow/underflow')
    need(used == set(s['nodes']), 'unused reference nodes')
    incident = {n for c in s['rods'].values() for n in (c['a'], c['b'])}
    need(all(c['node'] in incident for c in s['boundaries'].values()), 'unconnected reference boundary')
    need(bool(s['bodies']) if s['mode'] == 'transient' else
         bool(s['rods']) and bool(s['boundaries']) and not s['bodies'], 'reference mode content')
    grid_for(s)
    for net in networks(s):
        need(bool(set(net) & occupied), 'floating reference network')
    return s


def area(c):
    try:
        return c['A'] if c['kind'] == 'RodArea' else math.pi * (c['d'] / 2) ** 2
    except OverflowError as exc:
        raise ReferenceError('reference area overflow') from exc


def conductance(c):
    return c['k'] * area(c) / c['L']


def grid_for(s):
    a = s['analysis']
    need(isinstance(a, dict), 'reference analysis')
    if s['mode'] == 'steady':
        need(a == {}, 'steady reference has no physical time')
        return np.array([0., 1.])  # Backend evaluation indices, NOT physical time.
    need(set(a) == {'startTime', 'stopTime', 'intervals', 'solver', 'tolerance'}, 'reference analysis fields')
    need(number(a['startTime']) and a['startTime'] == 0 and number(a['stopTime'])
         and 1e-6 <= a['stopTime'] <= 1e7, 'reference time domain')
    need(type(a['intervals']) is int and 1000 <= a['intervals'] <= 20000
         and a['intervals'] % 2 == 0, 'reference interval domain')
    need(a['solver'] == 'dassl' and number(a['tolerance']) and a['tolerance'] in (1e-8, 1e-10), 'reference solver policy')
    return np.array([float(a['stopTime']) * (i / a['intervals']) for i in range(a['intervals'] + 1)])


def memberships(s):
    out = {n: [] for n in s['nodes']}
    for group in ('bodies', 'boundaries'):
        for name, c in s[group].items():
            out[c['node']].append(name + '.port')
    for name, c in s['rods'].items():
        out[c['a']].append(name + '.port_a'); out[c['b']].append(name + '.port_b')
    return {n: tuple(sorted(p)) for n, p in out.items()}


def networks(s):
    adjacency = {n: set() for n in s['nodes']}
    for c in s['rods'].values():
        adjacency[c['a']].add(c['b']); adjacency[c['b']].add(c['a'])
    remaining, result = set(adjacency), []
    while remaining:
        pending, group = [min(remaining)], set()
        while pending:
            node = pending.pop()
            if node not in group:
                group.add(node); pending.extend(adjacency[node] - group)
        remaining -= group; result.append(tuple(sorted(group)))
    return tuple(result)


def _solve_network(s, nodes, times, spectral):
    bodies = sorted((n, c) for n, c in s['bodies'].items() if c['node'] in nodes)
    bounds = sorted((n, c) for n, c in s['boundaries'].items() if c['node'] in nodes)
    anchors = [c['node'] for _, c in bodies + bounds]
    order = anchors + sorted(set(nodes) - set(anchors))
    index = {n: i for i, n in enumerate(order)}
    nb, nf, na = len(bodies), len(bounds), len(anchors)
    lap = np.zeros((len(order), len(order)))
    for c in s['rods'].values():
        if c['a'] in index:
            i, j, g = index[c['a']], index[c['b']], conductance(c)
            lap[i, i] += g; lap[j, j] += g; lap[i, j] -= g; lap[j, i] -= g
    need(bool(np.isfinite(lap).all()), 'reference matrix overflow')
    transform = np.eye(len(order), na)
    condition = 1.
    if na < len(order):
        block = lap[na:, na:]; scale = np.sqrt(np.diag(block))
        need(bool((scale > 0).all()), 'zero reference junction diagonal')
        scaled = (block / scale[:, None]) / scale[None, :]
        need(not bool(np.any((block != 0) & (scaled == 0))), 'reference scaled coupling lost')
        condition = float(np.linalg.cond(scaled))
        need(math.isfinite(condition) and condition <= 1e8, 'ill-conditioned reference junction solve')
        transform[na:] = np.linalg.solve(block, -lap[na:, :na])
    reduced = lap[:na] @ transform
    origin = min(c['T_initial'] for _, c in bodies) if bodies else min(c['T'] for _, c in bounds)
    origin = min([origin] + [c['T'] for _, c in bounds])
    fixed = np.array([c['T'] - origin for _, c in bounds])
    anchor_t = np.zeros((len(times), na)); anchor_integral = np.zeros_like(anchor_t)
    if nf:
        anchor_t[:, nb:] = fixed
        anchor_integral[:, nb:] = times[:, None] * fixed
    if nb:
        caps = np.array([c['m'] * c['c'] for _, c in bodies])
        initial = np.array([c['T_initial'] - origin for _, c in bodies])
        k = reduced[:nb, :nb]; forcing = -reduced[:nb, nb:] @ fixed
        if not spectral:
            augmented = np.zeros((2 * nb + 1, 2 * nb + 1))
            augmented[:nb, :nb] = -k / caps[:, None]
            augmented[:nb, -1] = forcing / caps
            augmented[nb:2 * nb, :nb] = np.eye(nb)
            v = np.r_[initial, np.zeros(nb), 1.]
            evolution = expm(times[:, None, None] * augmented) @ v
            anchor_t[:, :nb] = evolution[:, :nb]
            anchor_integral[:, :nb] = evolution[:, nb:2 * nb]
        else:
            root = np.sqrt(caps); h = (k / root[:, None]) / root[None, :]
            norm = float(np.linalg.norm(h, 2))
            need(float(np.max(np.abs(h-h.T))) <= 64*np.finfo(float).eps*max(norm, np.finfo(float).tiny),
                 'reference reduced matrix not symmetric within roundoff')
            values, vectors = eigh((h + h.T) / 2)
            cutoff = 128 * np.finfo(float).eps * max(norm, np.finfo(float).tiny)
            if not bounds:
                # Exactly ONE known conserved mode per connected closed network.
                need(abs(float(values[0])) <= cutoff, 'reference conserved mode unresolved')
                expected_null = root / np.linalg.norm(root)
                need(abs(float(vectors[:, 0] @ expected_null)) >= 1-1e-10, 'wrong reference conserved mode')
                values[0] = 0.
            nonzero = values[1:] if not bounds else values
            need(bool((nonzero > cutoff).all()), 'reference slow mode unresolved; no numerical zero substitution')
            e = np.exp(-times[:, None] * values)
            phi, psi = np.empty_like(e), np.empty_like(e)
            for j, rate in enumerate(values):
                if rate == 0:
                    phi[:, j] = times; psi[:, j] = times**2/2
                else:
                    x = rate * times
                    phi[:, j] = -np.expm1(-x)/rate
                    small = np.abs(x) < 1e-3
                    psi[small, j] = times[small]**2 * (0.5-x[small]/6+x[small]**2/24-x[small]**3/120+x[small]**4/720)
                    psi[~small, j] = (times[~small]-phi[~small, j])/rate
            a, b = vectors.T @ (root*initial), vectors.T @ (forcing/root)
            anchor_t[:, :nb] = ((e*a + phi*b) @ vectors.T)/root
            anchor_integral[:, :nb] = ((phi*a + psi*b) @ vectors.T)/root
    theta = anchor_t @ transform.T
    integrated_theta = anchor_integral @ transform.T
    need(bool(np.isfinite(theta).all() and np.isfinite(integrated_theta).all()), 'nonfinite reference trajectory')
    # Reconstruct ideal-junction temperatures from anchor offsets; avoids subtracting large absolutes in flows.
    return order, theta, integrated_theta, origin, condition


def calculate(s, spectral=False):
    """Return checking trajectories; no access to authored-model parser/results."""
    validate(s); times = grid_for(s)
    node_temp, node_offset, node_integral, conditions = {}, {}, {}, []
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        try:
            for nodes in networks(s):
                order, theta, integrated, origin, cond = _solve_network(s, nodes, times, spectral)
                conditions.append(cond)
                for i, n in enumerate(order):
                    node_temp[n] = theta[:, i] + origin
                    node_offset[n] = theta[:, i]
                    node_integral[n] = integrated[:, i]
        except (FloatingPointError, np.linalg.LinAlgError, OverflowError, ValueError) as exc:
            if isinstance(exc, ReferenceError):
                raise
            raise ReferenceError('reference numerical calculation failed') from exc
    columns, integrals, units, owners = {}, {}, {}, {}
    incoming = {n: np.zeros(len(times)) for n in s['nodes']}
    integral_in = {n: np.zeros(len(times)) for n in s['nodes']}
    def add(name, field, values, unit, node):
        key = name + '.' + field
        v = np.broadcast_to(np.asarray(values, dtype=float), (len(times),)).copy()
        need(bool(np.isfinite(v).all()), 'nonfinite reference output ' + key)
        columns[key] = v; units[key] = unit; owners[key] = node
    for name, c in s['rods'].items():
        a, b, g = c['a'], c['b'], conductance(c)
        flow = g*(node_offset[a]-node_offset[b])
        integrated = g*(node_integral[a]-node_integral[b])
        incoming[a] -= flow; incoming[b] += flow
        integral_in[a] -= integrated; integral_in[b] += integrated
        for f, val, unit, node in [('T_a', node_temp[a], 'K', a), ('T_b', node_temp[b], 'K', b),
                                  ('Q_flow', flow, 'W', a), ('port_a.Q_flow', flow, 'W', a),
                                  ('port_b.Q_flow', -flow, 'W', b), ('G', g, 'W/K', a)]:
            add(name, f, val, unit, node)
        if c['kind'] == 'RodCircular':
            add(name, 'A', area(c), 'm2', a)
    for name, c in s['bodies'].items():
        node, cap = c['node'], c['m']*c['c']
        for f, val, unit in [('T', node_temp[node], 'K'), ('Q_in', incoming[node], 'W'),
                             ('C', cap, 'J/K'), ('dU', cap*(node_temp[node]-c['T_initial']), 'J')]:
            add(name, f, val, unit, node)
        integrals[name + '.Q_in'] = integral_in[node]
    for name, c in s['boundaries'].items():
        node = c['node']
        add(name, 'T', c['T'], 'K', node); add(name, 'Q_to_network', -incoming[node], 'W', node)
        integrals[name + '.Q_to_network'] = -integral_in[node]
    return times, columns, integrals, units, owners, conditions


def trapezoids(times, values):
    out = np.zeros(len(times))
    out[1:] = np.cumsum(np.diff(times)*(values[:-1]+values[1:])/2)
    return out


def prepare(s):
    """Seal candidate checking data before seeing any candidate/native output.

    Identity seals are not authenticity or independent approval. Error estimates
    below are numerical cross-check diagnostics, NOT validated interval bounds.
    """
    s = deepcopy(s)
    t, primary, integrals, units, owners, conditions = calculate(s)
    _, secondary, integral2, _, _, _ = calculate(s, spectral=True)
    envelope = {}
    for nodes in networks(s):
        temps = [c['T_initial'] for c in s['bodies'].values() if c['node'] in nodes]
        temps += [c['T'] for c in s['boundaries'].values() if c['node'] in nodes]
        for n in nodes:
            envelope[n] = (min(temps), max(temps))
    scales, allowances, crosscheck = {}, {}, {}
    for key, v in primary.items():
        unit = units[key]
        if unit == 'K':
            lo, hi = envelope[owners[key]]
            scale = min(max(1., float(np.max(np.abs(v-v[0])))), max(1., hi-lo))
            epsilon = 1e-5 + 1e-6*scale
        elif unit in ('W', 'J'):
            scale = float(np.max(np.abs(v)))
            epsilon = {'W': 1e-6, 'J': 1e-3}[unit] + 1e-6*scale
        else:
            scale = float(np.max(np.abs(v)))
            epsilon = 64*math.ulp(scale)  # Parameter/export arithmetic, not a trajectory tolerance.
        discrepancy = float(np.max(np.abs(v-secondary[key])))
        need(math.isfinite(epsilon) and epsilon > 0 and discrepancy <= epsilon/100,
             'reference algorithms disagree for ' + key)
        scales[key], allowances[key], crosscheck[key] = scale, epsilon, discrepancy
    quadrature, integrated_crosscheck = {}, {}
    if s['mode'] == 'transient':
        for key, value in integrals.items():
            error = float(np.max(np.abs(value-integral2[key])))
            energy_scale = float(np.max(np.abs(value)))
            reference_budget = (1e-3 + 1e-6*energy_scale)/100
            need(error <= reference_budget, 'reference integral cross-check failed: ' + key)
            qerr = np.abs(trapezoids(t, primary[key])-value)
            need(float(np.max(qerr)) <= 1e-4*max(1., energy_scale), 'reference grid quadrature too coarse: ' + key)
            quadrature[key] = (qerr + reference_budget + t*(allowances[key]/100)).tolist()
            integrated_crosscheck[key] = error
    result = {'schema': 'sim_heat.reference_bundle/1', 'origin': 'analytical_reference_only',
              'nativeQualified': False, 'spec': s, 'specSha256': fingerprint(s), 'grid': t.tolist(),
              'columns': {k: v.tolist() for k, v in primary.items()}, 'units': units,
              'owners': owners, 'networkEnvelopes': {k: list(v) for k, v in envelope.items()},
              'scales': scales, 'allowances': allowances,
              'flowIntegrals': {k: v.tolist() for k, v in integrals.items()}, 'quadratureAllowances': quadrature,
              'method': {'primary': 'affine augmented matrix exponential', 'crossCheck': 'capacity-scaled symmetric eigensystem',
                         'numpy': np.__version__, 'scipy': scipy.__version__, 'junctionConditions': conditions,
                         'implementationSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         'maximumDiscrepancies': crosscheck, 'integralDiscrepancies': integrated_crosscheck,
                         'errorClaim': 'sampled cross-check, not a certified bound or independent review'}}
    result['seal'] = fingerprint(result)
    return result
