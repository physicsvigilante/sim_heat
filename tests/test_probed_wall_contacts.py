from fractions import Fraction
from unittest import TestCase

from tests.test_loaded_thermal_ports import LINK
from tools.probed_wall_contacts import investigate


class ProbedContactsTests(TestCase):
    layers = [(LINK, "hot", "300", "0")] * 4

    def solve(self, left="420", right="270", probe="360", contacts=("?", "0", "?"),
              qlo="40", qhi="40", after=2):
        return investigate(self.layers, contacts, left, right, qlo, qhi, after, probe)

    def assert_contact(self, contact, index, lo, hi):
        self.assertEqual(contact["afterLayer"], index)
        self.assertEqual(list(map(Fraction, contact["resistanceBoundsKPerW"])), [lo, hi])

    def test_thermometer_identifies_each_contact(self):
        for probe, r1, r2 in (("360", Fraction(1, 2), Fraction(5, 4)),
                              ("350", Fraction(3, 4), 1)):
            for reversed_wall in (False, True):
                result = (self.solve("270", "420", probe) if reversed_wall
                          else self.solve(probe=probe))
                first, second = result["inferredContacts"]
                self.assert_contact(first, 1, r2 if reversed_wall else r1, r2 if reversed_wall else r1)
                self.assert_contact(second, 3, r1 if reversed_wall else r2, r1 if reversed_wall else r2)

    def test_shared_current_band(self):
        a, b = self.solve(qlo="39", qhi="41")["inferredContacts"]
        self.assert_contact(a, 1, Fraction(60, 41) - 1, Fraction(60, 39) - 1)
        self.assert_contact(b, 3, Fraction(90, 41) - 1, Fraction(90, 39) - 1)

    def test_refuses_unidentifiable_or_inconsistent_measurements(self):
        for params in ({"contacts": ("?", "0.1", "?")}, {"contacts": ("?", "?", "0")},
                       {"contacts": ("0", "0", "?")}, {"after": 0}, {"after": True},
                       {"probe": "420"}, {"probe": "405"}, {"qlo": "0"}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.solve(**params)
