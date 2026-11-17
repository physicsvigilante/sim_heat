"""H1-C1-F02 OFFLINE authored-request -> expected export DEPENDENCY map.

Sources: original frozen H1 Modelica model/study, h1/model.py request/port
rules and h1/verification.py candidate observation projection logic, all
independently reviewed/pinned via the inherited expected-coverage consumer.
Only names, signs, units and source provenance; NO NUMERICAL PROJECTION.
No MAT, CSV, OMC, native runner, reference.prepare, new reference, owner
launch approval, native values or actual physical qualification.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from h1.study import load_study
from qualification.h1_c1.f02 import offline_expected_export_coverage as expected

ROOT=Path(__file__).resolve().parents[3]
SCHEMA="sim_heat.h1_c1_f02_offline_public_request_dependencies/1"
STATUS="PUBLIC_REQUEST_DEPENDENCIES_EXPECTED_ONLY_NATIVE_NOT_COMPUTED"
VALID_KINDS=("Body","FixedTemperature","RodArea","RodCircular")
FROZEN_VERIFICATION_RULE="h1/verification.py:check_candidate(port_key/observations)"
FALSE_FLAGS=(
    "nativeAllowed","nativeExecuted","nativeQualified","realNativeSamplesAvailable",
    "publicReadingsComputed","modelBuilt","compilerQueried","matDecoded",
    "referenceRegenerated","ownerNativeLaunchApproved",
    "realAcrossRunReservationAllocated",
    "originalF0Strict100xPassed","pr32BitwiseRegenerationPassed",
)


class DependencyRefusal(ValueError):
    pass


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise DependencyRefusal(reason)


def encoded(doc: dict) -> bytes:
    try:
        return (json.dumps(doc,sort_keys=True,indent=2,
                           allow_nan=False,ensure_ascii=True)+"\n").encode()
    except (ValueError,TypeError,OverflowError,RecursionError) as exc:
        raise DependencyRefusal("invalid serialized offline dependency report") from exc


def _port_key(model, port: str) -> str:
    """Exact NAME rule from frozen h1.verification.check_candidate.port_key.

    This is a string projection only. It cannot determine a real OMC export
    from a MAT file or prove the numeric equality of joined port signals.
    """
    need(type(port) is str and port in model.ports()
         and port.count(".")==1,
         "request port is not in frozen authored Modelica")
    component,member=port.split(".")
    kind=model.components[component].kind
    need(kind in VALID_KINDS,"unsupported frozen component for port")
    if kind in ("Body","FixedTemperature"):
        need(member=="port","invalid thermal storage/bath port")
        return component+".T"
    need(kind in ("RodArea","RodCircular")
         and member in ("port_a","port_b"),
         "invalid frozen rod port")
    return component+(".T_a" if member=="port_a" else ".T_b")


def _terms(study, authored: dict) -> tuple[str,list[dict]]:
    """Freeze semantics: direct model fields or ordered T(a)-T(b) only."""
    model=study.model
    op=authored["op"]
    if op=="temperature":
        key=_port_key(model,authored["target"])
        return "direct_expected_model_export",[{"exportName":key,"sign":1}]
    if op=="heatFlow":
        target=authored["target"]
        need(target in model.components and
             model.components[target].kind in ("RodArea","RodCircular"),
             "heatFlow target must be authored conducting rod")
        return "direct_expected_model_export",[
            {"exportName":target+".Q_flow","sign":1}]
    if op=="energyChange":
        target=authored["target"]
        need(target in model.components and
             model.components[target].kind=="Body",
             "energyChange must target authored Body")
        return "direct_expected_model_export",[
            {"exportName":target+".dU","sign":1}]
    if op=="temperatureDifference":
        a=_port_key(model,authored["a"])
        b=_port_key(model,authored["b"])
        need(a!=b,"temperature difference must have two distinct source fields")
        return "ordered_difference_of_two_expected_exports",[
            {"exportName":a,"sign":1},
            {"exportName":b,"sign":-1}]
    raise DependencyRefusal("unsupported original public observation operation")


def _source_bound(root: Path):
    """Full original source and saved analytical checking-bundle verification."""
    base=expected.inventory(root=root) # owner Option A OFFLINE-only and 11-gate HOLD.
    need(base["status"]==expected.STATUS
         and base["releaseBlocked"] is True
         and base["nativeObservationCount"]==0
         and base["nativePublicRequestsStillNotComputed"]==9
         and base["nativeExportSeriesObtained"]==0
         and base["nativeIntegralSeriesObtained"]==0
         and len(base["missingNativeReleaseGates"])==11,
         "expected-only original coverage became purported native evidence")
    study=load_study(root/expected.STUDY,root/"h1/cases")
    need(study.sha256==expected.MODAL_STUDY_SHA
         and study.model_sha256==expected.ORIGINAL_MODEL_SHA
         and study.request_report["admitted"] is True
         and len(study.data["requests"])==9,
         "frozen authored Modelica or modal study changed")
    exports={r["name"]:r for r in base["expectedModelExports"]}
    need(len(exports)==37
         and all(r["nativeStatus"]=="not_computed"
                 and r["observedNativeSamples"] is None for r in exports.values()),
         "expected model field inventory or native zero count changed")
    return base,study,exports


def inventory(*,root: Path=ROOT) -> dict:
    """Only dependency NAMES and SIGN labels, zero numerical values."""
    root=Path(root).resolve(strict=True)
    base,study,exports=_source_bound(root)
    dependencies=[]
    for authored,checked,original in zip(
            study.data["requests"],study.request_report["requests"],
            base["publicRequests"],strict=True):
        need(checked["status"]=="not_computed"
             and checked["id"]==authored["id"]
             and original["id"]==authored["id"]
             and original["operation"]==authored["op"]
             and original["unit"]==checked["unit"]
             and original["nativeStatus"]=="not_computed"
             and original["nativeValue"] is None,
             "original request identity was altered or promoted to observed")
        kind,terms=_terms(study,authored)
        need(len(terms) in (1,2)
             and len({t["exportName"] for t in terms})==len(terms)
             and all(t["exportName"] in exports for t in terms),
             "request has missing or duplicate required expected export")
        unit=checked["unit"]
        need(all(exports[t["exportName"]]["analyticalCheckingUnit"]==unit
                 for t in terms),
             "source operation/expected export units mismatch")
        need(kind=="ordered_difference_of_two_expected_exports" or
             (len(terms)==1 and terms[0]["sign"]==1),
             "unsupported direct-export sign")
        dependencies.append({
            "id":authored["id"],
            "operation":authored["op"],
            "authoredOperands":{k:v for k,v in authored.items()
                                if k not in ("id","op")},
            "expectedUnit":unit,
            "dependencyKind":kind,
            "orderedExpectedExportTerms":terms,
            "sourceRule":FROZEN_VERIFICATION_RULE,
            "expectedOnly":True,
            "nativeStatus":"not_computed",
            "nativeValue":None,
        })
    need(len(dependencies)==9
         and len({x["id"] for x in dependencies})==9
         and sum(x["dependencyKind"]=="ordered_difference_of_two_expected_exports"
                 for x in dependencies)==1
         and sum(x["dependencyKind"]=="direct_expected_model_export"
                 for x in dependencies)==8,
         "original nine public projections differ from approved request contract")
    report={
        "schema":SCHEMA,
        "status":STATUS,
        "sourceCase":"H1_C1_MODAL",
        "originalModelSha256":base["originalModelSha256"],
        "modalStudySha256":base["modalStudySha256"],
        "originalSavedReferenceRawSha256":base["originalSavedReferenceRawSha256"],
        "originalSavedReferenceSeal":base["originalSavedReferenceSeal"],
        "checkingReferenceOrigin":"analytical_reference_only",
        "projectionSource":FROZEN_VERIFICATION_RULE,
        "expectedModelExportCount":37,
        "expectedPublicRequestCount":9,
        "directExpectedModelFieldRequests":8,
        "derivedTemperatureDifferenceRequests":1,
        "expectedSourceTermCount":sum(len(x["orderedExpectedExportTerms"])
                                      for x in dependencies),
        "publicRequestDependencies":dependencies,
        "expectedOnly":True,
        "nativeObservationCount":0,
        "nativePublicRequestsStillNotComputed":9,
        "nativeExportSeriesObtained":0,
        "nativeIntegralSeriesObtained":0,
        "nativePublicValues":None,
        "missingNativeReleaseGates":base["missingNativeReleaseGates"],
        "releaseBlocked":True,
        **{field:False for field in FALSE_FLAGS},
        "limits":[
            "Only frozen source-defined FIELD DEPENDENCIES; NO public values are evaluated",
            "Direct mapping describes intended expected exports, not observed OMC availability",
            "Temperature difference is first temperature minus second; no numeric subtraction run",
            "Expected Modelica sign/orientation labels do not prove physical native correctness",
            "Actual nine native public values remain not_computed and eleven gates absent",
        ],
    }
    validate_shape(report)
    return report


def validate_shape(doc: dict) -> None:
    """Syntactic denial guard only. NOT a trusted exact source/provenance test."""
    need(type(doc) is dict and doc.get("schema")==SCHEMA
         and doc.get("status")==STATUS
         and doc.get("expectedOnly") is True
         and doc.get("checkingReferenceOrigin")=="analytical_reference_only"
         and doc.get("releaseBlocked") is True
         and doc.get("nativePublicValues") is None,
         "not an uncomputed original projection report")
    for key in FALSE_FLAGS:
        need(doc.get(key) is False, "native claim must be literal false: "+key)
    for key,value in (
        ("expectedModelExportCount",37),
        ("expectedPublicRequestCount",9),
        ("directExpectedModelFieldRequests",8),
        ("derivedTemperatureDifferenceRequests",1),
        ("expectedSourceTermCount",10),
        ("nativeObservationCount",0),
        ("nativePublicRequestsStillNotComputed",9),
        ("nativeExportSeriesObtained",0),
        ("nativeIntegralSeriesObtained",0),
    ):
        need(type(doc.get(key)) is int and doc[key]==value,
             "inconsistent source-derived expected/native count: "+key)
    need(type(doc.get("missingNativeReleaseGates")) is list
         and len(doc["missingNativeReleaseGates"])==11,
         "eleven actual release prerequisites must remain missing")
    rows=doc.get("publicRequestDependencies")
    need(type(rows) is list and len(rows)==9
         and len({r.get("id") for r in rows if type(r) is dict})==9,
         "duplicate/missing public request dependency rows")
    for row in rows:
        need(type(row) is dict and row.get("expectedOnly") is True
             and row.get("nativeStatus")=="not_computed"
             and row.get("nativeValue") is None
             and row.get("sourceRule")==FROZEN_VERIFICATION_RULE,
             "native public value/operation falsely determined")
        terms=row.get("orderedExpectedExportTerms")
        need(type(terms) is list and len(terms) in (1,2)
             and all(type(t) is dict
                     and set(t)=={"exportName","sign"}
                     and type(t["exportName"]) is str
                     and type(t["sign"]) is int
                     and t["sign"] in (-1,1) for t in terms),
             "malformed expected source term/sign")


def assert_exact_source_bound(candidate: dict, *,root: Path=ROOT):
    """Use this (not shape-only) for any proposed copied dependency document."""
    validate_shape(candidate)
    original=inventory(root=root)
    need(encoded(candidate)==encoded(original),
         "untrusted projection differs from exact authored scientific source")
    return True


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("describe-dependencies-only",))
    args=p.parse_args(argv)
    try:
        print(json.dumps(inventory(),sort_keys=True,indent=2,allow_nan=False))
        return 0 # Informational expected dependency list, never native PASS.
    except Exception as exc:
        print(json.dumps({
            "schema":SCHEMA,
            "status":"REFUSED_UNTRUSTED_REQUEST_PROJECTION",
            "reason":type(exc).__name__+": "+str(exc),
            "releaseBlocked":True,
            "nativeAllowed":False,"nativeExecuted":False,
            "nativeQualified":False,
            "nativePublicRequestsStillNotComputed":9,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
