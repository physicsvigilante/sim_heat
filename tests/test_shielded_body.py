from fractions import Fraction
import math
from unittest import TestCase

from scipy.integrate import quad
from tests.test_loaded_thermal_ports import LINK
from tools.radiating_body_time import investigate


class ShieldedBodyTests(TestCase):
    def study(self, shields, start="450", target="390", environment="400"):
        return investigate(LINK, "cold", "300", "0", environment, "1", "0.8", "0.00000005",
                           "100", start, target, track_energy=True, shield_stack=shields)

    def assert_enclosed(self, bounds, reference, max_width):
        lo, hi = map(float, map(Fraction, bounds))
        self.assertLessEqual(lo, reference)
        self.assertGreaterEqual(hi, reference)
        self.assertLess(hi - lo, max_width)

    def test_dissimilar_shields_and_reversing_radiation(self):
        # Resistances of three gaps from the body toward the black enclosure.
        # Radiation warms the body below 400 K while the 380 K bath cools it.
        dims = (1/.8 + 1/.5 - 1, 1/.2 + 1/.75 - 1, 1/.6)
        k = 5e-8/sum(dims)
        def radiation(t):
            return k*(400**4 - t**4)
        def cooling(t):
            return 2*(t-380) - radiation(t)
        time = quad(lambda t: 100/cooling(t), 390, 450)[0]
        rad = quad(lambda t: 100*radiation(t)/cooling(t), 390, 450)[0]
        result = self.study([("0.5", "0.2"), ("0.75", "0.6")])
        self.assertEqual(result["status"], "reached")
        self.assertEqual(result["bodyEnergyChangeJ"], "-6000")
        self.assert_enclosed(result["timeBoundsS"], time, 0.02*time)
        self.assert_enclosed(result["energyToBodyBoundsJ"]["radiation"], rad, 60)
        self.assert_enclosed(result["energyToBodyBoundsJ"]["conduction"], -6000 - rad, 60)

    def test_reflector_removes_only_radiation(self):
        result = self.study([("0", "1")], start="480", target="430")
        self.assert_enclosed(result["timeBoundsS"], 50*math.log(2), 0.2)
        self.assertEqual(result["energyToBodyBoundsJ"]["radiation"], ["0", "0"])
        self.assertEqual(result["energyToBodyBoundsJ"]["conduction"], ["-5000", "-5000"])
        equilibrium = self.study([("1", "0")], start="480", target="380")
        self.assertEqual(equilibrium["status"], "unreachable_in_finite_time")

    def test_rejects_invalid_shield_faces(self):
        for invalid in ([], [("1",)], [("1", "1.0001")]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.study(invalid)
