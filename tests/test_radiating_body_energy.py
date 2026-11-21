from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK, LEFT
from tools.radiating_body_time import investigate


class BodyEnergyTests(TestCase):
    def test_heating_cooling_and_radiation_sign_change(self):
        for start, target, env in ((300, 320, 400), (420, 400, 400), (300, 310, 305)):
            # For the sign-change case the outer hot bath supplies the composite wall.
            wall = env == 305
            source, port = (LINK, "cold") if wall else (LEFT, "middle")
            def power(t):
                phi = lambda x: x-300 + 0.001*(x-300)**2
                conduct = (2*(phi(380)-phi(t)) if wall else
                           1.5*(phi(280)-phi(t)) + 0.6*(phi(380)-phi(t)))
                return conduct, 2e-8*(env**4-t**4)
            step = (target-start)/4000
            expected = [0., 0.]
            for i in range(4000):
                channels = power(start+(i+0.5)*step)
                for j in range(2):
                    expected[j] += 200*step*channels[j]/sum(channels)
            result = investigate(source, port, "300", "0.002", str(env), "0.5", "0.8", "0.00000005",
                                 "200", str(start), str(target), track_energy=True)
            bounds = result["energyToBodyBoundsJ"]
            for name, reference in zip(("conduction", "radiation"), expected):
                lo, hi = map(F, bounds[name])
                self.assertLessEqual(float(lo), reference)
                self.assertGreaterEqual(float(hi), reference)
                self.assertLess(hi-lo, 10)
            self.assertEqual(F(bounds["radiation"][0])+F(bounds["conduction"][1]), 200*(target-start))

    def test_zero_radiation_and_trip_status(self):
        def trip(target, **options):
            return investigate(LINK, "cold", "280", "0", "390", "1", "0", "0.00000005",
                               "100", "280", target, **options)
        for target, energy in (("330", "5000"), ("280", "0")):
            self.assertEqual(trip(target, track_energy=True)["energyToBodyBoundsJ"],
                             {"radiation": ["0", "0"], "conduction": [energy, energy]})
        self.assertIsNone(trip("380", track_energy=True)["energyToBodyBoundsJ"])
        self.assertNotIn("energyToBodyBoundsJ", trip("330"))
