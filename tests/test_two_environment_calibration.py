from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_loaded_thermal_ports import LINK
from tools.two_environment_calibration import investigate


class EnvironmentalTrials(TestCase):
    def solve(self, trials):
        return investigate(LINK, "cold", "0.1", [("0.2","2")], "0.0000000567", trials)

    def test_radiation_only_and_convection_only_trials(self):
        # Matching air or enclosure to the surface isolates one mechanism.
        radiation = ("360","360","360","300")
        convection = ("360","360","350","360")
        with mp.workdps(110):
            flux = 20/((mp.mpf("0.5")+5/(8*mp.pi))*mp.mpf("0.16")*mp.pi)
            known = (flux/10, flux/(mp.mpf("0.0000000567")*(360**4-300**4)))
            for trials in [(radiation,convection), (convection,radiation),
                           (("359.9","360.1","360","300"), convection)]:
                result = self.solve(trials)
                for key, value in zip(("convectionCoefficientBoundsWPerM2K","emissivityBounds"),known):
                    lo, hi = map(F,result[key])
                    self.assertTrue(lo <= F(mp.nstr(value,95)) <= hi)
                    if trials[0][0] == trials[0][1]:
                        self.assertLess(hi-lo, F(1,10**12))

    def test_refuses_indistinguishable_and_out_of_range_trials(self):
        rad = ("360","360","360","300")
        for pair in [(rad,rad), (rad,("360","360","370","360")),
                     (("360","360","360","359.99"), ("360","360","350","360"))]:
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                self.solve(pair)
