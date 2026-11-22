from fractions import Fraction
from unittest import TestCase

from qualification.h1_n13.conduction import prepare
from tests.test_join_thermal_networks import LEFT, RIGHT, inputs
from tests.test_terminal_response import CASES
from tests.test_composite_wall import CASE, FACTS_PIN
from tools.two_contact_join import investigate


PAIRS = ("middle", "warm"), ("cool", "middle")
FULL = inputs(CASES.parent/"two_contacts", "76cbdba2b79184ef560b7cb74d336fedd459492d499216221267b3b1a36c2329")


class TwoContactTests(TestCase):
    def encloses(self, bounds, exact):
        lo, hi = map(Fraction, bounds)
        self.assertTrue(lo <= exact <= hi)
        self.assertLess(hi-lo, Fraction(1, 10**12))

    def test_exact_coupled_contacts_and_direct_six_rod_model(self):
        joined = investigate(LEFT, RIGHT, *PAIRS)
        direct = prepare(*FULL)
        hot, cold = "left.warm", "right.cool"
        self.assertEqual(joined["terminals"], [hot, cold])
        g = Fraction(1230,1261)
        for row in (hot, cold):
            for col in (hot, cold):
                self.encloses(joined["supplyResponseBoundsWPerK"][row][col], g if row == col else -g)
        for key, source, rate in ((hot, "warmL", 100*g), (cold, "coolR", -100*g)):
            self.encloses(joined["terminalSupplyBoundsW"][key], rate)
            self.assertAlmostEqual(direct["exports"][source+".Q_to_network"]["values"][0], float(rate), places=10)
        for key, request, rise in (("contact1", "contactT", 486), ("contact2", "secondContact", 496)):
            expected = 280 + Fraction(100*rise, 1261)
            self.encloses(joined["contactTemperatureBoundsK"][key], expected)
            self.assertAlmostEqual(direct["requests"][request]["values"][0], float(expected), places=10)

    def test_relabeling_contacts_preserves_terminal_law(self):
        base = investigate(LEFT, RIGHT, *PAIRS)
        swap = investigate(LEFT, RIGHT, *reversed(PAIRS))
        self.assertEqual(base["terminalSupplyBoundsW"], swap["terminalSupplyBoundsW"])
        self.assertEqual(base["contactTemperatureBoundsK"]["contact1"],
                         swap["contactTemperatureBoundsK"]["contact2"])

    def test_duplicate_unknown_and_unanchored_connections_refused(self):
        for bad in (("middle", "cool"), ("unknown", "middle")):
            with self.assertRaisesRegex(ValueError, "distinct left"):
                investigate(LEFT, RIGHT, PAIRS[0], bad)
        wall = inputs(CASE, FACTS_PIN)
        from tools.terminal_response import investigate as response
        a, b = response(*wall)["terminals"]
        with self.assertRaisesRegex(ValueError, "maintained external terminal"):
            investigate(wall, wall, (a, b), (b, a))
