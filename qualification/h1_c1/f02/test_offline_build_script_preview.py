"""Offline tests for nonexecuting Modelica build-text preview. No OMC."""
import json
from pathlib import Path
import shutil
import unittest
from unittest import mock
import uuid

from h1 import reference
from tools import h1_native_batch
from qualification.h1_c1.f02 import stage_immutable_inputs as stage
from qualification.h1_c1.f02 import offline_build_script_preview as preview


class OfflineBuildTextPreviewTests(unittest.TestCase):
    def setUp(self):
        self.label="preview-"+uuid.uuid4().hex[:20]
        self.stage_path=preview.ROOT/stage.STAGE_PARENT/self.label
        self.path=preview.ROOT/preview.OUT/self.label
        stage.stage(label=self.label)

    def tearDown(self):
        for p in (self.path,self.stage_path):
            if p.exists() and not p.is_symlink():
                shutil.rmtree(p)

    def make(self):
        result=preview.prepare(label=self.label)
        self.assertEqual(result["status"],"NONEXECUTABLE_BUILD_TEXT_PREVIEW_VERIFIED")
        return result

    def test_exact_script_text_and_input_reference_identity(self):
        receipt=self.make()
        text=(self.path/preview.SCRIPT).read_text()
        self.assertIn('loadModel(Modelica, {"4.0.0"})',text)
        self.assertEqual(text.count("buildModel("),1)
        self.assertIn("numberOfIntervals=4000",text)
        self.assertIn('outputFormat="mat"',text)
        self.assertIn('variableFilter=".*"',text)
        self.assertIn("method=\"dassl\"",text)
        self.assertEqual({x.name for x in self.path.iterdir()},
                         {preview.SCRIPT,preview.MANIFEST})
        self.assertEqual(receipt,preview.verify(label=self.label))
        self.assertEqual(receipt["referenceRawSha256"],preview.REF_SHA)
        self.assertEqual(receipt["referenceSeal"],preview.REF_SEAL)
        for k in ("nativeAllowed","omcVersionQueried","buildInvoked",
                  "modelLaunched","nativeExecuted","nativeQualified",
                  "ownerNativeLaunchApproved","oneShotReservationAllocated",
                  "referenceRegenerated","releaseTrustRootComplete"):
            self.assertIs(receipt[k],False,k)

    def test_no_compiler_or_reference_generator_invocation(self):
        with mock.patch.object(reference,"prepare",side_effect=AssertionError("regeneration forbidden")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError("native prepare forbidden")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError("native execute forbidden")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError("subprocess forbidden")):
            self.make()

    def test_repeated_label_refused_no_overwrite(self):
        self.make()
        with self.assertRaisesRegex(preview.PreviewRefusal,"refuse overwrite"):
            preview.prepare(label=self.label)

    def test_modified_build_text_refused(self):
        self.make()
        p=self.path/preview.SCRIPT
        p.write_bytes(p.read_bytes()+b"system(\"omc\");\n")
        with self.assertRaisesRegex(preview.PreviewRefusal,"build text/manifest differs"):
            preview.verify(label=self.label)

    def test_modified_manifest_approval_refused(self):
        self.make()
        p=self.path/preview.MANIFEST
        doc=json.loads(p.read_text())
        doc["nativeAllowed"]=True
        p.write_text(json.dumps(doc))
        with self.assertRaisesRegex(preview.PreviewRefusal,"build text/manifest differs"):
            preview.verify(label=self.label)

    def test_duplicate_json_key_refused(self):
        self.make()
        p=self.path/preview.MANIFEST
        raw=p.read_text()
        self.assertEqual(raw.count('"nativeAllowed": false'),1)
        p.write_text(raw.replace('"nativeAllowed": false',
               '"nativeAllowed": true, "nativeAllowed": false',1))
        with self.assertRaisesRegex(stage.StageRefusal,"duplicate JSON metadata key"):
            preview.verify(label=self.label)

    def test_extra_executable_or_native_script_refused(self):
        self.make()
        (self.path/"build.mos").write_bytes(b"fake")
        with self.assertRaisesRegex(preview.PreviewRefusal,"unexpected build-preview"):
            preview.verify(label=self.label)

    def test_modified_stage_byte_refused(self):
        self.make()
        p=self.stage_path/"model.mo"
        p.write_bytes(p.read_bytes()+b"\n")
        with self.assertRaises(stage.StageRefusal):
            preview.verify(label=self.label)

    def test_changed_stage_label_refused(self):
        self.make()
        p=self.path/preview.MANIFEST
        doc=json.loads(p.read_text())
        doc["stageLabel"]="different-label"
        p.write_text(json.dumps(doc))
        with self.assertRaisesRegex(preview.PreviewRefusal,"build text/manifest differs"):
            preview.verify(label=self.label)

    def test_missing_file_refused(self):
        self.make()
        (self.path/preview.SCRIPT).unlink()
        with self.assertRaisesRegex(preview.PreviewRefusal,"incomplete or unexpected"):
            preview.verify(label=self.label)

    def test_invalid_labels_refused(self):
        for label in ("/tmp/x","../bad","A","bad/path","a_b","",None):
            with self.subTest(label=label):
                with self.assertRaises(preview.PreviewRefusal):
                    preview.verify(label=label)

    def test_no_execute_or_build_cli(self):
        for action in ("execute","compile","build","launch","native","approve","run"):
            with self.subTest(action=action), mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ex:
                    preview.main([action,"--label",self.label])
                self.assertEqual(ex.exception.code,2)


if __name__=="__main__":
    unittest.main()
