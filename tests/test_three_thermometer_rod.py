from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.rod_generation import investigate as generate
from tools.three_thermometer_rod import investigate


class ThreeThermometers(TestCase):
    def test_unequal_spacing_composes_with_forward_probes(self):
        readings = []
        for x in ("0.25", "0.5", "1"):
            probe = generate(*LINK, [("facing", "320"), ("insert", "80")],
                             probe=("facing", x))["probe"]
            lo, hi = map(F, probe["temperatureBoundsK"])
            self.assertEqual(lo, hi)
            reading = str(float(lo))  # chosen dyadic temperatures are exact
            readings.append((x, reading, reading))
        result = investigate(LINK, "facing", readings[::-1])
        self.assertEqual(result["uniformPowerBoundsW"], ["320", "320"])
        self.assertFalse(result["nativeExecuted"])

    def test_independent_temperature_bands_and_linear_profile(self):
        # Midpoint excess over the endpoint mean is P/(8G), with G=4 W/K.
        for middle, expected in [(("375","375"), ["320","320"]),
                                 (("374","376"), ["288","352"]),
                                 (("365","365"), ["0","0"])]:
            r = investigate(LINK, "facing", [("0","380","380"), ("0.5",*middle), ("1","350","350")])
            self.assertEqual(r["uniformPowerBoundsW"], expected)

    def test_refuses_unresolved_sign_and_coincident_probes(self):
        for middle in [("0.5","364","366"), ("1","375","375")]:
            with self.subTest(middle=middle), self.assertRaises(ValueError):
                investigate(LINK, "facing", [("0","380","380"), middle, ("1","350","350")])
