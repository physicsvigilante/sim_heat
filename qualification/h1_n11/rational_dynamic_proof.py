"""N11: independently built outward-rational FULL GRID physical enclosures.

Checking-only mathematical *candidate*, not a reviewed independent reference
certificate, a native-runner bundle, owner authentication or OpenModelica output.
N1 supplies ONLY a SHA-pinned historical float64 candidate to be tested, not
the physical graph, matrix, interval arithmetic, integrals or predictions.

Different verification construction from N1: physical source facts are parsed
through the independently reviewed N4 grammar; node elimination uses interval
Gaussian pivots, not N1's hard-coded 2x2 determinant; the exponential uses
outward fixed-point MATRIX HORNER plus a separate norm/tail inequality. Every
saved value is enclosed from mathematical source inputs and compared against
the PREDECLARED original 1/100 checker budget, not a value-fitted tolerance.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction as F
from hashlib import sha256
from math import factorial, isfinite, ulp
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import json

from qualification.h1_n1 import certified_reference as n1
from qualification.h1_n4.static_physical import parse_facts, create_static_candidate
from qualification.h1_n9.static_trace_crosscheck import (
    ORIGINAL_GRID_HASHES, EXPECTED_LEGACY_FAILURES, verify_historical_grid
)

ROOT = Path(__file__).resolve().parents[2]
FACTS = ROOT / "qualification/h1_n1/reference-facts.json"
MODEL = ROOT / "qualification/h1_n1/inputs/T/model.mo"
STUDY = ROOT / "qualification/h1_n1/inputs/T/study.json"
FACTS_SHA = "39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf"
MODEL_SHA = "2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae"
STUDY_SHA = "12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a"
SCHEMA = "sim_heat.h1_n11.independent_rational_dynamic_enclosure_candidate/1"
SCALE = 10**88
TAYLOR = 24
PI_TERMS = 43
NATIVE_HOLD = tuple(EXPECTED_LEGACY_FAILURES)


class ProofRefusal(ValueError):
    """An exact arithmetic premise, source identity or physical bound failed."""


def need(ok, detail):
    if not ok:
        raise ProofRefusal("h1_n11: " + detail)


def ceil_fraction(q: F) -> int:
    return -((-q.numerator)//q.denominator)


@dataclass(frozen=True)
class Box:
    low: int
    high: int

    def __post_init__(self):
        need(type(self.low) is int and type(self.high) is int and self.low <= self.high,
             "invalid outward rational interval")

    @staticmethod
    def exact(value):
        q = F(value)
        return Box((q*SCALE).__floor__(), ceil_fraction(q*SCALE))

    @staticmethod
    def bounds(lo: F, hi: F):
        need(type(lo) is F and type(hi) is F and lo <= hi,
             "invalid exact source bound")
        return Box((lo*SCALE).__floor__(), ceil_fraction(hi*SCALE))

    def __add__(self, other):
        other = ibox(other)
        return Box(self.low+other.low, self.high+other.high)

    __radd__ = __add__

    def __neg__(self):
        return Box(-self.high, -self.low)

    def __sub__(self, other):
        return self + (-ibox(other))

    def __rsub__(self, other):
        return ibox(other) - self

    def __mul__(self, other):
        other = ibox(other)
        products = (self.low*other.low, self.low*other.high,
                    self.high*other.low, self.high*other.high)
        return Box(min(products)//SCALE,
                   -((-max(products))//SCALE))

    __rmul__ = __mul__

    def inverse(self):
        need(self.low > 0 or self.high < 0, "inverse interval includes zero")
        if self.high < 0:
            return -(-self).inverse()
        return Box((SCALE*SCALE)//self.high,
                   -((-SCALE*SCALE)//self.low))

    def __truediv__(self, other):
        return self*ibox(other).inverse()

    def absolute_upper(self):
        return F(max(abs(self.low), abs(self.high)), SCALE)

    def span(self):
        return F(self.low, SCALE), F(self.high, SCALE)

    def contains_zero(self):
        return self.low <= 0 <= self.high

    def contains(self, value):
        q = F(value)*SCALE
        return self.low <= q <= self.high


def ibox(value):
    return value if type(value) is Box else Box.exact(value)


def dot(row, vector):
    need(len(row) == len(vector), "vector inner dimensions do not match")
    return sum((a*b for a, b in zip(row, vector)), Box.exact(0))


def product(left, right):
    need(type(left) in (list, tuple) and type(right) in (list, tuple)
         and len(left) > 0 and len(right) > 0, "missing matrix")
    width = len(right)
    inner = len(left[0])
    need(all(len(row) == inner for row in left)
         and all(len(row) == len(right[0]) for row in right)
         and width == inner, "bad matrix dimensions")
    return [[sum((left[i][k]*right[k][j] for k in range(inner)), Box.exact(0))
             for j in range(len(right[0]))] for i in range(len(left))]


def identity(size):
    return [[Box.exact(int(i==j)) for j in range(size)] for i in range(size)]


def pi_bounds():
    """Independent alternating Machin rational enclosure; no float pi."""
    need(type(PI_TERMS) is int and PI_TERMS >= 2, "invalid Pi proof")
    def atan_remainder(q):
        x = F(1, q)
        partial = sum(((-1)**k*x**(2*k+1)/F(2*k+1)
                       for k in range(PI_TERMS)), F(0))
        omitted = (-1)**PI_TERMS*x**(2*PI_TERMS+1)/F(2*PI_TERMS+1)
        return min(partial, partial+omitted), max(partial, partial+omitted)
    a,b = atan_remainder(5), atan_remainder(239)
    lo,hi = 16*a[0]-4*b[1], 16*a[1]-4*b[0]
    need(F(3) < lo <= hi < F(4), "invalid independent Pi enclosure")
    return Box.bounds(lo,hi)


def source_number(value):
    need(type(value) in (int, Decimal), "original physical decimal required")
    return F(value)


def first_source():
    for file, digest in ((FACTS, FACTS_SHA), (MODEL, MODEL_SHA), (STUDY, STUDY_SHA)):
        need(sha256(file.read_bytes()).hexdigest() == digest,
             "original source SHA-256 changed: " + file.name)
    raw = FACTS.read_bytes()
    facts = parse_facts(raw, expected_sha256=FACTS_SHA)
    need(facts["modelSha256"]==MODEL_SHA and facts["studySha256"]==STUDY_SHA
         and facts["mode"]=="transient" and facts["id"]=="H1T1TFirstAttemptV1"
         and source_number(facts["analysis"]["stopTime"])==F(2400),
         "wrong first-author task or analysis")
    original = json.loads(STUDY.read_bytes())
    req = original["requests"]
    need(type(req) is list and len(req)==8
         and all(type(v) is dict and type(v.get("id")) is str for v in req)
         and len({v["id"] for v in req})==8, "original authored public requests invalid")
    return facts, req


def build_physics(facts):
    """Independent graph assembly, outward junction elimination via pivots.

    State is (u_body..., integral u_body d_tau..., 1), where
    u=(T-289K)/(78K), tau=t/(2400s). This change of units and the
    affine row are algebraic identities, not simulation approximations.
    """
    nodes = list(facts["nodes"])
    bodies, boundaries, rods = facts["bodies"], facts["boundaries"], facts["rods"]
    bnames, fnames = sorted(bodies), sorted(boundaries)
    dynamic = [bodies[n]["node"] for n in bnames]
    fixed = [boundaries[n]["node"] for n in fnames]
    junctions = sorted(set(nodes)-set(dynamic)-set(fixed))
    need(len(nodes)==7 and len(bnames)==3 and len(fnames)==2
         and len(junctions)==2 and len(rods)==10,
         "original source physical inventory changed")
    idx={name:i for i,name in enumerate(nodes)}
    zero=Box.exact(0)
    lap=[[zero for _ in nodes] for _ in nodes]
    pi=pi_bounds()
    conductance, area={},{}
    for rid, rod in sorted(rods.items()):
        k,L=source_number(rod["k"]),source_number(rod["L"])
        need(k>0 and L>0, "nonpositive original physical conductor")
        if rod["kind"]=="RodArea":
            A=Box.exact(source_number(rod["A"]))
        elif rod["kind"]=="RodCircular":
            d=source_number(rod["d"])
            A=pi*Box.exact(d*d/F(4))
            area[rid]=A
        else:
            raise ProofRefusal("h1_n11: unsupported rod kind")
        G=Box.exact(k)*A/Box.exact(L)
        need(G.low>0, "nonpositive original G interval")
        conductance[rid]=G
        a,b=idx[rod["a"]],idx[rod["b"]]
        need(a!=b, "rod loop")
        lap[a][a]=lap[a][a]+G
        lap[b][b]=lap[b][b]+G
        lap[a][b]=lap[a][b]-G
        lap[b][a]=lap[b][a]-G

    # Each row of Laplacian is exactly zero for the true physical G. It is
    # evaluated intervalwise, and must enclose zero without forcing it to zero.
    need(all(sum(row,zero).contains_zero() for row in lap),
         "Laplacian source balance fails")

    # Solve independent ownerless junction equations with Gaussian pivots.
    # Do NOT import N1's 2x2 determinant/Schur inverse. Each known node is
    # solved as a separate right-hand-side basis to enclose all coefficients.
    a,b = (lap[idx[junctions[0]]][idx[junctions[0]]],
           lap[idx[junctions[0]]][idx[junctions[1]]])
    c,d = (lap[idx[junctions[1]]][idx[junctions[0]]],
           lap[idx[junctions[1]]][idx[junctions[1]]])
    need(a.low>0, "first Gaussian pivot not positive")
    multiplier=c/a
    second=d-multiplier*b
    need(second.low>0, "second Gaussian pivot not positive")
    jcoef = {}
    for known in dynamic+fixed:
        rhs1=-lap[idx[junctions[0]]][idx[known]]
        rhs2=-lap[idx[junctions[1]]][idx[known]]
        x2=(rhs2-multiplier*rhs1)/second
        x1=(rhs1-b*x2)/a
        jcoef[known]=(x1,x2)
    for j in range(2):
        need(sum((jcoef[n][j] for n in dynamic+fixed),zero).contains(1),
             "junction does not preserve equal-temperature mode")

    origin=F(289)
    span=F(78)
    weights={}
    for i,node in enumerate(dynamic):
        weights[node]=[Box.exact(int(i==k)) for k in range(3)]+[zero]
    for name in fnames:
        node=boundaries[name]["node"]
        u=(source_number(boundaries[name]["T"])-origin)/span
        weights[node]=[zero,zero,zero,Box.exact(u)]
    for j,node in enumerate(junctions):
        offset=sum((jcoef[boundaries[name]["node"]][j]*
                    weights[boundaries[name]["node"]][-1] for name in fnames),zero)
        weights[node]=[jcoef[n][j] for n in dynamic]+[offset]

    C={name:Box.exact(source_number(bodies[name]["m"])*
                       source_number(bodies[name]["c"])) for name in bnames}
    seven=[[zero for _ in range(7)] for _ in range(7)]
    for i,name in enumerate(bnames):
        row=lap[idx[dynamic[i]]]
        for col in range(4):
            rhs=sum((row[idx[node]]*weights[node][col] for node in nodes),zero)
            seven[i][col if col<3 else 6]=-Box.exact(2400)*rhs/C[name]
        seven[3+i][i]=Box.exact(1)
    need(all(v.low==0 and v.high==0 for v in seven[-1]),
         "last affine ODE row not exactly zero")
    initial=[Box.exact((source_number(bodies[name]["T_initial"])-origin)/span)
             for name in bnames]+[zero,zero,zero,Box.exact(1)]
    return {"matrix":seven,"start":initial,"nodes":nodes,"weights":weights,
            "dynamic":dynamic,"bodies":bodies,"bnames":bnames,
            "fnames":fnames,"boundaries":boundaries,"rods":rods,
            "capacities":C,"G":conductance,"areas":area,
            "junctions":junctions}


def verified_exponential_step(B, intervals):
    """Outward interval Horner exp(B/N), explicit global Taylor tail proof.

    With rho=||B/N||inf <=1/2, ||sum_(k>m) X^k/k!||inf
    <=exp(rho)*rho^(m+1)/(m+1)! <=2*rho^(m+1)/(m+1)!.
    No replacement of a nonzero affine last row is ever allowed.
    """
    need(type(intervals) is int and intervals in (2400,4800)
         and type(B) is list and len(B)==7
         and all(type(row) is list and len(row)==7
                 and all(type(v) is Box for v in row) for row in B),
         "unsupported complete interval dynamics")
    need(all(x.low==0 and x.high==0 for x in B[-1]),
         "nonzero affine final row")
    X=[[cell/Box.exact(intervals) for cell in row] for row in B]
    rho=max(sum((v.absolute_upper() for v in row),F(0)) for row in X)
    need(F(0)<rho<=F(1,2), "independent exponential norm precondition")
    H=identity(7)
    one=identity(7)
    for k in range(TAYLOR,0,-1):
        HX=product(X,H)
        H=[[one[i][j]+HX[i][j]/Box.exact(k) for j in range(7)] for i in range(7)]
    tail=2*rho**(TAYLOR+1)/factorial(TAYLOR+1)
    radius=ceil_fraction(tail*SCALE)
    H=[[Box(v.low-radius,v.high+radius) for v in row] for row in H]
    # The true affine constant row is mathematically exactly [0,...,0,1]
    # because B[-1,:] was explicitly validated exactly zero.
    H[-1]=[Box.exact(int(j==6)) for j in range(7)]
    return H, {"intervalScale":"1e-88","hornerDegree":TAYLOR,
               "piAlternatingSeriesTerms":PI_TERMS,"rhoMax":str(rho),
               "globalMatrixEntryRemainderUpper":str(tail),
               "lastAffineRowPremiseChecked":True}


def apply(H, state):
    need(len(H)==len(state), "matrix-vector dimensions drifted")
    return [dot(row,state) for row in H]


def sample_physics(p, state, t: F, requests):
    """Independently enclose 77 + 8 + 5 source-physical quantities."""
    zero=Box.exact(0)
    u, integral = {},{}
    for name in p["nodes"]:
        weights=p["weights"][name]
        u[name]=dot(weights[:3],state[:3])+weights[3]
        integral[name]=dot(weights[:3],state[3:6])+weights[3]*Box.exact(t/F(2400))
    temperature={name:Box.exact(289)+Box.exact(78)*u[name] for name in p["nodes"]}
    temperature_int={name:Box.exact(289*t)+Box.exact(78*2400)*integral[name]
                     for name in p["nodes"]}

    flux={n:zero for n in p["nodes"]}
    intflux={n:zero for n in p["nodes"]}
    exports={}
    for rid,r in sorted(p["rods"].items()):
        a,b=r["a"],r["b"]
        G=p["G"][rid]
        q=G*(temperature[a]-temperature[b])
        qi=G*(temperature_int[a]-temperature_int[b])
        flux[a]=flux[a]-q
        flux[b]=flux[b]+q
        intflux[a]=intflux[a]-qi
        intflux[b]=intflux[b]+qi
        for field,value in (("T_a",temperature[a]),("T_b",temperature[b]),
                            ("Q_flow",q),("port_a.Q_flow",q),
                            ("port_b.Q_flow",-q),("G",G)):
            exports[rid+"."+field]=value
        if rid in p["areas"]:
            exports[rid+".A"]=p["areas"][rid]

    integrated={}
    for name in p["bnames"]:
        node=p["bodies"][name]["node"]
        C=p["capacities"][name]
        exports[name+".T"]=temperature[node]
        exports[name+".Q_in"]=flux[node]
        exports[name+".dU"]=C*(temperature[node]-
                              Box.exact(source_number(p["bodies"][name]["T_initial"])))
        exports[name+".C"]=C
        integrated[name+".Q_in"]=intflux[node]
    for name in p["fnames"]:
        node=p["boundaries"][name]["node"]
        exports[name+".T"]=temperature[node]
        exports[name+".Q_to_network"]=-flux[node]
        integrated[name+".Q_to_network"]=-intflux[node]

    def port_temp(v):
        need(type(v) is str and v.count(".")==1,
             "invalid first-author temperature target")
        name,port=v.split(".")
        if name in p["bodies"]:
            need(port=="port","bad body temperature port")
            return temperature[p["bodies"][name]["node"]]
        if name in p["boundaries"]:
            need(port=="port","bad fixed temperature port")
            return temperature[p["boundaries"][name]["node"]]
        if name in p["rods"]:
            need(port in ("port_a","port_b"), "bad conductor temperature port")
            return temperature[p["rods"][name]["a" if port=="port_a" else "b"]]
        raise ProofRefusal("h1_n11: unknown authored port")

    observed={}
    for r in requests:
        ident,op=r["id"],r["op"]
        need(ident not in observed,"duplicate authored observation")
        if op=="temperature":
            observed[ident]=port_temp(r["target"])
        elif op=="temperatureDifference":
            observed[ident]=port_temp(r["a"])-port_temp(r["b"])
        elif op=="heatFlow":
            need(r["target"] in p["rods"], "unknown heatflow target")
            observed[ident]=exports[r["target"]+".Q_flow"]
        elif op=="energyChange":
            need(r["target"] in p["bodies"], "unknown energy target")
            observed[ident]=exports[r["target"]+".dU"]
        else:
            raise ProofRefusal("h1_n11: unknown observation operation")

    # Algebraic non-storage nodes: exact physical Kirchhoff law must lie in
    # the computed enclosure. No replacement of nonzero flow by zero.
    need(all(flux[node].contains_zero() for node in p["junctions"]),
         "physical ownerless junction balance enclosure failed")
    for name in p["bnames"]:
        stored=exports[name+".dU"]
        supplied=integrated[name+".Q_in"]
        need((stored-supplied).contains_zero(),
             "integral body energy identity not enclosed")
    network=sum((exports[name+".dU"] for name in p["bnames"]),zero)
    supply=sum((integrated[name+".Q_to_network"] for name in p["fnames"]),zero)
    need((network-supply).contains_zero(),
         "global body/boundary integral balance not enclosed")
    return exports,observed,integrated


def field_unit(name):
    end=name.split(".")[-1]
    if end in ("T","T_a","T_b"):return "K"
    if end in ("Q_flow","Q_in","Q_to_network"):return "W"
    if end=="dU":return "J"
    return {"G":"W/K","A":"m2","C":"J/K"}.get(end)


def compare_float(f, enclosure: Box, unit, field, i):
    need(type(f) in (float,int) and isfinite(f) and type(enclosure) is Box,
         "nonfinite/invalid original reference centre")
    need(unit in ("K","W","J","W/K","J/K","m2"),"unrecognized SI dimension")
    original=F.from_float(float(f))
    lo,hi=enclosure.span()
    error=max(abs(original-lo),abs(original-hi))
    if unit=="K": allowed=F(11,10**8)
    elif unit=="W": allowed=F(1,10**8)
    elif unit=="J": allowed=F(1,10**5)
    else:
        need(f>0,"nonpositive physical constant")
        allowed=F(64,100)*F.from_float(ulp(float(f)))
    need(error <= allowed,
         "candidate outside independent outward physical 100x budget: "
         +field+" @ "+str(i))
    return error/allowed, hi-lo


def checked_grid(original, count, physical, source_requests):
    need(type(original) is dict and type(original.get("report")) is dict
         and original["report"].get("gridIntervals")==count,
         "unexpected saved candidate grid")
    columns, req, integrals=original["columns"],original["requests"],original["integrals"]
    units=original["units"]
    request_units={r["id"]:("W" if r["op"]=="heatFlow" else
                           "J" if r["op"]=="energyChange" else "K")
                   for r in source_requests}
    step,proof=verified_exponential_step(physical["matrix"],count)
    state=list(physical["start"])
    maxratios={family:F(0) for family in ("exports","requests","integrals")}
    maxwidths={family:F(0) for family in ("exports","requests","integrals")}
    compared=0
    for i in range(count+1):
        t=F(2400*i,count)
        need(type(original["grid"][i]) in (float,int)
             and original["grid"][i]==float(t),
             "saved candidate instant mismatches source analysis")
        values=sample_physics(physical,state,t,source_requests)
        for label, ours, theirs in zip(
            ("exports","requests","integrals"),values,
            (columns,req,integrals)):
            need(set(ours)==set(theirs), "missing or added "+label+" field")
            for name, box in ours.items():
                unit=(field_unit(name) if label=="exports" else
                      request_units[name] if label=="requests" else "J")
                need(unit is not None,"unknown internal quantity")
                if label=="exports":
                    need(units.get(name)==unit,"source SI unit discrepancy: "+name)
                r,w=compare_float(theirs[name][i],box,unit,name,i)
                maxratios[label]=max(maxratios[label],r)
                maxwidths[label]=max(maxwidths[label],w)
                compared+=1
        if i<count:
            state=apply(step,state)
    need(compared == 90*(count+1), "original complete 77/8/5 inventory missing")
    return {"intervals":count,"samples":count+1,
            "originalN1TraceSha256":ORIGINAL_GRID_HASHES[count],
            "enclosedInternalExports":77,"enclosedOriginalRequests":8,
            "enclosedIntegratedFlows":5,"individualComparedSamples":compared,
            "maximumErrorTo100xAllowance":{k:float(v) for k,v in maxratios.items()},
            "maximumExactEnclosureWidth":{k:str(v) for k,v in maxwidths.items()},
            "outwardRationalEnclosureSelfCheckPassed":True,
            "independentExternalMathematicalCertification":False,
            "verifiedStepProof":proof}


def audit(output=None):
    """Full trusted source-pinned N11 path; never accept caller-supplied traces."""
    if output is not None:
        output=Path(output).resolve()
        need(not output.is_relative_to(ROOT) and not output.exists(),
             "output must be a NEW location outside source repository")
    facts,requests=first_source()
    from qualification.h1_n4.static_physical import create_static_candidate
    raw=FACTS.read_bytes()
    static=create_static_candidate(raw,expected_sha256=FACTS_SHA)
    physics=build_physics(facts)
    grids=[]
    with TemporaryDirectory(prefix="h1-n11-rational-proof-") as temp:
        for count in ORIGINAL_GRID_HASHES:
            folder=Path(temp)/("grid-"+str(count))
            n1_report=n1.certify(n1.read_facts(),count,output=folder)
            blob=(folder/("N1_T1T_reference_grid"+str(count)+".json")).read_bytes()
            need(sha256(blob).hexdigest()==n1_report["fullTraceSha256"],
                 "regenerated N1 report and bytes differ")
            verify_historical_grid(blob,count,static)
            data=json.loads(blob.decode("utf8"))
            grids.append(checked_grid(data,count,physics,requests))
    receipt={"schema":SCHEMA,"stage":"offline_independent_outward_rational_candidate",
             "sourceFactsSha256":FACTS_SHA,"originalModelSha256":MODEL_SHA,
             "originalStudySha256":STUDY_SHA,"grids":grids,
             "individualPhysicallyEnclosedSamples":sum(
                 x["individualComparedSamples"] for x in grids),
             "sourceMathematicalEnclosureSelfChecked":True,
             "rigorousMethodWithinStatedRationalArithmetic":True,
             "independentExternalMathematicalCertification":False,
             "fullDynamicPhysical100xIndependentlyCertified":False,
             "referenceAccuracyCertified":False,
             "independentlyCertifiedReference":False,
             "runtimeReady":False,"referenceBundleWritten":False,
             "externalOwnerApprovalVerified":False,
             "nativeExecuted":False,"nativeQualified":False,
             "historicalReferenceRegenerated":False,
             "legacySevenStaticCheckingCentresStillFail":list(NATIVE_HOLD),
             "limitation":"candidate mathematical self-enclosures of preserved first-author T1-T grids; independent reviewer verification, versioned runner bundle and external owner/native authority still absent"}
    if output is not None:
        output.mkdir(parents=True,exist_ok=False)
        (output/"n11-rational-proof-candidate.json").write_text(
            json.dumps(receipt,sort_keys=True,indent=2,allow_nan=False)+"\n",
            encoding="utf8")
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(audit(output=args.out),sort_keys=True,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
