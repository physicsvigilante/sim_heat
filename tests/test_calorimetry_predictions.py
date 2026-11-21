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
