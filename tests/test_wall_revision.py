import json
from hashlib import sha256
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
from unittest import TestCase

from h1.study import load_study
from qualification.h1_n13.conduction import prepare
from tests.test_composite_wall import CASE, FACTS_PIN


REVISION_PIN = "7b266f98ac5952ddc385e1555b6238fa775ef453c2eac4c899ff2e4a283b9e79"


class WallRevisionTests(TestCase):
    def test_redistribution_through_same_observations(self):
        baseline = prepare(CASE / "study.json", CASE, CASE / "facts.json", FACTS_PIN)
        revised = prepare(CASE / "higher_k.json", CASE, CASE / "higher_k_facts.json", REVISION_PIN)
        self.assertEqual(baseline["requests"].keys(), revised["requests"].keys())
        for name, unit, value in (("interfaceT", "K", 940/3), ("stripRate", "W", 100/3),
                                  ("insertRate", "W", -700/3), ("facingRate", "W", 800/3)):
            self.assertEqual(revised["requests"][name]["unit"], unit)
            actual, = revised["requests"][name]["values"]
            self.assertAlmostEqual(actual, value, delta=1e-8)
        self.assertLess(revised["requests"]["stripRate"]["values"][0],
                        baseline["requests"]["stripRate"]["values"][0])

    def test_refuse_second_conductivity_change_with_fresh_model_pin(self):
        with TemporaryDirectory() as tmp:
            root = copytree(CASE, Path(tmp) / "wall")
            model = root / "higher_k.mo"
            changed = model.read_bytes().replace(b"strip(k=10,", b"strip(k=20,")
            self.assertNotEqual(changed, model.read_bytes())
            model.write_bytes(changed)
            path = root / "higher_k.json"
            study = json.loads(path.read_bytes())
            study["model"]["sha256"] = sha256(changed).hexdigest()
            path.write_text(json.dumps(study), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"expected only insert\.k"):
                load_study(path, root)
