from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_join_thermal_networks import LEFT, RIGHT
from tests.test_loaded_thermal_ports import LINK
from tools.phase_exposure_sequence import investigate


class PhaseEntropyTests(TestCase):
    def test_restored_bath_and_distinct_exterior_temperatures(self):
        with mp.workdps(100):
            def powers(env):
                def joint(face):
                    return (2*face+2300)/10
                face = mp.findroot(lambda t: 2*(t-joint(t)) +
                                   mp.mpf("0.00000004536")*(t**4-env**4), 330)
                return 3*(joint(face)-300), 5*(joint(face)-280)

            q1, s1 = powers(420)
            q2, s2 = powers(310)
            t = -1000*q1/q2
            hot = -(q1+s1)*1000/420
            cool = -(q2+s2)*t/310
            support = (s1*1000+s2*t)/280
            for net in (LEFT, RIGHT):
                out = investigate(net, "middle", "warm", "300", "200000", "0.2", "0.3",
                                  ("1", "0.8", "0.0000000567"), [("420", "1000")], "310", track_entropy=True)
                entropy = out["entropy"]
                self.assertEqual(entropy["bathChangeBoundsJPerK"], ["0"]*2)
                for interval, expected in (
                        (out["stages"][0]["enclosureEntropyChangeBoundsJPerK"], hot),
                        (out["inventoryRecovery"]["enclosureEntropyChangeBoundsJPerK"], cool),
                        (entropy["supportChangeBoundsJPerK"]["cool"], support),
                        (entropy["enclosuresChangeBoundsJPerK"], hot+cool),
                        (entropy["generatedBoundsJPerK"], hot+cool+support)):
                    low, high = map(F, interval)
                    self.assertTrue(low <= F(mp.nstr(expected, 85)) <= high)
                    self.assertLess(high-low, F(1, 10**10))
                self.assertGreater(F(entropy["generatedBoundsJPerK"][0]), 0)

    def test_first_depletion_equilibrium_and_zero_kelvin(self):
        args = (LINK, "hot", "cold", "275", "1000", "1", "1.5", ("1", "1", "0.0000001"))
        # A 200 K surface emits 150 W to 100 K and receives 150 W from the bath.
        result = investigate(*args, [("100", "500")], track_entropy=True)["entropy"]
        self.assertEqual(list(map(F, result["bathChangeBoundsJPerK"])), [F(-1500, 275)]*2)
        low, high = map(F, result["generatedBoundsJPerK"])
        self.assertTrue(low <= 15 - F(1500, 275) <= high)
        equal = investigate(*args, [("275", "5")], track_entropy=True)["entropy"]
        self.assertEqual(equal["generatedBoundsJPerK"], ["0"]*2)
        with self.assertRaisesRegex(ValueError, "positive reservoir"):
            investigate(*args, [("0", "1")], track_entropy=True)
        self.assertNotIn("entropy", investigate(*args, [("0", "1")], track_reservoir_energy=True))
