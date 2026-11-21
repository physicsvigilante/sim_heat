"""Predict isolated equilibrium and check stored energy in each transient component."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from h1.reference import networks
from qualification.h1_n4.static_physical import MAX_SOURCE_BYTES, parse_facts
from qualification.h1_n13.conduction import prepare


def investigate(study, root, facts_path, facts_sha256):
    path = Path(facts_path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("invalid source facts path")
    with path.open("rb") as stream:
        facts = parse_facts(stream.read(MAX_SOURCE_BYTES + 1), expected_sha256=facts_sha256)
    if facts["mode"] != "transient":
        raise ValueError("a transient calorimetry study is required")
    candidate = prepare(study, root, path, facts_sha256)
    results = []
    for nodes in networks(facts):
        bodies = sorted(n for n, b in facts["bodies"].items() if b["node"] in nodes)
        reservoirs = sorted(n for n, b in facts["boundaries"].items() if b["node"] in nodes)
        component = {"bodies": bodies, "reservoirs": reservoirs}
        results.append(component)
        if reservoirs:
            component["status"] = "externally_maintained"
            continue
        capacities = {n: Fraction(facts["bodies"][n]["m"]) * Fraction(facts["bodies"][n]["c"])
                      for n in bodies}
        total = sum(capacities.values())
        if total <= 0:
            raise ValueError("isolated component has no thermal capacity")
        initial = sum(c * Fraction(facts["bodies"][n]["T_initial"]) for n, c in capacities.items())
        # Each dU is relative to that body's own initial state; use the N13 joule budget.
        terms = [candidate["exports"][n + ".dU"]["values"] for n in bodies]
        radius = sum(Fraction(candidate["maxErrorToBudgetBySeries"]["exports"][n + ".dU"])
                     for n in bodies) / 10**5
        residual = max(abs(sum(map(Fraction, samples))) for samples in zip(*terms, strict=True))
        if residual > radius:
            raise ValueError("isolated component stored-energy changes exclude zero")
        # The observed spread at the final time distinguishes approach rate from equilibrium.
        lower, upper = [], []
        for name in bodies:
            key = name + ".T"
            centre = Fraction(candidate["exports"][key]["values"][-1])
            error = Fraction(candidate["maxErrorToBudgetBySeries"]["exports"][key]) / 10**8
            lower.append(centre - error)
            upper.append(centre + error)
        spread_lo = max(0, max(lower) - min(upper))
        spread_hi = max(upper) - min(lower) if len(bodies) > 1 else 0
        component.update(status="isolated", equilibriumTemperatureK=str(initial / total),
                         finalSpreadBoundsK=[str(spread_lo), str(spread_hi)],
                         heatCapacityJPerK=str(total), maximumStoredEnergyResidualJ=str(residual),
                         storedEnergyResidualBoundJ=str(radius))
    return {"schema": "sim_heat.offline_network_calorimetry/1", "components": results,
            "finalTimeSeconds": str(Fraction(facts["analysis"]["stopTime"])),
            **{k: candidate[k] for k in ("modelSha256", "studySha256", "factsSha256",
                                         "nativeExecuted", "nativeQualified",
                                         "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256), indent=2))
