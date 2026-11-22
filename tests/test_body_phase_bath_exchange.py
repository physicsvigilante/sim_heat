from fractions import Fraction as F
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.body_phase_bath_exchange import exp_neg_box, investigate, solve_from_law
from tools.terminal_response import investigate as terminal_response


class BodyPhaseBathExchangeTests(TestCase):
    def test_exp_neg_box_encloses_mpmath_across_scales(self):
        with mp.workdps(110):
            for x_str in ("0", "0.001", "0.5", "1", "3.75", "12.5", "25"):
                x = F(x_str)
                lo, hi = exp_neg_box(x).span()
                exact = F(mp.nstr(mp.exp(-mp.mpf(x_str)), 95))
                self.assertTrue(lo <= exact <= hi, f"failed for x={x_str}")
                self.assertLess(hi - lo, F(1, 10**30))
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            exp_neg_box(F(-1))

    def test_two_terminal_hot_and_cold_bodies_with_and_without_exhaustion(self):
        # LINK has R = 0.5 K/W (G = 2 W/K). Take C = 200 J/K -> tau = 100 s.
        # Case 1: Hot body at 303.15 K (dT = 30 K) -> max sensible heat = 6000 J.
        # Solid inventory = 0.02 kg * 334000 J/kg = 6680 J > 6000 J -> never exhausts!
        never = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "200", "303.15", "100",
        )
        self.assertEqual(never["phaseProcess"], "melting")
        self.assertEqual(never["plateauStatus"], "coexisting")
        self.assertIsNone(never["exhaustionTimeBoundsS"])
        self.assertIsNone(never["exhaustedPhase"])
        self.assertEqual(never["bodyTimeConstantBoundsS"], ["100", "100"])
        self.assertFalse(never["nativeExecuted"])
        self.assertFalse(never["nativeQualified"])

        # Exact energy conservation for 2-terminal network: dE_body + E_bath = 0.
        bal = interval(never["bodyEnergyChangeBoundsJ"]) + interval(never["latentEnergyIntoBathBoundsJ"])
        self.assertTrue(bal.low <= 0 <= bal.high)

        with mp.workdps(110):
            t_exact = mp.mpf("273.15") + 30 * mp.exp(-1)
            e_exact = 6000 * (1 - mp.exp(-1))
            t_lo, t_hi = map(F, never["finalBodyTemperatureBoundsK"])
            e_lo, e_hi = map(F, never["latentEnergyIntoBathBoundsJ"])
            self.assertTrue(t_lo <= F(mp.nstr(t_exact, 95)) <= t_hi)
            self.assertTrue(e_lo <= F(mp.nstr(e_exact, 95)) <= e_hi)

        # Case 2: Hot body at 373.15 K (dT = 100 K) -> max sensible heat = 20000 J > 6680 J.
        # Exact exhaustion time: tau * ln(20000 / (20000 - 6680)) = 100 * ln(20000/13320) ~ 40.6465 s.
        before = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "200", "373.15", "20",
        )
        self.assertEqual(before["plateauStatus"], "coexisting")
        ex_lo, ex_hi = map(F, before["exhaustionTimeBoundsS"])
        with mp.workdps(110):
            t_ex_exact = 100 * mp.log(mp.mpf(20000) / mp.mpf(13320))
            self.assertTrue(ex_lo <= F(mp.nstr(t_ex_exact, 95)) <= ex_hi)
            self.assertLess(ex_hi - ex_lo, F(1, 10**12))

        after = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "200", "373.15", "100",
        )
        self.assertEqual(after["plateauStatus"], "exhausted")
        self.assertEqual(after["exhaustedPhase"], "solid")
        self.assertEqual(after["remainingSolidBoundsKg"], ["0", "0"])
        self.assertEqual(after["remainingLiquidBoundsKg"], ["1/20", "1/20"])
        # Exact body temperature at solid exhaustion: 373.15 - 6680/200 = 339.75 K.
        self.assertEqual(after["finalBodyTemperatureBoundsK"], ["1359/4", "1359/4"])
        self.assertEqual(after["modeledDurationBoundsS"], after["exhaustionTimeBoundsS"])

        # Case 3: Cold body at 200 K freezing liquid (0.01 kg * 334000 = 3340 J < 200 * 73.15 = 14630 J).
        freeze = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.01",
            "200", "200", "100",
        )
        self.assertEqual(freeze["phaseProcess"], "freezing")
        self.assertEqual(freeze["plateauStatus"], "exhausted")
        self.assertEqual(freeze["exhaustedPhase"], "liquid")
        self.assertEqual(freeze["remainingLiquidBoundsKg"], ["0", "0"])
        self.assertEqual(freeze["finalBodyTemperatureBoundsK"], [str(F("200") + F("3340") / 200)] * 2)

        # Case 4: Exact isothermal equilibrium and zero duration.
        eq = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "200", "273.15", "100",
        )
        self.assertEqual(eq["phaseProcess"], "equilibrium")
        self.assertEqual(eq["plateauStatus"], "coexisting")
        self.assertEqual(eq["latentEnergyIntoBathBoundsJ"], ["0", "0"])
        self.assertEqual(eq["finalBodyTemperatureBoundsK"], ["5463/20", "5463/20"])

        zero_t = investigate(
            LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03",
            "200", "373.15", "0",
        )
        self.assertEqual(zero_t["plateauStatus"], "coexisting")
        self.assertEqual(zero_t["finalBodyTemperatureBoundsK"], ["7463/20", "7463/20"])
        self.assertEqual(zero_t["latentEnergyIntoBathBoundsJ"], ["0", "0"])

    def test_star_network_monotonic_and_reversing_regimes_against_mpmath(self):
        # STAR network has terminals warm, cool, middle (middle imposed at 330 K).
        # Put phase bath at warm (T_tr = 350 K -> middle at 330 K is COLDER than phase bath, so Q_inf < 0!).
        # Put hot body at cool (T_0 = 500 K) -> initially melts ice (Q_0 > 0), then reverses to freeze!
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        law = terminal_response(*inputs)
        row_p = law["supplyResponseBoundsWPerK"]["warm"]
        row_b = law["supplyResponseBoundsWPerK"]["cool"]

        # 1) Coexisting through reversal (large solid and liquid inventories).
        rev_coex = solve_from_law(
            law, "warm", "cool", "350", "1000", "50", "50", "100", "500", "120",
        )
        self.assertEqual(rev_coex["phaseProcess"], "reversing_melting_to_freezing")
        self.assertEqual(rev_coex["plateauStatus"], "coexisting")
        self.assertIsNotNone(rev_coex["reversalTimeBoundsS"])

        # Verify against independent 110-digit mpmath using exact conductances of STAR.
        t_mid = mp.mpf(law["imposedTemperaturesK"]["middle"])
        with mp.workdps(110):
            g_pb = -mp.mpf(str((F(row_p["cool"][0]) + F(row_p["cool"][1])) / 2))
            g_pm = -mp.mpf(str((F(row_p["middle"][0]) + F(row_p["middle"][1])) / 2))
            g_bm = -mp.mpf(str((F(row_b["middle"][0]) + F(row_b["middle"][1])) / 2))
            g_b = g_pb + g_bm
            t_eq = (g_pb * 350 + g_bm * t_mid) / g_b
            tau = 100 / g_b
            q_inf = g_pb * (t_eq - 350) + g_pm * (t_mid - 350)
            q_tr = g_pb * (500 - t_eq)
            t_star = tau * mp.log(-q_tr / q_inf)
            e_120 = q_inf * 120 + tau * q_tr * (1 - mp.exp(-120 / tau))
            t_120 = t_eq + (500 - t_eq) * mp.exp(-120 / tau)

            rs_lo, rs_hi = map(F, rev_coex["reversalTimeBoundsS"])
            e_lo, e_hi = map(F, rev_coex["latentEnergyIntoBathBoundsJ"])
            tb_lo, tb_hi = map(F, rev_coex["finalBodyTemperatureBoundsK"])
            self.assertTrue(rs_lo <= F(mp.nstr(t_star, 95)) <= rs_hi)
            self.assertTrue(e_lo <= F(mp.nstr(e_120, 95)) <= e_hi)
            self.assertTrue(tb_lo <= F(mp.nstr(t_120, 95)) <= tb_hi)

        # 2) Solid exhausts BEFORE reversal (small solid inventory = 1 kg -> 1000 J).
        rev_solid = solve_from_law(
            law, "warm", "cool", "350", "1000", "1", "50", "100", "500", "120",
        )
        self.assertEqual(rev_solid["phaseProcess"], "reversing_melting_to_freezing")
        self.assertEqual(rev_solid["plateauStatus"], "exhausted")
        self.assertEqual(rev_solid["exhaustedPhase"], "solid")
        self.assertLess(F(rev_solid["exhaustionTimeBoundsS"][1]), F(rev_solid["reversalTimeBoundsS"][0]))

        # 3) Solid survives peak, liquid exhausts AFTER reversal (large solid, small liquid = 0.5 kg).
        rev_liq = solve_from_law(
            law, "warm", "cool", "350", "1000", "50", "0.5", "100", "500", "300",
        )
        self.assertEqual(rev_liq["phaseProcess"], "reversing_melting_to_freezing")
        self.assertEqual(rev_liq["plateauStatus"], "exhausted")
        self.assertEqual(rev_liq["exhaustedPhase"], "liquid")
        self.assertGreater(F(rev_liq["exhaustionTimeBoundsS"][0]), F(rev_liq["reversalTimeBoundsS"][1]))

        # 4) Monotonic melting in STAR (T_tr = 300 K < middle 330 K, hot body at 400 K).
        mono = solve_from_law(
            law, "warm", "cool", "300", "1000", "5", "5", "100", "400", "500",
        )
        self.assertEqual(mono["phaseProcess"], "melting")
        self.assertEqual(mono["plateauStatus"], "exhausted")
        self.assertEqual(mono["exhaustedPhase"], "solid")

        # 5) Reversing freezing-to-melting in STAR (T_tr = 310 K < middle 330 K so Q_inf > 0,
        # cold body at 200 K initially freezes liquid then warms and reverses to melt).
        rev_f2m = solve_from_law(
            law, "warm", "cool", "310", "1000", "50", "50", "100", "200", "200",
        )
        self.assertEqual(rev_f2m["phaseProcess"], "reversing_freezing_to_melting")
        self.assertEqual(rev_f2m["plateauStatus"], "coexisting")
        self.assertIsNotNone(rev_f2m["reversalTimeBoundsS"])

        # 6) Exact zero initial bath flux with definite subsequent sign (Q_p(0) == 0, Q_inf != 0):
        # Freezing: T_tr = 350 K, T_0 = 362 K -> Q_inf = -24 W, Q_tr = +24 W, Q_p(t) = -24(1 - exp(-t/40)).
        # Melting:  T_tr = 310 K, T_0 = 298 K -> Q_inf = +24 W, Q_tr = -24 W, Q_p(t) = +24(1 - exp(-t/40)).
        for t_tr, t_0, expected_proc, sign in (
            ("350", "362", "freezing", -1),
            ("310", "298", "melting", 1),
        ):
            with self.subTest(t_tr=t_tr, t_0=t_0):
                res_120 = solve_from_law(
                    law, "warm", "cool", t_tr, "1000", "50", "50", "100", t_0, "120",
                )
                self.assertEqual(res_120["phaseProcess"], expected_proc)
                self.assertEqual(res_120["plateauStatus"], "coexisting")
                self.assertEqual(res_120["initialBathInflowBoundsW"], ["0", "0"])
                self.assertIsNotNone(res_120["exhaustionTimeBoundsS"])
                with mp.workdps(110):
                    e_exact = sign * (24 * 120 - 40 * 24 * (1 - mp.exp(-3)))
                    e_lo, e_hi = map(F, res_120["latentEnergyIntoBathBoundsJ"])
                    self.assertTrue(e_lo <= F(mp.nstr(e_exact, 95)) <= e_hi)

                res_0 = solve_from_law(
                    law, "warm", "cool", t_tr, "1000", "50", "50", "100", t_0, "0",
                )
                self.assertEqual(res_0["phaseProcess"], expected_proc)
                self.assertEqual(res_0["plateauStatus"], "coexisting")
                self.assertEqual(res_0["latentEnergyIntoBathBoundsJ"], ["0", "0"])
                self.assertEqual(res_0["finalBodyTemperatureBoundsK"], [t_0, t_0])
                self.assertIsNotNone(res_0["exhaustionTimeBoundsS"])

    def test_refusals_for_invalid_ports_capacity_and_decoupled_network(self):
        with self.assertRaisesRegex(ValueError, "distinct phase and body ports"):
            investigate(LINK, "hot", "hot", "273.15", "334000", "0.02", "0.03", "200", "300", "10")
        with self.assertRaisesRegex(ValueError, "positive heat capacity"):
            investigate(LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "0", "300", "10")

        law = terminal_response(*LINK)
        decoupled = {
            **law,
            "supplyResponseBoundsWPerK": {
                **law["supplyResponseBoundsWPerK"],
                "hot": {**law["supplyResponseBoundsWPerK"]["hot"], "cold": ["0", "0"]},
            },
        }
        with self.assertRaisesRegex(ValueError, "not thermally coupled"):
            solve_from_law(decoupled, "hot", "cold", "273.15", "334000", "0.02", "0.03", "200", "300", "10")

    def test_near_tangent_reversing_exhaustion_retains_exact_event_energy_and_zero_inventory(self):
        # Issue #195 F1 witnesses: peak exceeds the latent budget by ~2.74e-47 J before
        # reversal, while the untruncated horizon energy drops back below the budget.
        case = CASES / "star"
        inputs = (case / "study.json", case, case / "facts.json", STAR)
        budget = "34061415317.531641403602549745"
        capacity = "923864956.216485709294744294"
        duration = "1108637948"
        t_first_approx = F("705663761.067432")

        # 1) Melting-to-freezing near-tangent solid exhaustion.
        melt = investigate(
            inputs, "warm", "cool", "350", "1", budget, "999999999999",
            capacity, "500", duration,
        )
        self.assertEqual(melt["phaseProcess"], "reversing_melting_to_freezing")
        self.assertEqual(melt["plateauStatus"], "exhausted")
        self.assertEqual(melt["exhaustedPhase"], "solid")
        self.assertEqual(melt["latentEnergyIntoBathBoundsJ"], [str(F(budget)), str(F(budget))])
        self.assertEqual(melt["remainingSolidBoundsKg"], ["0", "0"])
        self.assertEqual(melt["modeledDurationBoundsS"], melt["exhaustionTimeBoundsS"])
        m_lo, m_hi = map(F, melt["modeledDurationBoundsS"])
        self.assertLessEqual(m_lo, m_hi)
        self.assertLess(abs(m_lo - t_first_approx), F(1))
        self.assertLess(abs(m_hi - t_first_approx), F(1))

        # 2) Mirrored freezing-to-melting near-tangent liquid exhaustion.
        freeze = investigate(
            inputs, "warm", "cool", "310", "1", "999999999999", budget,
            capacity, "160", duration,
        )
        self.assertEqual(freeze["phaseProcess"], "reversing_freezing_to_melting")
        self.assertEqual(freeze["plateauStatus"], "exhausted")
        self.assertEqual(freeze["exhaustedPhase"], "liquid")
        self.assertEqual(freeze["latentEnergyIntoBathBoundsJ"], [str(-F(budget)), str(-F(budget))])
        self.assertEqual(freeze["remainingLiquidBoundsKg"], ["0", "0"])
        self.assertEqual(freeze["modeledDurationBoundsS"], freeze["exhaustionTimeBoundsS"])
        f_lo, f_hi = map(F, freeze["modeledDurationBoundsS"])
        self.assertLessEqual(f_lo, f_hi)
        self.assertLess(abs(f_lo - t_first_approx), F(1))
        self.assertLess(abs(f_hi - t_first_approx), F(1))
