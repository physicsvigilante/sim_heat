from fractions import Fraction
from pathlib import Path
from unittest import TestCase

from qualification.h1_n13.conduction import prepare
from tools.terminal_response import investigate

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT/"studies/three_terminal"
STAR = "16c414cf443e389560056bb782ac3dea0ac75c40cf2ba103fa0de25bef18def0"
TRIANGLE = "14e792903c1a8fc7c8d8ebb1c9e11e09a1a4474ff7e716de47d770df13177924"


class TerminalResponseTests(TestCase):
    def test_star_and_triangle_have_same_terminal_law(self):
        # Eliminate the star junction using Tj = sum(g_i*T_i)/sum(g_i).
        legs = {"warm": 2, "middle": 3, "cool": 5}
        for topology, pin in (("star", STAR), ("triangle", TRIANGLE)):
            with self.subTest(topology=topology):
                case = CASES/topology
                args = case/"study.json", case, case/"facts.json", pin
                response = investigate(*args)["supplyResponseBoundsWPerK"]
                self.assertEqual(set(response), set(legs))
                for i, gi in legs.items():
                    self.assertEqual(set(response[i]), set(legs))
                    for j, gj in legs.items():
                        expected = (gi if i == j else 0) - Fraction(gi*gj, sum(legs.values()))
                        self.assertEqual(list(map(Fraction, response[i][j])), [expected, expected])
                direct = prepare(*args)["exports"]
                for terminal, expected in (("warm", 130), ("middle", 45), ("cool", -175)):
                    self.assertEqual(direct[terminal+".Q_to_network"], {"unit": "W", "values": [expected]})

    def test_refuse_transient_study(self):
        d = ROOT/"h1/cases/D1"
        with self.assertRaisesRegex(ValueError, "steady storage-free"):
            investigate(d/"study.json", d, ROOT/"h1/reference_cases/D1.json",
                        "92c913bd9a59fee7af14170f459f0959deee8da7d6876e4be222d3c3e94b71c7")
