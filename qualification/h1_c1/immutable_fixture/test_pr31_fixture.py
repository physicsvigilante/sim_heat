"""Offline negative controls for the candidate archived PR31 V2 reference.

Every adversarial case must be refused, including an attempt to turn storage
identity into owner/native approval. No original or frozen source is modified.
"""
import copy
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from qualification.h1_c1.immutable_fixture import inspect_pr31_fixture as inspector
from qualification.h1_c1.immutable_fixture.capture_pr31_fixture import (
    V2_RAW_SHA, V2_SEAL, verify_original,
)


class ImmutableFixtureTests(unittest.TestCase):
    def setUp(self):
        self.source = inspector.source_directory()

    def install_copy(self, directory):
        target = Path(directory)
        for name in (inspector.BUNDLE_NAME, inspector.MANIFEST_NAME):
            shutil.copyfile(self.source/name, target/name)
        return target

    def load_manifest(self, root):
        return json.loads((root/inspector.MANIFEST_NAME).read_text(encoding="utf-8"))

    def save_manifest(self, root, manifest):
        (root/inspector.MANIFEST_NAME).write_text(
            json.dumps(manifest, sort_keys=True, indent=2)+"\n", encoding="utf-8")

    def test_original_bundle_and_metadata_correct(self):
        obj = inspector.load_candidate(inspect_only=True)
        self.assertEqual(obj["rawSha256"], V2_RAW_SHA)
        self.assertEqual(obj["bundle"]["seal"], V2_SEAL)
        self.assertFalse(obj["manifest"]["approvedForNative"])
        self.assertEqual(len(obj["bundle"]["columns"]),37)
        self.assertEqual(len(obj["bundle"]["grid"]),4001)
        self.assertEqual(len(obj["bundle"]["flowIntegrals"]),4)

    def test_default_use_refused_even_with_valid_archive(self):
        with self.assertRaises(inspector.FixtureRefusal):
            inspector.load_candidate()
        with self.assertRaises(inspector.FixtureRefusal):
            inspector.load_candidate(inspect_only=False)

    def test_missing_and_corrupted_compressed_fixture_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=self.install_copy(t)
            data=(root/inspector.BUNDLE_NAME).read_bytes()
            changed=bytearray(data)
            changed[len(changed)//2] ^= 0x40
            (root/inspector.BUNDLE_NAME).write_bytes(changed)
            with self.assertRaises(inspector.FixtureRefusal):
                inspector.load_candidate(root,inspect_only=True)
            (root/inspector.BUNDLE_NAME).unlink()
            with self.assertRaises(inspector.FixtureRefusal):
                inspector.load_candidate(root,inspect_only=True)

    def test_forged_manifest_and_approval_refused(self):
        for field, replacement in (
            ("approvedForNative", True),
            ("canonicalSealedJsonSha256", "f"*64),
            ("reviewedV2SourceSha", "f"*64),
            ("physicalSpecSha256", "f"*64),
            ("archiveFullSha256", "f"*64),
            # PR #33 review F-01: these originally unpinned claims could be
            # counterfeited without modifying the valid stored reference.
            ("githubActionsOriginalZipSha256", "f"*64),
            ("extractedArchivedFileName", "unreviewed.json"),
            ("origin", "owner_certified_native_reference"),
            ("limitations", []),
            ("retentionClaim", "permanent owner certified reference"),
            ("referenceErrorClaim", "no reference errors exist"),
            ("archiveEncoding", "different_unverified_compressor"),
            ("archiveBytes", 636796),
        ):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as t:
                    root=self.install_copy(t)
                    manifest=self.load_manifest(root)
                    manifest[field]=replacement
                    self.save_manifest(root,manifest)
                    with self.assertRaises(inspector.FixtureRefusal):
                        inspector.load_candidate(root,inspect_only=True)

    def test_recompressed_altered_raw_reference_refused(self):
        """Even if attacker edits the manifest's compression SHA, raw SHA pins fail."""
        with tempfile.TemporaryDirectory() as t:
            root=self.install_copy(t)
            compressed=(root/inspector.BUNDLE_NAME).read_bytes()
            raw=lzma.decompress(compressed)
            obj=json.loads(raw)
            obj["columns"]["hotLead.G"][0]=0.44999999999999996
            forged_raw=(json.dumps(obj,sort_keys=True,indent=2)+"\n").encode("utf-8")
            forged=lzma.compress(forged_raw,format=lzma.FORMAT_XZ,preset=6)
            (root/inspector.BUNDLE_NAME).write_bytes(forged)
            manifest=self.load_manifest(root)
            manifest["archiveBytes"]=len(forged)
            manifest["archiveFullSha256"]=hashlib.sha256(forged).hexdigest()
            self.save_manifest(root,manifest)
            with self.assertRaises(inspector.FixtureRefusal):
                inspector.load_candidate(root,inspect_only=True)

    def test_valid_alternate_compression_with_forged_manifest_refused(self):
        """PR33 F-02: different valid XZ cannot replace the pinned Git object."""
        with tempfile.TemporaryDirectory() as t:
            root = self.install_copy(t)
            original = (root/inspector.BUNDLE_NAME).read_bytes()
            exact_raw = lzma.decompress(original)
            different = lzma.compress(exact_raw, format=lzma.FORMAT_XZ, preset=3)
            self.assertNotEqual(different, original)
            self.assertEqual(lzma.decompress(different), exact_raw)
            (root/inspector.BUNDLE_NAME).write_bytes(different)
            fake = self.load_manifest(root)
            fake["archiveFullSha256"] = hashlib.sha256(different).hexdigest()
            fake["archiveBytes"] = len(different)
            self.save_manifest(root, fake)
            with self.assertRaises(inspector.FixtureRefusal):
                inspector.load_candidate(root, inspect_only=True)

    def test_decoder_memory_limit_applied_to_authentic_archive(self):
        """PR33 F-03: actual decoder receives a bounded XZ memlimit."""
        original_decoder = lzma.LZMADecompressor
        with mock.patch.object(inspector.lzma, "LZMADecompressor",
                               wraps=original_decoder) as decoder:
            data = inspector.load_candidate(inspect_only=True)
            self.assertEqual(data["rawSha256"], V2_RAW_SHA)
            decoder.assert_called_once_with(
                format=lzma.FORMAT_XZ,
                memlimit=inspector.XZ_DECODER_MEMORY_LIMIT)

    def test_modified_header_refused_before_decoder_allocation(self):
        with tempfile.TemporaryDirectory() as t:
            root = self.install_copy(t)
            corrupted = bytearray((root/inspector.BUNDLE_NAME).read_bytes())
            corrupted[0] ^= 0x40
            (root/inspector.BUNDLE_NAME).write_bytes(corrupted)
            with mock.patch.object(inspector.lzma, "LZMADecompressor") as decoder:
                with self.assertRaises(inspector.FixtureRefusal):
                    inspector.load_candidate(root, inspect_only=True)
                decoder.assert_not_called()

    def test_original_raw_archive_rejects_changed_data(self):
        from qualification.h1_c1.immutable_fixture.capture_pr31_fixture import (
            V2_RAW_LENGTH,)
        raw=lzma.decompress((self.source/inspector.BUNDLE_NAME).read_bytes())
        self.assertEqual(len(raw),V2_RAW_LENGTH)
        verify_original(raw)
        with self.assertRaises(ValueError):
            verify_original(raw+b"\n")


if __name__=="__main__":
    unittest.main()
