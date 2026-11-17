"""H1-C1 F-02: offline *design* preflight of a disabled native-control plan.

This deliberately cannot prepare/launch OpenModelica, create a runnable model,
create an executable plan for frozen native_batch/1, or authorize a one-shot run.
It validates how the previously owner-adopted reference would be bound to a
future separately reviewed/approved native plan, without performing that action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from h1.study import load_study
from qualification.h1_c1.immutable_fixture import option_a_binding_preflight
from qualification.h1_c1.option_a import offline_reference_consumer

ROOT = Path(__file__).resolve().parents[3]
PLAN = Path("qualification/h1_c1/f02/F02_CONTROL_PLAN_PREVIEW.json")
PLAN_GIT_BLOB = "2c01301d1c493f33c9eb4bfb9778190adbb6d0bc"
STUDY = Path("h1/cases/H1_C1_MODAL/study.json")
MODEL_SHA = "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
STUDY_SHA = "b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"
REF_SHA = "0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368"
REF_SEAL = "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
REF_XZ_SHA = "fc5a7df5928c3fb8aef2ba4af516dfbd32b42c0450ebef1051ad4fd7efebd17f"
REF_MANIFEST_SHA = "50467b138ed64cdb908f2c763bc777e6babf0bb04a0711568acc559112e66f84"
HISTORICAL_PLAN_SHA = "f46b2621b38427ffc098d16d91695a134b7dc4d7f913021be625ee74b8a9319a"


class PreviewRefusal(ValueError):
    pass


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise PreviewRefusal(reason)


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def load_preview(path: Path = ROOT / PLAN) -> tuple[dict, str]:
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size < 16_384,
         "preview file missing/symlink/oversized")
    raw = path.read_bytes()
    need(git_blob_sha1(raw) == PLAN_GIT_BLOB,
         "preview differs from original pinned non-executable plan")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError) as exc:
        raise PreviewRefusal("invalid prospective plan JSON") from exc
    return doc, hashlib.sha256(raw).hexdigest()


def _unique(items: list[tuple[str, object]]) -> dict:
    obj = {}
    for k, v in items:
        if k in obj:
            raise ValueError("duplicate preview plan key")
        obj[k] = v
    return obj


def validate_preview(plan: dict) -> None:
    """Semantic gate IN ADDITION to the whole-file Git hash and source review."""
    need(set(plan) == {
        "schema", "status", "ownerDecisionScope", "caseId", "originalFrozenSourceCommit",
        "approvedOfflineConsumerSourceCommit", "firstModelSha256", "firstStudySha256",
        "modalStudyPath", "modalStudySha256", "modelPath",
        "originalUnlaunchedNativePlanSha256", "frozenCheckerAndSourcePinsCount",
        "checkingReference", "plannedStudySettings", "expectedToolchain",
        "requiredNotYetEstablished", "launchPolicy", "historicalLimitations", "purpose"
    }, "prospective plan fields changed")
    need(plan["schema"] == "sim_heat.h1_c1_f02_control_preview/1"
         and plan["schema"] != "sim_heat.native_batch/1"
         and plan["status"] == "DESIGN_ONLY_UNREVIEWED_NO_NATIVE_EXECUTION",
         "wrong/non-disabled plan schema/status")
    need(plan["ownerDecisionScope"] == "option_a_offline_reference_checking_only",
         "owner authorization inflated")
    need(plan["caseId"] == "H1_C1_MODAL"
         and plan["approvedOfflineConsumerSourceCommit"] ==
         "f7c69954490c8dcd48d152906e8e2a6d5699481d"
         and plan["originalFrozenSourceCommit"] ==
         "dd8c9432abe97563414bb3ed809e61e673473812",
         "wrong source/case lineage")
    need(plan["modelPath"] == "h1/cases/H1_C1_MODAL/model.mo"
         and plan["modalStudyPath"] == STUDY.as_posix()
         and plan["firstModelSha256"] == MODEL_SHA
         and plan["modalStudySha256"] == STUDY_SHA
         and plan["firstStudySha256"] ==
         "b235d4242728c44dd994e09db3ffd92d197398dde3fe6c8f006a801981997fdc"
         and plan["originalUnlaunchedNativePlanSha256"] == HISTORICAL_PLAN_SHA
         and plan["frozenCheckerAndSourcePinsCount"] == 23,
         "original model/study/plan identity changed")
    ref = plan["checkingReference"]
    need(set(ref) == {
        "source", "archivedRawSha256", "archivedCanonicalSeal", "archivedCompressedSha256",
        "originalWholeManifestSha256", "regenerationPermitted", "sourceAnchorCommit"
    } and ref["source"] == "one_immutable_saved_PR31_V2_bundle" and
         ref["archivedRawSha256"] == REF_SHA and
         ref["archivedCanonicalSeal"] == REF_SEAL and
         ref["archivedCompressedSha256"] == REF_XZ_SHA and
         ref["originalWholeManifestSha256"] == REF_MANIFEST_SHA and
         ref["sourceAnchorCommit"] == "bf51e7721bca73720aa9b5f5f2de90defee821ec" and
         ref["regenerationPermitted"] is False, "unauthorized reference or regeneration")
    settings = plan["plannedStudySettings"]
    # Explicit types matter: Python considers True == 1 and 1.0 == 1.
    # This predicate will also be reused by future OFFLINE staging checks.
    need(type(settings.get("startTime")) is int and
         type(settings.get("stopTime")) is float and
         type(settings.get("intervals")) is int and
         type(settings.get("tolerance")) is float and
         type(settings.get("solver")) is str, "wrong modal setting JSON scalar type")
    need(settings == {
        "startTime": 0, "stopTime": 1810.609003248995, "intervals": 4000,
        "solver": "dassl", "tolerance": 1e-8
    }, "modal grid/solver proposal differs from pinned study")
    need(plan["expectedToolchain"] == {
        "openModelicaVersion": "OpenModelica 1.27.0",
        "modelicaStandardLibraryVersion": "4.0.0",
        "pythonVersion": "3.13.5", "numpyVersion": "2.3.5", "scipyVersion": "1.17.0"
    }, "unreviewed prospective toolchain")
    missing = plan["requiredNotYetEstablished"]
    need(set(missing) == {
        "ownerSignedOrExternallyAuthenticatedReleaseRef", "protectionAndBackupAttestation",
        "approvedNativeSourceHead", "nativeRunnerArtifactSha256",
        "sourceCommitAndPlanSha256", "observedCompilerExecutableSha256",
        "observedMSLSourceTreeSha256", "independentRunnerReview",
        "durableAcrossRunReservation", "hostIdentityAndImage", "ownerNativeLaunchAuthorization"
    } and all(x is None for x in missing.values()), "runtime authority incorrectly claimed present")
    policy = plan["launchPolicy"]
    need(type(policy.get("maxLaunchesAfterSeparateApproval")) is int,
         "proposed one-shot budget must be JSON integer, not bool/float")
    need(set(policy) == {
        "nativeAllowed", "createExecutable", "queryCompilerVersion", "buildModel",
        "launchModel", "retryAllowed", "maxLaunchesAfterSeparateApproval",
        "allowSimulationEvidenceClaim", "allowAutomaticReferenceRegeneration"
    } and policy["maxLaunchesAfterSeparateApproval"] == 1 and all(
        policy[k] is False for k in policy if k != "maxLaunchesAfterSeparateApproval"
    ), "preview may have become executable or relaxed one-shot/negative guards")
    historical = plan["historicalLimitations"]
    need(historical == {
        "originalFrozenF0Static100xReferencePassed": False,
        "pr32ReviewedV2BitwiseRegenerationPassed": False,
        "firstAttemptAuthoringEvidenceUnchanged": True,
        "nativeObserved": False
    }, "frozen original FAIL/native status changed")
    need(plan["purpose"] ==
         "An offline-only design preview that refuses runtime; cannot be supplied to original native_batch/1 runner",
         "misleading preview purpose")


def audit(*, root: Path = ROOT, plan_path: Path = ROOT / PLAN) -> dict:
    plan, digest = load_preview(plan_path)
    validate_preview(plan)
    binding = option_a_binding_preflight.audit(root=root)
    need(binding["status"] == "CANDIDATE_REFERENCE_STUDY_BINDING_PASS_NOT_OWNER_APPROVED",
         "frozen source-to-reference audit failed")
    bundle, adopted = offline_reference_consumer.load_for_offline_checking(root=root)
    need(adopted["status"] == "APPROVED_REFERENCE_DATA_OFFLINE_CHECKING_ONLY"
         and adopted["referenceSeal"] == REF_SEAL
         and adopted["archivedReferenceRawSha256"] == REF_SHA
         and not adopted["nativeAllowed"]
         and not adopted["nativePlanApproved"]
         and not adopted["nativeExecuted"],
         "no exact offline-only reference authority")
    study = load_study(root / STUDY, root / "h1/cases")
    analysis = study.data["analysis"]
    need(study.sha256 == STUDY_SHA and study.model_sha256 == MODEL_SHA,
         "study/source identity drift")
    need(analysis == plan["plannedStudySettings"]
         and tuple(study.grid) == tuple(bundle["grid"]),
         "modal study/grid differs from frozen checking data")
    need(len(study.data["requests"]) == 9
         and len(bundle["columns"]) == 37
         and len(bundle["grid"]) == 4001
         and len(bundle["flowIntegrals"]) == 4,
         "preview output inventory mismatch")
    return {
        "schema": "sim_heat.h1_c1_f02_control_preflight/1",
        "status": "F02_CONTROL_DESIGN_PREFLIGHT_PASS_NONEXECUTABLE",
        "previewGitBlobSha1": PLAN_GIT_BLOB,
        "previewSha256": digest,
        "reviewedReferenceRawSha256": REF_SHA,
        "reviewedReferenceSeal": REF_SEAL,
        "sourceIdentityPinsVerified": binding["sourceHistory"]["sourcePinsVerified"],
        "publicRequests": len(study.data["requests"]),
        "exportChannels": len(bundle["columns"]),
        "timeGridSamples": len(bundle["grid"]),
        "integralHistories": len(bundle["flowIntegrals"]),
        "compilerObserved": False,
        "mslObserved": False,
        "oneShotReservationAllocated": False,
        "trustedReleaseRootComplete": False,
        "nativePlanApproved": False,
        "ownerNativeLaunchApproved": False,
        "nativeExecuted": False,
        "nativeQualified": False,
        "referenceRegenerated": False,
        "originalF0ReferencePassed100x": False,
        "pr32CrossHostBitwiseRegenerationPassed": False,
        "limits": [
            "Plan schema is deliberately incompatible with frozen native_batch/1",
            "No actual native adapter/runner/OMC is provided by this preflight",
            "No trusted host, protected owner-signed release or reservation exists",
            "No runtime work or native evidence may be inferred from this design check"
        ]
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["design-preview-only"])
    args = parser.parse_args(argv)
    try:
        result = audit()
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema": "sim_heat.h1_c1_f02_control_preflight/1",
            "status": "REFUSED_F02_CONTROL_PREVIEW",
            "reason": type(exc).__name__ + ": " + str(exc),
            "nativePlanApproved": False, "nativeExecuted": False,
            "nativeQualified": False, "ownerNativeLaunchApproved": False
        }, sort_keys=True))
        return 3


if __name__ == "__main__":
    sys.exit(main())
