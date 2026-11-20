"""N12 — OFFLINE three-case source/proof staging, deliberately NONRUNNABLE.

This is NOT a Modelica operation, adopted reference, approved semantic seal,
runner-compatible bundle or native readiness gate. It deterministically
packages the original N1 source-only physical candidate and the independently
reviewed (bounded) N11 proof for original/tight/dense study identities without
rewriting any historical physical facts or trusting solver outputs.

All outputs go to a NEW outside-repository scratch location, never to the
original first-author study/model, historical artifacts or live runner.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1, sha256
import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from h1.study import load_study
from qualification.h1_n1 import certified_reference as n1
from qualification.h1_n4.static_physical import create_static_candidate
from qualification.h1_n9.static_trace_crosscheck import verify_historical_grid, ORIGINAL_GRID_HASHES
from qualification.h1_n11 import rational_dynamic_proof as n11

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT/"qualification/h1_n1/inputs/T"
PLAN = ROOT/"qualification/h1_n3/migration-plan.json"
STAGE_SCHEMA = "sim_heat.h1_n12.source_only_three_case_reference_stage/1"
EXPECTED_PLAN_BLOB = "357a7cd92576b04bbb256ad2728633ebf92149af"
EXPECTED_N11_BLOB = "c136e77d4cea69a1c1d0fa1157f80e3a5013bf9e"
SOURCE_MODEL_SHA = "2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae"
SOURCE_STUDY_SHA = "12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a"
SOURCE_FACTS_SHA = "39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf"
# Descriptor identities independently checked against the reviewed N12 artifacts.
CASE_STUDY_SHA = {
    "primary": SOURCE_STUDY_SHA,
    "tight": "e7effca1fcd6e858fdeb19ba8e623780ffb5ef52aed669751f74e9d78c8e9758",
    "dense": "5f4b4bdc335a5a876de3d9d642f06c85ffe5b8499af9f892437c5be6ca3ce350",
}
ROLES = ("primary","tight","dense")
EXPECTED_RUNS = (
    ("primary","H1T1TFirstAttemptV1",2400,1e-8),
    ("tight","H1T1TFirstAttemptV1_N1_TIGHT",2400,1e-10),
    ("dense","H1T1TFirstAttemptV1_N1_DENSE",4800,1e-8),
)


class StageRefusal(ValueError):
    pass


def need(ok: bool, reason: str):
    if not ok:
        raise StageRefusal("h1_n12: "+reason)


def canonical(payload: dict) -> bytes:
    # Candidate identity encoding only. Not the future owner-signed N3/JCS
    # format, external authority, semantic seal, or native-runner bundle.
    try:
        return json.dumps(payload, sort_keys=True, separators=(",",":"),
                          allow_nan=False,ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise StageRefusal("h1_n12: noncanonical candidate payload") from exc


def digest(data: bytes):
    return sha256(data).hexdigest()


def git_blob(data: bytes):
    return sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()


def original_snapshots():
    # Capture and parse the SAME bytes. A caller may not reseal a changed
    # study to have it accepted as the first physical submission.
    model=(ORIGINAL/"model.mo").read_bytes()
    study=(ORIGINAL/"study.json").read_bytes()
    facts=n11.FACTS.read_bytes()
    need(digest(model)==SOURCE_MODEL_SHA and digest(study)==SOURCE_STUDY_SHA
         and digest(facts)==SOURCE_FACTS_SHA, "original author/model/facts identity")
    planbytes=PLAN.read_bytes()
    proofbytes=Path(n11.__file__).read_bytes()
    need(git_blob(planbytes)==EXPECTED_PLAN_BLOB
         and git_blob(proofbytes)==EXPECTED_N11_BLOB,
         "frozen N3 design or reviewed N11 method changed")
    try:
        spec=json.loads(study)
        plan=json.loads(planbytes)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise StageRefusal("h1_n12: malformed pinned original study/migration design") from exc
    return model,study,facts,spec,plan


def three_studies(original_study: bytes, source: dict, plan: dict) -> dict[str,bytes]:
    need(digest(original_study)==SOURCE_STUDY_SHA,
         "original first-authored study changed")
    need(source.get("schema")=="sim_heat.study/1"
         and source.get("id")=="H1T1TFirstAttemptV1"
         and source.get("model",{}).get("sha256")==SOURCE_MODEL_SHA
         and source.get("analysis")=={
             "startTime":0,"stopTime":2400,"intervals":2400,
             "solver":"dassl","tolerance":1e-8
         }, "original study identity/physical assumptions drifted")
    need(plan.get("schema")=="sim_heat.h1_n3.reference_migration_design/1"
         and plan.get("proposedVersion",{}).get("implementationExists") is False
         and plan.get("proposedVersion",{}).get("productionRunnerSupportsVersion") is False
         and plan.get("authorities",{}).get("nativeExecutionApproved") is False
         and plan.get("originalEvidence",{}).get("independentCompleteNumericalCertificate") is False,
         "N3 is no longer a native-blocked planning contract")
    rows=plan.get("runDefinitions")
    need(type(rows) is list and len(rows)==3
         and tuple((x["name"],x["studyId"],x["intervals"],float(x["tolerance"]))
                   for x in rows)==EXPECTED_RUNS,
         "original frozen N3 three-run definitions changed")
    result={"primary":original_study}
    for role,name,intervals,tol in EXPECTED_RUNS[1:]:
        variant=deepcopy(source)
        variant["id"]=name
        variant["analysis"]["intervals"]=intervals
        variant["analysis"]["tolerance"]=tol
        need(variant["model"]==source["model"] and
             variant["requests"]==source["requests"] and
             variant["provenance"]==source["provenance"] and
             variant["mode"]==source["mode"], "companion changes physical fields")
        result[role]=canonical(variant)+b"\n"
        need(digest(result[role])!=SOURCE_STUDY_SHA,
             "companion study silently reuses original bytes")
    need(len({digest(v) for v in result.values()})==3,
         "primary/tight/dense study descriptors need distinct bytes")
    return result


def admit_cases(studies: dict[str,bytes], model: bytes, temp: Path):
    # Check with the actual H1 authoring contract; never run OpenModelica.
    need(type(studies) is dict and set(studies)==set(ROLES)
         and digest(model)==SOURCE_MODEL_SHA, "case source drift")
    admitted={}
    for role in ROLES:
        need(digest(studies[role]) == CASE_STUDY_SHA[role], "study identity differs for "+role)
        folder=temp/"cases"/role
        folder.mkdir(parents=True,exist_ok=False)
        (folder/"model.mo").write_bytes(model)
        (folder/"study.json").write_bytes(studies[role])
        loaded=load_study(folder/"study.json",folder)
        need(loaded.request_report["admitted"] is True
             and len(loaded.request_report["requests"])==8
             and all(v["status"]=="not_computed"
                     for v in loaded.request_report["requests"])
             and loaded.model_sha256==SOURCE_MODEL_SHA
             and loaded.sha256==digest(studies[role]),
             "H1 source-only admission disagrees for "+role)
        admitted[role]=loaded
    return admitted


def _read_original_trace(blob: bytes, count: int) -> dict:
    need(digest(blob) == ORIGINAL_GRID_HASHES[count],
         "not the original complete N1 source-only reference trace")
    trace = json.loads(blob)
    need(trace.get("report",{}).get("schema")=="sim_heat.h1_n1.interval_reference_candidate/1"
         and trace["report"].get("refModelSha256")==SOURCE_MODEL_SHA
         and trace["report"].get("refStudySha256")==SOURCE_STUDY_SHA
         and trace["report"].get("gridIntervals")==count
         and trace["report"].get("samples")==count+1
         and trace["report"].get("allExports")==77
         and trace["report"].get("requests")==8
         and trace["report"].get("flowIntegrals")==5,
         "not the original complete N1 source-only reference trace")
    for name in ("nativeExecuted","nativeQualified","runtimeReady",
                 "independentlyCertifiedReference"):
        need(trace["report"].get(name) is False, "N1 tries to claim qualified data")
    need(len(trace.get("grid",[]))==count+1
         and len(trace.get("columns",{}))==77
         and len(trace.get("requests",{}))==8
         and len(trace.get("integrals",{}))==5,
         "missing full source-only physical request/reference inventory")
    return trace


def _audited_proof_sha() -> str:
    proof = n11.audit()
    need(proof.get("schema")==n11.SCHEMA
         and proof.get("sourceFactsSha256")==SOURCE_FACTS_SHA
         and proof.get("originalModelSha256")==SOURCE_MODEL_SHA
         and proof.get("originalStudySha256")==SOURCE_STUDY_SHA
         and proof.get("individualPhysicallyEnclosedSamples")==648180
         and proof.get("sourceMathematicalEnclosureSelfChecked") is True
         and proof.get("referenceAccuracyCertified") is False
         and proof.get("nativeExecuted") is False
         and proof.get("nativeQualified") is False
         and proof.get("referenceBundleWritten") is False
         and type(proof.get("grids")) is list
         and [(row.get("intervals"), row.get("originalN1TraceSha256"))
              for row in proof["grids"]] == list(ORIGINAL_GRID_HASHES.items()),
         "reviewed N11 candidate cannot be represented as adopted proof")
    return digest(canonical(proof))


def _verified_traces(root: Path, facts: bytes) -> dict:
    physical=create_static_candidate(facts,expected_sha256=SOURCE_FACTS_SHA)
    traces={}
    for count in ORIGINAL_GRID_HASHES:
        target=root/("n1-"+str(count))
        report=n1.certify(n1.read_facts(),count,output=target)
        blob=(target/("N1_T1T_reference_grid"+str(count)+".json")).read_bytes()
        need(digest(blob)==report["fullTraceSha256"],
             "source-only N1 trace report/bytes disagree")
        verify_historical_grid(blob,count,physical)
        traces[count]=_read_original_trace(blob,count)
    return traces


def prepare(out: Path):
    out=Path(out).resolve()
    need(not out.is_relative_to(ROOT) and not out.exists(),
         "output must be a NEW outside-repository scratch directory")
    model,source_study,facts,source,plan=original_snapshots()
    studies=three_studies(source_study,source,plan)
    # Full N11 source-rational proof is personally rerun, NOT inferred from a
    # prior 'review passed' string, and no caller-provided receipt can pass.
    proof_sha = _audited_proof_sha()
    with TemporaryDirectory(prefix="simheat-n12-") as scratch:
        root=Path(scratch)
        admitted=admit_cases(studies,model,root)
        traces = _verified_traces(root, facts)
        packets={}
        for role in ROLES:
            grid=4800 if role=="dense" else 2400
            case = admitted[role]
            trace = traces[grid]
            # Neither the original H1 verifier nor the future N3 dispatcher recognizes
            # this schema. Deliberately omit legacy 'seal', future 'semanticSeal',
            # per-output native allowances and release approval fields.
            payload={
                "schema":STAGE_SCHEMA,"stage":"candidate_data_preparation_offline_only",
                "role":role,
                "caseStudySha256":case.sha256,
                "originalFirstAuthorStudySha256":SOURCE_STUDY_SHA,
                "originalFirstAuthorModelSha256":SOURCE_MODEL_SHA,
                "originalPhysicalFactsSha256":SOURCE_FACTS_SHA,
                "originalPhysicalTraceStudySha256":SOURCE_STUDY_SHA,
                "originalTraceSha256":ORIGINAL_GRID_HASHES[grid],
                "originalN11ProofReceiptSha256":proof_sha,
                "mode":"transient",
                "analysis":case.data["analysis"],
                "studyId":case.data["id"],
                "grid":trace["grid"],
                "columns":trace["columns"],
                "units":trace["units"],
                "requests":trace["requests"],
                "flowIntegrals":trace["integrals"],
                "referenceAccuracyCertified":False,
                "independentlyCertifiedReference":False,
                "nativeExecuted":False,
                "nativeQualified":False,
                "runtimeReady":False,
                "referenceBundleWritten":False,
                "runnerConsumable":False,
                "referenceVersionAdopted":False,
                "externalOwnerApprovalVerified":False,
                "nativeAttemptAuthorized":False,
                "physicalInputOrLawChangedForCompanion":False,
                "origin":"SHA_VERIFIED_ORIGINAL_SOURCE_ONLY_N1_WITH_SEPARATELY_REVIEWED_N11_MATH",
                "restriction":"source-only physical target reused across solver-tolerance changes; no runtime bundle, independent owner seal, actual OMC output, or execution authority",
            }
            packets[role]=canonical(payload)+b"\n"
        # Re-read protected original sources before staging any output. A
        # changed first author/model/facts never inherits the old source pins.
        original_snapshots()
        out.mkdir(parents=True,exist_ok=False)
        for role in ROLES:
            case=out/"cases"/role
            case.mkdir(parents=True,exist_ok=False)
            (case/"model.mo").write_bytes(model)
            (case/"study.json").write_bytes(studies[role])
            (out/(role+".candidate.json")).write_bytes(packets[role])
        result={
            "schema":"sim_heat.h1_n12.three_case_stage_receipt/1",
            "sourceFactsSha256":SOURCE_FACTS_SHA,
            "originalModelSha256":SOURCE_MODEL_SHA,
            "originalStudySha256":SOURCE_STUDY_SHA,
            "n11SourceMathematicalReceiptSha256":proof_sha,
            "cases":[{
                "role":role,
                "studyId":admitted[role].data["id"],
                "derivedStudySha256":digest(studies[role]),
                "modelSha256":SOURCE_MODEL_SHA,
                "originalN1TraceSha256":ORIGINAL_GRID_HASHES[
                    4800 if role=="dense" else 2400],
                "candidateDataSha256":digest(packets[role]),
                "samples":4801 if role=="dense" else 2401,
                "H1SourceAdmitted":True,"publicRequestsNotComputed":True,
            } for role in ROLES],
            "differentStudyIdentitiesForOriginalAndAnalysisOnlyCompanions":True,
            "n11MathematicalSelfCheckRerun":True,
            "referencesSourceOnly":True,
            "referenceBundleWritten":False,
            "nativeExecutionReady":False,
            "referenceAccuracyCertified":False,
            "independentlyCertifiedReference":False,
            "externalOwnerApprovalVerified":False,
            "nativeExecuted":False,
            "nativeQualified":False,
            "runPermissionGranted":False,
            "productionRunnerModified":False,
            "legacySevenReferenceFailuresStillOpen":list(n11.NATIVE_HOLD),
            "originalNativeBlockersStillOpen":8,
            "limitation":"three source-only candidate packages and derived analysis descriptors, no old or future runner reference schema, no owner trust, no OpenModelica operation",
        }
        (out/"stage-receipt.json").write_bytes(canonical(result)+b"\n")
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.out),sort_keys=True,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
