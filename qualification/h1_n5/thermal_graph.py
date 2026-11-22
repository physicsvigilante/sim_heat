"""Composable H1 thermal graph balance assembly and trial snapshot, OFFLINE ONLY.

No numerical time integration, Schur solver, OpenModelica imports, native
outputs, reference bundle writing, owner approval, or trajectory certificate.
An unfamiliar supported H1 graph reuses identical equations and port signs.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction as F
from hashlib import sha256
import json

from qualification.h1_n4 import static_physical as n4

SCHEMA = "sim_heat.h1_n5.thermal_graph_balance_candidate/1"
TRIAL_SCHEMA = "sim_heat.h1_n5.user_trial_snapshot/1"
STATIC_VERSION = n4.SCHEMA


class GraphRefusal(ValueError):
    """An unsupported thermal graph/trial input failed closed."""


def need(ok, reason):
    if not ok:
        raise GraphRefusal("h1_n5: " + reason)


def fraction_text(value):
    need(type(value) is F, "internal quantity must be exact rational")
    return str(value)


def interval_text(pair):
    lo, hi = pair
    need(type(lo) is F and type(hi) is F and lo <= hi, "invalid exact interval")
    return [str(lo), str(hi)]


def _physical_positive(value):
    # Inherited N4 parser has already bounded the exact source numbers.
    need(type(value) in (int, Decimal), "invalid exact source physical type")
    result = F(value)
    need(result > 0, "nonpositive physical source quantity")
    return result


def _conductance_interval(rod, pi):
    k = _physical_positive(rod["k"])
    length = _physical_positive(rod["L"])
    if rod["kind"] == "RodArea":
        area = _physical_positive(rod["A"])
        return (k*area/length, k*area/length), (area, area)
    need(rod["kind"] == "RodCircular", "unsupported physical conductor")
    diameter = _physical_positive(rod["d"])
    area = (pi[0]*diameter*diameter/4,
            pi[1]*diameter*diameter/4)
    return (k*area[0]/length, k*area[1]/length), area


def _provenance_flags():
    return {
        "evidenceKind": "source_only_graph_assembly_or_user_trial_not_native",
        "sourceInterpretationIndependentlyAuthenticated": False,
        "sourceHashIsOwnerApproval": False,
        "graphDynamicSolverImplemented": False,
        "referenceBundleWritten": False,
        "historicalReferenceChanged": False,
        "independentlyCertifiedReference": False,
        "referenceAccuracyCertified": False,
        "nativeExecuted": False,
        "nativeQualified": False,
        "runtimeReady": False,
        "externalOwnerApprovalVerified": False,
        "fullGrid77Plus8Plus5Certified": False,
        "unfamiliarCompositionIndependentlyQualified": False,
    }


def assemble(raw, *, expected_sha256):
    """Derive reusable body and junction equations using proven static laws.

    For a rod oriented a->b, q_ab=G*(T_a - T_b), G in [lo,hi].
    Outgoing heat at node a is +q_ab, at node b is -q_ab.
    Body: C*dT/dt = -sum(outgoing q). Junction: sum(outgoing q)=0.
    Boundary temperature is fixed and boundary outward supply is sum(out q).
    No unknown temperature is calculated here.
    """
    need(type(raw) is bytes and type(expected_sha256) is str,
         "bounded source bytes and SHA identity required")
    try:
        facts = n4.parse_facts(raw, expected_sha256=expected_sha256)
        static = n4.create_static_candidate(raw, expected_sha256=expected_sha256)
        pi = n4.pi_rational_enclosure()
    except n4.PhysicalRefusal as exc:
        raise GraphRefusal("h1_n5: source/static physical admission refused") from exc
    # The N4 static physical candidate is a prerequisite, not a new
    # external seal or a promoted runtime reference.
    need(static["candidateValuesOnly"] is True
         and static["referenceAccuracyCertified"] is False
         and static["referenceBundleWritten"] is False,
         "static checker evidence changed")
    nodes = sorted(facts["nodes"])
    ports = {node: [] for node in nodes}
    rods = {}
    for name, rod in sorted(facts["rods"].items()):
        interval, area = _conductance_interval(rod, pi)
        need(interval[0] > 0 and interval[1] >= interval[0],
             "nonpositive source-exact conductance")
        a, b = rod["a"], rod["b"]
        need(a != b and a in ports and b in ports,
             "invalid rod-port graph")
        # The physical rod contributes +q_ab at a and -q_ab at b,
        # exactly once each, regardless of orientation or parallel edges.
        ports[a].append({"rod":name, "outwardFluxCoefficient":1,
                         "otherNode":b})
        ports[b].append({"rod":name, "outwardFluxCoefficient":-1,
                         "otherNode":a})
        rods[name] = {
            "kind": rod["kind"], "fromNode":a, "toNode":b,
            "areaM2ExactPhysicalInterval": interval_text(area),
            "conductanceWPerKExactPhysicalInterval": interval_text(interval),
            "staticPhysicalCandidateHex": static["exports"][name+".G"]["binary64Hex"],
            "outwardFluxLaw": "q_from_to=G*(T_from-T_to)",
        }
        if rod["kind"] == "RodCircular":
            need(name+".A" in static["exports"], "circular physical area missing")
    owned = {}
    for name, body in sorted(facts["bodies"].items()):
        node = body["node"]
        need(node not in owned, "multiply owned node")
        owned[node] = {
            "kind": "body", "owner": name,
            "capacityJPerKExact": fraction_text(
                _physical_positive(body["m"])*_physical_positive(body["c"])),
            "initialTemperatureKExact": fraction_text(
                _physical_positive(body["T_initial"])),
            "equation": "C*dT/dt=-sum(outwardRodHeatFlows)",
        }
        need(name+".C" in static["exports"], "body physical capacity missing")
    for name, boundary in sorted(facts["boundaries"].items()):
        node = boundary["node"]
        need(node not in owned, "multiply owned node")
        owned[node] = {
            "kind": "fixed_boundary", "owner": name,
            "temperatureKExact": fraction_text(
                _physical_positive(boundary["T"])),
            "equation": "T_node=T_prescribed; Q_supply=sum(outwardRodHeatFlows)",
        }
    equations = {}
    for node in nodes:
        ledger = sorted(ports[node], key=lambda item: item["rod"])
        entry = dict(owned.get(node, {
            "kind": "ownerless_junction", "owner": None,
            "equation": "sum(outwardRodHeatFlows)=0",
        }))
        entry["outwardRodPorts"] = ledger
        entry["portIncidence"] = len(ledger)
        if entry["kind"] == "ownerless_junction":
            need(len(ledger) >= 2, "ownerless open thermal port")
        equations[node] = entry
    # This identity is combinatorial, not a numeric all-grid certificate.
    for name, rod in rods.items():
        occurrences = [(node, port["outwardFluxCoefficient"])
                       for node, row in equations.items()
                       for port in row["outwardRodPorts"]
                       if port["rod"] == name]
        need(sorted(occurrences) == sorted([
            (rod["fromNode"], 1), (rod["toNode"], -1)
        ]), "rod energy-incidence identity broken")
    need(len(static["exports"]) ==
         len(facts["bodies"]) + len(facts["rods"]) +
         sum(r["kind"]=="RodCircular" for r in facts["rods"].values()),
         "static source export count differs from law inventory")
    return {
        "schema": SCHEMA,
        "stage": "offline_assembly_only_no_solver",
        "sourceFactsSha256": expected_sha256,
        "originalModelSha256": facts["modelSha256"],
        "originalStudySha256": facts["studySha256"],
        "studyId": facts["id"], "mode": facts["mode"],
        "method": "source-exact rational conductance intervals and signed port incidence",
        "nodes": nodes, "rodCount": len(rods),
        "bodies": len(facts["bodies"]), "boundaries": len(facts["boundaries"]),
        "junctions": sum(x["kind"]=="ownerless_junction"
                         for x in equations.values()),
        "rods": rods, "nodeEquations": equations,
        "staticPhysicalCandidateSchema": STATIC_VERSION,
        "structuralRodEnergyAntisymmetry": True,
        "structuralIdentityOnlyNotIntegratedConservationProof": True,
        **_provenance_flags(),
    }


def _exact_trial_temperature(value):
    # Strings avoid float64 guesses/rounding; no user-provided value is
    # treated as a solver result or used to fit checking tolerances.
    need(type(value) is str and 0 < len(value) <= 80,
         "trial temperatures require bounded decimal strings")
    try:
        decimal = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise GraphRefusal("h1_n5: malformed trial temperature") from exc
    need(decimal.is_finite() and len(decimal.as_tuple().digits)<=64
         and abs(decimal.as_tuple().exponent)<=250,
         "invalid trial numeric precision/exponent")
    temperature=F(decimal)
    need(0 < temperature <= 10**7,
         "trial temperature outside positive bounded Kelvin domain")
    return temperature


def _add(left, right):
    return (left[0]+right[0], left[1]+right[1])


def _neg(value):
    return (-value[1], -value[0])


def evaluate_trial(raw, *, expected_sha256, temperatures):
    """Evaluate heat flows for an ASSUMED temperature state; no solver involved.

    User-supplied values for ALL nodes, including algebraic junctions, are
    trial inputs. Nonzero junction residuals are reported, not repaired.
    """
    assembly=assemble(raw,expected_sha256=expected_sha256)
    need(type(temperatures) is dict
         and set(temperatures)==set(assembly["nodes"]),
         "one exact trial temperature required for each source node")
    t={name:_exact_trial_temperature(value)
       for name,value in temperatures.items()}
    for name,row in assembly["nodeEquations"].items():
        if row["kind"]=="fixed_boundary":
            need(t[name]==F(row["temperatureKExact"]),
                 "trial conflicts with maintained boundary temperature")
    node_out={node:(F(0),F(0)) for node in assembly["nodes"]}
    flows={}
    for name,rod in assembly["rods"].items():
        a,b=rod["fromNode"],rod["toNode"]
        lo,hi=(F(s) for s in rod["conductanceWPerKExactPhysicalInterval"])
        delta=t[a]-t[b]
        flow=(min(lo*delta,hi*delta),max(lo*delta,hi*delta))
        flows[name]={
            "fromNode":a,"toNode":b,"deltaTKExact":fraction_text(delta),
            "qFromToWExactPhysicalInterval":interval_text(flow),
            "kind":"assumed_node_temperatures_not_native_measurement",
        }
        node_out[a]=_add(node_out[a],flow)
        node_out[b]=_add(node_out[b],_neg(flow))
    balances={}
    for node,row in assembly["nodeEquations"].items():
        outgoing=node_out[node]
        result={
            "kind":row["kind"],
            "outgoingHeatFlowWInterval":interval_text(outgoing),
        }
        if row["kind"]=="body":
            cap=F(row["capacityJPerKExact"])
            result["dTdtKPerSInterval"] = interval_text(
                (-outgoing[1]/cap,-outgoing[0]/cap))
            result["interpretation"] = "instantaneous_trial_derivative_not_integrated_state"
        elif row["kind"]=="ownerless_junction":
            result["zeroWithinResidualInterval"] = (outgoing[0]<=0<=outgoing[1])
            result["interpretation"] = "algebraic_residual_not_automatically_solved"
        else:
            result["boundaryHeatSupplyWInterval"] = interval_text(outgoing)
            result["interpretation"] = "fixed_boundary_supply_outward_positive"
        balances[node]=result
    return {
        "schema":TRIAL_SCHEMA,
        "stage":"user_assumed_temperatures_no_time_solution",
        "assemblySchema":SCHEMA,
        "sourceFactsSha256":expected_sha256,
        "sourceStudyId":assembly["studyId"],
        "trialTemperatureKExact":{k:fraction_text(t[k]) for k in sorted(t)},
        "rodFlowFromToW":flows,
        "nodeBalances":balances,
        "rodAntisymmetryByConstruction":True,
        "junctionEquilibriumProved":False,
        "timeTrajectoryComputed":False,
        **_provenance_flags(),
    }
