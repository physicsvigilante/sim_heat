"""Proposed Option A reference-to-study binding audit; NO reference consumption approval.

The original frozen native runner regenerates checking references and must NOT be
called to "prepare" this V2 bundle. This audit only verifies the original
independently-reviewed archived bytes against the original frozen H1 study
contract and source pins. It never writes a reference, constructs a native plan,
runs OpenModelica, or grants owner/host/execution approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from h1 import reference
from h1.study import load_study
from h1.verification import _verify_bundle
from qualification.h1_c1.immutable_fixture import inspect_pr31_fixture as fixture

ROOT = Path(__file__).resolve().parents[3]
FROZEN_ORIGINAL_F0 = "dd8c9432abe97563414bb3ed809e61e673473812"
REVIEWED_ARCHIVE_HEAD = "bf51e7721bca73720aa9b5f5f2de90defee821ec"
REVIEWED_ARCHIVE_TREE = "a4c1e1cdd247cb07990db672ad4c092e93933d83"
ORIGINAL_NATIVE_PLAN_SHA = "f46b2621b38427ffc098d16d91695a134b7dc4d7f913021be625ee74b8a9319a"
ORIGINAL_MODEL_SHA = "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
ORIGINAL_FIRST_STUDY_SHA = "b235d4242728c44dd994e09db3ffd92d197398dde3fe6c8f006a801981997fdc"
MODAL_STUDY_SHA = "b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"
MODEL = "h1/cases/H1_C1_MODAL/model.mo"
STUDY = "h1/cases/H1_C1_MODAL/study.json"
FIRST_MODEL = "h1/cases/H1_C1_FIRST/model.mo"
FIRST_STUDY = "h1/cases/H1_C1_FIRST/study.json"
PLAN = "qualification/h1_c1/evaluation/C1_PRIMARY_NATIVE_PLAN_NOT_LAUNCHED.json"
PHYSICAL_SPEC = "qualification/h1_c1/evaluation/C1_FIRST_CHECKING_REFERENCE.json"
EXPECTED_SPEC_SHA = "1b4b497d7427deae9e83fd712fbe9119e0c8e6599212d7762c828eca10b594c9"
EXPECTED_SEAL = "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
SOURCE_PIN_COUNT = 23


class BindingRefusal(ValueError):
    pass


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise BindingRefusal(reason)


def sha(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(), "missing or symlink source: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity(root: Path) -> dict:
    """Verify frozen unlaunched plan input hashes without EVER executing it."""
    need(sha(root / PLAN) == ORIGINAL_NATIVE_PLAN_SHA, "unlaunched historical plan changed")
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    need(plan.get("schema") == "sim_heat.native_batch/1", "wrong historical source-pin schema")
    need(plan.get("branch") == "experiment/h1-c1-f0-native-primary-once",
         "original nonexecuted plan branch changed")
    need(plan.get("cases") == [{
        "study": STUDY, "reference": PHYSICAL_SPEC
    }], "original unlaunched plan binding changed")
    pins = plan.get("pins")
    need(isinstance(pins, dict) and len(pins) == SOURCE_PIN_COUNT,
         "missing fixed source identity pins")
    for rel, expected in pins.items():
        need(isinstance(rel, str) and isinstance(expected, str) and
             ".." not in Path(rel).parts and not Path(rel).is_absolute(),
             "invalid source pin path")
        need(sha(root / rel) == expected, "frozen source identity drift: " + rel)
    need(sha(root / FIRST_MODEL) == ORIGINAL_MODEL_SHA, "first physical model changed")
    need(sha(root / FIRST_STUDY) == ORIGINAL_FIRST_STUDY_SHA, "original first study changed")
    need(sha(root / MODEL) == ORIGINAL_MODEL_SHA, "assisted model no longer original")
    need(sha(root / STUDY) == MODAL_STUDY_SHA, "assisted study identity changed")
    need(sha(root / PHYSICAL_SPEC) == EXPECTED_SPEC_SHA, "physical checking spec changed")
    return {"originalUnlaunchedPlanSha256": ORIGINAL_NATIVE_PLAN_SHA,
            "sourcePinsVerified": len(pins),
            "originalModelSha256": ORIGINAL_MODEL_SHA,
            "originalFirstStudySha256": ORIGINAL_FIRST_STUDY_SHA,
            "assistedStudySha256": MODAL_STUDY_SHA,
            "originalPhysicalSpecSha256": EXPECTED_SPEC_SHA}


def audit(*, root: Path = ROOT, fixture_root: Path | None = None) -> dict:
    """Inspect only: never emits a materialized bundle or permitted native plan."""
    source = source_identity(root)
    archived = fixture.load_candidate(fixture_root, inspect_only=True)
    bundle = archived["bundle"]
    study = load_study(root / STUDY, root / "h1/cases")
    need(study.request_report["admitted"] is True, "modal study not admitted")
    need(len(study.request_report["requests"]) == 9, "not the frozen nine public requests")
    need(study.sha256 == MODAL_STUDY_SHA and study.model_sha256 == ORIGINAL_MODEL_SHA,
         "study/model differs from pinned original")
    need(bundle["seal"] == EXPECTED_SEAL, "V2 reference seal not reviewed")
    spec, grid, mandatory = _verify_bundle(study, bundle, EXPECTED_SEAL)
    need(spec == bundle["spec"], "binding changed original reference spec")
    need(len(grid) == 4001 and len(mandatory) == 37, "wrong checker-required output set")
    need(set(mandatory) == set(bundle["columns"]), "missing or extra checking outputs")
    need(set(bundle["units"]) == set(mandatory)
         and set(bundle["owners"]) == set(mandatory)
         and set(bundle["allowances"]) == set(mandatory), "missing reference metadata")
    need(len(bundle["flowIntegrals"]) == 4 and
         all(len(v) == 4001 for v in bundle["flowIntegrals"].values()),
         "missing all four checked energy-integral histories")
    need(bundle["origin"] == "analytical_reference_only"
         and bundle["nativeQualified"] is False, "checker bundle misclassified")
    need(archived["manifest"]["approvedForNative"] is False, "archive has forbidden approval claim")

    return {
        "schema": "sim_heat.c1_v2_owner_option_a_preflight/1",
        "status": "CANDIDATE_REFERENCE_STUDY_BINDING_PASS_NOT_OWNER_APPROVED",
        "sourceHistory": source,
        "reviewedArchiveSourceCommit": REVIEWED_ARCHIVE_HEAD,
        "reviewedArchiveSourceTree": REVIEWED_ARCHIVE_TREE,
        "checkedArchiveCompressedSha256": archived["compressedSha256"],
        "checkedArchiveRawSha256": archived["rawSha256"],
        "checkedReferenceSeal": EXPECTED_SEAL,
        "checkingMode": "offline_read_only",
        "matchedMandatoryExports": len(mandatory),
        "timeGridSamples": len(grid),
        "flowIntegralHistories": len(bundle["flowIntegrals"]),
        "publicRequests": len(study.request_report["requests"]),
        "crossHostBitwiseRegenerationPassed": False,
        "originalFrozenF0Reference100xPass": False,
        "nativeQualified": False,
        "nativeExecuted": False,
        "ownerApprovedOptionA": False,
        "authorizedForNative": False,
        "nativePlanCreated": False,
        "limitations": [
            "No owner-signed trust root or protected/durable reviewed Git ref",
            "Current code/branch is not a certified reference consumer",
            "Frozen H1 native runner prepares references afresh and is NOT invoked",
            "Original failed F0 80x reference and PR32 failed bitwise reproduction preserved",
            "No one-shot host/plan authorization, OpenModelica or native observations",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit-only",))
    args = parser.parse_args(argv)
    try:
        report = audit()
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (BindingRefusal, Exception) as exc:
        print(json.dumps({
            "schema": "sim_heat.c1_v2_owner_option_a_preflight/1",
            "status": "REFUSED_CANDIDATE_BINDING_OR_ORIGINAL_SOURCE",
            "reason": type(exc).__name__ + ": " + str(exc),
            "ownerApprovedOptionA": False,
            "nativeQualified": False,
            "nativeExecuted": False,
            "authorizedForNative": False,
            "nativePlanCreated": False,
        }, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
