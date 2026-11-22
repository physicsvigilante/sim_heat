from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.radial_phase_exposure import investigate


class RadialPhaseExposureTests(TestCase):
    def test_day_night_melt_and_refreeze_cycle_with_radiation_and_convection(self):
        stages = [
            ("day", "293.15", "10", "310", "100"),
            ("night", "253.15", "8", "240", "120"),
        ]
        res = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "0.1", [("0.2", "2")], "0.8", "0.0000000567", stages,
        )
        self.assertTrue(res["completedAllStages"])
        self.assertEqual(res["finalPlateauStatus"], "coexisting")
        self.assertEqual(res["modeledDurationBoundsS"], ["220", "220"])
        self.assertEqual([s["phaseProcess"] for s in res["stages"]], ["melting", "freezing"])
        self.assertEqual(res["geometry"], "sphere")
        self.assertFalse(res["nativeExecuted"])
        self.assertFalse(res["nativeQualified"])

        with mp.workdps(110):
            t_phase = mp.mpf("273.15")
            r_tot = mp.mpf("0.5") + 5 / (8 * mp.pi)
            area = mp.mpf("0.16") * mp.pi
            sigma = mp.mpf("0.0000000567")
            cum_e = mp.mpf("0")
            for row, (_, air, h, enc, dur) in zip(res["stages"], stages):
                t_s = mp.findroot(
                    lambda t: (t - t_phase) / r_tot
                    + area * (mp.mpf(h) * (t - mp.mpf(air))
                              + mp.mpf("0.8") * sigma * (t**4 - mp.mpf(enc)**4)),
                    t_phase,
                )
                q_shell = (t_phase - t_s) / r_tot
                q_phase = -q_shell
                cum_e += q_phase * mp.mpf(dur)
                for limits, target in [
                    (row["bathInflowBoundsW"], q_phase),
                    (row["shellOutwardHeatRateBoundsW"], q_shell),
                    (row["outerSurfaceTemperatureBoundsK"], t_s),
                    (row["cumulativeEnergyIntoBathBoundsJ"], cum_e),
                    (row["solidMassBoundsKg"], mp.mpf("0.02") - cum_e / 334000),
                    (row["liquidMassBoundsKg"], mp.mpf("0.03") + cum_e / 334000),
                ]:
                    lo, hi = map(F, limits)
                    self.assertTrue(lo <= F(mp.nstr(target, 95)) <= hi)
                    self.assertLess(hi - lo, F(1, 10**11))
                bal = (interval(row["bathInflowBoundsW"])
                       + interval(row["shellOutwardHeatRateBoundsW"]))
                self.assertTrue(bal.low <= 0 <= bal.high)
                slo, shi = map(F, row["solidMassBoundsKg"])
                llo, lhi = map(F, row["liquidMassBoundsKg"])
                self.assertEqual(slo + lhi, F("0.05"))
                self.assertEqual(shi + llo, F("0.05"))

    def test_cylindrical_mid_schedule_exhaustion_halts_without_fabricating_later_stages(self):
        stages = [
            ("warm_1", "260", "5", "340", "60"),
            ("warm_2", "260", "5", "340", "200"),
            ("cold_after", "240", "10", "240", "100"),
        ]
        res = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "0.1", [("0.2", "2")], "0.8", "0.0000000567", stages,
            cylinder_length_m="1",
        )
        self.assertFalse(res["completedAllStages"])
        self.assertEqual(len(res["stages"]), 2)
        self.assertEqual(res["stages"][0]["plateauStatus"], "coexisting")
        self.assertEqual(res["stages"][1]["plateauStatus"], "exhausted")
        self.assertEqual(res["finalPlateauStatus"], "exhausted")
        self.assertEqual(res["finalSolidMassBoundsKg"], ["0", "0"])
        self.assertEqual(res["finalLiquidMassBoundsKg"], ["1/20", "1/20"])
        self.assertEqual(res["geometry"], "cylinder")

        with mp.workdps(110):
            t_phase = mp.mpf("273.15")
            r_tot = mp.mpf("0.5") + mp.log(2) / (4 * mp.pi)
            area = mp.mpf("0.4") * mp.pi
            sigma = mp.mpf("0.0000000567")
            t_s = mp.findroot(
                lambda t: (t - t_phase) / r_tot
                + area * (5 * (t - 260) + mp.mpf("0.8") * sigma * (t**4 - mp.mpf("340")**4)),
                t_phase,
            )
            q_phase = (t_s - t_phase) / r_tot
            t_exh = mp.mpf("0.02") * 334000 / q_phase
            lo, hi = map(F, res["modeledDurationBoundsS"])
            self.assertTrue(lo <= F(mp.nstr(t_exh, 95)) <= hi)
            self.assertLess(hi - lo, F(1, 10**12))

    def test_exact_equilibrium_stage_and_unresolved_near_zero_stages(self):
        eq_seq = investigate(
            LINK, "hot", "cold", "300", "334000", "0.02", "0.03",
            "0.1", [("0.2", "2")], "1", "0.00000005",
            [
                ("melt", "352", "1", "290", "50"),
                ("hold_eq", "351.3595", "1", "290", "100"),
                ("freeze", "350", "1", "290", "50"),
            ],
        )
        self.assertTrue(eq_seq["completedAllStages"])
        self.assertEqual([s["phaseProcess"] for s in eq_seq["stages"]],
                         ["melting", "equilibrium", "freezing"])
        self.assertEqual(eq_seq["stages"][1]["bathInflowBoundsW"], ["0", "0"])
        self.assertEqual(eq_seq["stages"][1]["cumulativeEnergyIntoBathBoundsJ"],
                         eq_seq["stages"][0]["cumulativeEnergyIntoBathBoundsJ"])
        self.assertEqual(eq_seq["stages"][1]["solidMassBoundsKg"],
                         eq_seq["stages"][0]["solidMassBoundsKg"])

        # Sub-resolution near-zero stage that cannot exhaust either phase advances cleanly.
        safe = investigate(
            LINK, "hot", "cold", "300", "334000", "0.02", "0.03",
            "0.1", [("0.2", "2")], "1", "0.00000005",
            [
                ("near_zero", "351.359500000000000001", "1", "290", "100"),
                ("melt", "352", "1", "290", "50"),
            ],
        )
        self.assertTrue(safe["completedAllStages"])
        self.assertEqual(safe["stages"][0]["phaseProcess"], "unresolved")
        self.assertEqual(safe["stages"][0]["plateauStatus"], "coexisting")
        self.assertEqual(safe["stages"][1]["phaseProcess"], "melting")

        # Sub-resolution near-zero stage with tiny solid inventory halts as uncertain.
        uncertain = investigate(
            LINK, "hot", "cold", "300", "1", "0.000000000000000001", "0.03",
            "0.1", [("0.2", "2")], "1", "0.00000005",
            [
                ("near_zero", "351.359500000000000001", "1", "290", "100"),
                ("later", "352", "1", "290", "50"),
            ],
        )
        self.assertFalse(uncertain["completedAllStages"])
        self.assertEqual(len(uncertain["stages"]), 1)
        self.assertEqual(uncertain["stages"][0]["phaseProcess"], "unresolved")
        self.assertEqual(uncertain["finalPlateauStatus"], "exhaustion_time_uncertain")

        # Dual-phase unresolved-direction exhaustion: both solid and liquid are tiny
        # enough that worst-case positive or negative flow could exhaust either phase.
        dual_uncertain = investigate(
            LINK, "hot", "cold", "300", "1",
            "0.000000000000000001", "0.000000000000000001",
            "0.1", [("0.2", "2")], "1", "0.00000005",
            [
                ("near_zero_both", "351.359500000000000001", "1", "290", "100"),
                ("later", "352", "1", "290", "50"),
            ],
        )
        self.assertFalse(dual_uncertain["completedAllStages"])
        self.assertEqual(len(dual_uncertain["stages"]), 1)
        self.assertEqual(dual_uncertain["stages"][0]["phaseProcess"], "unresolved")
        self.assertEqual(dual_uncertain["finalPlateauStatus"], "exhaustion_time_uncertain")
        tlo, thi = map(F, dual_uncertain["modeledDurationBoundsS"])
        self.assertTrue(0 < tlo <= thi == F(100))

    def test_resolved_sign_exhaustion_time_uncertain_halts_schedule(self):
        # First measure the exhaustion time bracket for a large spherical bath with
        # nonzero radiation, then place the stage duration strictly inside [first, last).
        probe = investigate(
            LINK, "hot", "cold", "273.15", "334000", "10", "10",
            "0.1", [("0.15", "0.4")], "0.8", "0.0000000567",
            [("warm", "260", "5", "340", "1000000")],
        )
        self.assertEqual(probe["finalPlateauStatus"], "exhausted")
        t_lo, t_hi = map(F, probe["modeledDurationBoundsS"])
        self.assertLess(t_lo, t_hi)
        scale = 10**18
        mid_tick = int(((t_lo + t_hi) / 2) * scale)
        dur_str = f"{mid_tick // scale}.{mid_tick % scale:018d}"
        self.assertTrue(t_lo <= F(dur_str) < t_hi)

        res = investigate(
            LINK, "hot", "cold", "273.15", "334000", "10", "10",
            "0.1", [("0.15", "0.4")], "0.8", "0.0000000567",
            [("warm_edge", "260", "5", "340", dur_str), ("after", "250", "5", "250", "100")],
        )
        self.assertFalse(res["completedAllStages"])
        self.assertEqual(len(res["stages"]), 1)
        self.assertEqual(res["stages"][0]["phaseProcess"], "melting")
        self.assertEqual(res["finalPlateauStatus"], "exhaustion_time_uncertain")
        slo, shi = map(F, res["finalSolidMassBoundsKg"])
        self.assertEqual(slo, F(0))
        self.assertGreater(shi, F(0))

    def test_multi_reservoir_star_cycle_and_refusals(self):
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        stages = [
            ("cool_exterior", "280", "6", "260", "20"),
            ("hot_exterior", "350", "8", "360", "15"),
        ]
        res = investigate(
            inputs, "warm", "cool", "300", "1000", "2", "2",
            "0.1", [("0.2", "2")], "0.8", "0.0000000567", stages,
        )
        self.assertTrue(res["completedAllStages"])
        with mp.workdps(110):
            r_tot = mp.mpf("0.4") + 5 / (8 * mp.pi)
            area = mp.mpf("0.16") * mp.pi
            sigma = mp.mpf("0.0000000567")
            cum_e = mp.mpf("0")
            for row, (_, air, h, enc, dur) in zip(res["stages"], stages):
                t_s = mp.findroot(
                    lambda t: (t - 318) / r_tot
                    + area * (mp.mpf(h) * (t - mp.mpf(air))
                              + mp.mpf("0.8") * sigma * (t**4 - mp.mpf(enc)**4)),
                    mp.mpf("310"),
                )
                q_shell = (318 - t_s) / r_tot
                t_inner = 318 - mp.mpf("0.4") * q_shell
                t_center = (1590 + 5 * t_inner) / 10
                q_phase = 2 * (t_center - 300)
                q_middle = 3 * (t_center - 330)
                cum_e += q_phase * mp.mpf(dur)
                for limits, target in [
                    (row["bathInflowBoundsW"], q_phase),
                    (row["maintainedReservoirInflowBoundsW"]["middle"], q_middle),
                    (row["shellOutwardHeatRateBoundsW"], q_shell),
                    (row["cumulativeEnergyIntoBathBoundsJ"], cum_e),
                ]:
                    lo, hi = map(F, limits)
                    self.assertTrue(lo <= F(mp.nstr(target, 95)) <= hi)
                    self.assertLess(hi - lo, F(1, 10**11))
                bal = (interval(row["bathInflowBoundsW"])
                       + interval(row["maintainedReservoirInflowBoundsW"]["middle"])
                       + interval(row["shellOutwardHeatRateBoundsW"]))
                self.assertTrue(bal.low <= 0 <= bal.high)

        with self.assertRaisesRegex(ValueError, "one or more exterior stages"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                        "0.1", [("0.2", "2")], "0.8", "0.0000000567", [])
        with self.assertRaisesRegex(ValueError, "each stage requires"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                        "0.1", [("0.2", "2")], "0.8", "0.0000000567", [("day", "293.15", "10", "310")])
        with self.assertRaisesRegex(ValueError, "nonempty string name"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                        "0.1", [("0.2", "2")], "0.8", "0.0000000567", [("", "293.15", "10", "310", "10")])
        with self.assertRaisesRegex(ValueError, "positive stage duration"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
                        "0.1", [("0.2", "2")], "0.8", "0.0000000567", [("day", "293.15", "10", "310", "0")])
        with self.assertRaisesRegex(ValueError, "distinct"):
            investigate(LINK, "hot", "hot", "273.15", "334000", "0.02", "0.03",
                        "0.1", [("0.2", "2")], "0.8", "0.0000000567", [("day", "293.15", "10", "310", "10")])
