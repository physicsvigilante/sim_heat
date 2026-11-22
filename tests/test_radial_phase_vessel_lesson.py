from fractions import Fraction as F
import json
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "JEE_RADIAL_PHASE_VESSEL.md"
FACTS_SHA = "f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b"
STUDY_ARGS = [
    "--study", "studies/composite_wall/study.json",
    "--root", "studies/composite_wall",
    "--facts", "studies/composite_wall/facts.json",
    "--facts-sha256", FACTS_SHA,
    "--phase-port", "hot",
    "--surface-port", "cold",
    "--transition-k", "273.15",
    "--latent-heat-j-per-kg", "334000",
    "--solid-kg", "0.02",
    "--liquid-kg", "0.03",
]


def run_cli(module, extra):
    proc = subprocess.run(
        [sys.executable, "-B", "-m", module, *STUDY_ARGS, *extra],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def midpoint(pair):
    lo, hi = map(F, pair)
    return float((lo + hi) / 2)


class RadialPhaseVesselLessonTests(TestCase):
    def test_walkthrough_document_and_all_four_cli_replays_match_stated_numbers(self):
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
            "8.751",
            "11.116",
        ):
            self.assertIn(token, text)

        # Part 1: forward melting through spherical shell
        p1 = run_cli("tools.radial_phase_bath", [
            "--duration-s", "120", "--inner-radius-m", "0.1", "--layer", "0.2", "2",
            "--enclosure-k", "300", "--emissivity", "0.8", "--sigma", "0.0000000567",
            "--air-k", "293.15", "--h-w-per-m2-k", "10",
        ])
        self.assertAlmostEqual(midpoint(p1["bathInflowDuringPlateauBoundsW"]), 26.598, places=3)
        self.assertAlmostEqual(midpoint(p1["radialShell"]["surfaces"][0]["temperatureBoundsK"]), 286.449, places=3)
        self.assertAlmostEqual(midpoint(p1["radialShell"]["surfaces"][-1]["temperatureBoundsK"]), 291.741, places=3)
        self.assertAlmostEqual(midpoint(p1["remainingSolidBoundsKg"]), 0.010444, places=6)
        self.assertAlmostEqual(midpoint(p1["exhaustionTimeBoundsS"]), 251.145, places=3)

        # Part 2: cylindrical critical-radius hold-time sizing at 260 s and 270 s
        p2 = run_cli("tools.phase_shell_sizing", [
            "--hold-duration-s", "260", "--inner-radius-m", "0.1", "--coating-k", "1",
            "--radius-m", "0.5", "--radius-m", "0.2", "--radius-m", "0.12",
            "--enclosure-k", "280", "--emissivity", "0", "--sigma", "0.0000000567",
            "--cylinder-length-m", "1", "--air-k", "293.15", "--h-w-per-m2-k", "5",
        ])
        self.assertEqual([r["holdStatus"] for r in p2["sizes"]],
                         ["meets_hold_time", "fails_hold_time", "meets_hold_time"])
        self.assertEqual(p2["smallestEstablishedMeetingHoldRadiusM"], "3/25")
        for row, expected_t in zip(p2["sizes"], (265.288, 257.004, 273.817)):
            self.assertAlmostEqual(midpoint(row["exhaustionTimeBoundsS"]), expected_t, places=3)

        p2_270 = run_cli("tools.phase_shell_sizing", [
            "--hold-duration-s", "270", "--inner-radius-m", "0.1", "--coating-k", "1",
            "--radius-m", "0.5", "--radius-m", "0.2", "--radius-m", "0.12",
            "--enclosure-k", "280", "--emissivity", "0", "--sigma", "0.0000000567",
            "--cylinder-length-m", "1", "--air-k", "293.15", "--h-w-per-m2-k", "5",
        ])
        self.assertEqual(p2_270["smallestEstablishedMeetingHoldRadiusM"], "1/2")

        # Part 3: day/night melting and refreezing cycle
        p3 = run_cli("tools.radial_phase_exposure", [
            "--inner-radius-m", "0.1", "--layer", "0.2", "2",
            "--emissivity", "0.8", "--sigma", "0.0000000567",
            "--stage", "day", "293.15", "10", "310", "100",
            "--stage", "night", "253.15", "8", "240", "120",
        ])
        self.assertTrue(p3["completedAllStages"])
        self.assertAlmostEqual(midpoint(p3["stages"][0]["bathInflowBoundsW"]), 30.827, places=3)
        self.assertAlmostEqual(midpoint(p3["stages"][1]["bathInflowBoundsW"]), -26.426, places=3)
        self.assertAlmostEqual(midpoint(p3["cumulativeEnergyIntoBathBoundsJ"]), -88.436, places=3)
        self.assertAlmostEqual(midpoint(p3["finalSolidMassBoundsKg"]), 0.020265, places=6)

        # Part 4: inverse film calibration from melted ice alone
        p4 = run_cli("tools.phase_film_calibration", [
            "--duration-s", "120", "--melted-kg", "0.0095", "0.0096",
            "--inner-radius-m", "0.1", "--layer", "0.2", "2",
            "--air-k", "293.15", "--enclosure-k", "300",
            "--emissivity", "0.8", "--sigma", "0.0000000567",
        ])
        h_lo, h_hi = map(F, p4["convectionCoefficientBoundsWPerM2K"])
        self.assertTrue(h_lo <= F(10) <= h_hi)
        self.assertAlmostEqual(float(h_lo), 8.751, places=3)
        self.assertAlmostEqual(float(h_hi), 11.116, places=3)
