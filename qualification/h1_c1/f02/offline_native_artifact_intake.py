"""F02 LOCAL UNTRUSTED native-artifact intake FIREWALL; ALWAYS BLOCKED.

This is a READ-ONLY evidence *inventory* only. It can SHA-256 and strictly
parse local data-only candidate files to record what was presented, but can
NEVER establish that any file came from OpenModelica, an authenticated owner,
a trusted host, an approved native adapter or a protected atomic CAS store.
No native runner, MAT decoder, simulator, executable, or network is used.

Every result retains releaseBlocked=True, all native/owner flags False,
all nine original public native observations NOT COMPUTED, and 11 actual
owner/source/host/external-reservation prerequisites MISSING. Zero CLI
success is never native acceptance. Unsigned local hashes are not signatures.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from qualification.h1_c1.f02 import offline_release_readiness_hold as readiness
from qualification.h1_c1.f02 import stage_immutable_inputs as staged

ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_PARENT = "c1_f02_untrusted_native_evidence"
LABEL = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
STATUS = "BLOCKED_UNAUTHENTICATED_NATIVE_ARTIFACT_INTAKE"
SCHEMA = "sim_heat.c1_f02_untrusted_native_artifact_inventory/1"

# Names are an inventory wish list, not approved native plan/output formats.
# A file with one of these names can be entirely fake or malformed.
UNTRUSTED_FILENAMES = {
    "source-release.json": 16_384,
    "reference-backup-attestation.json": 16_384,
    "host-toolchain-attestation.json": 16_384,
    "native-plan-approval.json": 16_384,
    "durable-reservation-receipt.json": 16_384,
    "native-run-receipt.json": 16_384,
    "model_res.mat": 20*1024*1024,
    "normalized.csv": 20*1024*1024,
    "post-native-checks.json": 65_536,
}
FILE_NAMES = tuple(sorted(UNTRUSTED_FILENAMES))
MAX_COMBINED_BYTES = sum(UNTRUSTED_FILENAMES.values())
NO_EXECUTION_FIELDS = (
    "nativeAllowed","nativeExecuted","nativeQualified",
    "ownerNativeLaunchApproved","trustedReleaseReady",
    "ownerAuthenticated","compilerVersionQueried",
    "buildInvoked","modelLaunched","matDecoded",
    "publicReadingsComputed","realAcrossRunReservationAllocated",
    "referenceRegenerated","historicalF0Static100xPassed",
    "pr32BitwiseRegenerationPassed",
)


class IntakeRefusal(ValueError):
    pass


def need(ok: bool, why: str) -> None:
    if not ok:
        raise IntakeRefusal(why)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _finite_float(token: str) -> float:
    # parse_constant only catches NONSTANDARD NaN/Infinity tokens. Legal
    # JSON exponent syntax such as 1e999 otherwise converts to float('inf').
    value = float(token)
    need(math.isfinite(value), "nonfinite JSON number in untrusted file")
    return value


def _strict_untrusted_object(raw: bytes) -> dict:
    """Check format only; parse EXACTLY the same bytes recorded in the SHA.

    Reuse the previously reviewed duplicate-key and nonstandard-constant
    callbacks. This does NOT authenticate a writer, provide a filesystem
    snapshot, or establish any native provenance.
    """
    try:
        obj = json.loads(raw.decode("utf-8"),
                         object_pairs_hook=staged._no_duplicate_pairs,
                         parse_constant=staged._reject_nonfinite,
                         parse_float=_finite_float)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IntakeRefusal("malformed or non-UTF8 untrusted JSON") from exc
    need(type(obj) is dict, "untrusted JSON was not a bounded object")
    return obj


def _label(label: str) -> None:
    need(type(label) is str and LABEL.fullmatch(label) is not None,
         "unsafe local candidate label")


def _directory(candidate_root: Path, label: str) -> Path:
    """Path validation is local best-effort, NOT protection from concurrent writers."""
    _label(label)
    root = Path(candidate_root).resolve(strict=True)
    parent = root / CANDIDATE_PARENT
    need(not parent.is_symlink(), "symlinked untrusted candidate parent")
    need(not parent.exists() or parent.is_dir(),
         "untrusted evidence parent must be a directory or absent")
    folder = parent / label
    need(not folder.is_symlink(),
         "symlinked untrusted candidate directory")
    need(not folder.exists() or folder.is_dir(),
         "untrusted candidate path is not a directory")
    return folder


def _inventory(folder: Path) -> tuple[dict, list[str]]:
    if not folder.exists():
        return {},list(FILE_NAMES)
    members = list(folder.iterdir())
    need(len(members) <= len(FILE_NAMES),
         "extra entries in local candidate evidence")
    need({x.name for x in members} <= set(FILE_NAMES),
         "unexpected/possibly executable candidate file")
    need(all(p.is_file() and not p.is_symlink() for p in members),
         "nonregular or symlinked candidate file")
    present = {}
    combined = 0
    for path in sorted(members, key=lambda p:p.name):
        maximum = UNTRUSTED_FILENAMES[path.name]
        size = path.stat().st_size
        need(0 < size <= maximum, "empty/oversized untrusted evidence: "+path.name)
        combined += size
        need(combined <= MAX_COMBINED_BYTES,
             "untrusted evidence directory exceeds bounded bytes")
        raw=path.read_bytes()
        need(len(raw)==size,"concurrent untrusted file size changed")
        # Parse the SAME captured bytes used for this local SHA inventory.
        # No second pathname reopen; this reduces read inconsistency but does
        # NOT solve stat/read, directory-swap or adversarial TOCTOU races.
        if path.suffix==".json":
            _strict_untrusted_object(raw)
        present[path.name] = {
            "sizeBytes":size,
            "untrustedLocalSha256":_sha(raw),
            "originAuthenticated":False,
            "nativeEvidenceVerified":False,
        }
    return present,[name for name in FILE_NAMES if name not in present]


def inspect_only(*, label: str, candidate_root: Path=ROOT,
                 scientific_root: Path=ROOT) -> dict:
    """Even a full fabricated candidate set NEVER receives a native PASS."""
    _label(label)
    base=readiness.audit(root=scientific_root)
    need(base["status"]==readiness.STATUS and
         base["releaseBlocked"] is True and
         base["missingRequiredGateCount"]==11 and
         base["nativeAllowed"] is False and
         base["ownerNativeLaunchApproved"] is False and
         base["realAcrossRunReservationAllocated"] is False,
         "actual owner/source/host/CAS prerequisites not established")
    folder=_directory(candidate_root,label)
    present,missing=_inventory(folder)
    need(base["approvedArchivedReferenceRawSha256"]==
         "0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368" and
         base["approvedArchivedReferenceSeal"]==
         "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9",
         "original checking-only reference identity differs")
    return {
        "schema":SCHEMA,
        "status":STATUS,
        "releaseBlocked":True,
        "label":label,
        "reviewedSourceBaseline":base["reviewedOfflineBaselineSource"],
        "referenceRawSha256":base["approvedArchivedReferenceRawSha256"],
        "referenceSeal":base["approvedArchivedReferenceSeal"],
        "sourcePinsVerified":base["sourcePinsVerified"],
        "expectedUntrustedFilenames":list(FILE_NAMES),
        "localFilesOnly":present,
        "missingFilenames":missing,
        "allFileNamesPresentWouldBeNativeProof":False,
        "localFileHashesAreAuthenticProvenance":False,
        "elevenReleaseGatesStillMissing":base["missingRequiredNativeReleaseGates"],
        "nativePublicRequestsStillNotComputed":9,
        **{field:False for field in NO_EXECUTION_FIELDS},
        "limits":[
            "Read-only untrusted local file inventory; no native data/owner/provider authentication",
            "A file named model_res.mat is not decoded and is NOT a Modelica result",
            "A matching SHA is not an owner signature or a known trusted reference root",
            "All 11 actual release/CAS/host/owner gates remain MISSING",
            "No filesystem snapshot/TOCTOU or cross-host authenticity proof",
        ],
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("inspect-untrusted-files-only",))
    parser.add_argument("--label",required=True)
    args=parser.parse_args(argv)
    try:
        output=inspect_only(label=args.label)
        print(json.dumps(output,sort_keys=True,indent=2,allow_nan=False))
        return 0  # Successful DENIAL inspection; never approval or native proof.
    except Exception as exc:
        print(json.dumps({
            "schema":SCHEMA,
            "status":"REFUSED_UNTRUSTED_OR_MALFORMED_INTAKE",
            "reason":type(exc).__name__+": "+str(exc),
            "releaseBlocked":True,
            "nativeAllowed":False,"nativeExecuted":False,
            "ownerNativeLaunchApproved":False,
            "realAcrossRunReservationAllocated":False,
            "nativePublicRequestsStillNotComputed":9,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
