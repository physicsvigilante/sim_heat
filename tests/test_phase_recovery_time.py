from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_join_thermal_networks import LEFT, RIGHT
from tools.phase_exposure_sequence import investigate


class PhaseRecoveryTests(TestCase):
    def run_sequence(self, network, stages, recovery):
        return investigate(network, "middle", "warm", "300", "200000", "0.2", "0.3",
                           ("1", "0.8", "0.0000000567"), stages, recovery)

    def test_restore_after_melting_or_freezing(self):
        with mp.workdps(100):
            def bath_power(enclosure):
                def joint(face):
                    return (2*face + 2300)/10
                face = mp.findroot(lambda t: 2*(t-joint(t)) +
                                   mp.mpf("0.00000004536")*(t**4-enclosure**4), 325)
                return 3*(joint(face)-300)
            for network in (LEFT, RIGHT):
                for first, second in ((420, 310), (310, 420)):
                    q1, q2 = bath_power(first), bath_power(second)
                    recovery = self.run_sequence(network, [(str(first), "1000"), (str(second), "200")],
                                                 str(second))["inventoryRecovery"]
                    energy = 1000*q1+200*q2
                    expected = -energy/q2
                    for field, value in (("durationBoundsS", expected), ("energyIntoBathBoundsJ", -energy),
                                         ("endBoundsS", expected+1200)):
                        low, high = map(F, recovery[field])
                        self.assertTrue(low <= F(mp.nstr(value, 85)) <= high)
                        self.assertLess(high-low, F(1, 10**10))
                    self.assertEqual(recovery["finalSolidKg"], "1/5")
                    self.assertEqual(recovery["finalLiquidKg"], "3/10")

    def test_zero_time_wrong_direction_and_depletion(self):
        r = investigate(LEFT, "middle", "warm", "280", "200000", "1", "1",
                        ("1", "1", "0.0000000567"), [("280", "10")], "350")
        self.assertEqual(r["inventoryRecovery"]["durationBoundsS"], ["0", "0"])
        for schedule, recovery in (([("420", "1000")], "420"), ([("310", "3000")], "420")):
            with self.assertRaises(ValueError):
                self.run_sequence(LEFT, schedule, recovery)
