import math
from fractions import Fraction
from pathlib import Path
from unittest import TestCase

from tests.test_composite_wall import CASE, FACTS_PIN
from tests.test_wall_revision import REVISION_PIN
from tools.terminal_resistance import measure, terminal_pair


class TerminalResistanceTests(TestCase):
    def test_composite_wall_and_material_revision(self):
        for study, facts, pin, expected in (
            ("study.json", "facts.json", FACTS_PIN, "1/2"),
            ("higher_k.json", "higher_k_facts.json", REVISION_PIN, "3/8"),
        ):
            with self.subTest(study=study):
                result = measure(CASE / study, CASE, CASE / facts, pin)
                lower, upper = map(Fraction, result["resistanceBoundsKPerW"])
                self.assertLessEqual(lower, Fraction(expected))
                self.assertGreaterEqual(upper, Fraction(expected))
                self.assertLess(upper - lower, Fraction(1, 10**12))
                self.assertEqual((result["hot"], result["cold"]), ("hot", "cold"))

    def test_two_circular_rods_in_series(self):
        root = Path(__file__).resolve().parents[1] / "h1"
        case = root / "cases/S1"
        result = measure(case / "study.json", case, root / "reference_cases/S1.json",
                         "47b1d9035230cb252a992a3fdcdbdf6fbefd350f901aacaaae9dae37b561635a")
        lower, upper = map(Fraction, result["resistanceBoundsKPerW"])
        expected = (0.75 / 384.928 + 1.25 / 46.024) / (math.pi * 0.01**2)
        self.assertAlmostEqual(float(lower), expected, places=11)
        self.assertAlmostEqual(float(upper), expected, places=11)

    def test_refuse_undefined_measurements(self):
        facts = dict(mode="steady", bodies={}, nodes=["a", "b"],
                     boundaries={"left": {"T": 300}, "right": {"T": 300}},
                     rods={"rod": {"a": "a", "b": "b"}})
        for change, reason in (({}, "equal reservoir"), ({"rods": {}}, "connected"),
                               ({"mode": "transient"}, "steady"),
                               ({"boundaries": {}}, "two reservoirs")):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, reason):
                terminal_pair({**facts, **change})
