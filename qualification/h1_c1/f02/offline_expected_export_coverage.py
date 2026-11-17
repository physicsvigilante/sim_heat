"""H1-C1-F02 OFFLINE EXPECTED export/request coverage, never native results.

Reads only the previously reviewed original saved PR31 scientific CHECKING data,
original first-author Modelica, evaluator modal study, and the PR41 release HOLD.
Names and counts are EXPECTED, not produced or observed by OpenModelica.
No numeric reference time-series are copied into the receipt. No OMC, MAT,
CSV, compilation, native adapter, reference generation or permission exists.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from h1.model import internal_exports
from h1.study import load_study
from qualification.h1_c1.f02 import offline_release_readiness_hold as readiness
from qualification.h1_c1.option_a import offline_reference_consumer as approved

ROOT=Path(__file__).resolve().parents[3]
STUDY=Path("h1/cases/H1_C1_MODAL/study.json")
SCHEMA="sim_heat.h1_c1_f02_offline_expected_export_coverage/1"
STATUS="EXPECTED_ANALYTICAL_COVERAGE_ONLY_NO_NATIVE_OBSERVATION"
ORIGINAL_REFERENCE_SHA="0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368"
ORIGINAL_REFERENCE_SEAL="d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
ORIGINAL_MODEL_SHA="9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
MODAL_STUDY_SHA="b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"
REAL_NATIVE_FALSE=(
    "nativeAllowed","nativeExecuted","nativeQualified","modelBuilt",
    "compilerQueried","realAcrossRunReservationAllocated",
    "ownerNativeLaunchApproved","trustedReleaseReady","matDecoded",
    "referenceRegenerated","originalF0Strict100xPassed",
    "pr32BitwiseRegenerationPassed","nativeObservationsComputed",
)


class CoverageRefusal(ValueError):
    pass


def need(ok: bool, reason: str):
    if not ok:
        raise CoverageRefusal(reason)


def encoded(value: dict) -> bytes:
    """Canonical equality retains literal JSON booleans/int/null distinctions."""
    try:
        return (json.dumps(value,sort_keys=True,indent=2,
                           ensure_ascii=True,allow_nan=False)+"\n").encode("utf-8")
    except (ValueError,TypeError,OverflowError,RecursionError) as exc:
        raise CoverageRefusal("invalid noncanonical coverage receipt") from exc


def _integral_names(study):
    """Expected energy histories, from original model component KINDS only."""
    return tuple(sorted(
        name+(".Q_in" if c.kind=="Body" else ".Q_to_network")
        for name,c in study.model.components.items()
        if c.kind in ("Body","FixedTemperature")
    ))


def _basis(root: Path):
    """Pinned, read-only original science + Option A only, no generator."""
    root=Path(root).resolve(strict=True)
    held=readiness.audit(root=root)
    need(held["status"]==readiness.STATUS and
         held["releaseBlocked"] is True and
         held["missingRequiredGateCount"]==11 and
         held["nativeAllowed"] is False and
         held["nativeExecuted"] is False and
         held["ownerNativeLaunchApproved"] is False and
         held["realAcrossRunReservationAllocated"] is False,
         "frozen source or eleven native release HOLD gates changed")
    bundle,decision=approved.load_for_offline_checking(root=root)
    need(decision["status"]=="APPROVED_REFERENCE_DATA_OFFLINE_CHECKING_ONLY"
         and decision["nativeAllowed"] is False
         and decision["nativeExecuted"] is False
         and decision["referenceSeal"]==ORIGINAL_REFERENCE_SEAL
         and decision["archivedReferenceRawSha256"]==ORIGINAL_REFERENCE_SHA
         and decision["ownerDirectionAuthenticatedOnGitHub"] is False
         and bundle["nativeQualified"] is False
         and bundle["origin"]=="analytical_reference_only"
         and bundle["seal"]==ORIGINAL_REFERENCE_SEAL,
         "approved checking data must not be a native observation")
    study=load_study(root/STUDY,root/"h1/cases")
    need(study.sha256==MODAL_STUDY_SHA and
         study.model_sha256==ORIGINAL_MODEL_SHA and
         study.request_report["admitted"] is True
         and len(study.data["requests"])==9,
         "original modal public observation description drift")
    exports=internal_exports(study.model)
    need(len(exports)==37 and len(set(exports))==37
         and tuple(sorted(exports))==tuple(exports)
         and set(exports)==set(bundle["columns"])
         and set(exports)==set(bundle["units"])
         and set(exports)==set(bundle["owners"])
         and set(exports)==set(bundle["allowances"]),
         "37 original mandatory model exports differ from analytical reference")
    integrals=_integral_names(study)
    need(len(integrals)==4 and set(integrals)==set(bundle["flowIntegrals"])
         and set(integrals)==set(bundle["quadratureAllowances"]),
         "expected four body/boundary energy-integral histories differ")
    grid=bundle["grid"]
    need(len(grid)==4001 and len(study.grid)==4001
         and tuple(grid)==tuple(study.grid)
         and study.data["analysis"]["intervals"]==4000
         and len(study.request_report["requests"])==9
         and all(r["status"]=="not_computed"
                 for r in study.request_report["requests"]),
         "saved analytical grid/request statuses differ")
    need(all(len(bundle["columns"][k])==len(grid) for k in exports)
         and all(len(bundle["flowIntegrals"][k])==len(grid)
                 for k in integrals),
         "saved original analytical series shape mismatch")
    return held,decision,bundle,study,exports,integrals


def inventory(*,root: Path=ROOT) -> dict:
    """Return ONLY expected names, units and counts; zero native values."""
    held,decision,bundle,study,exports,integrals=_basis(root)
    requests=[]
    for authored,checked in zip(study.data["requests"],
                               study.request_report["requests"],strict=True):
        need(checked["id"]==authored["id"]
             and checked["status"]=="not_computed"
             and checked["unit"] in ("K","W","J"),
             "public request identity/units changed")
        requests.append({
            "id":authored["id"],
            "operation":authored["op"],
            "authoredOperands":{k:v for k,v in authored.items()
                                if k not in ("id","op")},
            "unit":checked["unit"],
            "nativeStatus":"not_computed",
            "nativeValue":None,
        })
    columns=[
        {"name":key,"analyticalCheckingUnit":bundle["units"][key],
         "savedAnalyticalReferenceSamples":len(bundle["columns"][key]),
         "nativeStatus":"not_computed","observedNativeSamples":None}
        for key in exports
    ]
    flows=[
        {"name":key,"savedAnalyticalIntegralSamples":len(bundle["flowIntegrals"][key]),
         "nativeStatus":"not_computed","observedNativeSamples":None}
        for key in integrals
    ]
    report={
        "schema":SCHEMA,
        "status":STATUS,
        "sourceCase":"H1_C1_MODAL",
        "originalModelSha256":ORIGINAL_MODEL_SHA,
        "modalStudySha256":MODAL_STUDY_SHA,
        "originalSavedReferenceRawSha256":ORIGINAL_REFERENCE_SHA,
        "originalSavedReferenceSeal":ORIGINAL_REFERENCE_SEAL,
        "referenceOrigin":"analytical_reference_only",
        "referenceUse":"approved_for_offline_checking_only",
        "sourcePinsVerified":held["sourcePinsVerified"],
        "analyticalGridSamples":len(bundle["grid"]),
        "expectedModelExportCount":len(columns),
        "expectedModelExports":columns,
        "expectedIntegralCount":len(flows),
        "expectedFlowIntegrals":flows,
        "publicRequestCount":len(requests),
        "publicRequests":requests,
        "nativeObservationCount":0,
        "nativePublicRequestsStillNotComputed":len(requests),
        "nativeExportSeriesObtained":0,
        "nativeIntegralSeriesObtained":0,
        "releaseBlocked":True,
        "missingNativeReleaseGates":held["missingRequiredNativeReleaseGates"],
        **{field:False for field in REAL_NATIVE_FALSE},
        "limitations":[
            "37 names, 4 histories and 9 public requests are EXPECTED only",
            "4001 points apply ONLY to the saved checking reference, not observed OMC output",
            "No native MAT/CSV or 37 actual native exports have been read or decoded",
            "All 11 owner/release/host/adapter/external-CAS/native prerequisites remain MISSING",
            "A successful offline report never qualifies physics or authorizes native launch",
        ]
    }
    validate_shape(report)
    return report


def validate_shape(report: dict):
    """Defensive denial assertion, not any authenticated trust or approval."""
    need(type(report) is dict
         and report.get("schema")==SCHEMA
         and report.get("status")==STATUS
         and report.get("releaseBlocked") is True
         and report.get("referenceOrigin")=="analytical_reference_only"
         and report.get("referenceUse")=="approved_for_offline_checking_only"
         and report.get("originalModelSha256")==ORIGINAL_MODEL_SHA
         and report.get("modalStudySha256")==MODAL_STUDY_SHA
         and report.get("originalSavedReferenceRawSha256")==ORIGINAL_REFERENCE_SHA
         and report.get("originalSavedReferenceSeal")==ORIGINAL_REFERENCE_SEAL,
         "expected-coverage report source/provenance drift")
    for field in REAL_NATIVE_FALSE:
        need(report.get(field) is False,
             "native claim must be literal false: "+field)
    need(type(report.get("analyticalGridSamples")) is int
         and report["analyticalGridSamples"]==4001
         and type(report.get("expectedModelExportCount")) is int
         and report["expectedModelExportCount"]==37
         and type(report.get("expectedIntegralCount")) is int
         and report["expectedIntegralCount"]==4
         and type(report.get("publicRequestCount")) is int
         and report["publicRequestCount"]==9,
         "non-native expected dimensions drift")
    for field in ("nativeObservationCount","nativeExportSeriesObtained",
                  "nativeIntegralSeriesObtained"):
        need(type(report.get(field)) is int and report[field]==0,
             "native series cannot be forged: "+field)
    need(type(report.get("nativePublicRequestsStillNotComputed")) is int
         and report["nativePublicRequestsStillNotComputed"]==9,
         "nine native public requests have NOT been computed")
    for group,n,label in (("expectedModelExports",37,"export"),
                          ("expectedFlowIntegrals",4,"integral"),
                          ("publicRequests",9,"request")):
        data=report.get(group)
        need(type(data) is list and len(data)==n
             and len(set(x["name"] if label!="request" else x["id"] for x in data))==n,
             "expected "+label+" inventory not unique/exact count")
        for item in data:
            need(item.get("nativeStatus")=="not_computed",
                 "forged native "+label+" observation")
            value=("nativeValue" if label=="request" else "observedNativeSamples")
            need(value in item and item[value] is None,
                 "native "+label+" value/samples must be literal null")
    need(type(report.get("missingNativeReleaseGates")) is list
         and len(report["missingNativeReleaseGates"])==11,
         "missing genuine real release gates")


def assert_exact_expected(candidate: dict, *,root: Path=ROOT):
    """No parsed-dict bool/int/float equality bypasses exact source contract."""
    required=inventory(root=root)
    validate_shape(candidate)
    need(encoded(candidate)==encoded(required),
         "expected analytical/native-absent inventory differs from original")
    return True


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("describe-expected-only",))
    args=parser.parse_args(argv)
    try:
        print(json.dumps(inventory(),sort_keys=True,indent=2,allow_nan=False))
        return 0 # Expected-data coverage inventory ONLY, not native success.
    except Exception as exc:
        print(json.dumps({
            "schema":SCHEMA,
            "status":"REFUSED_EXPECTED_OR_UNTRUSTED_NATIVE_COVERAGE",
            "reason":type(exc).__name__+": "+str(exc),
            "releaseBlocked":True,"nativeAllowed":False,
            "nativeExecuted":False,"nativeQualified":False,
            "nativePublicRequestsStillNotComputed":9,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
