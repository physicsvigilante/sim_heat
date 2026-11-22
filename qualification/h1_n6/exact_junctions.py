"""Offline exact-rational junction equilibrium for admitted H1 RodArea graphs.

Educational algebraic *snapshot* only: body temperatures are explicit user
assumptions, boundary temperatures come from physical source facts, ownerless
junctions are solved exactly, and body heat rates are conditional instantaneous
derivatives. NO dynamic time integration, circular-Pi approximation, native
runtime, provenance authority, or runner-consumable reference is produced.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction as F
import re

from qualification.h1_n5 import thermal_graph as n5

SCHEMA = "sim_heat.h1_n6.exact_area_junction_snapshot/1"
CHECKER_VERSION = "h1_n6.exact_area_junctions/1"
MAX_JUNCTIONS = 20
MAX_FRACTION_BITS = 16384
ASCII_DECIMAL = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z",
    re.ASCII,
)


class JunctionRefusal(ValueError):
    """An invalid or unsupported source/temperature/junction premise."""


def need(condition, message):
    if not condition:
        raise JunctionRefusal("h1_n6: " + message)


def bounded(value):
    need(type(value) is F
         and value.numerator.bit_length() <= MAX_FRACTION_BITS
         and value.denominator.bit_length() <= MAX_FRACTION_BITS,
         "exact rational intermediate exceeds bounded proof scope")
    return value


def exact_ascii_kelvin(value):
    """One full-match ASCII numeric token, not Decimal's Unicode/space syntax."""
    need(type(value) is str and 0 < len(value) <= 80
         and ASCII_DECIMAL.fullmatch(value) is not None,
         "one canonical ASCII decimal temperature token required")
    try:
        d = Decimal(value)
    except (InvalidOperation, OverflowError, ValueError) as exc:
        raise JunctionRefusal("h1_n6: invalid exact temperature") from exc
    need(d.is_finite() and len(d.as_tuple().digits) <= 64
         and abs(d.as_tuple().exponent) <= 250,
         "bounded finite decimal temperature required")
    result = bounded(F(d))
    need(0 < result <= F(10**7), "positive bounded Kelvin temperature required")
    return result


def _solve_positive_dirichlet_laplacian(a, rhs):
    """Exact Gaussian elimination for an anchored symmetric positive graph.

    A is the unknown-junction principal Dirichlet Laplacian. For admitted
    positive conductances, every unknown component is anchored to a known
    node, so A is SPD. Each exact positive pivot is asserted; refuse rather
    than silently regularize singular or out-of-budget systems.
    """
    n = len(rhs)
    need(n <= MAX_JUNCTIONS and len(a) == n
         and all(type(row) is list and len(row) == n for row in a),
         "unsupported junction matrix dimension")
    if n == 0:
        return []
    mat = [[bounded(F(v)) for v in row] for row in a]
    b = [bounded(F(v)) for v in rhs]
    for j in range(n):
        pivot = mat[j][j]
        need(pivot > 0, "Dirichlet system is unanchored or not positive definite")
        inv = bounded(F(1) / pivot)
        for k in range(j, n):
            mat[j][k] = bounded(mat[j][k] * inv)
        b[j] = bounded(b[j] * inv)
        for i in range(n):
            if i == j:
                continue
            factor = mat[i][j]
            if factor == 0:
                continue
            for k in range(j, n):
                mat[i][k] = bounded(mat[i][k] - factor * mat[j][k])
            b[i] = bounded(b[i] - factor * b[j])
    need(all(mat[i][j] == F(int(i == j))
             for i in range(n) for j in range(n)),
         "exact Gauss-Jordan certificate is not identity")
    return b


def solve_snapshot(raw, *, expected_sha256, body_node_temperatures):
    """Solve ONLY storage-free junction temperatures, from exact area-rod G.

    The caller supplies each body-owned node T explicitly. Source-fixed
    boundaries are loaded from the authenticated-in-this-call physical facts.
    Any circular rod is deliberately REFUSED: replacing rigorous Pi interval
    conductances by midpoints would not be an exact physical solution.
    """
    need(type(raw) is bytes and type(expected_sha256) is str,
         "source bytes and SHA pin required")
    try:
        graph = n5.assemble(raw, expected_sha256=expected_sha256)
    except n5.GraphRefusal as exc:
        raise JunctionRefusal("h1_n6: N5 source graph admission refused") from exc
    need(graph["schema"] == n5.SCHEMA
         and graph["graphDynamicSolverImplemented"] is False
         and graph["referenceAccuracyCertified"] is False
         and graph["nativeExecuted"] is False,
         "source graph claimed unsupported solver or native evidence")
    rods = graph["rods"]
    need(all(r["kind"] == "RodArea" for r in rods.values()),
         "circular conductor requires a future interval-safe junction solver")
    body_nodes = sorted(name for name, node in graph["nodeEquations"].items()
                        if node["kind"] == "body")
    need(type(body_node_temperatures) is dict
         and set(body_node_temperatures) == set(body_nodes),
         "one assumed temperature per BODY node required")
    known = {node: exact_ascii_kelvin(body_node_temperatures[node])
             for node in body_nodes}
    for node, row in graph["nodeEquations"].items():
        if row["kind"] == "fixed_boundary":
            known[node] = bounded(F(row["temperatureKExact"]))
    junctions = sorted(node for node, row in graph["nodeEquations"].items()
                       if row["kind"] == "ownerless_junction")
    need(0 < len(known) <= 64 and len(junctions) <= MAX_JUNCTIONS,
         "at least one physical anchor and bounded unknown junction count required")
    index = {node: i for i, node in enumerate(junctions)}
    n = len(junctions)
    lap = [[F(0) for _ in range(n)] for _ in range(n)]
    rhs = [F(0) for _ in range(n)]
    edges = []
    for rod_name, r in sorted(rods.items()):
        a, b = r["fromNode"], r["toNode"]
        lo, hi = (F(x) for x in r["conductanceWPerKExactPhysicalInterval"])
        need(lo == hi and lo > 0, "area conductance must be a positive exact rational")
        g = bounded(lo)
        edges.append((rod_name, a, b, g))
        for node, other in ((a, b), (b, a)):
            if node not in index:
                continue
            j = index[node]
            lap[j][j] = bounded(lap[j][j] + g)
            if other in index:
                lap[j][index[other]] = bounded(lap[j][index[other]] - g)
            else:
                need(other in known, "unbound graph neighbour")
                rhs[j] = bounded(rhs[j] + g * known[other])
    initial_lap = [row[:] for row in lap]
    initial_rhs = rhs[:]
    junction_values = _solve_positive_dirichlet_laplacian(lap, rhs)
    full = dict(known)
    full.update({name: bounded(value) for name, value in zip(junctions, junction_values)})
    need(set(full) == set(graph["nodes"]), "incomplete solved node inventory")
    # Discrete maximum principle for positive passive conductances and a
    # Dirichlet graph: every junction T lies in the known-anchor range.
    lowest, highest = min(known.values()), max(known.values())
    need(all(lowest <= t <= highest for t in junction_values),
         "passive Dirichlet temperature exceeds known-source envelope")
    for j, name in enumerate(junctions):
        lhs = sum((initial_lap[j][k] * full[node]
                   for k, node in enumerate(junctions)), F(0))
        need(bounded(lhs) == initial_rhs[j],
             "solved junction fails original exact nodal balance: " + name)
    node_out = {node: F(0) for node in graph["nodes"]}
    flows = {}
    for rod_name, a, b, g in edges:
        q = bounded(g * (full[a] - full[b]))
        node_out[a] = bounded(node_out[a] + q)
        node_out[b] = bounded(node_out[b] - q)
        flows[rod_name] = {
            "fromNode": a, "toNode": b,
            "positiveFromTo": True,
            "heatFlowWExact": str(q),
        }
    need(sum(node_out.values(), F(0)) == F(0),
         "structural global rod energy antisymmetry broken")
    need(all(node_out[node] == F(0) for node in junctions),
         "junction conservation not exact after solution")
    body_rates = {}
    boundary_supplies = {}
    for node, row in graph["nodeEquations"].items():
        if row["kind"] == "body":
            capacity = bounded(F(row["capacityJPerKExact"]))
            need(capacity > 0, "nonpositive body thermal capacity")
            body_rates[node] = str(bounded(-node_out[node] / capacity))
        if row["kind"] == "fixed_boundary":
            boundary_supplies[node] = str(node_out[node])
    result = {
        "schema": SCHEMA,
        "version": CHECKER_VERSION,
        "stage": "offline_exact_algebraic_junctions_at_user_assumed_body_T",
        "status": "EXACT_JUNCTION_EQUILIBRIUM_ONLY_NO_TRAJECTORY",
        "originalSourceFactsSha256": expected_sha256,
        "sourceStudyId": graph["studyId"],
        "assemblySchema": n5.SCHEMA,
        "staticCandidateSchema": graph["staticPhysicalCandidateSchema"],
        "rodDomain": "RodArea_ONLY",
        "rodCount": len(edges),
        "junctionsSolved": len(junctions),
        "bodyOwnedNodes": body_nodes,
        "junctionSolvedTemperaturesKExact": {node: str(full[node]) for node in junctions},
        "knownBodyTemperatureKExact": {node: str(known[node]) for node in body_nodes},
        "prescribedBoundaryTemperatureKExact": {
            node: str(known[node]) for node, row in graph["nodeEquations"].items()
            if row["kind"] == "fixed_boundary"},
        "allNodeTemperatureKExact": {node: str(full[node]) for node in sorted(full)},
        "rodHeatFlows": flows,
        "outgoingNodeHeatFlowWExact": {node: str(node_out[node]) for node in sorted(node_out)},
        "junctionResidualWExact": {node: str(node_out[node]) for node in junctions},
        "instantaneousBodyRateKPerSExact": body_rates,
        "boundarySupplyWExact": boundary_supplies,
        "totalNodeOutwardHeatFlowWExact": "0",
        "junctionsAlgebraicallySolved": True,
        "bodyRatesConditionalOnUserAssumedBodyTemperatures": True,
        "sourceFixedBoundariesEnforced": True,
        "timeTrajectoryComputed": False,
        "initialValueProblemSolved": False,
        "allGridAccuracyCertified": False,
        "referenceBundleWritten": False,
        "referenceAccuracyCertified": False,
        "independentlyCertifiedReference": False,
        "fullGrid77Plus8Plus5Certified": False,
        "runtimeReady": False,
        "nativeExecuted": False,
        "nativeQualified": False,
        "sourceInterpretationIndependentlyAuthenticated": False,
        "externalOwnerApprovalVerified": False,
        "generalH1DynamicsQualified": False,
        "limitation": "algebraic junctions only; source-authenticity and time integration not qualified",
    }
    return result
