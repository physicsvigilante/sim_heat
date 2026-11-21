from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.phase_shell_sizing import investigate


class PhaseShellSizingTests(TestCase):
    def test_critical_radius_nonmonotonic_hold_time_in_cylinder(self):
        # Cylinder with k=1, h=5 -> critical radius r_c = k/h = 0.2 m.
        # Supply radii unsorted to verify ascending output ordering.
        base_args = (LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03")
        shell_args = ("0.1", [], "1", ["0.5", "0.2", "0.12"], "280", "0", "0.0000000567", "1")
        film = dict(air_k="293.15", h_w_per_m2_k="5")

        r260 = investigate(*base_args, "260", *shell_args, **film)
        self.assertEqual([row["outerRadiusM"] for row in r260["sizes"]], ["3/25", "1/5", "1/2"])
        self.assertEqual([row["holdStatus"] for row in r260["sizes"]],
                         ["meets_hold_time", "fails_hold_time", "meets_hold_time"])
        self.assertEqual(r260["smallestEstablishedMeetingHoldRadiusM"], "3/25")
        self.assertEqual(r260["geometry"], "cylinder")
        self.assertFalse(r260["nativeExecuted"])
        self.assertFalse(r260["nativeQualified"])

        with mp.workdps(110):
            for row, r_str in zip(r260["sizes"], ("0.12", "0.2", "0.5")):
                r_out = mp.mpf(r_str)
                r_tot = mp.mpf("0.5") + mp.log(r_out / mp.mpf("0.1")) / (2 * mp.pi) + 1 / (10 * mp.pi * r_out)
                q_phase = mp.mpf("20") / r_tot
                t_exh = mp.mpf("0.02") * 334000 / q_phase
                lo, hi = map(F, row["exhaustionTimeBoundsS"])
                self.assertTrue(lo <= F(mp.nstr(t_exh, 95)) <= hi)
                self.assertLess(hi - lo, F(1, 10**12))

        r270 = investigate(*base_args, "270", *shell_args, **film)
        self.assertEqual([row["holdStatus"] for row in r270["sizes"]],
                         ["fails_hold_time", "fails_hold_time", "meets_hold_time"])
        self.assertEqual(r270["smallestEstablishedMeetingHoldRadiusM"], "1/2")

        r280 = investigate(*base_args, "280", *shell_args, **film)
        self.assertEqual([row["holdStatus"] for row in r280["sizes"]],
                         ["fails_hold_time", "fails_hold_time", "fails_hold_time"])
        self.assertIsNone(r280["smallestEstablishedMeetingHoldRadiusM"])

    def test_nonzero_radiation_and_convection_spherical_sizing(self):
        result = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "200",
            "0.1", [], "1.5", ["0.15", "0.25", "0.4"], "340", "0.8", "0.0000000567",
            air_k="260", h_w_per_m2_k="5",
        )
        self.assertEqual(result["geometry"], "sphere")
        with mp.workdps(110):
            t_phase = mp.mpf("273.15")
            sigma = mp.mpf("0.0000000567")
            for row, r_str in zip(result["sizes"], ("0.15", "0.25", "0.4")):
                r_out = mp.mpf(r_str)
                r_tot = mp.mpf("0.5") + (1 / mp.mpf("0.1") - 1 / r_out) / (4 * mp.pi * mp.mpf("1.5"))
                area = 4 * mp.pi * r_out**2
                t_s = mp.findroot(
                    lambda t: (t - t_phase) / r_tot
                    + area * (5 * (t - 260) + mp.mpf("0.8") * sigma * (t**4 - mp.mpf("340")**4)),
                    t_phase,
                )
                q_shell = (t_phase - t_s) / r_tot
                q_phase = -q_shell
                t_exh = mp.mpf("0.02") * 334000 / abs(q_phase)
                for limits, target in [
                    (row["bathInflowDuringPlateauBoundsW"], q_phase),
                    (row["shellOutwardHeatRateBoundsW"], q_shell),
                    (row["exhaustionTimeBoundsS"], t_exh),
                ]:
                    lo, hi = map(F, limits)
                    self.assertTrue(lo <= F(mp.nstr(target, 95)) <= hi)
                    self.assertLess(hi - lo, F(1, 10**12))
                bal = (interval(row["bathInflowDuringPlateauBoundsW"])
                       + interval(row["shellOutwardHeatRateBoundsW"]))
                self.assertTrue(bal.low <= 0 <= bal.high)
                slo, shi = map(F, row["remainingSolidBoundsKg"])
                llo, lhi = map(F, row["remainingLiquidBoundsKg"])
                self.assertEqual(slo + lhi, F("0.05"))
                self.assertEqual(shi + llo, F("0.05"))

    def test_unresolved_smaller_radius_blocks_minimum_claim(self):
        probe = investigate(
            LINK, "hot", "cold", "273.15", "334000", "10", "10", "100",
            "0.1", [], "0.4", ["0.15", "0.4"], "340", "0.8", "0.0000000567",
            air_k="260", h_w_per_m2_k="5",
        )
        t_lo, t_hi = map(F, probe["sizes"][0]["exhaustionTimeBoundsS"])
        self.assertLess(t_lo, t_hi)
        # Pick an 18-decimal hold time strictly inside the smaller radius's
        # exhaustion bracket so it is unresolved while 0.4 m clearly survives.
        scale = 10**18
        mid_tick = int(((t_lo + t_hi) / 2) * scale)
        hold_str = f"{mid_tick // scale}.{mid_tick % scale:018d}"
        self.assertTrue(t_lo <= F(hold_str) < t_hi)

        blocked = investigate(
            LINK, "hot", "cold", "273.15", "334000", "10", "10", hold_str,
            "0.1", [], "0.4", ["0.15", "0.4"], "340", "0.8", "0.0000000567",
            air_k="260", h_w_per_m2_k="5",
        )
        self.assertEqual(blocked["sizes"][0]["holdStatus"], "unresolved")
        self.assertEqual(blocked["sizes"][0]["plateauStatus"], "exhaustion_time_uncertain")
        self.assertEqual(blocked["sizes"][1]["holdStatus"], "meets_hold_time")
        self.assertIsNone(blocked["smallestEstablishedMeetingHoldRadiusM"])

    def test_exact_equilibrium_and_unresolved_near_zero_direction(self):
        eq = investigate(
            LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
            "0.1", [], "2", ["0.15", "0.2"], "290", "1", "0.00000005",
            air_k="351.3595", h_w_per_m2_k="1",
        )
        self.assertEqual(eq["smallestEstablishedMeetingHoldRadiusM"], "3/20")
        for row in eq["sizes"]:
            self.assertEqual(row["phaseProcess"], "equilibrium")
            self.assertEqual(row["holdStatus"], "meets_hold_time")
            self.assertIsNone(row["exhaustionTimeBoundsS"])
            self.assertEqual(row["remainingSolidBoundsKg"], ["1/50", "1/50"])
            self.assertEqual(row["remainingLiquidBoundsKg"], ["3/100", "3/100"])

        # Sub-resolution near-zero interval: direction is unresolved, but even
        # worst-case flow in either direction cannot exhaust 0.02/0.03 kg in 100 s.
        safe = investigate(
            LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
            "0.1", [], "2", ["0.15", "0.2"], "290", "1", "0.00000005",
            air_k="351.359500000000000001", h_w_per_m2_k="1",
        )
        self.assertEqual(safe["smallestEstablishedMeetingHoldRadiusM"], "3/20")
        for row in safe["sizes"]:
            self.assertEqual(row["phaseProcess"], "unresolved")
            self.assertEqual(row["holdStatus"], "meets_hold_time")
            self.assertEqual(row["plateauStatus"], "coexisting")
            self.assertIsNone(row["exhaustionTimeBoundsS"])
            slo, shi = map(F, row["remainingSolidBoundsKg"])
            llo, lhi = map(F, row["remainingLiquidBoundsKg"])
            self.assertEqual(slo + lhi, F("0.05"))
            self.assertEqual(shi + llo, F("0.05"))

        # With tiny latent capacity, the same uncertified near-zero interval
        # could exhaust a phase -> unresolved hold status and no minimum claim.
        uncertain = investigate(
            LINK, "hot", "cold", "300", "1", "0.000000000000000001", "0.03", "100",
            "0.1", [], "2", ["0.15", "0.2"], "290", "1", "0.00000005",
            air_k="351.359500000000000001", h_w_per_m2_k="1",
        )
        self.assertIsNone(uncertain["smallestEstablishedMeetingHoldRadiusM"])
        for row in uncertain["sizes"]:
            self.assertEqual(row["phaseProcess"], "unresolved")
            self.assertEqual(row["holdStatus"], "unresolved")
            self.assertEqual(row["plateauStatus"], "exhaustion_time_uncertain")

    def test_multi_reservoir_star_and_refusals(self):
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        res = investigate(
            inputs, "warm", "cool", "300", "1000", "1", "1", "70",
            "0.1", [], "2", ["0.15", "0.25"], "260", "0.8", "0.0000000567",
            air_k="280", h_w_per_m2_k="6",
        )
        for row in res["sizes"]:
            bal = (interval(row["bathInflowDuringPlateauBoundsW"])
                   + interval(row["maintainedReservoirInflowBoundsW"]["middle"])
                   + interval(row["shellOutwardHeatRateBoundsW"]))
            self.assertTrue(bal.low <= 0 <= bal.high)

        with self.assertRaisesRegex(ValueError, "positive target hold duration"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "0",
                        "0.1", [], "1", ["0.2"], "280", "0", "0.0000000567")
        with self.assertRaisesRegex(ValueError, "distinct available outer radii"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "10",
                        "0.1", [], "1", ["0.2", "0.20"], "280", "0", "0.0000000567")
        with self.assertRaisesRegex(ValueError, "distinct available outer radii"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "10",
                        "0.1", [], "1", [], "280", "0", "0.0000000567")
        with self.assertRaisesRegex(ValueError, "distinct"):
            investigate(LINK, "hot", "hot", "273.15", "334000", "0.02", "0.03", "10",
                        "0.1", [], "1", ["0.2"], "280", "0", "0.0000000567")
