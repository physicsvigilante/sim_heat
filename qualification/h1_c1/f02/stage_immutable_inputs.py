"""F-02 immutable input staging, explicitly NOT a native runner.

Copies saved PR31 raw reference bytes and frozen source files to a new scratch
folder for future inspection. No OpenModelica, build script, executable plan,
reference regeneration, native result or runtime authorization is produced.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re

from qualification.h1_c1.f02 import offline_control_preflight as f02
from qualification.h1_c1.immutable_fixture import (
    capture_pr31_fixture as captured,
    inspect_pr31_fixture as inspector,
)
from qualification.h1_c1.option_a import offline_reference_consumer as adopted

ROOT = Path(__file__).resolve().parents[3]
STAGE_PARENT = "c1_f02_stage_evidence"
LABEL = re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
SOURCE_FILES = {
    "model.mo": ("h1/cases/H1_C1_MODAL/model.mo",
                 "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"),
    "study.json": ("h1/cases/H1_C1_MODAL/study.json",
                   "b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"),
    "SimHeat.mo": ("experiments/h1_spike/SimHeat.mo",
                   "e57955b6c32cb34321a6b1908306c4ea9a63ae259b95a5fd48c7e8d3b4da10ea"),
}
REFERENCE_FILE = "reference.bundle.json"
MANIFEST_FILE = "STAGED_INPUTS_MANIFEST.json"
STATE_FILE = "STAGE_STATE.json"
ALLOWED_FILES = set(SOURCE_FILES) | {REFERENCE_FILE, MANIFEST_FILE, STATE_FILE}


class StageRefusal(ValueError):
    pass


def need(value: bool, reason: str):
    if not value:
        raise StageRefusal(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_raw(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, allow_nan=False)+"\n").encode()


def source_file(root: Path, rel: str, expected: str) -> bytes:
    path = root/rel
    need(path.is_file() and not path.is_symlink(), "missing/symlink original source")
    raw=path.read_bytes()
    need(sha(raw)==expected, "original source SHA mismatch: "+rel)
    return raw


def exact_reference_bytes(root: Path) -> bytes:
    """Extract existing raw bytes only; do NOT compute a reference."""
    path=root/"qualification/h1_c1/immutable_fixture/PR31_V2_REFERENCE.json.xz"
    need(path.is_file() and not path.is_symlink(), "missing archived reference")
    compressed=path.read_bytes()
    need(len(compressed)==inspector.EXPECTED_ARCHIVE_BYTES and
         sha(compressed)==inspector.EXPECTED_ARCHIVE_RAW_SHA256,
         "wrong compressed reference identity")
    decompressor=lzma.LZMADecompressor(
        format=lzma.FORMAT_XZ,memlimit=inspector.XZ_DECODER_MEMORY_LIMIT)
    raw=decompressor.decompress(compressed,max_length=captured.V2_RAW_LENGTH+1)
    need(decompressor.eof and not decompressor.unused_data and
         len(raw)==captured.V2_RAW_LENGTH and sha(raw)==captured.V2_RAW_SHA,
         "wrong exact reviewed PR31 raw reference bytes")
    bundle=captured.verify_original(raw)
    need(bundle["seal"]==captured.V2_SEAL and
         bundle["nativeQualified"] is False, "wrong reference seal/native label")
    return raw


def stage(*, label: str, root: Path=ROOT) -> dict:
    need(isinstance(label,str) and LABEL.fullmatch(label) is not None,"unsafe stage name")
    root=Path(root).resolve(strict=True)
    preview=f02.audit(root=root)
    need(preview["status"]=="F02_CONTROL_DESIGN_PREFLIGHT_PASS_NONEXECUTABLE" and
         preview["nativeExecuted"] is False and preview["nativePlanApproved"] is False,
         "nonexecuting F02 design not verified")
    approved_bundle, approval=adopted.load_for_offline_checking(root=root)
    need(approval["status"]=="APPROVED_REFERENCE_DATA_OFFLINE_CHECKING_ONLY" and
         approval["nativeAllowed"] is False and
         approved_bundle["seal"]==captured.V2_SEAL,
         "only original offline reference approved")
    originals={name:source_file(root,rel,expected)
               for name,(rel,expected) in SOURCE_FILES.items()}
    exact=exact_reference_bytes(root)
    data={**originals,REFERENCE_FILE:exact}

    parent=root/STAGE_PARENT
    need(not parent.is_symlink() and
         (not parent.exists() or parent.is_dir()),"invalid staging parent")
    parent.mkdir(exist_ok=True)
    out=parent/label
    need(not out.exists() and not out.is_symlink(),
         "staging must be fresh; never overwrite an attempt")
    out.mkdir(exist_ok=False)
    state={"schema":"sim_heat.c1_f02_stage_state/1",
           "status":"INCOMPLETE_NONNATIVE",
           "nativeAllowed":False,"nativeExecuted":False,
           "nativePlanCreated":False,"oneShotReservationAllocated":False}
    (out/STATE_FILE).write_bytes(json_raw(state))
    # Mid-stage failures leave INCOMPLETE_NONNATIVE for inspection/refusal.
    for name,raw in data.items():
        with (out/name).open("xb") as file:
            file.write(raw)
    manifest={
        "schema":"sim_heat.c1_f02_immutable_stage/1",
        "status":"STAGED_FOR_OFFLINE_INSPECTION_ONLY",
        "sourceMode":"original_frozen_model_plus_saved_PR31_V2",
        "ownerScope":"reference_checking_only",
        "case":"H1_C1_MODAL",
        "sourcePinCount":23,
        "disabledPreviewSha256":sha((root/f02.PLAN).read_bytes()),
        "referenceSeal":captured.V2_SEAL,
        "referenceRawSha256":captured.V2_RAW_SHA,
        "sourceFilesSha256":{name:expected for name,(_,expected) in SOURCE_FILES.items()},
        "stagedFilesSha256":{name:sha(raw) for name,raw in data.items()},
        "nativeAllowed":False,"nativeExecuted":False,
        "nativePlanCreated":False,"nativePlanApproved":False,
        "ownerNativeLaunchApproved":False,"referenceRegenerated":False,
        "oneShotReservationAllocated":False,"buildScriptIncluded":False,
        "executableIncluded":False,"compilerQueryIncluded":False,
        "originalF0Static100xPassed":False,
        "pr32CrossHostBitwiseRegenerationPassed":False,
        "limitations":[
            "Offline data only, not a runnable native_batch/1 plan",
            "No compiler/version query, build, launch, or reservation",
            "The original F0 and PR32 negative histories remain failed",
            "Future native requires distinct R2, trusted host, and owner launch approval",
        ],
    }
    (out/MANIFEST_FILE).write_bytes(json_raw(manifest))
    state["status"]="STAGED_NOT_EXECUTED"
    (out/STATE_FILE).write_bytes(json_raw(state))
    return verify(label=label,root=root)


def verify(*,label: str,root: Path=ROOT) -> dict:
    need(isinstance(label,str) and LABEL.fullmatch(label) is not None,"unsafe stage name")
    root=Path(root).resolve(strict=True)
    directory=root/STAGE_PARENT/label
    need(directory.is_dir() and not directory.is_symlink(),"stage directory missing")
    files=list(directory.iterdir())
    need({p.name for p in files}==ALLOWED_FILES and all(
        p.is_file() and not p.is_symlink() for p in files),
        "staged payload incomplete, extra or symlink")
    state=json.loads((directory/STATE_FILE).read_text())
    need(state=={
        "schema":"sim_heat.c1_f02_stage_state/1",
        "status":"STAGED_NOT_EXECUTED",
        "nativeAllowed":False,"nativeExecuted":False,
        "nativePlanCreated":False,"oneShotReservationAllocated":False
    },"refused incomplete/untrusted stage state")
    doc=json.loads((directory/MANIFEST_FILE).read_text())
    expected={name:digest for name,(_,digest) in SOURCE_FILES.items()}
    expected[REFERENCE_FILE]=captured.V2_RAW_SHA
    need(doc.get("schema")=="sim_heat.c1_f02_immutable_stage/1" and
         doc.get("status")=="STAGED_FOR_OFFLINE_INSPECTION_ONLY" and
         doc.get("sourceMode")=="original_frozen_model_plus_saved_PR31_V2" and
         doc.get("ownerScope")=="reference_checking_only" and
         doc.get("case")=="H1_C1_MODAL" and
         doc.get("sourcePinCount")==23 and
         doc.get("disabledPreviewSha256")==sha((root/f02.PLAN).read_bytes()) and
         doc.get("referenceSeal")==captured.V2_SEAL and
         doc.get("referenceRawSha256")==captured.V2_RAW_SHA and
         doc.get("sourceFilesSha256")=={
             name:digest for name,(_,digest) in SOURCE_FILES.items()} and
         doc.get("stagedFilesSha256")==expected,
         "staged manifest source/reference identity mismatch")
    for name,digest in expected.items():
        need(sha((directory/name).read_bytes())==digest,
             "staged bytes changed: "+name)
    need(captured.verify_original((directory/REFERENCE_FILE).read_bytes())["seal"]
         ==captured.V2_SEAL,"staged canonical reference mismatch")
    false_fields=("nativeAllowed","nativeExecuted","nativePlanCreated",
                  "nativePlanApproved","ownerNativeLaunchApproved",
                  "referenceRegenerated","oneShotReservationAllocated",
                  "buildScriptIncluded","executableIncluded",
                  "compilerQueryIncluded","originalF0Static100xPassed",
                  "pr32CrossHostBitwiseRegenerationPassed")
    need(all(doc.get(k) is False for k in false_fields),
         "staged manifest asserts forbidden execution/claim")
    return {
        "schema":"sim_heat.c1_f02_stage_receipt/1",
        "status":"OFFLINE_STAGED_EXACT_INPUTS_NOT_NATIVE",
        "label":label,"fileCount":len(expected),
        "referenceSeal":captured.V2_SEAL,
        "referenceRawSha256":captured.V2_RAW_SHA,
        "nativeAllowed":False,"nativeExecuted":False,
        "ownerNativeLaunchApproved":False,"nativePlanCreated":False,
        "oneShotReservationAllocated":False,"referenceRegenerated":False,
        "originalF0Static100xPassed":False,
        "pr32CrossHostBitwiseRegenerationPassed":False
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("stage-offline-only","verify-offline-only"))
    parser.add_argument("--label",required=True)
    args=parser.parse_args(argv)
    try:
        result=(stage if args.action=="stage-offline-only" else verify)(label=args.label)
        print(json.dumps(result,sort_keys=True,indent=2,allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema":"sim_heat.c1_f02_stage_receipt/1",
            "status":"REFUSED_INCOMPLETE_OR_UNTRUSTED_OFFLINE_STAGE",
            "reason":type(exc).__name__+": "+str(exc),
            "nativeAllowed":False,"nativeExecuted":False,
            "nativePlanCreated":False,"ownerNativeLaunchApproved":False
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
