"""Offline adversarial tests for non-executable H1-C1 F02 control preview."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from h1 import reference
from qualification.h1_c1.f02 import offline_control_preflight as f02


class F02ControlPreviewTests(unittest.TestCase):
    def plan(self):
        doc, raw_sha = f02.load_preview()
        self.assertEqual(len(raw_sha), 64)
        return doc

    def test_preview_binds_original_model_and_adopted_science_without_native(self):
        result = f02.audit()
        self.assertEqual(result["status"], "F02_CONTROL_DESIGN_PREFLIGHT_PASS_NONEXECUTABLE")
        self.assertEqual(result["sourceIdentityPinsVerified"], 23)
        self.assertEqual(result["publicRequests"], 9)
        self.assertEqual(result["exportChannels"], 37)
        self.assertEqual(result["timeGridSamples"], 4001)
        self.assertEqual(result["integralHistories"], 4)
        self.assertEqual(result["reviewedReferenceSeal"], f02.REF_SEAL)
        self.assertEqual(result["previewGitBlobSha1"], f02.PLAN_GIT_BLOB)
        for flag in ("compilerObserved","mslObserved","oneShotReservationAllocated",
                     "trustedReleaseRootComplete","nativePlanApproved",
                     "ownerNativeLaunchApproved","nativeExecuted","nativeQualified",
                     "referenceRegenerated","originalF0ReferencePassed100x",
                     "pr32CrossHostBitwiseRegenerationPassed"):
            self.assertIs(result[flag], False,flag)

    def test_no_reference_recalculation_may_be_called(self):
        with mock.patch.object(reference, "prepare", side_effect=AssertionError(
            "regenerating the reviewed V2 reference is forbidden")):
            self.assertEqual(f02.audit()["sourceIdentityPinsVerified"], 23)

    def test_tampered_plan_file_cannot_advance(self):
        original = (f02.ROOT/f02.PLAN).read_bytes()
        with tempfile.TemporaryDirectory() as t:
            altered = Path(t)/"proposal.json"
            altered.write_bytes(original + b"\n")
            with self.assertRaisesRegex(f02.PreviewRefusal, "original pinned"):
                f02.load_preview(altered)

    def test_converted_to_original_native_batch_schema_refuses(self):
        altered = self.plan()
        altered["schema"] = "sim_heat.native_batch/1"
        with self.assertRaises(f02.PreviewRefusal):
            f02.validate_preview(altered)

    def test_native_flags_forgery_refused(self):
        for k in ("nativeAllowed","createExecutable","queryCompilerVersion",
                  "buildModel","launchModel","retryAllowed",
                  "allowSimulationEvidenceClaim","allowAutomaticReferenceRegeneration"):
            with self.subTest(field=k):
                altered = deepcopy(self.plan())
                altered["launchPolicy"][k] = True
                with self.assertRaises(f02.PreviewRefusal):
                    f02.validate_preview(altered)

    def test_one_shot_budget_must_be_exact(self):
        for n in (0, 2, 999):
            with self.subTest(launches=n):
                altered = self.plan()
                altered["launchPolicy"]["maxLaunchesAfterSeparateApproval"] = n
                with self.assertRaises(f02.PreviewRefusal):
                    f02.validate_preview(altered)

    def test_fake_native_owner_or_host_reservation_refused(self):
        keys = self.plan()["requiredNotYetEstablished"]
        for k in keys:
            with self.subTest(field=k):
                altered = self.plan()
                altered["requiredNotYetEstablished"][k] = "CLAIMED_PRESENT"
                with self.assertRaises(f02.PreviewRefusal):
                    f02.validate_preview(altered)

    def test_reference_substitution_and_regeneration_refused(self):
        changes = {
            "archivedCanonicalSeal": "c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07",
            "archivedRawSha256": "f"*64,
            "archivedCompressedSha256": "f"*64,
            "sourceAnchorCommit": "f"*40,
            "regenerationPermitted": True,
        }
        for k, v in changes.items():
            with self.subTest(field=k):
                altered = self.plan()
                altered["checkingReference"][k] = v
                with self.assertRaises(f02.PreviewRefusal):
                    f02.validate_preview(altered)

    def test_toolchain_and_grid_cannot_be_relaxed(self):
        for k, value in (
            ("openModelicaVersion", "OpenModelica 1.26.0"),
            ("modelicaStandardLibraryVersion", "3.2.3"),
            ("pythonVersion", "3.12.0"),
        ):
            with self.subTest(k=k):
                altered = self.plan()
                altered["expectedToolchain"][k] = value
                with self.assertRaises(f02.PreviewRefusal):
                    f02.validate_preview(altered)
        grid = self.plan()
        grid["plannedStudySettings"]["intervals"] = 500
        with self.assertRaises(f02.PreviewRefusal):
            f02.validate_preview(grid)

    def test_original_negative_history_not_rewritten(self):
        for field in ("originalFrozenF0Static100xReferencePassed",
                      "pr32ReviewedV2BitwiseRegenerationPassed", "nativeObserved"):
            with self.subTest(field=field):
                altered = self.plan()
                altered["historicalLimitations"][field] = True
                with self.assertRaises(f02.PreviewRefusal):
                    f02.validate_preview(altered)

    def test_native_actions_are_not_available_in_cli(self):
        for action in ("execute","prepare","approve","launch","native","run-model"):
            with self.subTest(action=action), mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as exc:
                    f02.main([action])
                self.assertEqual(exc.exception.code, 2)

    def test_refused_when_owner_consumer_unapproved_or_wrong_reference(self):
        from qualification.h1_c1.option_a import offline_reference_consumer as consumer
        with mock.patch.object(consumer, "load_for_offline_checking",
                               side_effect=consumer.AdoptionRefusal("no offline authority")):
            with self.assertRaises(consumer.AdoptionRefusal):
                f02.audit()
        with mock.patch.object(consumer, "load_for_offline_checking",
                               return_value=({}, {"status":"FAKE",
                                                  "referenceSeal":"f"*64,
                                                  "archivedReferenceRawSha256":"f"*64,
                                                  "nativeAllowed":False,
                                                  "nativePlanApproved":False,
                                                  "nativeExecuted":False})):
            with self.assertRaises(f02.PreviewRefusal):
                f02.audit()

    def test_refused_when_original_source_pin_mismatch(self):
        with mock.patch.object(f02.option_a_binding_preflight, "audit",
                               side_effect=f02.PreviewRefusal("original frozen source pin differs")):
            with self.assertRaisesRegex(f02.PreviewRefusal, "source pin differs"):
                f02.audit()


if __name__ == "__main__":
    unittest.main()
