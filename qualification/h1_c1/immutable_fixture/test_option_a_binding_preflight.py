"""Proposed Option A reference/study binding tests; never grants native usage."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from h1 import reference
from qualification.h1_c1.immutable_fixture import option_a_binding_preflight as preflight
from qualification.h1_c1.immutable_fixture import inspect_pr31_fixture as fixture


class OptionAReadOnlyBindingTests(unittest.TestCase):
    def test_reviewed_bundle_binds_all_frozen_study_exports_without_native(self):
        result = preflight.audit()
        self.assertEqual(result["status"], "CANDIDATE_REFERENCE_STUDY_BINDING_PASS_NOT_OWNER_APPROVED")
        self.assertEqual(result["sourceHistory"]["sourcePinsVerified"], 23)
        self.assertEqual(result["matchedMandatoryExports"], 37)
        self.assertEqual(result["timeGridSamples"], 4001)
        self.assertEqual(result["flowIntegralHistories"], 4)
        self.assertEqual(result["publicRequests"], 9)
        self.assertEqual(result["checkedReferenceSeal"], preflight.EXPECTED_SEAL)
        self.assertFalse(result["ownerApprovedOptionA"])
        self.assertFalse(result["authorizedForNative"])
        self.assertFalse(result["nativeQualified"])
        self.assertFalse(result["nativeExecuted"])
        self.assertFalse(result["nativePlanCreated"])

    def test_reference_is_read_only_no_generator_invocation(self):
        with mock.patch.object(reference, "prepare", side_effect=AssertionError(
            "dynamic preparation forbidden for immutable V2 reference")):
            self.assertEqual(preflight.audit()["matchedMandatoryExports"], 37)

    def test_original_unlaunched_plan_source_hashes_checked(self):
        expected = preflight.source_identity(preflight.ROOT)
        self.assertEqual(expected["sourcePinsVerified"], 23)
        self.assertEqual(expected["originalUnlaunchedPlanSha256"], preflight.ORIGINAL_NATIVE_PLAN_SHA)

    def test_altered_study_file_refused_before_binding(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            plan=json.loads((preflight.ROOT/preflight.PLAN).read_text())
            for name in plan["pins"]:
                source=preflight.ROOT/name
                dest=root/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
            dest=root/preflight.PLAN
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(preflight.ROOT/preflight.PLAN,dest)
            study=root/preflight.STUDY
            study.write_bytes(study.read_bytes()+b"\n")
            with self.assertRaisesRegex(preflight.BindingRefusal, "source identity drift"):
                preflight.source_identity(root)

    def test_mutated_v2_bundle_refused_even_if_study_unchanged(self):
        original=fixture.load_candidate(inspect_only=True)
        obj=deepcopy(original)
        obj["bundle"]["columns"]["hotLead.G"][0] = 0.44999999999999996
        with mock.patch.object(preflight.fixture, "load_candidate",return_value=obj):
            with self.assertRaises(Exception):
                preflight.audit()

    def test_old_seal_cannot_be_accepted_as_replacement(self):
        original=fixture.load_candidate(inspect_only=True)
        obj=dict(original)
        obj["bundle"]=dict(original["bundle"],seal="d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b")
        with mock.patch.object(preflight.fixture, "load_candidate",return_value=obj):
            with self.assertRaisesRegex(preflight.BindingRefusal, "V2 reference seal not reviewed"):
                preflight.audit()

    def test_missing_archival_inputs_refused(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(Exception):
                preflight.audit(fixture_root=Path(t))

    def test_no_execute_or_materialize_command_exposed(self):
        with mock.patch("sys.stderr"):
            for command in ("execute","prepare","materialize","approve"):
                with self.subTest(command=command):
                    with self.assertRaises(SystemExit) as e:
                        preflight.main([command])
                    self.assertEqual(e.exception.code, 2)


if __name__=="__main__":
    unittest.main()
