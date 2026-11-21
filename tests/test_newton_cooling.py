from fractions import Fraction as F
from math import log
from unittest import TestCase

from scipy.integrate import quad
from tests.test_loaded_thermal_ports import LINK
from tools.radiating_body_time import investigate


class NewtonCoolingTests(TestCase):
    def run_body(self, target, film=("400", "0.5", "4"), eps="0", shields=None):
        return investigate(LINK, "cold", "300", "0", "410", "0.2", eps, "0.00000005",
                           "100", "430", target, air_film=film, track_energy=True, shield_stack=shields)

    def contains(self, bounds, expected, max_width):
        a, b = map(float, map(F, bounds))
        self.assertLessEqual(a, expected)
        self.assertGreaterEqual(b, expected)
        self.assertLess(b-a, max_width)

    def test_exact_newton_cooling_with_air_flow_reversal(self):
        # The effective bath is 390 K, C/(G+hA) = 25 s. Convection changes sign at 400 K.
        r = self.run_body("395")
        t = 25*log(8)
        air = 20*t - 1750
        self.contains(r["timeBoundsS"], t, 0.5)
        self.contains(r["energyToBodyBoundsJ"]["convection"], air, 30)
        self.contains(r["energyToBodyBoundsJ"]["conduction"], -3500-air, 30)
        self.assertEqual(r["energyToBodyBoundsJ"]["radiation"], ["0", "0"])
        self.assertEqual(self.run_body("390")["status"], "unreachable_in_finite_time")

    def test_shielded_radiation_with_separate_air_film(self):
        # Two black shields reduce the radiative coefficient by a factor of three.
        k = 0.2 * 5e-8 / 3
        def air(t):
            return 2*(400-t)
        def rad(t):
            return k*(410**4-t**4)
        def outward(t):
            return 2*(t-380) - air(t) - rad(t)
        r = self.run_body("400", eps="1", shields=[("1", "1")]*2)
        for key, flux in (("radiation", rad), ("convection", air), ("conduction", lambda t: 2*(380-t))):
            energy = quad(lambda t: 100*flux(t)/outward(t), 400, 430)[0]
            self.contains(r["energyToBodyBoundsJ"][key], energy, 35)

    def test_zero_duration_and_bad_film(self):
        result = self.run_body("430")
        self.assertEqual(result["energyToBodyBoundsJ"]["convection"], ["0", "0"])
        for film in ([], ("300", "0", "1"), ("300", "1", "-1")):
            with self.subTest(film=film), self.assertRaises(ValueError):
                self.run_body("400", film=film)
