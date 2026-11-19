"""Reusable graph-independent H1 static source-physical candidate, OFFLINE ONLY.

Exact source decimal rational inputs, exact integer RN-even binary64 and a
rational alternating-series Pi enclosure. NEVER imports H1 solvers, Modelica,
native runners, legacy float reference data or measured outputs.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from fractions import Fraction as F
from hashlib import sha256
import json
import math
import re

SCHEMA = "sim_heat.h1_n4.static_physical_candidate/1"
SOURCE_SCHEMA = "sim_heat.reference/1"
MAX_SOURCE_BYTES = 262144
PI_TERMS = 40
CIRCUIT_KINDS = ("RodArea", "RodCircular")
RE_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
RE_HASH = re.compile(r"[0-9a-f]{64}\Z")

# Mirror only production H1's Modelica INSTANCE identifier restriction.
# Metadata study IDs and synthetic graph node labels are not Modelica names.
# Parity against h1.model.RESERVED is enforced in the offline tests.
COMPONENT_RESERVED = set(
    "algorithm and annotation block break class connect connector constant "
    "constrainedby der discrete each else elseif elsewhen encapsulated end "
    "enumeration equation expandable extends external false final flow for "
    "function if import impure in initial inner input loop model not operator "
    "or outer output package parameter partial protected public pure record "
    "redeclare replaceable return stream then true type when while within "
    "time Real Integer Boolean String Modelica SimHeat".split()
)


class PhysicalRefusal(ValueError):
    """A physical input, evidence or exact-arithmetic premise is not satisfied."""

def need(ok, reason):
    if not ok:
        raise PhysicalRefusal("h1_n4: " + reason)

def _decimal_token(token):
    need(type(token) is str and len(token) <= 80, "overlong source decimal")
    try:
        d=Decimal(token)
    except (InvalidOperation, ValueError) as exc:
        raise PhysicalRefusal("h1_n4: invalid source decimal") from exc
    need(d.is_finite() and len(d.as_tuple().digits) <= 64
         and abs(d.as_tuple().exponent) <= 250,
         "source decimal precision/exponent outside bounded scope")
    return d

def _integer_token(token):
    need(len(token.lstrip("-")) <= 32, "oversized source integer")
    return int(token)

def _pairs_unique(pairs):
    result={}
    for k,v in pairs:
        need(k not in result, "duplicate source JSON key")
        result[k]=v
    return result

def _invalid_constant(token):
    raise PhysicalRefusal("h1_n4: nonfinite source JSON: " + token)

def _fraction_positive(number):
    need(type(number) in (int, Decimal), "physical field must be an exact decimal or integer")
    value=F(number)
    need(value > 0 and value.numerator.bit_length() <= 2048
         and value.denominator.bit_length() <= 2048, "invalid positive bounded physical field")
    return value

def _ident(name):
    # This type check applies to study metadata IDs and synthetic node labels.
    return type(name) is str and RE_IDENT.fullmatch(name) is not None

def _component_ident(name):
    # Components become Modelica instance names; reserved keywords cannot pass.
    return _ident(name) and name not in COMPONENT_RESERVED

def parse_facts(raw, *, expected_sha256):
    """Hash the SAME input bytes that are parsed; caller's hash is NOT an approval."""
    need(type(raw) is bytes and 0 < len(raw) <= MAX_SOURCE_BYTES, "bounded raw fact bytes required")
    need(type(expected_sha256) is str and RE_HASH.fullmatch(expected_sha256) is not None,
         "source SHA-256 pin required")
    need(sha256(raw).hexdigest() == expected_sha256, "source bytes differ from supplied hash")
    try:
        data=json.loads(raw.decode("utf-8"), parse_int=_integer_token,
                        parse_float=_decimal_token, parse_constant=_invalid_constant,
                        object_pairs_hook=_pairs_unique)
    except PhysicalRefusal:
        raise
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise PhysicalRefusal("h1_n4: malformed source JSON") from exc
    need(type(data) is dict and set(data)=={
         "schema","id","mode","modelSha256","studySha256","analysis",
         "provenance","nodes","bodies","boundaries","rods"}, "unexpected source fields")
    need(data["schema"]==SOURCE_SCHEMA and data["mode"] in ("transient","steady")
         and _ident(data["id"]), "source schema/mode/id")
    need(type(data["provenance"]) is str and 0 < len(data["provenance"]) <= 8192,
         "nonempty bounded provenance description")
    for digest in ("modelSha256","studySha256"):
        need(type(data[digest]) is str and RE_HASH.fullmatch(data[digest]) is not None,
             "original model/study digest missing")
    nodes=data["nodes"]
    need(type(nodes) is list and 0 < len(nodes) <= 64
         and all(_ident(x) for x in nodes) and len(set(nodes))==len(nodes),
         "invalid distinct source nodes")
    all_names=set()
    used=set()
    owned=set()
    incident=set()
    # Port incidence counts every physical rod end (parallel rods count twice).
    # Graph neighbours alone cannot detect an ownerless open degree-one port.
    port_incidence={node:0 for node in nodes}
    for group,maximum in (("bodies",8),("boundaries",8),("rods",32)):
        records=data[group]
        need(type(records) is dict and len(records) <= maximum,
             "unsupported H1 component inventory")
        for name,c in records.items():
            need(_component_ident(name) and name not in all_names and type(c) is dict,
                 "invalid, reserved or duplicate component identity")
            all_names.add(name)
            if group=="bodies":
                need(set(c)=={"node","m","c","T_initial"}, "body fields drift")
                for k in ("m","c","T_initial"):
                    _fraction_positive(c[k])
                need(_fraction_positive(c["m"])*_fraction_positive(c["c"]) > 0,
                     "invalid body capacity")
            elif group=="boundaries":
                need(set(c)=={"node","T"}, "boundary fields drift")
                _fraction_positive(c["T"])
            else:
                need(type(c.get("kind")) is str and c["kind"] in CIRCUIT_KINDS,
                     "unsupported rod kind")
                fields={"kind","a","b","k","L",
                        "A" if c["kind"]=="RodArea" else "d"}
                need(set(c)==fields, "rod geometry must be explicit")
                for k in ("k","L","A" if c["kind"]=="RodArea" else "d"):
                    _fraction_positive(c[k])
                need(type(c["a"]) is str and type(c["b"]) is str
                     and c["a"] in nodes and c["b"] in nodes and c["a"]!=c["b"],
                     "invalid rod endpoints")
                incident.update((c["a"],c["b"]))
                used.update((c["a"],c["b"]))
                port_incidence[c["a"]]+=1
                port_incidence[c["b"]]+=1
            if group!="rods":
                node=c["node"]
                need(type(node) is str and node in nodes and node not in owned,
                     "invalid or multiply-owned node")
                owned.add(node)
                used.add(node)
    need(used==set(nodes), "unused source node")
    need(all(port_incidence[node]>=2 for node in nodes if node not in owned),
         "open ownerless rod end: every ownerless junction requires two rod ports")
    need(all(c["node"] in incident for c in data["boundaries"].values()),
         "disconnected maintained boundary")
    need(bool(data["bodies"]) if data["mode"]=="transient"
         else bool(data["rods"]) and bool(data["boundaries"]) and not data["bodies"],
         "invalid steady/transient component domain")
    analysis=data["analysis"]
    need(type(analysis) is dict, "analysis must be an explicit H1 object")
    if data["mode"]=="steady":
        need(not analysis,"steady reference must not claim physical time")
    else:
        need(set(analysis)=={"startTime","stopTime","intervals","solver","tolerance"},
             "transient analysis fields")
        start=analysis["startTime"]
        need(type(start) in (int,Decimal) and F(start)==0,
             "original source analysis must start at zero")
        stop=_fraction_positive(analysis["stopTime"])
        need(F(1,10**6)<=stop<=F(10**7),
             "physical time horizon outside H1 domain")
        count=analysis["intervals"]
        need(type(count) is int and 1000<=count<=20000 and count%2==0,
             "transient sample intervals outside H1 domain")
        tolerance=_fraction_positive(analysis["tolerance"])
        need(type(analysis["solver"]) is str and analysis["solver"]=="dassl"
             and tolerance in (F(1,10**8),F(1,10**10)),
             "H1 study solver/tolerance not supported")
    adjacency={n:set() for n in nodes}
    for rod in data["rods"].values():
        adjacency[rod["a"]].add(rod["b"])
        adjacency[rod["b"]].add(rod["a"])
    remaining=set(nodes)
    while remaining:
        start=remaining.pop()
        component={start}
        frontier=[start]
        while frontier:
            for other in adjacency[frontier.pop()]:
                if other not in component:
                    component.add(other)
                    remaining.discard(other)
                    frontier.append(other)
        need(bool(component & owned),
             "unanchored H1 thermal component")
    return data

def power_two(e):
    need(type(e) is int and -2048 <= e <= 2048, "binary exponent outside checker scope")
    return F(2**e) if e>=0 else F(1,2**(-e))

def floor_log2(x):
    need(type(x) is F and x>0, "positive exact rational required")
    e=x.numerator.bit_length()-x.denominator.bit_length()
    return e-1 if x < power_two(e) else e

def rn_even_binary64(x):
    """Exact rational -> nearest IEEE binary64, ties to even (no float arithmetic)."""
    need(type(x) is F and x>=0, "nonnegative exact rational required")
    if x==0:
        return F(0)
    e=floor_log2(x)
    need(e<=1023, "binary64 overflow")
    quantum=power_two(max(e-52,-1074))
    scaled=x/quantum
    n,remainder=divmod(scaled.numerator,scaled.denominator)
    if 2*remainder>scaled.denominator or (2*remainder==scaled.denominator and n%2):
        n+=1
    result=n*quantum
    need(result<=(2-power_two(-52))*power_two(1023),"binary64 overflow")
    return result

def ulp_positive(x):
    need(type(x) is F and x>=0 and rn_even_binary64(x)==x,
         "exact binary64 centre required")
    return power_two(max(floor_log2(x)-52,-1074)) if x else power_two(-1074)

def pi_rational_enclosure(terms=PI_TERMS):
    need(type(terms) is int and 2 <= terms <= 64,"bounded Machin proof required")
    def atan_bounds(denom):
        x=F(1,denom)
        partial=sum(((-1)**k*x**(2*k+1)/F(2*k+1) for k in range(terms)),F(0))
        next_term=(-1)**terms*x**(2*terms+1)/F(2*terms+1)
        return min(partial,partial+next_term),max(partial,partial+next_term)
    a,b=atan_bounds(5),atan_bounds(239)
    return 16*a[0]-4*b[1],16*a[1]-4*b[0]

def physical_budget(centre,bounds):
    """Exact *physical* enclosure, not a binary64 operation-order target."""
    need(type(centre) is F and type(bounds) is tuple and len(bounds)==2,
         "invalid physical certificate input")
    lo,hi=bounds
    need(type(lo) is F and type(hi) is F and 0 < lo <= hi,
         "invalid positive physical interval")
    epsilon=64*ulp_positive(centre)
    error=max(abs(centre-lo),abs(centre-hi))
    return error<=epsilon/100,error,epsilon

def _constant(name,unit,family,bounds):
    lo,hi=bounds
    left,right=rn_even_binary64(lo),rn_even_binary64(hi)
    need(left==right and left>0, "source physical rounding is unresolved: " + name)
    passed,error,epsilon=physical_budget(left,bounds)
    need(passed,"physical reference error exceeds 1/100 budget: " + name)
    return {"unit":unit,"law":family,"binary64Hex":float(left).hex(),
            "physicalLowerRational":str(lo),"physicalUpperRational":str(hi),
            "errorUpperRational":str(error),"nativeAllowanceRational":str(epsilon),
            "referenceMaximumRational":str(epsilon/100),
            "errorToReferenceBudgetUpperRational":str(error/(epsilon/100)),
            "physical100x":"PASS_CANDIDATE_NOT_NATIVE_QUALIFIED"}

def create_static_candidate(raw,*,expected_sha256):
    """Graph-independent static calculations; output NEVER enables any runner."""
    facts=parse_facts(raw,expected_sha256=expected_sha256)
    pi_lo,pi_hi=pi_rational_enclosure()
    result={}
    for name,b in sorted(facts["bodies"].items()):
        value=_fraction_positive(b["m"])*_fraction_positive(b["c"])
        result[name+".C"]=_constant(name+".C","J/K","body_capacity_m_times_c",(value,value))
    for name,rod in sorted(facts["rods"].items()):
        k,L=_fraction_positive(rod["k"]),_fraction_positive(rod["L"])
        if rod["kind"]=="RodCircular":
            d=_fraction_positive(rod["d"])
            bounds=(pi_lo*d*d/4,pi_hi*d*d/4)
            result[name+".A"]=_constant(name+".A","m2","circular_area_pi_d_squared_over_four",bounds)
        else:
            area=_fraction_positive(rod["A"])
            bounds=(area,area)
        G=(k*bounds[0]/L,k*bounds[1]/L)
        result[name+".G"]=_constant(name+".G","W/K",
              "circular_kA_over_L" if rod["kind"]=="RodCircular" else "area_kA_over_L",G)
    need(len(result)==len(facts["bodies"])+len(facts["rods"])+sum(
         c["kind"]=="RodCircular" for c in facts["rods"].values()),
         "incomplete static export inventory")
    return {"schema":SCHEMA,"stage":"offline_exact_static_physical_candidate",
            "sourceFactsSha256":expected_sha256,
            "originalModelSha256":facts["modelSha256"],"originalStudySha256":facts["studySha256"],
            "sourceStudyId":facts["id"],
            "method":"exact source decimals, rational Pi enclosure, exact RN-even binary64",
            "physical100xTarget":"EXACT_SOURCE_MATHEMATICS_NOT_OLD_FLOAT_OPERATIONS",
            "piSeriesTerms":PI_TERMS,"exports":result,"staticExports":len(result),
            "candidateValuesOnly":True,"referenceBundleWritten":False,
            "historicalReferenceRegenerated":False,"independentlyCertifiedReference":False,
            "nativeExecuted":False,"nativeQualified":False,"runtimeReady":False,
            "referenceAccuracyCertified":False,"generalH1DynamicsQualified":False,
            "externalOwnerApprovalVerified":False,
            "limitation":"static-source physical candidate only; no dynamics, native provenance, external seal or runner adoption"}
