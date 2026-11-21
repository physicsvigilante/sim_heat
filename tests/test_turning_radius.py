from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_loaded_thermal_ports import LINK
from tools.radiating_radial_layers import turning_radius


class TurningRadiusTests(TestCase):
    def test_bracket_encloses_stationary_energy_balance(self):
        for length in (None,"1"):
            answer = turning_radius(LINK,"cold","0.1",[("0.12","2")],"280","0.8",
                                    "0.0000000567",length,"1.4")
            lo,hi = map(F,answer["turningRadiusBoundsM"])
            with mp.workdps(100):
                u = mp.mpf(".8")*mp.mpf(".0000000567")
                n = 2 if length is None else 1
                def stationary_balance(r):
                    # An extremum at nonzero heat flow requires 4 eps sigma T^3 = n k/r.
                    t = (n*2/(4*u*r))**(mp.mpf(1)/3)
                    if n == 2:
                        area, shell = 4*mp.pi*r*r,(10-1/r)/(8*mp.pi)
                    else:
                        area, shell = 2*mp.pi*r,mp.log(10*r)/(4*mp.pi)
                    return (380-t)/(mp.mpf(".5")+shell)-u*area*(t**4-280**4)
                ref = mp.findroot(stationary_balance, (mp.mpf(".4"),mp.mpf("1.2")))
                self.assertTrue(lo <= F(mp.nstr(ref,80)) <= hi)
            self.assertLess(hi-lo,F(1,10**12))
            self.assertEqual(answer["extremumWithinBracket"],"maximum")
            self.assertEqual(answer["lowerEndpoint"]["outerRadiusSensitivity"]["heatRateMagnitudeTrend"],"increasing")
            self.assertEqual(answer["upperEndpoint"]["outerRadiusSensitivity"]["heatRateMagnitudeTrend"],"decreasing")

    def test_reject_equal_drives_same_trend_or_reversed_search(self):
        for end,env in (("0.11","280"),("0.13","280"),("1.4","380")):
            with self.assertRaises(ValueError):
                turning_radius(LINK,"cold","0.1",[("0.12","2")],env,"0.8","0.0000000567",None,end)
