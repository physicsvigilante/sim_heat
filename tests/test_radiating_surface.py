from fractions import Fraction as F
from unittest import TestCase

from tests.test_composite_wall import CASE, FACTS_PIN
from tests.test_join_thermal_networks import LEFT
from tools.radiating_surface import investigate

WALL = CASE/"study.json", CASE, CASE/"facts.json", FACTS_PIN


class RadiatingSurfaceTests(TestCase):
    def test_exact_surface_and_energy_rate(self):
        law = investigate(*WALL, "cold", "0", "4.5", "1", "0.00000005")
        for key, exact in (("surfaceTemperatureBoundsK", 200), ("netHeatToEnclosureBoundsW", 360)):
            lo, hi = map(F, law[key])
            self.assertTrue(lo <= exact <= hi)
            self.assertLess(hi-lo, F(1,10**12))

    def test_star_can_absorb_or_emit(self):
        for t in (280, 390):
            law = investigate(*LEFT, "middle", str(t), "0.02", "0.8", "0.0000000567")
            lo, hi = map(F, law["surfaceTemperatureBoundsK"])
            qlo, qhi = map(F, law["netHeatToEnclosureBoundsW"])
            # Hand reduction of the actual branches gives 10/21 K/W.
            def residual(x):
                return (x-F(2160,7))*F(21,10) + F("0.0000000567")*F(".016")*(x**4-t**4)
            self.assertLessEqual(residual(lo), 0)
            self.assertGreaterEqual(residual(hi), 0)
            self.assertLess(hi-lo, F(1,10**12))
            self.assertLess(qhi-qlo, F(1,10**12))
            self.assertTrue(qhi < 0 if t == 390 else qlo > 0)

    def test_reflective_surface_and_equal_temperatures(self):
        for environment, emissivity in (("280","0"), ("380","1")):
            law = investigate(*WALL, "cold", environment, "0.02", emissivity, "0.0000000567")
            self.assertEqual(law["surfaceTemperatureBoundsK"], ["380","380"])
            self.assertEqual(law["netHeatToEnclosureBoundsW"], ["0","0"])

    def test_invalid_exterior_refused(self):
        for values in (("-1","1","1","1"), ("280","0","1","1"), ("280","1","1.1","1"),
                       ("280","1","1","0"), ("280","1","nan","1")):
            with self.assertRaises(ValueError):
                investigate(*WALL, "cold", *values)
