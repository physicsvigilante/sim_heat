"""Reduce heat exchange between two insulated bodies through a storage-free rod network."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from h1.reference import networks
from qualification.h1_n4.static_physical import MAX_SOURCE_BYTES, parse_facts
from qualification.h1_n5.thermal_graph import assemble
from qualification.h1_n13.conduction import Box, Conduction, prepare


def investigate(study, root, facts_path, facts_sha256):
    path = Path(facts_path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("invalid source facts path")
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    facts = parse_facts(raw, expected_sha256=facts_sha256)
    components = networks(facts)
    if (facts["mode"] != "transient" or len(components) != 1 or
            len(facts["bodies"]) != 2 or facts["boundaries"]):
        raise ValueError("one connected isolated transient pair required")
    candidate = prepare(study, root, path, facts_sha256)
    net = Conduction(assemble(raw, expected_sha256=facts_sha256), components)
    first, second = sorted(net.bodies, key=net.owner.__getitem__)
    unit_field = [Box.exact(int(node == first)) for node in net.bodies]
    _, incoming = net.flows(net.values(unit_field))
    conductance = -incoming[first]
    if conductance.low <= 0:
        raise ValueError("body-to-body conductance is unresolved")

    bodies = [net.owner[first], net.owner[second]]
    c1, c2 = (Fraction(facts["bodies"][b]["m"]) * Fraction(facts["bodies"][b]["c"])
              for b in bodies)
    t1, t2 = net.initial[first], net.initial[second]
    reduced = c1*c2/(c1+c2)
    difference = t1-t2
    return {"schema": "sim_heat.offline_isolated_pair_exchange/1",
            "fromBody": bodies[0], "toBody": bodies[1],
            "initialTemperatureDifferenceK": str(difference),
            "equilibriumTemperatureK": str((c1*t1+c2*t2)/(c1+c2)),
            "reducedHeatCapacityJPerK": str(reduced),
            "asymptoticHeatFromFirstToSecondJ": str(reduced*difference),
            "effectiveConductanceBoundsWPerK": list(map(str, conductance.span())),
            "initialHeatFromFirstToSecondBoundsW": list(map(str, (conductance*difference).span())),
            "differenceTimeConstantBoundsSeconds": list(map(str, (Box.exact(reduced)/conductance).span())),
            **{key: candidate[key] for key in ("modelSha256", "studySha256", "factsSha256",
                                               "nativeExecuted", "nativeQualified",
                                               "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256), indent=2))
