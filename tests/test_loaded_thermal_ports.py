from fractions import Fraction as F
from unittest import TestCase

from qualification.h1_n13.conduction import prepare
from tests.test_composite_wall import CASE, FACTS_PIN
from tests.test_join_thermal_networks import LEFT, RIGHT, inputs
from tests.test_terminal_response import CASES
from tools.loaded_thermal_ports import investigate

LINK = inputs(CASE, FACTS_PIN)
FULL = inputs(CASES.parent/"loaded_thermal_ports", "137e707179de334e72df970facb62c5eb29c46e49a8462985f0660c6d7d2c476")


class LoadedPortTests(TestCase):
    def encloses(self, bounds, value):
        lo, hi = map(F, bounds)
        self.assertTrue(lo <= value <= hi)
        self.assertLess(hi-lo, F(1, 10**12))

    def test_loaded_temperatures_and_oriented_transfer(self):
        law = investigate(LEFT, LINK, RIGHT, "middle", "warm")
        open_left, open_right = F(2160,7), F(1195,4)
        rl, rw, rr = F(10,21), F(1,2), F(5,8)
        q = (open_left-open_right)/(rl+rw+rr)
        tl, tr = open_left-q*rl, open_right+q*rr
        for field, value in (("leftOpenTemperatureBoundsK", open_left), ("rightOpenTemperatureBoundsK", open_right),
                             ("leftPortResistanceBoundsKPerW", rl), ("rightPortResistanceBoundsKPerW", rr),
                             ("linkResistanceBoundsKPerW", rw), ("leftLoadedTemperatureBoundsK", tl),
                             ("rightLoadedTemperatureBoundsK", tr), ("leftToRightHeatRateBoundsW", q)):
            self.encloses(law[field], value)
        direct = prepare(*FULL)
        for key, exact, scale in (("contactT", tl, 10**8), ("rightPortT", tr, 10**8), ("wallFlow", -q, 10**8)):
            actual, = direct["requests"][key]["values"]
            radius = F(direct["maxErrorToBudgetBySeries"]["requests"][key])/scale
            self.assertLessEqual(abs(F(actual)-exact), radius)

    def test_reversed_and_balanced_drives(self):
        reverse = investigate(RIGHT, LINK, LEFT, "warm", "middle")
        self.assertLess(F(reverse["leftToRightHeatRateBoundsW"][1]), 0)
        same = investigate(LEFT, LINK, LEFT, "cool", "cool")
        self.encloses(same["leftToRightHeatRateBoundsW"], 0)

    def test_overdetermined_link_and_unknown_port_refused(self):
        with self.assertRaisesRegex(ValueError, "exactly two terminals"):
            investigate(LEFT, LEFT, RIGHT, "middle", "warm")
        with self.assertRaisesRegex(ValueError, "unknown released terminal"):
            investigate(LEFT, LINK, RIGHT, "first", "warm")
