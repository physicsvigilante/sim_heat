import json
import math
from hashlib import sha256
from tempfile import TemporaryDirectory
from fractions import Fraction
from pathlib import Path
from unittest import TestCase

from tools.temperature_passages import brackets, investigate

ROOT = Path(__file__).resolve().parents[1]
D1 = ROOT / "h1/cases/D1"
D1_PIN = "92c913bd9a59fee7af14170f459f0959deee8da7d6876e4be222d3c3e94b71c7"
TWIN = ROOT / "qualification/h1_n13/heldout"
TWIN_PIN = "57c393f2b11bf658a378b6fa6ab96425b14116b8c2fc519e4bedba1e883d1783"


class PassageTests(TestCase):
    def test_single_body_halfway_to_reservoir(self):
        r = investigate(D1/"study.json", D1, ROOT/"h1/reference_cases/D1.json",
                        D1_PIN, "body", "323.15")
        event, = r["passages"]
        self.assertEqual(event["direction"], "warming")
        lo, hi = map(Fraction, event["timeBoundsSeconds"])
        self.assertLess(lo, 2500 * math.log(2))
        self.assertGreater(hi, 2500 * math.log(2))
        self.assertEqual(hi-lo, Fraction(25, 2))

    def test_composed_body_warms_then_cools_through_same_temperature(self):
        r = investigate(TWIN/"study.json", TWIN, TWIN/"facts.json", TWIN_PIN, "blue", "307")
        self.assertEqual(r["status"], "bracketed")
        self.assertEqual([e["sampleIndices"] for e in r["passages"]], [[369, 370], [943, 944]])
        for event, direction in zip(r["passages"], ("warming", "cooling")):
            self.assertEqual(event["direction"], direction)
            lo, hi = map(Fraction, event["timeBoundsSeconds"])
            sign = 1 if direction == "warming" else -1
            for time, expected in ((lo, -sign), (hi, sign)):
                blue = 305 + 10*math.exp(-time/60) - 40*math.exp(-time/15)
                self.assertGreater(expected*(blue-307), 0)

    def test_inconclusive_samples_cannot_establish_a_side(self):
        step = Fraction(1, 3)
        self.assertEqual(brackets([299, 300, 301], 1, 300, step), ([], 3))
        events, overlaps = brackets([298, 299, 301, 302], 1, 300, step)
        self.assertEqual(overlaps, 2)
        self.assertEqual(events, [{"direction": "warming", "sampleIndices": [0, 3],
                                   "timeBoundsSeconds": ["0", "1"]}])

    def test_single_body_cooling_into_colder_bath(self):
        with TemporaryDirectory() as scratch:
            root = Path(scratch)
            model = (D1/"model.mo").read_bytes().replace(b"T=353.15", b"T=233.15")
            (root/"model.mo").write_bytes(model)
            study = json.loads((D1/"study.json").read_bytes())
            study["model"]["sha256"] = sha256(model).hexdigest()
            descriptor = json.dumps(study).encode()
            (root/"study.json").write_bytes(descriptor)
            facts = json.loads((ROOT/"h1/reference_cases/D1.json").read_bytes())
            facts["boundaries"]["reservoir"]["T"] = 233.15
            facts.update(modelSha256=sha256(model).hexdigest(), studySha256=sha256(descriptor).hexdigest())
            raw = json.dumps(facts).encode()
            (root/"facts.json").write_bytes(raw)
            result = investigate(root/"study.json", root, root/"facts.json", sha256(raw).hexdigest(),
                                 "body", "263.15")
        event, = result["passages"]
        self.assertEqual(event["direction"], "cooling")
        lo, hi = map(Fraction, event["timeBoundsSeconds"])
        self.assertLess(lo, 2500 * math.log(2))
        self.assertGreater(hi, 2500 * math.log(2))
        self.assertEqual(hi-lo, Fraction(25, 2))
