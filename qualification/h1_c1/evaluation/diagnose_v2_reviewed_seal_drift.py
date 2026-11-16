#!/usr/bin/env python3
"""Compare actual archived PR31 V2 bundle to both exact-run clean-host bundles.

Diagnostics only: a mismatching seal remains HOLD. Writes *field-level* evidence
with sampled numeric differences, never edits or re-seals any input bundle.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

from qualification.h1_c1.evaluation.compare_v2_reproduction import (
    differences, load, seal,
)

EXPECTED_PR31_RAW = "0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368"
EXPECTED_PR31_SEAL = "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
ORIGINAL_F0_SEAL = "d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b"
NAME = "C1_REFERENCE_V2_BUNDLE.json"


def count_numeric_changes(a, b):
    summary = {
        "numDifferentColumns": 0,
        "differentColumnSamples": 0,
        "columnDifferences": {},
        "differentIntegralHistories": 0,
        "differentIntegralSamples": 0,
        "integralDifferences": {},
        "differentAllowanceKeys": [],
        "differentOtherTopLevelKeys": [],
    }
    for section, key, detail in [
        ("columns", "columnDifferences", "differentColumnSamples"),
        ("flowIntegrals", "integralDifferences", "differentIntegralSamples"),
    ]:
        for name in sorted(set(a.get(section, {})) | set(b.get(section, {}))):
            x = a.get(section, {}).get(name)
            y = b.get(section, {}).get(name)
            if not isinstance(x, list) or not isinstance(y, list):
                if x != y:
                    summary[key][name] = {"kind": "missing/non-array"}
                continue
            different = [(idx, vx, vy) for idx, (vx, vy) in enumerate(zip(x, y))
                         if type(vx) is not type(vy) or vx != vy]
            if different or len(x) != len(y):
                sample = []
                max_absolute_delta = 0.0
                for idx, vx, vy in different:
                    if len(sample) < 8:
                        sample.append({"index": idx, "old": vx, "new": vy,
                                       "absoluteDelta": abs(float(vx)-float(vy))})
                    max_absolute_delta = max(max_absolute_delta,
                                             abs(float(vx)-float(vy)))
                summary[key][name] = {
                    "differentValues": len(different),
                    "leftLength": len(x), "rightLength": len(y),
                    "maxAbsoluteDelta": max_absolute_delta,
                    "examples": sample,
                }
                summary[detail] += len(different)
    summary["numDifferentColumns"] = len(summary["columnDifferences"])
    summary["differentIntegralHistories"] = len(summary["integralDifferences"])
    summary["differentAllowanceKeys"] = sorted(
        name for name in set(a.get("allowances", {})) | set(b.get("allowances", {}))
        if a.get("allowances", {}).get(name) != b.get("allowances", {}).get(name))
    summary["differentOtherTopLevelKeys"] = sorted(
        k for k in set(a) | set(b)
        if k not in {"columns", "flowIntegrals", "seal"} and a.get(k) != b.get(k))
    return summary


def run(pr31dir, h22dir, h24dir, output):
    receipt = {
        "schema": "sim_heat.c1_v2_reference_archive_drift/1",
        "stage": "offline_diagnostic_only",
        "nativeExecuted": False,
        "nativeQualified": False,
        "status": "INCOMPLETE_REFERENCE_DRIFT_DIAGNOSTIC__HOLD",
        "oldHistoricalF0Seal": ORIGINAL_F0_SEAL,
        "referenceCertifiableByThisReport": False,
        "refusals": [],
    }
    try:
        specs = {}
        for name, root in (("pr31_reviewed", pr31dir), ("new_ubuntu2204", h22dir),
                           ("new_ubuntu2404", h24dir)):
            obj, raw, size = load(root / NAME)
            declared, calculated = seal(obj)
            entry = {"file": str(root / NAME), "rawSha256": raw, "bytes": size,
                     "canonicalSeal": declared, "recalculatedSeal": calculated,
                     "sealInternallyValid": declared == calculated,
                     "newF0ParentSeal": obj.get("method", {}).get(
                         "staticExportRoundingV2", {}).get("sourceF0RepreparedSeal"),
                     "specSha256": obj.get("specSha256"),
                     "checkingStatus": obj.get("origin"),
                     "nativeQualified": obj.get("nativeQualified")}
            receipt[name] = entry
            if not entry["sealInternallyValid"]:
                receipt["refusals"].append(name + ": invalid internal seal")
            specs[name] = obj
        if receipt["pr31_reviewed"]["rawSha256"] != EXPECTED_PR31_RAW or (
            receipt["pr31_reviewed"]["canonicalSeal"] != EXPECTED_PR31_SEAL
        ):
            receipt["refusals"].append("downloaded reviewed-PR31 artifact is not exact source")
        receipt["pr31_to_ubuntu2204"] = {
            "fieldComparison": differences(specs["pr31_reviewed"], specs["new_ubuntu2204"]),
            "numericalBreakdown": count_numeric_changes(
                specs["pr31_reviewed"], specs["new_ubuntu2204"]),
        }
        receipt["pr31_to_ubuntu2404"] = {
            "fieldComparison": differences(specs["pr31_reviewed"], specs["new_ubuntu2404"]),
            "numericalBreakdown": count_numeric_changes(
                specs["pr31_reviewed"], specs["new_ubuntu2404"]),
        }
        receipt["new_host22_to_host24"] = differences(
            specs["new_ubuntu2204"], specs["new_ubuntu2404"])
        if receipt["pr31_to_ubuntu2204"]["fieldComparison"]["differentLeaves"] or (
            receipt["pr31_to_ubuntu2404"]["fieldComparison"]["differentLeaves"]
        ):
            receipt["status"] = "CAPTURED_REVIEWED_V2_SEAL_DRIFT__CERTIFICATION_HOLD"
        else:
            receipt["status"] = "ALL_CHECKED_BUNDLES_MATCH__STILL_REQUIRES_INDEPENDENT_REVIEW"
    except Exception as e:
        receipt["refusals"].append(type(e).__name__ + ": " + str(e))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as f:
        f.write(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "status": receipt["status"],
        "pr31_to_22_differentLeaves": receipt.get("pr31_to_ubuntu2204", {}).get(
            "fieldComparison", {}).get("differentLeaves"),
        "pr31_to_24_differentLeaves": receipt.get("pr31_to_ubuntu2404", {}).get(
            "fieldComparison", {}).get("differentLeaves"),
        "new_host22_to_24_differentLeaves": receipt.get(
            "new_host22_to_host24", {}).get("differentLeaves"),
        "refusals": receipt["refusals"],
        "nativeExecuted": False,
    }, sort_keys=True))
    return 0 if not receipt["refusals"] else 3


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed-pr31", type=Path, required=True)
    parser.add_argument("--ubuntu2204", type=Path, required=True)
    parser.add_argument("--ubuntu2404", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    x = parser.parse_args()
    sys.exit(run(x.reviewed_pr31, x.ubuntu2204, x.ubuntu2404, x.output))
