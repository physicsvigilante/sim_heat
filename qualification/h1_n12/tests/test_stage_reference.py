"""N12 three-source-study, proof staging and strict refusal tests only.

These tests never grant OpenModelica permission, adopt a reference, or
overwrite the original author submission; no native binary is invoked.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from qualification.h1_n12 import stage_reference as n12
from qualification.h1_n1 import certified_reference as n1


class TripleSourceStageTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model,cls.source_bytes,cls.facts,cls.study,cls.plan=(
            n12.original_snapshots())

    def test_frozen_original_author_and_future_n3_contract_pins(self):
        self.assertEqual(n12.digest(self.model),n12.SOURCE_MODEL_SHA)
        self.assertEqual(n12.digest(self.source_bytes),n12.SOURCE_STUDY_SHA)
        self.assertEqual(n12.digest(self.facts),n12.SOURCE_FACTS_SHA)
        self.assertEqual(n12.git_blob(n12.PLAN.read_bytes()),
                         n12.EXPECTED_PLAN_BLOB)
        self.assertEqual(n12.git_blob(Path(n12.n11.__file__).read_bytes()),
                         n12.EXPECTED_N11_BLOB)
        self.assertFalse(self.plan["proposedVersion"]["implementationExists"])
        self.assertFalse(self.plan["proposedVersion"]["productionRunnerSupportsVersion"])

    def test_three_descriptors_preserve_every_original_physical_fact(self):
        studies=n12.three_studies(self.source_bytes,self.study,self.plan)
        self.assertEqual(set(studies),set(n12.ROLES))
        self.assertEqual(studies["primary"],self.source_bytes)
        self.assertEqual(len(set(map(n12.digest,studies.values()))),3)
        for role,name,intervals,tolerance in n12.EXPECTED_RUNS:
            model=json.loads(studies[role])
            self.assertEqual(model["id"],name)
            self.assertEqual(model["analysis"]["intervals"],intervals)
            self.assertEqual(model["analysis"]["tolerance"],tolerance)
            for item in ("model","requests","provenance","schema","mode"):
                self.assertEqual(model[item],self.study[item])
            self.assertEqual(model["analysis"]["startTime"],0)
            self.assertEqual(model["analysis"]["stopTime"],2400)
            self.assertEqual(model["analysis"]["solver"],"dassl")

    def test_three_distinct_cases_all_pass_original_h1_source_admission(self):
        studies=n12.three_studies(self.source_bytes,self.study,self.plan)
        with TemporaryDirectory() as scratch:
            loaded=n12.admit_cases(studies,self.model,Path(scratch))
            self.assertEqual(set(loaded),set(n12.ROLES))
            for role in n12.ROLES:
                case=loaded[role]
                self.assertEqual(case.sha256,n12.digest(studies[role]))
                self.assertEqual(case.model_sha256,n12.SOURCE_MODEL_SHA)
                self.assertEqual(len(case.request_report["requests"]),8)
                self.assertTrue(all(x["status"]=="not_computed"
                                    for x in case.request_report["requests"]))

    def test_corrupt_three_run_spec_or_attempt_to_promote_n3_refuses(self):
        bad=deepcopy(self.plan)
        bad["runDefinitions"][2]["intervals"]=2400
        with self.assertRaisesRegex(n12.StageRefusal,"three-run definitions"):
            n12.three_studies(self.source_bytes,self.study,bad)
        bad=deepcopy(self.plan)
        bad["proposedVersion"]["productionRunnerSupportsVersion"]=True
        with self.assertRaisesRegex(n12.StageRefusal,"native-blocked"):
            n12.three_studies(self.source_bytes,self.study,bad)
        bad=deepcopy(self.study)
        bad["provenance"][0]["note"]="Changed source"
        with self.assertRaisesRegex(n12.StageRefusal,"original first-authored study"):
            n12.three_studies(n12.canonical(bad)+b"\n",bad,self.plan)

    def test_replaced_original_model_fails_before_any_result_stage(self):
        with TemporaryDirectory() as scratch:
            p=Path(scratch)
            (p/"model.mo").write_bytes(self.model+b"// altered\n")
            (p/"study.json").write_bytes(self.source_bytes)
            with patch.object(n12,"ORIGINAL",p):
                with self.assertRaisesRegex(n12.StageRefusal,
                                            "original author/model/facts identity"):
                    n12.original_snapshots()

    def test_tampered_or_foreign_trace_cannot_enter_stage(self):
        rawtrace=b'{"schema":"not-original"}'
        fake={"report":{"schema":"sim_heat.h1_n1.interval_reference_candidate/1",
                        "gridIntervals":2400,"samples":2401}}
        badproof={"schema":n12.n11.SCHEMA,
                  "nativeExecuted":True,
                  "individualPhysicallyEnclosedSamples":648180}
        with self.assertRaisesRegex(n12.StageRefusal,"original complete N1"):
            n12.stage_packet("primary",self.source_bytes,fake,rawtrace,
                             badproof,n12.digest(n12.canonical(badproof)))
        with self.assertRaisesRegex(n12.StageRefusal,"unknown case role"):
            n12.stage_packet("legacy",self.source_bytes,fake,rawtrace,
                             badproof,"x"*64)

    def test_reject_existing_or_in_repo_output_before_running_any_proof(self):
        with self.assertRaisesRegex(n12.StageRefusal,"outside-repository"):
            n12.prepare(n12.ROOT/"qualification/h1_n12/forbidden")
        with TemporaryDirectory() as scratch:
            with self.assertRaisesRegex(n12.StageRefusal,"NEW outside-repository"):
                n12.prepare(Path(scratch))

    def test_non_authority_n12_schema_not_legacy_or_future_runtime(self):
        self.assertNotEqual(n12.STAGE_SCHEMA,"sim_heat.reference_bundle/2")
        self.assertNotEqual(n12.STAGE_SCHEMA,"sim_heat.h1_n3.reference_bundle/1")
        self.assertNotIn("seal",n12.STAGE_SCHEMA)
        self.assertEqual(tuple(role for role,*_ in n12.EXPECTED_RUNS),
                         n12.ROLES)


if __name__=="__main__":
    import unittest
    unittest.main()
