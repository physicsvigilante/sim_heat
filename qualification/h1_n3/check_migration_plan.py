"""Read-only H1-N3 design audit. NEVER generates a native reference or calls OMC."""
from __future__ import annotations
import argparse
import ast
from hashlib import sha1, sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = Path(__file__).resolve().parent / "migration-plan.json"
PLAN_BLOB = "2203449ddd3282ddfc71699097f3fe320d2c7c54"
BLOBS = {
    "qualification/h1_n1/certified_reference.py": "145fdd3e2d8e7c870e3ae609ac46a0c2694b7898",
    "qualification/h1_n2/compare.py": "5c03b86e9e4e141482f63c44276a4f087b8513bb",
    "h1/reference.py": "331d31d604bf98d6ba10a97b65b42ad46cfed713",
    "h1/verification.py": "567a326565659da4b844efc26b0314e6994c3f6f",
    "h1/temporal.py": "01960b7a8b11bfcedb1f015b439bfd1160d94253",
    "h1/policy.py": "05ad449a3cd199808b60af0cc94879c6518cc775",
    "tools/h1_native_batch.py": "6e6d97f69650e695a90c48f82fcd864618e569e9",
    "qualification/h1_n1/plan.json": "047711c940988e0f59be3d34c2ea4e71edd1ac70",
}
ORIGINALS = {
    "qualification/h1_n1/inputs/T/model.mo": "2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae",
    "qualification/h1_n1/inputs/T/study.json": "12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a",
    "qualification/h1_n1/reference-facts.json": "39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf",
}
BLOCKERS = (
    "R2_PLAN_REVIEW_NOT_YET_COMPLETE",
    "EXACT_RUNTIME_IMAGE_BINARY_AND_MSL_MANIFEST_UNBOUND",
    "INDEPENDENT_100X_REFERENCE_ERROR_CERTIFICATE_NOT_IMPLEMENTED_OR_VERIFIED",
    "STATIC_CHECKING_CENTRES_FAIL_PHYSICAL_100X_BOUND",
    "TARGET_HOST_ALL_THREE_NEW_REFERENCE_SEALS_AND_REPLAY_NOT_READY",
    "PRIMARY_ONLY_COMMON_TIME_COMPARATOR_NOT_IMPLEMENTED_OR_REVIEWED",
    "EXACT_EXECUTION_MANIFEST_SINGLE_USE_CONTROL_AND_COMPANION_BYTES_NOT_READY",
    "SEPARATE_EXPLICIT_NATIVE_OWNER_PERMISSION_NOT_GRANTED",
)
SEVEN = ("T02.G", "T06.A", "T06.G", "T07.G", "T08.G", "T10.G", "T_Plug.C")
TRACES = {
    "primary": "b13877c8d069a60928cf3b23ae007b1a10feb53151f00ffb65a57082a7fc10af",
    "dense": "9ba71a1d2fccb39be071df0647793f6fb844737e2ac9c91bb143546ab8d26b40",
}

class DesignRefusal(ValueError):
    pass

def need(ok, why):
    if not ok:
        raise DesignRefusal("h1_n3: " + why)

def blob_sha(raw):
    return sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def strict_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def invalid(x):
        raise DesignRefusal("h1_n3: nonfinite JSON constant")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
    except DesignRefusal:
        raise
    except (ValueError, UnicodeError, TypeError, OverflowError, RecursionError) as exc:
        raise DesignRefusal("h1_n3: malformed JSON") from exc

def read_plan():
    raw = PLAN_PATH.read_bytes()  # same bytes hashed and parsed; no second read
    need(len(raw) <= 65536 and blob_sha(raw) == PLAN_BLOB, "plan bytes not pinned")
    plan = strict_json(raw)
    need(type(plan) is dict, "plan must be object")
    return plan

def same_typed(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(
            same_typed(actual[k], v) for k,v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            same_typed(a,b) for a,b in zip(actual,expected))
    return actual == expected

def runner_still_old(raw):
    """Inspect syntax without importing or executing the native runner."""
    try:
        source = ast.parse(raw.decode("utf-8"))
    except (UnicodeError, ValueError, SyntaxError) as exc:
        raise DesignRefusal("h1_n3: runner unreadable") from exc
    return any(
        isinstance(node, ast.FunctionDef) and node.name == "prepare"
        and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and call.func.attr == "prepare"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "reference"
                for call in ast.walk(node))
        for node in source.body)

def audit(plan):
    """VERIFIED DESIGN is never NATIVE-READY; caller cannot change this."""
    need(same_typed(plan, read_plan()), "unreviewed in-memory plan change")
    need(plan["schema"] == "sim_heat.h1_n3.reference_migration_design/1"
         and plan["stage"] == "OFFLINE_DESIGN_ONLY_NOT_A_CHECKER_OR_NATIVE_PLAN",
         "invalid non-executable scope")
    need(plan["lineage"]["baseCommit"] == "6baba681ae1680e2fcae1ea8efbf0953afcb031b"
         and plan["lineage"]["baseTree"] == "27b6ce015d5ba8229ee5990d3fa1e90352fe3f45",
         "base identity mismatch")
    need(plan["immutableSourceGitBlobs"] == BLOBS, "source pin list changed")
    sources = {}
    for name, expected in BLOBS.items():
        raw = (ROOT/name).read_bytes()
        need(blob_sha(raw) == expected, "modified pinned source: " + name)
        sources[name] = raw
    for name, expected in ORIGINALS.items():
        need(sha256((ROOT/name).read_bytes()).hexdigest() == expected,
             "modified original source: " + name)
    need(runner_still_old(sources["tools/h1_native_batch.py"]),
         "old runner preparation path not confirmed")
    old_plan = strict_json(sources["qualification/h1_n1/plan.json"])
    need(type(old_plan) is dict and old_plan.get("executionBlockers") == list(BLOCKERS)
         and old_plan.get("executionReady") is False
         and old_plan.get("authority", {}).get("nativeExecutionApproved") is False,
         "existing original native execution blockers changed")
    p = plan["originalEvidence"]
    need(p["fullGridTraceSha256"] == TRACES
         and (p["allExports"],p["publicRequests"],p["flowIntegrals"]) == (77,8,5)
         and p["independentCompleteNumericalCertificate"] is False,
         "source-only reference overclaimed")
    need(plan["legacyRefusals"]["staticPhysical100xFailNames"] == list(SEVEN)
         and plan["legacyRefusals"]["originalNativeExecutionBlockers"] == list(BLOCKERS),
         "seven static refusals or eight blockers dropped")
    need([r["name"] for r in plan["runDefinitions"]] == ["primary","tight","dense"]
         and [(r["intervals"],r["samples"]) for r in plan["runDefinitions"]]
             == [(2400,2401),(2400,2401),(4800,4801)]
         and all(r["futureReferenceSha256"] is None
                 and r["externallySealedDigest"] is None for r in plan["runDefinitions"]),
         "invented N1 new reference or run identity")
    version=plan["proposedVersion"]
    need(all(version[key] is False for key in (
             "implementationExists","productionRunnerSupportsVersion",
             "runnerReferenceRepreparationUpdated","directOldBundleEditingPermitted",
             "historicalReferenceRewritingPermitted",
             "fallbackToOldCheckingCentresPermitted")), "unreviewed version promotion")
    need(plan["trustBoundary"]["outputCannotGrantNativePermission"] is True
         and all(v is False for k,v in plan["trustBoundary"].items()
                 if k!="outputCannotGrantNativePermission"),
         "self-authenticating or non-existent external seal")
    need(plan["authorities"]["planningAllowed"] is True
         and all(v is False for k,v in plan["authorities"].items()
                 if k!="planningAllowed"), "owner permission invented")
    need(plan["designFlags"]["nativeCallsPerformed"] == 0
         and all(v is False for k,v in plan["designFlags"].items()
                 if k!="nativeCallsPerformed"), "native operation/result invented")
    return {
        "schema": "sim_heat.h1_n3.design_check_receipt/1",
        "status": "DESIGN_VERIFIED_NATIVE_BLOCKED",
        "sourcePinsVerified": True,
        "legacyRunnerStillUsesOldPrepare": True,
        "sourceOnlyTraceHashesRecordedNotRecomputed": TRACES.copy(),
        "versionedReferenceImplemented": False,
        "referenceAccuracyCertified": False,
        "independentlyCertifiedReference": False,
        "referenceMigrated": False,
        "runtimeReady": False,
        "nativeExecuted": False,
        "nativeQualified": False,
        "nativeCalls": 0,
        "oldStaticRefusals": list(SEVEN),
        "nativeExecutionBlockers": list(BLOCKERS),
        "ownerNativePermission": False,
    }

def check(output=None):
    result = audit(read_plan())
    if output is not None:
        path=Path(output).resolve()
        need(not path.is_relative_to(ROOT) and not path.exists() and path.parent.is_dir(),
             "output must be a new outside-repo scratch file")
        path.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n",encoding="utf-8")
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args=parser.parse_args()
    print(json.dumps(check(args.out),indent=2,sort_keys=True))

if __name__=="__main__":
    main()
