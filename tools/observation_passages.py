"""Bracket a signed SI threshold for any authored H1 transient observation."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import prepare
from tools.bounded_passages import read_pinned_facts, series_passages


def investigate(study, root, facts_path, facts_sha256, request_id, threshold, unit):
    threshold = Fraction(threshold)
    facts = read_pinned_facts(facts_path, facts_sha256)
    if facts["mode"] != "transient":
        raise ValueError("a transient observation history is required")
    candidate = prepare(study, root, facts_path, facts_sha256)
    if request_id not in candidate["requests"]:
        raise ValueError("unknown study observation")
    if unit != candidate["requests"][request_id]["unit"]:
        raise ValueError("threshold unit differs from the requested observation")
    events, overlaps, radius, provenance = series_passages(
        candidate, facts, "requests", request_id, threshold, ("decreasing", "increasing"))
    return {"schema": "sim_heat.offline_observation_passages/1", "requestId": request_id,
            "unit": unit, "threshold": str(threshold), "errorBound": str(radius),
            "status": "bracketed" if events else "no_certified_passage",
            "passages": events, "samplesOverlappingThreshold": overlaps, **provenance}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "request-id", "threshold", "unit"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate(args.study, args.root, args.facts, args.facts_sha256,
                                 args.request_id, args.threshold, args.unit), indent=2))
