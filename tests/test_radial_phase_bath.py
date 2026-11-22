from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.radial_phase_bath import investigate


class RadialPhaseBath(TestCase):
    def test_spherical_ice_vessel_melts_or_freezes_until_one_phase_exhausts(self):
        for air, mode in (("293.15","melting"), ("253.15","freezing")):
            r = investigate(LINK,"hot","cold","273.15","334000","0.02","0.03","10000",
                            "0.1",[("0.2","2")],"280","0","0.0000000567",
                            air_k=air,h_w_per_m2_k="10")
            with mp.workdps(110):
                total = mp.mpf("0.5") + 5/(8*mp.pi) + 1/(mp.mpf("1.6")*mp.pi)
                q = (mp.mpf(air)-mp.mpf("273.15"))/total
                mass = mp.mpf("0.02" if mode == "melting" else "0.03")
                for limits, target in [(r["bathInflowDuringPlateauBoundsW"], q),
                                       (r["exhaustionTimeBoundsS"], mass*334000/abs(q))]:
                    lo, hi = map(F, limits)
                    self.assertTrue(lo <= F(mp.nstr(target,95)) <= hi)
                    self.assertLess(hi-lo,F(1,10**12))
            self.assertEqual(r["phaseProcess"], mode)
            self.assertEqual(r["plateauStatus"], "exhausted")
            key = "remainingSolidBoundsKg" if mode == "melting" else "remainingLiquidBoundsKg"
            self.assertEqual(r[key], ["0","0"])

    def test_exact_opposing_flux_equilibrium_and_perturbations(self):
        eq = investigate(LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
                         "0.1", [("0.2", "2")], "290", "1", "0.00000005",
                         air_k="351.3595", h_w_per_m2_k="1")
        self.assertEqual(eq["phaseProcess"], "equilibrium")
        self.assertEqual(eq["plateauStatus"], "coexisting")
        self.assertEqual(eq["bathInflowDuringPlateauBoundsW"], ["0", "0"])
        self.assertEqual(eq["radialShell"]["outwardHeatRateBoundsW"], ["0", "0"])
        self.assertIsNone(eq["exhaustionTimeBoundsS"])
        self.assertEqual(eq["remainingSolidBoundsKg"], ["1/50", "1/50"])
        self.assertEqual(eq["remainingLiquidBoundsKg"], ["3/100", "3/100"])

        for air, mode in (("351.3596", "melting"), ("351.3594", "freezing")):
            r = investigate(LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
                            "0.1", [("0.2", "2")], "290", "1", "0.00000005",
                            air_k=air, h_w_per_m2_k="1")
            self.assertEqual(r["phaseProcess"], mode)
            qlo, qhi = map(F, r["bathInflowDuringPlateauBoundsW"])
            self.assertTrue(qlo > 0 if mode == "melting" else qhi < 0)
            slo, shi = map(F, r["remainingSolidBoundsKg"])
            llo, lhi = map(F, r["remainingLiquidBoundsKg"])
            self.assertEqual(slo + lhi, F("0.05"))
            self.assertEqual(shi + llo, F("0.05"))

        # Uncertified sub-resolution near-zero intervals must still refuse rather
        # than collapsing to equilibrium by tolerance.
        with self.assertRaisesRegex(ValueError, "unresolved"):
            investigate(LINK, "hot", "cold", "300", "334000", "0.02", "0.03", "100",
                        "0.1", [("0.2", "2")], "290", "1", "0.00000005",
                        air_k="351.359500000000000001", h_w_per_m2_k="1")

    def test_cylindrical_nonzero_radiation_and_convection_with_distinct_environments(self):
        cases = (
            ("340", "260", "5", "melting", "0.02"),
            ("240", "310", "2", "freezing", "0.03"),
        )
        for enc, air, h, mode, exhaust_mass in cases:
            coex = investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "10",
                               "0.1", [("0.2", "2")], enc, "0.8", "0.0000000567",
                               cylinder_length_m="1", air_k=air, h_w_per_m2_k=h)
            exh = investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "50000",
                              "0.1", [("0.2", "2")], enc, "0.8", "0.0000000567",
                              cylinder_length_m="1", air_k=air, h_w_per_m2_k=h)
            with mp.workdps(110):
                t_phase = mp.mpf("273.15")
                r_tot = mp.mpf("0.5") + mp.log(2) / (4 * mp.pi)
                area = mp.mpf("0.4") * mp.pi
                sigma = mp.mpf("0.0000000567")
                t_s = mp.findroot(
                    lambda t: (t - t_phase) / r_tot
                    + area * (mp.mpf(h) * (t - mp.mpf(air))
                              + mp.mpf("0.8") * sigma * (t**4 - mp.mpf(enc)**4)),
                    t_phase,
                )
                q_shell = (t_phase - t_s) / r_tot
                q_phase = -q_shell
                t_exh = mp.mpf(exhaust_mass) * 334000 / abs(q_phase)
                rem_solid = mp.mpf("0.02") - q_phase * 10 / 334000
                for limits, target in [
                    (coex["bathInflowDuringPlateauBoundsW"], q_phase),
                    (coex["radialShell"]["outwardHeatRateBoundsW"], q_shell),
                    (coex["radialShell"]["surfaces"][-1]["temperatureBoundsK"], t_s),
                    (coex["exhaustionTimeBoundsS"], t_exh),
                    (coex["remainingSolidBoundsKg"], rem_solid),
                ]:
                    lo, hi = map(F, limits)
                    self.assertTrue(lo <= F(mp.nstr(target, 95)) <= hi)
                    self.assertLess(hi - lo, F(1, 10**12))
            self.assertEqual(coex["radialShell"]["geometry"], "cylinder")
            self.assertEqual(coex["phaseProcess"], mode)
            self.assertEqual(coex["plateauStatus"], "coexisting")
            balance = (interval(coex["bathInflowDuringPlateauBoundsW"])
                       + interval(coex["radialShell"]["outwardHeatRateBoundsW"]))
            self.assertTrue(balance.low <= 0 <= balance.high)
            slo, shi = map(F, coex["remainingSolidBoundsKg"])
            llo, lhi = map(F, coex["remainingLiquidBoundsKg"])
            self.assertEqual(slo + lhi, F("0.05"))
            self.assertEqual(shi + llo, F("0.05"))

            self.assertEqual(exh["plateauStatus"], "exhausted")
            depleted, full = (("remainingSolidBoundsKg", "remainingLiquidBoundsKg")
                              if mode == "melting"
                              else ("remainingLiquidBoundsKg", "remainingSolidBoundsKg"))
            self.assertEqual(exh[depleted], ["0", "0"])
            self.assertEqual(exh[full], ["1/20", "1/20"])

    def test_multi_reservoir_nonzero_radiation_and_shell_flow(self):
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        coex = investigate(inputs, "warm", "cool", "300", "1000", "1", "1", "10",
                           "0.1", [("0.2", "2")], "260", "0.8", "0.0000000567",
                           air_k="280", h_w_per_m2_k="6")
        exh = investigate(inputs, "warm", "cool", "300", "1000", "1", "1", "1000",
                          "0.1", [("0.2", "2")], "260", "0.8", "0.0000000567",
                          air_k="280", h_w_per_m2_k="6")
        with mp.workdps(110):
            r_tot = mp.mpf("0.4") + 5 / (8 * mp.pi)
            area = mp.mpf("0.16") * mp.pi
            sigma = mp.mpf("0.0000000567")
            t_s = mp.findroot(
                lambda t: (t - 318) / r_tot
                + area * (6 * (t - 280) + mp.mpf("0.8") * sigma * (t**4 - mp.mpf("260")**4)),
                mp.mpf("300"),
            )
            q_shell = (318 - t_s) / r_tot
            t_inner = 318 - mp.mpf("0.4") * q_shell
            t_center = (1590 + 5 * t_inner) / 10
            q_phase = 2 * (t_center - 300)
            q_middle = 3 * (t_center - 330)
            for limits, target in [
                (coex["bathInflowDuringPlateauBoundsW"], q_phase),
                (coex["maintainedReservoirInflowBoundsW"]["middle"], q_middle),
                (coex["radialShell"]["outwardHeatRateBoundsW"], q_shell),
                (coex["remainingSolidBoundsKg"], 1 - q_phase * 10 / 1000),
            ]:
                lo, hi = map(F, limits)
                self.assertTrue(lo <= F(mp.nstr(target, 95)) <= hi)
                self.assertLess(hi - lo, F(1, 10**12))
        q_shell_lo, _ = map(F, coex["radialShell"]["outwardHeatRateBoundsW"])
        self.assertGreater(q_shell_lo, 0)
        total = (interval(coex["bathInflowDuringPlateauBoundsW"])
                 + interval(coex["maintainedReservoirInflowBoundsW"]["middle"])
                 + interval(coex["radialShell"]["outwardHeatRateBoundsW"]))
        self.assertTrue(total.low <= 0 <= total.high)
        slo, shi = map(F, coex["remainingSolidBoundsKg"])
        llo, lhi = map(F, coex["remainingLiquidBoundsKg"])
        self.assertEqual(slo + lhi, F(2))
        self.assertEqual(shi + llo, F(2))
        self.assertEqual(exh["plateauStatus"], "exhausted")
        self.assertEqual(exh["remainingSolidBoundsKg"], ["0", "0"])
        self.assertEqual(exh["remainingLiquidBoundsKg"], ["2", "2"])

    def test_other_reservoir_can_melt_bath_even_with_zero_shell_heat(self):
        case = CASES/"star"
        inputs = (case/"study.json",case,case/"facts.json",STAR)
        result = investigate(inputs,"warm","cool","300","1000","1","1","10",
                             "0.1",[("0.2","2")],"310","0","0.0000000567")
        self.assertEqual(result["radialShell"]["outwardHeatRateBoundsW"], ["0","0"])
        # Released third branch carries zero heat; the remaining 2 and 3 W/K
        # arms in series conduct 36 W from 330 K middle to the 300 K phase bath.
        for limits, target in [(result["bathInflowDuringPlateauBoundsW"],36),
                               (result["maintainedReservoirInflowBoundsW"]["middle"],-36),
                               (result["remainingSolidBoundsKg"], F("0.64"))]:
            lo,hi = map(F,limits)
            self.assertTrue(lo <= target <= hi)
            self.assertLess(hi-lo,F(1,10**12))
        with self.assertRaisesRegex(ValueError,"distinct"):
            investigate(inputs,"warm","warm","300","1000","1","1","10",
                        "0.1",[("0.2","2")],"310","0","0.0000000567")
