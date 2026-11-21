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

    def incomplete_proof(self):
        return dict(schema=n12.n11.SCHEMA, sourceFactsSha256=n12.SOURCE_FACTS_SHA,
                     originalModelSha256=n12.SOURCE_MODEL_SHA, originalStudySha256=n12.SOURCE_STUDY_SHA,
                     individualPhysicallyEnclosedSamples=648180, sourceMathematicalEnclosureSelfChecked=True,
                     nativeExecuted=False, nativeQualified=False, referenceAccuracyCertified=False,
                     referenceBundleWritten=False)

    def test_caller_cannot_stage_divergent_data_with_authentic_trace(self):
        # F-01 combined a real blob, altered data, a self-hashed proof and
        # the wrong study role to emit the normal source-verified schema.
        with TemporaryDirectory() as scratch:
            target = Path(scratch) / "trace"
            n1.certify(n1.read_facts(), 2400, output=target)
            blob = (target / "N1_T1T_reference_grid2400.json").read_bytes()
            self.assertEqual(n12.digest(blob), n12.ORIGINAL_GRID_HASHES[2400])
            trace = json.loads(blob)
            trace["columns"]["T06.Q_flow"][0] = 987654321.0
            trace["units"]["T06.Q_flow"] = "J"
            trace["requests"]["t_collar_to_plug"][0] = -987654321.0
            trace["integrals"]["T_Collar.Q_in"][0] = 123.0
            proof = self.incomplete_proof()
            proof_sha = n12.digest(n12.canonical(proof))
            with self.assertRaises((AttributeError, n12.StageRefusal)):
                n12.stage_packet("tight", self.source_bytes, trace, blob, proof, proof_sha)
            with self.assertRaisesRegex(n12.StageRefusal, "original complete N1"):
                n12._read_original_trace(n12.canonical(trace), 2400)
            out = Path(scratch) / "stage"
            with self.assertRaises(TypeError):
                n12.prepare(out, role="tight", study=self.source_bytes,
                            trace=trace, trace_blob=blob, proof=proof, proof_sha=proof_sha)
            self.assertFalse(out.exists())

    def test_incomplete_or_promoted_audit_refused_before_output(self):
        proof = self.incomplete_proof()
        grids = [dict(intervals=n, originalN1TraceSha256=h)
                 for n, h in n12.ORIGINAL_GRID_HASHES.items()]
        for change in ({}, {"grids": []}, {"grids": grids, "nativeQualified": True},
                       {"grids": grids, "schema": "sim_heat.reference_bundle/2"}):
            with self.subTest(change=change), TemporaryDirectory() as scratch:
                out = Path(scratch) / "stage"
                with patch.object(n12.n11, "audit", return_value={**proof, **change}) as audit:
                    with self.assertRaisesRegex(n12.StageRefusal, "reviewed N11"):
                        n12.prepare(out)
                    audit.assert_called_once_with()
                self.assertFalse(out.exists())

    def test_case_admission_binds_study_bytes_to_role(self):
        studies = n12.three_studies(self.source_bytes, self.study, self.plan)
        for field in ("role", "model", "provenance"):
            with self.subTest(field=field), TemporaryDirectory() as scratch:
                tight = json.loads(studies["tight"])
                if field == "role":
                    bad = studies["primary"]
                else:
                    tight[field] = {}
                    bad = n12.canonical(tight)
                with self.assertRaisesRegex(n12.StageRefusal, "study identity differs for tight"):
                    n12.admit_cases({**studies, "tight": bad}, self.model, Path(scratch))

    def test_original_changed_during_preparation_refused_before_first_write(self):
        with TemporaryDirectory() as scratch:
            original = Path(scratch) / "original"
            original.mkdir()
            (original / "model.mo").write_bytes(self.model)
            (original / "study.json").write_bytes(self.source_bytes)
            out = Path(scratch) / "stage"

            def change_original(root, facts):
                (original / "model.mo").write_bytes(self.model + b"// changed")
                trace = dict(grid=[], columns={}, units={}, requests={}, integrals={})
                return {2400: trace, 4800: trace}

            with (patch.object(n12, "ORIGINAL", original),
                  patch.object(n12, "_audited_proof_sha", return_value="unused"),
                  patch.object(n12, "_verified_traces", side_effect=change_original)):
                with self.assertRaisesRegex(n12.StageRefusal, "original author/model/facts identity"):
                    n12.prepare(out)
            self.assertFalse(out.exists())

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
