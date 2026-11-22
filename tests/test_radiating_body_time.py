from fractions import Fraction as F
import math
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK, LEFT
from tools.radiating_body_time import investigate


class BodyTimeTests(TestCase):
    def wall(self, start, target, capacity="100"):
        return investigate(LINK, "cold", "280", "0", "390", "1", "0", "0.00000005",
                           capacity, start, target)

    def check_time(self, result, reference):
        self.assertEqual(result["status"], "reached")
        low, high = map(F, result["timeBoundsS"])
        self.assertLess(float(low), reference)
        self.assertGreater(float(high), reference)
        self.assertLess(float(high-low), 0.004*reference)

    def test_reflective_wall_heating_and_cooling(self):
        for start, target, energy in (("280", "330", 5000), ("480", "430", -5000)):
            result = self.wall(start, target)
            self.check_time(result, 50*math.log(2))
            self.assertEqual(F(result["bodyEnergyChangeJ"]), energy)

    def test_radiating_star_with_varying_conductivity(self):
        # Hand-reduced star has body couplings 1.5 and 0.6 W/K at 300 K.
        def phi(t):
            return t-300 + 0.001*(t-300)**2
        def net(t):
            return (1.5*(phi(280)-phi(t)) + 0.6*(phi(380)-phi(t))
                    + 0.00000002*(400**4-t**4))
        for start, target in ((300, 320), (420, 400)):
            step = (target-start)/2000
            expected = sum(200*step/net(start+(i+0.5)*step) for i in range(2000))
            result = investigate(LEFT, "middle", "300", "0.002", "400", "0.5", "0.8", "0.00000005",
                                 "200", str(start), str(target))
            self.check_time(result, expected)

    def test_direction_asymptote_and_refusals(self):
        for start, target in (("280", "380"), ("280", "381"), ("280", "279"), ("380", "400")):
            result = self.wall(start, target)
            self.assertEqual((result["status"], result["timeBoundsS"]), ("unreachable_in_finite_time", None))
        self.assertEqual(self.wall("380", "380")["timeBoundsS"], ["0", "0"])
        with self.assertRaisesRegex(ValueError, "capacity"):
            self.wall("280", "320", "0")
        with self.assertRaisesRegex(ValueError, "positive"):
            investigate(LINK, "cold", "300", "-0.01", "280", "1", "1", "0.00000005",
                        "100", "430", "380")
