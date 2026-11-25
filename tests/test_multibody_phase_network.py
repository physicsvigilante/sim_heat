"""Tests and independent 110-digit mpmath oracles for tools/multibody_phase_network.py."""
import contextlib
import copy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase

from mpmath import mp

from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR, TRIANGLE
from tools.body_phase_bath_exchange import investigate as single_body_investigate
from tools.multibody_phase_network import (
    EVIDENCE_CATEGORY,
    MAX_INITIAL_STEPS,
    MULTIBODY_SCHEMA,
    investigate,
    main as cli_main,
    solve_from_law,
)
from tools.offline_provenance import OFFLINE_FLAG_KEYS
from tools.terminal_response import investigate as terminal_response


def _assert_intervals_overlap(tc, a_pair, b_pair):
    a_lo, a_hi = map(F, a_pair)
    b_lo, b_hi = map(F, b_pair)
    tc.assertLessEqual(max(a_lo, b_lo), min(a_hi, b_hi), f"{a_pair} does not overlap {b_pair}")


def _assert_encloses(tc, pair, mp_val, *, max_width=F(1, 10**12)):
    lo, hi = map(F, pair)
    target = F(mp.nstr(mp_val, 95))
    tc.assertTrue(lo <= target <= hi, f"{target} not in [{lo}, {hi}]")
    tc.assertLess(hi - lo, max_width)


class MultibodyPhaseNetworkTests(TestCase):
    def test_single_body_star_reversing_matches_body_phase_bath_exchange(self):
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        ref = single_body_investigate(
            star_inputs, "cool", "warm", "350", "334000", "0.05", "0.05", "1000", "450", "5000",
        )
        res = investigate(
            star_inputs,
            {
                "warm": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "1000",
                    "initialBodyTemperatureK": "450",
                },
                "middle": {"kind": "maintained", "temperatureK": "330"},
                "cool": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "350",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0.05",
                    "initialLiquidKg": "0.05",
                },
            },
            "5000",
        )
        self.assertEqual(res["schema"], MULTIBODY_SCHEMA)
        self.assertEqual(res["evidence"]["category"], EVIDENCE_CATEGORY)
        for flag in OFFLINE_FLAG_KEYS:
            self.assertIs(res[flag], False)
            self.assertIs(res["evidence"][flag], False)
        self.assertEqual(res["phaseSystem"]["plateauStatus"], ref["plateauStatus"])
        _assert_intervals_overlap(
            self,
            res["ports"]["warm"]["finalBodyTemperatureBoundsK"],
            ref["finalBodyTemperatureBoundsK"],
        )
        _assert_intervals_overlap(
            self,
            res["ports"]["cool"]["latentEnergyIntoBathBoundsJ"],
            ref["latentEnergyIntoBathBoundsJ"],
        )

    def test_two_coupled_bodies_and_phase_bath_on_star_verified_against_110_digit_expm(self):
        # STAR effective conductances: W_wm = 3/5, W_wc = 1, W_mc = 3/2 W/K.
        # warm: C1 = 500 J/K, T1(0) = 420 K; middle: C2 = 1500 J/K, T2(0) = 220 K;
        # cool: phase bath at T_tr = 273.15 K with ample solid & liquid inventory.
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        res = investigate(
            star_inputs,
            {
                "warm": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "500",
                    "initialBodyTemperatureK": "420",
                },
                "middle": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "1500",
                    "initialBodyTemperatureK": "220",
                },
                "cool": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "1",
                },
            },
            "600",
        )
        self.assertEqual(res["phaseSystem"]["plateauStatus"], "coexisting")
        self.assertEqual(res["modeledDurationBoundsS"], ["600", "600"])

        # Independent 110-digit mpmath matrix exponential oracle.
        with mp.workdps(110):
            w_wm, w_wc, w_mc = mp.mpf("0.6"), mp.mpf("1.0"), mp.mpf("1.5")
            c1, c2 = mp.mpf("500"), mp.mpf("1500")
            tp = mp.mpf("273.15")
            d = mp.mpf("600")
            # ODE in shifted variables z_i = T_i - tp: dz/dt = M z
            m = mp.matrix([
                [-(w_wm + w_wc) / c1, w_wm / c1],
                [w_wm / c2, -(w_wm + w_mc) / c2],
            ])
            z0 = mp.matrix([mp.mpf("420") - tp, mp.mpf("220") - tp])
            z_end = mp.expm(m * d) * z0
            t1_end = z_end[0] + tp
            t2_end = z_end[1] + tp
            # Energy conservation: E_cool = -(C1*(T1_end - T1_0) + C2*(T2_end - T2_0))
            e_cool = -(c1 * (t1_end - mp.mpf("420")) + c2 * (t2_end - mp.mpf("220")))

            _assert_encloses(self, res["ports"]["warm"]["finalBodyTemperatureBoundsK"], t1_end)
            _assert_encloses(self, res["ports"]["middle"]["finalBodyTemperatureBoundsK"], t2_end)
            _assert_encloses(self, res["ports"]["cool"]["latentEnergyIntoBathBoundsJ"], e_cool)

    def test_two_body_nonmonotonic_intermediate_peak_exhaustion_is_caught(self):
        # warm (small C=200, hot 500 K) initially melts cool (T_tr=300 K) because
        # Q_cool(0) = 1*(500-300) + 1.5*(220-300) = +200 - 120 = +80 W > 0!
        # Meanwhile middle (huge C=10000, cold 220 K) stays cold and drags E_cool(t)
        # strongly negative at duration = 1000 s (E_cool(1000) < 0).
        # With tiny solid inventory e_solid = 2000 J (solid=0.02 kg, L=100000 J/kg),
        # E_cool(t) peaks well above +2000 J around t ~ 60 s before reversing!
        # The solver MUST catch this intermediate peak exhaustion rather than seeing E(1000) < e_solid.
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        res = investigate(
            star_inputs,
            {
                "warm": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "200",
                    "initialBodyTemperatureK": "500",
                },
                "middle": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "10000",
                    "initialBodyTemperatureK": "220",
                },
                "cool": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "300",
                    "specificLatentHeatJPerKg": "100000",
                    "initialSolidKg": "0.02",  # e_solid = 2000 J -> exceeded during early peak!
                    "initialLiquidKg": "5",
                },
            },
            "1000",
        )
        self.assertEqual(res["phaseSystem"]["plateauStatus"], "exhausted")
        self.assertEqual(res["phaseSystem"]["firstExhaustedCandidatePorts"], ["cool"])
        self.assertEqual(res["ports"]["cool"]["exhaustedPhase"], "solid")
        self.assertEqual(res["ports"]["cool"]["remainingSolidBoundsKg"], ["0", "0"])
        self.assertEqual(res["ports"]["cool"]["latentEnergyIntoBathBoundsJ"], ["2000", "2000"])
        mod_lo, mod_hi = map(F, res["modeledDurationBoundsS"])
        # Independent 110-digit mpmath.expm oracle for the exact FIRST E_cool(t) = 2000 J crossing.
        with mp.workdps(110):
            w_wm, w_wc, w_mc = mp.mpf("0.6"), mp.mpf("1.0"), mp.mpf("1.5")
            c1, c2 = mp.mpf("200"), mp.mpf("10000")
            tp = mp.mpf("300")
            m = mp.matrix([
                [-(w_wm + w_wc) / c1, w_wm / c1],
                [w_wm / c2, -(w_wm + w_mc) / c2],
            ])
            z0 = mp.matrix([mp.mpf("500") - tp, mp.mpf("220") - tp])

            def e_cool(t):
                zt = mp.expm(m * t) * z0
                return -(c1 * (zt[0] - z0[0]) + c2 * (zt[1] - z0[1]))

            t_first = mp.findroot(lambda t: e_cool(t) - mp.mpf("2000"), mp.mpf("46"))
            _assert_encloses(self, res["modeledDurationBoundsS"], t_first, max_width=F(1, 10**5))
        self.assertGreater(mod_lo, F("46.37"))
        self.assertLess(mod_hi, F("46.38"))

    def test_two_isolated_bodies_on_link_and_two_competing_phase_baths_on_triangle(self):
        # 1. Two isolated bodies on LINK (0 phase baths, 0 maintained reservoirs)
        res_iso = investigate(
            LINK,
            {
                "hot": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "1000",
                    "initialBodyTemperatureK": "400",
                },
                "cold": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "3000",
                    "initialBodyTemperatureK": "300",
                },
            },
            "500",
        )
        self.assertIsNone(res_iso["phaseSystem"])
        # Exact analytical solution: T_eq = (1000*400 + 3000*300)/4000 = 325 K,
        # tau = (C1*C2/(C1+C2)) / G = 750 / 2 = 375 s.
        with mp.workdps(110):
            e = mp.exp(-mp.mpf("500") / mp.mpf("375"))
            t_hot = mp.mpf("325") + mp.mpf("75") * e
            t_cold = mp.mpf("325") - mp.mpf("25") * e
            _assert_encloses(self, res_iso["ports"]["hot"]["finalBodyTemperatureBoundsK"], t_hot)
            _assert_encloses(self, res_iso["ports"]["cold"]["finalBodyTemperatureBoundsK"], t_cold)

        # 2. TRIANGLE with 1 lumped body + 2 competing phase baths (warm exhausts first, cool stops early)
        tri_inputs = (CASES / "triangle" / "study.json", CASES / "triangle", CASES / "triangle" / "facts.json", TRIANGLE)
        res_tri = investigate(
            tri_inputs,
            {
                "warm": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "400",
                    "specificLatentHeatJPerKg": "1000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0.01",  # freezes out quickly
                },
                "cool": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "300",
                    "specificLatentHeatJPerKg": "1000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "1",
                },
                "middle": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "500",
                    "initialBodyTemperatureK": "350",
                },
            },
            "100",
        )
        self.assertEqual(res_tri["phaseSystem"]["plateauStatus"], "exhausted")
        self.assertEqual(res_tri["phaseSystem"]["firstExhaustedCandidatePorts"], ["warm"])
        self.assertEqual(res_tri["ports"]["warm"]["plateauStatusAtModeledStop"], "exhausted")
        self.assertEqual(res_tri["ports"]["warm"]["statusAtRequestedDuration"], "exhausted")
        self.assertEqual(res_tri["ports"]["warm"]["remainingLiquidBoundsKg"], ["0", "0"])
        self.assertEqual(res_tri["ports"]["cool"]["plateauStatusAtModeledStop"], "coexisting")
        self.assertEqual(
            res_tri["ports"]["cool"]["statusAtRequestedDuration"],
            "not_modeled_after_system_exhaustion",
        )

    def test_cli_entry_point_and_negative_controls(self):
        payload = {
            "source": {
                "studyPath": str(LINK[0]),
                "rootPath": str(LINK[1]),
                "factsPath": str(LINK[2]),
                "factsSha256": str(LINK[3]),
            },
            "ports": {
                "hot": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "1000",
                    "initialBodyTemperatureK": "400",
                },
                "cold": {
                    "kind": "lumped_body",
                    "heatCapacityJPerK": "3000",
                    "initialBodyTemperatureK": "300",
                },
            },
            "durationS": "500",
        }
        with tempfile.TemporaryDirectory() as tmp:
            req_path = Path(tmp) / "mb.json"
            req_path.write_text(json.dumps(payload), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli_main(["--request", str(req_path)])
            out = json.loads(buf.getvalue())
            self.assertEqual(out["schema"], MULTIBODY_SCHEMA)

        law = terminal_response(*LINK)
        # Zero lumped bodies -> refused
        with self.assertRaisesRegex(ValueError, "at least one lumped_body"):
            solve_from_law(
                law,
                {
                    "hot": {"kind": "maintained", "temperatureK": "380"},
                    "cold": {"kind": "maintained", "temperatureK": "280"},
                },
                "100",
            )
        # Extra typo key -> refused
        with self.assertRaisesRegex(ValueError, "unsupported keys"):
            solve_from_law(
                law,
                {
                    "hot": {
                        "kind": "lumped_body",
                        "heatCapacityJPerK": "1000",
                        "initialBodyTemperatureK": "400",
                        "extraKey": "1",
                    },
                    "cold": {"kind": "maintained", "temperatureK": "300"},
                },
                "100",
            )
        # Positive boundary (initial_steps = MAX_INITIAL_STEPS) accepted; oversized/invalid refused.
        link_body_phase = {
            "hot": {
                "kind": "lumped_body",
                "heatCapacityJPerK": "1000",
                "initialBodyTemperatureK": "400",
            },
            "cold": {
                "kind": "phase_bath",
                "transitionTemperatureK": "273.15",
                "specificLatentHeatJPerKg": "334000",
                "initialSolidKg": "1",
                "initialLiquidKg": "1",
            },
        }
        ok_max = solve_from_law(law, link_body_phase, "10", initial_steps=MAX_INITIAL_STEPS)
        self.assertEqual(ok_max["phaseSystem"]["plateauStatus"], "coexisting")
        for bad_steps in (0, -1, True, MAX_INITIAL_STEPS + 1, 10**9):
            with self.assertRaisesRegex(ValueError, "initial_steps must be an integer"):
                solve_from_law(law, link_body_phase, "10", initial_steps=bad_steps)

        # CLI oversized initialSteps rejected BEFORE any grid allocation.
        bad_cli = copy.deepcopy(payload)
        bad_cli["initialSteps"] = 10**9
        with tempfile.TemporaryDirectory() as tmp:
            req_path = Path(tmp) / "oversized.json"
            req_path.write_text(json.dumps(bad_cli), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "initial_steps must be an integer"):
                cli_main(["--request", str(req_path)])

        # Forged provenance flag -> refused
        for flag in OFFLINE_FLAG_KEYS:
            forged = copy.deepcopy(law)
            forged[flag] = True
            with self.assertRaisesRegex(ValueError, "refuses non-False"):
                solve_from_law(
                    forged,
                    {
                        "hot": {
                            "kind": "lumped_body",
                            "heatCapacityJPerK": "1000",
                            "initialBodyTemperatureK": "400",
                        },
                        "cold": {"kind": "maintained", "temperatureK": "300"},
                    },
                    "100",
                )

    def test_f03_near_miss_star_r_9999_and_999999_and_triangle_two_bath_candidates(self):
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        star_law = terminal_response(*star_inputs)
        tri_inputs = (CASES / "triangle" / "study.json", CASES / "triangle", CASES / "triangle" / "facts.json", TRIANGLE)
        tri_law = terminal_response(*tri_inputs)

        # 1) STAR r = 0.9999 and r = 0.999999 with initial_steps=16:
        # Exact peak E_peak = 100*(276/5 - 48/5*ln(27/4)) ~ 3686.8390066 J; liquid exhausts at 353.293930845 s.
        with mp.workdps(80):
            e_peak_star = 100 * (mp.mpf(276) / 5 - mp.mpf(48) / 5 * mp.log(mp.mpf(27) / 4))
            e_fn = lambda t: mp.mpf(-24) * t + mp.mpf(6480) * (1 - mp.exp(-t / 40))
            t_liq_star = mp.findroot(lambda t: e_fn(t) + 2000, (mp.mpf(300), mp.mpf(400)))
            tb_liq_star = 338 + 162 * mp.exp(-t_liq_star / 40)
            em_liq_star = -(mp.mpf(100) * (tb_liq_star - 500) + mp.mpf(-2000))

            for ratio_s in ("0.9999", "0.999999"):
                solid_str = mp.nstr(e_peak_star / mp.mpf(ratio_s), 16)
                ports = {
                    "warm": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "350",
                        "specificLatentHeatJPerKg": "1",
                        "initialSolidKg": solid_str,
                        "initialLiquidKg": "2000",
                    },
                    "cool": {"kind": "lumped_body", "heatCapacityJPerK": "100", "initialBodyTemperatureK": "500"},
                    "middle": {"kind": "maintained", "temperatureK": "330"},
                }
                res = solve_from_law(star_law, ports, "400", initial_steps=16)
                self.assertEqual(res["phaseSystem"]["plateauStatus"], "exhausted")
                self.assertEqual(res["phaseSystem"]["firstExhaustedCandidatePorts"], ["warm"])
                self.assertEqual(res["ports"]["warm"]["exhaustedPhase"], "liquid")
                self.assertEqual(res["solverMetadata"]["terminationReason"], "resolved")
                _assert_encloses(self, res["modeledDurationBoundsS"], t_liq_star, max_width=F(1, 10**4))
                _assert_encloses(self, res["ports"]["cool"]["finalBodyTemperatureBoundsK"], tb_liq_star, max_width=F(1, 10**2))
                _assert_encloses(
                    self, res["ports"]["middle"]["integratedEnergyIntoReservoirBoundsJ"], em_liq_star, max_width=F(1)
                )

            # 2) Two-bath candidate case on TRIANGLE (actual M01 geometry):
            # middle has near-miss peak (r = 0.9999 and 0.999999), cool genuinely exhausts solid later.
            m_tri = tri_law["supplyResponseBoundsWPerK"]
            w_wm = -mp.mpf(F(m_tri["warm"]["middle"][0]).numerator) / F(m_tri["warm"]["middle"][0]).denominator
            w_wc = -mp.mpf(F(m_tri["warm"]["cool"][0]).numerator) / F(m_tri["warm"]["cool"][0]).denominator
            w_mc = -mp.mpf(F(m_tri["middle"]["cool"][0]).numerator) / F(m_tri["middle"]["cool"][0]).denominator
            g_w = w_wm + w_wc
            teq_w = (w_wm * 350 + w_wc * 300) / g_w
            tau_w = mp.mpf(100) / g_w
            q_mid = lambda t: w_wm * (teq_w + (500 - teq_w) * mp.exp(-t / tau_w) - 350) + w_mc * (300 - 350)
            e_mid = lambda t: (
                w_wm * ((teq_w - 350) * t + (500 - teq_w) * tau_w * (1 - mp.exp(-t / tau_w)))
                + w_mc * (300 - 350) * t
            )
            e_cool = lambda t: (
                w_wc * ((teq_w - 300) * t + (500 - teq_w) * tau_w * (1 - mp.exp(-t / tau_w)))
                + w_mc * (350 - 300) * t
            )
            t_star_mid = mp.findroot(q_mid, (mp.mpf(1), mp.mpf(100)))
            e_peak_mid = e_mid(t_star_mid)
            cool_s = e_cool(200) * mp.mpf("0.7")
            t_cool_exh = mp.findroot(lambda t: e_cool(t) - cool_s, (mp.mpf(10), mp.mpf(200)))

            for ratio_s in ("0.9999", "0.999999"):
                ports_2b = {
                    "warm": {"kind": "lumped_body", "heatCapacityJPerK": "100", "initialBodyTemperatureK": "500"},
                    "middle": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "350",
                        "specificLatentHeatJPerKg": "1",
                        "initialSolidKg": mp.nstr(e_peak_mid / mp.mpf(ratio_s), 16),
                        "initialLiquidKg": "100000",
                    },
                    "cool": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "300",
                        "specificLatentHeatJPerKg": "1",
                        "initialSolidKg": mp.nstr(cool_s, 14),
                        "initialLiquidKg": "100000",
                    },
                }
                res_2b = solve_from_law(tri_law, ports_2b, "200", initial_steps=16)
                self.assertEqual(res_2b["phaseSystem"]["plateauStatus"], "exhausted")
                self.assertEqual(res_2b["phaseSystem"]["firstExhaustedCandidatePorts"], ["cool"])
                self.assertEqual(res_2b["ports"]["cool"]["exhaustedPhase"], "solid")
                self.assertEqual(res_2b["solverMetadata"]["terminationReason"], "resolved")
                _assert_encloses(self, res_2b["modeledDurationBoundsS"], t_cool_exh, max_width=F(1, 10**4))

    def test_f03_coexisting_near_miss_cert_hi_none_and_forced_small_budget_soundness(self):
        # CR-02 discriminating witness: STAR solid=3687.2079161, liquid=5000, D=400.
        # Bath never exhausts; exact coexisting state at D=400: T_cool ~ 338.0073548 K, E_warm ~ -3120.294192 J.
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        star_law = terminal_response(*star_inputs)
        ports_coex = {
            "warm": {
                "kind": "phase_bath",
                "transitionTemperatureK": "350",
                "specificLatentHeatJPerKg": "1",
                "initialSolidKg": "3687.2079161",
                "initialLiquidKg": "5000",
            },
            "cool": {"kind": "lumped_body", "heatCapacityJPerK": "100", "initialBodyTemperatureK": "500"},
            "middle": {"kind": "maintained", "temperatureK": "330"},
        }
        with mp.workdps(80):
            t_400 = mp.mpf(338) + mp.mpf(162) * mp.exp(mp.mpf(-10))
            e_warm_400 = mp.mpf(-24) * 400 + mp.mpf(6480) * (1 - mp.exp(mp.mpf(-10)))
            e_mid_400 = -(mp.mpf(100) * (t_400 - 500) + e_warm_400)

            # Forced tiny prune budget -> cert_hi is None, exhaustion_time_uncertain, MUST enclose state_at(duration)!
            unc = solve_from_law(
                star_law, ports_coex, "400", initial_steps=16, max_prune_refinements=2, max_bisect_refinements=2
            )
            self.assertEqual(unc["phaseSystem"]["plateauStatus"], "exhaustion_time_uncertain")
            self.assertEqual(unc["solverMetadata"]["terminationReason"], "refinement_budget")
            self.assertEqual(unc["solverMetadata"]["pruneRefinementsUsed"], 2)
            _assert_encloses(self, unc["ports"]["cool"]["finalBodyTemperatureBoundsK"], t_400, max_width=F(500))
            _assert_encloses(self, unc["ports"]["warm"]["latentEnergyIntoBathBoundsJ"], e_warm_400, max_width=F(20000))
            _assert_encloses(
                self, unc["ports"]["middle"]["integratedEnergyIntoReservoirBoundsJ"], e_mid_400, max_width=F(50000)
            )

            # Default budgets resolve the near-miss peak completely -> coexisting!
            ok = solve_from_law(star_law, ports_coex, "400", initial_steps=16)
            self.assertEqual(ok["phaseSystem"]["plateauStatus"], "coexisting")
            self.assertEqual(ok["solverMetadata"]["terminationReason"], "resolved")
            _assert_encloses(self, ok["ports"]["cool"]["finalBodyTemperatureBoundsK"], t_400)
            _assert_encloses(self, ok["ports"]["warm"]["latentEnergyIntoBathBoundsJ"], e_warm_400)
            _assert_encloses(self, ok["ports"]["middle"]["integratedEnergyIntoReservoirBoundsJ"], e_mid_400)

            # Forced small budgets on exhausted case: sound & reports refinement_budget.
            ports_exh = copy.deepcopy(ports_coex)
            ports_exh["warm"]["initialLiquidKg"] = "2000"
            e_fn = lambda t: mp.mpf(-24) * t + mp.mpf(6480) * (1 - mp.exp(-t / 40))
            t_liq = mp.findroot(lambda t: e_fn(t) + 2000, (mp.mpf(300), mp.mpf(400)))
            tb_liq = 338 + 162 * mp.exp(-t_liq / 40)
            em_liq = -(mp.mpf(100) * (tb_liq - 500) + mp.mpf(-2000))
            exh_small = solve_from_law(
                star_law, ports_exh, "400", initial_steps=16, max_prune_refinements=2, max_bisect_refinements=2
            )
            self.assertEqual(exh_small["phaseSystem"]["plateauStatus"], "exhausted")
            self.assertEqual(exh_small["solverMetadata"]["terminationReason"], "refinement_budget")
            _assert_encloses(self, exh_small["modeledDurationBoundsS"], t_liq, max_width=F(400))
            _assert_encloses(self, exh_small["ports"]["cool"]["finalBodyTemperatureBoundsK"], tb_liq, max_width=F(500))
            _assert_encloses(self, exh_small["ports"]["warm"]["latentEnergyIntoBathBoundsJ"], mp.mpf(-2000), max_width=F(10000))
            _assert_encloses(
                self, exh_small["ports"]["middle"]["integratedEnergyIntoReservoirBoundsJ"], em_liq, max_width=F(50000)
            )

    def test_f04_pure_phase_regimes_epsilon_limit_zero_flux_and_small_first_cell(self):
        link_law = terminal_response(*LINK)
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        star_law = terminal_response(*star_inputs)

        # 1) Pure solid ice + inflow (Opus P1 case): LINK, 1 kg ice at 273 K, 373 K body C=4200, D=10 s.
        # Exact oracle: tau = C / G = 4200 / 2 = 2100 s, E(10) = 4200*100*(1 - exp(-10/2100)).
        pure_s = solve_from_law(
            link_law,
            {
                "hot": {"kind": "lumped_body", "heatCapacityJPerK": "4200", "initialBodyTemperatureK": "373"},
                "cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0",
                },
            },
            "10",
        )
        self.assertEqual(pure_s["phaseSystem"]["plateauStatus"], "coexisting")
        self.assertIs(pure_s["phaseSystem"]["exhaustedAtStart"], False)
        self.assertIs(pure_s["ports"]["cold"]["exhaustedAtStart"], False)
        self.assertIsNone(pure_s["ports"]["cold"]["exhaustedPhase"])
        with mp.workdps(80):
            e_ex = mp.mpf(420000) * (1 - mp.exp(-mp.mpf(10) / 2100))
            t_ex = mp.mpf(273) + mp.mpf(100) * mp.exp(-mp.mpf(10) / 2100)
            m_melt = e_ex / mp.mpf(334000)
            _assert_encloses(self, pure_s["ports"]["cold"]["latentEnergyIntoBathBoundsJ"], e_ex)
            _assert_encloses(self, pure_s["ports"]["hot"]["finalBodyTemperatureBoundsK"], t_ex)
            _assert_encloses(self, pure_s["ports"]["cold"]["remainingSolidBoundsKg"], mp.mpf(1) - m_melt)
            _assert_encloses(self, pure_s["ports"]["cold"]["remainingLiquidBoundsKg"], m_melt)

        # Epsilon-convergence check (eps in {1e-9, 1e-12})
        for eps_s in ("0.000000001", "0.000000000001"):
            eps = F(eps_s)
            ref = solve_from_law(
                link_law,
                {
                    "hot": {"kind": "lumped_body", "heatCapacityJPerK": "4200", "initialBodyTemperatureK": "373"},
                    "cold": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "1",
                        "initialLiquidKg": eps_s,
                    },
                },
                "10",
            )
            self.assertEqual(pure_s["modeledDurationBoundsS"], ref["modeledDurationBoundsS"])
            self.assertEqual(
                pure_s["ports"]["hot"]["finalBodyTemperatureBoundsK"],
                ref["ports"]["hot"]["finalBodyTemperatureBoundsK"],
            )
            self.assertEqual(
                pure_s["ports"]["cold"]["latentEnergyIntoBathBoundsJ"],
                ref["ports"]["cold"]["latentEnergyIntoBathBoundsJ"],
            )
            self.assertEqual(
                pure_s["ports"]["cold"]["remainingSolidBoundsKg"],
                ref["ports"]["cold"]["remainingSolidBoundsKg"],
            )
            lo0, hi0 = map(F, pure_s["ports"]["cold"]["remainingLiquidBoundsKg"])
            loe, hie = map(F, ref["ports"]["cold"]["remainingLiquidBoundsKg"])
            self.assertLessEqual(abs(lo0 - (loe - eps)), (hi0 - lo0) + (hie - loe) + F(1, 10**30))

        # 2) Pure liquid + freezing outflow mirror.
        pure_l = solve_from_law(
            link_law,
            {
                "hot": {"kind": "lumped_body", "heatCapacityJPerK": "4200", "initialBodyTemperatureK": "200"},
                "cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0",
                    "initialLiquidKg": "1",
                },
            },
            "10",
        )
        self.assertEqual(pure_l["phaseSystem"]["plateauStatus"], "coexisting")
        self.assertIs(pure_l["phaseSystem"]["exhaustedAtStart"], False)
        self.assertLess(F(pure_l["ports"]["cold"]["latentEnergyIntoBathBoundsJ"][1]), F(0))

        # 3) Regime (b): pure solid + outflow -> exhaustedAtStart=True (for both D=10 and D=0).
        for dur_s in ("10", "0"):
            exh = solve_from_law(
                link_law,
                {
                    "hot": {"kind": "lumped_body", "heatCapacityJPerK": "4200", "initialBodyTemperatureK": "200"},
                    "cold": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "1",
                        "initialLiquidKg": "0",
                    },
                },
                dur_s,
            )
            self.assertEqual(exh["phaseSystem"]["plateauStatus"], "exhausted")
            self.assertIs(exh["phaseSystem"]["exhaustedAtStart"], True)
            self.assertEqual(exh["phaseSystem"]["firstExhaustionTimeBoundsS"], ["0", "0"])
            self.assertEqual(exh["modeledDurationBoundsS"], ["0", "0"])
            self.assertEqual(exh["phaseSystem"]["firstExhaustedCandidatePorts"], ["cold"])
            self.assertIs(exh["ports"]["cold"]["exhaustedAtStart"], True)
            self.assertEqual(exh["ports"]["cold"]["exhaustedPhase"], "liquid")
            self.assertEqual(exh["ports"]["cold"]["remainingSolidBoundsKg"], ["1", "1"])
            self.assertEqual(exh["ports"]["cold"]["remainingLiquidBoundsKg"], ["0", "0"])

        # 4) Regime (c): exact equilibrium -> coexisting at T_tr, exhaustedAtStart=False.
        eq = solve_from_law(
            link_law,
            {
                "hot": {"kind": "lumped_body", "heatCapacityJPerK": "4200", "initialBodyTemperatureK": "273"},
                "cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0",
                },
            },
            "100",
        )
        self.assertEqual(eq["phaseSystem"]["plateauStatus"], "coexisting")
        self.assertIs(eq["phaseSystem"]["exhaustedAtStart"], False)
        self.assertEqual(eq["ports"]["cold"]["remainingSolidBoundsKg"], ["1", "1"])
        self.assertEqual(eq["ports"]["cold"]["remainingLiquidBoundsKg"], ["0", "0"])

        # 5) Regime (d) OQ-C3: zero initial flux with nonzero derivative (both Q'(0)>0 and Q'(0)<0 on STAR)
        #    returns conservative exhaustion_time_uncertain modeled from t = 0.
        for t_tr, t_0 in (("310", "298"), ("350", "362")):
            zf = solve_from_law(
                star_law,
                {
                    "warm": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": t_tr,
                        "specificLatentHeatJPerKg": "1000",
                        "initialSolidKg": "50",
                        "initialLiquidKg": "0",
                    },
                    "cool": {"kind": "lumped_body", "heatCapacityJPerK": "100", "initialBodyTemperatureK": t_0},
                    "middle": {"kind": "maintained", "temperatureK": "330"},
                },
                "120",
            )
            self.assertEqual(zf["phaseSystem"]["plateauStatus"], "exhaustion_time_uncertain")
            self.assertIs(zf["phaseSystem"]["exhaustedAtStart"], False)
            self.assertEqual(zf["modeledDurationBoundsS"][0], "0")

        # 6) Small solid inventory on the first cell [0, b]: solid exhaustion inside [0, b] MUST be caught!
        # LINK: hot=373 K, C=4200, cold pure solid 0.001 kg (L=1000 -> e_solid=1 J), D=160 s -> grid[1]=10 s.
        # Q(0) = 200 W, so solid exhausts at t ~ 0.005 s << grid[1]=10 s!
        small_inv = solve_from_law(
            link_law,
            {
                "hot": {"kind": "lumped_body", "heatCapacityJPerK": "4200", "initialBodyTemperatureK": "373"},
                "cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273",
                    "specificLatentHeatJPerKg": "1000",
                    "initialSolidKg": "0.001",
                    "initialLiquidKg": "0",
                },
            },
            "160",
            initial_steps=16,
        )
        self.assertEqual(small_inv["phaseSystem"]["plateauStatus"], "exhausted")
        self.assertIs(small_inv["phaseSystem"]["exhaustedAtStart"], False)
        self.assertEqual(small_inv["ports"]["cold"]["exhaustedPhase"], "solid")
        self.assertEqual(small_inv["ports"]["cold"]["remainingSolidBoundsKg"], ["0", "0"])
        self.assertLess(F(small_inv["modeledDurationBoundsS"][1]), F("0.01"))

        # 7) Zero total mass still refused.
        with self.assertRaises(ValueError):
            solve_from_law(
                link_law,
                {
                    "hot": {"kind": "lumped_body", "heatCapacityJPerK": "4200", "initialBodyTemperatureK": "373"},
                    "cold": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "0",
                        "initialLiquidKg": "0",
                    },
                },
                "10",
            )
