from fractions import Fraction as F
from math import log
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK, LEFT
from tools.timed_specific_heat import investigate


class SpecificHeatTests(TestCase):
    def wall(self, start="280", target="330", low="34.65", high="34.67", tare="20", mass="0.2"):
        return investigate(LINK, "cold", "280", "0", "400", "1", "0", "0.00000005",
                           start, target, low, high, tare, mass)

    def test_half_difference_heating_and_cooling(self):
        for start, target in (("280", "330"), ("480", "430")):
            result = self.wall(start, target)
            a, b = map(F, result["sampleSpecificHeatBoundsJPerKgK"])
            for measured in (34.65, 34.67):
                expected = (2*measured/log(2)-20)/0.2
                self.assertTrue(float(a) <= expected <= float(b))
            self.assertLess(b-a, 2)
            self.assertTrue(a < 400 < b)
            self.assertFalse(result["unitCapacityPassage"]["nativeQualified"])

    def test_nonlinear_multibath_timing(self):
        # Integrate the physical three-terminal balance directly for C=200 J/K.
        step = 20/2000
        def phi(x):
            return x-300+0.001*(x-300)**2
        def power(x):
            return 1.5*(phi(280)-phi(x))+0.6*(phi(380)-phi(x))+2e-8*(400**4-x**4)
        secs = sum(200*step/power(300+(i+0.5)*step) for i in range(2000))
        result = investigate(LEFT, "middle", "300", "0.002", "400", "0.5", "0.8", "0.00000005",
                             "300", "320", f"{secs-0.001:.9f}", f"{secs+0.001:.9f}", "50", "0.25")
        a, b = map(F, result["sampleSpecificHeatBoundsJPerKgK"])
        self.assertTrue(a < 600 < b)
        self.assertLess(b-a, 1)

    def test_uninformative_and_unphysical_measurements(self):
        for changes in (dict(target="280"), dict(target="380"), dict(low="0"), dict(high="30"),
                        dict(mass="0"), dict(tare="101"), dict(tare="100")):
            with self.assertRaises(ValueError):
                self.wall(**changes)
