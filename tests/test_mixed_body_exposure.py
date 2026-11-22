from fractions import Fraction as F
from math import exp
from unittest import TestCase

from scipy.integrate import solve_ivp
from tests.test_loaded_thermal_ports import LINK
from tools.body_exposure_sequence import investigate as schedule
from tools.body_exposure_temperature import investigate as exposure


class MixedExposureTests(TestCase):
    def check(self, box, point, tolerance=0.25):
        a, b = map(float, map(F, box))
        self.assertLessEqual(a, point)
        self.assertLessEqual(point, b)
        self.assertLess(b-a, tolerance)

    def test_three_stages_including_heating_past_rod_bath(self):
        stages = [("300", "500", "0.5", "8", "20"), ("300", "10"),
                  ("300", "280", "1", "2", "15")]
        result = schedule(LINK, "cold", "300", "0", "0.2", "0", "0.00000005", "100", "360", stages)
        t = 360
        for i, (air, g, seconds) in enumerate(((500, 4, 20), (300, 0, 10), (280, 2, 15))):
            bath = (2*380 + g*air)/(2+g)
            t = bath + (t-bath)*exp(-(2+g)*seconds/100)
            self.check(result["stages"][i]["temperatureBoundsK"], t, 0.4)
        self.assertGreater(F(result["stages"][0]["temperatureBoundsK"][0]), 380)
        self.assertNotIn("airFilm", result["stages"][1])

    def test_shield_and_film_after_a_fixed_duration(self):
        def rhs(t, y):
            temp = y[0]
            return [(2*(380-temp) + 2*(400-temp) + 0.2*5e-8/3*(410**4-temp**4))/100]
        ref = solve_ivp(rhs, (0, 30), [430], rtol=1e-12, atol=1e-12)
        result = exposure(LINK, "cold", "300", "0", "410", "0.2", "1", "0.00000005",
                          "100", "430", "30", air_film=("400","0.5","4"), shield_stack=[("1","1")]*2)
        self.check(result["temperatureBoundsK"], ref.y[0,-1])
        self.assertEqual(result["exterior"]["radiantExchangeCoefficientWPerK4"], "1/300000000")
        self.assertEqual(result["airFilm"]["areaM2"], "1/2")

    def test_thermally_inactive_film_does_not_extend_material_domain(self):
        # A 1000 K reading at h=0 does not drive the rod or require the rod law there.
        result = exposure(LINK, "cold", "300", "-0.002", "300", "0.2", "0", "0.00000005",
                          "100", "360", "0", air_film=("1000","1","0"))
        self.assertEqual(result["temperatureBoundsK"], ["360", "360"])
