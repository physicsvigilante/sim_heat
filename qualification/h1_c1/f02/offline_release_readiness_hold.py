"""Read-only H1-C1 F02 PRE-NATIVE READINESS HOLD audit (not a native gate).

Asserts the *absence* of 11 owner/release/host/adapter/store/native gates,
checks the original approved scientific source through reviewed offline
preflights, and produces an explicit blocked receipt. This module has no
mode/API/argument that could approve a native operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from qualification.h1_c1.f02 import offline_control_preflight as f02
from qualification.h1_c1.f02 import offline_external_cas_contract as fake_contract

ROOT=Path(__file__).resolve().parents[3]
RECORD=Path("qualification/h1_c1/f02/RELEASE_GATES_ABSENT.json")
PINNED_RECORD_GIT_BLOB="cf0d9841a7312082db038ef999ee307691987e44"
EXPECTED_OFFLINE_BASELINE="ebe203781e87ba108e8dec845074ca7ca47972ef"
EXPECTED_OFFLINE_TREE="ca0254a94bb2f6785608c0ad8700a693a00f647e"
STATUS="BLOCKED_11_NATIVE_RELEASE_GATES_MISSING_OFFLINE_ONLY"

class ReadinessRefusal(ValueError):
    pass


def need(ok: bool, why: str):
    if not ok:
        raise ReadinessRefusal(why)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


def _unique(rows):
    result={}
    for key,value in rows:
        need(key not in result,"duplicate owner/readiness JSON key: "+key)
        result[key]=value
    return result


def _no_constant(token: str):
    raise ReadinessRefusal("nonfinite readiness JSON constant: "+token)


def read_absence(path: Path=ROOT/RECORD) -> tuple[dict,str]:
    path=Path(path)
    need(path.is_file() and not path.is_symlink() and
         0<path.stat().st_size<=8192, "missing/unsafe readiness declaration")
    raw=path.read_bytes()
    need(git_blob(raw)==PINNED_RECORD_GIT_BLOB,
         "readiness absence declaration not exact pinned Git object")
    try:
        obj=json.loads(raw.decode("utf-8"),object_pairs_hook=_unique,
                       parse_constant=_no_constant)
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise ReadinessRefusal("invalid readiness absence JSON") from exc
    need(type(obj) is dict,"readiness absence must be an object")
    validate_absence(obj)
    return obj,sha256(raw)


def validate_absence(doc: dict) -> None:
    """Validation is NEVER a promotion to a release or approval record."""
    need(type(doc) is dict and set(doc)=={
        "schema","status","reviewedOfflineSourceCommit",
        "reviewedOfflineSourceTree","frozenOriginalF0Commit",
        "originalFirstModelSha256","modalStudySha256",
        "approvedArchivedReferenceRawSha256","approvedArchivedReferenceSeal",
        "ownerDirectionScope","ownerIdentityAuthenticatedExternally",
        "referenceRegenerated","originalFrozenF0Static100xPassed",
        "pr32BitwiseReproductionPassed","nativeAllowed","nativeExecuted",
        "nativeQualified","nativePlanApproved","ownerNativeLaunchApproved",
        "trustedReleaseReady","realAcrossRunReservationAllocated",
        "unresolvedNativeReleaseGates","limits"
    }, "unreviewed release-readiness fields")
    exact={
        "schema":"sim_heat.c1_f02_readiness_absence_declaration/1",
        "status":"EXPLICITLY_MISSING_PRE_NATIVE_GATES_NOT_AN_APPROVAL",
        "reviewedOfflineSourceCommit":EXPECTED_OFFLINE_BASELINE,
        "reviewedOfflineSourceTree":EXPECTED_OFFLINE_TREE,
        "frozenOriginalF0Commit":"dd8c9432abe97563414bb3ed809e61e673473812",
        "originalFirstModelSha256":f02.MODEL_SHA,
        "modalStudySha256":f02.STUDY_SHA,
        "approvedArchivedReferenceRawSha256":f02.REF_SHA,
        "approvedArchivedReferenceSeal":f02.REF_SEAL,
        "ownerDirectionScope":"option_a_exact_saved_reference_offline_checking_only",
    }
    for k,v in exact.items():
        need(doc.get(k)==v, "unreviewed/offline scientific provenance claim: "+k)
    denied=(
        "ownerIdentityAuthenticatedExternally","referenceRegenerated",
        "originalFrozenF0Static100xPassed","pr32BitwiseReproductionPassed",
        "nativeAllowed","nativeExecuted","nativeQualified",
        "nativePlanApproved","ownerNativeLaunchApproved","trustedReleaseReady",
        "realAcrossRunReservationAllocated"
    )
    need(all(doc.get(k) is False for k in denied),
         "native/trust/negative historical evidence falsely asserted")
    gates=doc["unresolvedNativeReleaseGates"]
    need(type(gates) is dict and set(gates)==set(fake_contract.MISSING) and
         len(gates)==11 and all(v is None for v in gates.values()),
         "release gate was filled or omitted: new independent R2 and owner native approval needed")
    need(doc["limits"]==[
        "All native release evidence gates are explicitly absent; this is NOT a release declaration",
        "Read-only local source/reference identity cannot authenticate a GitHub owner or a live protected release",
        "None of the untrusted local/fake CAS providers is a real owner-controlled native reservation",
        "No OMC version query, Modelica build or native launch has been approved or performed"
    ], "release limits removed or misrepresented")


def audit(*,root: Path=ROOT,record_path: Path=ROOT/RECORD) -> dict:
    record,record_raw_sha=read_absence(record_path)
    prior=f02.audit(root=root)
    need(prior["status"]=="F02_CONTROL_DESIGN_PREFLIGHT_PASS_NONEXECUTABLE" and
         prior["sourceIdentityPinsVerified"]==23 and
         prior["reviewedReferenceRawSha256"]==f02.REF_SHA and
         prior["reviewedReferenceSeal"]==f02.REF_SEAL and
         prior["nativePlanApproved"] is False and
         prior["ownerNativeLaunchApproved"] is False and
         prior["nativeExecuted"] is False and
         prior["originalF0ReferencePassed100x"] is False and
         prior["pr32CrossHostBitwiseRegenerationPassed"] is False,
         "original frozen scientific/source binding failed or native status inflated")
    fake=fake_contract.audit_contract_only()
    need(fake["status"]==fake_contract.DENIAL and
         fake["externalStoreConnected"] is False and
         fake["nativeAllowed"] is False and
         fake["ownerNativeLaunchApproved"] is False and
         fake["realAcrossRunReservationAllocated"] is False and
         fake["crossHostAtomicityProved"] is False and
         tuple(fake["missingGates"])==tuple(fake_contract.MISSING),
         "fake contract must not be mistaken for actual release authority")
    return {
        "schema":"sim_heat.c1_f02_release_readiness_hold_receipt/1",
        "status":STATUS,
        "releaseBlocked":True,
        "readOnlyScientificSourceIdentityVerified":True,
        "readinessAbsenceGitBlob":PINNED_RECORD_GIT_BLOB,
        "readinessAbsenceSha256":record_raw_sha,
        "reviewedOfflineBaselineSource":EXPECTED_OFFLINE_BASELINE,
        "reviewedOfflineBaselineTree":EXPECTED_OFFLINE_TREE,
        "approvedArchivedReferenceRawSha256":f02.REF_SHA,
        "approvedArchivedReferenceSeal":f02.REF_SEAL,
        "sourcePinsVerified":prior["sourceIdentityPinsVerified"],
        "referenceChannels":prior["exportChannels"],
        "referenceGridSamples":prior["timeGridSamples"],
        "flowIntegralHistories":prior["integralHistories"],
        "publicRequests":prior["publicRequests"],
        "missingRequiredNativeReleaseGates":list(fake_contract.MISSING),
        "missingRequiredGateCount":len(fake_contract.MISSING),
        "nativeAllowed":False,"nativeExecuted":False,
        "nativeQualified":False,"nativePlanApproved":False,
        "ownerIdentityAuthenticatedExternally":False,
        "ownerNativeLaunchApproved":False,
        "trustedReleaseReady":False,
        "realAcrossRunReservationAllocated":False,
        "ownerControlledExternalStoreConnected":False,
        "compilerOrHostObserved":False,
        "compilerQueried":False,"buildInvoked":False,"modelLaunched":False,
        "referenceRegenerated":False,
        "originalF0Static100xPassed":False,
        "pr32BitwiseReproductionPassed":False,
        "limits": [
            "Successful offline HOLD audit is NOT release readiness or a native permission token",
            "All 11 essential external/native gates are absent; nothing can be promoted by this module",
            "Exact content hashes show saved checking DATA integrity, not owner authenticity or native observation",
            "The owner approved only Option A checking data; no OpenModelica action is authorized"
        ],
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("inspect-pre-native-hold-only",))
    args=parser.parse_args(argv)
    try:
        print(json.dumps(audit(),indent=2,sort_keys=True,allow_nan=False))
        return 0 # Informational audit completed, but ALWAYS BLOCKED.
    except Exception as exc:
        print(json.dumps({
            "schema":"sim_heat.c1_f02_release_readiness_hold_receipt/1",
            "status":"REFUSED_INVALID_OFFLINE_RELEASE_AUDIT",
            "reason":type(exc).__name__+": "+str(exc),
            "releaseBlocked":True,
            "nativeAllowed":False,
            "ownerNativeLaunchApproved":False,
            "realAcrossRunReservationAllocated":False,
            "nativeExecuted":False,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    sys.exit(main())
