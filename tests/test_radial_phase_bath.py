from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.radial_phase_bath import investigate


class RadialPhaseBath(TestCase):
    def test_spherical_ice_vessel_melts_or_freezes_until_one_phase_exhausts(self):
        for air, mode in (("293.15","melting"), ("253.15","freezing")):
            r = investigate(LINK,"hot","cold","273.15","334000","0.02","0.03","10000",
                            "0.1",[("0.2","2")],"280","0","0.0000000567",
                            air_k=air,h_w_per_m2_k="10")
            with mp.workdps(110):
                total = mp.mpf("0.5") + 5/(8*mp.pi) + 1/(mp.mpf("1.6")*mp.pi)
                q = (mp.mpf(air)-mp.mpf("273.15"))/total
                mass = mp.mpf("0.02" if mode == "melting" else "0.03")
                for limits, target in [(r["bathInflowDuringPlateauBoundsW"], q),
                                       (r["exhaustionTimeBoundsS"], mass*334000/abs(q))]:
                    lo, hi = map(F, limits)
                    self.assertTrue(lo <= F(mp.nstr(target,95)) <= hi)
                    self.assertLess(hi-lo,F(1,10**12))
            self.assertEqual(r["phaseProcess"], mode)
            self.assertEqual(r["plateauStatus"], "exhausted")
            key = "remainingSolidBoundsKg" if mode == "melting" else "remainingLiquidBoundsKg"
            self.assertEqual(r[key], ["0","0"])

    def test_other_reservoir_can_melt_bath_even_with_zero_shell_heat(self):
        case = CASES/"star"
        inputs = (case/"study.json",case,case/"facts.json",STAR)
        result = investigate(inputs,"warm","cool","300","1000","1","1","10",
                             "0.1",[("0.2","2")],"310","0","0.0000000567")
        self.assertEqual(result["radialShell"]["outwardHeatRateBoundsW"], ["0","0"])
        # Released third branch carries zero heat; the remaining 2 and 3 W/K
        # arms in series conduct 36 W from 330 K middle to the 300 K phase bath.
        for limits, target in [(result["bathInflowDuringPlateauBoundsW"],36),
                               (result["maintainedReservoirInflowBoundsW"]["middle"],-36),
                               (result["remainingSolidBoundsKg"], F("0.64"))]:
            lo,hi = map(F,limits)
            self.assertTrue(lo <= target <= hi)
            self.assertLess(hi-lo,F(1,10**12))
        with self.assertRaisesRegex(ValueError,"distinct"):
            investigate(inputs,"warm","warm","300","1000","1","1","10",
                        "0.1",[("0.2","2")],"310","0","0.0000000567")
