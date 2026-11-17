"""SIM_HEAT H1-C1 F02: self-contained OFFLINE nonphysical topology viewer.

Derived from the ORIGINAL Modelica port-junction graph and expected-only
public request overlays. Diagram pixels are arbitrary teaching-layout units:
they are NOT coordinates, lengths, shapes, pose, flow measurements, or
material dimensions. The HTML viewer has no fetch/network or native bridge,
and every requested native value remains NOT COMPUTED.

NO OpenModelica, MAT/CSV decode, reference.prepare, physical solver,
native permission, actual owner-authenticated release or real atomic CAS.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from collections import deque

from qualification.h1_c1.f02 import offline_topology_observation_overlay as source

SCHEMA="sim_heat.h1_c1_f02_offline_nonphysical_schematic/1"
STATUS="NONPHYSICAL_SOURCE_SCHEMATIC_ONLY_NO_NATIVE_DATA"
DECLARED_UNITS="schematic_pixels_not_meters_or_apparatus_geometry"
SOURCE_CI_COMMIT="4f077d5e3f231dacae5986d66bdaf0bdbe555b83"
FALSE_FLAGS=(
    "nativeAllowed","nativeExecuted","nativeQualified","nativePublicValuesComputed",
    "realNativeExportsAvailable","ownerNativeLaunchApproved",
    "realAcrossRunReservationAllocated","modelBuilt","compilerQueried",
    "referenceRegenerated","originalF0Strict100xPassed",
    "pr32BitwiseRegenerationPassed",
)


class SchematicRefusal(ValueError):
    pass


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise SchematicRefusal(reason)


def canon(value: dict) -> bytes:
    try:
        return (json.dumps(value,sort_keys=True,ensure_ascii=True,
                           allow_nan=False,indent=2)+"\n").encode()
    except (TypeError,ValueError,OverflowError,RecursionError) as exc:
        raise SchematicRefusal("noncanonical nonphysical view contract") from exc


def _path_from_source(nodes: list[dict], rods: list[dict]) -> list[str]:
    """Derive diagram ORDER from the graph, never assert physical locations."""
    names={j["owningComponent"]:j["id"] for j in nodes}
    need(len(names)==4 and set(names)=={
        "hotBath","leftBuffer","rightBuffer","coldBath"},
         "four original sources/anchors not available")
    adj={j["id"]:set() for j in nodes}
    for edge in rods:
        a,b=edge["fromJunctionId"],edge["toJunctionId"]
        need(a in adj and b in adj and a!=b,
             "source rod refers to a missing/same junction")
        adj[a].add(b)
        adj[b].add(a)
    start=names["hotBath"]
    finish=names["coldBath"]
    # With two parallel bridges, the SIMPLE graph is a 4-node path.
    need(len(adj)==4 and len(rods)==4
         and sorted(len(a) for a in adj.values())==[1,1,2,2]
         and len(adj[start])==1 and len(adj[finish])==1,
         "original source graph no longer a four-junction path")
    queue=deque([(start,[start])])
    visited=set()
    found=[]
    while queue:
        now,path=queue.popleft()
        if now in visited:
            continue
        visited.add(now)
        if now==finish:
            found=path
            break
        for next_id in sorted(adj[now]):
            if next_id not in visited:
                queue.append((next_id,path+[next_id]))
    need(len(found)==4 and len(set(found))==4
         and set(found)==set(adj),
         "no unique spanning thermal-junction diagram order")
    return found


def contract() -> dict:
    """Only ORIGINAL source-derived graph and expected/uncomputed labels."""
    original=source.inventory()
    need(original["schema"]==source.SCHEMA
         and original["status"]==source.STATUS
         and original["sourceDerivedOnly"] is True
         and original["releaseBlocked"] is True
         and original["nativeObservationCount"]==0
         and original["nativePublicRequestsStillNotComputed"]==9
         and len(original["missingNativeReleaseGates"])==11
         and original["layout"] is None
         and original["physicalApparatusGeometry"] is None,
         "reviewed original source overlay absent or source/native promoted")
    # Deliberately reconstruct and check entire original source-bound input.
    need(source.assert_exact_source_bound(original),
         "source view-data is not exact original Modelica topology")
    junctions=original["thermalJunctions"]
    rods=original["orientedRodEdges"]
    source_order=_path_from_source(junctions,rods)
    x={name:132+250*i for i,name in enumerate(source_order)}
    y=218
    nodes=[
        {"id":j["id"],"label":j["owningComponent"],
         "sourcePorts":j["sourcePorts"],"diagramX":x[j["id"]],
         "diagramY":y,"nativeStatus":"not_computed",
         "nativeTemperature":None}
        for j in junctions
    ]
    # Parallel rods get arbitrary separated LANES solely for clarity.
    # Not their real separation, shape, material, length or physical pose.
    parallels={name:i for g in original["sourceParallelRodGroups"]
               for i,name in enumerate(g["rodNames"])}
    need(parallels=={"flatBridge":0,"roundBridge":1},
         "original parallel conductor group changed")
    edges=[]
    for edge in rods:
        name=edge["name"]
        a,b=edge["fromJunctionId"],edge["toJunctionId"]
        start,end=x[a],x[b]
        direction=1 if end>start else -1
        need(abs(end-start)==250,
             "rod endpoint columns are not adjacent source-junction ranks")
        dy= (-44 if parallels[name]==0 else 44) if name in parallels else 0
        edges.append({
            "name":name,"sourcePortA":edge["portA"],
            "sourcePortB":edge["portB"],
            "fromJunctionId":a,"toJunctionId":b,
            "diagramStartX":start+direction*36,
            "diagramEndX":end-direction*36,
            "diagramY":y+dy,
            "expectedPositiveFlowExport":edge["expectedPositiveFlowExport"],
            "sourceOrientation":"port_a_to_port_b_not_observed_heat_direction",
            "nativeStatus":"not_computed","nativeHeatFlow":None,
        })
    source_ids={"node-"+n["id"] for n in nodes}
    rod_ids={"rod-"+e["name"] for e in edges}
    overlays=[]
    for request in original["expectedPublicRequestOverlays"]:
        kind=request["placement"]["kind"]
        where=request["placement"]
        if kind in ("thermal_port","ordered_thermal_port_pair","thermal_body"):
            focus=["node-"+v for v in where["junctionIds"]]
        elif kind=="oriented_source_rod":
            focus=["rod-"+where["rodName"]]+[
                "node-"+v for v in where["junctionIds"]]
        else:
            raise SchematicRefusal("unsupported original public source placement")
        need(len(focus)==len(set(focus))
             and set(focus)<=source_ids|rod_ids
             and request["nativeStatus"]=="not_computed"
             and request["nativeValue"] is None
             and request["expectedOnly"] is True,
             "public request focus points outside original source graph")
        overlays.append({
            "id":request["id"],
            "unit":request["unit"],
            "operation":request["operation"],
            "expectedExportTerms":request["orderedExpectedExportTerms"],
            "highlightElements":focus,
            "nativeStatus":"not_computed",
            "nativeValue":None,
        })
    need(len(nodes)==4 and len(edges)==4 and len(overlays)==9
         and len({r["id"] for r in overlays})==9,
         "nonphysical schematic row count differs from source")
    report={
        "schema":SCHEMA,"status":STATUS,
        "sourceReviewHead":SOURCE_CI_COMMIT,
        "originalModelSha256":original["originalModelSha256"],
        "modalStudySha256":original["modalStudySha256"],
        "approvedOfflineReferenceRawSha256":original["originalSavedReferenceRawSha256"],
        "approvedOfflineReferenceSeal":original["originalSavedReferenceSeal"],
        "layoutPurpose":"topological_reading_order_only",
        "diagramUnits":DECLARED_UNITS,
        "physicalLengthScale":None,
        "physicalApparatusGeometry":None,
        "physicalCoordinatesKnown":False,
        "sourceJunctionOrder":source_order,
        "schematicJunctions":nodes,
        "schematicOrientedRods":edges,
        "publicRequestHighlights":overlays,
        "sourceConnectCount":original["originalConnectCount"],
        "sourceParallelPair":original["sourceParallelRodGroups"][0]["rodNames"],
        "sourceExactPortCount":original["terminalPortCount"],
        "nativeObservationCount":0,
        "nativePublicRequestsStillNotComputed":9,
        "nativePublicValues":None,
        "releaseBlocked":True,
        "missingNativeReleaseGates":original["missingNativeReleaseGates"],
        **{k:False for k in FALSE_FLAGS},
        "limitations":[
            "Schematic x/y coordinates are arbitrary diagram pixels, NOT real apparatus geometry",
            "Arrow labels show frozen port_a-to-port_b Q_flow SIGN CONVENTION, not actual heat direction",
            "Request highlighting selects expected field dependencies, NOT computed native values",
            "No native or MAT/CSV result was generated, observed or decoded",
            "All eleven real owner/source/host/adapter/external CAS native gates remain missing",
            "This self-contained HTML is an offline teaching-view candidate, not an authenticated release",
        ],
    }
    validate_shape(report)
    return report


def validate_shape(doc: dict):
    """Coarse source-only negative contract; NOT full native provenance."""
    need(type(doc) is dict and doc.get("schema")==SCHEMA
         and doc.get("status")==STATUS
         and doc.get("layoutPurpose")=="topological_reading_order_only"
         and doc.get("diagramUnits")==DECLARED_UNITS
         and doc.get("releaseBlocked") is True
         and doc.get("physicalLengthScale") is None
         and doc.get("physicalApparatusGeometry") is None
         and doc.get("physicalCoordinatesKnown") is False
         and doc.get("nativePublicValues") is None,
         "fake physical or native schematic authority")
    for key in FALSE_FLAGS:
        need(doc.get(key) is False,"native/owner permission falsified: "+key)
    for key,n in (
        ("nativeObservationCount",0),("nativePublicRequestsStillNotComputed",9),
        ("sourceConnectCount",8),("sourceExactPortCount",12),
    ):
        need(type(doc.get(key)) is int and doc[key]==n,
             "schematic/source cardinality changed: "+key)
    for key,n in (
        ("sourceJunctionOrder",4),("schematicJunctions",4),
        ("schematicOrientedRods",4),("publicRequestHighlights",9),
        ("sourceParallelPair",2),("missingNativeReleaseGates",11),
    ):
        need(type(doc.get(key)) is list and len(doc[key])==n,
             "schematic source/outcome list changed: "+key)
    for row in doc["schematicJunctions"]:
        need(type(row) is dict and row.get("nativeStatus")=="not_computed"
             and row.get("nativeTemperature") is None
             and type(row.get("diagramX")) is int
             and type(row.get("diagramY")) is int,
             "schematic thermal junction not source-only")
    for row in doc["schematicOrientedRods"]:
        need(type(row) is dict and row.get("nativeStatus")=="not_computed"
             and row.get("nativeHeatFlow") is None
             and row.get("sourceOrientation")==
             "port_a_to_port_b_not_observed_heat_direction",
             "schematic rod is not a source sign label")
    for row in doc["publicRequestHighlights"]:
        need(type(row) is dict and row.get("nativeStatus")=="not_computed"
             and row.get("nativeValue") is None
             and type(row.get("highlightElements")) is list,
             "public native request not still uncomputed")


def assert_exact_source_bound(candidate: dict):
    """Full original-source readback, never an owner/native attestation."""
    validate_shape(candidate)
    need(canon(candidate)==canon(contract()),
         "candidate schematic differs from exact original frozen Modelica source")
    return True


def _text(value: object) -> str:
    return html.escape(str(value),quote=True)


def _term_label(terms: list[dict]) -> str:
    return " ".join(
        ("+" if t["sign"]==1 else "−")+" "+t["exportName"]
        for t in terms
    ).lstrip("+ ").strip()


CSS=r"""
:root {color-scheme:light; font-family:system-ui,Arial,sans-serif; background:#f8fafc; color:#10243c}
*{box-sizing:border-box}
body{margin:0; padding:24px; line-height:1.55}
main{max-width:1080px;margin:0 auto}
h1{font-size:1.55rem;margin:.1rem 0 .5rem}
h2{font-size:1.07rem;margin:1.3rem 0 .35rem}
p{max-width:900px}
.warning{font-weight:700;color:#7f2626;background:#fff4ed;border:1px solid #d9a47c;padding:12px;border-radius:8px}
.meta{font-size:.89rem;color:#314860}
.controls{margin-top:1rem;border:1px solid #cdd9e4;background:white;padding:14px;border-radius:9px}
select{max-width:100%;width:420px;margin:.45rem 0;padding:.55rem;font:inherit;color:#10243c;border:1px solid #8295ae;border-radius:6px;background:white}
select:focus-visible{outline:3px solid #7048c1}
output{display:block;min-height:3rem;font-weight:600;margin-top:.4rem}
.diagram{width:100%;overflow-x:auto;background:white;border:1px solid #d6e0e8;border-radius:9px}
svg{width:100%;min-width:760px;height:auto;display:block}
.node circle{fill:#e5effa;stroke:#335f83;stroke-width:3}
.node .owner{font-size:16px;font-weight:700;fill:#17354c;text-anchor:middle}
.node .node-id{font-size:13px;fill:#526679;text-anchor:middle}
.rod line{stroke:#25495d;stroke-width:4}
.rod .rod-name{fill:#204257;font-size:15px;font-weight:700;text-anchor:middle}
.rod .rod-sign{fill:#425971;font-size:11px;text-anchor:middle}
svg.has-selection [data-element]{opacity:.22}
svg.has-selection [data-element].selected{opacity:1}
.node.selected circle{fill:#f0e3ff;stroke:#65329b;stroke-width:5}
.rod.selected line{stroke:#65329b;stroke-width:7}
.rod.selected .rod-name{fill:#512285}
footer{border-top:1px solid #d9e0e8;margin-top:1rem;font-size:.88rem;color:#304760;padding-top:.6rem}
code{overflow-wrap:anywhere}
@media(max-width:700px){body{padding:12px}h1{font-size:1.35rem}}
"""
JS=r"""(() => {
"use strict";
const select=document.getElementById("public-request");
const schematic=document.getElementById("topology-schematic");
const detail=document.getElementById("request-detail");
function update(){
  const option=select.options[select.selectedIndex];
  const ids=new Set((option.dataset.focus||"").split(",").filter(Boolean));
  schematic.classList.toggle("has-selection",ids.size>0);
  schematic.querySelectorAll("[data-element]").forEach(element=>{
    element.classList.toggle("selected",ids.has(element.dataset.element));
  });
  detail.textContent=option.dataset.summary||"Choose a request to highlight expected source fields. No native values exist.";
}
select.addEventListener("change",update);
update();
})();"""


def render_html() -> str:
    """One complete offline HTML document; NO script/network/dependency loads."""
    doc=contract()
    need(doc["nativeObservationCount"]==0 and doc["releaseBlocked"] is True,
         "untrusted source viewer cannot render claimed native data")
    nodes=doc["schematicJunctions"]
    edges=doc["schematicOrientedRods"]
    node_markup=[]
    for n in nodes:
        x,y=n["diagramX"],n["diagramY"]
        label=_text(n["label"])
        ident=_text(n["id"])
        members=_text(", ".join(n["sourcePorts"]))
        node_markup.append(
            f'<g class="node" role="group" data-element="node-{ident}" '
            f'aria-label="{label}: source junction {ident}; ports {members}; '
            f'native temperature not computed">'
            f'<title>{label}: {members}; native temperature not computed</title>'
            f'<circle cx="{x}" cy="{y}" r="29"/>'
            f'<text class="owner" x="{x}" y="{y+62}">{label}</text>'
            f'<text class="node-id" x="{x}" y="{y+81}">{ident}</text>'
            '</g>'
        )
    edge_markup=[]
    for e in edges:
        name=_text(e["name"])
        middle=(e["diagramStartX"]+e["diagramEndX"])//2
        ey=e["diagramY"]
        label_y=ey-19 if name!="roundBridge" else ey+28
        sign_y=label_y+14
        edge_markup.append(
            f'<g class="rod" role="group" data-element="rod-{name}" '
            f'aria-label="{name}, source port a to b positive sign convention; '
            f'native flow not computed">'
            f'<title>{name}: port_a → port_b is the source-positive Q_flow convention. '
            f'Actual heat direction NOT observed.</title>'
            f'<line x1="{e["diagramStartX"]}" y1="{ey}" '
            f'x2="{e["diagramEndX"]}" y2="{ey}" marker-end="url(#sign-arrow)"/>'
            f'<text class="rod-name" x="{middle}" y="{label_y}">{name}</text>'
            f'<text class="rod-sign" x="{middle}" y="{sign_y}">+Q_flow: a→b (convention)</text>'
            '</g>'
        )
    # Native status must come from original source-checked record, never a
    # client-provided numeric/result payload. No HTML injection is accepted.
    choices=['<option value="" data-focus="" data-summary="">Show all source topology</option>']
    for o in doc["publicRequestHighlights"]:
        focus=",".join(o["highlightElements"])
        reason=_term_label(o["expectedExportTerms"])
        summary=(f'{o["id"]}: expected {reason} ({o["unit"]}); '
                 "native value NOT COMPUTED. Source-defined fields only.")
        choices.append(
            f'<option value="{_text(o["id"])}" data-focus="{_text(focus)}" '
            f'data-summary="{_text(summary)}">'
            f'{_text(o["id"])} — {_text(o["unit"])} (not computed)</option>'
        )
    script_hash=base64.b64encode(hashlib.sha256(JS.encode()).digest()).decode()
    csp=("default-src 'none'; base-uri 'none'; form-action 'none'; "
         "connect-src 'none'; img-src 'none'; font-src 'none'; object-src 'none'; "
         "style-src 'unsafe-inline'; script-src 'sha256-"+script_hash+"'")
    source_label=_text(doc["originalModelSha256"])
    return ("<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{_text(csp)}">'
        '<title>SIM_HEAT — original topology only (NO native data)</title>'
        '<style>'+CSS+'</style></head><body><main>'
        '<h1>SIM_HEAT: original authored thermal connections</h1>'
        '<p class="warning" role="status">SCHEMATIC TOPOLOGY ONLY · NOT TO PHYSICAL SCALE · '
        'ALL NINE NATIVE READINGS NOT COMPUTED · RELEASE BLOCKED</p>'
        '<p>Four ideal thermal junctions, four source-oriented conductors and '
        'the two parallel bridges. Spacing, lines and labels are arranged only '
        'to make the original port connections legible. There are no real '
        'dimensions, flow magnitudes or measured temperatures here.</p>'
        '<div class="diagram"><svg id="topology-schematic" viewBox="0 0 1060 390" '
        'role="img" aria-labelledby="diagram-title diagram-desc">'
        '<title id="diagram-title">Nonphysical thermal connection schematic</title>'
        '<desc id="diagram-desc">Hot bath, left buffer, right buffer and cold bath '
        'connected by hot lead, flat and round parallel bridges, and cold lead. '
        'Arrows are source sign conventions, not observed heat flow.</desc>'
        '<defs><marker id="sign-arrow" markerWidth="9" markerHeight="9" '
        'refX="7" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L7,3 L0,6 z" fill="#25495d"/></marker></defs>'
        +''.join(edge_markup)+''.join(node_markup)+'</svg></div>'
        '<div class="controls"><label for="public-request"><strong>'
        'Highlight an original public observation (EXPECTED only)</strong></label>'
        '<div><select id="public-request">'+''.join(choices)+'</select></div>'
        '<output id="request-detail" aria-live="polite"></output></div>'
        '<h2>Interpretation boundary</h2>'
        '<p>No OMC or native output was evaluated. A source field like '
        '<code>hotLead.Q_flow</code> identifies an expected variable, not a measured '
        'flow. <code>leftBuffer.T − rightBuffer.T</code> is an intended dependency, '
        'not a numeric subtraction performed by this viewer. This page cannot '
        'authorize compilation or a native launch.</p>'
        f'<footer>Original Modelica SHA-256: <code>{source_label}</code>. '
        'Offline-only checking reference; 11 required native-release safeguards '
        'are missing. No external scripts, fonts, images or network requests.</footer>'
        '<script>'+JS+'</script></main></body></html>\n")


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=(
        "describe-nonphysical-layout-only","print-offline-html-only"))
    args=p.parse_args(argv)
    try:
        if args.action=="describe-nonphysical-layout-only":
            print(json.dumps(contract(),sort_keys=True,indent=2,allow_nan=False))
        else:
            print(render_html(),end="")
        return 0  # Source-only viewer content produced, NEVER native permission.
    except Exception as exc:
        print(json.dumps({
            "schema":SCHEMA,"status":"REFUSED_UNTRUSTED_SCHEMATIC_SOURCE",
            "reason":type(exc).__name__+": "+str(exc),
            "releaseBlocked":True,"nativeAllowed":False,
            "nativeExecuted":False,"nativeQualified":False,
            "nativePublicRequestsStillNotComputed":9,
        },sort_keys=True))
        return 3


if __name__=="__main__":
    raise SystemExit(main())
