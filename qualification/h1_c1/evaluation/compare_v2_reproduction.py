#!/usr/bin/env python3
"""Fail-closed V2 reference reproducibility comparator (never runs Modelica).

Compare actual separately prepared *full* V2 bundles, not their summary flags.
Retain field-level differences and a receipt before a refusal. A PASS is specific
to the observed processes/hosts and never authorizes native execution.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

OLD_SEAL = "d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b"
EXPECTED_V2_SEAL = "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
SPEC_SHA = "3afcfddb28ddbf9f9266548504bb43fc2f5420e90d10cb4acbf87334c6e3ab4c"
PR31_HEAD = "d857c8e807612026ecdf624277b4ace3977fefe3"
EXPECTED_VERSIONS = {
    "python": "3.13.5", "numpyVersion": "2.3.5",
    "scipyVersion": "1.17.0", "mpmathVersion": "1.3.0",
    "threadpoolctlVersion": "3.6.0",
}
BUNDLE = "C1_REFERENCE_V2_BUNDLE.json"
REPORT = "C1_REFERENCE_V2_REPORT.json"


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_json(value):
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                allow_nan=False).encode("utf-8"))


def load(path, maximum=12_000_000):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > maximum:
        raise ValueError("missing/oversized/symlink file: " + str(path))
    data = path.read_bytes()
    return json.loads(data.decode("utf-8")), sha_bytes(data), len(data)


def seal(value):
    if not isinstance(value, dict) or "seal" not in value:
        raise ValueError("missing canonical seal")
    payload = dict(value)
    declared = payload.pop("seal")
    return declared, sha_json(payload)


def differences(a, b, max_examples=60):
    """Bound examples but count all differing leaves, including dynamic arrays."""
    result = {"differentLeaves": 0, "examples": [], "differentTopLevelFields": []}
    top = set()

    def walk(x, y, path):
        if type(x) is not type(y):
            change(path, x, y)
        elif isinstance(x, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x or k not in y:
                    change(path + "." + k, x.get(k, "<missing>"), y.get(k, "<missing>"))
                else:
                    walk(x[k], y[k], path + "." + k)
        elif isinstance(x, list):
            if len(x) != len(y):
                change(path + ".length", len(x), len(y))
            for i in range(min(len(x), len(y))):
                walk(x[i], y[i], path + "[" + str(i) + "]")
        elif x != y:
            change(path, x, y)

    def change(path, x, y):
        result["differentLeaves"] += 1
        top.add(path.split(".", 2)[1].split("[", 1)[0] if "." in path else path)
        if len(result["examples"]) < max_examples:
            result["examples"].append({"path": path, "left": x, "right": y})

    walk(a, b, "$")
    result["differentTopLevelFields"] = sorted(top)
    result["truncatedExamples"] = result["differentLeaves"] > len(result["examples"])
    return result


def check_bundle(bundle, report):
    errors = []
    if bundle.get("schema") != "sim_heat.reference_bundle/2":
        errors.append("bad reference schema")
    if bundle.get("nativeQualified") is not False or bundle.get("origin") != "analytical_reference_only":
        errors.append("improper reference/native provenance")
    got_seal, calculated = seal(bundle)
    if got_seal != calculated:
        errors.append("declared canonical seal does not match saved bundle")
    if got_seal != EXPECTED_V2_SEAL or got_seal == OLD_SEAL:
        errors.append("V2 seal not equal to original independently reviewed candidate")
    if bundle.get("specSha256") != SPEC_SHA or sha_json(bundle.get("spec")) != SPEC_SHA:
        errors.append("physical spec identity mismatch")
    columns = bundle.get("columns", {})
    integrations = bundle.get("flowIntegrals", {})
    if len(bundle.get("grid", [])) != 4001 or len(columns) != 37 or len(integrations) != 4:
        errors.append("wrong output/grid/integral sizes")
    if set(columns) != set(bundle.get("allowances", {})) or set(columns) != set(bundle.get("units", {})):
        errors.append("column allowance/unit registry mismatch")
    for name, arr in columns.items():
        if len(arr) != 4001 or not all(type(v) in (int, float) and math.isfinite(v) for v in arr):
            errors.append("invalid column " + name)
    for name, arr in integrations.items():
        if len(arr) != 4001 or not all(type(v) in (int, float) and math.isfinite(v) for v in arr):
            errors.append("invalid integral " + name)
    if any(bundle.get("grid", [])[i] >= bundle["grid"][i+1] for i in range(max(0, len(bundle.get("grid", []))-1))):
        errors.append("unsorted time grid")
    if columns.get("hotLead.G") != [float(Decimal("0.45"))] * 4001:
        errors.append("V2 static conductance not correctly rounded")
    else:
        error = abs(Fraction.from_float(columns["hotLead.G"][0]) - Fraction(9, 20))
        allowance = Fraction.from_float(bundle["allowances"]["hotLead.G"])
        if error > allowance / 100 or (allowance / error) != 320:
            errors.append("V2 hotLead.G 100x budget failed")
    if report.get("nativeExecuted") is not False or report.get("nativeQualified") is not False:
        errors.append("native qualification incorrectly claimed")
    if report.get("status") != "offline_checking_reference_prospective_not_native":
        errors.append("report is not a successful offline checking candidate")
    if report.get("newV2BundleSeal") != got_seal or report.get("repeatEqual") is not True:
        errors.append("reported V2 seal/repeat inconsistent")
    if report.get("originalF0BundleSeal") != OLD_SEAL:
        errors.append("original F0 seal not preserved")
    v = report.get("referenceVerification", {})
    if v.get("all37ColumnsStrict100xPass") is not True or v.get("assessedScalarValues") != 148037:
        errors.append("missing 37x4001 strict 100x evidence")
    ratio = v.get("maxReferenceErrorFractionOfNativeAllowance")
    if type(ratio) not in (int, float) or not math.isfinite(ratio) or ratio > 0.01:
        errors.append("strict 100x ratio not established")
    if len(v.get("maximumFlowIntegralErrorJ", {})) != 4:
        errors.append("not all four integral reference histories checked")
    return errors


def runtime_receipt(path, os_expected=None):
    root = path.parent
    provenance, sha, length = load(root / "runtime.json", 200_000)
    errors = []
    if provenance.get("stage") != "offline_checking_only_no_native":
        errors.append("runtime native-claim invalid")
    for k, v in EXPECTED_VERSIONS.items():
        if provenance.get(k) != v:
            errors.append("mismatched " + k)
    if not provenance.get("actualLoadedThreadpoolLibraries"):
        errors.append("missing loaded BLAS/threadpool evidence")
    if not any(x.get("user_api") == "blas" for x in provenance.get("actualLoadedThreadpoolLibraries", [])):
        errors.append("no actual BLAS library attested")
    if not provenance.get("numpyShowRuntimeStdout") or not provenance.get("scipyBuildConfigStdout"):
        errors.append("missing numerical build/runtime diagnostics")
    if len(provenance.get("installedWheels", [])) != 4:
        errors.append("missing installed package wheel tags/RECORD identities")
    manifest = root / "wheels.sha256"
    if not manifest.is_file():
        errors.append("missing hashed downloaded-and-installed wheel manifest")
        wheels_sha = None
    else:
        w = manifest.read_bytes()
        wheels_sha = sha_bytes(w)
        if len(w.decode("utf-8").splitlines()) != 4:
            errors.append("unexpected number of installed wheel files")
    if os_expected and provenance.get("osRelease", {}).get("VERSION_ID") != os_expected:
        errors.append("unexpected OS image version")
    return {
        "runtime": provenance,
        "rawSha256": sha,
        "bytes": length,
        "installedWheelArchiveManifestSha256": wheels_sha,
        "errors": errors,
    }


def mutation_controls(bundle):
    """Must reject static/dynamic/integral numerical tampering AND allowance metadata."""
    if not __debug__:
        raise RuntimeError("optimized python invalidates reference verifier")
    from qualification.h1_c1.evaluation.prepare_reference_v2 import independent_validate
    from h1 import reference
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    spec = reference.read_reference(
        root / "qualification/h1_c1/evaluation/C1_FIRST_CHECKING_REFERENCE.json")
    probes = [
        ("static_lower_neighbor", "columns", "hotLead.G", 0, 0.44999999999999996),
        ("dynamic_temperature", "columns", "leftBuffer.T", 127, None),
        ("energy_integral", "flowIntegrals", "leftBuffer.Q_in", 127, None),
        ("allowance_widening", "allowances", "hotLead.G", None, None),
    ]
    results = {}
    for label, section, key, idx, replacement in probes:
        changed = deepcopy(bundle)
        if label == "allowance_widening":
            changed[section][key] *= 1.5
        elif replacement is None:
            changed[section][key][idx] += 0.01
        else:
            changed[section][key][idx] = replacement
        sealed, recomputed = seal(changed)
        if sealed == recomputed:
            raise AssertionError("tamper failed seal detection: " + label)
        numerical_rejected = None
        if label != "allowance_widening":
            try:
                independent_validate(changed, spec)
            except (AssertionError, ValueError):
                numerical_rejected = True
            else:
                numerical_rejected = False
                raise AssertionError("high-precision strict reference guard did not reject: " + label)
        results[label] = {"invalidatesCanonicalSeal": True,
                          "rejectedByHighPrecisionCheck": numerical_rejected}
    return results


def compare(left, right, mode, out):
    receipt = {
        "schema": "sim_heat.c1_v2_reference_reproduction/1",
        "mode": mode,
        "status": "REFUSED_INCOMPLETE",
        "nativeExecuted": False,
        "nativeQualified": False,
        "historicalFrozenF0ReferenceChanged": False,
        "approvedNativePlanCreated": False,
        "expectedPr31SourceHead": PR31_HEAD,
        "expectedV2Seal": EXPECTED_V2_SEAL,
        "originalArchivedSeal": OLD_SEAL,
        "inputs": {"left": str(left), "right": str(right)},
        "refusals": [],
    }
    try:
        bundles = []
        reports = []
        for label, directory in (("left", left), ("right", right)):
            bundle, rawsha, size = load(directory / BUNDLE)
            report, report_sha, report_size = load(directory / REPORT, 500_000)
            bundles.append(bundle)
            reports.append(report)
            receipt[label] = {
                "bundleRawSha256": rawsha,
                "bundleBytes": size,
                "bundleSeal": bundle.get("seal"),
                "reportRawSha256": report_sha,
                "reportBytes": report_size,
                "bundleCheckingErrors": check_bundle(bundle, report)
            }
            receipt["refusals"].extend(label + ": " + item
                                      for item in receipt[label]["bundleCheckingErrors"])
        receipt["fullBundleFieldComparison"] = differences(bundles[0], bundles[1])
        receipt["bundleRawBytesEqual"] = receipt["left"]["bundleRawSha256"] == receipt["right"]["bundleRawSha256"]
        receipt["bundleCanonicalSealsEqual"] = bundles[0]["seal"] == bundles[1]["seal"]
        if not receipt["bundleRawBytesEqual"] or receipt["fullBundleFieldComparison"]["differentLeaves"] != 0:
            receipt["refusals"].append("full reference bundles differ; no certification")
        for label, dir in (("left", left), ("right", right)):
            runtime = runtime_receipt(dir, os_expected=None)
            # Records are separate for each host even when bundles match.
            receipt[label]["runtimeRawSha256"] = runtime["rawSha256"]
            receipt[label]["runtimeErrors"] = runtime["errors"]
            receipt[label]["runtimeSummary"] = {
                "osRelease": runtime["runtime"]["osRelease"],
                "imageVersion": runtime["runtime"]["runner"].get("ImageVersion"),
                "blas": runtime["runtime"]["actualLoadedThreadpoolLibraries"],
                "wheelArchiveManifestSha256": runtime["installedWheelArchiveManifestSha256"],
            }
            receipt["refusals"].extend(label + ": " + x for x in runtime["errors"])
        if mode == "cross-host":
            a = receipt["left"]["runtimeSummary"]["osRelease"]
            b = receipt["right"]["runtimeSummary"]["osRelease"]
            if a.get("VERSION_ID") != "22.04" or b.get("VERSION_ID") != "24.04":
                receipt["refusals"].append("missing distinct Ubuntu 22.04 and 24.04 hosted environments")
        elif mode == "same-host":
            if left.parent != right.parent:
                receipt["refusals"].append("same-host comparison directories not in same evidence root")
            receipt["mutationControls"] = mutation_controls(bundles[0])
        else:
            receipt["refusals"].append("unknown comparison mode")
    except Exception as exc:
        receipt["refusals"].append(type(exc).__name__ + ": " + str(exc))
    if not receipt["refusals"]:
        receipt["status"] = ("PASS_TWO_CLEAN_PROCESSES_ON_ONE_HOST" if mode == "same-host"
                            else "PASS_TESTED_TWO_DISTINCT_HOST_ENVIRONMENTS")
    else:
        receipt["status"] = "REFUSED_REPRODUCIBILITY_OR_PROVENANCE"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as f:
        f.write(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "refusals": receipt["refusals"],
                      "fullFieldDiffCount": receipt.get("fullBundleFieldComparison", {}).get("differentLeaves"),
                      "nativeExecuted": False}, sort_keys=True))
    return 0 if not receipt["refusals"] else 3


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("same-host", "cross-host"), required=True)
    x = parser.parse_args()
    sys.exit(compare(x.left, x.right, x.mode, x.output))
