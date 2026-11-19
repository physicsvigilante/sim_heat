"""Independent exact Fraction corner replay of H1-N7 algebraic enclosures.

This is an OFFLINE CROSS-CHECK, not a native reference or certificate.
N4's bounded source admission is reused, but numerical conductances, Machin
Pi enclosure, exact Cramer's-rule physical junction solve, source residual
r and signed universal barrier inequalities are independently recomputed
from source facts, not from the checked N7 conductance interval output.

Only at most four junctions/four uncertain circular rods are accepted.
Enclosure of all independent endpoint corners does NOT alone establish
universal enclosure; rowwise signed comparison inequalities are separately
reverified for every conductance in its full source interval.
"""
from __future__ import annotations

from fractions import Fraction as F
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from itertools import permutations, product
import json
import re

from qualification.h1_n4.static_physical import parse_facts, PhysicalRefusal

SCHEMA = "sim_heat.h1_n8.independent_corner_replay/1"
N7_SCHEMA = "sim_heat.h1_n7.verified_interval_junction_snapshot/1"
MAX_JUNCTIONS = 4
MAX_CIRCULAR = 4
MAX_BITS = 16384
ASCII = re.compile(r"[+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z",re.ASCII)


# Exact N7/1 schema under review: a cross-verifier must not report PASS on
# metadata whose authority, direction or physical sign it did not validate.
# The original source-model/study SHA identities are integrity strings,
# NEVER independently approved source evidence.
N7_VERSION = "h1_n7.verified_interval_dirichlet/1"
N7_STATUS = "VERIFIED_INTERVAL_ALGEBRAIC_JUNCTIONS_ONLY_NO_TRAJECTORY"
N7_STAGE = "offline_source_exact_rational_interval_junction_enclosure"
N7_ASSEMBLY = "sim_heat.h1_n5.thermal_graph_balance_candidate/1"
N7_LIMITATION = (
    "exact rational bounds for algebraic junction K only; "
    "no native source authority or time integration"
)
N7_FALSE_FIELDS = (
    "sourceInterpretationIndependentlyAuthenticated",
    "ownerApprovedExpectedReferenceManifestVerified",
    "independentlyCertifiedReference",
    "referenceAccuracyCertified",
    "referenceBundleWritten",
    "allGrid77Plus8Plus5Certified",
    "nativeExecuted",
    "nativeQualified",
    "runtimeReady",
    "timeTrajectoryComputed",
    "initialValueProblemSolved",
    "generalH1DynamicsQualified",
    "fullSystemAlgebraicAndDynamicStateSolved",
)
N7_TRUE_FIELDS = (
    "structuralRodEnergyAntisymmetry",
    "junctionEquilibriumExistsUniqueWithinEnclosures",
    "bodyRatesConditionalOnUserAssumedTemperatures",
    "physicalPiNotReplacedByNumericalMidpoint",
)
N7_REQUIRED_TOP = frozenset((
    "schema","version","status","stage",
    "sourceFactsSha256","sourceStudyId","assemblySchema",
    "graphSourceModelSha256","graphSourceStudySha256",
    "bodyTemperatureAssumptionsKExact","fixedBoundaryTemperaturesKExact",
    "allNodeTemperatureKExactPhysicalEnclosures",
    "junctionTemperatureEnclosuresK","junctionsEnclosed","rods",
    "hasCircularConductor","rodHeatFlows","nodeBalanceEnclosures",
    "proof","limitation",
    *N7_TRUE_FIELDS,*N7_FALSE_FIELDS,
))
N7_ROD_FIELDS = frozenset((
    "fromNode","toNode","positiveFromTo",
    "conductanceWPerKExactPhysicalInterval",
    "heatFlowWExactPhysicalEnclosure","orientation",
))
N7_PROOF_ROW_FIELDS = frozenset((
    "junctionNode","nominalProofCentreK","residualAbsoluteBoundW",
    "verifiedBarrierRadiusK","lowerBoundOnAllPhysicalLaplacianBarrierW",
    "enclosureK","trueKInsideEnclosureByComparison",
))


def _pair(value, description):
    need(type(value) is list and len(value)==2
         and all(type(item) is str for item in value),
         "malformed exact physical interval: "+description)
    try:
        lo,hi=(bounded(F(item)) for item in value)
    except (ValueError,OverflowError,TypeError,ZeroDivisionError) as exc:
        raise CornerRefusal("h1_n8: malformed rational interval: "+description) from exc
    need(lo<=hi,"reversed exact physical interval: "+description)
    return lo,hi


def _attest_n7_evidence_flags(report):
    need(type(report) is dict and set(report)==N7_REQUIRED_TOP,
         "N7 report schema contains missing/unreviewed evidence fields")
    need(report["schema"]==N7_SCHEMA
         and report["version"]==N7_VERSION
         and report["status"]==N7_STATUS
         and report["stage"]==N7_STAGE
         and report["assemblySchema"]==N7_ASSEMBLY
         and report["limitation"]==N7_LIMITATION,
         "N7 source-only contract/version/status drift")
    for name in N7_FALSE_FIELDS:
        need(report[name] is False,
             "untrusted N7 authority/native/certificate promotion: "+name)
    for name in N7_TRUE_FIELDS:
        need(report[name] is True,
             "N7 required source-only physical semantics drift: "+name)
    proof=report["proof"]
    need(type(proof) is dict and proof.get("barrierCertified") is True,
         "missing/unreviewed N7 algebraic proof")
    for name in ("proofIsIndependentNativeCertificate",
                 "nominalCentresArePhysicalAnswers"):
        need(name in proof and proof[name] is False,
             "untrusted N7 proof claims independent/native authority: "+name)
    need(type(report["rodHeatFlows"]) is dict
         and type(report["junctionTemperatureEnclosuresK"]) is dict
         and type(report["allNodeTemperatureKExactPhysicalEnclosures"]) is dict
         and type(report["bodyTemperatureAssumptionsKExact"]) is dict
         and type(report["fixedBoundaryTemperaturesKExact"]) is dict
         and type(report["nodeBalanceEnclosures"]) is dict
         and type(proof.get("rows")) is list,
         "malformed N7 required physical evidence collections")


def _check_source_and_node_report(report, facts, known, junctions, edges, circular):
    """Tie every reported label to original admission-checked source bytes."""
    need(report["sourceStudyId"]==facts["id"]
         and report["graphSourceModelSha256"]==facts["modelSha256"]
         and report["graphSourceStudySha256"]==facts["studySha256"],
         "source-fact model/study/ID metadata disagrees with source")
    need(type(report["junctionsEnclosed"]) is int
         and report["junctionsEnclosed"]==len(junctions)
         and type(report["rods"]) is int
         and report["rods"]==len(edges)
         and report["hasCircularConductor"] is bool(circular),
         "wrong graph inventory/circular law declaration")
    expected_body={v["node"]:str(known[v["node"]])
                   for v in facts["bodies"].values()}
    expected_boundary={v["node"]:str(known[v["node"]])
                       for v in facts["boundaries"].values()}
    need(report["bodyTemperatureAssumptionsKExact"]==expected_body,
         "reported assumed-body Kelvin values not source-bound")
    need(report["fixedBoundaryTemperaturesKExact"]==expected_boundary,
         "reported prescribed-boundary Kelvin values not source-bound")
    need(set(report["junctionTemperatureEnclosuresK"])==set(junctions)
         and set(report["allNodeTemperatureKExactPhysicalEnclosures"])==
             set(known)|set(junctions)
         and set(report["rodHeatFlows"])=={x[0] for x in edges}
         and set(report["nodeBalanceEnclosures"])==set(known)|set(junctions),
         "N7 graph output fields do not cover exact source inventory")
    for node,value in known.items():
        need(_pair(report["allNodeTemperatureKExactPhysicalEnclosures"][node],
                   "fixed/assumed "+node)==(value,value),
             "known-node temperature interval differs from source/assumption")
    for node in junctions:
        need(_pair(report["allNodeTemperatureKExactPhysicalEnclosures"][node],
                   "junction "+node)==
             _pair(report["junctionTemperatureEnclosuresK"][node],
                   "verified junction "+node),
             "all-node temperature enclosure contradicts junction proof")
    proof=report["proof"]
    if junctions:
        need(set(proof)=={
            "algorithm","premise","allConductancesCheckedAgainstSourcePhysicalIntervals",
            "nominalCentresArePhysicalAnswers",
            "trueJunctionEnclosedForAllAdmissibleConductances",
            "barrierCertified","proofIsIndependentNativeCertificate",
            "maximumPermittedEnclosureWidthK","rows",
        } and proof["algorithm"]==
            "EXACT_RATIONAL_MIDPOINT_RESIDUAL_AND_POSITIVE_M_MATRIX_BARRIER"
            and proof["premise"]==
            "positive_anchored_Dirichlet_Laplacian_inverse_entrywise_nonnegative"
            and proof["allConductancesCheckedAgainstSourcePhysicalIntervals"] is True
            and proof["trueJunctionEnclosedForAllAdmissibleConductances"] is True
            and F(proof["maximumPermittedEnclosureWidthK"])==F(1,10**6),
            "unreviewed or incomplete N7 universal proof declaration")
    else:
        need(set(proof)=={
            "algorithm","barrierCertified","nominalCentresArePhysicalAnswers",
            "proofIsIndependentNativeCertificate","rows",
        } and proof["algorithm"]=="NO_UNKNOWN_JUNCTIONS"
            and proof["rows"]==[],
            "invalid vacuous N7 proof declaration")


def _verify_full_physical_report(report, facts, known, junctions, enclosure, edges):
    """Exact node/rod labels, physical intervals and conditional heat balances."""
    node_temperatures={node:(value,value) for node,value in known.items()}
    node_temperatures.update(enclosure)
    out={node:(F(0),F(0)) for node in node_temperatures}
    for name,a,b,lo,hi in edges:
        record=report["rodHeatFlows"][name]
        need(type(record) is dict and set(record)==N7_ROD_FIELDS
             and record["fromNode"]==a and record["toNode"]==b
             and record["positiveFromTo"] is True
             and record["orientation"]=="q_from_to=G*(T_from-T_to)",
             "untrusted physical rod orientation/sign metadata: "+name)
        need(_pair(record["conductanceWPerKExactPhysicalInterval"],
                   "conductance "+name)==(lo,hi),
             "untrusted physical rod G interval/source label: "+name)
        a_lo,a_hi=node_temperatures[a]
        b_lo,b_hi=node_temperatures[b]
        dlo,dhi=a_lo-b_hi,a_hi-b_lo
        q=min(lo*dlo,lo*dhi,hi*dlo,hi*dhi),max(lo*dlo,lo*dhi,hi*dlo,hi*dhi)
        need(_pair(record["heatFlowWExactPhysicalEnclosure"],
                   "oriented heat "+name)==q,
             "source-rational rod heat-flow interval misrepresented: "+name)
        out[a]=(bounded(out[a][0]+q[0]),bounded(out[a][1]+q[1]))
        out[b]=(bounded(out[b][0]-q[1]),bounded(out[b][1]-q[0]))
    bybody={v["node"]:v for v in facts["bodies"].values()}
    byboundary={v["node"]:v for v in facts["boundaries"].values()}
    for node,balance in report["nodeBalanceEnclosures"].items():
        need(type(balance) is dict,"malformed source physical balance "+node)
        outgoing=out[node]
        need(_pair(balance.get("outwardHeatFlowWIndependentIntervalSum"),
                   "outflow "+node)==outgoing,
             "source physical signed node outflow misreported "+node)
        if node in bybody:
            capacity=bounded(F(bybody[node]["m"])*F(bybody[node]["c"]))
            need(capacity>0 and set(balance)=={
                     "kind","outwardHeatFlowWIndependentIntervalSum",
                     "conditionalDTdtKPerSInterval","note"
                 } and balance["kind"]=="body"
                 and balance["note"]==
                     "formal_rate_given_user_assumed_body_K_not_integrated"
                 and _pair(balance["conditionalDTdtKPerSInterval"],
                           "conditional body rate "+node)==
                     (bounded(-outgoing[1]/capacity),
                      bounded(-outgoing[0]/capacity)),
                 "reported conditional body rate is not source-physical "+node)
        elif node in byboundary:
            need(set(balance)=={
                     "kind","outwardHeatFlowWIndependentIntervalSum",
                     "boundarySupplyWEnclosure","note"
                 } and balance["kind"]=="fixed_boundary"
                 and balance["note"]=="outward_positive_boundary_heat_supply"
                 and _pair(balance["boundarySupplyWEnclosure"],
                           "boundary supply "+node)==outgoing,
                 "reported physical boundary supply inconsistent "+node)
        else:
            need(set(balance)=={
                     "kind","outwardHeatFlowWIndependentIntervalSum",
                     "junctionResidualExactlyZeroByVerifiedEquation","note"
                 } and balance["kind"]=="ownerless_junction"
                 and balance["junctionResidualExactlyZeroByVerifiedEquation"] is True
                 and balance["note"]==
                     "interval_sum_overbounds_correlated_true_zero_junction_flow"
                 and outgoing[0]<=0<=outgoing[1],
                 "reported source junction balance improperly labeled "+node)


class CornerRefusal(ValueError):
    pass

def need(ok, why):
    if not ok:
        raise CornerRefusal("h1_n8: "+why)

def bounded(value):
    need(type(value) is F and
         value.numerator.bit_length()<=MAX_BITS and
         value.denominator.bit_length()<=MAX_BITS,
         "independent exact-rational work bound exceeded")
    return value

def original_decimal(value):
    # JSON parsing here keeps decimal literals exact; never first uses float.
    need(type(value) in (int,F), "source number must be a JSON int or fraction")
    f=F(value)
    need(f>0, "positive source law parameter required")
    return bounded(f)

def pi_bounds():
    """Independently form Machin alternating-series endpoints in 40 steps.

    At 40 terms the next alternating arctan term is POSITIVE, so the partial
    is the rigorous lower bound and partial + next is the upper bound.
    """
    def arctan(q):
        s=F(0)
        x=F(1,q)
        for j in range(40):
            term=x**(2*j+1)/F(2*j+1)
            s=s+term if j%2==0 else s-term
        next_term=x**81/F(81)
        return s,s+next_term
    a0,a1=arctan(5)
    b0,b1=arctan(239)
    return bounded(16*a0-4*b1),bounded(16*a1-4*b0)

def ascii_kelvin(value):
    need(type(value) is str and len(value)<=80 and ASCII.fullmatch(value) is not None,
         "assumed body Kelvin must be an exact ASCII decimal string")
    try:
        d=Decimal(value)
    except (InvalidOperation,ValueError,OverflowError) as exc:
        raise CornerRefusal("h1_n8: bad source-independent assumed Kelvin") from exc
    need(d.is_finite() and len(d.as_tuple().digits)<=64
         and abs(d.as_tuple().exponent)<=250,
         "invalid assumed Kelvin precision")
    f=bounded(F(d))
    need(0<f<=10**7,"invalid positive Kelvin")
    return f

def _signed_det(matrix):
    """Permutation determinant, different algorithm from N6 Gauss–Jordan."""
    n=len(matrix)
    need(n<=MAX_JUNCTIONS and all(len(row)==n for row in matrix),
         "small determinant input required")
    if n==0:
        return F(1)
    total=F(0)
    for perm in permutations(range(n)):
        inversions=sum(perm[i]>perm[j] for i in range(n) for j in range(i+1,n))
        term=F(1)
        for i,j in enumerate(perm):
            term=bounded(term*matrix[i][j])
        total=bounded(total+(-term if inversions%2 else term))
    return total

def _matrix(junctions,known,edges,choice):
    n=len(junctions)
    index={node:i for i,node in enumerate(junctions)}
    mat=[[F(0) for _ in range(n)] for _ in range(n)]
    rhs=[F(0) for _ in range(n)]
    for name,a,b,lo,hi in edges:
        g=choice[name]
        need(lo<=g<=hi,"independent corner value outside exact physical bound")
        for node,other in ((a,b),(b,a)):
            if node not in index:
                continue
            j=index[node]
            mat[j][j]=bounded(mat[j][j]+g)
            if other in index:
                mat[j][index[other]]=bounded(mat[j][index[other]]-g)
            else:
                need(other in known,"unbound declared source node")
                rhs[j]=bounded(rhs[j]+g*known[other])
    return mat,rhs

def _cramer(mat,rhs):
    n=len(rhs)
    need(len(mat)==n and n<=MAX_JUNCTIONS,"Cramer's dimension outside review scope")
    if n==0:
        return []
    determinant=_signed_det(mat)
    need(determinant>0,"physical source graph not uniquely positive anchored")
    solutions=[]
    for col in range(n):
        changed=[[rhs[i] if j==col else mat[i][j]
                  for j in range(n)] for i in range(n)]
        solutions.append(bounded(_signed_det(changed)/determinant))
    for i in range(n):
        need(sum((mat[i][j]*solutions[j] for j in range(n)),F(0))==rhs[i],
             "independent Cramer residual failed")
    return solutions

def _source_graph(raw,expected_sha256,body_temperatures):
    need(type(raw) is bytes and type(expected_sha256) is str,
         "actual source facts bytes and hash required")
    try:
        admitted=parse_facts(raw,expected_sha256=expected_sha256)
    except PhysicalRefusal as exc:
        raise CornerRefusal("h1_n8: inherited N4 admission refused") from exc
    # Parse the SAME authenticated bytes independently with exact rational
    # numeric types; do not rely on N7's claimed geometry or rod values.
    facts=json.loads(raw.decode("utf-8"),parse_float=F,parse_int=int)
    nodes=set(facts["nodes"])
    body_nodes={record["node"] for record in facts["bodies"].values()}
    need(type(body_temperatures) is dict
         and set(body_temperatures)==body_nodes,
         "one user-assumed Kelvin for each body-owned node")
    known={node:ascii_kelvin(body_temperatures[node]) for node in body_nodes}
    for record in facts["boundaries"].values():
        known[record["node"]]=original_decimal(record["T"])
    junctions=sorted(nodes-set(known))
    need(len(junctions)<=MAX_JUNCTIONS,"too many unknown junctions for independent replay")
    pi0,pi1=pi_bounds()
    edges=[]
    circle=[]
    for name,rod in sorted(facts["rods"].items()):
        scale=original_decimal(rod["k"])/original_decimal(rod["L"])
        if rod["kind"]=="RodArea":
            g=bounded(scale*original_decimal(rod["A"]))
            lo,hi=g,g
        else:
            d=original_decimal(rod["d"])
            factor=bounded(scale*d*d/4)
            lo,hi=bounded(factor*pi0),bounded(factor*pi1)
            circle.append(name)
        need(0<lo<=hi,"invalid independent physical G")
        edges.append((name,rod["a"],rod["b"],lo,hi))
    need(len(circle)<=MAX_CIRCULAR,"too many uncertain circular rods for corner replay")
    return admitted,known,junctions,edges,circle

def _replay_impl(raw,*,expected_sha256,body_node_temperatures,reported):
    """Cross-check N7 against independent source Pi, Cramer's corners and rows.

    This consumes an N7 report as *untrusted data*; caller-supplied report,
    source SHA and body assumptions do NOT grant owner/source/native authority.
    """
    _attest_n7_evidence_flags(reported)
    need(reported["sourceFactsSha256"]==expected_sha256,
         "N7 source hash differs from independently supplied source bytes")
    facts,known,junctions,edges,circular=_source_graph(
        raw,expected_sha256,body_node_temperatures)
    _check_source_and_node_report(reported,facts,known,junctions,edges,circular)
    rows=reported["proof"]["rows"]
    need(len(rows)==len(junctions) and
         {row["junctionNode"] for row in rows}==set(junctions)
         and reported["proof"]["barrierCertified"] is True
         and reported["proof"]["nominalCentresArePhysicalAnswers"] is False,
         "missing N7 exact rational proof rows")
    need(all(type(row) is dict
             and set(row)==N7_PROOF_ROW_FIELDS
             and row["trueKInsideEnclosureByComparison"] is True
             and row["enclosureK"]==reported["junctionTemperatureEnclosuresK"][row["junctionNode"]]
             for row in rows),
         "N7 proof rows not consistent with published physical enclosures")
    bynode={row["junctionNode"]:row for row in rows}
    centre={}
    barriers={}
    radii={}
    for name in junctions:
        row=bynode[name]
        centre[name]=bounded(F(row["nominalProofCentreK"]))
        barriers[name]=bounded(F(row["verifiedBarrierRadiusK"]))
        radii[name]=bounded(F(row["residualAbsoluteBoundW"]))
        need(barriers[name]>=0 and radii[name]>=0,"negative physical comparison proof")
    centre_all={**known,**centre}
    # Authenticates the proof centre independently: the source-residual r
    # formula assumes x0 EXACTLY solves the midpoint equations. A merely
    # close/fitted centre could invalidate a claimed universal error bound.
    midpoint={name:bounded((lo+hi)/2) for name,_,_,lo,hi in edges}
    mid_mat,mid_rhs=_matrix(junctions,known,edges,midpoint)
    for j,name in enumerate(junctions):
        lhs=bounded(sum((mid_mat[j][k]*centre[junctions[k]]
                         for k in range(len(junctions))),F(0)))
        need(lhs==mid_rhs[j],
             "claimed midpoint proof centre does not solve exact midpoint equations")
    # Crucial universal check: signed worst-case row contributions from the
    # source-derived full G intervals, NOT just endpoint-sampled solutions.
    negative_gradients=0
    for node in junctions:
        residual=F(0)
        lower=F(0)
        for _,a,b,lo,hi in edges:
            if node!=a and node!=b:
                continue
            other=b if node==a else a
            residual=bounded(residual+(hi-lo)/2*abs(centre_all[node]-centre_all[other]))
            grad=barriers[node]-(barriers[other] if other in barriers else F(0))
            if lo!=hi and grad<0:
                negative_gradients+=1
            lower=bounded(lower+(lo if grad>=0 else hi)*grad)
        need(residual==radii[node],
             "independent source-residual bound disagrees with N7 proof")
        need(lower==bounded(F(bynode[node]["lowerBoundOnAllPhysicalLaplacianBarrierW"]))
             and lower>=radii[node],
             "universal signed-gradient M-matrix barrier not proved")
    enclosure={name:tuple(map(F,reported["junctionTemperatureEnclosuresK"][name]))
               for name in junctions}
    need(all(lo<=hi for lo,hi in enclosure.values()),
         "invalid reported junction interval")
    # N7 publishes the intersection of the proven ±barrier and a passive
    # known-source temperature envelope. The *entire* certified interval must
    # be contained in the report; merely including the nominal midpoint is
    # insufficient and could admit a post-hoc narrowed, uncertified claim.
    known_lo,known_hi=min(known.values()),max(known.values())
    for name in junctions:
        lo,hi=enclosure[name]
        # N7/1 also promises a *maximum published resolution*, not merely
        # mathematical containment of the true physical temperature.
        # Independently verify that the claimed full width honours the
        # source-only precision limit. The zero-junction proof has no such
        # field and intentionally does not enter this loop.
        maximum_width=F(reported["proof"]["maximumPermittedEnclosureWidthK"])
        need(F(0)<=hi-lo<=maximum_width,
             "published junction enclosure width exceeds declared maximum")
        safe_lo=max(known_lo,centre[name]-barriers[name])
        safe_hi=min(known_hi,centre[name]+barriers[name])
        need(safe_lo<=safe_hi and lo<=safe_lo<=safe_hi<=hi,
             "reported enclosure not covering universal certified envelope")
    # An N8 PASS includes *all* human-readable N7 physical metadata, not
    # merely its correct 16 sampled numeric corners. Rebuild signed flow,
    # conductance and per-node rate intervals independently from source.
    _verify_full_physical_report(reported,facts,known,junctions,enclosure,edges)
    corner_outputs=[]
    for signs in product((0,1),repeat=len(circular)):
        selected={name:bit for name,bit in zip(circular,signs)}
        choice={name:(hi if selected.get(name,0) else lo)
                for name,_,_,lo,hi in edges}
        mat,rhs=_matrix(junctions,known,edges,choice)
        x=_cramer(mat,rhs)
        actual={**known,**dict(zip(junctions,x))}
        for node in junctions:
            lo,hi=enclosure[node]
            need(lo<=actual[node]<=hi,
                 "independent exact physical corner outside N7 enclosure")
        for j,node in enumerate(junctions):
            lhs=bounded(sum((mat[j][k]*centre[junctions[k]]
                             for k in range(len(junctions))),F(0)))
            need(abs(rhs[j]-lhs)<=radii[node],"corner residual exceeds universal r")
            av=bounded(sum((mat[j][k]*barriers[junctions[k]]
                            for k in range(len(junctions))),F(0)))
            need(av>=radii[node],"corner violates verified A(g)v lower row")
        for name,a,b,_,_ in edges:
            q=bounded(choice[name]*(actual[a]-actual[b]))
            lo,hi=(F(z) for z in reported["rodHeatFlows"][name]["heatFlowWExactPhysicalEnclosure"])
            need(lo<=q<=hi,"corner physical heat flow not contained")
        corner_outputs.append({"uncertainEndpointChoices":selected,
                               "temperaturesKExact":{k:str(actual[k]) for k in junctions}})
    return {
        "schema":SCHEMA,
        "status":"OFFLINE_INDEPENDENT_SOURCE_CORNER_AND_SIGNED_BARRIER_CROSSCHECK_PASS",
        "sourceFactsSha256":expected_sha256,
        "sourceStudyId":facts["id"],
        "method":"independent_decimal_Pi_and_permutation_Cramer_plus_full_interval_row_inequality",
        "junctionsCompared":len(junctions),
        "uncertainCircularRods":len(circular),
        "endpointCornersChecked":len(corner_outputs),
        "negativeUnknownGradientContributionsChecked":negative_gradients,
        "universalRowComparisonVerified":True,
        "universalEnclosureFollowsPositiveDirichletInverse":True,
        "cornerChecksAloneNotUniversalProof":True,
        "nativeExecuted":False,
        "nativeQualified":False,
        "referenceAccuracyCertified":False,
        "independentlyCertifiedReference":False,
        "fullGrid77Plus8Plus5Certified":False,
        "referenceBundleWritten":False,
        "ownerApprovedSourceManifestVerified":False,
        "timeTrajectoryComputed":False,
        "unfamiliarCompositionIndependentlyQualified":False,
        "cornerReadouts":corner_outputs,
    }


def replay(raw,*,expected_sha256,body_node_temperatures,reported):
    """Fail-closed public boundary for untrusted N7 results/source metadata."""
    try:
        return _replay_impl(raw,expected_sha256=expected_sha256,
                            body_node_temperatures=body_node_temperatures,
                            reported=reported)
    except CornerRefusal:
        raise
    except (KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError,
            UnicodeError,RecursionError,ArithmeticError) as exc:
        raise CornerRefusal("h1_n8: malformed untrusted N7 report/source") from exc
