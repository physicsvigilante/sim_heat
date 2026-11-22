import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction
from math import log
from unittest import TestCase

from tests.test_temperature_passages import D1, D1_PIN, ROOT, TWIN, TWIN_PIN
from tools.heat_flow_reversals import investigate


class ReversalTests(TestCase):
    def test_lower_rod_reverses_at_analytical_zero(self):
        result = investigate(TWIN/"study.json", TWIN, TWIN/"facts.json", TWIN_PIN, "lower")
        event, = result["reversals"]
        self.assertEqual(result["status"], "bracketed")
        self.assertEqual((result["positiveFrom"], result["positiveTo"]), ("lower.port_a", "lower.port_b"))
        self.assertEqual(event["direction"], "positive_to_negative")
        self.assertEqual(event["sampleIndices"], [415, 416])
        lo, hi = map(Fraction, event["timeBoundsSeconds"])
        self.assertLess(lo, 20*log(8))
        self.assertGreater(hi, 20*log(8))
        self.assertEqual(hi-lo, Fraction(1, 10))

    def test_single_body_heating_has_no_observed_reversal(self):
        result = investigate(D1/"study.json", D1, ROOT/"h1/reference_cases/D1.json", D1_PIN, "rod")
        self.assertEqual(result["status"], "no_certified_reversal")
        self.assertEqual(result["reversals"], [])

    def test_body_cannot_be_observed_as_rod(self):
        with self.assertRaisesRegex(ValueError, "existing member of rods"):
            investigate(TWIN/"study.json", TWIN, TWIN/"facts.json", TWIN_PIN, "blue")

    def test_reorienting_lower_rod_swaps_direction_at_same_time(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            model = (TWIN/"model.mo").read_text()
            model = model.replace("lower.port_a", "reverse_placeholder").replace(
                "lower.port_b", "lower.port_a").replace("reverse_placeholder", "lower.port_b")
            raw = model.encode()
            (root/"model.mo").write_bytes(raw)
            study = json.loads((TWIN/"study.json").read_bytes())
            study["model"]["sha256"] = sha256(raw).hexdigest()
            descriptor = json.dumps(study).encode()
            (root/"study.json").write_bytes(descriptor)
            facts = json.loads((TWIN/"facts.json").read_bytes())
            rod = facts["rods"]["lower"]
            rod["a"], rod["b"] = rod["b"], rod["a"]
            facts.update(modelSha256=sha256(raw).hexdigest(), studySha256=sha256(descriptor).hexdigest())
            data = json.dumps(facts).encode()
            (root/"facts.json").write_bytes(data)
            event, = investigate(root/"study.json", root, root/"facts.json",
                                 sha256(data).hexdigest(), "lower")["reversals"]
        self.assertEqual(event["direction"], "negative_to_positive")
        self.assertEqual(event["sampleIndices"], [415, 416])
