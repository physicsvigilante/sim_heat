from fractions import Fraction as F
from itertools import product
from math import log
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.two_mass_calorimeter import investigate


class TwoMassTests(TestCase):
    def run_trials(self, trials):
        return investigate(LINK, "cold", "280", "0", "400", "1", "0", "0.00000005", "280", "330", trials)

    def test_two_loaded_trials_and_shared_unit_factor(self):
        trials = [("0.2","34.65","34.67"), ("0.5","76.24","76.26")]
        result = self.run_trials(trials)
        self.assertEqual(result, self.run_trials(trials[::-1]))
        slope = list(map(F, result["sampleSpecificHeatBoundsJPerKgK"]))
        tare = list(map(F, result["emptyCalorimeterCapacityBoundsJPerK"]))
        for t1, t2 in product((34.65, 34.67), (76.24, 76.26)):
            c = 2*(t2-t1)/(0.3*log(2))
            empty = 2*t1/log(2)-0.2*c
            self.assertTrue(float(slope[0]) <= c <= float(slope[1]))
            self.assertTrue(float(tare[0]) <= empty <= float(tare[1]))
        self.assertTrue(slope[0] < 400 < slope[1] and tare[0] < 20 < tare[1])
        self.assertLess(slope[1]-slope[0], 2)

    def test_empty_trial_and_refusal_cases(self):
        result = self.run_trials([("0","6.93","6.94"), ("0.2","34.65","34.67")])
        self.assertTrue(F(result["emptyCalorimeterCapacityBoundsJPerK"][0]) < 20
                        < F(result["emptyCalorimeterCapacityBoundsJPerK"][1]))
        for trials in ([], [("1","1","1")]*2, [("1","2","2"),("2","1","1")],
                       [("1","1","1"),("2","3","3")], [("1","1","2"),("2","2","3")]):
            with self.assertRaises(ValueError):
                self.run_trials(trials)
