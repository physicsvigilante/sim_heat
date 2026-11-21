from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.rod_generation import investigate
from tools.rod_temperature_profile import peak


class HeatedProfiles(TestCase):
    def check(self, bounds, target):
        a, b = map(F, bounds)
        self.assertLessEqual(a, target)
        self.assertGreaterEqual(b, target)
        self.assertLess(b-a, F(1, 10**12))

    def test_facing_has_an_interior_maximum(self):
        # 160 W from the facing reaches the joint. G_left+G_right = 8 W/K.
        # Joint rises from 330 to 350 K. On the facing T=380+10x-40x².
        result = investigate(*LINK, [("facing", "320")], profiles=True)
        self.check(result["nodeTemperatureBoundsK"]["interface"], 350)
        facing = result["rodPeaks"]["facing"]
        self.check(facing["peakTemperatureBoundsK"], F(380) + F(5, 8))
        self.check(facing["peakPositionFractionFromABounds"], F(1, 8))
        self.check(result["rodPeaks"]["insert"]["peakPositionFractionFromABounds"], 1)

    def test_shared_star_and_flat_profiles(self):
        case = CASES/"star"
        result = investigate(case/"study.json", case, case/"facts.json", STAR, [("first", "160")], profiles=True)
        self.check(result["nodeTemperatureBoundsK"]["joint"], 323)
        self.assertEqual(peak(F(380), F(380), F(0)), 380)
        plain = investigate(*LINK, [("insert", "0")], profiles=True)
        self.check(plain["nodeTemperatureBoundsK"]["interface"], 330)
        self.check(plain["rodPeaks"]["facing"]["peakPositionFractionFromABounds"], 0)

    def test_coupled_bridge_and_unheated_flat_link(self):
        case = CASES.parent/"steady_bridge"
        inputs = (case/"study.json", case, case/"facts.json",
                  "4cc763729e8d71b0abfc0eb5d1c3cc4d08185225104af8640541adcfdbf10bbf")
        result = investigate(*inputs, [("link", "28")], profiles=True)
        # The two junction rises solve 5u-v=14 and -u+3v=14.
        self.check(result["nodeTemperatureBoundsK"]["upper"], 334)
        self.check(result["nodeTemperatureBoundsK"]["lower"], 336)
        link = result["rodPeaks"]["link"]
        self.check(link["peakPositionFractionFromABounds"], F(4, 7))
        self.check(link["peakTemperatureBoundsK"], 334 + F(32, 7))
        flat = investigate(*inputs, [("link", "0")], profiles=True)["rodPeaks"]["link"]
        self.assertEqual(flat["peakPositionFractionFromABounds"], ["0", "1"])
