from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.radiative_gap import investigate


class ShieldStackTests(TestCase):
    def solve(self, shields, *, left="cold", right="hot", support=None):
        return investigate(LINK, LINK, left, right, "0.02", "1", "1", "0.0000000567",
                           support_inputs=support, shield_stack=shields)

    def test_two_black_shields(self):
        result = self.solve([("1", "1")] * 2)
        lo, hi = map(F, result["leftToRightHeatRateBoundsW"])
        # Three black gaps each carry q. The two solid networks drop q/2 apiece.
        def balance(q):
            return 3*q - F(".02")*F(".0000000567")*((380-q/2)**4 - (280+q/2)**4)
        self.assertLessEqual(balance(lo), 0)
        self.assertGreaterEqual(balance(hi), 0)
        self.assertLess(hi-lo, F(1, 10**14))
        for i, shield in enumerate(result["shieldsLeftToRight"], 1):
            a, b = map(F, shield["temperatureBoundsK"])
            def moment(q):
                return (380-q/2)**4 - i*q/(F(".02")*F(".0000000567"))
            self.assertLessEqual(a**4, moment(lo))
            self.assertGreaterEqual(b**4, moment(hi))
            self.assertLess(b-a, F(1, 10**12))

    def test_asymmetric_reversal(self):
        shields = [("0.9", "0.1"), ("0.6", "0.4"), ("0.2", "0.5")]
        forward = self.solve(shields)
        reverse = self.solve([p[::-1] for p in shields[::-1]], left="hot", right="cold")
        lo, hi = map(F, forward["leftToRightHeatRateBoundsW"])
        self.assertEqual(list(map(F, reverse["leftToRightHeatRateBoundsW"])), [-hi, -lo])
        for a, b in zip(forward["shieldsLeftToRight"], reverse["shieldsLeftToRight"][::-1], strict=True):
            self.assertEqual(a["temperatureBoundsK"], b["temperatureBoundsK"])

    def test_isolated_cluster_and_conducting_bypass(self):
        # The first and last shields each equilibrate to one plate. The middle
        # two shields exchange heat only with each other.
        shields = [("1", "0"), ("1", "1"), ("1", "0"), ("1", "1")]
        for support in (None, LINK):
            result = self.solve(shields, support=support)
            shields_out = result["shieldsLeftToRight"]
            self.assertEqual(shields_out[0]["temperatureBoundsK"], result["leftPlateTemperatureBoundsK"])
            self.assertEqual(shields_out[-1]["temperatureBoundsK"], result["rightPlateTemperatureBoundsK"])
            for shield in shields_out[1:3]:
                self.assertIsNone(shield["temperatureBoundsK"])
                self.assertEqual(shield["temperatureStatus"], "undetermined")
            if support:
                self.assertGreater(F(result["supportHeatRateBoundsW"][0]), 0)
                self.assertEqual(result["radiativeHeatRateBoundsW"], ["0", "0"])
            else:
                self.assertEqual(result["leftToRightHeatRateBoundsW"], ["0", "0"])

    def test_rejects_invalid_stack(self):
        for shields in ([], [("0.1",)], [("1", "1.01")]):
            with self.subTest(shields=shields), self.assertRaises(ValueError):
                self.solve(shields)
