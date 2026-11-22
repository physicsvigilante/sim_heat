from fractions import Fraction as F
from math import exp
from unittest import TestCase

from tests.test_loaded_thermal_ports import LEFT, LINK
from tools.body_exposure_sequence import investigate


class SequenceTests(TestCase):
    def test_hot_cold_hot_history_and_signed_storage(self):
        stages = [("430", "15"), ("250", "21"), ("390", "6")]
        result = investigate(LEFT, "middle", "300", "0.002", "0.5", "0.8", "0.00000005",
                             "200", "300", stages)
        t = 300
        elapsed = 0
        previous = ["300", "300"]
        def phi(x):
            return x-300+(x-300)**2/1000
        for record, (env, seconds) in zip(result["stages"], stages, strict=True):
            def speed(x):
                return (1.5*(phi(280)-phi(x)) + 0.6*(phi(380)-phi(x))+2e-8*(int(env)**4-x**4))/200
            step = 0.01
            for _ in range(100*int(seconds)):
                a = speed(t)
                b = speed(t+step*a/2)
                c = speed(t+step*b/2)
                t += step*(a+2*b+2*c+speed(t+step*c))/6
            elapsed += int(seconds)
            self.assertEqual(record["initialTemperatureBoundsK"], previous)
            self.assertEqual(F(record["elapsedS"]), elapsed)
            previous = record["temperatureBoundsK"]
            lo, hi = map(F, previous)
            self.assertTrue(float(lo) <= t <= float(hi))
            self.assertLess(hi-lo, F(1, 4))
            self.assertEqual(list(map(F, record["cumulativeBodyEnergyChangeBoundsJ"])),
                             [200*(lo-300), 200*(hi-300)])

    def test_reflective_split_exposure_zero_hold_and_refusals(self):
        def run(stages):
            return investigate(LINK, "cold", "280", "0", "1", "0", "0.00000005", "100", "280", stages)
        stages = run([("300","20"), ("900","0"), ("200","20")])["stages"]
        self.assertEqual(stages[0]["temperatureBoundsK"], stages[1]["temperatureBoundsK"])
        lo, hi = map(F, stages[-1]["temperatureBoundsK"])
        self.assertTrue(float(lo) <= 380-100*exp(-40/50) <= float(hi))
        for invalid in ([], [("300","-1")], [("-1","0")]):
            with self.assertRaises(ValueError):
                run(invalid)
