"""Validate pinned source digests and enforce offline provenance flags on derived results."""
from fractions import Fraction
import re

from qualification.h1_n4.static_physical import pi_rational_enclosure
from qualification.h1_n13.conduction import Box

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_HASH_KEYS = ("modelSha256", "studySha256", "factsSha256")
OFFLINE_FLAG_KEYS = (
    "nativeExecuted",
    "nativeQualified",
    "independentlyCertifiedReference",
    "runnerConsumable",
)


def offline_provenance(law):
    """Validate source digest shape and offline flags on a law mapping, stamping derived flags False.

    Refuses missing/malformed 64-lowercase-hex SHA-256 strings and any non-False
    (including forged True, wrong-type, or None) provenance flags on the incoming law
    mapping. Always emits explicit False values for all four offline flags on the
    derived result. Note: checking 64-hex syntax validates digest shape only. The
    terminal_response preparation path checks source-byte SHA-256 matches and
    study/facts/model consistency against supplied pins; digest shape or hash
    agreement alone is not source authentication, which requires independently
    trusted pins or custody.
    """
    if not isinstance(law, dict):
        raise ValueError("pinned terminal law mapping required")
    hashes = {}
    for key in SOURCE_HASH_KEYS:
        value = law.get(key)
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise ValueError(f"valid 64-hex {key} required in pinned law")
        hashes[key] = value
    for key in OFFLINE_FLAG_KEYS:
        if key in law and law[key] is not False:
            raise ValueError(f"offline derived solver refuses non-False {key} provenance")
    return {
        **hashes,
        "nativeExecuted": False,
        "nativeQualified": False,
        "independentlyCertifiedReference": False,
        "runnerConsumable": False,
    }


def _rod_conductance_box(rod, pi):
    k = Fraction(rod["k"])
    length = Fraction(rod["L"])
    if rod["kind"] == "RodArea":
        g = k * Fraction(rod["A"]) / length
        return Box.bounds(g, g)
    if rod["kind"] == "RodCircular":
        d = Fraction(rod["d"])
        return Box.bounds(k * pi[0] * d * d / (4 * length), k * pi[1] * d * d / (4 * length))
    raise ValueError("unsupported rod kind in prepared facts")


def _verify_network_matches_facts(net, facts):
    nodes = facts.get("nodes")
    boundaries = facts.get("boundaries", {})
    bodies = facts.get("bodies", {})
    rods = facts.get("rods", {})
    if not isinstance(nodes, list) or len(net.nodes) != len(nodes) or set(net.nodes) != set(nodes):
        raise ValueError("prepared network does not match prepared facts")
    if ({net.owner[n] for n in net.fixed} != set(boundaries)
            or len(net.fixed) != len(boundaries)
            or {net.owner[n] for n in net.bodies} != set(bodies)
            or len(net.bodies) != len(bodies)):
        raise ValueError("prepared network does not match prepared facts")
    for n in net.fixed:
        b = boundaries[net.owner[n]]
        if b.get("node") != n or net.initial[n] != Fraction(b["T"]):
            raise ValueError("prepared network does not match prepared facts")
    for n in net.bodies:
        body = bodies[net.owner[n]]
        cap = Box.exact(Fraction(body["m"]) * Fraction(body["c"]))
        if (body.get("node") != n
                or net.initial[n] != Fraction(body["T_initial"])
                or net.capacity[n].span() != cap.span()):
            raise ValueError("prepared network does not match prepared facts")

    if len(net.edges) != len(rods):
        raise ValueError("prepared network does not match prepared facts")
    pi = pi_rational_enclosure()
    seen_rods = set()
    for name, a, b, g in net.edges:
        if name not in rods or name in seen_rods:
            raise ValueError("prepared network does not match prepared facts")
        seen_rods.add(name)
        rod = rods[name]
        if (a, b) != (rod["a"], rod["b"]) or g.span() != _rod_conductance_box(rod, pi).span():
            raise ValueError("prepared network does not match prepared facts")

    expected_junctions = set(nodes) - set(net.fixed) - set(net.bodies)
    if (len(net.junctions) != len(expected_junctions)
            or set(net.junctions) != expected_junctions):
        raise ValueError("prepared network junctions do not match prepared facts")

    owners = net.bodies + net.fixed
    if set(net.weights) != set(net.nodes) or any(len(net.weights[n]) != len(owners) for n in net.nodes):
        raise ValueError("prepared network weights do not match prepared facts")
    for j in range(len(owners)):
        for i, owner_node in enumerate(owners):
            expected_w = Fraction(int(i == j))
            if net.weights[owner_node][j].span() != (expected_w, expected_w):
                raise ValueError("prepared network weights do not match prepared facts")
        unit = [Box.exact(int(i == j)) for i in range(len(owners))]
        _, incoming = net.flows(net.values(unit))
        if not all(incoming[jn].contains_zero() for jn in expected_junctions):
            raise ValueError("prepared network weights violate junction balance")


def verified_prepared_provenance(candidate, facts, net=None):
    """Validate offline provenance and cross-check prepared candidate/facts/network identity."""
    provenance = offline_provenance(candidate)
    if not isinstance(facts, dict):
        raise ValueError("prepared facts mapping required")
    if (facts.get("modelSha256") != provenance["modelSha256"]
            or facts.get("studySha256") != provenance["studySha256"]
            or facts.get("mode") != candidate.get("mode")):
        raise ValueError("prepared facts and candidate identities do not match")
    if net is not None:
        _verify_network_matches_facts(net, facts)
    return provenance
