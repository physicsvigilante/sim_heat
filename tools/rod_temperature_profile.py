"""Recover node temperatures and rod peaks for steady one-dimensional uniform generation."""
from fractions import Fraction as F
from itertools import product

from qualification.h1_n7.verified_junctions import _enclosure_from_verified_barrier
from qualification.h1_n13.conduction import Box, ZERO
from tools.radiating_surface import decimal_input


def loaded_temperatures(net, powers, fixed_temperatures=None):
    prescribed = fixed_temperatures or {}
    temperatures = net.values([prescribed.get(n, Box.exact(net.initial[n])) for n in net.fixed])
    injections = {node: F(0) for node in net.nodes}
    edges = []
    for rod, a, b, g in net.edges:
        half = powers.get(rod, F(0))/2
        injections[a] += half
        injections[b] += half
        edges.append((rod, a, b, *g.span()))
    if not any(injections[n] for n in net.junctions):
        return temperatures

    for probe in net.junctions:
        # Ground the baths and impose unit voltage at the probe in the thermal
        # analogy. Use 1 K and 2 K for the inherited positive-temperature proof.
        known = {n: F(1) for n in net.fixed}
        known[probe] = F(2)
        free = [n for n in net.junctions if n != probe]
        enclosed, _ = _enclosure_from_verified_barrier(free, known, edges)
        weights = {n: Box.exact(t-1) for n, t in known.items()}
        weights.update({n: Box.bounds(lo-1, hi-1) for n, (lo, hi) in enclosed.items()})
        _, incoming = net.flows(weights)
        conductance = -incoming[probe]
        # Reciprocity turns the distributed endpoint inputs into an equivalent
        # source at this probe. Its one-port conductance converts watts to kelvins.
        effective = sum((weights[n]*p for n, p in injections.items()), ZERO)
        temperatures[probe] += effective/conductance
    return temperatures


def peak(a, b, curvature):
    if not curvature:
        return max(a, b)
    x = max(F(0), min(F(1), (1 + (b-a)/curvature)/2))
    return (1-x)*a + x*b + curvature*x*(1-x)


def rod_peaks(net, powers, *, fixed_temperatures=None, probe=None):
    if probe is not None:
        name, position = probe
        fraction = decimal_input(position, "position fraction from port a")
        if not any(rod == name for rod, *_ in net.edges) or fraction > 1:
            raise ValueError("probe requires a known rod and a position fraction in [0,1]")
        probe = (name, fraction)
    temperatures = loaded_temperatures(net, powers, fixed_temperatures)
    records = {}
    observation = {}
    for rod, first, last, conductance in net.edges:
        a, b = temperatures[first], temperatures[last]
        power = powers.get(rod, F(0))
        gl, gh = conductance.span()
        curve = (power/(2*gh), power/(2*gl))
        if probe is not None and rod == probe[0]:
            x = probe[1]
            # T(x) is quadratic for uniform generation. Fourier's law gives
            # Q(x) = -G dT/dx for the dimensionless coordinate from a to b.
            temp = a*(1-x) + b*x + Box.bounds(*curve)*(x*(1-x))
            current = conductance*(a-b) + Box.exact(power*(x-F(1,2)))
            observation = {"probe": {"rod": rod, "fromNode": first, "toNode": last,
                                     "positionFractionFromA": str(x),
                                     "temperatureBoundsK": list(map(str, temp.span())),
                                     "heatCurrentTowardBBoundsW": list(map(str, current.span()))}}
        al, ah = a.span()
        bl, bh = b.span()
        # Every point of the profile increases with both endpoint temperatures
        # and with curvature, so the same ordering bounds its maximum.
        hottest = (peak(al, bl, curve[0]), peak(ah, bh, curve[1]))
        if power:
            xs = [max(F(0), min(F(1), (1+d/k)/2))
                  for d, k in product((bl-ah, bh-al), curve)]
            positions = (min(xs), max(xs))
        elif al > bh:
            positions = (F(0), F(0))
        elif bl > ah:
            positions = (F(1), F(1))
        else:
            positions = (F(0), F(1))
        records[rod] = {"fromNode": first, "toNode": last,
                        "peakTemperatureBoundsK": list(map(str, hottest)),
                        "peakPositionFractionFromABounds": list(map(str, positions))}
    return {"nodeTemperatureBoundsK": {n: list(map(str, box.span())) for n, box in temperatures.items()},
            "rodPeaks": records, **observation}
