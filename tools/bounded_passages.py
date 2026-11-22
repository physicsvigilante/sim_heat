"""Shared strict-side passage checks for bounded H1 temperature and heat-rate histories."""
from fractions import Fraction
from pathlib import Path

from qualification.h1_n4.static_physical import MAX_SOURCE_BYTES, parse_facts
from qualification.h1_n13.conduction import prepare
from tools.offline_provenance import verified_prepared_provenance


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


def read_pinned_facts(facts_path, facts_sha256):
    path = Path(facts_path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("invalid source facts path")
    with path.open("rb") as stream:
        return parse_facts(stream.read(MAX_SOURCE_BYTES + 1), expected_sha256=facts_sha256)


def observe(study, root, facts_path, facts_sha256, *, group, name, field, threshold, directions):
    facts = read_pinned_facts(facts_path, facts_sha256)
    if facts["mode"] != "transient" or name not in facts[group]:
        raise ValueError(f"expected a transient study and an existing member of {group}")
    candidate = prepare(study, root, facts_path, facts_sha256)
    key = name + "." + field
    return series_passages(candidate, facts, "exports", key, threshold, directions)


def series_passages(candidate, facts, family, key, threshold, directions):
    provenance = verified_prepared_provenance(candidate, facts)
    series = candidate[family][key]
    scale = {"K": 10**8, "W": 10**8, "J": 10**5}[series["unit"]]
    radius = Fraction(candidate["maxErrorToBudgetBySeries"][family][key]) / scale
    analysis = facts["analysis"]
    step = Fraction(analysis["stopTime"]) / analysis["intervals"]
    passages, overlaps = brackets(series["values"], radius, threshold, step, directions)
    return passages, overlaps, radius, provenance
