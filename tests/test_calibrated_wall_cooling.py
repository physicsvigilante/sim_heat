from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.calibrated_wall_cooling import decay_bounds, investigate


class CalibratedPredictionTests(TestCase):
    def study(self, port="cold", capacity="100", area="0.5", duration="60"):
        return investigate(LINK, "cold", "100", "0.5", "20", ["430", "410", "400"],
                           LINK, port, capacity, area, "430", duration)

    def check(self, r, key, reference):
        a, b = (mp.mpf(q.numerator)/q.denominator for q in map(F, r[key]))
        self.assertLessEqual(a, reference)
        self.assertGreaterEqual(b, reference)
        self.assertLess(b-a, mp.mpf("1e-64"))

    def test_unused_fourth_reading_and_initial_condition(self):
        with mp.workdps(110):
            result = self.study()
            self.check(result, "temperatureAfterExposureBoundsK", 395)
            self.check(result, "halfLifeBoundsS", 20)
            self.assertEqual(self.study(duration="0")["temperatureAfterExposureBoundsK"], ["430","430"])

    def test_changed_wall_drive_area_and_capacity(self):
        with mp.workdps(110):
            h = 2*(5*mp.log(2)-2)
            air = 390 + 40/h
            eq = (2*280 + h*air)/(2+h)
            tau = 150/(2+h)
            result = self.study("hot", "150", "1")
            self.check(result, "newEquilibriumTemperatureBoundsK", eq)
            self.check(result, "timeConstantBoundsS", tau)
            self.check(result, "temperatureAfterExposureBoundsK", eq + (430-eq)*mp.exp(-60/tau))
            for value in (F(256), F(1000)):
                lo, hi = decay_bounds(value)
                self.assertEqual(lo, 0)
                self.assertLess(mp.exp(-int(value)), mp.mpf(hi.numerator)/hi.denominator)
        with self.assertRaises(ValueError):
            self.study(area="0")

    def test_transfer_to_a_new_three_terminal_network(self):
        case = CASES/"star"
        star = (case/"study.json", case, case/"facts.json", STAR)
        result = investigate(LINK, "cold", "100", "0.5", "20", ["430","410","400"],
                             star, "middle", "150", "1", "430", "60")
        with mp.workdps(110):
            g = mp.mpf(21)/10
            t_open = mp.mpf(2160)/7
            h = 2*(5*mp.log(2)-2)
            air = 390 + 40/h
            eq = (g*t_open + h*air)/(g+h)
            self.check(result, "temperatureAfterExposureBoundsK", eq + (430-eq)*mp.exp(-60*(g+h)/150))
        self.assertEqual(result["newWall"]["factsSha256"], STAR)
        self.assertNotEqual(result["newWall"]["factsSha256"], result["calibration"]["factsSha256"])
