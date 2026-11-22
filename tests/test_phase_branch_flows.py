from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_coupled_phase_baths import COLD, LINK, WARM
from tests.test_steady_bridge import BASE, CASE, CHANGED
from tools.coupled_phase_baths import investigate


class PhaseBranchTests(TestCase):
    def encloses(self, pair, expected):
        low, high = map(F, pair)
        self.assertLessEqual(low, expected)
        self.assertLessEqual(expected, high)
        self.assertLess(high - low, F(1, 10**12))

    def test_post_freezing_parallel_split_and_reversed_rod(self):
        out = investigate(LINK, WARM, COLD, "1000", ("2000", "4200"), track_rods=True)
        with mp.workdps(100):
            delta = 60 * mp.exp(-mp.mpf(250) / 550)
            heat = 90000 + 1100 * (60 - delta)
            drive = F(mp.nstr(delta, 95))
            total = F(mp.nstr(heat, 95))
        rods = out["stateAtDuration"]["rods"]
        self.assertEqual(set(rods), {"facing", "strip", "insert"})
        for name, share in (("facing", 1), ("strip", F(1, 4)), ("insert", F(-3, 4))):
            self.encloses(rods[name]["heatFlowBoundsW"], 2 * drive * share)
            self.encloses(rods[name]["transferredHeatBoundsJ"], total * share)

    def test_balanced_and_unbalanced_cross_link_in_both_directions(self):
        for prefix, pin, coefficient in (("", BASE, 0), ("changed_", CHANGED, F(1, 10))):
            inputs = CASE / (prefix + "study.json"), CASE, CASE / (prefix + "facts.json"), pin
            for sign in (1, -1, 0):
                hot = ("hot", "320" if sign >= 0 else "300", "1000", "1", "1")
                cold = ("cold", "300" if sign > 0 else "320", "1000", "1", "1")
                state = investigate(inputs, hot, cold, "2", ("100", "200"), track_rods=True)
                cross = state["stateAtDuration"]["rods"]["link"]
                self.encloses(cross["heatFlowBoundsW"], sign * 20 * coefficient)
                self.encloses(cross["transferredHeatBoundsJ"], sign * 40 * coefficient)

    def test_missing_specific_heat_refused(self):
        with self.assertRaisesRegex(ValueError, "specific heats"):
            investigate(LINK, WARM, COLD, "3", track_rods=True)
