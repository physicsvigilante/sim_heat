"""Validate pinned source digests and enforce offline provenance flags on derived results."""
from fractions import Fraction
import re

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
        if ({net.owner[n] for n in net.fixed} != set(facts.get("boundaries", {}))
                or {net.owner[n] for n in net.bodies} != set(facts.get("bodies", {}))
                or {name for name, *_ in net.edges} != set(facts.get("rods", {}))
                or any(net.initial[n] != Fraction(facts["boundaries"][net.owner[n]]["T"])
                       for n in net.fixed)):
            raise ValueError("prepared network does not match prepared facts")
    return provenance
