from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK, LEFT, RIGHT
from tools.join_variable_conductors import investigate


class JoinedMaterialTests(TestCase):
    def encloses(self, bounds, value):
        low, high = map(F, bounds)
        self.assertLessEqual(low, value)
        self.assertLessEqual(value, high)
        self.assertLess(high-low, F(1, 10**12))

    def test_dissimilar_composite_walls_forward_and_reverse(self):
        def drive(left, right):
            return investigate((LINK, left, "280", "0.00625"), (LINK, right, "280", "0"))
        forward = drive("cold", "hot")
        self.encloses(forward["contactTemperatureBoundsK"], 340)
        self.encloses(forward["leftToRightHeatRateBoundsW"], 120)
        self.encloses(forward["left"]["rodHeatFlowBoundsW"]["insert"], -90)
        self.encloses(forward["right"]["terminalSupplyBoundsW"]["cold"], -120)
        reverse = drive("hot", "cold")
        a, b = (F(t)-280 for t in reverse["contactTemperatureBoundsK"])
        # Cold-side integral x+x^2/320 equals hot-side drop 100-x.
        self.assertLessEqual(a*a/320+2*a, 100)
        self.assertGreaterEqual(b*b/320+2*b, 100)
        qlo, qhi = map(F, reverse["leftToRightHeatRateBoundsW"])
        self.assertTrue(-120 < qlo <= qhi < -100)

    def test_four_retained_baths_and_constant_conductivity_limit(self):
        out = investigate((LEFT, "middle", "320", "0"), (RIGHT, "warm", "290", "0"))
        contact = F(11260, 37)
        self.encloses(out["contactTemperatureBoundsK"], contact)
        self.encloses(out["leftToRightHeatRateBoundsW"], (F(2160, 7)-contact)*F(21, 10))
        self.assertEqual(set(out["left"]["terminalSupplyBoundsW"]), {"cool", "warm"})
        self.assertEqual(set(out["right"]["terminalSupplyBoundsW"]), {"cool", "middle"})

    def test_equal_baths_and_refusals(self):
        side = LINK, "cold", "380", "-0.1"
        out = investigate(side, side)
        self.encloses(out["contactTemperatureBoundsK"], 380)
        self.encloses(out["leftToRightHeatRateBoundsW"], 0)
        with self.assertRaisesRegex(ValueError, "positive"):
            investigate((LINK, "cold", "280", "-0.01"), (LINK, "hot", "280", "0"))
        with self.assertRaisesRegex(ValueError, "unknown"):
            investigate((LINK, "other", "280", "0"), side)
