"""Adversarial checks for the successor, using the preserved first-run data."""
from fractions import Fraction
import gzip
import json
from math import nextafter
from unittest import TestCase

from qualification.h1_n13.heldout.oracle import HERE
from tools.verify_twinbridge import verify


def original():
    with gzip.open(HERE / "first-output.json.gz", "rt", encoding="utf-8") as stream:
        return json.load(stream)


class ErrorRatioTests(TestCase):
    def test_original_reproduces_frozen_oracle_summary(self):
        self.assertEqual(verify(original()), json.loads((HERE / "oracle-results.json").read_bytes()))

    def test_understated_maxima_rejected_with_values_unchanged(self):
        for family, name, factor in (("requests", "lowerFlow", 0),
                                     ("exports", "amber.T", Fraction(1, 2)),
                                     ("integrals", "bath.Q_to_network", Fraction(1, 2))):
            with self.subTest(family=family, name=name):
                data = original()
                ratios = data["maxErrorToBudgetBySeries"][family]
                actual = Fraction(ratios[name])
                self.assertGreater(actual, 0)
                ratios[name] = str(factor * actual)
                with self.assertRaisesRegex(ValueError, rf"understated error ratio for {family}\.{name} at sample"):
                    verify(data)

    def test_static_budget_uses_spacing_at_later_sample(self):
        data = original()
        values = data["exports"]["upper.G"]["values"]
        self.assertEqual(values[0], 2.0)
        self.assertEqual(values[57], 2.0)
        values[57] = nextafter(2.0, 0.0)
        data["maxErrorToBudgetBySeries"]["exports"]["upper.G"] = "1"
        with self.assertRaisesRegex(ValueError, r"understated error ratio for exports\.upper\.G at sample 57$"):
            verify(data)
