from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_loaded_thermal_ports import LINK
from tools.radial_film_calibration import investigate


class FilmCalibrationTests(TestCase):
    def run_case(self, band, air="450", eps="0.8", length=None):
        return investigate(LINK, "cold", "0.1", [("0.2","2")], band, air, "280", eps,
                           "0.0000000567", length)

    def test_independent_opposing_fluxes_and_uncertain_reading(self):
        with mp.workdps(110):
            for length in (None, "1"):
                area = (mp.mpf("0.16") if length is None else mp.mpf("0.4"))*mp.pi
                shell = 5/(8*mp.pi) if length is None else mp.log(2)/(4*mp.pi)
                def coefficient(t):
                    supply = (380-t)/(mp.mpf("0.5")+shell)
                    radiation = mp.mpf("0.00000004536")*(t**4-280**4)
                    return (supply/area-radiation)/(t-450)
                for band in (("360","360"), ("359","361")):
                    r = self.run_case(band, length=length)
                    lo, hi = map(F,r["convectionCoefficientBoundsWPerM2K"])
                    for t in range(int(band[0]), int(band[1])+1):
                        self.assertTrue(lo <= F(mp.nstr(coefficient(t),95)) <= hi)
                    if band[0] == band[1]:
                        self.assertLess(hi-lo, F(1,10**12))
                    self.assertLess(F(r["netHeatToAirBoundsW"][1]), 0)
                    self.assertGreater(F(r["netHeatToEnclosureBoundsW"][0]), 0)

    def test_zero_and_unidentifiable_or_incompatible_readings(self):
        self.assertEqual(self.run_case(("380","380"), eps="0")["convectionCoefficientBoundsWPerM2K"], ["0","0"])
        for band, air in [(("449","451"),"450"), (("360","360"),"300"), (("361","359"),"450")]:
            with self.subTest(band=band, air=air), self.assertRaises(ValueError):
                self.run_case(band, air)
