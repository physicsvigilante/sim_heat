import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction
from unittest import TestCase

from qualification.h1_n13.conduction import prepare
from tests.test_composite_wall import CASE, FACTS_PIN
from tools.terminal_resistance import measure

EXTENSION = CASE.parent / "series_extension"
EXTENSION_PIN = "1a60624f561e9edbf0e2457c127b06e9425bc9c6a0b6b576945f40413cd71d44"


class SeriesExtensionTests(TestCase):
    def test_reuse_measured_wall_resistance_in_series(self):
        original = measure(CASE / "study.json", CASE, CASE / "facts.json", FACTS_PIN)
        added = Fraction("0.10") / (10 * Fraction("0.020"))
        lo, hi = map(Fraction, original["resistanceBoundsKPerW"])
        predicted = (100 / (hi + added), 100 / (lo + added))
        full = prepare(EXTENSION / "study.json", EXTENSION, EXTENSION / "facts.json", EXTENSION_PIN)
        q, = full["exports"]["hot.Q_to_network"]["values"]
        self.assertLessEqual(predicted[0], q)
        self.assertLessEqual(q, predicted[1])
        self.assertEqual(q, 100)
        self.assertEqual(full["requests"]["joinT"], {"unit": "K", "values": [380 - q * added]})
        for name, unit, expected in (("interfaceT", "K", 305), ("facingRate", "W", 100),
                                     ("stripRate", "W", 25), ("insertRate", "W", -75)):
            self.assertEqual(full["requests"][name], {"unit": unit, "values": [expected]})
        self.assertEqual(full["exports"]["cold.Q_to_network"]["values"], [-q])

    def test_reversed_backing_reference_refused(self):
        facts = json.loads((EXTENSION / "facts.json").read_bytes())
        layer = facts["rods"]["backing"]
        layer["a"], layer["b"] = layer["b"], layer["a"]
        data = json.dumps(facts).encode()
        with TemporaryDirectory() as scratch:
            path = Path(scratch) / "facts.json"
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "reference physical connectivity differs"):
                prepare(EXTENSION / "study.json", EXTENSION, path, sha256(data).hexdigest())
