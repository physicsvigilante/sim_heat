from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.powered_wall_surface import investigate
from tools.radiating_surface import investigate as unpowered


class PoweredSurfaceTests(TestCase):
    def check(self, bounds, target):
        a, b = map(F, bounds)
        self.assertLessEqual(a, target)
        self.assertGreaterEqual(b, target)
        self.assertLess(b-a, F(1, 10**12))

    def test_internal_heating_with_hot_air_and_cold_enclosure(self):
        result = investigate(LINK, "cold", [("facing","320")], "300", "0.2", "1", "0.00000005",
                             air_k="450", h_w_per_m2_k="13.5", profiles=True)
        for key, value in (("heatedOpenTemperatureBoundsK",420), ("surfaceTemperatureBoundsK",400),
                           ("netHeatToAirBoundsW",-135), ("netHeatToEnclosureBoundsW",175),
                           ("conductorToSurfaceHeatBoundsW",40)):
            self.check(result[key], value)
        self.check(result["nodeTemperatureBoundsK"]["interface"], 410)
        facing = result["rodPeaks"]["facing"]
        self.check(facing["peakTemperatureBoundsK"], F(3285, 8))
        self.check(facing["peakPositionFractionFromABounds"], F(7, 8))
        self.assertEqual(set(result["maintainedBathSupplyBoundsW"]), {"hot"})
        self.check(result["maintainedBathSupplyBoundsW"]["hot"], -280)

    def test_adiabatic_surface_and_zero_generation(self):
        result = investigate(LINK, "cold", [("insert","80")], "300", "0.2", "0", "0.00000005")
        self.check(result["surfaceTemperatureBoundsK"], 410)
        self.check(result["conductorToSurfaceHeatBoundsW"], 0)
        self.check(result["maintainedBathSupplyBoundsW"]["hot"], -80)
        args = ("300", "0.2", "1", "0.00000005")
        old = unpowered(*LINK, "cold", *args)
        new = investigate(LINK, "cold", [("insert","0")], *args)
        self.assertEqual(new["surfaceTemperatureBoundsK"], old["surfaceTemperatureBoundsK"])
        self.assertEqual(new["netHeatToEnclosureBoundsW"], old["netHeatToEnclosureBoundsW"])
