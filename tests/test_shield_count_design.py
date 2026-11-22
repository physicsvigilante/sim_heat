from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.radiative_gap import investigate as forward
from tools.shield_count_design import investigate, required_count


class ShieldDesignTests(TestCase):
    def run_design(self, limit, *, support=None, faces=("1", "1"), left="cold", right="hot"):
        return investigate(LINK, LINK, left, right, "0.02", "1", "1", "0.0000000567", faces, limit, support)

    def test_minimal_count_with_solid_temperature_drops(self):
        for l, r in (("cold", "hot"), ("hot", "cold")):
            for limit in ("7", "3", "0.5"):
                count = self.run_design(limit, left=l, right=r)["guaranteedSufficientCount"]
                self.assertGreater(count, 0)
                for n in (count-1, count):
                    result = forward(LINK, LINK, l, r, "0.02", "1", "1", "0.0000000567",
                                     shield_stack=[("1", "1")]*n if n else None)
                    a, b = sorted(abs(F(x)) for x in result["leftToRightHeatRateBoundsW"])
                    if n == count:
                        self.assertLessEqual(b, F(limit))
                    else:
                        self.assertGreater(a, F(limit))
        self.assertEqual(self.run_design("7")["guaranteedSufficientCount"], 2)

    def test_bypass_and_perfect_reflection(self):
        self.assertEqual(self.run_design("60", support=LINK)["status"], "no_finite_count")
        self.assertEqual(self.run_design("0")["minimumRequiredCountBounds"], [None, None])
        self.assertEqual(self.run_design("0", faces=("0", "1"))["minimumRequiredCountBounds"], [1, 1])
        self.assertEqual(self.run_design("0", left="hot", right="hot")["minimumRequiredCountBounds"], [0, 0])
        self.assertEqual(self.run_design("100")["minimumRequiredCountBounds"], [0, 0])

    def test_exact_integer_boundary_and_support_floor(self):
        # At Q=1 W the plate temperatures are 3 K and 2 K. Black gaps each add one unit.
        args = (F(4), F(1), F(1), F(1))
        faces = [F(1)]*4
        self.assertEqual(required_count(*args, F(0), F(1), F(4,65), faces), 3)
        self.assertIsNone(required_count(*args, F(1), F(1), F(4,65), faces))
        self.assertEqual(required_count(*args, F(1), F(1), F(4,65), [F(1), F(1), F(0), F(1)]), 1)
