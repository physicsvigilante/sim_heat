from fractions import Fraction as F
import json
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.shell_environments import investigate


class ShellEnvironments(TestCase):
    def solve(self, conditions, budget="127"):
        return investigate(LINK, "cold", "0.1", [], "1", ["0.5","0.2","0.12"], budget,
                           "0","0.0000000567",conditions,"1")

    def test_one_size_for_warm_and_cold_air(self):
        conditions = [("winter","280","5","280"), ("summer","483","5","483")]
        result = self.solve(conditions)
        self.assertEqual(result["smallestEstablishedWithinBudgetRadiusM"], "1/2")
        self.assertEqual([x["status"] for x in result["sizes"]], ["over_budget","over_budget","within_budget"])
        for row in result["sizes"]:
            cold, hot = row["environments"]["winter"], row["environments"]["summer"]
            self.assertGreater(F(cold["outwardHeatRateBoundsW"][0]), 0)
            self.assertLess(F(hot["outwardHeatRateBoundsW"][1]), 0)
            self.assertEqual(row["worstMagnitudeBoundsW"],hot["magnitudeBoundsW"])
        self.assertEqual(self.solve(conditions[::-1]),result)
        self.assertEqual(self.solve(conditions[:1])["smallestEstablishedWithinBudgetRadiusM"], "3/25")

    def test_exact_equality_and_distinct_condition_names(self):
        calm = ("calm","280","0","280")
        self.assertEqual(self.solve([calm],budget="0")["smallestEstablishedWithinBudgetRadiusM"], "3/25")
        for cases in ([], iter(()), [calm,calm]):
            with self.assertRaises(ValueError):
                self.solve(cases)

    def test_environment_names_survive_json_round_trip(self):
        active = ("1","483","5","483")
        calm = ("01","280","0","280")
        result = self.solve([active,calm])
        self.assertEqual(json.loads(json.dumps(result)), result)
        self.assertEqual(set(result["environments"]), {"1","01"})
        for row in result["sizes"]:
            self.assertEqual(set(row["environments"]), {"1","01"})
            self.assertEqual(row["status"], row["environments"]["1"]["status"])
        with self.assertRaisesRegex(ValueError, "name"):
            self.solve([(1,*active[1:]), ("1",*calm[1:])])

    def test_each_environment_requires_explicit_air_and_film(self):
        for air, film in [(None,None), (None,"0"), ("280",None)]:
            with self.subTest(air=air, film=film), self.assertRaises(ValueError):
                self.solve([("case",air,film,"270")])
