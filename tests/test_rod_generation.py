from fractions import Fraction
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.rod_generation import investigate


class GenerationTests(TestCase):
    def check(self, fields, expected):
        self.assertEqual(set(fields), set(expected))
        for terminal, q in expected.items():
            low, high = map(Fraction, fields[terminal])
            self.assertLessEqual(low, q)
            self.assertGreaterEqual(high, q)
            self.assertLess(high - low, Fraction(1, 10**12))

    def test_composite_wall_and_hot_bath_reversal(self):
        for watts, hot in (("240", 20), ("320", -40)):
            result = investigate(*LINK, [("facing", watts)])
            self.check(result["unheatedBathSupplyBoundsW"], {"hot": 200, "cold": -200})
            self.check(result["netBathSupplyBoundsW"], {"hot": hot, "cold": -int(watts) - hot})
        result = investigate(*LINK, [("facing", "240"), ("insert", "80")])
        self.check(result["netBathSupplyBoundsW"], {"hot": 0, "cold": -320})
        self.check(result["rodsWithGeneration"]["insert"]["generatedPowerToBathBoundsW"],
                   {"hot": 20, "cold": 60})

    def test_three_terminal_star_from_explicit_junction_balance(self):
        case = CASES/"star"
        result = investigate(case/"study.json", case, case/"facts.json", STAR, [("first", "160")])
        # 80 W directly at warm. The other 80 W raises the joint by 8 K,
        # exporting another 16, 24, 40 W through its three conductances.
        self.check(result["generatedPowerToBathBoundsW"], {"warm": 96, "middle": 24, "cool": 40})
        self.check(result["netBathSupplyBoundsW"], {"warm": 34, "middle": 21, "cool": -215})

    def test_zero_generation_and_bad_sources(self):
        result = investigate(*LINK, [("insert", "0")])
        self.assertEqual(result["unheatedBathSupplyBoundsW"], result["netBathSupplyBoundsW"])
        for bad in ([], [("missing", "2")], [("insert", "2"), ("insert", "2")], [("strip", "-1")]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                investigate(*LINK, bad)
