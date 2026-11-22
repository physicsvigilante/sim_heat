from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from unittest import TestCase

from qualification.h1_n13.conduction import prepare
from tests.test_temperature_passages import TWIN, TWIN_PIN
from tools.body_relaxation import investigate

CASE = Path(__file__).resolve().parents[1]/"studies/loaded_star"
PIN = "1fccce839e69c67230819498fb1da973ac614264378ada75ae7d0b13b7816ff8"
ARGS = CASE/"study.json", CASE, CASE/"facts.json", PIN


class BodyRelaxationTests(TestCase):
    def test_loaded_star_coefficients_and_entire_transient(self):
        result = investigate(*ARGS)
        for field, expected in (("effectiveConductanceBoundsWPerK", Fraction(21, 10)),
                                ("equilibriumTemperatureBoundsK", Fraction(2160, 7)),
                                ("timeConstantBoundsSeconds", 100), ("initialBodyInflowBoundsW", -87)):
            lo, hi = map(Fraction, result[field])
            self.assertLessEqual(lo, expected)
            self.assertGreaterEqual(hi, expected)
            self.assertLess(hi-lo, Fraction(1, 10**12))
        full = prepare(*ARGS)
        with localcontext() as ctx:
            ctx.prec = 80
            eq = Decimal(2160)/7
            targets = (("temperature", 10**8), ("energy", 10**5))
            for name, scale in targets:
                values = full["requests"][name]["values"]
                self.assertEqual(len(values), 1001)
                radius = Fraction(full["maxErrorToBudgetBySeries"]["requests"][name])/scale
                for i, actual in enumerate(values):
                    decay = (-Decimal(i)/200).exp()
                    reference = eq + (350-eq)*decay if name == "temperature" else 8700*(decay-1)
                    self.assertLessEqual(abs(Fraction(actual)-Fraction(reference)),
                                         radius + Fraction(1, 10**70), (name, i))

    def test_two_bodies_refused_even_with_a_bath(self):
        with self.assertRaisesRegex(ValueError, "one body"):
            investigate(TWIN/"study.json", TWIN, TWIN/"facts.json", TWIN_PIN)
