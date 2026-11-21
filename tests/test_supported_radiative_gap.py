from fractions import Fraction as F
from unittest import TestCase

from tests.test_join_thermal_networks import LEFT, inputs
from tests.test_loaded_thermal_ports import LINK
from tests.test_steady_bridge import CASE, BASE
from tools.radiative_gap import investigate

SUPPORT = inputs(CASE, BASE)


class SupportedGapTests(TestCase):
    def test_separate_path_rates_and_wall_balances(self):
        for forward, shield in ((True, None), (False, ("0.6","0.3"))):
            with self.subTest(forward=forward, shield=shield):
                ports = ("cold","hot") if forward else ("hot","cold")
                law = investigate(LINK, LINK, *ports, "0.02","0.8","0.5","0.0000000567",
                                  shield, SUPPORT)
                hot, cold = (380,280) if forward else (280,380)
                # Balanced bridge has two series branches of 1 and 2 K/W.
                g = F(1)+F(1,2)
                resistance = 1/F(".8")+1/F(".5")-1
                if shield:
                    resistance += 1/F(".6")+1/F(".3")-1
                k = F(".02")*F(".0000000567")/resistance
                def channels(q):
                    l, r = hot-q/2, cold+q/2
                    return g*(l-r), k*(l**4-r**4)
                lo, hi = sorted((F(0),F(hot-cold)))
                for _ in range(128):
                    mid = (lo+hi)/2
                    if mid < sum(channels(mid)):
                        lo = mid
                    else:
                        hi = mid
                for key, exact in (("leftToRightHeatRateBoundsW",(lo,hi)),
                                   ("supportHeatRateBoundsW",(channels(hi)[0],channels(lo)[0])),
                                   ("radiativeHeatRateBoundsW",(channels(hi)[1],channels(lo)[1]))):
                    lower, upper = map(F,law[key])
                    self.assertTrue(lower <= exact[0] <= exact[1] <= upper, key)
                    self.assertLess(upper-lower,F(1,10**12))

    def test_reflecting_surface_still_transmits_heat_through_support(self):
        law = investigate(LINK, LINK, "cold","hot","0.02","0","1","0.0000000567",
                          support_inputs=SUPPORT)
        lo, hi = map(F, law["supportHeatRateBoundsW"])
        self.assertTrue(lo <= 60 <= hi)
        self.assertEqual(law["radiativeHeatRateBoundsW"],["0","0"])
        self.assertEqual(law["sources"]["support"]["factsSha256"], BASE)

    def test_refuse_third_support_terminal_and_stale_pin(self):
        for support in (LEFT, (*SUPPORT[:-1],"0"*64)):
            with self.assertRaises(ValueError):
                investigate(LINK, LINK, "cold","hot","0.02","1","1","0.0000000567",
                            support_inputs=support)
