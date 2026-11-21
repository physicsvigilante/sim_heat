from fractions import Fraction as F
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.two_heater_calorimetry import investigate


class TwoHeaterTests(TestCase):
    def test_signed_bath_supply_and_independent_rod_powers(self):
        for rods in (["facing", "insert"], ["insert", "facing"]):
            for baths in ([("hot","0","0"), ("cold","-320","-320")],
                          [("cold","-320","-320"), ("hot","0","0")]):
                self.assertEqual(investigate(LINK, rods, baths)["inferredRodPowerBoundsW"],
                                 {"facing":["240","240"], "insert":["80","80"]})

    def test_measured_bands_with_known_third_heater(self):
        # A known 40 W in the strip removes an extra 10 W at hot and 30 W at cold.
        result = investigate(LINK, ["facing","insert"], [("hot","-11","-9"), ("cold","-351","-349")],
                             [("strip","40")])
        for rod, expected in (("facing",240), ("insert",80)):
            a,b = map(F,result["inferredRodPowerBoundsW"][rod])
            self.assertEqual((a,b), (expected-2, expected+2))

    def test_indistinguishable_heaters_and_bad_measurements(self):
        rods = ["facing","insert"]
        baths = [("hot","0","0"),("cold","-320","-320")]
        for unknowns, measures, known in ((["strip","insert"], baths, []), (rods, [baths[0]]*2, []),
                (rods, [("hot","250","250"), baths[1]], []), (rods,baths,[("facing","1")]),
                (rods, [("hot","1","0"), baths[1]], [])):
            with self.subTest(unknowns=unknowns, measures=measures), self.assertRaises(ValueError):
                investigate(LINK, unknowns, measures, known)
