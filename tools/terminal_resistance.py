"""Measure two-terminal steady resistance through the offline H1 reference engine."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from h1.reference import networks
from qualification.h1_n4.static_physical import MAX_SOURCE_BYTES, parse_facts
from qualification.h1_n13.conduction import prepare


def terminal_pair(facts):
    boundaries = facts["boundaries"]
    if facts["mode"] != "steady" or facts["bodies"]:
        raise ValueError("terminal resistance requires a steady conductor network")
    if len(boundaries) != 2 or len(networks(facts)) != 1:
        raise ValueError("expected one connected network with exactly two reservoirs")
    cold, hot = sorted(boundaries, key=lambda name: boundaries[name]["T"])
    difference = Fraction(boundaries[hot]["T"]) - Fraction(boundaries[cold]["T"])
    if difference == 0:
        raise ValueError("equal reservoir temperatures cannot measure resistance")
    return hot, cold, difference


def supply_bounds(candidate, reservoir):
    key = reservoir + ".Q_to_network"
    centre, = candidate["exports"][key]["values"]
    # The pinned N13 engine bounds each W export by its ratio times 1e-8 W.
    error = Fraction(candidate["maxErrorToBudgetBySeries"]["exports"][key]) / 10**8
    centre = Fraction(centre)
    return centre - error, centre + error


def measure(study, root, facts_path, facts_sha256):
    path = Path(facts_path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("invalid source facts path")
    with path.open("rb") as stream:
        facts = parse_facts(stream.read(MAX_SOURCE_BYTES + 1), expected_sha256=facts_sha256)
    hot, cold, difference = terminal_pair(facts)
    candidate = prepare(study, root, path, facts_sha256)
    hot_lo, hot_hi = supply_bounds(candidate, hot)
    cold_lo, cold_hi = supply_bounds(candidate, cold)
    # Steady conservation gives the same through-rate at both terminals.
    low, high = max(hot_lo, -cold_hi), min(hot_hi, -cold_lo)
    if low <= 0 or high < low:
        raise ValueError("terminal supplies do not resolve a common positive heat rate")
    return {
        "schema": "sim_heat.offline_terminal_resistance/1",
        "hot": hot, "cold": cold, "temperatureDifferenceK": str(difference),
        "heatRateBoundsW": [str(low), str(high)],
        "resistanceBoundsKPerW": [str(difference / high), str(difference / low)],
        **{key: candidate[key] for key in ("modelSha256", "studySha256", "factsSha256",
                                            "nativeExecuted", "nativeQualified",
                                            "independentlyCertifiedReference", "runnerConsumable")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.study, args.root, args.facts, args.facts_sha256), indent=2))
