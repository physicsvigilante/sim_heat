from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.radiating_surface import investigate


class MixedSurfaceTests(TestCase):
    def study(self, air, h, eps="1", enclosure="300"):
        return investigate(*LINK, "cold", enclosure, "0.2", eps, "0.00000005", air_k=air, h_w_per_m2_k=h)

    def check(self, result, field, target):
        a, b = map(F, result[field])
        self.assertLessEqual(a, target)
        self.assertGreaterEqual(b, target)
        self.assertLess(b-a, F(1, 10**12))

    def test_air_drives_heat_into_wall_and_to_cold_enclosure(self):
        # At 400 K the wall absorbs 40 W; the enclosure gains 175 W.
        result = self.study("450", "21.5")
        for field, expected in (("surfaceTemperatureBoundsK", 400), ("netHeatToEnclosureBoundsW", 175),
                                ("netHeatToAirBoundsW", -215), ("conductorToSurfaceHeatBoundsW", -40)):
            self.check(result, field, expected)

    def test_reflector_and_zero_film_limits(self):
        result = self.study("300", "10", eps="0")
        self.check(result, "surfaceTemperatureBoundsK", 340)
        self.check(result, "netHeatToAirBoundsW", 80)
        self.check(result, "netHeatToEnclosureBoundsW", 0)
        radiating = investigate(*LINK, "cold", "300", "0.2", "1", "0.00000005")
        zero_film = self.study("999", "0")
        for field in ("surfaceTemperatureBoundsK", "netHeatToEnclosureBoundsW"):
            self.assertEqual(zero_film[field], radiating[field])
        self.check(zero_film, "netHeatToAirBoundsW", 0)

    def test_isothermal_and_invalid(self):
        result = self.study("380", "15", enclosure="380")
        for field in ("netHeatToEnclosureBoundsW", "netHeatToAirBoundsW", "conductorToSurfaceHeatBoundsW"):
            self.check(result, field, 0)
        for air, h in ((None, "2"), ("300", None), ("300", "-2")):
            with self.subTest(air=air, h=h), self.assertRaises(ValueError):
                self.study(air, h)
