"""Offline-only, NON-EXECUTING Modelica build-text preview.

Uses unchanged frozen build_script() as a PURE STRING formatter for verified
staged source bytes. No native plan, OMC, compilation or model launch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
from h1.study import load_study
from tools.h1_native_batch import build_script
from qualification.h1_c1.f02 import stage_immutable_inputs as staging

ROOT=Path(__file__).resolve().parents[3]
OUT="c1_f02_build_preview_evidence"
SCRIPT="unexecuted-build-script.mos.txt"
MANIFEST="NONNATIVE_BUILD_PREVIEW_MANIFEST.json"
LABEL=re.compile(r"[a-z][a-z0-9-]{0,31}\Z")
REF_SHA="0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368"
REF_SEAL="d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
MODEL_SHA="9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
STUDY_SHA="b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"

class PreviewRefusal(ValueError):
    pass

def need(cond,reason):
    if not cond:
        raise PreviewRefusal(reason)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encoded(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()

def inputs(root,label):
    need(type(label) is str and LABEL.fullmatch(label) is not None,
         "unsafe preview label")
    verified=staging.verify(root=root,label=label)
    need(verified["status"]=="OFFLINE_STAGED_EXACT_INPUTS_NOT_NATIVE" and
         verified["nativeAllowed"] is False and
         verified["nativeExecuted"] is False and
         verified["referenceSeal"]==REF_SEAL and
         verified["referenceRawSha256"]==REF_SHA,
         "source stage not verified for offline-only use")
    folder=root/staging.STAGE_PARENT/label
    study=load_study(folder/"study.json",folder)
    need(study.sha256==STUDY_SHA and study.model_sha256==MODEL_SHA and
         study.request_report["admitted"] is True and
         len(study.data["requests"])==9, "staged model/study drift")
    # Importing build_script is safe: NO h1_native_batch.prepare or execute.
    text=build_script(study,folder/"SimHeat.mo",folder/"model.mo")
    need(text.count("buildModel(")==1 and
         'loadModel(Modelica, {"4.0.0"})' in text and
         'getVersion(Modelica) <> "4.0.0"' in text and
         'numberOfIntervals=4000' in text and
         'outputFormat="mat"' in text and
         'variableFilter=".*"' in text and
         'method="dassl"' in text and
         'fileNamePrefix="model"' in text,
         "unexpected source-only Modelica preview")
    raw=text.encode("utf-8")
    need(len(raw)<=16_384,"oversized text preview")
    return raw,verified

def contract(label,raw):
    return {
        "schema":"sim_heat.c1_f02_build_text_preview/1",
        "status":"OFFLINE_TEXT_PREVIEW_UNEXECUTED",
        "stageLabel":label,
        "stageStatus":"OFFLINE_STAGED_EXACT_INPUTS_NOT_NATIVE",
        "textSha256":sha(raw),
        "modelSha256":MODEL_SHA,"studySha256":STUDY_SHA,
        "referenceRawSha256":REF_SHA,"referenceSeal":REF_SEAL,
        "librarySha256":staging.SOURCE_FILES["SimHeat.mo"][1],
        "targetMSL":"4.0.0","targetSolver":"dassl","targetIntervals":4000,
        "hostObserved":False,"omcVersionQueried":False,
        "buildInvoked":False,"modelLaunched":False,
        "nativeExecuted":False,"nativeQualified":False,
        "nativeAllowed":False,"nativePlanCreated":False,
        "ownerNativeLaunchApproved":False,
        "oneShotReservationAllocated":False,"referenceRegenerated":False,
        "frozenF0Original100xPassed":False,
        "pr32BitwiseRegenerationPassed":False,
        "limitations":[
            "This is reviewable text, NOT an approved runnable native plan",
            "The frozen h1_native_batch.prepare path is forbidden (regenerates reference)",
            "No observed compiler/MSL/host or durable one-shot lock",
            "Any real OMC attempt needs distinct owner approval and pre-native R2"
        ]
    }

def _target(root,label):
    need(type(label) is str and LABEL.fullmatch(label) is not None,
         "unsafe preview label")
    root=Path(root).resolve(strict=True)
    parent=root/OUT
    need(not parent.is_symlink() and
         (not parent.exists() or parent.is_dir()),
         "invalid build-preview parent")
    return parent,parent/label

def prepare(*,label,root=ROOT):
    root=Path(root).resolve(strict=True)
    raw,verified=inputs(root,label)
    parent,target=_target(root,label)
    parent.mkdir(exist_ok=True)
    need(not target.exists() and not target.is_symlink(),
         "preview attempt exists; refuse overwrite")
    target.mkdir(exist_ok=False)
    with (target/SCRIPT).open("xb") as f:
        f.write(raw)
    with (target/MANIFEST).open("xb") as f:
        f.write(encoded(contract(label,raw)))
    return verify(label=label,root=root)

def verify(*,label,root=ROOT):
    root=Path(root).resolve(strict=True)
    raw,verified=inputs(root,label)
    parent,target=_target(root,label)
    need(parent.is_dir() and not parent.is_symlink() and
         target.is_dir() and not target.is_symlink(),
         "build-preview parent or stage missing/symlink")
    files=list(target.iterdir())
    need({p.name for p in files}=={SCRIPT,MANIFEST} and
         all(p.is_file() and not p.is_symlink() for p in files),
         "incomplete or unexpected build-preview files")
    saved=(target/SCRIPT).read_bytes()
    # First validate JSON shape and duplicate-key/non-finite refusal using the
    # reviewed strict staging parser. Its decoded dict alone is NOT sufficient:
    # Python treats 0 == False and 4000.0 == 4000. Preserve literal types and
    # exact source-to-evidence serialization by pinning the entire raw manifest.
    doc=staging.strict_metadata(target/MANIFEST)
    expected=contract(label,raw)
    manifest_raw=(target/MANIFEST).read_bytes()
    need(saved==raw and
         manifest_raw==encoded(expected) and
         doc==expected,
         "build text/manifest differs from verified source")
    return {
        "schema":"sim_heat.c1_f02_build_text_receipt/1",
        "status":"NONEXECUTABLE_BUILD_TEXT_PREVIEW_VERIFIED",
        "stageLabel":label,"textSha256":sha(raw),
        "referenceRawSha256":REF_SHA,"referenceSeal":REF_SEAL,
        "stageFiles":verified["fileCount"],
        "nativeAllowed":False,"omcVersionQueried":False,
        "buildInvoked":False,"modelLaunched":False,
        "nativeExecuted":False,"nativeQualified":False,
        "ownerNativeLaunchApproved":False,"oneShotReservationAllocated":False,
        "referenceRegenerated":False,"releaseTrustRootComplete":False
    }

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("preview-text-only","verify-preview-only"))
    parser.add_argument("--label",required=True)
    args=parser.parse_args(argv)
    try:
        proc=prepare if args.action=="preview-text-only" else verify
        print(json.dumps(proc(label=args.label),sort_keys=True,indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema":"sim_heat.c1_f02_build_text_receipt/1",
            "status":"REFUSED_BUILD_TEXT_PREVIEW",
            "reason":type(exc).__name__+": "+str(exc),
            "nativeAllowed":False,"omcVersionQueried":False,
            "buildInvoked":False,"modelLaunched":False,
            "nativeExecuted":False,"ownerNativeLaunchApproved":False
        },sort_keys=True))
        return 3

if __name__=="__main__":
    raise SystemExit(main())
