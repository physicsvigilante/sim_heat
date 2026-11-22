"""Bracket reversals of the signed conductive heat rate through an H1 rod."""
import argparse
import json

from tools.bounded_passages import observe


def investigate(study, root, facts_path, facts_sha256, rod):
    reversals, overlaps, radius, provenance = observe(
        study, root, facts_path, facts_sha256, group="rods", name=rod, field="Q_flow",
        threshold=0, directions=("positive_to_negative", "negative_to_positive"),
    )
    return {
        "schema": "sim_heat.offline_heat_flow_reversals/1",
        "rod": rod, "positiveFrom": rod + ".port_a", "positiveTo": rod + ".port_b",
        "heatRateErrorBoundW": str(radius), "samplesOverlappingZero": overlaps,
        "status": "bracketed" if reversals else "no_certified_reversal",
        "reversals": reversals, **provenance,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("study", "root", "facts", "facts-sha256", "rod"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256,
                                 args.rod), indent=2))
