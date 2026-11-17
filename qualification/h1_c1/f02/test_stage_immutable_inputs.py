"""Negative tests for F02 immutable INPUT snapshot. No Modelica/OMC runs."""
import json
from pathlib import Path
import shutil
import unittest
from unittest import mock
import uuid

from h1 import reference
from qualification.h1_c1.f02 import stage_immutable_inputs as staging


class F02OfflineStagingTests(unittest.TestCase):
    def setUp(self):
        self.label = "test-" + uuid.uuid4().hex[:20]
        self.path = staging.ROOT/staging.STAGE_PARENT/self.label

    def tearDown(self):
        if self.path.exists() and not self.path.is_symlink():
            shutil.rmtree(self.path)

    def make(self):
        result=staging.stage(label=self.label)
        self.assertEqual(result["status"],"OFFLINE_STAGED_EXACT_INPUTS_NOT_NATIVE")
        return result

    def test_stages_exact_original_bytes_and_verified_saved_reference(self):
        receipt=self.make()
        self.assertEqual(receipt["fileCount"],4)
        self.assertEqual(receipt["referenceRawSha256"],staging.captured.V2_RAW_SHA)
        self.assertEqual(receipt["referenceSeal"],staging.captured.V2_SEAL)
        self.assertEqual({p.name for p in self.path.iterdir()},staging.ALLOWED_FILES)
        for name,(source,sha) in staging.SOURCE_FILES.items():
            self.assertEqual((self.path/name).read_bytes(),(staging.ROOT/source).read_bytes())
            self.assertEqual(staging.sha((self.path/name).read_bytes()),sha)
        self.assertEqual(staging.sha((self.path/staging.REFERENCE_FILE).read_bytes()),
                         staging.captured.V2_RAW_SHA)
        self.assertEqual(staging.verify(label=self.label),receipt)
        for name in ("model","model_res.mat","build.mos","run.sh","model.exe"):
            self.assertFalse((self.path/name).exists())
        for key in ("nativeAllowed","nativeExecuted","nativePlanCreated",
                    "ownerNativeLaunchApproved","oneShotReservationAllocated",
                    "referenceRegenerated","originalF0Static100xPassed",
                    "pr32CrossHostBitwiseRegenerationPassed"):
            self.assertIs(receipt[key],False,key)

    def test_numerical_reference_preparation_never_called(self):
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
                "forbidden regenerated scientific reference")):
            self.make()

    def test_refuses_repeated_label_without_overwrite(self):
        self.make()
        with self.assertRaisesRegex(staging.StageRefusal,"never overwrite"):
            staging.stage(label=self.label)

    def test_bad_labels_refused(self):
        for label in ("../x","/tmp/elsewhere","other/path","","A",
                      "a_b","a"*33,"x/../y",None):
            with self.subTest(label=label):
                with self.assertRaises(staging.StageRefusal):
                    staging.stage(label=label)

    def test_changed_staged_model_refused(self):
        self.make()
        path=self.path/"model.mo"
        path.write_bytes(path.read_bytes()+b"\n")
        with self.assertRaisesRegex(staging.StageRefusal,"staged bytes changed"):
            staging.verify(label=self.label)

    def test_changed_staged_reference_bytes_refused(self):
        self.make()
        path=self.path/staging.REFERENCE_FILE
        raw=path.read_bytes()
        path.write_bytes(raw[:-1])
        with self.assertRaisesRegex(staging.StageRefusal,"staged bytes changed"):
            staging.verify(label=self.label)

    def test_extra_native_executable_or_build_script_refused(self):
        self.make()
        with (self.path/"build.mos").open("xb") as f:
            f.write(b"fake")
        with self.assertRaisesRegex(staging.StageRefusal,"incomplete, extra or symlink"):
            staging.verify(label=self.label)

    def test_stage_incomplete_or_relabelled_running_refused(self):
        self.make()
        target=self.path/staging.STATE_FILE
        state=json.loads(target.read_text())
        state["status"]="RUNNING_NATIVE"
        target.write_text(json.dumps(state))
        with self.assertRaisesRegex(staging.StageRefusal,"incomplete/untrusted stage state"):
            staging.verify(label=self.label)

    def test_forged_native_permission_in_manifest_refused(self):
        self.make()
        target=self.path/staging.MANIFEST_FILE
        doc=json.loads(target.read_text())
        doc["nativeAllowed"]=True
        target.write_text(json.dumps(doc))
        with self.assertRaisesRegex(staging.StageRefusal,"forbidden execution"):
            staging.verify(label=self.label)

    def test_forged_unknown_command_in_manifest_refused(self):
        self.make()
        path=self.path/staging.MANIFEST_FILE
        doc=json.loads(path.read_text())
        doc["command"]="omc build.mos"
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(staging.StageRefusal,"unexpected field"):
            staging.verify(label=self.label)

    def test_changed_history_limits_refused(self):
        self.make()
        path=self.path/staging.MANIFEST_FILE
        doc=json.loads(path.read_text())
        doc["limitations"]=[]
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(staging.StageRefusal,"limitation"):
            staging.verify(label=self.label)

    def test_missing_stage_member_refused(self):
        self.make()
        (self.path/"study.json").unlink()
        with self.assertRaisesRegex(staging.StageRefusal,"incomplete, extra or symlink"):
            staging.verify(label=self.label)

    def test_refuse_when_non_executable_design_source_changed(self):
        with mock.patch.object(staging.f02,"audit",
              side_effect=staging.StageRefusal("disabled source/plan pin mismatch")):
            with self.assertRaises(staging.StageRefusal):
                staging.stage(label=self.label)
        self.assertFalse(self.path.exists())

    def test_refuse_when_owner_offline_consumer_missing(self):
        with mock.patch.object(staging.adopted,"load_for_offline_checking",
              side_effect=staging.StageRefusal("offline owner approved reference absent")):
            with self.assertRaises(staging.StageRefusal):
                staging.stage(label=self.label)
        self.assertFalse(self.path.exists())

    def test_refuse_new_native_commands_in_cli(self):
        with mock.patch("sys.stderr"):
            for command in ("build","execute","run","launch","native","approve","reserve"):
                with self.subTest(command=command),self.assertRaises(SystemExit) as x:
                    staging.main([command,"--label",self.label])
                self.assertEqual(x.exception.code,2)

    def test_verify_before_staging_fails(self):
        with self.assertRaisesRegex(staging.StageRefusal,"stage directory missing"):
            staging.verify(label=self.label)


if __name__=="__main__":
    unittest.main()
