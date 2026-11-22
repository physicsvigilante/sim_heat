"""H1-N10: independent high-precision DYNAMIC replay of original T1-T facts.

OFFLINE, checking-only cross-implementation corroboration. Reconstruct a
generic thermal graph and augmented linear ODE directly from source-exact
N4-parsed physical facts; mpmath expm is independent of N1's Schur/interval
Taylor implementation. It is NOT a rigorous independently certified error
bound, runner reference, native observation, or release authority.

The only production of N1 values is a disposable rerun of its unchanged
source-only candidate. Its original full trace SHA must match BEFORE any
comparison. No native CSV/MAT, h1.reference, or Modelica execution is read.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from mpmath import mp

from qualification.h1_n1 import certified_reference as n1
from qualification.h1_n4.static_physical import parse_facts
from qualification.h1_n9.static_trace_crosscheck import (
    ORIGINAL_GRID_HASHES, verify_historical_grid,
    EXPECTED_LEGACY_FAILURES,
)

ROOT = Path(__file__).resolve().parents[2]
FACTS_PATH = ROOT / "qualification/h1_n1/reference-facts.json"
AUTHOR_DIR = ROOT / "qualification/h1_n1/inputs/T"
SOURCE_FACTS_SHA = "39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf"
MODEL_SHA = "2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae"
STUDY_SHA = "12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a"
SCHEMA = "sim_heat.h1_n10.independent_dynamic_replay_candidate/1"
PHYSICAL_INTERVAL_SECONDS = 2400
DECIMAL_PRECISION = 90


class ReplayRefusal(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise ReplayRefusal("h1_n10: " + reason)


def mp_source(value):
    """Source integers/Decimals, not pre-rounded Python binary floats."""
    need(type(value) in (int, Decimal), "source number must be exact decimal or integer")
    result = mp.mpf(str(value))
    need(mp.isfinite(result), "nonfinite physical source")
    return result


def load_original():
    raw = FACTS_PATH.read_bytes()
    need(sha256(raw).hexdigest() == SOURCE_FACTS_SHA, "T1-T physical source facts drifted")
    for name, digest in (("model.mo", MODEL_SHA), ("study.json", STUDY_SHA)):
        need(sha256((AUTHOR_DIR / name).read_bytes()).hexdigest() == digest,
             "first authored source differs: " + name)
    facts = parse_facts(raw, expected_sha256=SOURCE_FACTS_SHA)
    need(facts["id"] == "H1T1TFirstAttemptV1"
         and facts["modelSha256"] == MODEL_SHA
         and facts["studySha256"] == STUDY_SHA
         and facts["mode"] == "transient"
         and facts["analysis"]["stopTime"] == 2400,
         "source/analysis identity mismatch")
    # The actual original public request inventory comes from first-author
    # study bytes, not an N1 request implementation or synthetic answer map.
    study = json.loads((AUTHOR_DIR / "study.json").read_bytes())
    need(type(study) is dict and type(study.get("requests")) is list
         and len(study["requests"]) == 8, "original authored requests unavailable")
    return facts, study["requests"]


def assemble(facts):
    """Own graph Laplacian, junction elimination and 2n+1 affine ODE.

    Input is already N4-admitted source facts; this function independently
    reconstructs physics, not its per-component static answer/graph output.
    The generic source helper here is testable with reversed rod orientations.
    """
    nodes = list(facts["nodes"])
    bodies = facts["bodies"]
    boundaries = facts["boundaries"]
    rods = facts["rods"]
    need(len(nodes) == len(set(nodes)) and 0 < len(bodies) <= 8,
         "invalid physical node/body count")
    body_names, boundary_names = sorted(bodies), sorted(boundaries)
    dnodes = [bodies[name]["node"] for name in body_names]
    fnodes = [boundaries[name]["node"] for name in boundary_names]
    jnodes = [name for name in nodes if name not in set(dnodes+fnodes)]
    need(len(set(dnodes+fnodes+jnodes)) == len(nodes)
         and set(dnodes+fnodes+jnodes) == set(nodes),
         "node ownership mismatch")
    ids = {name: index for index, name in enumerate(nodes)}
    lap = mp.matrix(len(nodes))
    conductances, areas = {}, {}
    for name, rod in sorted(rods.items()):
        k = mp_source(rod["k"])
        L = mp_source(rod["L"])
        if rod["kind"] == "RodArea":
            A = mp_source(rod["A"])
        else:
            diameter = mp_source(rod["d"])
            A = mp.pi * diameter * diameter / 4
            areas[name] = A
        G = k*A/L
        need(mp.isfinite(G) and G > 0, "nonpositive source conductance: " + name)
        conductances[name] = G
        a, b = ids[rod["a"]], ids[rod["b"]]
        need(a != b, "rod must connect distinct nodes")
        lap[a,a] += G
        lap[b,b] += G
        lap[a,b] -= G
        lap[b,a] -= G

    j_to_d = [[mp.zero for _ in dnodes] for _ in jnodes]
    j_to_f = [[mp.zero for _ in fnodes] for _ in jnodes]
    if jnodes:
        # Distinct from N1's fixed-size 2x2 explicit interval determinant.
        ljj = mp.matrix([[lap[ids[a], ids[b]] for b in jnodes] for a in jnodes])
        need(mp.det(ljj) > 0, "singular/nonpositive junction system")
        inverse = mp.inverse(ljj)
        for q in range(len(jnodes)):
            for col, node in enumerate(dnodes):
                j_to_d[q][col] = -sum(
                    (inverse[q,p]*lap[ids[jnodes[p]],ids[node]]
                     for p in range(len(jnodes))), mp.zero)
            for col, node in enumerate(fnodes):
                j_to_f[q][col] = -sum(
                    (inverse[q,p]*lap[ids[jnodes[p]],ids[node]]
                     for p in range(len(jnodes))), mp.zero)
    capacities = {
        name: mp_source(bodies[name]["m"])*mp_source(bodies[name]["c"])
        for name in body_names
    }
    fixed_values = [mp_source(boundaries[name]["T"]) for name in boundary_names]
    d = len(dnodes)
    ode = mp.matrix(2*d+1)
    for i, name in enumerate(body_names):
        C = capacities[name]
        need(C > 0, "nonpositive capacity")
        dn = dnodes[i]
        for k, node in enumerate(dnodes):
            coefficient = lap[ids[dn], ids[node]] + sum(
                (lap[ids[dn],ids[jnodes[j]]]*j_to_d[j][k]
                 for j in range(len(jnodes))), mp.zero)
            ode[i,k] = -coefficient / C
        forcing = mp.zero
        for k, node in enumerate(fnodes):
            coefficient = lap[ids[dn],ids[node]] + sum(
                (lap[ids[dn],ids[jnodes[j]]]*j_to_f[j][k]
                 for j in range(len(jnodes))), mp.zero)
            forcing += coefficient*fixed_values[k]
        ode[i,2*d] = -forcing/C
        ode[d+i,i] = 1  # independent body-temperature time integrals
    state0 = mp.matrix(
        [mp_source(bodies[name]["T_initial"]) for name in body_names]
        + [mp.zero]*d + [mp.one])
    need(all(ode[2*d,i] == 0 for i in range(2*d+1)),
         "affine final row must be identically zero")
    return dict(nodes=nodes, body_names=body_names, boundary_names=boundary_names,
                jnodes=jnodes, dnodes=dnodes, fnodes=fnodes, bodies=bodies,
                boundaries=boundaries, rods=rods, conductances=conductances,
                areas=areas, capacities=capacities, fixed_values=fixed_values,
                j_to_d=j_to_d, j_to_f=j_to_f, ode=ode, state0=state0)


def snapshot(system, state, time, authored_requests):
    """Recompute signed quantities and exact-in-time integrals independently."""
    d = len(system["dnodes"])
    dynamic = [state[i] for i in range(d)]
    dynamic_integral = [state[d+i] for i in range(d)]
    temp, tempint = {}, {}
    for i, node in enumerate(system["dnodes"]):
        temp[node], tempint[node] = dynamic[i], dynamic_integral[i]
    for i, node in enumerate(system["fnodes"]):
        temp[node] = system["fixed_values"][i]
        tempint[node] = time*temp[node]
    for j, node in enumerate(system["jnodes"]):
        a = system["j_to_d"][j]
        b = system["j_to_f"][j]
        temp[node] = sum((a[i]*dynamic[i] for i in range(d)), mp.zero) + sum(
            (b[i]*system["fixed_values"][i] for i in range(len(b))), mp.zero)
        tempint[node] = sum((a[i]*dynamic_integral[i] for i in range(d)), mp.zero) + sum(
            (b[i]*system["fixed_values"][i]*time for i in range(len(b))), mp.zero)

    incoming = {n:mp.zero for n in system["nodes"]}
    integrated = {n:mp.zero for n in system["nodes"]}
    exports = {}
    for name, rod in sorted(system["rods"].items()):
        a, b = rod["a"], rod["b"]
        G = system["conductances"][name]
        flow = G*(temp[a]-temp[b])
        flow_int = G*(tempint[a]-tempint[b])
        incoming[a] -= flow
        incoming[b] += flow
        integrated[a] -= flow_int
        integrated[b] += flow_int
        for key, value in (
            ("T_a",temp[a]), ("T_b",temp[b]), ("Q_flow",flow),
            ("port_a.Q_flow",flow), ("port_b.Q_flow",-flow), ("G",G)
        ):
            exports[name+"."+key] = value
        if name in system["areas"]:
            exports[name+".A"] = system["areas"][name]
    integrated_flows = {}
    for name in system["body_names"]:
        body = system["bodies"][name]
        node = body["node"]
        C = system["capacities"][name]
        exports[name+".T"] = temp[node]
        exports[name+".Q_in"] = incoming[node]
        exports[name+".dU"] = C*(temp[node]-mp_source(body["T_initial"]))
        exports[name+".C"] = C
        integrated_flows[name+".Q_in"] = integrated[node]
    for name in system["boundary_names"]:
        node = system["boundaries"][name]["node"]
        exports[name+".T"] = temp[node]
        exports[name+".Q_to_network"] = -incoming[node]
        integrated_flows[name+".Q_to_network"] = -integrated[node]

    def port_temperature(ref):
        bits = ref.split(".")
        need(len(bits) == 2, "unsupported authored temperature port")
        name, port = bits
        if name in system["bodies"]:
            need(port == "port", "unsupported body port")
            return temp[system["bodies"][name]["node"]]
        if name in system["boundaries"]:
            need(port == "port", "unsupported boundary port")
            return temp[system["boundaries"][name]["node"]]
        if name in system["rods"]:
            need(port in ("port_a","port_b"), "unsupported conductor port")
            return temp[system["rods"][name]["a" if port=="port_a" else "b"]]
        raise ReplayRefusal("h1_n10: unknown authored temperature owner")

    requests = {}
    for item in authored_requests:
        name, op = item["id"], item["op"]
        need(name not in requests, "duplicate authored request")
        if op == "temperature":
            requests[name] = port_temperature(item["target"])
        elif op == "temperatureDifference":
            requests[name] = port_temperature(item["a"])-port_temperature(item["b"])
        elif op == "heatFlow":
            need(item["target"] in system["rods"], "unknown conductor request")
            requests[name] = exports[item["target"]+".Q_flow"]
        elif op == "energyChange":
            need(item["target"] in system["bodies"], "unknown energy owner")
            requests[name] = exports[item["target"]+".dU"]
        else:
            raise ReplayRefusal("h1_n10: unsupported authored request operation")
    return exports, requests, integrated_flows


def expected_unit(name, *, family):
    if family == "integrals":
        return "J"
    if family == "requests":
        raise ReplayRefusal("h1_n10: request units are defined by original descriptor")
    suffix = name.split(".")[-1]
    if suffix in ("T","T_a","T_b"):
        return "K"
    if suffix in ("Q_flow","Q_in","Q_to_network"):
        return "W"
    if suffix == "dU":
        return "J"
    return {"A":"m2","G":"W/K","C":"J/K"}.get(suffix)


def compare_value(value, physical, unit, name, i, grid):
    """Fixed pre-result 100x corroboration threshold; never fit to output."""
    need(type(value) in (float,int) and math.isfinite(value)
         and type(unit) is str, "invalid candidate quantity")
    if unit == "K":
        epsilon = mp.mpf("0.000011")
    elif unit == "W":
        epsilon = mp.mpf("0.000001")
    elif unit == "J":
        epsilon = mp.mpf("0.001")
    else:
        need(unit in ("m2","W/K","J/K") and value > 0,
             "unsupported static quantity/unit")
        epsilon = 64*mp.mpf(math.ulp(float(value)))
    error = abs(mp.mpf(value)-physical)
    allowance = epsilon/100
    need(allowance > 0 and error <= allowance,
         "N1/independent physical discrepancy: " + name
         + " at sample " + str(i) + " grid " + str(grid))
    return error/allowance


def compare_grid(trace, grid, facts, authored_requests):
    """Check ALL original 77+8+5 outputs against a second numerical method."""
    need(type(trace) is dict and type(trace.get("report")) is dict
         and trace["report"].get("gridIntervals") == grid
         and type(trace.get("grid")) is list and len(trace["grid"]) == grid+1,
         "missing pinned original grid")
    with mp.workdps(DECIMAL_PRECISION):
        system = assemble(facts)
        need(len(system["body_names"]) == 3 and len(system["jnodes"]) == 2
             and len(system["rods"]) == 10, "T1-T physical scope altered")
        step = mp.expm(system["ode"]*(mp.mpf(PHYSICAL_INTERVAL_SECONDS)/grid))
        state = system["state0"]
        cols, reqs, ints = trace["columns"],trace["requests"],trace["integrals"]
        need(set(cols) and set(reqs)=={item["id"] for item in authored_requests},
             "wrong original request labels")
        max_ratios = {"columns":mp.zero,"requests":mp.zero,"integrals":mp.zero}
        comparisons = 0
        request_units = {
            item["id"]:("W" if item["op"]=="heatFlow" else
                        "J" if item["op"]=="energyChange" else "K")
            for item in authored_requests
        }
        for i in range(grid+1):
            t = mp.mpf(PHYSICAL_INTERVAL_SECONDS*i)/grid
            need(type(trace["grid"][i]) in (float,int)
                 and trace["grid"][i] == float(t),
                 "original saved-time identity mismatch at sample " + str(i))
            actual = snapshot(system,state,t,authored_requests)
            for family, predictions, originals in zip(
                ("columns","requests","integrals"),actual,(cols,reqs,ints)
            ):
                need(set(predictions)==set(originals),
                     "missing/foreign original observable: " + family)
                for name, physical in predictions.items():
                    unit = (
                        expected_unit(name, family=family) if family!="requests"
                        else request_units[name]
                    )
                    if family=="columns":
                        need(trace["units"].get(name)==unit,
                             "original column unit mismatch: " + name)
                    ratio=compare_value(originals[name][i],physical,unit,name,i,grid)
                    max_ratios[family]=max(max_ratios[family],ratio)
                    comparisons+=1
            if i<grid:
                state=step*state
        need(comparisons == 90*(grid+1), "original 77/8/5 inventory did not match")
        return {
            "gridIntervals":grid,"samples":grid+1,
            "allInternalExports":77,"publicRequests":8,"integratedFlows":5,
            "individualPhysicalSampleComparisons":comparisons,
            "maxRatioTo100xCheckingAllowance":{
                key:float(value) for key,value in max_ratios.items()
            },
            "independentMethod":"mpmath high-precision generic graph Laplacian, linear junction solve and augmented matrix exponential",
            "mathematicalIntervalCertificateFromThisMethod":False,
            "sourceOnlyCandidateAgreement":True,
        }


def audit(*, output: Path | None = None):
    if output is not None:
        output=Path(output).resolve()
        need(not output.is_relative_to(ROOT) and not output.exists(),
             "output must be a new outside-repository scratch folder")
    original, original_requests = load_original()
    summaries=[]
    with TemporaryDirectory(prefix="h1-n10-independent-dynamics-") as work:
        for grid in ORIGINAL_GRID_HASHES:
            target=Path(work)/str(grid)
            n1_report=n1.certify(n1.read_facts(),grid,output=target)
            source_blob=(target/("N1_T1T_reference_grid"+str(grid)+".json")).read_bytes()
            need(n1_report["fullTraceSha256"]==sha256(source_blob).hexdigest(),
                 "N1 candidate trace digest differs from generated report")
            # Verify entire original N1 bytes and N4 static proof BEFORE using
            # a single dynamic value in this independent numerical check.
            original_physical = (FACTS_PATH).read_bytes()
            from qualification.h1_n4.static_physical import create_static_candidate
            n4=create_static_candidate(original_physical,expected_sha256=SOURCE_FACTS_SHA)
            verify_historical_grid(source_blob,grid,n4)
            trace=json.loads(source_blob.decode("utf-8"))
            report=compare_grid(trace,grid,original,original_requests)
            report["originalN1TraceSha256"]=sha256(source_blob).hexdigest()
            summaries.append(report)
    receipt={
        "schema":SCHEMA,
        "stage":"offline_only_independent_dynamic_numerical_corroboration",
        "sourceFactsSha256":SOURCE_FACTS_SHA,
        "originalModelSha256":MODEL_SHA,
        "originalStudySha256":STUDY_SHA,
        "grids":summaries,
        "totalOriginalSampleComparisons":sum(x["individualPhysicalSampleComparisons"] for x in summaries),
        "newMethodIsRigorousIntervalProof":False,
        "referenceAccuracyCertified":False,
        "independentlyCertifiedReference":False,
        "fullDynamicPhysical100xIndependentlyCertified":False,
        "runtimeReady":False,
        "referenceBundleWritten":False,
        "externalOwnerApprovalVerified":False,
        "nativeExecuted":False,
        "nativeQualified":False,
        "historicalReferenceRegenerated":False,
        "legacySevenStaticCheckingCentresStillFail":EXPECTED_LEGACY_FAILURES,
        "evidenceLimit":"high-precision mpmath numerical corroboration of original N1 source-only candidates at all saved 77/8/5 observations; no rigorous independent error bound, external authorization, runner bundle or native result",
    }
    if output is not None:
        output.mkdir(parents=True,exist_ok=False)
        (output/"n10-dynamic-crosscheck.json").write_text(
            json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    print(json.dumps(audit(output=a.out),sort_keys=True,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
