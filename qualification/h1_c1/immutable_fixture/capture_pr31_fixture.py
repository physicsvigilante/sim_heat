"""Create a PROPOSED immutable copy of the original PR31 checking artifact.

This never prepares a reference, repairs a past artifact, executes Modelica,
grants owner approval, or changes the original F0 numerical checker.
Input must be the exact reviewed PR31 artifact member extracted from
GitHub Actions run 43915934653, artifact 14249313720.
"""
import hashlib
import json
import lzma
from pathlib import Path
import sys

OLD_F0_SEAL = "d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b"
V2_SEAL = "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9"
V2_RAW_SHA = "0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368"
V2_RAW_LENGTH = 4409800
SPEC_SHA = "3afcfddb28ddbf9f9266548504bb43fc2f5420e90d10cb4acbf87334c6e3ab4c"
MODEL_SHA = "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
MODAL_STUDY_SHA = "b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"
REVIEW_HEAD = "d857c8e807612026ecdf624277b4ace3977fefe3"
F0_HEAD = "dd8c9432abe97563414bb3ed809e61e673473812"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def verify_original(raw):
    if len(raw) != V2_RAW_LENGTH or sha(raw) != V2_RAW_SHA:
        raise ValueError("raw archived PR31 bytes do not match reviewed identity")
    obj = json.loads(
        raw.decode("utf-8"), object_pairs_hook=unique_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    if obj.get("seal") != V2_SEAL:
        raise ValueError("wrong historical V2 seal")
    canonical = dict(obj)
    del canonical["seal"]
    expected = sha(json.dumps(canonical, sort_keys=True,
                              separators=(",", ":"), allow_nan=False).encode("utf-8"))
    if expected != V2_SEAL:
        raise ValueError("canonical seal mismatch")
    if obj.get("schema") != "sim_heat.reference_bundle/2" or (
        obj.get("origin") != "analytical_reference_only" or
        obj.get("nativeQualified") is not False
    ):
        raise ValueError("reference provenance/schema mismatch")
    if obj.get("specSha256") != SPEC_SHA or (
        sha(json.dumps(obj["spec"], sort_keys=True, separators=(",", ":"),
                       allow_nan=False).encode("utf-8")) != SPEC_SHA
    ):
        raise ValueError("original physical spec fingerprint mismatch")
    if obj["spec"]["modelSha256"] != MODEL_SHA or (
        obj["spec"]["studySha256"] != MODAL_STUDY_SHA
    ):
        raise ValueError("physical model/analysis input changed")
    grid = obj.get("grid", [])
    cols = obj.get("columns", {})
    ints = obj.get("flowIntegrals", {})
    if len(grid) != 4001 or len(cols) != 37 or len(ints) != 4:
        raise ValueError("missing/reference observations")
    if set(cols) != set(obj["allowances"]) or set(cols) != set(obj["units"]):
        raise ValueError("inconsistent allowance/unit set")
    if any(len(v) != 4001 for v in [*cols.values(), *ints.values()]):
        raise ValueError("wrong reference series length")
    if cols.get("hotLead.G") != [0.45]*4001 or (
        obj["method"].get("staticExportRoundingV2", {}).get(
            "oldF0ArchivedSeal") != OLD_F0_SEAL
    ):
        raise ValueError("V2 static correction/history missing")
    return obj


def build(raw, output_dir):
    original = verify_original(raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir/"PR31_V2_REFERENCE.json.xz"
    manifest_path = output_dir/"PR31_V2_REFERENCE_MANIFEST.json"
    if data_path.exists() or manifest_path.exists():
        raise FileExistsError("durable immutable-fixture candidate already exists; refuse overwrite")
    compressed = lzma.compress(raw, format=lzma.FORMAT_XZ, preset=6)
    if len(compressed) >= 1_000_000:
        raise ValueError("unexpected compressed size")
    if lzma.decompress(compressed) != raw:
        raise ValueError("compressed roundtrip differs")
    manifest = {
        "schema": "sim_heat.c1_v2_fixture_candidate/1",
        "status": "PROPOSED_STORAGE_ONLY_NOT_APPROVED_FOR_NATIVE_CONSUMPTION",
        "origin": "archived_independently_reviewed_PR31_V2_artifact",
        "approvedForNative": False,
        "nativeQualified": False,
        "nativeExecuted": False,
        "historicalF0SourceSha": F0_HEAD,
        "reviewedV2SourceSha": REVIEW_HEAD,
        "githubActionsRunId": 43915934653,
        "githubActionsArtifactId": 14249313720,
        "githubActionsOriginalZipSha256":
            "d9259837e0e03c70989b50b2c9dcbf13aca260da4d1cb0ae000b2a23ef65732e",
        "extractedArchivedFileName": "C1_REFERENCE_V2_BUNDLE.json",
        "originalReferenceFullSha256": V2_RAW_SHA,
        "originalReferenceBytes": V2_RAW_LENGTH,
        "canonicalSealedJsonSha256": V2_SEAL,
        "originalF0FailedReferenceSeal": OLD_F0_SEAL,
        "physicalSpecSha256": SPEC_SHA,
        "originalModelSha256": MODEL_SHA,
        "evaluatorStudySha256": MODAL_STUDY_SHA,
        "archiveEncoding": "lzma_xz_preset6_python_stdlib",
        "archivePath": "qualification/h1_c1/immutable_fixture/PR31_V2_REFERENCE.json.xz",
        "archiveFullSha256": sha(compressed),
        "archiveBytes": len(compressed),
        "channelCount": len(original["columns"]),
        "timeSampleCount": len(original["grid"]),
        "flowIntegralCount": len(original["flowIntegrals"]),
        "referenceErrorClaim":
            "PR31 R2 separately checked saved samples under unchanged 100x budget",
        "retentionClaim": "repository Git object candidate, not an approved source of truth",
        "limitations": [
            "original F0 80x static reference FAIL remains unchanged",
            "cross-host bitwise regeneration of reviewed PR31 V2 remains FAILED",
            "this bundle does not grant F02 native execution",
            "only owner-approved future consumer may bind exact archived bytes",
            "republication from GitHub Actions requires verification against immutable SHA",
        ],
    }
    with data_path.open("xb") as out:
        out.write(compressed)
    with manifest_path.open("x", encoding="utf-8") as out:
        out.write(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False)+"\n")
    print(json.dumps({
        "status": manifest["status"], "archiveSha256": manifest["archiveFullSha256"],
        "archivedBytes": V2_RAW_LENGTH, "compressedBytes": len(compressed),
        "archivedRawSha": V2_RAW_SHA, "archivedSeal": V2_SEAL,
        "nativeExecuted": False,
    }, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m ...capture_pr31_fixture <archived_bundle> <new_empty_dir>")
    raw_path, dir_path = Path(sys.argv[1]), Path(sys.argv[2])
    if not raw_path.is_file() or raw_path.is_symlink():
        raise ValueError("missing/untrusted archived input path")
    build(raw_path.read_bytes(), dir_path)
