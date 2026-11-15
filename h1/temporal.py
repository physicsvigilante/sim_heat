"""Checking-only temporal sensitivity bounds for the admitted passive networks.

No sampled derivative, production graph, or candidate data is used. Exact
rational arithmetic on the supplied binary input values and directed conversion
provide conservative scalar bounds. This does NOT certify the reference solver,
material idealization, source interpretation, or native exports.
"""
from fractions import Fraction
import math


class TemporalError(ValueError):
    pass


def _need(ok, message):
    if not ok:
        raise TemporalError(message)


def _fraction(value):
    _need(type(value) in (int, float) and math.isfinite(value), 'nonfinite temporal input')
    return Fraction(value)


def _directed(value, upward):
    """Convert a nonnegative rational with the indicated rounding direction."""
    _need(value >= 0, 'negative temporal bound')
    try:
        result = float(value)
    except OverflowError as exc:
        raise TemporalError('temporal bound overflow') from exc
    _need(math.isfinite(result), 'temporal bound overflow')
    represented = Fraction(result)
    if upward and represented < value:
        result = math.nextafter(result, math.inf)
    elif not upward and represented > value:
        result = math.nextafter(result, 0.0)
    _need(math.isfinite(result), 'temporal bound overflow')
    return result


def derivative_bounds(spec):
    """Global-in-time absolute derivatives for t >= 0 under fixed boundaries.

    Passive-network maximum principle: temperatures stay in their connected
    initial/boundary envelope. Body rates are bounded by D*sum(G)/C. An ideal
    junction's derivative is a convex combination of body/boundary derivatives.
    Circular area uses the conservative upper bound A <= d*d (pi < 4).
    """
    nodes = spec['nodes']
    incident = {n: [] for n in nodes}
    adjacency = {n: set() for n in nodes}
    conductances = {}
    for name, rod in spec['rods'].items():
        area = _fraction(rod['A']) if rod['kind'] == 'RodArea' else _fraction(rod['d'])**2
        g = _fraction(rod['k'])*area/_fraction(rod['L'])
        _need(g > 0, 'nonpositive temporal conductance')
        conductances[name] = g
        a, b = rod['a'], rod['b']
        incident[a].append(name); incident[b].append(name)
        adjacency[a].add(b); adjacency[b].add(a)
    rates, flow_bounds = {}, {}
    remaining = set(nodes)
    while remaining:
        pending, group = [min(remaining)], set()
        while pending:
            node = pending.pop()
            if node not in group:
                group.add(node); pending.extend(adjacency[node]-group)
        remaining -= group
        bodies = [(name, c) for name, c in spec['bodies'].items() if c['node'] in group]
        boundaries = [c for c in spec['boundaries'].values() if c['node'] in group]
        temps = [_fraction(c['T_initial']) for _, c in bodies]+[_fraction(c['T']) for c in boundaries]
        _need(bool(temps), 'unanchored temporal network')
        delta = max(temps)-min(temps)
        body_rates = {}
        for name, body in bodies:
            cap = _fraction(body['m'])*_fraction(body['c'])
            _need(cap > 0, 'nonpositive temporal capacity')
            flow_bounds[name] = delta*sum((conductances[e] for e in incident[body['node']]), Fraction(0))
            body_rates[body['node']] = flow_bounds[name]/cap
        fastest = max(body_rates.values(), default=Fraction(0))
        for node in group:
            rates[node] = body_rates.get(node, fastest)
        for boundary in boundaries:
            rates[boundary['node']] = Fraction(0)
    output = {}
    rod_rates = {}
    for name, rod in spec['rods'].items():
        a, b = rod['a'], rod['b']
        rod_rates[name] = conductances[name]*(rates[a]+rates[b])
        output[name+'.T_a'] = rates[a]; output[name+'.T_b'] = rates[b]
        for field in ('Q_flow', 'port_a.Q_flow', 'port_b.Q_flow'):
            output[name+'.'+field] = rod_rates[name]
        output[name+'.G'] = Fraction(0)
        if rod['kind'] == 'RodCircular':
            output[name+'.A'] = Fraction(0)
    for name, body in spec['bodies'].items():
        node = body['node']
        output[name+'.T'] = rates[node]
        output[name+'.Q_in'] = sum((rod_rates[e] for e in incident[node]), Fraction(0))
        output[name+'.dU'] = flow_bounds[name]
        output[name+'.C'] = Fraction(0)
    for name, boundary in spec['boundaries'].items():
        output[name+'.T'] = Fraction(0)
        output[name+'.Q_to_network'] = sum((rod_rates[e] for e in incident[boundary['node']]), Fraction(0))
    return ({k: _directed(v, True) for k, v in output.items()},
            {k: _directed(v, True) for k, v in rates.items()})


def make_policy(spec, grid, allowances):
    """Seal a window using <= 1% of each applicable existing error allowance.

    Body initial temperatures use their stricter 1e-6 K check. All possible
    temperature differences use the absolute 1e-5 K floor, so changing requests
    cannot evade the preflight. No physical tolerance is increased.
    """
    _need(len(grid) >= 2, 'short temporal grid')
    times = [float(x) for x in grid]
    _need(all(math.isfinite(x) for x in times) and times[0] == 0, 'invalid temporal grid')
    spacing = min(b-a for a, b in zip(times, times[1:]))
    _need(spacing > 0, 'unordered temporal grid')
    geometric = min(1e-9*max(1., abs(times[0]), abs(times[-1])), spacing/10)
    bounds, node_rates = derivative_bounds(spec)
    _need(set(bounds) == set(allowances), 'temporal output coverage differs')
    limits = {'grid_geometry': _fraction(geometric)}
    for key, rate in bounds.items():
        budget = _fraction(allowances[key])
        _need(budget > 0, 'invalid temporal output allowance')
        if rate > 0:
            limits['output:'+key] = budget/(100*_fraction(rate))
    for name in spec['bodies']:
        rate = bounds[name+'.T']
        if rate > 0:
            limits['initial:'+name] = _fraction(1e-6)/(100*_fraction(rate))
    # A bound valid even for differences across disconnected assemblies.
    difference_rate = 2*max((_fraction(v) for v in node_rates.values()), default=Fraction(0))
    if difference_rate > 0:
        limits['all_temperature_differences'] = _fraction(1e-5)/(100*difference_rate)
    limiting = min(limits, key=limits.get)
    epsilon = _directed(limits[limiting], False)
    _need(epsilon > 0, 'temporal window underflows')
    ulp_floor = 8*max(math.ulp(x) for x in times)
    _need(ulp_floor <= epsilon, 'temporal sensitivity exceeds timestamp resolution')
    return {'schema': 'sim_heat.temporal/1', 'maximumShift': epsilon,
            'geometricMaximumShift': geometric, 'minimumRepresentableWindow': ulp_floor,
            'budgetFraction': 0.01, 'limitingConstraint': limiting,
            'derivativeBounds': bounds, 'nodeTemperatureRateBounds': node_rates,
            'domain': [times[0], times[-1]],
            'basis': 'passive-network envelope; exact rational input arithmetic; outward-rounded rate bounds',
            'association': 'bounded grid association without interpolation; quadrature uses the planned grid'}
