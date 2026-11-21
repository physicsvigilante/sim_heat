from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.radiative_gap import investigate


def solve(shield, first="cold", second="hot"):
    return investigate(LINK, LINK, first, second, "0.02", "0.8", "0.5", "0.0000000567", shield)


class RadiationShieldTests(TestCase):
    def test_two_radiosity_balances_agree_with_the_rod_rates(self):
        result = solve(("0.6", "0.3"))
        qlo, qhi = map(F, result["leftToRightHeatRateBoundsW"])
        slo, shi = map(F, result["shieldTemperatureBoundsK"])
        area_sigma = F(".02")*F(".0000000567")
        dl = 1/F(".8")+1/F(".6")-1
        dr = 1/F(".3")+1/F(".5")-1
        # Compute the required shield fourth power independently from each wall
        # and the separate reflected and emitted radiosity balances.
        def left(q):
            return (380-q/2)**4-q*dl/area_sigma
        def right(q):
            return (280+q/2)**4+q*dr/area_sigma
        self.assertGreaterEqual(left(qlo),right(qlo))
        self.assertLessEqual(left(qhi),right(qhi))
        low, high = F(0), F(100)
        for _ in range(120):
            trial = (low+high)/2
            if left(trial) > right(trial):
                low = trial
            else:
                high = trial
        self.assertTrue(qlo <= low <= high <= qhi)
        self.assertLessEqual(slo**4, right(low))
        self.assertGreaterEqual(shi**4, right(high))
        self.assertLess(shi-slo,F(1,10**12))
        self.assertLess(qhi,F(solve(None)["leftToRightHeatRateBoundsW"][0]))

    def test_blocked_gaps_and_equilibrium(self):
        for faces, expected in ((("0","1"),"280"),(("1","0"),"380"),(("0","0"),None)):
            r = solve(faces)
            self.assertEqual(r["leftToRightHeatRateBoundsW"], ["0","0"])
            self.assertEqual(r["shieldTemperatureBoundsK"], [expected,expected] if expected else None)
            self.assertEqual(r["shieldTemperatureStatus"], "bounded" if expected else "undetermined")
        self.assertEqual(solve(("0.2","0.9"),"cold","cold")["shieldTemperatureBoundsK"], ["380","380"])

    def test_bad_face_inputs(self):
        for faces in (("1",), ("0.1","1.2"), "11", ("0.1","-0.1")):
            with self.assertRaises(ValueError):
                solve(faces)
