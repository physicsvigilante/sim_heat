from fractions import Fraction as F
from unittest import TestCase

from tests.test_terminal_response import CASES, STAR
from tools.two_heater_calorimetry import investigate


class CalorimetryPredictions(TestCase):
    def predict(self, warm, middle):
        case = CASES/"star"
        return investigate((case/"study.json", case, case/"facts.json", STAR), ["first","second"],
                           [("warm", *warm), ("middle", *middle)], predict=True)

    def test_unmeasured_bath_and_buried_peak(self):
        r = self.predict(("22","22"), ("-57","-57"))
        self.assertEqual(set(r["unmeasuredBathSupplyBoundsW"]), {"cool"})
        # 140 W enters the joint, so it warms by 14 K to 329 K.
        for limits, expected in ((r["unmeasuredBathSupplyBoundsW"]["cool"], -245),
                                 (r["rodPeakTemperatureBoundsK"]["second"], 330+F(361,80))):
            lo, hi = map(F, limits)
            self.assertLessEqual(lo, expected)
            self.assertGreaterEqual(hi, expected)
            self.assertLess(hi-lo, F(1,10**12))

    def test_measurement_band_encloses_all_corner_predictions(self):
        r = self.predict(("21","23"), ("-58","-56"))
        for warm in ("21", "23"):
            for middle in ("-58","-56"):
                corner = self.predict((warm,warm), (middle,middle))
                for key in ("rodPeakTemperatureBoundsK","unmeasuredBathSupplyBoundsW"):
                    for name, bounds in corner[key].items():
                        lo, hi = map(F, r[key][name])
                        a, b = map(F, bounds)
                        self.assertTrue(lo <= a <= b <= hi)

    def test_cold_bath_band_preserves_shared_measurements(self):
        # At the common joint, eliminate the two heater powers from the end
        # fluxes. With G=(2,3,5) W/K the cold supply changes by one third of
        # the sum of the changes in the two measured bath supplies.
        for warm, middle in [(("21","23"), ("-58","-56")),
                             (("20","23"), ("-57","-57"))]:
            result = self.predict(warm, middle)
            lo, hi = map(F, result["unmeasuredBathSupplyBoundsW"]["cool"])
            for i, limit in enumerate((lo, hi)):
                expected = -245 + (F(warm[i])-22 + F(middle[i])+57)/3
                self.assertTrue(lo <= expected <= hi)
                self.assertLess(abs(limit-expected), F(1, 10**12))
