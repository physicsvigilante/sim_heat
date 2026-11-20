"""H1-N9: cross-check N1's ORIGINAL full-grid *static* channels with generic N4.

OFFLINE checking evidence, NOT a new solver, certified 77-channel dynamics,
runner-consumable reference, authenticated expected seal, or native permission.
N1/N4 remain unchanged and separately provenance-limited. This module
reconstructs both historical N1 candidate traces without touching repository
or archived data, then checks all fourteen physical static fields at EVERY
saved sample against N4's separately implemented exact-source/RN-even proof.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from qualification.h1_n1 import certified_reference as n1
from qualification.h1_n4.static_physical import create_static_candidate

ROOT = Path(__file__).resolve().parents[2]
FACTS = ROOT / "qualification" / "h1_n1" / "reference-facts.json"
ORIGINAL_GRID_HASHES = {
    2400: "b13877c8d069a60928cf3b23ae007b1a10feb53151f00ffb65a57082a7fc10af",
    4800: "9ba71a1d2fccb39be071df0647793f6fb844737e2ac9c91bb143546ab8d26b40",
}
EXPECTED_LEGACY_FAILURES = [
    "T02.G", "T06.A", "T06.G", "T07.G",
    "T08.G", "T10.G", "T_Plug.C",
]
SCHEMA = "sim_heat.h1_n9.static_full_grid_crosscheck/1"
MAX_TRACE_BYTES = 20_000_000


class CrosscheckRefusal(ValueError):
    pass


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise CrosscheckRefusal("h1_n9: " + reason)


def check_static_samples(columns: dict, units: dict, static_candidate: dict, count: int) -> int:
    """Check the *actual candidate float64 bits*, every row, not only t=0.

    This is deliberately separately testable using tiny fixtures. The public
    audit below always constructs static_candidate afresh from pinned facts,
    and also SHA-checks complete original N1 trace bytes before calling here.
    """
    need(type(columns) is dict and type(units) is dict
         and type(static_candidate) is dict and type(count) is int and count > 0,
         "invalid sample/certificate container")
    need(static_candidate.get("schema") == "sim_heat.h1_n4.static_physical_candidate/1"
         and static_candidate.get("candidateValuesOnly") is True
         and static_candidate.get("independentlyCertifiedReference") is False
         and static_candidate.get("runtimeReady") is False
         and static_candidate.get("nativeExecuted") is False
         and static_candidate.get("nativeQualified") is False,
         "N4 static evidence status is not candidate-only")
    exports = static_candidate.get("exports")
    need(type(exports) is dict and len(exports) == 14
         and static_candidate.get("staticExports") == 14,
         "incomplete exact-source static proof")
    need(set(exports).issubset(columns) and set(exports).issubset(units),
         "missing static exported trace channels")
    checked = 0
    for name, proof in sorted(exports.items()):
        need(type(name) is str and type(proof) is dict
             and proof.get("physical100x") == "PASS_CANDIDATE_NOT_NATIVE_QUALIFIED",
             "invalid per-quantity physical 100x proof")
        expected = proof.get("binary64Hex")
        need(type(expected) is str and type(proof.get("unit")) is str,
             "missing physical centre/unit")
        try:
            target = float.fromhex(expected)
        except (ValueError, OverflowError) as exc:
            raise CrosscheckRefusal("h1_n9: invalid N4 static centre") from exc
        need(math.isfinite(target) and target > 0 and target.hex() == expected
             and units[name] == proof["unit"],
             "static unit or physical centre unsupported: " + name)
        series = columns[name]
        need(type(series) is list and len(series) == count,
             "incomplete full-grid static series: " + name)
        for index, value in enumerate(series):
            # A bool is NOT a numeric result. A numeric string is not a result.
            need(type(value) in (float, int) and math.isfinite(value)
                 and float(value).hex() == expected,
                 "N1/N4 static bit mismatch: " + name + " at sample " + str(index))
            checked += 1
    return checked


def verify_historical_grid(blob: bytes, grid: int, static_candidate: dict) -> dict:
    """Fail closed on non-original trace bytes, then inspect every static row."""
    need(type(blob) is bytes and 0 < len(blob) <= MAX_TRACE_BYTES
         and grid in ORIGINAL_GRID_HASHES,
         "unexpected trace bytes or grid")
    digest = sha256(blob).hexdigest()
    need(digest == ORIGINAL_GRID_HASHES[grid],
         "N1 trace differs from originally reviewed candidate: " + str(grid))
    try:
        trace = json.loads(blob.decode("utf-8"),
                           parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise CrosscheckRefusal("h1_n9: malformed trace") from exc
    need(type(trace) is dict and type(trace.get("report")) is dict
         and type(trace.get("columns")) is dict
         and type(trace.get("units")) is dict
         and type(trace.get("requests")) is dict
         and type(trace.get("integrals")) is dict
         and type(trace.get("grid")) is list,
         "missing full-grid report or data")
    report = trace["report"]
    need(report.get("schema") == "sim_heat.h1_n1.interval_reference_candidate/1"
         and report.get("sourceFactsSha256") == n1.FACTS_SHA256
         and report.get("refModelSha256") == n1.MODEL_SHA256
         and report.get("refStudySha256") == n1.STUDY_SHA256
         and report.get("gridIntervals") == grid
         and report.get("samples") == grid + 1
         and report.get("staticExports") == 14
         and report.get("allExports") == 77
         and report.get("requests") == 8
         and report.get("flowIntegrals") == 5
         and report.get("mathematicalIntervalSelfCheckPassed") is True,
         "N1 candidate source/grid/method contract drifted")
    for forbidden in ("independentlyCertifiedReference", "runtimeReady",
                      "nativeExecuted", "nativeQualified",
                      "originalCheckingCentresAdopted",
                      "historicalReferenceRegenerated"):
        need(report.get(forbidden) is False, "false evidence flag changed: " + forbidden)
    need(report.get("staticCheckingPhysical100xRefusalsRetained") ==
         EXPECTED_LEGACY_FAILURES, "original seven legacy failures were altered")
    need(len(trace["grid"]) == grid + 1
         and len(trace["columns"]) == 77
         and len(trace["requests"]) == 8
         and len(trace["integrals"]) == 5
         and set(trace["columns"]) == set(trace["units"]),
         "full-grid inventory absent or extra")
    for family in ("columns", "requests", "integrals"):
        for series in trace[family].values():
            need(type(series) is list and len(series) == grid+1
                 and all(type(x) in (float, int) and math.isfinite(x) for x in series),
                 "nonfinite or incomplete full-grid series")
    need(static_candidate["sourceFactsSha256"] == n1.FACTS_SHA256
         and static_candidate["originalModelSha256"] == n1.MODEL_SHA256
         and static_candidate["originalStudySha256"] == n1.STUDY_SHA256,
         "N4 original physical source differs from N1")
    checked = check_static_samples(trace["columns"], trace["units"], static_candidate, grid+1)
    return {"gridIntervals": grid, "samples": grid+1,
            "originalN1TraceSha256": digest, "N1Exports": 77,
            "N1PublicRequests": 8, "N1FlowIntegrals": 5,
            "N4StaticExports": 14, "individualStaticSamplesCompared": checked,
            "staticPhysical100xBitAgreement": True,
            "dynamicPhysical100xIndependentlyReverified": False}


def audit(*, out: Path | None = None) -> dict:
    """Regenerate N1 source-only traces, compute N4 independently; no binaries."""
    if out is not None:
        out = Path(out).resolve()
        need(not out.is_relative_to(ROOT) and not out.exists(),
             "output must be a NEW scratch directory outside the repository")
    raw = FACTS.read_bytes()
    need(sha256(raw).hexdigest() == n1.FACTS_SHA256,
         "original T1-T physical source-facts bytes changed")
    facts = n1.read_facts()
    physical = create_static_candidate(raw, expected_sha256=n1.FACTS_SHA256)
    results = []
    with TemporaryDirectory(prefix="simheat-h1-n9-") as scratch:
        for intervals in ORIGINAL_GRID_HASHES:
            folder = Path(scratch) / ("grid-" + str(intervals))
            generated = n1.certify(facts, intervals, output=folder)
            path = folder / ("N1_T1T_reference_grid" + str(intervals) + ".json")
            checked = verify_historical_grid(path.read_bytes(), intervals, physical)
            need(generated.get("fullTraceSha256") == checked["originalN1TraceSha256"],
                 "N1 emitted trace SHA differs from report")
            results.append(checked)
    receipt = {
        "schema": SCHEMA,
        "stage": "offline_only_static_N1_N4_crosscheck",
        "sourceFactsSha256": n1.FACTS_SHA256,
        "originalModelSha256": n1.MODEL_SHA256,
        "originalStudySha256": n1.STUDY_SHA256,
        "N4GenericStaticCandidateSchema": physical["schema"],
        "originalN1Grids": results,
        "staticExportCount": 14,
        "staticSampleComparisons": sum(r["individualStaticSamplesCompared"] for r in results),
        "sevenLegacyStaticCheckingCentresStillRefused": EXPECTED_LEGACY_FAILURES,
        "staticPhysicalAgreement": "PASS_CHECKING_CANDIDATES_ONLY",
        "independentFullGridPhysicalCertificate": False,
        "runtimeReady": False,
        "referenceBundleWritten": False,
        "referenceAccuracyCertified": False,
        "independentlyCertifiedReference": False,
        "externalOwnerApprovalVerified": False,
        "nativeExecuted": False,
        "nativeQualified": False,
        "historicalReferenceRegenerated": False,
        "limitation": "N1 self-bounded historical T1-T traces independently agree with N4 exact-source static centre bits at every sample; not a dynamic independent proof, new bundle, actual native result or runtime release"
    }
    if out is not None:
        out.mkdir(parents=True, exist_ok=False)
        (out / "n9-static-trace-crosscheck.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(out=args.out), sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
