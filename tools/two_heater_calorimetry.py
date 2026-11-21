"""Identify two uniformly heated rods from two signed steady bath-supply measurements."""
import argparse
from fractions import Fraction as F
import json

from qualification.h1_n13.conduction import Box
from tools.radiating_surface import decimal_input
from tools.rod_generation import bounds, generation_from_network
from tools.terminal_response import prepare_steady_network


def signed_power(value):
    negative = isinstance(value, str) and value.startswith("-")
    magnitude = decimal_input(value[1:] if negative else value, "measured bath supply")
    return -magnitude if negative else magnitude


def investigate(inputs, heaters, measurements, known_powers=()):
    if len(heaters) != 2 or len(set(heaters)) != 2:
        raise ValueError("two distinct unknown rods required")
    if len(measurements) != 2 or len({m[0] for m in measurements}) != 2:
        raise ValueError("two distinct measured bath supplies required")
    facts, candidate, net = prepare_steady_network(*inputs)
    known = list(known_powers)
    if any(name in heaters for name, _ in known):
        raise ValueError("a heater cannot be both known and unknown")
    units = [generation_from_network(facts, candidate, net, [(name, "1")]) for name in heaters]
    background = (generation_from_network(facts, candidate, net, known)["netBathSupplyBoundsW"]
                  if known else units[0]["unheatedBathSupplyBoundsW"])
    records, rows, deficits = {}, [], []
    for port, qlo, qhi in measurements:
        lo, hi = signed_power(qlo), signed_power(qhi)
        if port not in background or lo > hi:
            raise ValueError("known bath and ordered signed measurement bounds required")
        observed = Box.bounds(lo, hi)
        deficit = Box.bounds(*map(F, background[port])) - observed
        row = [Box.bounds(*map(F, result["generatedPowerToBathBoundsW"][port])) for result in units]
        rows.append(row)
        deficits.append(deficit)
        records[port] = {"measuredSupplyBoundsW": [str(lo), str(hi)],
                         "supplyBeforeUnknownsBoundsW": background[port],
                         "unitSourceShares": {name: bounds(weight) for name, weight in zip(heaters, row, strict=True)}}
    (a, b), (c, d) = rows
    det = a*d-b*c
    if det.contains_zero():
        raise ValueError("the selected baths cannot distinguish these heaters within the available bounds")
    u, v = deficits
    powers = ((u*d-b*v)/det, (a*v-u*c)/det)
    if any(p.low < 0 for p in powers):
        raise ValueError("observations cannot establish two nonnegative powers")
    return {
        "schema": "sim_heat.offline_two_heater_calorimetry/1", "measuredBaths": records,
        "knownRodPowersW": {name: str(decimal_input(x, "known rod power")) for name, x in known},
        "inferredRodPowerBoundsW": {name: bounds(p) for name, p in zip(heaters, powers, strict=True)},
        "sensitivityDeterminantBounds": bounds(det),
        **{k: candidate[k] for k in ("modelSha256", "studySha256", "factsSha256", "nativeExecuted",
                                      "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--"+field, required=True)
    parser.add_argument("--heaters", required=True, nargs=2)
    parser.add_argument("--bath", action="append", nargs=3, required=True, metavar=("BATH", "LOW_W", "HIGH_W"))
    parser.add_argument("--generate", action="append", nargs=2, default=[], metavar=("KNOWN_ROD", "TOTAL_W"))
    a = parser.parse_args()
    print(json.dumps(investigate((a.study, a.root, a.facts, a.facts_sha256), a.heaters, a.bath, a.generate), indent=2))
