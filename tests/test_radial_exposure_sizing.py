from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.radial_exposure_sizing import investigate


class RadialExposureSizingTests(TestCase):
    def test_critical_radius_mid_day_exhaustion_and_night_refreeze(self):
        # Cylinder with k=1, h=5 -> critical radius r_c = 0.2 m.
        # Day (260 s) exhausts 0.20 m (at 257.004 s) before Night can refreeze it,
        # while 0.12 m (265.288 s) and 0.50 m (273.817 s) survive Day and refreeze at Night.
        stages_260 = [
            ("day", "293.15", "5", "280", "260"),
            ("night", "253.15", "5", "250", "200"),
        ]
        # Pass generators for radii, inner_layers, and stages to verify single-pass safety.
        res = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "0.1", (x for x in ()), "1", (r for r in ("0.5", "0.2", "0.12")),
            "0", "0.0000000567", (s for s in stages_260), cylinder_length_m="1",
        )
        self.assertEqual([r["outerRadiusM"] for r in res["sizes"]], ["3/25", "1/5", "1/2"])
        self.assertEqual([r["scheduleStatus"] for r in res["sizes"]],
                         ["survives_schedule", "exhausts_during_schedule", "survives_schedule"])
        self.assertEqual(res["smallestEstablishedSurvivingRadiusM"], "3/25")
        self.assertIsNone(res["sizes"][0]["haltingStageIndex"])
        self.assertEqual(res["sizes"][1]["haltingStageIndex"], 0)
        self.assertEqual(res["sizes"][1]["haltingStageName"], "day")
        self.assertEqual(len(res["sizes"][1]["stages"]), 1)
        self.assertEqual(res["sizes"][1]["finalSolidMassBoundsKg"], ["0", "0"])
        self.assertEqual(res["sizes"][1]["finalLiquidMassBoundsKg"], ["1/20", "1/20"])
        self.assertEqual(len(res["sizes"][0]["stages"]), 2)
        self.assertEqual(res["sizes"][0]["modeledDurationBoundsS"], ["460", "460"])
        self.assertEqual(res["geometry"], "cylinder")
        self.assertFalse(res["nativeExecuted"])
        self.assertFalse(res["nativeQualified"])

        # Extending Day to 270 s eliminates 0.12 m too, leaving only 0.50 m.
        stages_270 = [("day", "293.15", "5", "280", "270"), ("night", "253.15", "5", "250", "200")]
        res_270 = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "0.1", [], "1", ["0.12", "0.2", "0.5"],
            "0", "0.0000000567", stages_270, cylinder_length_m="1",
        )
        self.assertEqual([r["scheduleStatus"] for r in res_270["sizes"]],
                         ["exhausts_during_schedule", "exhausts_during_schedule", "survives_schedule"])
        self.assertEqual(res_270["smallestEstablishedSurvivingRadiusM"], "1/2")

        # Stage-2 (Night) liquid exhaustion: short Day (40 s) + long cold Night (300 s)
        # with small initial liquid (0.015 kg) exhausts liquid during Night on 0.20 m.
        stages_freeze = [("day", "293.15", "5", "280", "40"), ("night", "253.15", "5", "250", "300")]
        res_freeze = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.015",
            "0.1", [], "1", ["0.2", "0.5"],
            "0", "0.0000000567", stages_freeze, cylinder_length_m="1",
        )
        self.assertEqual(res_freeze["sizes"][0]["scheduleStatus"], "exhausts_during_schedule")
        self.assertEqual(res_freeze["sizes"][0]["haltingStageIndex"], 1)
        self.assertEqual(res_freeze["sizes"][0]["haltingStageName"], "night")
        self.assertEqual(len(res_freeze["sizes"][0]["stages"]), 2)
        self.assertEqual(res_freeze["sizes"][0]["finalLiquidMassBoundsKg"], ["0", "0"])

    def test_spherical_nonzero_radiation_and_convection_independent_mpmath(self):
        stages = [
            ("day", "293.15", "10", "310", "100"),
            ("night", "253.15", "8", "240", "120"),
        ]
        res = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "0.1", [], "2", ["0.15", "0.2"], "0.8", "0.0000000567", stages,
        )
        self.assertEqual(res["geometry"], "sphere")
        self.assertEqual(res["smallestEstablishedSurvivingRadiusM"], "3/20")
        with mp.workdps(110):
            t_phase = mp.mpf("273.15")
            sigma = mp.mpf("0.0000000567")
            for row, r_str in zip(res["sizes"], ("0.15", "0.2")):
                r_out = mp.mpf(r_str)
                r_tot = mp.mpf("0.5") + (1 / mp.mpf("0.1") - 1 / r_out) / (8 * mp.pi)
                area = 4 * mp.pi * r_out**2
                cum_e = mp.mpf("0")
                for st, (_, air, h, enc, dur) in zip(row["stages"], stages):
                    t_s = mp.findroot(
                        lambda t: (t - t_phase) / r_tot
                        + area * (mp.mpf(h) * (t - mp.mpf(air))
                                  + mp.mpf("0.8") * sigma * (t**4 - mp.mpf(enc)**4)),
                        t_phase,
                    )
                    q_phase = (t_s - t_phase) / r_tot
                    cum_e += q_phase * mp.mpf(dur)
                    bal = interval(st["bathInflowBoundsW"]) + interval(st["shellOutwardHeatRateBoundsW"])
                    self.assertTrue(bal.low <= 0 <= bal.high)
                lo, hi = map(F, row["cumulativeEnergyIntoBathBoundsJ"])
                self.assertTrue(lo <= F(mp.nstr(cum_e, 95)) <= hi)
                self.assertLess(hi - lo, F(1, 10**11))
                slo, shi = map(F, row["finalSolidMassBoundsKg"])
                llo, lhi = map(F, row["finalLiquidMassBoundsKg"])
                self.assertEqual(slo + lhi, F("0.05"))
                self.assertEqual(shi + llo, F("0.05"))

    def test_unresolved_smaller_radius_blocks_minimum_claim(self):
        probe = investigate(
            LINK, "hot", "cold", "273.15", "334000", "10", "10",
            "0.1", [], "0.4", ["0.15", "0.4"], "0.8", "0.0000000567",
            [("warm", "260", "5", "340", "1000000")],
        )
        self.assertEqual(probe["sizes"][0]["scheduleStatus"], "exhausts_during_schedule")
        t_lo, t_hi = map(F, probe["sizes"][0]["modeledDurationBoundsS"])
        self.assertLess(t_lo, t_hi)
        scale = 10**18
        mid_tick = int(((t_lo + t_hi) / 2) * scale)
        dur_str = f"{mid_tick // scale}.{mid_tick % scale:018d}"
        self.assertTrue(t_lo <= F(dur_str) < t_hi)

        blocked = investigate(
            LINK, "hot", "cold", "273.15", "334000", "10", "10",
            "0.1", [], "0.4", ["0.15", "0.4"], "0.8", "0.0000000567",
            [("warm_edge", "260", "5", "340", dur_str), ("cool", "250", "5", "250", "100")],
        )
        self.assertEqual(blocked["sizes"][0]["scheduleStatus"], "unresolved")
        self.assertEqual(blocked["sizes"][0]["haltingStageIndex"], 0)
        self.assertEqual(blocked["sizes"][0]["haltingStageName"], "warm_edge")
        self.assertEqual(blocked["sizes"][1]["scheduleStatus"], "survives_schedule")
        self.assertIsNone(blocked["smallestEstablishedSurvivingRadiusM"])

    def test_multi_reservoir_star_and_refusals(self):
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        res = investigate(
            inputs, "warm", "cool", "300", "1000", "2", "2",
            "0.1", [], "2", ["0.15", "0.25"], "0.8", "0.0000000567",
            [("cool", "280", "6", "260", "20"), ("hot", "350", "8", "360", "15")],
        )
        self.assertEqual(res["smallestEstablishedSurvivingRadiusM"], "3/20")
        for row in res["sizes"]:
            for st in row["stages"]:
                bal = (interval(st["bathInflowBoundsW"])
                       + interval(st["maintainedReservoirInflowBoundsW"]["middle"])
                       + interval(st["shellOutwardHeatRateBoundsW"]))
                self.assertTrue(bal.low <= 0 <= bal.high)

        # Fixed inner layer preserved in output metadata alongside stocked outer coating.
        layered = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "0.1", [("0.15", "2")], "1", ["0.2", "0.3"], "0.8", "0.0000000567",
            [("day", "293.15", "10", "310", "80"), ("night", "253.15", "8", "240", "100")],
        )
        self.assertEqual(len(layered["innerLayers"]), 1)
        self.assertEqual(layered["innerLayers"][0]["outerRadiusM"], "3/20")
        self.assertEqual(layered["smallestEstablishedSurvivingRadiusM"], "1/5")

        with self.assertRaisesRegex(ValueError, "distinct available outer radii"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                        "0.1", [], "1", [], "0", "0.0000000567", [("d", "293.15", "5", "280", "10")])
        with self.assertRaisesRegex(ValueError, "distinct available outer radii"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                        "0.1", [], "1", ["0.2", "0.20"], "0", "0.0000000567", [("d", "293.15", "5", "280", "10")])
        with self.assertRaisesRegex(ValueError, "one or more exterior stages"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                        "0.1", [], "1", ["0.2"], "0", "0.0000000567", [])
        with self.assertRaisesRegex(ValueError, "distinct"):
            investigate(LINK, "hot", "hot", "273.15", "334000", "0.02", "0.03",
                        "0.1", [], "1", ["0.2"], "0", "0.0000000567", [("d", "293.15", "5", "280", "10")])
