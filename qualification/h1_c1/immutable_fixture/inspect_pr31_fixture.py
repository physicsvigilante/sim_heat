"""Read-only integrity verifier for a PROPOSED archived checking-reference fixture.

No fallback to reference.prepare, OpenModelica, native runner, or floating input.
Default is fail closed because owner certification/promotion is NOT approved.
"""
import hashlib
import json
import lzma
from pathlib import Path

from .capture_pr31_fixture import (
    V2_RAW_SHA, V2_RAW_LENGTH, V2_SEAL, OLD_F0_SEAL,
    SPEC_SHA, MODEL_SHA, MODAL_STUDY_SHA, REVIEW_HEAD, F0_HEAD,
    unique_pairs, verify_original,
)

EXPECTED_STATUS = "PROPOSED_STORAGE_ONLY_NOT_APPROVED_FOR_NATIVE_CONSUMPTION"
BUNDLE_NAME = "PR31_V2_REFERENCE.json.xz"
MANIFEST_NAME = "PR31_V2_REFERENCE_MANIFEST.json"

# Trusted only with a separately reviewed/pinned source commit. These constants
# are independent of writable values inside the candidate manifest itself.
EXPECTED_MANIFEST_RAW_SHA256 = "50467b138ed64cdb908f2c763bc777e6babf0bb04a0711568acc559112e66f84"
EXPECTED_ARCHIVE_RAW_SHA256 = "fc5a7df5928c3fb8aef2ba4af516dfbd32b42c0450ebef1051ad4fd7efebd17f"
EXPECTED_ARCHIVE_BYTES = 503_552
XZ_DECODER_MEMORY_LIMIT = 64 * 1024 * 1024


class FixtureRefusal(ValueError):
    pass


def source_directory():
    return Path(__file__).resolve().parent


def load_candidate(root=None, *, inspect_only=False):
    """Verify exact original archived bytes, but NEVER authorize native use.

    inspect_only=True is a restricted archival test/report surface, not
    a bypass to obtain a native-qualifying, owner-approved reference.
    """
    if not inspect_only:
        raise FixtureRefusal("owner approval and separate native plan absent; no reference consumption")
    root = Path(root) if root is not None else source_directory()
    binary = root/BUNDLE_NAME
    manifest_path = root/MANIFEST_NAME
    if not binary.is_file() or binary.is_symlink() or (
        not manifest_path.is_file() or manifest_path.is_symlink()
    ):
        raise FixtureRefusal("candidate archived fixture/manifest missing or symlink")
    try:
        # Verify the *whole* originally reviewed manifest before interpreting
        # its historical attribution or any values used as evidence.
        if manifest_path.stat().st_size > 20_000:
            raise FixtureRefusal("oversized fixture manifest")
        manifest_raw = manifest_path.read_bytes()
        if hashlib.sha256(manifest_raw).hexdigest() != EXPECTED_MANIFEST_RAW_SHA256:
            raise FixtureRefusal("entire manifest is not the pinned reviewed manifest")
        manifest = json.loads(manifest_raw.decode("utf-8"), object_pairs_hook=unique_pairs)
        if manifest.get("schema") != "sim_heat.c1_v2_fixture_candidate/1" or (
            manifest.get("status") != EXPECTED_STATUS or
            manifest.get("approvedForNative") is not False or
            manifest.get("nativeQualified") is not False or
            manifest.get("nativeExecuted") is not False
        ):
            raise FixtureRefusal("wrong candidate contract/status; native not authorized")
        requirements = {
            "reviewedV2SourceSha": REVIEW_HEAD,
            "historicalF0SourceSha": F0_HEAD,
            "githubActionsRunId": 43915934653,
            "githubActionsArtifactId": 14249313720,
            "originalReferenceFullSha256": V2_RAW_SHA,
            "originalReferenceBytes": V2_RAW_LENGTH,
            "canonicalSealedJsonSha256": V2_SEAL,
            "originalF0FailedReferenceSeal": OLD_F0_SEAL,
            "physicalSpecSha256": SPEC_SHA,
            "originalModelSha256": MODEL_SHA,
            "evaluatorStudySha256": MODAL_STUDY_SHA,
            "archivePath":
                "qualification/h1_c1/immutable_fixture/PR31_V2_REFERENCE.json.xz",
            "archiveEncoding": "lzma_xz_preset6_python_stdlib",
            "channelCount": 37, "timeSampleCount": 4001, "flowIntegralCount": 4,
        }
        for field, expected in requirements.items():
            if manifest.get(field) != expected:
                raise FixtureRefusal("fixture manifest identity field mismatch: "+field)
        # The specific Git object is pinned independently of the mutable
        # manifest. Recompression and manifest rehashing cannot pass.
        if binary.stat().st_size != EXPECTED_ARCHIVE_BYTES:
            raise FixtureRefusal("archive size not the pinned reviewed representation")
        payload = binary.read_bytes()
        payload_sha = hashlib.sha256(payload).hexdigest()
        if (len(payload) != EXPECTED_ARCHIVE_BYTES or
            payload_sha != EXPECTED_ARCHIVE_RAW_SHA256 or
            len(payload) != manifest.get("archiveBytes") or
            payload_sha != manifest.get("archiveFullSha256")
        ):
            raise FixtureRefusal("compressed archive differs from pinned reviewed bytes")
        # Bound XZ dictionary/decoder memory independently of the output cap.
        # The original archive is authenticated before invoking the decoder.
        decompressor = lzma.LZMADecompressor(
            format=lzma.FORMAT_XZ, memlimit=XZ_DECODER_MEMORY_LIMIT)
        plain = decompressor.decompress(payload, max_length=V2_RAW_LENGTH+1)
        if not decompressor.eof or decompressor.unused_data or (
            len(plain) != V2_RAW_LENGTH
        ):
            raise FixtureRefusal("compressed archive unexpectedly large/truncated/trailing bytes")
        obj = verify_original(plain)
        return {"bundle": obj,
                "manifest": manifest,
                "compressedSha256": hashlib.sha256(payload).hexdigest(),
                "rawSha256": hashlib.sha256(plain).hexdigest()}
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError,
            KeyError, TypeError, EOFError, lzma.LZMAError) as exc:
        if isinstance(exc, FixtureRefusal):
            raise
        raise FixtureRefusal("candidate fixture verification refused") from exc


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archived-root", type=Path, default=source_directory())
    p.add_argument("--inspect-only", action="store_true")
    args = p.parse_args()
    try:
        result = load_candidate(args.archived_root, inspect_only=args.inspect_only)
        report = {
            "status": "CANDIDATE_STORAGE_INTEGRITY_PASS_NOT_AUTHORIZED_FOR_NATIVE",
            "nativeQualified": False, "nativeExecuted": False,
            "approvedForNative": False,
            "archivedRawSha256": result["rawSha256"],
            "archivedCanonicalSeal": result["bundle"]["seal"],
            "storedCompressionSha256": result["compressedSha256"],
            "samples": len(result["bundle"]["grid"]),
            "channels": len(result["bundle"]["columns"]),
        }
    except FixtureRefusal as exc:
        report = {
            "status": "REFUSED_NO_APPROVED_CANONICAL_FIXTURE",
            "nativeQualified": False, "nativeExecuted": False,
            "approvedForNative": False, "reason": str(exc),
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"].startswith("CANDIDATE_STORAGE_INTEGRITY") else 3


if __name__ == "__main__":
    raise SystemExit(main())
