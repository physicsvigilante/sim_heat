from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK, LEFT
from tools.nonlinear_radiating_wall import investigate


class NonlinearSurfaceTests(TestCase):
    def encloses(self, bounds, expected):
        lo, hi = map(F, bounds)
        self.assertTrue(lo <= expected <= hi)
        self.assertLess(hi-lo, F(1, 10**12))

    def test_exact_surface_branch_split_and_constant_limit(self):
        # Integral of 1 + (T-200)/400 from 200 to 380 is 220.5 K.
        for slope, area, power in (("0.0025", "5.5125", 441), ("0", "4.5", 360)):
            result = investigate(LINK, "cold", "200", slope, "0", area, "1", "0.00000005")
            self.encloses(result["surfaceTemperatureBoundsK"], 200)
            self.encloses(result["netHeatToEnclosureBoundsW"], power)
            self.encloses(result["terminalSupplyBoundsW"]["hot"], power)
            self.encloses(result["rodHeatFlowBoundsW"]["insert"], -F(3, 4)*power)

    def test_three_terminal_absorption(self):
        result = investigate(LEFT, "middle", "300", "-0.001", "400", "0.5", "0.8", "0.00000005")
        a, b = map(F, result["surfaceTemperatureBoundsK"])
        def potential(t):
            return (t-300)-(t-300)**2/F(2000)
        def balance(t):
            return (F("1.5")*(potential(t)-potential(280)) + F(".6")*(potential(t)-potential(380))
                    + F(".00000002")*(t**4-400**4))
        self.assertLessEqual(balance(a), 0)
        self.assertGreaterEqual(balance(b), 0)
        self.assertLess(b-a, F(1, 10**12))
        self.assertLess(F(result["netHeatToEnclosureBoundsW"][1]), 0)

    def test_reflective_surface_and_material_domain(self):
        result = investigate(LINK, "cold", "380", "-0.01", "900", "1", "0", "0.00000005")
        self.encloses(result["surfaceTemperatureBoundsK"], 380)
        self.encloses(result["netHeatToEnclosureBoundsW"], 0)
        with self.assertRaisesRegex(ValueError, "positive"):
            investigate(LINK, "cold", "380", "-0.01", "900", "1", "1", "0.00000005")
