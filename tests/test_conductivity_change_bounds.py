from fractions import Fraction
from unittest import TestCase

from tests.test_composite_wall import CASE, FACTS_PIN
from tests.test_steady_bridge import CASE as BRIDGE, BASE
from tests.test_wall_revision import REVISION_PIN
from tools.conductivity_change_bounds import predict
from tools.terminal_resistance import measure


class ConductivityChangeTests(TestCase):
    def bounds(self, root, pin, rod, factor):
        result = predict(root/"study.json", root, root/"facts.json", pin, rod, factor)
        self.assertFalse(result["nativeExecuted"])
        return tuple(map(Fraction, result["predictedResistanceBoundsKPerW"]))

    def check_limits(self, interval, lower, upper):
        lo, hi = interval
        self.assertLessEqual(lo, lower)
        self.assertGreaterEqual(hi, upper)
        self.assertLess(max(lower-lo, hi-upper), Fraction(1, 10**12))

    def test_composite_wall_strengthening_encloses_full_revised_solve(self):
        lo, hi = self.bounds(CASE, FACTS_PIN, "insert", "7/3")
        self.check_limits((lo, hi), Fraction(1,3), Fraction(11,28))
        revised = measure(CASE/"higher_k.json", CASE, CASE/"higher_k_facts.json", REVISION_PIN)
        rlo, rhi = map(Fraction, revised["resistanceBoundsKPerW"])
        self.assertTrue(lo <= rlo <= Fraction(3,8) <= rhi <= hi)

    def test_weakening_and_unchanged_material(self):
        self.check_limits(self.bounds(CASE, FACTS_PIN, "insert", "0.5"),
                          Fraction(8,13), Fraction(11,16))
        self.check_limits(self.bounds(CASE, FACTS_PIN, "insert", "1"),
                          Fraction(1,2), Fraction(1,2))

    def test_balanced_bridge_link(self):
        self.check_limits(self.bounds(BRIDGE, BASE, "link", "1500"),
                          Fraction(2,3), Fraction(2,3))

    def test_bad_hypotheses(self):
        for factor in ("0", "-1", "1/0", "1e999999", "NaN", True):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                self.bounds(CASE, FACTS_PIN, "insert", factor)
        with self.assertRaisesRegex(ValueError, "unknown rod"):
            self.bounds(CASE, FACTS_PIN, "missing", "2")
