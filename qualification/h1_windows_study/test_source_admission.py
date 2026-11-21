"""Offline checks for the source identities recorded in OFFLINE-RECORD.md."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from unittest import TestCase

from h1.model import internal_exports
from h1.reference import read_reference
from h1.study import load_study
from h1.verification import bind_reference
from qualification.h1_n1.check_plan import check


ROOT = Path(__file__).resolve().parents[2]
N1 = ROOT / "qualification/h1_n1"
PARENT = "6904ec8219be0ddb8ec1635a9d000ddda80307c9"
MANIFEST_SHA = "28e249bbda68fba3a511caede4dfdec8cd5254e3a02b5eda5025bba82dbb6766"
WINDOWS_LOADER_SHA = "04b5bea4fe93396d74912e102f59977201c500d8672de05ed4e78ce77fa6817f"


class SourceAdmissionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (N1 / "SOURCE-PINS.json").read_bytes()
        if sha256(raw).hexdigest() != MANIFEST_SHA:
            raise AssertionError("historical N1 manifest changed")
        cls.pins = json.loads(raw)

    def test_parent_and_candidate_source_bytes(self):
        for group in ("readonlySha256", "inputSha256"):
            for name, expected in self.pins[group].items():
                with self.subTest(path=name):
                    original = subprocess.check_output(
                        ["git", "cat-file", "blob", f"{PARENT}:{name}"], cwd=ROOT
                    )
                    self.assertEqual(sha256(original).hexdigest(), expected)
                    current = (ROOT / name).read_bytes()
                    candidate_pin = WINDOWS_LOADER_SHA if name == "h1/study.py" else expected
                    self.assertEqual(sha256(current).hexdigest(), candidate_pin)

    def test_original_study_admitted_with_uncomputed_requests(self):
        study = load_study(N1 / "inputs/T/study.json", N1 / "inputs")
        bind_reference(study, read_reference(N1 / "reference-facts.json"))
        pins = self.pins["inputSha256"]
        self.assertEqual(study.model_sha256, pins["qualification/h1_n1/inputs/T/model.mo"])
        self.assertEqual(study.sha256, pins["qualification/h1_n1/inputs/T/study.json"])
        self.assertEqual(len(list(internal_exports(study.model))), 77)
        self.assertTrue(study.request_report["admitted"])
        requests = study.request_report["requests"]
        self.assertEqual(len(requests), 8)
        self.assertEqual({request["status"] for request in requests}, {"not_computed"})

    def test_historical_checker_refuses_changed_loader(self):
        with self.assertRaises(ValueError) as caught:
            check()
        self.assertEqual(str(caught.exception), "source drift: h1/study.py")
