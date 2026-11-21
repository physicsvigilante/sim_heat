from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp
from tests.test_loaded_thermal_ports import LINK
from tools.three_reading_cooling import investigate


class ThreeReadingTests(TestCase):
    def study(self, readings, spacing="20"):
        return investigate(LINK, "cold", "100", "0.5", spacing, readings)

    def test_identifies_same_film_from_heating_and_cooling(self):
        with mp.workdps(100):
            total = 5*mp.log(2)
            h = 2*(total-2)
            air = 390 + 20/(total-2)
            for readings in (("430", "410", "400"), ("350", "370", "380")):
                result = self.study(readings)
                self.assertEqual(result["equilibriumTemperatureK"], "390")
                self.assertEqual(result["successiveIncrementRatio"], "1/2")
                for k, v in (("totalConductanceBoundsWPerK", total),
                             ("filmCoefficientBoundsWPerM2K", h), ("airTemperatureBoundsK", air)):
                    a, b = (mp.mpf(x.numerator)/x.denominator for x in map(F, result[k]))
                    self.assertTrue(a <= v <= b)
                    self.assertLess(b-a, mp.mpf("1e-65"))
                for i, t in enumerate(readings):
                    recovered = 390 + (int(readings[0])-390)*mp.exp(-total*20*i/100)
                    self.assertLess(abs(recovered-int(t)), mp.mpf("1e-90"))

    def test_rejects_nonidentifiable_and_nonpassive_inputs(self):
        for readings, spacing in ((("300","300","300"),"20"), (("300","320","340"),"20"),
                                  (("330","320","325"),"20"), (("430","410","400"),"100"),
                                  (("6","3","1"),"1"), (("11","7","5"),"20")):
            with self.subTest(readings=readings), self.assertRaises(ValueError):
                self.study(readings, spacing)

    def test_nonunit_ratio_numerator(self):
        r = self.study(("405", "400", "397"))
        self.assertEqual(r["successiveIncrementRatio"], "3/5")
        self.assertEqual(r["equilibriumTemperatureK"], "785/2")
        with mp.workdps(100):
            expected = -5*mp.log(mp.mpf(3)/5)
            a, b = (mp.mpf(q.numerator)/q.denominator for q in map(F, r["totalConductanceBoundsWPerK"]))
            self.assertTrue(a < expected < b)
