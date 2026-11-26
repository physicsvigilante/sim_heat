"""F-06 regression tests for nested study roots and backslash refusal."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from h1.model import Refusal
from h1.study import checked_path, load_study

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "h1" / "cases"


class H1WindowsNestedPathsTests(unittest.TestCase):
    def test_nested_root_admission_api_and_cli(self):
        study = load_study(CASES / "D1" / "study.json", CASES)
        self.assertEqual(study.data["id"], "H1_D1")
        self.assertTrue(study.request_report["admitted"])

        proc = subprocess.run(
            [sys.executable, "-B", "-m", "h1", "h1/cases/D1/study.json", "--root", "h1/cases"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["admitted"])
        self.assertIs(payload["nativeExecuted"], False)

    def test_nested_revision_chain_admission(self):
        study = load_study(CASES / "D2_K2" / "study.json", CASES)
        self.assertEqual(study.data["id"], "H1_D2_K2")
        self.assertTrue(study.request_report["admitted"])
        self.assertEqual(study.data["revision"]["parentStudyPath"], "../D2/study.json")

    def test_top_of_root_study_non_regression_control(self):
        study = load_study(CASES / "D1" / "study.json", CASES / "D1")
        self.assertEqual(study.data["id"], "H1_D1")
        self.assertTrue(study.request_report["admitted"])

    def test_authored_backslash_paths_remain_refused(self):
        with self.assertRaises(Refusal) as ctx:
            checked_path(CASES, "D1\\study.json", CASES, ".json")
        self.assertEqual(ctx.exception.code, "path")
        self.assertIn("portable relative path required", str(ctx.exception))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(strict=True)
            shutil.copytree(CASES / "D2", root / "D2")
            shutil.copytree(CASES / "D2_K2", root / "D2_K2")

            # 1) Backslash in authored model.path must still be refused (both top-of-root and nested).
            d2_study = root / "D2" / "study.json"
            data = json.loads(d2_study.read_text(encoding="utf-8"))
            bad_model = dict(data, model={**data["model"], "path": ".\\model.mo"})
            d2_study.write_text(json.dumps(bad_model, indent=2) + "\n", encoding="utf-8")
            for study_root in (root / "D2", root):
                with self.assertRaises(Refusal) as ctx_model:
                    load_study(d2_study, study_root)
                self.assertEqual(ctx_model.exception.code, "path")
                self.assertIn("portable relative path required", str(ctx_model.exception))

            # Restore valid D2 study and inject backslash in D2_K2 revision.parentStudyPath.
            d2_study.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            k2_study = root / "D2_K2" / "study.json"
            k2_data = json.loads(k2_study.read_text(encoding="utf-8"))
            bad_rev = dict(k2_data, revision={**k2_data["revision"], "parentStudyPath": "..\\D2\\study.json"})
            k2_study.write_text(json.dumps(bad_rev, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(Refusal) as ctx_rev:
                load_study(k2_study, root)
            self.assertEqual(ctx_rev.exception.code, "path")
            self.assertIn("portable relative path required", str(ctx_rev.exception))


if __name__ == "__main__":
    unittest.main()
