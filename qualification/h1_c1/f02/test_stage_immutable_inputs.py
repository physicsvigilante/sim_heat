"""Negative tests for F02 immutable INPUT snapshot. No Modelica/OMC runs."""
import json
from pathlib import Path
import tempfile
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

    def test_duplicate_stage_manifest_keys_refuse(self):
        self.make()
        path=self.path/staging.MANIFEST_FILE
        raw=path.read_text()
        for key,old in (
            ("nativeAllowed", '"nativeAllowed": false'),
            ("nativeExecuted", '"nativeExecuted": false'),
            ("ownerNativeLaunchApproved", '"ownerNativeLaunchApproved": false'),
            ("status", '"status": "STAGED_FOR_OFFLINE_INSPECTION_ONLY"'),
        ):
            with self.subTest(key=key):
                self.assertEqual(raw.count(old),1)
                injected=old.replace(": ", ': true, "'+key+'": ',1) if key!="status" else (
                    '"status": "NATIVE_RUNNING", '+old)
                path.write_text(raw.replace(old,injected,1))
                with self.assertRaisesRegex(staging.StageRefusal,"duplicate JSON metadata key"):
                    staging.verify(label=self.label)
                path.write_text(raw)

    def test_duplicate_state_keys_refuse(self):
        self.make()
        path=self.path/staging.STATE_FILE
        raw=path.read_text()
        for key,old in (
            ("nativeAllowed", '"nativeAllowed": false'),
            ("nativeExecuted", '"nativeExecuted": false'),
            ("status", '"status": "STAGED_NOT_EXECUTED"'),
        ):
            with self.subTest(key=key):
                self.assertEqual(raw.count(old),1)
                injected=old.replace(": ", ': true, "'+key+'": ',1) if key!="status" else (
                    '"status": "RUNNING_NATIVE", '+old)
                path.write_text(raw.replace(old,injected,1))
                with self.assertRaisesRegex(staging.StageRefusal,"duplicate JSON metadata key"):
                    staging.verify(label=self.label)
                path.write_text(raw)

    def test_nested_duplicate_and_nonfinite_json_refuse(self):
        self.make()
        path=self.path/staging.MANIFEST_FILE
        raw=path.read_text()
        needle='"model.mo": "'+staging.SOURCE_FILES["model.mo"][1]+'"'
        self.assertEqual(raw.count(needle),2)
        # One instance inside sourceFilesSha256 and one in stagedFilesSha256.
        path.write_text(raw.replace(needle,needle+', '+needle,1))
        with self.assertRaisesRegex(staging.StageRefusal,"duplicate JSON metadata key"):
            staging.verify(label=self.label)
        path.write_text(raw.replace('"sourcePinCount": 23',
                                    '"sourcePinCount": NaN',1))
        with self.assertRaisesRegex(staging.StageRefusal,"nonstandard JSON constant"):
            staging.verify(label=self.label)

    def test_staged_metadata_rejects_bool_numeric_zero_and_float_source_count(self):
        self.make()
        state=self.path/staging.STATE_FILE
        original=state.read_bytes()
        altered=json.loads(original)
        altered["nativeAllowed"]=0
        state.write_text(json.dumps(altered))
        with self.assertRaisesRegex(staging.StageRefusal,"incomplete/untrusted"):
            staging.verify(label=self.label)
        state.write_bytes(original)
        path=self.path/staging.MANIFEST_FILE
        original=path.read_bytes()
        for value in (23.0, True):
            with self.subTest(value=repr(value)):
                doc=json.loads(original)
                doc["sourcePinCount"]=value
                path.write_text(json.dumps(doc))
                with self.assertRaisesRegex(staging.StageRefusal,"JSON integer"):
                    staging.verify(label=self.label)
        path.write_bytes(original)

    def test_renamed_stage_refuses_even_when_all_data_bytes_match(self):
        self.make()
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            parent=root/staging.STAGE_PARENT
            parent.mkdir()
            shutil.copytree(self.path,parent/"new-label")
            with self.assertRaisesRegex(staging.StageRefusal,"attempt label mismatch"):
                staging.verify(root=root,label="new-label")

    def test_symlinked_staging_parent_is_refused(self):
        self.make()
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/staging.STAGE_PARENT).symlink_to(self.path.parent,
                                                    target_is_directory=True)
            with self.assertRaisesRegex(staging.StageRefusal,"parent missing or symlink"):
                staging.verify(root=root,label=self.label)

    def test_post_stage_coordinated_preview_and_manifest_drift_refuses(self):
        self.make()
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            plan=root/staging.f02.PLAN
            plan.parent.mkdir(parents=True,exist_ok=True)
            original=(staging.ROOT/staging.f02.PLAN).read_bytes()
            changed=original+b"\\n"
            plan.write_bytes(changed)
            parent=root/staging.STAGE_PARENT
            parent.mkdir()
            new_stage=parent/self.label
            shutil.copytree(self.path,new_stage)
            manifest=new_stage/staging.MANIFEST_FILE
            changed_doc=json.loads(manifest.read_text())
            changed_doc["disabledPreviewSha256"]=staging.sha(changed)
            manifest.write_text(json.dumps(changed_doc))
            with self.assertRaisesRegex(staging.f02.PreviewRefusal,"original pinned"):
                staging.verify(root=root,label=self.label)

    def test_standalone_preview_pin_is_independent_of_parser_result(self):
        preview,original_sha=staging.f02.load_preview()
        self.assertEqual(staging.pinned_disabled_preview(staging.ROOT),original_sha)
        with mock.patch.object(staging.f02,"load_preview",return_value=(preview,"f"*64)):
            with self.assertRaisesRegex(staging.StageRefusal,"independently pinned"):
                staging.verify(label=self.label) if self.path.exists() else (
                    staging.pinned_disabled_preview(staging.ROOT))

    def test_verify_before_staging_fails(self):
        with self.assertRaisesRegex(staging.StageRefusal,"stage directory missing"):
            staging.verify(label=self.label)


if __name__=="__main__":
    unittest.main()
