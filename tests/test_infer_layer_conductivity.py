from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.infer_layer_conductivity import investigate


class ConductivityInferenceTests(TestCase):
    def test_buried_panel_and_reverse(self):
        layers = [(LINK,"hot","370","0.002"),(LINK,"cold","335","-0.003"),(LINK,"hot","290","0.005")]
        for rev in (False, True):
            r = investigate(layers[::-1] if rev else layers, ["0.75","0.5"] if rev else ["0.5","0.75"],
                            "280" if rev else "380", "380" if rev else "280", "40","40", 2)
            for key, expected in (("effectiveReferenceConductanceBoundsWPerK",4),
                                  ("commonRodConductivityMultiplierBounds",2),
                                  ("leftLayerFaceBoundsK",330 if rev else 340),
                                  ("rightLayerFaceBoundsK",340 if rev else 330)):
                a,b = map(F,r[key])
                self.assertTrue(a <= expected <= b)
                self.assertLess(b-a,F(1,10**12))

    def test_single_layer_and_refusals(self):
        layer = (LINK,"hot","300","0")
        result = investigate([layer], [], "380","280","39","41",1)
        a,b = map(F,result["commonRodConductivityMultiplierBounds"])
        self.assertLessEqual(a,F(39,200))
        self.assertGreaterEqual(b,F(41,200))
        self.assertLess(b-a,F("0.011"))
        for layers, contacts, qlo, qhi, index in (([layer],[],"0","40",1),([layer],[],"40","40",0),
                ([layer]*2,[],"40","40",1),([layer]*2,["0.5"],"99","101",2)):
            with self.assertRaises(ValueError):
                investigate(layers, contacts, "380","280",qlo,qhi,index)

    def test_integrated_law_away_from_reference_temperature(self):
        # The mean conductivity is 1.5 times the reference across this span.
        result = investigate([(LINK, "hot", "280", "0.01")], [], "380", "280", "300", "300", 1)
        self.assertEqual(list(map(F, result["commonRodConductivityMultiplierBounds"])), [1, 1])
