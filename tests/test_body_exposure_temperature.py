from fractions import Fraction as F
from math import exp
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK, LEFT
from tools.body_exposure_temperature import investigate


class ExposureTemperatureTests(TestCase):
    def check(self, result, reference, width):
        a, b = map(F, result["temperatureBoundsK"])
        self.assertLessEqual(float(a), reference)
        self.assertGreaterEqual(float(b), reference)
        self.assertLess(b-a, width)

    def test_constant_wall_half_life_limit_and_equilibrium(self):
        for start in (280, 480, 380):
            for duration in (0, 35, 3500):
                result = investigate(LINK, "cold", "280", "0", "900", "1", "0", "0.00000005",
                                     "100", str(start), str(duration))
                self.check(result, 380+(start-380)*exp(-duration/50), 0.5)
                lo, hi = map(F, result["temperatureBoundsK"])
                self.assertEqual(list(map(F, result["bodyEnergyChangeBoundsJ"])),
                                 [100*(lo-start), 100*(hi-start)])

    def test_star_heats_and_cools(self):
        def speed(t):
            phi = lambda v: v-300+(v-300)**2/1000
            q = 1.5*(phi(280)-phi(t))+0.6*(phi(380)-phi(t))+2e-8*(400**4-t**4)
            return q/200
        for start in (300, 420):
            temp = start
            step = 0.01
            for _ in range(1500):
                a = speed(temp)
                b = speed(temp+step*a/2)
                c = speed(temp+step*b/2)
                d = speed(temp+step*c)
                temp += step*(a+2*b+2*c+d)/6
            result = investigate(LEFT, "middle", "300", "0.002", "400", "0.5", "0.8", "0.00000005",
                                 "200", str(start), "15")
            self.check(result, temp, 0.15)

    def test_invalid_capacity_and_duration(self):
        for cap, duration in (("0", "1"), ("1", "-1")):
            with self.assertRaises(ValueError):
                investigate(LINK, "cold", "300", "0", "400", "1", "1", "0.00000005", cap, "300", duration)
