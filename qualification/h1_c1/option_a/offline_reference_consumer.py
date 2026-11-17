"""Option A: approved-for-OFFLINE-CHECKING immutable H1-C1 V2 reference.

Records owner scope but NEVER grants native execution, plan preparation, or
permission to trust an unreviewed source revision. The original frozen H1 native
batch runner regenerates reference data and is NOT used here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from qualification.h1_c1.immutable_fixture import inspect_pr31_fixture
from qualification.h1_c1.immutable_fixture import option_a_binding_preflight

ROOT = Path(__file__).resolve().parents[3]
DECISION_PATH = Path("qualification/h1_c1/option_a/OWNER_ADOPTION.json")
# Git blob identity is a separately reviewed source literal, not the mutable
# decision file's own SHA claim. Protected owner signature/branch is NOT present.
EXPECTED_DECISION_GIT_BLOB_SHA1 = "0fc2e11e6e2bf618799ec5b314e2872f14236d8c"
EXPECTED_REVIEW_HUB_DECISION_GIT_BLOB_SHA1 = "599bfd42362c5d75224c82291b08b3f97310eb7c"
REVIEWED_STORAGE_SHA = "bf51e7721bca73720aa9b5f5f2de90defee821ec"
REVIEWED_STORAGE_TREE = "a4c1e1cdd247cb07990db672ad4c092e93933d83"
ANCHOR_REMOTE_REF = ("refs/remotes/origin/"
                     "qualification/h1-c1-f0-option-a-reviewed-reference-anchor")
EXPECTED_REFERENCE_SEAL = "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
EXPECTED_SOURCE_MODEL = "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
EXPECTED_STUDY = "b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"


class AdoptionRefusal(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise AdoptionRefusal(message)


def git_blob_sha1(contents: bytes) -> str:
    framed = b"blob " + str(len(contents)).encode("ascii") + b"\x00" + contents
    return hashlib.sha1(framed).hexdigest()


def git_rev_parse(root: Path, expression: str) -> str:
    """Read-only Git identity query, never modifies refs or performs build."""
    cmd = ["git", "-C", str(root), "rev-parse", "--verify", expression]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AdoptionRefusal("trusted reviewed Git reference unavailable") from exc
    need(proc.returncode == 0, "reviewed reference ref/tree missing")
    return proc.stdout.strip()


def verify_owner_record(root: Path) -> dict:
    path = root / DECISION_PATH
    need(path.is_file() and not path.is_symlink() and path.stat().st_size < 16_384,
         "owner-adoption decision missing/oversized/symlink")
    raw = path.read_bytes()
    need(git_blob_sha1(raw) == EXPECTED_DECISION_GIT_BLOB_SHA1,
         "entire owner-decision record differs from reviewed/pinned decision")
    data = json.loads(raw.decode("utf-8"))
    need(data.get("schema") == "sim_heat.h1_c1_option_a_owner_adoption/1"
         and data.get("decision") == "approved_for_checking_reference_only",
         "owner checking-reference decision/schema changed")
    need(data.get("centralOwnerDecision", {}).get("gitBlobSha1") ==
         EXPECTED_REVIEW_HUB_DECISION_GIT_BLOB_SHA1,
         "owner approval evidence no longer matches review hub")
    need(data.get("scope") == "H1_C1_MODAL_exact_archived_V2_reference_offline_checking",
         "owner checking scope changed")
    need(data.get("reviewedStorageCommit") == REVIEWED_STORAGE_SHA and
         data.get("reviewedStorageTree") == REVIEWED_STORAGE_TREE and
         data.get("sourceReferenceAnchorExpectedCommit") == REVIEWED_STORAGE_SHA,
         "approved historic source identity changed")
    need(data.get("exactCanonicalReferenceSeal") == EXPECTED_REFERENCE_SEAL
         and data.get("exactOriginalModelSha256") == EXPECTED_SOURCE_MODEL
         and data.get("exactEvaluatorModalStudySha256") == EXPECTED_STUDY,
         "approved reference/model/study changed")
    need(data.get("referenceUseApproved") is True and
         data.get("approvedUse") ==
         "offline_read_only_scientific_checking_of_exact_h1_c1_modal_study_only",
         "read-only approval not present")
    for prohibited in (
        "ownerApprovedNativeExecution", "authorizedToRunOpenModelica",
        "authorizedForProductionMerge", "nativeQualified", "nativeExecuted",
        "originalF0ReferenceStrict100xPassed",
        "v2GeneratorCrossHostBitwiseReproducible",
    ):
        need(data.get(prohibited) is False, "prohibited claim appears in owner record: "+prohibited)
    need(data.get("approvalProvenanceLimit") ==
         "Chat A records conversation instruction; not independently signed or authenticated as a GitHub owner release",
         "unapproved owner-attribution upgrade")
    return data


def verify_reference_anchor(root: Path) -> dict:
    actual = git_rev_parse(root, ANCHOR_REMOTE_REF)
    need(actual == REVIEWED_STORAGE_SHA,
         "reviewed checking-fixture source anchor has moved")
    tree = git_rev_parse(root, REVIEWED_STORAGE_SHA + "^{tree}")
    need(tree == REVIEWED_STORAGE_TREE, "reviewed checking-fixture tree differs")
    return {"referenceAnchor": ANCHOR_REMOTE_REF,
            "referenceAnchorCommit": actual,
            "referenceAnchorTree": tree,
            "anchorProtectedOrSigned": False}


def load_for_offline_checking(*, purpose: str = "offline_checking",
                              root: Path = ROOT) -> tuple[dict, dict]:
    """Return reviewed bundle for OFFLINE checking only; never a native grant.

    The returned bundle is inspectable public scientific data. A separate,
    independently reviewed native permission boundary is still required.
    """
    need(purpose == "offline_checking", "only offline reference checking was authorized")
    root = Path(root)
    record = verify_owner_record(root)
    anchor = verify_reference_anchor(root)
    binding = option_a_binding_preflight.audit(root=root)
    need(binding["status"] == "CANDIDATE_REFERENCE_STUDY_BINDING_PASS_NOT_OWNER_APPROVED"
         and binding["checkedReferenceSeal"] == EXPECTED_REFERENCE_SEAL,
         "original frozen checker failed to bind reviewed reference")
    need(binding["nativeExecuted"] is False and binding["authorizedForNative"] is False
         and binding["nativePlanCreated"] is False,
         "frozen checker preflight must remain offline and nonauthorizing")
    checked = inspect_pr31_fixture.load_candidate(inspect_only=True)
    bundle = checked["bundle"]
    need(bundle["seal"] == EXPECTED_REFERENCE_SEAL and
         bundle["nativeQualified"] is False and
         bundle["origin"] == "analytical_reference_only",
         "checked artifact seal/provenance drift")
    need(checked["manifest"]["approvedForNative"] is False,
         "archived integrity record cannot approve native use")
    receipt = {
        "schema": "sim_heat.c1_option_a_offline_reference_receipt/1",
        "status": "APPROVED_REFERENCE_DATA_OFFLINE_CHECKING_ONLY",
        "decision": record["decision"],
        "decisionGitBlobSha1": EXPECTED_DECISION_GIT_BLOB_SHA1,
        "ownerDirectionAuthenticatedOnGitHub": False,
        "reviewedStorageCommit": REVIEWED_STORAGE_SHA,
        "referenceAnchor": anchor,
        "archivedReferenceRawSha256": checked["rawSha256"],
        "referenceSeal": EXPECTED_REFERENCE_SEAL,
        "modelSha256": EXPECTED_SOURCE_MODEL,
        "studySha256": EXPECTED_STUDY,
        "matchedExports": binding["matchedMandatoryExports"],
        "timeGridSamples": binding["timeGridSamples"],
        "flowIntegralHistories": binding["flowIntegralHistories"],
        "publicRequests": binding["publicRequests"],
        "scientificRegenBitwiseCertified": False,
        "originalF0Strict100xResult": "FAILED_HISTORIC_80X",
        "nativeQualified": False,
        "nativeExecuted": False,
        "nativeAllowed": False,
        "nativePlanApproved": False,
        "productionMergeAllowed": False,
        "requiresIndependentCurrentConsumerReview": True,
        "releaseTrustRootComplete": False,
        "limitations": [
            "This is scientific reference data access, not an owner-authenticated native permission token",
            "The GitHub reference branch is ordinary/unprotected and not a signed durable release",
            "No trusted standalone native adapter or cross-run launch reservation exists",
            "No OpenModelica version/build/launch or observed C1 output was produced",
        ],
    }
    return bundle, receipt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("check-reference-only",))
    parsed = p.parse_args(argv)
    try:
        _, receipt = load_for_offline_checking()
    except Exception as exc:
        receipt = {
            "schema": "sim_heat.c1_option_a_offline_reference_receipt/1",
            "status": "REFUSED_UNTRUSTED_OR_NONOFFLINE_REFERENCE",
            "reason": type(exc).__name__ + ": " + str(exc),
            "nativeAllowed": False, "nativeQualified": False,
            "nativeExecuted": False, "nativePlanApproved": False,
        }
        print(json.dumps(receipt, sort_keys=True, indent=2))
        return 3
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
