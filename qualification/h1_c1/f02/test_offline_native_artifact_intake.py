"""Negative-only tests: local native-looking files NEVER establish native evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import uuid

from h1 import matv4, reference
from tools import h1_native_batch
from qualification.h1_c1.f02 import offline_native_artifact_intake as intake
from qualification.h1_c1.f02 import offline_stale_snapshot_cas_model as fake
from qualification.h1_c1.f02 import stage_immutable_inputs as staging


class NativeArtifactIntakeOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Real inherited source/study/archive binding performed once here.
        cls.original_readiness=intake.readiness.audit()
        assert cls.original_readiness["status"]==intake.readiness.STATUS
        assert cls.original_readiness["missingRequiredGateCount"]==11

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="simheat-intake-fake-")
        self.root=Path(self.temp.name)
        self.label="candidate-"+uuid.uuid4().hex[:12]
        self.parent=self.root/intake.CANDIDATE_PARENT
        self.folder=self.parent/self.label
        # Source checks already validated in setUpClass; use a stable result
        # for isolated malformed-file stress and avoid reference regeneration.
        self.audit_patch=mock.patch.object(
            intake.readiness,"audit",return_value=self.original_readiness)
        self.audit_patch.start()

    def tearDown(self):
        self.audit_patch.stop()
        self.temp.cleanup()

    def check(self):
        return intake.inspect_only(label=self.label,candidate_root=self.root)

    def write(self,name,data):
        self.folder.mkdir(parents=True,exist_ok=True)
        path=self.folder/name
        path.write_bytes(data)
        return path

    def assert_blocked(self,report):
        self.assertEqual(report["status"],intake.STATUS)
        self.assertIs(report["releaseBlocked"],True)
        self.assertEqual(len(report["elevenReleaseGatesStillMissing"]),11)
        self.assertEqual(report["nativePublicRequestsStillNotComputed"],9)
        self.assertIs(report["allFileNamesPresentWouldBeNativeProof"],False)
        self.assertIs(report["localFileHashesAreAuthenticProvenance"],False)
        for key in intake.NO_EXECUTION_FIELDS:
            with self.subTest(native_flag=key):
                self.assertIs(report[key],False,key)

    def test_integrated_real_science_HOLD_and_absent_evidence(self):
        # setUpClass ran the full pinned scientific HOLD audit once.
        # Metadata/staging is deliberately absent: still successful HOLD.
        report=self.check()
        self.assert_blocked(report)
        self.assertEqual(report["missingFilenames"],list(intake.FILE_NAMES))
        self.assertEqual(report["localFilesOnly"],{})
        self.assertEqual(report["sourcePinsVerified"],23)

    def test_missing_candidate_does_not_create_directory(self):
        self.assertFalse(self.parent.exists())
        self.assert_blocked(self.check())
        self.assertFalse(self.parent.exists())

    def test_partial_unauthenticated_file_is_hashed_not_qualified(self):
        p=self.write("model_res.mat",b"SIMULATED_FAKE_MAT_DO_NOT_DECODE")
        result=self.check()
        self.assert_blocked(result)
        self.assertEqual(set(result["localFilesOnly"]),{"model_res.mat"})
        self.assertEqual(len(result["missingFilenames"]),len(intake.FILE_NAMES)-1)
        self.assertEqual(result["localFilesOnly"][p.name]["untrustedLocalSha256"],
                         hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertIs(result["localFilesOnly"][p.name]["originAuthenticated"],False)
        self.assertIs(result["localFilesOnly"][p.name]["nativeEvidenceVerified"],False)

    def test_every_expected_file_name_can_exist_and_still_never_pass(self):
        for name in intake.FILE_NAMES:
            raw=(b"FAKE_NATIVE_OUTPUT_NOT_OMC" if not name.endswith(".json")
                 else json.dumps({"ownerSigned":True,"nativeQualified":True,
                                  "fake":True}).encode())
            self.write(name,raw)
        x=self.check()
        self.assert_blocked(x)
        self.assertEqual(len(x["localFilesOnly"]),len(intake.FILE_NAMES))
        self.assertEqual(x["missingFilenames"],[])
        self.assertEqual(x["nativePublicRequestsStillNotComputed"],9)

    def test_forged_owner_and_native_metadata_cannot_upgrade_receipt(self):
        self.write("source-release.json",b'{"ownerSigned": true, "nativeAllowed": true}')
        self.write("durable-reservation-receipt.json",
                   b'{"ownerNativeLaunchApproved": true, "reservation": "claimed"}')
        self.write("native-run-receipt.json",
                   b'{"nativeQualified":true,"actualRequestsComputed":9}')
        self.write("post-native-checks.json",b'{"status":"PASS","accepted":true}')
        x=self.check()
        self.assert_blocked(x)
        self.assertEqual(len(x["localFilesOnly"]),4)

    def test_forged_evidence_metadata_numeric_zero_remains_untrusted(self):
        self.write("source-release.json",
                   b'{"ownerNativeLaunchApproved":0,"nativeAllowed":0.0}')
        self.assert_blocked(self.check())

    def test_candidate_file_hash_mutation_is_not_provenance(self):
        path=self.write("normalized.csv",b"time,x\n0,12345\n")
        x=self.check()
        path.write_bytes(b"time,x\n0,54321\n")
        y=self.check()
        self.assertNotEqual(x["localFilesOnly"]["normalized.csv"]["untrustedLocalSha256"],
                            y["localFilesOnly"]["normalized.csv"]["untrustedLocalSha256"])
        self.assert_blocked(x)
        self.assert_blocked(y)

    def test_duplicate_json_key_rejected(self):
        self.write("source-release.json",
                   b'{"ownerNativeLaunchApproved": true, "ownerNativeLaunchApproved":false}')
        with self.assertRaisesRegex(staging.StageRefusal,"duplicate JSON metadata key"):
            self.check()

    def test_nonfinite_json_constants_rejected(self):
        for invalid in (b'NaN',b'Infinity',b'-Infinity'):
            with self.subTest(token=invalid):
                self.write("source-release.json",b'{"rating":'+invalid+b'}')
                with self.assertRaisesRegex(staging.StageRefusal,
                                            "nonstandard JSON constant"):
                    self.check()

    def test_valid_json_exponent_overflow_rejected_at_any_depth(self):
        # PR44 reviewer F-06: 1e999 is valid JSON but Python decodes to inf.
        samples=(
            b'{"reading":1e999}',
            b'{"reading":-1e999}',
            b'{"reading":1E+9999}',
            b'{"nested":{"reported":[1.0,{"v":-2.5e999}]}}',
        )
        for name in ("source-release.json","native-run-receipt.json",
                     "post-native-checks.json"):
            for raw in samples:
                with self.subTest(name=name,raw=raw):
                    path=self.write(name,raw)
                    with self.assertRaisesRegex(intake.IntakeRefusal,
                                                "nonfinite JSON number"):
                        self.check()
                    path.unlink()

    def test_finite_json_exponents_are_still_untrusted(self):
        path=self.write("host-toolchain-attestation.json",
                        b'{"large":1e308,"small":1e-308,'
                        b'"fakeOwnerNativeLaunchApproved":true}')
        report=self.check()
        self.assert_blocked(report)
        self.assertEqual(report["localFilesOnly"][path.name]["untrustedLocalSha256"],
                         hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertIs(report["localFilesOnly"][path.name]["originAuthenticated"],False)

    def test_json_sha_and_parser_consume_one_identical_byte_read(self):
        path=self.write("native-run-receipt.json",
                        b'{"nativeQualified":true,"origin":"UNTRUSTED"}')
        real_read=Path.read_bytes
        reads=[]
        def tracked_read(p):
            if p==path:
                reads.append(p.name)
            return real_read(p)
        # No prior strict_metadata(path) should reopen a mutable file AFTER
        # the SHA was calculated. This does not make the directory atomic.
        with (
            mock.patch.object(Path,"read_bytes",new=tracked_read),
            mock.patch.object(staging,"strict_metadata",
                              side_effect=AssertionError("second JSON open forbidden")),
        ):
            report=self.check()
        self.assertEqual(reads,[path.name])
        self.assert_blocked(report)
        self.assertEqual(report["localFilesOnly"][path.name]["untrustedLocalSha256"],
                         hashlib.sha256(real_read(path)).hexdigest())

    def test_nested_duplicate_json_keys_still_refuse_with_same_bytes(self):
        self.write("source-release.json",
                   b'{"envelope":{"nativeAllowed":true,"nativeAllowed":false}}')
        with self.assertRaisesRegex(staging.StageRefusal,
                                    "duplicate JSON metadata key"):
            self.check()

    def test_malformed_json_rejected(self):
        for raw in (b'{bad',b'\xff',b'[]',b'{"owner":}'):
            with self.subTest(raw=raw):
                self.write("host-toolchain-attestation.json",raw)
                with self.assertRaises((staging.StageRefusal,ValueError)):
                    self.check()

    def test_unexpected_native_script_or_executable_refused(self):
        self.write("model_res.mat",b"fake")
        self.write("build.mos",b"getVersion();")
        with self.assertRaisesRegex(intake.IntakeRefusal,"unexpected"):
            self.check()

    def test_empty_or_oversized_candidate_refused(self):
        for name in ("model_res.mat","native-run-receipt.json"):
            with self.subTest(name=name):
                path=self.write(name,b"")
                with self.assertRaisesRegex(intake.IntakeRefusal,"empty/oversized"):
                    self.check()
                path.write_bytes(b"x"*(intake.UNTRUSTED_FILENAMES[name]+1))
                with self.assertRaisesRegex(intake.IntakeRefusal,"empty/oversized"):
                    self.check()
                path.unlink()

    def test_symlinked_candidate_parent_refused(self):
        real=self.root/"real-parent"
        real.mkdir()
        self.parent.symlink_to(real,target_is_directory=True)
        with self.assertRaisesRegex(intake.IntakeRefusal,"symlinked"):
            self.check()

    def test_symlinked_candidate_directory_refused(self):
        target=self.root/"real"
        target.mkdir()
        self.parent.mkdir()
        self.folder.symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(intake.IntakeRefusal,"symlinked"):
            self.check()

    def test_symlinked_candidate_member_refused(self):
        source=self.root/"real-file.json"
        source.write_text('{"notTrusted":true}')
        self.folder.mkdir(parents=True)
        (self.folder/"source-release.json").symlink_to(source)
        with self.assertRaisesRegex(intake.IntakeRefusal,"nonregular or symlinked"):
            self.check()

    def test_bad_label_and_extra_files_refuse(self):
        for bad in ("../path","/tmp/p","UPPER","hello/other","a_b","",None):
            with self.subTest(label=bad):
                with self.assertRaises(intake.IntakeRefusal):
                    intake.inspect_only(label=bad,candidate_root=self.root)
        self.write("source-release.json",b"{}")
        self.write(".hidden",b"fake")
        with self.assertRaises(intake.IntakeRefusal):
            self.check()

    def test_false_owner_or_fake_CAS_never_accepted_from_prior_stage(self):
        receipt=fake.fake_stale_reader_race(contenders=8)
        receipt["status"]="OWNER_SIGNED_APPROVED"
        receipt["fakeCounts"]["oneFakeFirstClaims"]=999
        # PR43 F-06: superficially well-shaped but fabricated fake counts
        # aren't authenticated, regardless of shape validators.
        fake.validate_receipt(receipt)
        self.write("durable-reservation-receipt.json",
                   json.dumps(receipt).encode())
        x=self.check()
        self.assert_blocked(x)
        with self.assertRaises(fake.CASRefusal):
            fake.require_real_native_permission(receipt)

    def test_source_reference_HOLD_refusal_propagates(self):
        with mock.patch.object(intake.readiness,"audit",
                               side_effect=intake.IntakeRefusal("missing owner release")):
            with self.assertRaisesRegex(intake.IntakeRefusal,"owner release"):
                self.check()

    def test_no_native_MAT_decoder_reference_regenerator_or_subprocess(self):
        self.write("model_res.mat",b"FAKE MAT, NEVER DECODE")
        with mock.patch.object(matv4,"decode_mat_file",side_effect=AssertionError(
                "MAT decoding forbidden without native attestation")), \
             mock.patch.object(reference,"prepare",side_effect=AssertionError(
                "regenerating approved saved reference forbidden")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
                "native preparation forbidden")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
                "native execution forbidden")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
                "native subprocess forbidden")):
            self.assert_blocked(self.check())

    def test_only_untrusted_inspection_CLI_available(self):
        with mock.patch("builtins.print"):
            self.assertEqual(intake.main(["inspect-untrusted-files-only",
                                          "--label","ci-offline-intake"]),0)
        for action in ("native","execute","approve","run","build","launch",
                       "omc","reserve-native","verify-native","qualify"):
            with self.subTest(action=action),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    intake.main([action,"--label",self.label])
                self.assertEqual(ctx.exception.code,2)


if __name__=="__main__":
    unittest.main()
