"""Bracket threshold passages of a continuous H1 body-temperature history."""
import argparse
from fractions import Fraction
import json

from tools.bounded_passages import brackets as bounded_brackets, observe


def brackets(values, radius, threshold, step):
    return bounded_brackets(values, radius, threshold, step, ("cooling", "warming"))


def investigate(study, root, facts_path, facts_sha256, body, threshold):
    threshold = Fraction(threshold)
    if threshold <= 0:
        raise ValueError("positive absolute temperature in kelvin required")
    passages, overlaps, radius, provenance = observe(
        study, root, facts_path, facts_sha256, group="bodies", name=body,
        field="T", threshold=threshold, directions=("cooling", "warming"),
    )
    return {
        "schema": "sim_heat.offline_temperature_passages/1",
        "body": body, "thresholdK": str(threshold), "temperatureErrorBoundK": str(radius),
        "status": "bracketed" if passages else "no_certified_passage",
        "passages": passages, "samplesOverlappingThreshold": overlaps,
        **provenance,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("study", "root", "facts", "facts-sha256", "body", "threshold-k"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256,
                                 args.body, args.threshold_k), indent=2))
