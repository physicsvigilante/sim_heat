"""Steady rods with k(T) = k_ref * (1 + alpha * (T - T_ref)) and a shared alpha."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.radiating_surface import decimal_input
from tools.terminal_response import prepare_steady_network


def investigate(inputs, reference_k, slope_per_k):
    reference = decimal_input(reference_k, "reference temperature")
    negative = isinstance(slope_per_k, str) and slope_per_k.startswith("-")
    slope = decimal_input(slope_per_k[1:] if negative else slope_per_k, "relative conductivity slope")
    if negative:
        slope = -slope
    _, candidate, net = prepare_steady_network(*inputs)
    cold, hot = min(net.initial.values()), max(net.initial.values())
    base_factor = 1 + slope * (cold - reference)
    if reference <= 0 or min(base_factor, 1 + slope * (hot-reference)) <= 0:
        raise ValueError("positive reference temperature and conductivity across the full temperature range required")

    def potential(t):
        rise = t-cold
        return rise * (base_factor + slope*rise/2)

    def inverse(value):
        if value == 0:
            return cold, cold
        if value == potential(hot):
            return hot, hot
        if not slope:
            return cold+value, cold+value
        low, high = cold, hot
        for _ in range(96):
            mid = (low+high)/2
            current = potential(mid)
            if current == value:
                return mid, mid
            if current < value:
                low = mid
            else:
                high = mid
        return low, high

    # Integrated Fourier conduction is linear in the common potential.
    field = net.values([Box.exact(potential(net.initial[n])) for n in net.fixed])
    flows, incoming = net.flows(field)
    node_bounds = {}
    for node, box in field.items():
        if node in net.initial:
            node_bounds[node] = [str(net.initial[node])]*2
            continue
        lo, hi = box.span()
        lo, hi = max(lo, Fraction(0)), min(hi, potential(hot))
        if hi < lo:
            raise ValueError("junction potential inconsistent with maintained temperatures")
        node_bounds[node] = [str(inverse(lo)[0]), str(inverse(hi)[1])]
    return {"schema": "sim_heat.offline_variable_conductivity/1",
            "referenceTemperatureK": str(reference), "sharedRelativeSlopePerK": str(slope),
            "portTemperatureBoundsK": {port: node_bounds[node] for port, node in net.ports.items()},
            "rodHeatFlowBoundsW": {name: bounds(flow) for name, flow in flows.items()},
            "terminalSupplyBoundsW": {net.owner[n]: bounds(-incoming[n]) for n in net.fixed},
            **{k: candidate[k] for k in ("studySha256", "modelSha256", "factsSha256", "nativeExecuted",
                                         "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "study", "facts", "facts-sha256", "reference-k", "slope-per-k"):
        parser.add_argument("--"+name, required=True)
    a = parser.parse_args()
    print(json.dumps(investigate((a.study, a.root, a.facts, a.facts_sha256),
                                 a.reference_k, a.slope_per_k), indent=2))
