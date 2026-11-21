"""Shared strict-side passage checks for bounded H1 temperature and heat-rate histories."""
from fractions import Fraction
from pathlib import Path

from qualification.h1_n4.static_physical import MAX_SOURCE_BYTES, parse_facts
from qualification.h1_n13.conduction import prepare


def brackets(values, radius, threshold, step, directions):
    """Opposite strict sides prove a passage even across inconclusive samples."""
    falling, rising = directions
    passages = []
    previous_side = 0
    previous_index = 0
    overlaps = 0
    for index, value in enumerate(values):
        distance = Fraction(value) - threshold
        if abs(distance) <= radius:
            overlaps += 1
            continue
        side = 1 if distance > 0 else -1
        if previous_side and side != previous_side:
            passages.append({
                "direction": rising if side > 0 else falling,
                "sampleIndices": [previous_index, index],
                "timeBoundsSeconds": [str(previous_index * step), str(index * step)],
            })
        previous_index, previous_side = index, side
    return passages, overlaps


def observe(study, root, facts_path, facts_sha256, *, group, name, field, threshold, directions):
    path = Path(facts_path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("invalid source facts path")
    with path.open("rb") as stream:
        facts = parse_facts(stream.read(MAX_SOURCE_BYTES + 1), expected_sha256=facts_sha256)
    if facts["mode"] != "transient" or name not in facts[group]:
        raise ValueError(f"expected a transient study and an existing member of {group}")
    candidate = prepare(study, root, path, facts_sha256)
    key = name + "." + field
    radius = Fraction(candidate["maxErrorToBudgetBySeries"]["exports"][key]) / 10**8
    analysis = facts["analysis"]
    step = Fraction(analysis["stopTime"]) / analysis["intervals"]
    passages, overlaps = brackets(candidate["exports"][key]["values"], radius, threshold, step, directions)
    provenance = {key: candidate[key] for key in ("modelSha256", "studySha256", "factsSha256",
                                            "nativeExecuted", "nativeQualified",
                                            "independentlyCertifiedReference", "runnerConsumable")}
    return passages, overlaps, radius, provenance
