from fractions import Fraction
from pathlib import Path
from unittest import TestCase

from qualification.h1_n13.conduction import prepare
from tests.test_terminal_response import CASES, STAR, TRIANGLE
from tools.join_thermal_networks import investigate
from tools.terminal_response import investigate as terminal_response


def inputs(case, pin):
    return case / "study.json", case, case / "facts.json", pin


LEFT = inputs(CASES/"star", STAR)
RIGHT = inputs(CASES/"triangle", TRIANGLE)
FULL = inputs(CASES.parent/"joined_terminals",
              "bf8bebb43189f2034ce3be32e3441f14c8b684eaf9e3a19876a2361a0f0482a9")


class JoinedNetworkTests(TestCase):
    def assert_encloses(self, bounds, expected):
        lo, hi = map(Fraction, bounds)
        self.assertLessEqual(lo, expected)
        self.assertGreaterEqual(hi, expected)
        self.assertLess(hi - lo, Fraction(1, 10**12))

    def test_shared_contact_and_four_terminal_law(self):
        joined = investigate(LEFT, RIGHT, "middle", "warm")
        resolved = prepare(*FULL)
        direct_matrix = terminal_response(*FULL)["supplyResponseBoundsWPerK"]
        mapping = {"left.cool": "coolL", "left.warm": "warmL",
                   "right.cool": "coolR", "right.middle": "middleR"}
        # First reduce the left star by hand. The contact then has four neighbours.
        g = dict(zip(mapping, map(Fraction, ("1.5", "0.6", "1", "0.6")), strict=True))
        other = {"left.cool": "left.warm", "left.warm": "left.cool",
                 "right.cool": "right.middle", "right.middle": "right.cool"}
        temperature = {n: Fraction(v) for n, v in joined["imposedTemperaturesK"].items()}
        junction = Fraction(11260, 37)
        self.assert_encloses(joined["contactTemperatureBoundsK"], junction)
        self.assertAlmostEqual(resolved["requests"]["contactT"]["values"][0], float(junction), places=10)
        for i, physical in mapping.items():
            parallel = Fraction(1) if i.startswith("left.") else Fraction(3, 2)
            q = g[i]*(temperature[i]-junction) + parallel*(temperature[i]-temperature[other[i]])
            self.assert_encloses(joined["terminalSupplyBoundsW"][i], q)
            self.assertAlmostEqual(resolved["exports"][physical+".Q_to_network"]["values"][0], float(q), places=10)
            for j in mapping:
                expected = -g[i]*g[j]/sum(g.values())
                if i == j:
                    expected += g[i] + parallel
                if j == other[i]:
                    expected -= parallel
                self.assert_encloses(joined["supplyResponseBoundsWPerK"][i][j], expected)
                self.assert_encloses(direct_matrix[physical][mapping[j]], expected)

    def test_join_requires_a_terminal_of_each_network(self):
        with self.assertRaisesRegex(ValueError, "unknown left contact terminal"):
            investigate(LEFT, RIGHT, "first", "warm")
