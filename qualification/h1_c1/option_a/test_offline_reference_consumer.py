"""Adoption-only offline reference-consumer regressions; no Modelica execution."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from h1 import reference
from qualification.h1_c1.immutable_fixture import inspect_pr31_fixture as fixture
from qualification.h1_c1.option_a import offline_reference_consumer as consumer


class ApprovedOfflineReferenceTests(unittest.TestCase):
    def test_approved_scientific_reference_remains_non_native(self):
        bundle, receipt = consumer.load_for_offline_checking()
        self.assertEqual(receipt["status"], "APPROVED_REFERENCE_DATA_OFFLINE_CHECKING_ONLY")
        self.assertEqual(receipt["matchedExports"], 37)
        self.assertEqual(receipt["timeGridSamples"], 4001)
        self.assertEqual(receipt["flowIntegralHistories"], 4)
        self.assertEqual(receipt["publicRequests"], 9)
        self.assertEqual(receipt["referenceSeal"], consumer.EXPECTED_REFERENCE_SEAL)
        self.assertEqual(receipt["referenceAnchor"]["referenceAnchorCommit"],
                         consumer.REVIEWED_STORAGE_SHA)
        self.assertFalse(receipt["ownerDirectionAuthenticatedOnGitHub"])
        self.assertFalse(receipt["referenceAnchor"]["anchorProtectedOrSigned"])
        for field in ("nativeAllowed", "nativeQualified", "nativeExecuted",
                      "nativePlanApproved", "productionMergeAllowed",
                      "releaseTrustRootComplete"):
            self.assertIs(receipt[field], False)
        self.assertEqual(bundle["origin"], "analytical_reference_only")
        self.assertIs(bundle["nativeQualified"], False)

    def test_reference_generator_is_never_called(self):
        with mock.patch.object(reference, "prepare", side_effect=AssertionError(
            "regenerating reference rather than consuming archived bytes")):
            bundle, receipt = consumer.load_for_offline_checking()
        self.assertEqual(bundle["seal"], consumer.EXPECTED_REFERENCE_SEAL)
        self.assertFalse(receipt["nativeAllowed"])

    def test_original_source_anchor_is_exact_reviewed_commit_and_tree(self):
        pin = consumer.verify_reference_anchor(consumer.ROOT)
        self.assertEqual(pin["referenceAnchorCommit"], consumer.REVIEWED_STORAGE_SHA)
        self.assertEqual(pin["referenceAnchorTree"], consumer.REVIEWED_STORAGE_TREE)

    def test_moved_or_missing_anchor_refused(self):
        with mock.patch.object(consumer, "git_rev_parse", return_value="f"*40):
            with self.assertRaisesRegex(consumer.AdoptionRefusal, "moved"):
                consumer.verify_reference_anchor(consumer.ROOT)
        with mock.patch.object(consumer, "git_rev_parse", side_effect=consumer.AdoptionRefusal(
            "reviewed reference ref/tree missing")):
            with self.assertRaises(consumer.AdoptionRefusal):
                consumer.load_for_offline_checking()

    def test_unknown_and_native_purpose_refused(self):
        for purpose in ("native", "native_execution", "refit", "production", "", None):
            with self.subTest(purpose=purpose):
                with self.assertRaisesRegex(consumer.AdoptionRefusal, "only offline"):
                    consumer.load_for_offline_checking(purpose=purpose)

    def test_untrusted_owner_decision_raw_bytes_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root/consumer.DECISION_PATH
            target.parent.mkdir(parents=True,exist_ok=True)
            source = consumer.ROOT/consumer.DECISION_PATH
            shutil.copyfile(source,target)
            decision = consumer.verify_owner_record(root)
            self.assertTrue(decision["referenceUseApproved"])
            target.write_bytes(target.read_bytes()+b"\n")
            with self.assertRaisesRegex(consumer.AdoptionRefusal, "entire owner-decision"):
                consumer.verify_owner_record(root)

    def test_forged_native_permission_or_canonical_seal_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root/consumer.DECISION_PATH
            target.parent.mkdir(parents=True,exist_ok=True)
            original = json.loads((consumer.ROOT/consumer.DECISION_PATH).read_text())
            for field, value in (
                ("ownerApprovedNativeExecution", True),
                ("authorizedToRunOpenModelica", True),
                ("authorizedForProductionMerge", True),
                ("exactCanonicalReferenceSeal", "c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07"),
                ("originalF0ReferenceStrict100xPassed", True),
                ("v2GeneratorCrossHostBitwiseReproducible", True),
            ):
                with self.subTest(field=field):
                    changed = dict(original, **{field: value})
                    target.write_text(json.dumps(changed,sort_keys=True,indent=2)+"\n")
                    with self.assertRaises(consumer.AdoptionRefusal):
                        consumer.verify_owner_record(root)

    def test_second_read_cannot_replace_mathematical_reference(self):
        original = fixture.load_candidate(inspect_only=True)
        compromised = deepcopy(original)
        compromised["bundle"]["columns"]["hotLead.G"][0] = 0.44999999999999996
        with mock.patch.object(consumer.inspect_pr31_fixture, "load_candidate",
                               return_value=compromised):
            with self.assertRaisesRegex(consumer.AdoptionRefusal, "approved reference changed"):
                consumer.load_for_offline_checking()

    def test_second_read_cannot_swap_raw_identity(self):
        compromised = deepcopy(fixture.load_candidate(inspect_only=True))
        compromised["rawSha256"] = "f"*64
        with mock.patch.object(consumer.inspect_pr31_fixture, "load_candidate",
                               return_value=compromised):
            with self.assertRaisesRegex(consumer.AdoptionRefusal, "approved reference changed"):
                consumer.load_for_offline_checking()

    def test_no_unreviewed_cli_actions_or_native_execution(self):
        with mock.patch("sys.stderr"):
            for action in ("execute","prepare","approve","launch","native","materialize"):
                with self.subTest(action=action), self.assertRaises(SystemExit) as err:
                    consumer.main([action])
                self.assertEqual(err.exception.code,2)

    def test_receipt_is_offline_not_native_execution_or_owner_attestation(self):
        bundle, receipt = consumer.load_for_offline_checking()
        self.assertEqual(receipt["originalF0Strict100xResult"],"FAILED_HISTORIC_80X")
        self.assertFalse(receipt["scientificRegenBitwiseCertified"])
        self.assertFalse(receipt["ownerDirectionAuthenticatedOnGitHub"])
        self.assertFalse(receipt["nativePlanApproved"])
        self.assertEqual(len(bundle["grid"]),4001)


if __name__ == "__main__":
    unittest.main()
