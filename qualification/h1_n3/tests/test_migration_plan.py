"""Synthetic read-only refusals for an entirely non-executable migration design."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from qualification.h1_n3 import check_migration_plan as n3

class MigrationPlanSafety(unittest.TestCase):
    def test_design_verified_but_native_stays_blocked(self):
        r=n3.check()
        self.assertEqual(r["status"],"DESIGN_VERIFIED_NATIVE_BLOCKED")
        self.assertTrue(r["sourcePinsVerified"])
        self.assertTrue(r["legacyRunnerStillUsesOldPrepare"])
        self.assertEqual(len(r["oldStaticRefusals"]),7)
        self.assertEqual(len(r["nativeExecutionBlockers"]),8)
        self.assertEqual(r["nativeCalls"],0)
        for field in ("versionedReferenceImplemented","referenceAccuracyCertified",
                      "independentlyCertifiedReference","referenceMigrated",
                      "runtimeReady","nativeExecuted","nativeQualified",
                      "ownerNativePermission"):
            self.assertIs(r[field],False,field)
        self.assertEqual(r["sourceOnlyTraceHashesRecordedNotRecomputed"],n3.TRACES)

    def test_forged_authority_seals_checker_implementation_and_scope_refuse(self):
        edits={
          "install":lambda p:p["authorities"].__setitem__("nativeInstallApproved",True),
          "query":lambda p:p["authorities"].__setitem__("nativeVersionQueryApproved",True),
          "launch":lambda p:p["authorities"].__setitem__("nativeLaunchApproved",True),
          "merge":lambda p:p["authorities"].__setitem__("productionMergeApproved",True),
          "deploy":lambda p:p["authorities"].__setitem__("deployApproved",True),
          "host":lambda p:p["trustBoundary"].__setitem__("hostBinaryAndMslAttested",True),
          "external_seal":lambda p:p["trustBoundary"].__setitem__("expectedSealExternallyPinnedBeforeNativeOutput",True),
          "self_seal":lambda p:p["trustBoundary"].__setitem__("callerProvidedBundleSealIsAuthentic",True),
          "checker":lambda p:p["proposedVersion"].__setitem__("implementationExists",True),
          "runner_dispatch":lambda p:p["proposedVersion"].__setitem__("productionRunnerSupportsVersion",True),
          "legacy_fallback":lambda p:p["proposedVersion"].__setitem__("fallbackToOldCheckingCentresPermitted",True),
          "edit_old":lambda p:p["proposedVersion"].__setitem__("directOldBundleEditingPermitted",True),
          "ref_digest":lambda p:p["runDefinitions"][0].__setitem__("futureReferenceSha256","0"*64),
          "seal_digest":lambda p:p["runDefinitions"][1].__setitem__("externallySealedDigest","0"*64),
          "wrong_case":lambda p:p["runDefinitions"][2].__setitem__("studyId","made-up"),
          "less_dense":lambda p:p["runDefinitions"][2].__setitem__("intervals",2400),
          "false_native":lambda p:p["designFlags"].__setitem__("nativeQualified",True),
          "native_call":lambda p:p["designFlags"].__setitem__("nativeCallsPerformed",1),
          "drop_static":lambda p:p["legacyRefusals"]["staticPhysical100xFailNames"].pop(),
          "drop_blocker":lambda p:p["legacyRefusals"]["originalNativeExecutionBlockers"].pop(),
          "trace":lambda p:p["originalEvidence"]["fullGridTraceSha256"].__setitem__("primary","f"*64),
          "fake_certificate":lambda p:p["originalEvidence"].__setitem__("independentCompleteNumericalCertificate",True),
          "source_pin":lambda p:p["immutableSourceGitBlobs"].__setitem__("h1/reference.py","f"*40),
          "source_fact":lambda p:p["lineage"].__setitem__("originalStudySha256","f"*64),
          "extra":lambda p:p.__setitem__("nativeApproved",True),
          "bool_int_spoof":lambda p:p["designFlags"].__setitem__("nativeCallsPerformed",False),
        }
        for name,mutate in edits.items():
            with self.subTest(attack=name):
                p=deepcopy(n3.read_plan())
                mutate(p)
                with self.assertRaisesRegex(n3.DesignRefusal,"unreviewed in-memory plan"):
                    n3.audit(p)

    def test_plan_byte_mutation_and_duplicate_or_nonfinite_json_refuse(self):
        raw=n3.PLAN_PATH.read_bytes()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"plan.json"
            for value in (raw+b" ",b'{"a":1,"a":2}',b'{"status":NaN}'):
                path.write_bytes(value)
                with patch.object(n3,"PLAN_PATH",path):
                    with self.assertRaises(n3.DesignRefusal):
                        n3.read_plan()
            path.write_bytes(raw)
            with patch.object(n3,"PLAN_PATH",path):
                self.assertEqual(n3.read_plan(),n3.read_plan())
        with self.assertRaisesRegex(n3.DesignRefusal,"duplicate"):
            n3.strict_json(b'{"a":1,"a":2}')
        with self.assertRaisesRegex(n3.DesignRefusal,"nonfinite"):
            n3.strict_json(b'{"a":Infinity}')

    def test_pinned_original_and_legacy_source_drift_refuse(self):
        original_read=Path.read_bytes
        for item,message in (("qualification/h1_n1/inputs/T/model.mo","modified original source"),
                             ("h1/reference.py","modified pinned source")):
            target=n3.ROOT/item
            def fake(path):
                raw=original_read(path)
                return raw+b"changed" if path==target else raw
            with self.subTest(path=item), patch.object(Path,"read_bytes",fake):
                with self.assertRaisesRegex(n3.DesignRefusal,message):
                    n3.audit(n3.read_plan())

    def test_runner_is_ast_inspected_not_launched(self):
        src=(n3.ROOT/"tools/h1_native_batch.py").read_bytes()
        self.assertTrue(n3.runner_still_old(src))
        self.assertFalse(n3.runner_still_old(b"def prepare(root):\n    return None\n"))
        with self.assertRaises(n3.DesignRefusal):
            n3.runner_still_old(b"not Python !")
        code=(n3.ROOT/"qualification/h1_n3/check_migration_plan.py").read_text()
        self.assertNotIn("import h1_native_batch",code)
        self.assertNotIn("subprocess.run(",code)
        self.assertNotIn("subprocess.Popen(",code)

    def test_outside_repo_scratch_receipt_is_nonoverwriting(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"receipt.json"
            report=n3.check(p)
            self.assertEqual(report,json.loads(p.read_text()))
            self.assertFalse(report["nativeExecuted"])
            with self.assertRaisesRegex(n3.DesignRefusal,"outside-repo"):
                n3.check(p)
        with self.assertRaisesRegex(n3.DesignRefusal,"outside-repo"):
            n3.check(n3.ROOT/"qualification/h1_n3/NOT_NATIVE.json")

    def test_no_unavailable_host_reference_or_new_checkers_are_claimed(self):
        p=n3.read_plan()
        self.assertFalse(p["originalEvidence"]["nativeEvidence"])
        self.assertEqual(p["originalEvidence"]["fullGridTraceSha256"],n3.TRACES)
        self.assertEqual([r["name"] for r in p["runDefinitions"]],["primary","tight","dense"])
        self.assertTrue(all(r["externallySealedDigest"] is None for r in p["runDefinitions"]))
        self.assertTrue(all(r["futureReferenceSha256"] is None for r in p["runDefinitions"]))
        self.assertFalse(p["proposedVersion"]["implementationExists"])
        self.assertFalse(p["proposedVersion"]["productionRunnerSupportsVersion"])
        self.assertEqual(len(p["requiredFutureSequence"]),10)

if __name__=="__main__":
    unittest.main()
