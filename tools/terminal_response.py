"""Bound the steady heat-rate response to temperature changes at maintained terminals."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from h1.reference import networks
from qualification.h1_n4.static_physical import MAX_SOURCE_BYTES, parse_facts
from qualification.h1_n5.thermal_graph import assemble
from qualification.h1_n13.conduction import Box, Conduction, prepare


def prepare_steady_network(study, root, facts_path, facts_sha256):
    path = Path(facts_path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("invalid source facts path")
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    facts = parse_facts(raw, expected_sha256=facts_sha256)
    components = networks(facts)
    if facts["mode"] != "steady" or facts["bodies"]:
        raise ValueError("steady storage-free conduction is required")
    if len(components) != 1 or len(facts["boundaries"]) < 2:
        raise ValueError("one connected network with at least two terminals is required")

    candidate = prepare(study, root, path, facts_sha256)
    net = Conduction(assemble(raw, expected_sha256=facts_sha256), components)
    return facts, candidate, net


def investigate(study, root, facts_path, facts_sha256, *, include_rods=False):
    facts, candidate, net = prepare_steady_network(study, root, facts_path, facts_sha256)
    return response_from_network(facts, candidate, net, include_rods=include_rods)


def response_from_network(facts, candidate, net, *, include_rods=False):
    terminals = sorted(facts["boundaries"])
    response = {name: {} for name in terminals}
    rods = {name: {} for name in facts["rods"]} if include_rods else {}
    # Each column is the supply response to a unit increment at one terminal.
    for selected in terminals:
        increments = [Box.exact(net.owner[n] == selected) for n in net.fixed]
        signed, incoming = net.flows(net.values(increments))
        for name in rods:
            rods[name][selected] = list(map(str, signed[name].span()))
        for n in net.fixed:
            supply = -incoming[n]
            response[net.owner[n]][selected] = [str(x) for x in supply.span()]

    return {**({"rodResponseBoundsWPerK": rods} if include_rods else {}),
            "schema": "sim_heat.offline_terminal_response/1", "terminals": terminals,
            "supplyResponseBoundsWPerK": response,
            "imposedTemperaturesK": {n: str(Fraction(facts["boundaries"][n]["T"])) for n in terminals},
            **{k: candidate[k] for k in ("modelSha256", "studySha256", "factsSha256",
                                         "nativeExecuted", "nativeQualified",
                                         "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256), indent=2))
