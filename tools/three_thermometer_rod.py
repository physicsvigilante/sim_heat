"""Infer uniform steady rod heating from curvature between three thermometers."""
import argparse
import json

from qualification.h1_n13.conduction import Box
from tools.radiating_surface import decimal_input
from tools.rod_generation import bounds
from tools.terminal_response import prepare_steady_network


def reading(position, low, high):
    x = decimal_input(position, "position fraction from port a")
    lo, hi = (decimal_input(value, "temperature in kelvin") for value in (low, high))
    if x > 1 or lo > hi:
        raise ValueError("positions must lie in [0,1] and temperature bounds must be ordered")
    return x, lo, hi


def investigate(inputs, rod, probes, *, check=None):
    if len(probes) != 3:
        raise ValueError("three thermometer readings required")
    readings = sorted(reading(*probe) for probe in probes)
    (x0, lo0, hi0), (x1, lo1, hi1), (x2, lo2, hi2) = readings
    if x0 == x1 or x1 == x2:
        raise ValueError("three distinct thermometer positions required")
    _, candidate, net = prepare_steady_network(*inputs)
    conductances = {name: g for name, _, _, g in net.edges}
    if rod not in conductances:
        raise ValueError("thermometers must name one rod in the pinned study")

    # For T(x) = A + B*x - P*x²/(2G), subtract the right secant
    # slope from the left. The middle reading is the same in both slopes.
    def power_per_conductance(t0, t1, t2):
        return 2*((t1-t0)/(x1-x0) - (t2-t1)/(x2-x1))/(x2-x0)

    curvature = Box.bounds(power_per_conductance(hi0, lo1, hi2),
                           power_per_conductance(lo0, hi1, lo2))
    if curvature.low < 0:
        raise ValueError("readings cannot establish nonnegative uniform heating")
    result = {
        "schema": "sim_heat.offline_rod_power_from_curvature/1",
        "rod": rod, "positionOrigin": "port_a",
        "thermometers": [{"fraction": str(x), "temperatureBoundsK": [str(lo), str(hi)]}
                         for x, lo, hi in readings],
        "conductanceBoundsWPerK": bounds(conductances[rod]),
        "uniformPowerBoundsW": bounds(conductances[rod]*curvature),
        "scope": "local profile curvature under constant conductance and uniform steady generation",
        **{k: candidate[k] for k in ("modelSha256", "studySha256", "factsSha256",
                                     "nativeExecuted", "nativeQualified",
                                     "independentlyCertifiedReference", "runnerConsumable")},
    }

    if check is not None:
        x, low, high = reading(*check)
        if x in (x0, x1, x2):
            raise ValueError("the check thermometer requires a fourth distinct position")
        # Lagrange interpolation is linear in the three temperatures. Include
        # the sign of each weight, also when extrapolating along the same rod.
        lower = upper = 0
        for xi, lo, hi in readings:
            weight = 1
            for xj, _, _ in readings:
                if xi != xj:
                    weight *= (x-xj)/(xi-xj)
            lower += min(weight*lo, weight*hi)
            upper += max(weight*lo, weight*hi)
        result["checkThermometer"] = {
            "fraction": str(x), "measuredBoundsK": [str(low), str(high)],
            "predictedBoundsK": [str(lower), str(upper)],
            "consistentWithLocalQuadratic": low <= upper and high >= lower,
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "rod"):
        parser.add_argument("--"+field, required=True)
    parser.add_argument("--probe", action="append", nargs=3, required=True,
                        metavar=("FRACTION_FROM_A", "LOW_K", "HIGH_K"))
    parser.add_argument("--check", nargs=3, metavar=("FRACTION_FROM_A", "LOW_K", "HIGH_K"))
    args = parser.parse_args()
    print(json.dumps(investigate((args.study, args.root, args.facts, args.facts_sha256),
                                 args.rod, args.probe, check=args.check), indent=2))
