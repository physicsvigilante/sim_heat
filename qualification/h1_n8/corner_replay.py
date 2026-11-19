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

def replay(raw,*,expected_sha256,body_node_temperatures,reported):
    """Cross-check N7 against independent source Pi, Cramer's corners and rows.

    This consumes an N7 report as *untrusted data*; caller-supplied report,
    source SHA and body assumptions do NOT grant owner/source/native authority.
    """
    need(type(reported) is dict and reported.get("schema")==N7_SCHEMA
         and reported.get("sourceFactsSha256")==expected_sha256
         and reported.get("referenceAccuracyCertified") is False
         and reported.get("nativeQualified") is False
         and reported.get("nativeExecuted") is False
         and reported.get("timeTrajectoryComputed") is False,
         "unexpected source claim or N7 reference/native promotion")
    facts,known,junctions,edges,circular=_source_graph(
        raw,expected_sha256,body_node_temperatures)
    need(reported.get("sourceStudyId")==facts["id"]
         and reported.get("junctionsEnclosed")==len(junctions)
         and reported.get("rods")==len(edges),
         "declared graph identity and inventory mismatch")
    need(set(reported["junctionTemperatureEnclosuresK"])==set(junctions)
         and set(reported["rodHeatFlows"])=={e[0] for e in edges},
         "incomplete N7 output inventory")
    rows=reported["proof"]["rows"]
    need(len(rows)==len(junctions) and
         {row["junctionNode"] for row in rows}==set(junctions)
         and reported["proof"]["barrierCertified"] is True
         and reported["proof"]["nominalCentresArePhysicalAnswers"] is False,
         "missing N7 exact rational proof rows")
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
    for name in junctions:
        lo,hi=enclosure[name]
        need(lo<=centre[name]-barriers[name]<=centre[name]+barriers[name]<=hi
             or (lo>=min(known.values()) and hi<=max(known.values())
                 and lo<=centre[name]<=hi),
             "reported enclosure incompatible with verified radius/envelope")
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
