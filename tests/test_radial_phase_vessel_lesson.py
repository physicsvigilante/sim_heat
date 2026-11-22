from fractions import Fraction as F
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "JEE_RADIAL_PHASE_VESSEL.md"


def extract_fenced_commands(text):
    blocks = re.findall(r"```sh\n(.*?)\n```", text, flags=re.DOTALL)
    return [shlex.split(block.strip()) for block in blocks]


def run_documented_command(tokens):
    assert tokens[0] == "python"
    proc = subprocess.run(
        [sys.executable, *tokens[1:]],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def midpoint(pair):
    lo, hi = map(F, pair)
    return float((lo + hi) / 2)


class RadialPhaseVesselLessonTests(TestCase):
    def test_walkthrough_document_and_literal_cli_replays_match_stated_numbers(self):
        text = DOC.read_text(encoding="utf-8")
        for token in (
            "tools.radial_phase_bath",
            "tools.phase_shell_sizing",
            "tools.radial_phase_exposure",
            "tools.phase_film_calibration",
            "26.598 W",
            "251.145 s",
            "265.288",
            "257.004",
            "273.817",
            "−88.436 J",
            "0.020265 kg",
            "26.441",
            "26.720",
            "291.631",
            "291.826",
            "8.750",
            "11.117",
        ):
            self.assertIn(token, text)

        commands = extract_fenced_commands(text)
        self.assertEqual(len(commands), 4)
        self.assertEqual(
            [cmd[3] for cmd in commands],
            [
                "tools.radial_phase_bath",
                "tools.phase_shell_sizing",
                "tools.radial_phase_exposure",
                "tools.phase_film_calibration",
            ],
        )

        # Part 1: forward melting through spherical shell (literal documented command)
        p1 = run_documented_command(commands[0])
        self.assertAlmostEqual(midpoint(p1["bathInflowDuringPlateauBoundsW"]), 26.598, places=3)
        self.assertAlmostEqual(midpoint(p1["radialShell"]["surfaces"][0]["temperatureBoundsK"]), 286.449, places=3)
        self.assertAlmostEqual(midpoint(p1["radialShell"]["surfaces"][-1]["temperatureBoundsK"]), 291.741, places=3)
        self.assertAlmostEqual(midpoint(p1["remainingSolidBoundsKg"]), 0.010444, places=6)
        self.assertAlmostEqual(midpoint(p1["exhaustionTimeBoundsS"]), 251.145, places=3)

        # Part 2: cylindrical critical-radius hold-time sizing at 260 s (literal command) and 270 s variation
        p2 = run_documented_command(commands[1])
        self.assertEqual([r["holdStatus"] for r in p2["sizes"]],
                         ["meets_hold_time", "fails_hold_time", "meets_hold_time"])
        self.assertEqual(p2["smallestEstablishedMeetingHoldRadiusM"], "3/25")
        for row, expected_t in zip(p2["sizes"], (265.288, 257.004, 273.817)):
            self.assertAlmostEqual(midpoint(row["exhaustionTimeBoundsS"]), expected_t, places=3)

        cmd_270 = ["270" if tok == "260" else tok for tok in commands[1]]
        p2_270 = run_documented_command(cmd_270)
        self.assertEqual(p2_270["smallestEstablishedMeetingHoldRadiusM"], "1/2")

        # Part 3: day/night melting and refreezing cycle (literal documented command)
        p3 = run_documented_command(commands[2])
        self.assertTrue(p3["completedAllStages"])
        self.assertAlmostEqual(midpoint(p3["stages"][0]["bathInflowBoundsW"]), 30.827, places=3)
        self.assertAlmostEqual(midpoint(p3["stages"][1]["bathInflowBoundsW"]), -26.426, places=3)
        self.assertAlmostEqual(midpoint(p3["cumulativeEnergyIntoBathBoundsJ"]), -88.436, places=3)
        self.assertAlmostEqual(midpoint(p3["finalSolidMassBoundsKg"]), 0.020265, places=6)

        # Part 4: inverse film calibration from melted ice alone (literal documented command)
        # Verify strict outward enclosure of the stated printed brackets.
        p4 = run_documented_command(commands[3])
        q_lo, q_hi = map(F, p4["inferredBathInflowBoundsW"])
        self.assertTrue(F("26.441") <= q_lo <= q_hi <= F("26.720"))
        ts_lo, ts_hi = map(F, p4["outerSurfaceTemperatureBoundsK"])
        self.assertTrue(F("291.631") <= ts_lo <= ts_hi <= F("291.826"))
        h_lo, h_hi = map(F, p4["convectionCoefficientBoundsWPerM2K"])
        self.assertTrue(F("8.750") <= h_lo <= F(10) <= h_hi <= F("11.117"))
