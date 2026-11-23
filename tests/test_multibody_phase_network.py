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
