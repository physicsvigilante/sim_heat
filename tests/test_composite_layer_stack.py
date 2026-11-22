from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LEFT, LINK
from tools.composite_layer_stack import investigate


class LayerStackTests(TestCase):
    def encloses(self, bounds, expected):
        a, b = map(F, bounds)
        self.assertTrue(a <= expected <= b)
        self.assertLess(b-a, F(1, 10**12))

    def test_three_distinct_materials_with_two_temperature_jumps(self):
        layers = [(LINK, "hot", "370", "0.002"), (LINK, "cold", "340", "-0.003"),
                  (LINK, "hot", "290", "0.005")]
        for reverse in (False, True):
            sequence = layers[::-1] if reverse else layers
            gaps = ["0.75","0.25"] if reverse else ["0.25","0.75"]
            result = investigate(sequence, gaps, "280" if reverse else "380", "380" if reverse else "280")
            q = -40 if reverse else 40
            self.encloses(result["leftToRightHeatRateBoundsW"], q)
            faces = [(380,360),(350,330),(300,280)]
            if reverse:
                faces = [(b,a) for a,b in faces[::-1]]
            for record, (a,b) in zip(result["layers"], faces, strict=True):
                self.encloses(record["leftFaceTemperatureBoundsK"], a)
                self.encloses(record["rightFaceTemperatureBoundsK"], b)
                self.encloses(record["rodHeatFlowBoundsW"]["insert"],
                              -F(3,4)*q if record["leftTerminal"] == "hot" else F(3,4)*q)

    def test_constant_equal_baths_and_refusals(self):
        layer = (LINK, "hot", "300", "0")
        self.encloses(investigate([layer]*4, ["0","0.25","0.75"], "300","360")["leftToRightHeatRateBoundsW"], -20)
        self.encloses(investigate([layer], [], "300","300")["leftToRightHeatRateBoundsW"], 0)
        for layers, gaps in (([], []), ([layer]*2, []), ([layer]*2, ["-1"]),
                             ([(LEFT,"middle","300","0")], []), ([(LINK,"absent","300","0")], [])):
            with self.assertRaises(ValueError):
                investigate(layers, gaps, "300","360")
