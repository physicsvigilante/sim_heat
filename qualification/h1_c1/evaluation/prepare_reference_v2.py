#!/usr/bin/env python3
"""Prospective H1-C1 V2 checking-only reference; not Modelica or native evidence.

Frozen h1.reference prepares a NEW bundle from the unmodified physical spec.
Only hotLead.G static export is independently rounded from exact decimal task
facts (9/20). The bundle is separately sealed and never overwrites old evidence.
An independent 80-digit two-state solution checks ALL 37 columns x 4001
timestamps against the unchanged 100x reference-error budgets.
"""
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys

import mpmath as mp
import numpy as np
import scipy
from h1 import reference

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "qualification/h1_c1/evaluation"
SPEC = BASE / "C1_FIRST_CHECKING_REFERENCE.json"
PLAN = BASE / "C1_PRIMARY_NATIVE_PLAN_NOT_LAUNCHED.json"
MODEL = ROOT / "h1/cases/H1_C1_MODAL/model.mo"
STUDY = ROOT / "h1/cases/H1_C1_MODAL/study.json"
SOURCE_SHA = "1b4b497d7427deae9e83fd712fbe9119e0c8e6599212d7762c828eca10b594c9"
PLAN_SHA = "f46b2621b38427ffc098d16d91695a134b7dc4d7f913021be625ee74b8a9319a"
OLD_SEAL = "d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b"
MODEL_SHA = "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
STUDY_SHA = "b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"
OUTPUT_KEY = "hotLead.G"
mp.mp.dps = 85


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rational_decimal(x):
    return Fraction(Decimal(x))


def mp_num(x):
    # String conversion is intentional for authored decimal SI physical facts.
    return mp.mpf(str(x))


def assemble_independent_physics(spec):
    # Separate exact-decimal task representation; not Modelica parser.
    bodies, baths, rods = spec["bodies"], spec["boundaries"], spec["rods"]
    assert set(bodies) == {"leftBuffer", "rightBuffer"}
    assert set(baths) == {"hotBath", "coldBath"}
    assert set(rods) == {"hotLead", "flatBridge", "roundBridge", "coldLead"}
    assert [(rods[n]["a"], rods[n]["b"]) for n in rods] == [
        ("H","L"),("L","R"),("L","R"),("R","C")]
    q = mp_num
    C1 = q(bodies["leftBuffer"]["m"]) * q(bodies["leftBuffer"]["c"])
    C2 = q(bodies["rightBuffer"]["m"]) * q(bodies["rightBuffer"]["c"])
    area = {}
    g = {}
    for name, rod in rods.items():
        A = q(rod["A"]) if rod["kind"] == "RodArea" else mp.pi * q(rod["d"])**2 / 4
        area[name] = A
        g[name] = q(rod["k"]) * A / q(rod["L"])
    assert g["hotLead"] == mp.mpf(9)/20
    gb = g["flatBridge"] + g["roundBridge"]
    T_H = q(baths["hotBath"]["T"])
    T_C = q(baths["coldBath"]["T"])
    L0 = q(bodies["leftBuffer"]["T_initial"])
    R0 = q(bodies["rightBuffer"]["T_initial"])
    A = mp.matrix([[-(g["hotLead"]+gb)/C1, gb/C1],
                   [gb/C2, -(gb+g["coldLead"])/C2]])
    f = mp.matrix([g["hotLead"]*T_H/C1, g["coldLead"]*T_C/C2])
    t0 = mp.matrix([L0,R0])
    steady = -mp.inverse(A)*f
    a,d = A[0,0],A[1,1]
    discr = mp.sqrt((a-d)**2 + 4*A[0,1]*A[1,0])
    slow = -(a+d+discr)/2
    fast = -(a+d-discr)/2
    assert slow > 0 and fast > slow
    I = mp.eye(2)
    slowP = (A+fast*I)/(fast-slow)
    fastP = (A+slow*I)/(slow-fast)
    ds = slowP*(t0-steady)
    df = fastP*(t0-steady)
    return locals()


def exact_at(t, p):
    t=mp.mpf(t)  # float->mp conversion is exact binary physical grid instant
    e1=mp.exp(-p["slow"]*t)
    e2=mp.exp(-p["fast"]*t)
    T=p["steady"]+p["ds"]*e1+p["df"]*e2
    integrated=p["steady"]*t + p["ds"]*(-mp.expm1(-p["slow"]*t))/p["slow"] + p["df"]*(-mp.expm1(-p["fast"]*t))/p["fast"]
    nodes={"H":p["T_H"],"L":T[0],"R":T[1],"C":p["T_C"]}
    int_nodes={"H":p["T_H"]*t,"L":integrated[0],"R":integrated[1],"C":p["T_C"]*t}
    out={}
    integ={}
    body_in={"L":mp.mpf(0),"R":mp.mpf(0)}
    for name,rod in p["rods"].items():
        a,b=rod["a"],rod["b"]
        g=p["g"][name]
        flow=g*(nodes[a]-nodes[b])
        out.update({name+".T_a":nodes[a], name+".T_b":nodes[b],
                    name+".Q_flow":flow,name+".port_a.Q_flow":flow,
                    name+".port_b.Q_flow":-flow,name+".G":g})
        if rod["kind"]=="RodCircular":
            out[name+".A"]=p["area"][name]
        if a in body_in:
            body_in[a]-=flow
        if b in body_in:
            body_in[b]+=flow
        integ[name]=g*(int_nodes[a]-int_nodes[b])
    for name,body in p["bodies"].items():
        n=body["node"]
        C=p["C1"] if n=="L" else p["C2"]
        out[name+".T"]=nodes[n]
        out[name+".Q_in"]=body_in[n]
        out[name+".C"]=C
        out[name+".dU"]=C*(nodes[n]-mp_num(body["T_initial"]))
    for name,bath in p["baths"].items():
        n=bath["node"]
        out[name+".T"]=nodes[n]
        # Q_to_network is net leaving fixed-temperature boundary.
        out[name+".Q_to_network"]=(p["g"]["hotLead"]*(nodes["H"]-nodes["L"])
                                   if n=="H" else
                                   p["g"]["coldLead"]*(nodes["C"]-nodes["R"]))
    return out, integ


def make_candidate(spec):
    bundle=reference.prepare(spec)   # original pinned F0 code, no modifications
    assert bundle["schema"]=="sim_heat.reference_bundle/2"
    assert bundle["origin"]=="analytical_reference_only" and bundle["nativeQualified"] is False
    assert set(bundle["columns"]) and len(bundle["columns"])==37
    vals=bundle["columns"][OUTPUT_KEY]
    assert len(vals)==4001 and all(x == 0.44999999999999996 for x in vals)
    exact = rational_decimal("150")*rational_decimal("0.00030")/rational_decimal("0.10")
    assert exact==Fraction(9,20)
    corrected=float(Decimal("0.45"))
    allowance=bundle["allowances"][OUTPUT_KEY]
    assert allowance == 64*math.ulp(vals[0])
    error=abs(Fraction.from_float(corrected)-exact)
    assert error <= Fraction.from_float(allowance)/100
    original_seal=bundle["seal"]
    bundle["columns"][OUTPUT_KEY]=[corrected]*len(vals)
    bundle["method"]["staticExportRoundingV2"]={
       "schema":"sim_heat.c1_static_export_rounding/1",
       "field":OUTPUT_KEY,
       "exactDecimalTaskConductance":"9/20 W/K",
       "binary64Value":repr(corrected),
       "derivation":"exact decimal rational k*A/L rounded once to nearest binary64",
       "oldF0SealedValue":repr(vals[0]),
       "oldF0ArchivedSeal":OLD_SEAL,
       "sourceF0RepreparedSeal":original_seal,
       "status":"new_versioned_checking_only_reference_not_native"
    }
    bundle.pop("seal")
    bundle["seal"]=reference.fingerprint(bundle)
    return bundle


def independent_validate(bundle, spec):
    p=assemble_independent_physics(spec)
    grid=bundle["grid"]
    cols=bundle["columns"]
    assert len(grid)==4001 and len(cols)==37 and grid[0]==0.0
    assert grid[-1]==spec["analysis"]["stopTime"]
    assert all(grid[i] < grid[i+1] for i in range(len(grid)-1))
    assert set(cols)==set(bundle["allowances"])==set(bundle["units"])
    errmax={name:mp.mpf(0) for name in cols}
    ratio_max=mp.mpf(0)
    at={"index":0,"field":""}
    integral_worst={}
    for idx,t in enumerate(grid):
        expected, integral=exact_at(t,p)
        assert set(expected)==set(cols), (set(expected)^set(cols))
        for name,val in expected.items():
            actual=cols[name][idx]
            assert math.isfinite(actual)
            eps=bundle["allowances"][name]
            assert eps>0 and math.isfinite(eps)
            error=abs(mp.mpf(actual)-val)
            limit=mp.mpf(eps)/100
            assert error <= limit, (
                "strict 100x reference error",name,idx,str(error),str(limit))
            if error>errmax[name]: errmax[name]=error
            ratio=error/mp.mpf(eps)
            if ratio>ratio_max:
                ratio_max=ratio;at={"index":idx,"field":name}
        # Reference integral checks are independent of the frozen F0 integrator.
        expected_integrals={
          "leftBuffer.Q_in":p["C1"]*(expected["leftBuffer.T"]-p["L0"]),
          "rightBuffer.Q_in":p["C2"]*(expected["rightBuffer.T"]-p["R0"]),
          "hotBath.Q_to_network":integral["hotLead"],
          "coldBath.Q_to_network":-integral["coldLead"]
        }
        for key,ideal in expected_integrals.items():
            stored=mp.mpf(bundle["flowIntegrals"][key][idx])
            error=abs(stored-ideal)
            scale=mp.mpf(max(abs(z) for z in bundle["flowIntegrals"][key]))
            budget=(mp.mpf("1e-3")+mp.mpf("1e-6")*scale)/100
            assert error<=budget,("integral strict 100x",key,idx,str(error),str(budget))
            integral_worst[key]=max(integral_worst.get(key,mp.mpf(0)),error)
    assert ratio_max <= mp.mpf("0.01")
    return {
      "allColumns":37,
      "allTimeSamples":4001,
      "assessedScalarValues":37*4001,
      "maxReferenceErrorFractionOfNativeAllowance":float(ratio_max),
      "maxReferenceErrorAt":at,
      "all37ColumnsStrict100xPass":True,
      "maximumErrorByColumn":{k:float(v) for k,v in sorted(errmax.items())},
      "maximumFlowIntegralErrorJ":{k:float(v) for k,v in sorted(integral_worst.items())},
      "independentMethod":"85-decimal-digit affine 2x2 spectral projectors, exact decimal task inputs",
      "staticReferenceCorrectionStrictMarginX":320
    }


def run(outdir):
    assert sha(SPEC)==SOURCE_SHA and sha(PLAN)==PLAN_SHA
    assert sha(MODEL)==MODEL_SHA and sha(STUDY)==STUDY_SHA
    plan=json.loads(PLAN.read_text())
    assert len(plan["pins"])==23
    for name,expected in plan["pins"].items():
        assert sha(ROOT/name)==expected,("frozen pin changed",name)
    spec=reference.read_reference(SPEC)
    candidate=make_candidate(spec)
    validation=independent_validate(candidate,spec)
    # A new checking-only bundle, not replacing the original F0 historical seal.
    assert candidate["seal"] != OLD_SEAL
    assert candidate["method"]["staticExportRoundingV2"]["oldF0ArchivedSeal"]==OLD_SEAL
    # On the same clean process, check that two full preparations have equal
    # canonical seals. If not, preserve BOTH artifacts before marking REFUSED.
    second=make_candidate(spec)
    same=candidate["seal"]==second["seal"]
    outdir.mkdir(parents=True,exist_ok=True)
    for key,value in [("C1_REFERENCE_V2_BUNDLE.json",candidate),
                      ("C1_REFERENCE_V2_REPEAT_BUNDLE.json",second)]:
        with (outdir/key).open("x",encoding="utf-8") as f:
            f.write(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n")
    method_diff=None
    if not same:
        method_diff={
          "columnNamesDiffering":[key for key in candidate["columns"]
                                  if candidate["columns"][key]!=second["columns"][key]],
          "methodDiffers":candidate["method"]!=second["method"],
          "allowancesDiffer":candidate["allowances"]!=second["allowances"],
          "integralsDiffer":candidate["flowIntegrals"]!=second["flowIntegrals"]
        }
    result={
      "schema":"sim_heat.c1_v2_reference_preparation/1",
      "status":"offline_checking_reference_prospective_not_native" if same
               else "REFUSED_NONREPRODUCIBLE_CHECKING_REFERENCE",
      "nativeExecuted":False,"nativeQualified":False,
      "originalFrozenSourceChanged":False,"firstAuthorFilesChanged":False,
      "originalReferenceSealedBytesChanged":False,
      "originalF0BundleSeal":OLD_SEAL,
      "firstRepreparedF0Seal":candidate["method"]["staticExportRoundingV2"]["sourceF0RepreparedSeal"],
      "newV2BundleSeal":candidate["seal"],
      "repeatV2BundleSeal":second["seal"],
      "repeatEqual":same,
      "reproducibilityDifferences":method_diff,
      "originalPhysicalInputSha256":SOURCE_SHA,
      "oldUnlaunchedNativePlanSha256":PLAN_SHA,
      "referenceVerification":validation,
      "environment":{"python":sys.version.split()[0],"numpy":np.__version__,
                     "scipy":scipy.__version__,"mpmath":mp.__version__,
                     "platform":platform.platform(),
                     "machine":platform.machine(),
                     "processor":platform.processor(),
                     "openblas":str(np.show_runtime())},
      "limits":["Two preparations on one CI host cannot certify cross-host determinism.",
                "Never use an unlaunched old plan with this new seal.",
                "No actual Modelica trace, native qualification, or authorized native attempt."]
    }
    with (outdir/"C1_REFERENCE_V2_REPORT.json").open("x",encoding="utf-8") as f:
        f.write(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n")
    if not same:
        raise RuntimeError("V2 checking-only reference seals disagree; see preserved report")
    return result


if __name__=="__main__":
    assert len(sys.argv)==2, "supply a new clean output directory"
    result=run(Path(sys.argv[1]))
    print(json.dumps({"status":result["status"],"seal":result["newV2BundleSeal"],
                      "strict100x":result["referenceVerification"]["all37ColumnsStrict100xPass"],
                      "repeatEqual":result["repeatEqual"],
                      "nativeExecuted":False},sort_keys=True))
