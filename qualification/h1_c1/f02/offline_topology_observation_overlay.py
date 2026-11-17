"""H1-C1-F02 OFFLINE source-derived thermal topology / observation overlay.

No browser, drawing coordinates, geometry or apparatus pose. JSON exposes the
author's original Modelica port equivalence classes, exact connect() wires,
oriented rod edges, source-defined parallel bridge and public request overlays.
ALL temperatures/flows/public values are NULL and NOT COMPUTED.

This is a topology/view-data contract ONLY, never a solver, MAT decoder,
trusted native adapter, owner permission, new reference or OpenModelica run.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from h1.model import PORTS
from h1.study import load_study
from qualification.h1_c1.f02 import offline_public_request_dependencies as deps
from qualification.h1_c1.f02 import offline_expected_export_coverage as coverage

ROOT=Path(__file__).resolve().parents[3]
SCHEMA="sim_heat.h1_c1_f02_offline_topology_observation_overlay/1"
STATUS="ORIGINAL_TOPOLOGY_AND_EXPECTED_REQUEST_OVERLAY_NO_NATIVE"
FALSE_FLAGS=(
    "nativeAllowed","nativeExecuted","nativeQualified",
    "nativeObservationsComputed","realNativeExportsAvailable",
    "modelBuilt","compilerQueried","matDecoded",
    "referenceRegenerated","ownerNativeLaunchApproved",
    "realAcrossRunReservationAllocated",
    "originalF0Strict100xPassed","pr32BitwiseRegenerationPassed",
)


class OverlayRefusal(ValueError):
    pass


def need(ok: bool, why: str) -> None:
    if not ok:
        raise OverlayRefusal(why)


def canonical(doc: dict) -> bytes:
    """Exact string serialization prevents bool/int/float report confusion."""
    try:
        return (json.dumps(doc,sort_keys=True,indent=2,
                           ensure_ascii=True,allow_nan=False)+"\n").encode("utf-8")
    except (ValueError,TypeError,OverflowError,RecursionError) as exc:
        raise OverlayRefusal("invalid noncanonical topology overlay JSON") from exc


def _source() -> tuple[dict,object]:
    """Original study/parser and approved checking-only dependency descriptor."""
    original=deps.inventory()
    need(original["status"]==deps.STATUS
         and original["releaseBlocked"] is True
         and original["nativeObservationCount"]==0
         and original["nativePublicRequestsStillNotComputed"]==9
         and len(original["missingNativeReleaseGates"])==11,
         "previous expected public dependency model is not RELEASE BLOCKED")
    study=load_study(ROOT/coverage.STUDY,ROOT/"h1/cases")
    need(study.sha256==coverage.MODAL_STUDY_SHA
         and study.model_sha256==coverage.ORIGINAL_MODEL_SHA
         and study.request_report["admitted"] is True,
         "frozen Modelica author source/evaluator study drift")
    return original,study


def inventory() -> dict:
    original,study=_source()
    model=study.model
    topology=study.topology
    ports=sorted(model.ports())
    need(len(model.components)==8 and len(ports)==12
         and len(model.connections)==8 and len(topology.nodes)==4
         and len(topology.edges)==4 and len(topology.networks)==1
         and len(topology.anchored_nodes)==4,
         "original eight-component four-junction graph no longer matches")
    need(set(topology.node_of)==set(ports)
         and set(port for group in topology.nodes for port in group)==set(ports)
         and len({port for group in topology.nodes for port in group})==12,
         "source-derived junction membership has omitted/duplicate port")
    junctions=[]
    owners={}
    for i,group in enumerate(topology.nodes):
        anchors=sorted((port.split(".")[0] for port in group
                        if model.components[port.split(".")[0]].kind
                        in ("Body","FixedTemperature")))
        need(len(anchors)==1,"unowned/multiply owned source thermal junction")
        owner=anchors[0]
        need(owner not in owners, "one owner attached to multiple junctions")
        owners[owner]=i
        junctions.append({
            "id":f"junction-{i:02d}",
            "sourcePorts":list(group),
            "owningComponent":owner,
            "owningKind":model.components[owner].kind,
            "nativeTemperature":None,
            "nativeStatus":"not_computed",
        })
    need(set(owners)=={"hotBath","leftBuffer","rightBuffer","coldBath"},
         "the four original thermal anchor identities differ")
    def jid(port: str) -> str:
        need(port in topology.node_of,"unknown source terminal")
        return f"junction-{topology.node_of[port]:02d}"
    components=[]
    for name,c in sorted(model.components.items()):
        need(c.kind in PORTS,"unknown original physical component kind")
        components.append({
            "name":name,
            "kind":c.kind,
            "sourcePorts":[{"port":name+"."+term,
                            "junctionId":jid(name+"."+term)}
                           for term in PORTS[c.kind]],
            "physicalPoseSpecified":False,
            "nativeStatus":"not_computed",
        })
    wires=[]
    for i,(a,b) in enumerate(model.connections):
        need(a in model.ports() and b in model.ports() and a!=b,
             "unknown/invalid original Modelica connect ports")
        need(jid(a)==jid(b),"original source connection splits an ideal junction")
        wires.append({
            "sourceConnectIndex":i,
            "fromPort":a,
            "toPort":b,
            "junctionId":jid(a),
        })
    need(len(wires)==len({tuple(sorted((w["fromPort"],w["toPort"])))
                              for w in wires})==8,
         "duplicate/omitted original connect() declarations")
    rods=[]
    for name,a_idx,b_idx,_conductance in topology.edges:
        c=model.components[name]
        need(c.kind in ("RodArea","RodCircular")
             and a_idx==topology.node_of[name+".port_a"]
             and b_idx==topology.node_of[name+".port_b"] and a_idx!=b_idx,
             "incorrect oriented source rod endpoints")
        rods.append({
            "name":name,
            "componentKind":c.kind,
            "portA":name+".port_a","portB":name+".port_b",
            "fromJunctionId":jid(name+".port_a"),
            "toJunctionId":jid(name+".port_b"),
            "expectedPositiveFlowExport":name+".Q_flow",
            "flowSignConvention":"source_port_a_to_port_b_positive",
            "nativeHeatFlow":None,
            "nativeStatus":"not_computed",
        })
    need({x["name"] for x in rods}==
         {"hotLead","flatBridge","roundBridge","coldLead"},
         "original conductor identities changed")
    pairs={}
    for x in rods:
        key=tuple(sorted((x["fromJunctionId"],x["toJunctionId"])))
        pairs.setdefault(key,[]).append(x["name"])
    parallel=[
        {"sharedJunctionIds":list(pair),
         "rodNames":sorted(names),
         "topologyOnly":True,
         "observedParallelHeatFlows":None}
        for pair,names in sorted(pairs.items())
        if len(names)>1
    ]
    need(len(parallel)==1
         and parallel[0]["rodNames"]==["flatBridge","roundBridge"],
         "original two parallel bridge rods no longer join the same junction pair")
    overlays=[]
    for authored,related in zip(study.data["requests"],
                               original["publicRequestDependencies"],strict=True):
        need(authored["id"]==related["id"]
             and authored["op"]==related["operation"]
             and related["expectedOnly"] is True
             and related["nativeStatus"]=="not_computed"
             and related["nativeValue"] is None,
             "original public request/expected field dependencies drifted")
        op=authored["op"]
        if op=="temperature":
            placement={"kind":"thermal_port","sourcePort":authored["target"],
                       "junctionIds":[jid(authored["target"])]}
        elif op=="temperatureDifference":
            a,b=authored["a"],authored["b"]
            need(jid(a)!=jid(b),"original temperature difference collapsed")
            placement={"kind":"ordered_thermal_port_pair",
                       "firstSourcePort":a,"secondSourcePort":b,
                       "junctionIds":[jid(a),jid(b)]}
        elif op=="heatFlow":
            rod=next((x for x in rods if x["name"]==authored["target"]),None)
            need(rod is not None,"original heat-flow request not a source rod")
            placement={"kind":"oriented_source_rod",
                       "rodName":rod["name"],
                       "junctionIds":[rod["fromJunctionId"],rod["toJunctionId"]]}
        elif op=="energyChange":
            component=authored["target"]
            need(component in owners
                 and model.components[component].kind=="Body",
                 "original energy request not a stored thermal Body")
            placement={"kind":"thermal_body",
                       "componentName":component,
                       "junctionIds":[jid(component+".port")]}
        else:
            raise OverlayRefusal("unsupported original request operation")
        overlays.append({
            "id":related["id"],
            "operation":related["operation"],
            "unit":related["expectedUnit"],
            "authoredOperands":related["authoredOperands"],
            "orderedExpectedExportTerms":related["orderedExpectedExportTerms"],
            "placement":placement,
            "expectedOnly":True,
            "nativeStatus":"not_computed",
            "nativeValue":None,
        })
    need(len(overlays)==9 and len({x["id"] for x in overlays})==9
         and all(x["nativeValue"] is None for x in overlays),
         "original nine public request overlays incomplete")
    report={
        "schema":SCHEMA,
        "status":STATUS,
        "originalModelSha256":coverage.ORIGINAL_MODEL_SHA,
        "modalStudySha256":coverage.MODAL_STUDY_SHA,
        "originalSavedReferenceRawSha256":coverage.ORIGINAL_REFERENCE_SHA,
        "originalSavedReferenceSeal":coverage.ORIGINAL_REFERENCE_SEAL,
        "caseId":"H1_C1_MODAL",
        "componentCount":8,"thermalJunctionCount":4,
        "terminalPortCount":12,"originalConnectCount":8,
        "orientedRodCount":4,"parallelBridgeGroupCount":1,
        "publicRequestCount":9,
        "components":components,
        "thermalJunctions":junctions,
        "sourceConnectWires":wires,
        "orientedRodEdges":rods,
        "sourceParallelRodGroups":parallel,
        "expectedPublicRequestOverlays":overlays,
        "layout":None,
        "physicalApparatusGeometry":None,
        "nativeObservationCount":0,
        "nativePublicRequestsStillNotComputed":9,
        "sourceDerivedOnly":True,
        "releaseBlocked":True,
        "missingNativeReleaseGates":original["missingNativeReleaseGates"],
        **{k:False for k in FALSE_FLAGS},
        "limits":[
            "Only ORIGINAL model connection topology; no physical pose or geometry inferred",
            "Source-oriented rod edges show sign convention, NOT observed direction of heat",
            "Nine labels are intended public observations; NO native temperatures, energy or heat flows",
            "Four junctions and parallel bridge are port equivalence classes, NOT an executable schematic",
            "Full owner/host/release/CAS/native gates remain missing, no OMC or MAT",
        ],
    }
    validate_shape(report)
    return report


def validate_shape(doc: dict) -> None:
    """Denial-only structural guard; NOT source-attested native evidence."""
    need(type(doc) is dict
         and doc.get("schema")==SCHEMA and doc.get("status")==STATUS
         and doc.get("sourceDerivedOnly") is True
         and doc.get("releaseBlocked") is True
         and doc.get("layout") is None
         and doc.get("physicalApparatusGeometry") is None,
         "untrusted topology/native/physical layout assertion")
    for key in FALSE_FLAGS:
        need(doc.get(key) is False,
             "false native/owner/old historical claim: "+key)
    for key,value in (
        ("componentCount",8),("thermalJunctionCount",4),
        ("terminalPortCount",12),("originalConnectCount",8),
        ("orientedRodCount",4),("parallelBridgeGroupCount",1),
        ("publicRequestCount",9),("nativeObservationCount",0),
        ("nativePublicRequestsStillNotComputed",9),
    ):
        need(type(doc.get(key)) is int and doc[key]==value,
             "incorrect original source topology/request cardinality: "+key)
    for group,n in (
        ("components",8),("thermalJunctions",4),("sourceConnectWires",8),
        ("orientedRodEdges",4),("sourceParallelRodGroups",1),
        ("expectedPublicRequestOverlays",9),
    ):
        need(type(doc.get(group)) is list and len(doc[group])==n,
             "wrong topology/overlay count: "+group)
    need(type(doc.get("missingNativeReleaseGates")) is list
         and len(doc["missingNativeReleaseGates"])==11,
         "real release gates unexpectedly claimed complete")
    for row in doc["expectedPublicRequestOverlays"]:
        need(type(row) is dict and row.get("expectedOnly") is True
             and row.get("nativeStatus")=="not_computed"
             and row.get("nativeValue") is None,
             "native public observation has not been computed")
    for row in doc["thermalJunctions"]:
        need(type(row) is dict and row.get("nativeTemperature") is None
             and row.get("nativeStatus")=="not_computed",
             "native thermal junction temperature cannot be asserted")
    for row in doc["orientedRodEdges"]:
        need(type(row) is dict and row.get("nativeHeatFlow") is None
             and row.get("nativeStatus")=="not_computed",
             "native rod heat flow cannot be asserted")


def assert_exact_source_bound(untrusted: dict) -> bool:
    """Always re-derive from frozen source; never trust shape or a local SHA."""
    validate_shape(untrusted)
    need(canonical(untrusted)==canonical(inventory()),
         "topology/observable overlay differs from exact frozen source")
    return True


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("describe-source-topology-only",))
    args=p.parse_args(argv)
    try:
        print(json.dumps(inventory(),sort_keys=True,indent=2,allow_nan=False))
        return 0 # Only source-derived OFFLINE view data, never a native PASS.
    except Exception as exc:
        print(json.dumps({
            "schema":SCHEMA,"status":"REFUSED_UNTRUSTED_ORIGINAL_TOPOLOGY",
            "reason":type(exc).__name__+": "+str(exc),
            "releaseBlocked":True,"nativeAllowed":False,
            "nativeExecuted":False,"nativeQualified":False,
            "nativePublicRequestsStillNotComputed":9,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
