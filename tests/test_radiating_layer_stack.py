from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.composite_layer_stack import investigate


class RadiatingLayerTests(TestCase):
    def encloses(self, bounds, value):
        a, b = map(F, bounds)
        self.assertTrue(a <= value <= b)
        self.assertLess(b-a, F(1,10**12))

    def test_radiating_surface_and_contact_jump(self):
        layers = [(LINK,"hot","350","0.001"), (LINK,"hot","230","-0.001")]
        result = investigate(layers, ["0.5"], "380","0", radiation=("1.5","1","0.00000005"))
        self.encloses(result["netHeatToEnclosureBoundsW"], 120)
        self.encloses(result["surfaceTemperatureBoundsK"], 200)
        self.encloses(result["layers"][0]["rightFaceTemperatureBoundsK"], 320)
        self.encloses(result["layers"][1]["leftFaceTemperatureBoundsK"], 260)
        self.assertEqual(result["contactResistancesKPerW"], ["1/2"])
        for layer in result["layers"]:
            self.encloses(layer["rodHeatFlowBoundsW"]["insert"], -90)

    def test_absorption_reflective_and_equal_temperature(self):
        layers = [(LINK,"hot","300","0")]*2
        result = investigate(layers, ["0.5"], "280", "400", radiation=("1","1","0.00000005"))
        a,b = map(F, result["surfaceTemperatureBoundsK"])
        def residual(t):
            return (t-280)/F("1.5") + F("0.00000005")*(t**4-400**4)
        self.assertLessEqual(residual(a), 0)
        self.assertGreaterEqual(residual(b), 0)
        self.assertLess(b-a, F(1,10**12))
        self.assertLess(F(result["netHeatToEnclosureBoundsW"][1]), 0)
        for env, eps in (("900","0"), ("280","1")):
            result = investigate(layers, ["0.5"], "280", env, radiation=("1",eps,"0.00000005"))
            self.encloses(result["surfaceTemperatureBoundsK"], 280)
            self.encloses(result["netHeatToEnclosureBoundsW"], 0)
            self.assertEqual(result["exterior"]["enclosureTemperatureK"], env)
        with self.assertRaises(ValueError):
            investigate(layers, ["0.5"], "280", "400", radiation=("1","1.1","0.00000005"))
