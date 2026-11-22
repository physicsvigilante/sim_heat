from fractions import Fraction
from unittest import TestCase

from mpmath import mp

from tests.test_coupled_phase_baths import LINK
from tools.coupled_phase_baths import investigate


class StateAtTimeTests(TestCase):
    def test_plateau_and_both_sensible_baths(self):
        # Each inventory changes phase after 50 J. At 40 W this takes 1.25 s.
        hot = ("hot", "320", "100", "0.5", "0.5")
        cold = ("cold", "300", "100", "0.5", "0.5")
        for left, right in ((hot, cold), (cold, hot)):
            for t in ("0", "1", "1.25", "2", "9999"):
                result = investigate(LINK, left, right, t, ("2", "3"), track_duration=True)
                state = result["stateAtDuration"]
                with mp.workdps(100):
                    seconds = mp.mpf(t)
                    energy = (40 * seconds if seconds <= mp.mpf("1.25") else
                              74 - 24 * mp.exp(-mp.mpf(5) / 3 * (seconds - mp.mpf("1.25"))))
                    expected = Fraction(mp.nstr(energy, 95))
                low, high = map(Fraction, state["transferredEnergyMagnitudeBoundsJ"])
                self.assertLessEqual(low, expected)
                self.assertGreaterEqual(high, expected)
                self.assertLess(high - low, Fraction(1, 10**14))
                for port, sign, initial, cp in (("hot", -1, 320, 2), ("cold", 1, 300, 3)):
                    row = state["baths"][port]
                    def check(field, value):
                        a, b = map(Fraction, row[field])
                        self.assertLessEqual(a, value)
                        self.assertLessEqual(value, b)
                    liquid = Fraction(1, 2) + sign * min(expected, 50) / 100
                    check("liquidMassBoundsKg", liquid)
                    check("solidMassBoundsKg", 1 - liquid)
                    check("temperatureBoundsK", initial + sign * max(Fraction(0), expected - 50) / cp)
                    check("energyIntoBathBoundsJ", sign * expected)

    def test_equal_temperatures_and_missing_material_data(self):
        hot = ("hot", "300", "100", "1", "1")
        cold = ("cold", *hot[1:])
        result = investigate(LINK, hot, cold, "999", ("2", "3"), track_duration=True)
        self.assertEqual(result["stateAtDuration"]["transferredEnergyMagnitudeBoundsJ"], ["0", "0"])
        with self.assertRaisesRegex(ValueError, "specific heats"):
            investigate(LINK, hot, cold, "0", track_duration=True)

    def test_freezing_finishes_before_melting(self):
        from tests.test_coupled_phase_baths import WARM, COLD
        result = investigate(LINK, WARM, COLD, "1000", ("2000", "4200"), track_duration=True)
        state = result["stateAtDuration"]
        # First 750 s exhaust 90 kJ of latent heat. Only the hot bath then changes T.
        with mp.workdps(90):
            kelvin = mp.mpf("273.15") + 60 * mp.exp(-mp.mpf(250) / 550)
            energy = 90000 + 1100 * (mp.mpf("333.15") - kelvin)
            expected = Fraction(mp.nstr(energy, 85))
        lo, hi = map(Fraction, state["transferredEnergyMagnitudeBoundsJ"])
        self.assertTrue(lo <= expected <= hi)
        self.assertLess(hi - lo, Fraction(1, 10**12))
        self.assertEqual(state["baths"]["cold"]["temperatureBoundsK"], ["5463/20"] * 2)
        self.assertEqual(state["baths"]["hot"]["liquidMassBoundsKg"], ["0"] * 2)

    def test_short_horizon_after_tiny_latent_inventories(self):
        hot = ("hot", "331", "1", "999999999999", "0.1")
        cold = ("cold", "301", "1", "0.1", "999999999999")
        cp = ("999999999999", "999999999999")
        output = investigate(LINK, hot, cold, "1", cp, track_duration=True)
        low, high = map(Fraction, output["stateAtDuration"]["transferredEnergyMagnitudeBoundsJ"])
        # The 60 W initial rate lasts 1/600 s, then two equal capacities relax.
        with mp.workdps(110):
            capacity = mp.mpf("999999999999.1") * mp.mpf(cp[0])
            elapsed = 1 - 1 / mp.mpf(600)
            energy = mp.mpf("0.1") - 15 * capacity * mp.expm1(-4 * elapsed / capacity)
            exact = Fraction(mp.nstr(energy, 95))
        self.assertLessEqual(low, exact)
        self.assertLessEqual(exact, high)
        self.assertLessEqual(high, 60)
        self.assertLess(high - low, Fraction(1, 10**15))
