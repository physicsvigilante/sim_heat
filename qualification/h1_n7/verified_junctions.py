"""Offline rigorous junction-temperature enclosures for admitted H1 RodCircular graphs.

The true source-real conductance of every rod is contained in an exact
rational interval inherited from N4/N5 (Machin Pi for circular areas).
A midpoint Dirichlet solution is used ONLY as a proof centre. A positive
rational barrier is verified against ALL conductances in their intervals,
certifying a two-sided bound via the nonnegative inverse of the anchored
graph's M-matrix. No midpoint is represented as a physical exact answer.

No native simulator, trajectory, reference-bundle adoption or approval.
"""
from __future__ import annotations

from fractions import Fraction as F

from qualification.h1_n5 import thermal_graph as n5
from qualification.h1_n6 import exact_junctions as n6

SCHEMA = "sim_heat.h1_n7.verified_interval_junction_snapshot/1"
VERSION = "h1_n7.verified_interval_dirichlet/1"
MAX_JUNCTIONS = 12
MAX_PROOF_WIDTH_K = F(1, 10**6)


class IntervalJunctionRefusal(ValueError):
    """Exact interval/physical/refusal contract is not satisfied."""


def need(condition, message):
    if not condition:
        raise IntervalJunctionRefusal("h1_n7: " + message)


def bounded(value):
    need(type(value) is F and
         value.numerator.bit_length() <= n6.MAX_FRACTION_BITS and
         value.denominator.bit_length() <= n6.MAX_FRACTION_BITS,
         "unbounded rational interval/proof intermediate")
    return value


def _s(value):
    return str(bounded(value))


def _sinterval(lo, hi):
    need(lo <= hi, "interval order violation")
    return [_s(lo), _s(hi)]


def _add(x, y):
    return (bounded(x[0]+y[0]), bounded(x[1]+y[1]))


def _neg(x):
    return (bounded(-x[1]), bounded(-x[0]))


def _mul_pos_interval(glo, ghi, delta_lo, delta_hi):
    need(0 < glo <= ghi and delta_lo <= delta_hi,
         "invalid positive conductance or temperature interval")
    values=(bounded(glo*delta_lo), bounded(glo*delta_hi),
            bounded(ghi*delta_lo), bounded(ghi*delta_hi))
    return min(values), max(values)


def _positive_solver(matrix, rhs):
    try:
        return [bounded(x) for x in n6._solve_positive_dirichlet_laplacian(matrix, rhs)]
    except (n6.JunctionRefusal, ZeroDivisionError, OverflowError) as exc:
        raise IntervalJunctionRefusal("h1_n7: exact anchored Laplacian solve refused") from exc


def _enclosure_from_verified_barrier(junctions, known, edges):
    """Compute and verify a rational interval containing every physical solution.

    For g_e in [lo_e, hi_e], define midpoint g0 and exact nominal x0.
    Residual |b(g)-A(g)x0| <= r, componentwise, with
      r_j = sum_e ((hi_e-lo_e)/2)*|x0_j-x0_other|.
    Find nonnegative v with A(g)v >= r for EVERY admissible g, where
    the value of v on every known Dirichlet node is zero. A(g)^-1 >= 0
    for positive conductance graphs anchored to fixed or assumed T.
    Thus x0-v <= x(g) <= x0+v. All inequalities are exact rationals.
    """
    index={name:i for i,name in enumerate(junctions)}
    n=len(junctions)
    need(n<=MAX_JUNCTIONS, "too many unknown source junctions")
    if n==0:
        return {}, {"algorithm":"NO_UNKNOWN_JUNCTIONS", "barrierCertified":True,
                    "nominalCentresArePhysicalAnswers":False,
                    "proofIsIndependentNativeCertificate":False,
                    "rows":[]}

    mat=[[F(0) for _ in range(n)] for _ in range(n)]
    rhs=[F(0) for _ in range(n)]
    for _,a,b,lo,hi in edges:
        mid=bounded((lo+hi)/2)
        for this,other in ((a,b),(b,a)):
            if this not in index:
                continue
            j=index[this]
            mat[j][j]=bounded(mat[j][j]+mid)
            if other in index:
                mat[j][index[other]]=bounded(mat[j][index[other]]-mid)
            else:
                need(other in known, "missing known-neighbour temperature")
                rhs[j]=bounded(rhs[j]+mid*known[other])

    centre=_positive_solver(mat,rhs)
    nominal=dict(known)
    nominal.update({node:centre[i] for i,node in enumerate(junctions)})
    for j,node in enumerate(junctions):
        residual=bounded(sum((mat[j][k]*centre[k] for k in range(n)),F(0))-rhs[j])
        need(residual==0, "nominal rational centre not exact Laplacian solution")

    radius=[F(0) for _ in range(n)]
    for _,a,b,lo,hi in edges:
        delta_g=bounded((hi-lo)/2)
        if delta_g==0:
            continue
        difference=bounded(abs(nominal[a]-nominal[b]))
        for node in (a,b):
            if node in index:
                j=index[node]
                radius[j]=bounded(radius[j]+delta_g*difference)
    maximum=max(radius)
    barrier=[F(0) for _ in range(n)]
    lower_row=[F(0) for _ in range(n)]
    if maximum>0:
        # Add a strictly positive buffer at EVERY unknown node. Without it,
        # a radius-zero interior row may have no slack under coefficient drift.
        buffered=[bounded(r+maximum/1024) for r in radius]
        initial=_positive_solver(mat,buffered)
        barrier=[bounded(F(4)*v) for v in initial]
        need(all(v>0 for v in barrier), "nonpositive barrier candidate")

        for _,a,b,lo,hi in edges:
            for this,other in ((a,b),(b,a)):
                if this not in index:
                    continue
                j=index[this]
                v_this=barrier[j]
                v_other=barrier[index[other]] if other in index else F(0)
                gradient=bounded(v_this-v_other)
                # Correct minimum of g*(v_this-v_other) over g in [lo,hi].
                g=lo if gradient>=0 else hi
                lower_row[j]=bounded(lower_row[j]+g*gradient)
        need(all(lower_row[j]>=radius[j] for j in range(n)),
             "unable to certify a nonnegative M-matrix comparison barrier")
    else:
        # r==0 implies x0 solves the true equations for all allowed g.
        # Positive anchored conductances imply uniqueness, so v=0 is valid.
        need(all(r==0 for r in radius),"unresolved zero residual bound")

    lo_known, hi_known=min(known.values()),max(known.values())
    enclosures={}
    rows=[]
    for j,node in enumerate(junctions):
        lower=bounded(max(lo_known,centre[j]-barrier[j]))
        upper=bounded(min(hi_known,centre[j]+barrier[j]))
        need(0<lower<=upper and upper-lower<=MAX_PROOF_WIDTH_K,
             "junction enclosure exceeds bounded exploratory precision")
        enclosures[node]=(lower,upper)
        rows.append({
            "junctionNode":node,
            "nominalProofCentreK":_s(centre[j]),
            "residualAbsoluteBoundW":_s(radius[j]),
            "verifiedBarrierRadiusK":_s(barrier[j]),
            "lowerBoundOnAllPhysicalLaplacianBarrierW":_s(lower_row[j]),
            "enclosureK":_sinterval(lower,upper),
            "trueKInsideEnclosureByComparison":True,
        })
    proof={
        "algorithm":"EXACT_RATIONAL_MIDPOINT_RESIDUAL_AND_POSITIVE_M_MATRIX_BARRIER",
        "premise":"positive_anchored_Dirichlet_Laplacian_inverse_entrywise_nonnegative",
        "allConductancesCheckedAgainstSourcePhysicalIntervals":True,
        "nominalCentresArePhysicalAnswers":False,
        "trueJunctionEnclosedForAllAdmissibleConductances":True,
        "barrierCertified":True,
        "proofIsIndependentNativeCertificate":False,
        "maximumPermittedEnclosureWidthK":_s(MAX_PROOF_WIDTH_K),
        "rows":rows,
    }
    return enclosures,proof


def solve_snapshot(raw, *, expected_sha256, body_node_temperatures):
    """Certified-by-local-rational-barrier *algebraic* enclosure only.

    User-provided body temperatures are assumed; fixed boundaries are from
    source facts. No time integration or exact point solution is fabricated
    when the physical Pi-dependent conductance remains an interval.
    """
    need(type(raw) is bytes and type(expected_sha256) is str,
         "raw physical source bytes and external SHA string required")
    try:
        graph=n5.assemble(raw,expected_sha256=expected_sha256)
    except n5.GraphRefusal as exc:
        raise IntervalJunctionRefusal("h1_n7: N5/N4 source admission refused") from exc
    need(graph["schema"]==n5.SCHEMA
         and graph["graphDynamicSolverImplemented"] is False
         and graph["nativeExecuted"] is False
         and graph["referenceAccuracyCertified"] is False,
         "unexpected graph evidence/authority promotion")
    body_nodes=sorted(node for node,entry in graph["nodeEquations"].items()
                      if entry["kind"]=="body")
    need(type(body_node_temperatures) is dict
         and set(body_node_temperatures)==set(body_nodes),
         "one exact assumed temperature for each body node")
    known={}
    try:
        for node in body_nodes:
            known[node]=bounded(n6.exact_ascii_kelvin(body_node_temperatures[node]))
    except n6.JunctionRefusal as exc:
        raise IntervalJunctionRefusal("h1_n7: invalid assumed body Kelvin") from exc
    for node,entry in graph["nodeEquations"].items():
        if entry["kind"]=="fixed_boundary":
            known[node]=bounded(F(entry["temperatureKExact"]))
    junctions=sorted(node for node,entry in graph["nodeEquations"].items()
                     if entry["kind"]=="ownerless_junction")
    need(len(known)>0 and len(junctions)<=MAX_JUNCTIONS,
         "missing anchor or unsupported unknown-junction inventory")
    edges=[]
    for name,rod in sorted(graph["rods"].items()):
        lo,hi=(bounded(F(s)) for s in rod["conductanceWPerKExactPhysicalInterval"])
        need(0<lo<=hi,"nonpositive physical conductance interval")
        edges.append((name,rod["fromNode"],rod["toNode"],lo,hi))
    enclosures,proof=_enclosure_from_verified_barrier(junctions,known,edges)
    nodeT={node:(value,value) for node,value in known.items()}
    nodeT.update(enclosures)
    need(set(nodeT)==set(graph["nodes"]),"missing node physical temperature interval")
    outgoing={node:(F(0),F(0)) for node in graph["nodes"]}
    flows={}
    for name,a,b,lo,hi in edges:
        da=bounded(nodeT[a][0]-nodeT[b][1])
        db=bounded(nodeT[a][1]-nodeT[b][0])
        q=_mul_pos_interval(lo,hi,da,db)
        flows[name]={
            "fromNode":a,"toNode":b,
            "positiveFromTo":True,
            "conductanceWPerKExactPhysicalInterval":_sinterval(lo,hi),
            "heatFlowWExactPhysicalEnclosure":_sinterval(*q),
            "orientation":"q_from_to=G*(T_from-T_to)",
        }
        outgoing[a]=_add(outgoing[a],q)
        outgoing[b]=_add(outgoing[b],_neg(q))
    balances={}
    for node,entry in graph["nodeEquations"].items():
        lo,hi=outgoing[node]
        row={
            "kind":entry["kind"],
            "outwardHeatFlowWIndependentIntervalSum":_sinterval(lo,hi),
        }
        if entry["kind"]=="ownerless_junction":
            need(lo<=0<=hi,
                 "true zero junction residual not enclosed by flow intervals")
            row["junctionResidualExactlyZeroByVerifiedEquation"]=True
            row["note"]="interval_sum_overbounds_correlated_true_zero_junction_flow"
        elif entry["kind"]=="body":
            cap=bounded(F(entry["capacityJPerKExact"]))
            need(cap>0,"invalid exact body capacity")
            row["conditionalDTdtKPerSInterval"]=_sinterval(
                bounded(-hi/cap),bounded(-lo/cap))
            row["note"]="formal_rate_given_user_assumed_body_K_not_integrated"
        else:
            row["boundarySupplyWEnclosure"]=_sinterval(lo,hi)
            row["note"]="outward_positive_boundary_heat_supply"
        balances[node]=row

    flags={
        "sourceInterpretationIndependentlyAuthenticated":False,
        "ownerApprovedExpectedReferenceManifestVerified":False,
        "independentlyCertifiedReference":False,
        "referenceAccuracyCertified":False,
        "referenceBundleWritten":False,
        "allGrid77Plus8Plus5Certified":False,
        "nativeExecuted":False,
        "nativeQualified":False,
        "runtimeReady":False,
        "timeTrajectoryComputed":False,
        "initialValueProblemSolved":False,
        "generalH1DynamicsQualified":False,
        "fullSystemAlgebraicAndDynamicStateSolved":False,
    }
    return {
        "schema":SCHEMA,
        "version":VERSION,
        "status":"VERIFIED_INTERVAL_ALGEBRAIC_JUNCTIONS_ONLY_NO_TRAJECTORY",
        "stage":"offline_source_exact_rational_interval_junction_enclosure",
        "sourceFactsSha256":expected_sha256,
        "sourceStudyId":graph["studyId"],
        "assemblySchema":n5.SCHEMA,
        "graphSourceModelSha256":graph["originalModelSha256"],
        "graphSourceStudySha256":graph["originalStudySha256"],
        "bodyTemperatureAssumptionsKExact":{n:_s(known[n]) for n in body_nodes},
        "fixedBoundaryTemperaturesKExact":{n:_s(known[n]) for n in known if n not in body_nodes},
        "allNodeTemperatureKExactPhysicalEnclosures":{
            n:_sinterval(*nodeT[n]) for n in sorted(nodeT)
        },
        "junctionTemperatureEnclosuresK":{
            n:_sinterval(*enclosures[n]) for n in sorted(enclosures)
        },
        "junctionsEnclosed":len(junctions),
        "rods":len(edges),
        "hasCircularConductor":any(row["kind"]=="RodCircular" for row in graph["rods"].values()),
        "rodHeatFlows":flows,
        "nodeBalanceEnclosures":balances,
        "proof":proof,
        "structuralRodEnergyAntisymmetry":True,
        "junctionEquilibriumExistsUniqueWithinEnclosures":True,
        "bodyRatesConditionalOnUserAssumedTemperatures":True,
        "physicalPiNotReplacedByNumericalMidpoint":True,
        "limitation":"exact rational bounds for algebraic junction K only; no native source authority or time integration",
        **flags,
    }
