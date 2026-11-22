"""Validate pinned source digests and enforce offline provenance flags on derived results."""
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
    """Validate source digests and offline flags on a law mapping, stamping derived flags False.

    Refuses missing/malformed SHA-256 digests and any non-False (including forged True,
    wrong-type, or None) provenance flags on the incoming law mapping. Always emits
    explicit False values for all four offline flags on the derived result.
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
