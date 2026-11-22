from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, TRIANGLE
from tools.infer_rod_power import investigate


class InferredRodPowerTests(TestCase):
    def study(self, bounds, known=()):
        return investigate(LINK, "cold", "facing", known, *bounds, "300", "0.2", "1", "0.00000005",
                           air_k="450", h_w_per_m2_k="13.5")

    def test_surface_reading_recovers_facing_power_and_background(self):
        self.assertEqual(self.study(("400","400"))["inferredRodPowerBoundsW"], ["320","320"])
        result = self.study(("400","400"), [("insert","80")])
        self.assertEqual(result["inferredRodPowerBoundsW"], ["80","80"])
        self.assertEqual(result["knownRodPowersW"], {"insert":"80"})

    def test_endpoint_transport_and_refusals(self):
        def exact(t):
            return 4*(F(1,10**8)*(t**4-300**4) + F("2.7")*(t-450) + 2*(t-380))
        result = self.study(("399","401"))
        self.assertEqual(list(map(F,result["inferredRodPowerBoundsW"])), [exact(399), exact(401)])
        for bounds, sources in ((("395","200"), []), (("320","400"), []), (("400","400"), [("facing","3")])):
            with self.assertRaises(ValueError):
                self.study(bounds, sources)

    def test_shielding_by_fixed_temperature_nodes_and_zero_generation(self):
        case = CASES/"triangle"
        args = (case/"study.json", case, case/"facts.json", TRIANGLE)
        with self.assertRaisesRegex(ValueError, "sensitivity"):
            investigate(args, "middle", "second", [], "300","300","300","1","0","0.00000005")
        r = investigate(LINK,"cold","facing",[],"380","380","300","1","0","0.00000005")
        self.assertEqual(r["inferredRodPowerBoundsW"], ["0","0"])
