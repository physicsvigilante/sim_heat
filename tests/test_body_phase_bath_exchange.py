import copy
from fractions import Fraction as F
import itertools
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import Box, ZERO, interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR
from tools.body_phase_bath_exchange import (
    _bisect_threshold,
    exp_neg_box,
    exp_neg_interval,
    investigate,
    solve_from_law,
)
from tools.offline_investigation import (
    InvestigationRequest,
    LumpedBodySpec,
    PhaseBathSpec,
    run_investigation,
    validate_pinned_law,
)
from tools.radiating_surface import physical_port
from tools.spherical_conduction import radial_log
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

    @staticmethod
    def _widened_star_law(delta):
        case = CASES / "star"
        base = terminal_response(case / "study.json", case, case / "facts.json", STAR)
        g0 = {("cool", "middle"): F(3, 2), ("cool", "warm"): F(1), ("middle", "warm"): F(3, 5)}
        law = copy.deepcopy(base)
        m = law["supplyResponseBoundsWPerK"]
        for (a, b), g in g0.items():
            m[a][b] = m[b][a] = [str(-(g + delta)), str(-(g - delta))]
        for a in law["terminals"]:
            s = sum(g for (x, y), g in g0.items() if a in (x, y))
            m[a][a] = [str(s - 2 * delta), str(s + 2 * delta)]
        validate_pinned_law(law)
        return law

    def test_f01_reversing_opposite_phase_exhaustion_encloses_27_realizations_both_routes_and_mirrors(self):
        # F-01 regression (P6-equivalent): widened passive STAR interval law at delta = 1e-2 and 1e-6,
        # tested in both melting-first and freezing-first mirror regimes, on both direct solve_from_law
        # and typed offline_investigation.run_investigation routes.
        cases = [
            # (delta, t_tr, t0, solid, liquid, expected_proc, expected_phase)
            (F(1, 100), "350", "363", "100000", "0.001", "reversing_melting_to_freezing", "liquid"),
            (F(1, 10**6), "350", "362.0001", "100000", "0.0000000001", "reversing_melting_to_freezing", "liquid"),
            (F(1, 100), "310", "297", "0.001", "100000", "reversing_freezing_to_melting", "solid"),
            (F(1, 10**6), "310", "297.9999", "0.0000000001", "100000", "reversing_freezing_to_melting", "solid"),
        ]
        with mp.workdps(60):
            for delta, t_tr_s, t0_s, sol_s, liq_s, exp_proc, exp_phase in cases:
                law = self._widened_star_law(delta)
                direct = solve_from_law(law, "warm", "cool", t_tr_s, "1", sol_s, liq_s, "100", t0_s, "10")
                req = InvestigationRequest(
                    composition="body_phase_bath_exchange",
                    source=law,
                    duration_s="10",
                    phase_bath=PhaseBathSpec("warm", t_tr_s, "1", sol_s, liq_s),
                    body=LumpedBodySpec("cool", "100", t0_s),
                )
                typed = run_investigation(req)
                self.assertEqual(typed["rawResult"], direct)

                for route_name, ex_pair, tf_pair, de_pair, status, phase, proc in (
                    (
                        "direct",
                        direct["exhaustionTimeBoundsS"],
                        direct["finalBodyTemperatureBoundsK"],
                        direct["bodyEnergyChangeBoundsJ"],
                        direct["plateauStatus"],
                        direct["exhaustedPhase"],
                        direct["phaseProcess"],
                    ),
                    (
                        "typed",
                        typed["status"]["exhaustionTimeS"]["bounds"],
                        typed["quantities"]["finalBodyTemperatureK"]["bounds"],
                        typed["quantities"]["bodyEnergyChangeJ"]["bounds"],
                        typed["status"]["plateauStatus"],
                        typed["status"]["exhaustedPhase"],
                        typed["status"]["phaseProcess"],
                    ),
                ):
                    with self.subTest(delta=str(delta), proc=exp_proc, route=route_name):
                        self.assertEqual(proc, exp_proc)
                        self.assertEqual(status, "exhausted")
                        self.assertEqual(phase, exp_phase)
                        ex_lo, ex_hi = map(F, ex_pair)
                        tf_lo, tf_hi = map(F, tf_pair)
                        de_lo, de_hi = map(F, de_pair)
                        d_mp = mp.mpf(delta.numerator) / delta.denominator
                        t_tr = mp.mpf(t_tr_s)
                        t0 = mp.mpf(t0_s)
                        t_m = mp.mpf("330")
                        c_mp = mp.mpf("100")
                        limit = -mp.mpf(liq_s) if exp_phase == "liquid" else mp.mpf(sol_s)

                        for s in itertools.product((-1, 0, 1), repeat=3):
                            gwc = mp.mpf(1) + s[0] * d_mp
                            gwm = mp.mpf(3) / 5 + s[1] * d_mp
                            gcm = mp.mpf(3) / 2 + s[2] * d_mp
                            g_b = gwc + gcm
                            teq = (gwc * t_tr + gcm * t_m) / g_b
                            tau = c_mp / g_b
                            q_inf = gwc * (teq - t_tr) + gwm * (t_m - t_tr)
                            q_tr = gwc * (t0 - teq)
                            e_fn = lambda t: q_inf * t + tau * q_tr * (1 - mp.exp(-t / tau))
                            tpk = tau * mp.log(-q_tr / q_inf)
                            lo, hi = tpk, mp.mpf(10)
                            for _ in range(140):
                                mid = (lo + hi) / 2
                                if (e_fn(mid) > limit) if exp_phase == "liquid" else (e_fn(mid) < limit):
                                    lo = mid
                                else:
                                    hi = mid
                            t_ex = hi
                            t_b = teq + (t0 - teq) * mp.exp(-t_ex / tau)
                            d_e = c_mp * (t_b - t0)
                            self.assertTrue(
                                ex_lo <= F(mp.nstr(t_ex, 45)) <= ex_hi,
                                f"t_ex={mp.nstr(t_ex, 15)} excluded from [{float(ex_lo)}, {float(ex_hi)}]",
                            )
                            self.assertTrue(
                                tf_lo <= F(mp.nstr(t_b, 45)) <= tf_hi,
                                f"T_b={mp.nstr(t_b, 15)} excluded from [{float(tf_lo)}, {float(tf_hi)}]",
                            )
                            self.assertTrue(
                                de_lo <= F(mp.nstr(d_e, 45)) <= de_hi,
                                f"dE={mp.nstr(d_e, 15)} excluded from [{float(de_lo)}, {float(de_hi)}]",
                            )

    def test_f01_bisect_threshold_default_rejects_unsafe_lo_and_supports_pure_e0_mirrors(self):
        # 1) Default lo_proved_safe=False must refuse to certify lo when before(lo) is False.
        ex_lo, ex_hi = _bisect_threshold(lambda t: Box.exact(t), F(5), F(6), F(10), increasing=True)
        self.assertIsNone(ex_lo)
        self.assertEqual(ex_hi, F(6))
        ex_lo2, ex_hi2 = _bisect_threshold(lambda t: Box.exact(-t), F(-5), F(6), F(10), increasing=False)
        self.assertIsNone(ex_lo2)
        self.assertEqual(ex_hi2, F(6))
        ex_lo3, ex_hi3 = _bisect_threshold(lambda t: Box.bounds(F(4), F(6)), F(5), F(0), F(10), increasing=True)
        self.assertIsNone(ex_lo3)
        self.assertIsNone(ex_hi3)

        # 2) Pure-phase e = 0 mirror (both melting-first and freezing-first) via direct
        #    _bisect_threshold(..., target=0, lo=ts_lo, ..., lo_proved_safe=True) per CR-13.
        delta = F(1, 100)
        law = self._widened_star_law(delta)
        for melting_first, t_tr, t0 in ((True, F(350), F(363)), (False, F(310), F(297))):
            maintained = {**law["imposedTemperaturesK"], "warm": str(t_tr)}
            opens, port_r = physical_port({**law, "imposedTemperaturesK": maintained}, "cool")
            t_eq = Box.bounds(*opens)
            tau = Box.exact(F(100)) * Box.bounds(*port_r)
            row_p = law["supplyResponseBoundsWPerK"]["warm"]
            row_b = law["supplyResponseBoundsWPerK"]["cool"]
            g_pb = -interval(row_p["cool"])
            g_bm = -interval(row_b["middle"])
            share = Box.exact(1) / (Box.exact(1) + g_bm / g_pb)
            q_inf = g_pb * (t_eq - t_tr) + (-interval(row_p["middle"])) * (F(maintained["middle"]) - t_tr)
            q_tr = g_pb * (t0 - t_eq)
            tau_q_tr = Box.exact(F(100)) * share * (t0 - t_eq)
            ratio = -q_tr / q_inf
            r_lo, r_hi = ratio.span()
            t_star = tau * Box.bounds(radial_log(r_lo).span()[0], radial_log(r_hi).span()[1])
            ts_lo, _ = t_star.span()

            def energy_at(t, q_inf=q_inf, tau_q_tr=tau_q_tr, tau=tau):
                if t == 0:
                    return ZERO
                return q_inf * t + tau_q_tr * (Box.exact(1) - exp_neg_interval(Box.exact(t) / tau))

            # Verify interval dependency makes default lo_proved_safe=False return None at ts_lo.
            default_lo, _ = _bisect_threshold(
                energy_at, F(0), ts_lo, F(10), increasing=not melting_first,
            )
            self.assertIsNone(default_lo)

            # With lo_proved_safe=True, ts_lo is retained as lower bound and encloses all 27 realizations.
            ex_lo, ex_hi = _bisect_threshold(
                energy_at, F(0), ts_lo, F(10), increasing=not melting_first, lo_proved_safe=True,
            )
            self.assertEqual(ex_lo, ts_lo)
            self.assertIsNotNone(ex_hi)
            self.assertLess(ex_lo, ex_hi)
            with mp.workdps(70):
                d_mp = mp.mpf(delta.numerator) / delta.denominator
                for s in itertools.product((-1, 0, 1), repeat=3):
                    gwc = mp.mpf(1) + s[0] * d_mp
                    gwm = mp.mpf(3) / 5 + s[1] * d_mp
                    gcm = mp.mpf(3) / 2 + s[2] * d_mp
                    teq_m = (gwc * mp.mpf(int(t_tr)) + gcm * mp.mpf(330)) / (gwc + gcm)
                    tau_m = mp.mpf(100) / (gwc + gcm)
                    qinf_m = gwc * (teq_m - mp.mpf(int(t_tr))) + gwm * (mp.mpf(330) - mp.mpf(int(t_tr)))
                    qtr_m = gwc * (mp.mpf(int(t0)) - teq_m)
                    e_fn = lambda t: qinf_m * t + tau_m * qtr_m * (1 - mp.exp(-t / tau_m))
                    lo, hi = tau_m * mp.log(-qtr_m / qinf_m), mp.mpf(10)
                    for _ in range(200):
                        mid = (lo + hi) / 2
                        if (e_fn(mid) > 0) if melting_first else (e_fn(mid) < 0):
                            lo = mid
                        else:
                            hi = mid
                    self.assertTrue(ex_lo <= F(mp.nstr(hi, 55)) <= ex_hi)
