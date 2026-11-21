"""Partition uniform rod heat generation among the baths of a steady conducting network."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import Box, ZERO
from tools.radiating_surface import decimal_input
from tools.rod_temperature_profile import rod_peaks
from tools.terminal_response import prepare_steady_network


def bounds(box):
    return list(map(str, box.span()))


def investigate(study, root, facts_path, facts_sha256, rod_powers, *, profiles=False, probe=None):
    facts, candidate, net = prepare_steady_network(study, root, facts_path, facts_sha256)
    return generation_from_network(facts, candidate, net, rod_powers, profiles=profiles, probe=probe)


def generation_from_network(facts, candidate, net, rod_powers, *, profiles=False, probe=None):
    sources = {}
    for name, watts in rod_powers:
        if name not in facts["rods"] or name in sources:
            raise ValueError("each heat source must name a distinct rod in the pinned network")
        sources[name] = decimal_input(watts, "rod heat generation in watts")
    if not sources:
        raise ValueError("specify at least one rod and its uniformly generated power")

    _, incoming = net.flows(net.values([Box.exact(net.initial[n]) for n in net.fixed]))
    absorbed = {net.owner[n]: ZERO for n in net.fixed}
    records = {}
    for name, power in sources.items():
        rod = facts["rods"][name]
        delivered = []
        for j, node in enumerate(net.fixed):
            # A uniform line source contributes P/2 at each endpoint. By
            # reciprocity, the fraction reaching a bath from a node equals
            # its temperature influence under unit drive at that bath.
            share = (net.weights[rod["a"]][j] + net.weights[rod["b"]][j]) * Fraction(1, 2)
            lo, hi = share.span()
            share = Box.bounds(max(Fraction(0), lo), min(Fraction(1), hi))
            heat = share * power
            terminal = net.owner[node]
            absorbed[terminal] += heat
            delivered.append((terminal, heat))
        if not (sum((q for _, q in delivered), ZERO) - power).contains_zero():
            raise ValueError("rod power failed to balance across maintained baths")
        records[name] = {"uniformGeneratedPowerW": str(power),
                         "generatedPowerToBathBoundsW": {t: bounds(q) for t, q in delivered}}

    total = sum(sources.values())
    supply = {net.owner[n]: -incoming[n] - absorbed[net.owner[n]] for n in net.fixed}
    if not (sum(supply.values(), ZERO) + total).contains_zero():
        raise ValueError("bath supply and generated power failed steady energy balance")
    result = {
        "schema": "sim_heat.offline_uniform_rod_generation/1",
        "rodsWithGeneration": records, "totalGeneratedPowerW": str(total),
        "imposedTemperaturesK": {net.owner[n]: str(net.initial[n]) for n in net.fixed},
        "unheatedBathSupplyBoundsW": {net.owner[n]: bounds(-incoming[n]) for n in net.fixed},
        "generatedPowerToBathBoundsW": {t: bounds(q) for t, q in absorbed.items()},
        "netBathSupplyBoundsW": {t: bounds(q) for t, q in supply.items()},
        **{k: candidate[k] for k in ("modelSha256", "studySha256", "factsSha256",
                                      "nativeExecuted", "nativeQualified",
                                      "independentlyCertifiedReference", "runnerConsumable")},
    }
    if probe is not None:
        name, position = probe
        fraction = decimal_input(position, "position fraction from port a")
        if name not in facts["rods"] or fraction > 1:
            raise ValueError("probe requires a known rod and a position fraction in [0,1]")
        probe = (name, fraction)
    if profiles or probe is not None:
        result["schema"] = "sim_heat.offline_heated_rod_profiles/1"
        result.update(rod_peaks(net, sources, probe=probe))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--generate", nargs=2, action="append", required=True, metavar=("ROD", "TOTAL_W"))
    parser.add_argument('--profiles', action='store_true')
    parser.add_argument("--probe", nargs=2, metavar=("ROD", "FRACTION_FROM_A"))
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256, args.generate, profiles=args.profiles, probe=args.probe), indent=2))
