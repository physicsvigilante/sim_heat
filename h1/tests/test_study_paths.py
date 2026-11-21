"""Portable study paths through the public offline loader."""
import json
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
from unittest import TestCase

from h1.model import Refusal
from h1.study import load_study


class StudyPathTests(TestCase):
    def test_nested_revision_and_authored_separators(self):
        cases = Path(__file__).resolve().parents[1] / "cases"
        with TemporaryDirectory() as scratch:
            root = Path(scratch) / "cases"
            root.mkdir()
            for name in ("D2", "D2_K2"):
                copytree(cases / name, root / name)
            path = root / "D2_K2/study.json"
            original = path.read_bytes()
            self.assertEqual(load_study(path, root).path, path.resolve())
            # An equivalent root spelling also occurs with Windows 8.3 temp paths.
            (Path(scratch) / "sibling").mkdir()
            alias_root = Path(scratch) / "sibling" / ".." / "cases"
            alias_path = alias_root / "D2_K2/study.json"
            self.assertEqual(load_study(alias_path, alias_root).path, path.resolve())
            for section, key, value in (
                ("model", "path", r".\model.mo"),
                ("revision", "parentStudyPath", r"..\D2\study.json"),
            ):
                with self.subTest(field=key):
                    descriptor = json.loads(original)
                    descriptor[section][key] = value
                    path.write_bytes(json.dumps(descriptor).encode("utf-8"))
                    with self.assertRaisesRegex(Refusal, "portable relative path required"):
                        load_study(path, root)
