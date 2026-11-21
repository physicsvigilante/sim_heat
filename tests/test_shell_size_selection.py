from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp
from tests.test_loaded_thermal_ports import LINK
from tools.shell_size_selection import investigate


class ShellSizes(TestCase):
    def run_case(self, air, budget="127", radii=("0.5","0.2","0.12"), h="5"):
        return investigate(LINK,"cold","0.1",[],"1",radii,budget,"300","0","0.0000000567",
                           "1",air_k=air,h_w_per_m2_k=h)

    def test_thicker_can_pass_then_fail_then_pass_in_both_directions(self):
        for air in ("280","480"):
            r=self.run_case(air)
            self.assertEqual([x["status"] for x in r["sizes"]], ["within_budget","over_budget","within_budget"])
            self.assertEqual(r["smallestEstablishedWithinBudgetRadiusM"], "3/25")
            with mp.workdps(100):
                for row in r["sizes"]:
                    radius=F(row["outerRadiusM"])
                    x=mp.mpf(radius.numerator)/radius.denominator
                    resistance=mp.mpf("0.5")+mp.log(10*x)/(2*mp.pi)+1/(2*mp.pi*x*5)
                    q=F(mp.nstr((380-int(air))/resistance,90))
                    lo, hi=map(F,row["outwardHeatRateBoundsW"])
                    self.assertTrue(lo <= q <= hi)

    def test_budget_equality_no_fit_and_duplicate_choices(self):
        self.assertEqual(self.run_case("280", budget="0", h="0")["smallestEstablishedWithinBudgetRadiusM"], "3/25")
        self.assertIsNone(self.run_case("280", budget="0")["smallestEstablishedWithinBudgetRadiusM"])
        with self.assertRaisesRegex(ValueError,"distinct"):
            self.run_case("280",radii=["0.2","0.20"])

    def test_smaller_unresolved_option_prevents_minimum_claim(self):
        r = investigate(LINK,"cold","0.1",[],"1",["0.5","1"],"122.313994961348177145",
                        "280","1","0.0000000567","1")
        self.assertEqual([row["status"] for row in r["sizes"]], ["unresolved","within_budget"])
        self.assertIsNone(r["smallestEstablishedWithinBudgetRadiusM"])
