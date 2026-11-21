"""Reduce a one-body conduction network with maintained baths to its cooling law."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from h1.reference import networks
from qualification.h1_n4.static_physical import MAX_SOURCE_BYTES, parse_facts
from qualification.h1_n5.thermal_graph import assemble
from qualification.h1_n13.conduction import Box, Conduction, prepare


def endpoints(value):
    return [str(x) for x in value.span()]


def investigate(study, root, facts_path, facts_sha256):
    path = Path(facts_path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("invalid source facts path")
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    facts = parse_facts(raw, expected_sha256=facts_sha256)
    components = networks(facts)
    if (facts["mode"] != "transient" or len(components) != 1 or
            len(facts["bodies"]) != 1 or not facts["boundaries"]):
        raise ValueError("one connected transient network with one body and maintained baths required")
    candidate = prepare(study, root, path, facts_sha256)
    network = Conduction(assemble(raw, expected_sha256=facts_sha256), components)
    node, = network.bodies
    name = network.owner[node]
    body = facts["bodies"][name]
    capacity = Fraction(body["m"]) * Fraction(body["c"])
    initial = Fraction(body["T_initial"])
    baths = [Fraction(facts["boundaries"][network.owner[n]]["T"]) for n in network.fixed]
    origin = min(baths)
    # A 1 K body increment gives the negative slope of incoming body heat.
    _, slope = network.flows(network.values([Box.exact(1)] + [Box.exact(0) for _ in baths]))
    conductance = -slope[node]
    if conductance.low <= 0:
        raise ValueError("body-to-bath conductance is unresolved")
    offsets = [Box.exact(t-origin) for t in baths]
    _, incoming = network.flows(network.values([Box.exact(0), *offsets]))
    equilibrium = origin + incoming[node] / conductance
    initial_inflow = incoming[node] - conductance * (initial-origin)
    return {"schema": "sim_heat.offline_single_body_relaxation/1", "body": name,
            "heatCapacityJPerK": str(capacity), "initialTemperatureK": str(initial),
            "effectiveConductanceBoundsWPerK": endpoints(conductance),
            "equilibriumTemperatureBoundsK": endpoints(equilibrium),
            "timeConstantBoundsSeconds": endpoints(Box.exact(capacity) / conductance),
            "initialBodyInflowBoundsW": endpoints(initial_inflow),
            **{k: candidate[k] for k in ("modelSha256", "studySha256", "factsSha256",
                                         "nativeExecuted", "nativeQualified",
                                         "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256), indent=2))
