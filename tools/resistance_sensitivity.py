"""Measure which rods control effective resistance in a steady two-terminal network."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from h1.reference import networks
from qualification.h1_n4.static_physical import MAX_SOURCE_BYTES, parse_facts
from qualification.h1_n5.thermal_graph import assemble
from qualification.h1_n13.conduction import Box, Conduction, prepare


def square(interval):
    low, high = interval.span()
    a, b = low**2, high**2
    return Box.bounds(Fraction(0) if low <= 0 <= high else min(a, b), max(a, b))


def bounds(interval):
    return [str(v) for v in interval.span()]


def investigate(study, root, facts_path, facts_sha256):
    path = Path(facts_path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("invalid source facts path")
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    facts = parse_facts(raw, expected_sha256=facts_sha256)
    components = networks(facts)
    if (facts["mode"] != "steady" or facts["bodies"] or
            len(components) != 1 or len(facts["boundaries"]) != 2):
        raise ValueError("one steady connected two-terminal network required")
    candidate = prepare(study, root, path, facts_sha256)
    net = Conduction(assemble(raw, expected_sha256=facts_sha256), components)
    first, second = net.fixed
    values = net.values([Box.exact(1), Box.exact(0)])
    flows, incoming = net.flows(values)
    throughput = -incoming[first]
    if throughput.low <= 0:
        raise ValueError("effective conductance is unresolved")
    rods = {}
    for name, a, b, conductance in net.edges:
        fraction = flows[name] / throughput
        derivative = square(fraction)
        rods[name] = {"resistanceDerivativeBounds": bounds(derivative),
                      "relativeSensitivityBounds": bounds(derivative * throughput / conductance)}
    return {"schema": "sim_heat.offline_resistance_sensitivity/1",
            "terminals": [net.owner[first], net.owner[second]],
            "effectiveResistanceBoundsKPerW": bounds(Box.exact(1) / throughput), "rods": rods,
            **{k: candidate[k] for k in ("modelSha256", "studySha256", "factsSha256",
                                         "nativeExecuted", "nativeQualified",
                                         "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256), indent=2))
