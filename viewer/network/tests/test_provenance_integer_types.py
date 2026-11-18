"""PR51 Chat B F-01: six source metadata integer fields require literal int.

Synthetic/repacked archives with independently recomputed *test-only* ZIP and
member hashes. These are NOT native results, not original GitHub archive edits,
not an authenticated signature, and cannot authorize OpenModelica execution.
Original model, archived checking reference and historical native plans remain
untouched. All real original published archives are replayed separately in CI.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from h1.model import Refusal
from viewer.network.tools.build_case import stable_json
from viewer.network.tools.build_steady_case import compile_steady
from viewer.network.tests.test_steady_adapter import (
    ROOT, make_test_only_members, zip_test_only, RUN_ID,
    COMMIT, ARCHIVE_ARTIFACT_ID, CASE_TITLE,
)
from viewer.network.tests import test_project_audit as audit_fixtures


class StrictNativeMetadataIntegerTypes(unittest.TestCase):
    """Positive ordinary integer cases and independently rehashed negative variants."""

    @classmethod
    def setUpClass(cls):
        # The imported sibling test class is NOT collected by unittest here.
        # Initialize its original synthetic D1 campaign fixture explicitly.
        # This creates only test-only analytical checking data, never C1
        # saved-reference regeneration or native OpenModelica execution.
        audit_fixtures.CampaignTypeAuditTests.setUpClass()

    @staticmethod
    def repack_steady(*, record: str | None = None,
                      field: str | None = None, value=None):
        files,attempt=make_test_only_members()
        if record=="attempt":
            attempt["cases"][0][field]=value
        elif record=="provenance":
            key="case_01/mat_provenance.json"
            data=json.loads(files[key].decode("utf-8"))
            data[field]=value
            files[key]=stable_json(data)
        with TemporaryDirectory(prefix="simheat-typed-steady-") as d:
            path=Path(d)/"TEST-ONLY-repacked-steady.zip"
            digest=zip_test_only(path,files,attempt)
            return compile_steady(
                ROOT,"h1/cases/S1/study.json",path,digest,
                1,ARCHIVE_ARTIFACT_ID,CASE_TITLE,
                expected_run_id=RUN_ID,expected_commit_sha=COMMIT)

    @staticmethod
    def repack_campaign(*, record: str | None = None,
                        field: str | None = None,value=None):
        def mutate(files,attempt):
            if record=="attempt":
                attempt["cases"][0][field]=value
            elif record=="provenance":
                key="case_01/mat_provenance.json"
                data=json.loads(files[key].decode("utf-8"))
                data[field]=value
                files[key]=stable_json(data)
        # This is a coherent synthetic D1 campaign, NOT the original D2_K2
        # archive. It uses the actual source campaign adapter, as before.
        return audit_fixtures.CampaignTypeAuditTests().compile_mutant(mutate)

    def test_steady_original_literal_integer_controls_still_pass(self):
        output=self.repack_steady()
        self.assertIs(output["source"]["nativeQualified"],False)
        self.assertEqual(output["source"]["algebraicEvaluations"],2)
        self.assertIs(type(output["source"]["duplicateRowsCollapsed"]),int)

    def test_campaign_original_literal_integer_controls_still_pass(self):
        output=self.repack_campaign()
        self.assertIs(output["source"]["nativeQualified"],False)
        self.assertEqual(output["source"]["canonicalSamples"],1001)
        self.assertIs(type(output["source"]["duplicateRowsCollapsed"]),int)

    def test_steady_case_canonical_samples_refuses_floats_and_booleans(self):
        for wrong in (2.0,True,False,"2",None):
            with self.subTest(value=repr(wrong)):
                with self.assertRaises(Refusal) as caught:
                    self.repack_steady(record="attempt",field="canonicalSamples",value=wrong)
                self.assertEqual(caught.exception.code,"steady_evidence")

    def test_campaign_case_canonical_samples_refuses_floats_and_booleans(self):
        for wrong in (1001.0,True,False,"1001",None):
            with self.subTest(value=repr(wrong)):
                with self.assertRaises(Refusal) as caught:
                    self.repack_campaign(record="attempt",field="canonicalSamples",value=wrong)
                self.assertEqual(caught.exception.code,"campaign_evidence")

    def test_steady_provenance_sample_count_refuses_nonints(self):
        for wrong in (2.0,True,False,"2",None):
            with self.subTest(value=repr(wrong)):
                with self.assertRaises(Refusal) as caught:
                    self.repack_steady(record="provenance",field="samples",value=wrong)
                self.assertEqual(caught.exception.code,"steady_evidence")

    def test_campaign_provenance_sample_count_refuses_nonints(self):
        for wrong in (1001.0,True,False,"1001",None):
            with self.subTest(value=repr(wrong)):
                with self.assertRaises(Refusal) as caught:
                    self.repack_campaign(record="provenance",field="samples",value=wrong)
                self.assertEqual(caught.exception.code,"campaign_evidence")

    def test_steady_duplicate_row_count_refuses_true_and_float_one(self):
        for wrong in (True,1.0,False,0.0,"1",None):
            with self.subTest(value=repr(wrong)):
                with self.assertRaises(Refusal) as caught:
                    self.repack_steady(record="provenance",
                                       field="duplicateRowsCollapsed",value=wrong)
                self.assertEqual(caught.exception.code,"steady_evidence")

    def test_campaign_duplicate_row_count_refuses_true_and_float_one(self):
        for wrong in (True,1.0,False,0.0,"1",None):
            with self.subTest(value=repr(wrong)):
                with self.assertRaises(Refusal) as caught:
                    self.repack_campaign(record="provenance",
                                         field="duplicateRowsCollapsed",value=wrong)
                self.assertEqual(caught.exception.code,"campaign_evidence")

    def test_test_only_repacked_archives_remain_diagnostic_only(self):
        for kind,fun in (("steady",self.repack_steady),
                         ("campaign",self.repack_campaign)):
            with self.subTest(kind=kind):
                result=fun()
                self.assertEqual(result["source"]["evidenceKind"],
                                 "historical_native_diagnostic")
                self.assertIs(result["source"]["nativeQualified"],False)
                self.assertEqual(result["source"]["publicRequestStatus"],
                                 "diagnostic_only")


if __name__=="__main__":
    unittest.main()
