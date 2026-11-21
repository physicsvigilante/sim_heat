from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK, LEFT, RIGHT
from tools.join_variable_conductors import investigate


class ContactResistanceTests(TestCase):
    def encloses(self, bounds, value):
        lo, hi = map(F, bounds)
        self.assertTrue(lo <= value <= hi)
        self.assertLess(hi-lo, F(1, 10**12))

    def test_nonlinear_layer_with_known_faces(self):
        # The mean of the hot layer's face temperatures equals its reference.
        # Its integrated heat current is 2*(380-340) = 80 W.
        result = investigate((LINK, "cold", "360", "0.01"), (LINK, "hot", "280", "0"), "0.25")
        self.encloses(result["leftFaceTemperatureBoundsK"], 340)
        self.encloses(result["rightFaceTemperatureBoundsK"], 320)
        self.encloses(result["leftToRightHeatRateBoundsW"], 80)
        self.encloses(result["left"]["rodHeatFlowBoundsW"]["insert"], -60)
        self.encloses(result["right"]["terminalSupplyBoundsW"]["cold"], -80)

    def test_four_baths_forward_and_reverse(self):
        a, b = (LEFT, "middle", "300", "0"), (RIGHT, "warm", "300", "0")
        left_open, right_open = F(2160,7), F(1195,4)
        q = (left_open-right_open)/(F(10,21)+F("0.75")+F(5,8))
        for left, right, sign in ((a,b,1), (b,a,-1)):
            result = investigate(left, right, "0.75")
            self.encloses(result["leftToRightHeatRateBoundsW"], sign*q)
            faces = left_open-q*F(10,21), right_open+q*F(5,8)
            for key, expected in zip(("leftFaceTemperatureBoundsK", "rightFaceTemperatureBoundsK"),
                                     faces if sign == 1 else faces[::-1]):
                self.encloses(result[key], expected)
        self.assertEqual(investigate(a,b), investigate(a,b,"0.0"))
        with self.assertRaises(ValueError):
            investigate(a,b,"-1")
