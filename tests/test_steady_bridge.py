from fractions import Fraction
from pathlib import Path
from unittest import TestCase

from qualification.h1_n13.conduction import prepare
from tools.terminal_resistance import measure

CASE = Path(__file__).resolve().parents[1] / "studies/steady_bridge"
BASE = "4cc763729e8d71b0abfc0eb5d1c3cc4d08185225104af8640541adcfdbf10bbf"
CHANGED = "9e62ef107a7499beb80406ac8b54b35e084830eb17f8d370ce96888884ba9f1f"


class SteadyBridgeTests(TestCase):
    def test_balance_breaks_after_one_feed_change(self):
        for prefix, pin, upper, lower, cross, total, resistance in (
            ("", BASE, 330, 330, 0, 150, Fraction(2, 3)),
            ("changed_", CHANGED, 345, 335, 10, 185, Fraction(20, 37)),
        ):
            with self.subTest(study=prefix):
                args = (CASE / (prefix + "study.json"), CASE, CASE / (prefix + "facts.json"), pin)
                candidate = prepare(*args)
                for name, value, unit in (("upperT", upper, "K"), ("lowerT", lower, "K"),
                                          ("crossFlow", cross, "W")):
                    self.assertEqual(candidate["requests"][name], {"values": [value], "unit": unit})
                for terminal, signed in (("hot", total), ("cold", -total)):
                    self.assertEqual(candidate["exports"][terminal + ".Q_to_network"]["values"], [signed])
                lo, hi = map(Fraction, measure(*args)["resistanceBoundsKPerW"])
                self.assertLessEqual(lo, resistance)
                self.assertGreaterEqual(hi, resistance)
                self.assertLess(hi - lo, Fraction(1, 10**12))

    def test_refuse_baseline_facts_for_changed_material(self):
        with self.assertRaisesRegex(ValueError, "identity|hash|SHA|binding"):
            prepare(CASE / "changed_study.json", CASE, CASE / "facts.json", BASE)
