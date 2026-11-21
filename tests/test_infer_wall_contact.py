from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.infer_wall_contact import investigate


class InferredContactTests(TestCase):
    def test_nonlinear_stack_both_directions(self):
        layers = [(LINK,"hot","370","0.002"),(LINK,"cold","340","-0.003"),(LINK,"hot","290","0.005")]
        for rev in (False, True):
            result = investigate(layers[::-1] if rev else layers, ["?", "0.25"] if rev else ["0.25","?"],
                                 "280" if rev else "380", "380" if rev else "280", "40","40")
            for key, expected in (("contactResistanceBoundsKPerW", F("0.75")),
                                  ("leftContactFaceBoundsK", 300 if rev else 330),
                                  ("rightContactFaceBoundsK", 330 if rev else 300)):
                lo, hi = map(F, result[key])
                self.assertTrue(lo <= expected <= hi)
                self.assertLess(hi-lo, F(1,10**12))

    def test_constant_layer_measurement_band_and_refusals(self):
        layers = [(LINK,"hot","300","0")]*3
        def infer(lo, hi, contacts=("?", "0.25")):
            return investigate(layers, contacts, "380", "280", lo, hi)
        result = infer("39","41")
        a,b = map(F, result["contactResistanceBoundsKPerW"])
        self.assertLessEqual(a, F(100,41)-F("1.75"))
        self.assertGreaterEqual(b, F(100,39)-F("1.75"))
        self.assertLess(b-a, F("0.13"))
        for lo,hi in (("0","40"),("42","40"),("57","58"),("60","61"),("500","500")):
            with self.assertRaises(ValueError):
                infer(lo,hi)
        with self.assertRaises(ValueError):
            infer("40","40", ("?","?"))
