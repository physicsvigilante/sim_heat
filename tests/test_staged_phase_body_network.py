"""Tests and independent 110-digit mpmath oracles for tools/staged_phase_body_network.py."""
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
from tests.test_terminal_response import CASES, STAR
from tools.offline_provenance import OFFLINE_FLAG_KEYS
from tools.staged_phase_body_network import (
    EVIDENCE_CATEGORY,
    STAGED_SCHEMA,
    investigate,
    main as cli_main,
    solve_from_law,
)
from tools.terminal_response import investigate as terminal_response


def _assert_encloses(tc, pair, mp_val, *, max_width=F(1, 10**12)):
    lo, hi = map(F, pair)
    target = F(mp.nstr(mp_val, 95))
    tc.assertTrue(lo <= target <= hi, f"{target} not in [{lo}, {hi}]")
    tc.assertLess(hi - lo, max_width)


class StagedPhaseBodyNetworkTests(TestCase):
    def test_three_stage_heating_subcooled_solid_to_melting_to_liquid_on_link_and_star(self):
        # LINK (G = 2 W/K, R = 0.5 K/W), hot maintained at 380 K, cold holds 0.5 kg ice at 250 K.
        # c_s = 2100 J/(kg K), c_l = 4200 J/(kg K), L = 334000 J/kg, T_tr = 273.15 K.
        with mp.workdps(110):
            r = mp.mpf("0.5")
            teq = mp.mpf("380")
            t0 = mp.mpf("250")
            ttr = mp.mpf("273.15")
            m = mp.mpf("0.5")
            cs, cl, lat = mp.mpf("2100"), mp.mpf("4200"), mp.mpf("334000")
            tau_s = m * cs * r
            tau_l = m * cl * r
            t1 = tau_s * mp.log((teq - t0) / (teq - ttr))
            q_plat = (teq - ttr) / r
            t2 = t1 + m * lat / q_plat

            # Sample one duration in each of the 3 stages:
            # Stage 1: d = 50 s (< t1 ~ 103 s)
            # Stage 2: d = 500 s (t1 < 500 < t2 ~ 885 s)
            # Stage 3: d = 1500 s (> t2)
            for dur_str, expected_stage in (("50", "solid_sensible"), ("500", "melting_plateau"), ("1500", "liquid_sensible")):
                res = investigate(
                    LINK, "cold", "250", "273.15", "334000", "2100", "4200", "0.5", "0", dur_str,
                )
                self.assertEqual(res["schema"], STAGED_SCHEMA)
                self.assertEqual(res["evidence"]["category"], EVIDENCE_CATEGORY)
                for flag in OFFLINE_FLAG_KEYS:
                    self.assertIs(res[flag], False)
                    self.assertIs(res["evidence"][flag], False)
                tr = res["trajectory"]
                self.assertEqual(tr["regime"], "heating")
                self.assertEqual(tr["finalStage"], expected_stage)
                self.assertIs(tr["postExhaustionModeled"], True)
                _assert_encloses(self, tr["transitionEntryTimeBoundsS"], t1)
                _assert_encloses(self, tr["phaseExhaustionTimeBoundsS"], t2)

                d = mp.mpf(dur_str)
                if expected_stage == "solid_sensible":
                    tf = teq - (teq - t0) * mp.exp(-d / tau_s)
                    epre = m * cs * (tf - t0)
                    elat = mp.mpf(0)
                    epost = mp.mpf(0)
                    sol_f, liq_f = m, mp.mpf(0)
                elif expected_stage == "melting_plateau":
                    tf = ttr
                    epre = m * cs * (ttr - t0)
                    melted = q_plat * (d - t1) / lat
                    elat = melted * lat
                    epost = mp.mpf(0)
                    sol_f, liq_f = m - melted, melted
                else:
                    tf = teq - (teq - ttr) * mp.exp(-(d - t2) / tau_l)
                    epre = m * cs * (ttr - t0)
                    elat = m * lat
                    epost = m * cl * (tf - ttr)
                    sol_f, liq_f = mp.mpf(0), m

                _assert_encloses(self, tr["finalTemperatureBoundsK"], tf)
                _assert_encloses(self, tr["remainingSolidBoundsKg"], sol_f)
                _assert_encloses(self, tr["remainingLiquidBoundsKg"], liq_f)
                _assert_encloses(self, tr["sensibleEnergyPreTransitionBoundsJ"], epre)
                _assert_encloses(self, tr["latentEnergyChangeBoundsJ"], elat)
                _assert_encloses(self, tr["sensibleEnergyPostTransitionBoundsJ"], epost)
                _assert_encloses(self, tr["totalEnergyIntoSubstanceBoundsJ"], epre + elat + epost)

        # Also verify 3-terminal STAR (warm=380, middle=330 maintained; cool holds subcooled ice).
        # STAR leg conductances: first=2, second=3, third=5 => at cool, R_port = 1/5 + 1/(2+3) = 2/5 K/W,
        # T_eq = (2*380 + 3*330)/5 = 350 K.
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        res_star = investigate(
            star_inputs, "cool", "260", "273.15", "334000", "2100", "4200", "0.1", "0", "800",
        )
        self.assertEqual(res_star["portEquivalent"]["equilibriumTemperatureBoundsK"], ["350", "350"])
        self.assertEqual(res_star["portEquivalent"]["portResistanceBoundsKPerW"], ["2/5", "2/5"])
        self.assertEqual(res_star["trajectory"]["finalStage"], "liquid_sensible")
        self.assertEqual(res_star["trajectory"]["remainingSolidBoundsKg"], ["0", "0"])
        self.assertEqual(res_star["trajectory"]["remainingLiquidBoundsKg"], ["1/10", "1/10"])
        with mp.workdps(110):
            r, teq = mp.mpf("0.4"), mp.mpf("350")
            m, cs, cl, lat = mp.mpf("0.1"), mp.mpf("2100"), mp.mpf("4200"), mp.mpf("334000")
            t1 = m * cs * r * mp.log((teq - mp.mpf("260")) / (teq - mp.mpf("273.15")))
            t2 = t1 + m * lat * r / (teq - mp.mpf("273.15"))
            tf = teq - (teq - mp.mpf("273.15")) * mp.exp(-(mp.mpf("800") - t2) / (m * cl * r))
            _assert_encloses(self, res_star["trajectory"]["finalTemperatureBoundsK"], tf)

    def test_three_stage_cooling_warm_liquid_to_freezing_to_subcooled_solid(self):
        # LINK with maintained hot=220 K override; cold holds 0.2 kg warm water at 310 K.
        with mp.workdps(110):
            r = mp.mpf("0.5")
            teq = mp.mpf("220")
            t0 = mp.mpf("310")
            ttr = mp.mpf("273.15")
            m = mp.mpf("0.2")
            cs, cl, lat = mp.mpf("2100"), mp.mpf("4200"), mp.mpf("334000")
            tau_l = m * cl * r
            tau_s = m * cs * r
            t1 = tau_l * mp.log((t0 - teq) / (ttr - teq))
            q_out = (ttr - teq) / r
            t2 = t1 + m * lat / q_out

            for dur_str, expected_stage in (("100", "liquid_sensible"), ("500", "freezing_plateau"), ("1500", "solid_sensible")):
                res = investigate(
                    LINK, "cold", "310", "273.15", "334000", "2100", "4200", "0", "0.2", dur_str,
                    maintained_temperatures_k={"hot": "220"},
                )
                tr = res["trajectory"]
                self.assertEqual(tr["regime"], "cooling")
                self.assertEqual(tr["finalStage"], expected_stage)
                _assert_encloses(self, tr["transitionEntryTimeBoundsS"], t1)
                _assert_encloses(self, tr["phaseExhaustionTimeBoundsS"], t2)
                d = mp.mpf(dur_str)
                if expected_stage == "liquid_sensible":
                    tf = teq + (t0 - teq) * mp.exp(-d / tau_l)
                elif expected_stage == "freezing_plateau":
                    tf = ttr
                else:
                    tf = teq + (ttr - teq) * mp.exp(-(d - t2) / tau_s)
                _assert_encloses(self, tr["finalTemperatureBoundsK"], tf)

    def test_coexisting_bath_chaining_post_exhaustion_equilibrium_and_interval_uncertainty(self):
        # 1. Start at T0 = T_tr with coexisting 0.05 kg solid + 0.05 kg liquid -> melts & warms as 0.1 kg liquid.
        res = investigate(
            LINK, "cold", "273.15", "273.15", "334000", "2100", "4200", "0.05", "0.05", "500",
        )
        self.assertIsNone(res["trajectory"]["transitionEntryTimeBoundsS"])
        self.assertEqual(res["trajectory"]["finalStage"], "liquid_sensible")
        self.assertEqual(res["trajectory"]["remainingSolidBoundsKg"], ["0", "0"])
        self.assertEqual(res["trajectory"]["remainingLiquidBoundsKg"], ["1/10", "1/10"])
        self.assertEqual(res["trajectory"]["sensibleEnergyPreTransitionBoundsJ"], ["0", "0"])
        self.assertEqual(res["trajectory"]["latentEnergyChangeBoundsJ"], ["16700", "16700"])

        # 2. Subcooled heating that never reaches T_tr (T_eq = 265 < T_tr = 273.15).
        stay_solid = investigate(
            LINK, "cold", "250", "273.15", "334000", "2100", "4200", "0.1", "0", "500",
            maintained_temperatures_k={"hot": "265"},
        )
        self.assertEqual(stay_solid["trajectory"]["finalStage"], "solid_sensible")
        self.assertIsNone(stay_solid["trajectory"]["transitionEntryTimeBoundsS"])
        self.assertIsNone(stay_solid["trajectory"]["phaseExhaustionTimeBoundsS"])

        # 3. Exact equilibrium (T_eq == T0).
        eq = investigate(
            LINK, "cold", "273.15", "273.15", "334000", "2100", "4200", "0.05", "0.05", "500",
            maintained_temperatures_k={"hot": "273.15"},
        )
        self.assertEqual(eq["trajectory"]["regime"], "equilibrium")
        self.assertEqual(eq["trajectory"]["totalEnergyIntoSubstanceBoundsJ"], ["0", "0"])

        # 4. Interval resistance straddling stage boundary -> stage_boundary_uncertain with sound enclosure.
        interval_law = {
            "schema": "sim_heat.offline_terminal_response/1",
            "terminals": ["hot", "cold"],
            "imposedTemperaturesK": {"hot": "373.15", "cold": "273.15"},
            "supplyResponseBoundsWPerK": {
                "hot": {"hot": ["1", "2"], "cold": ["-2", "-1"]},
                "cold": {"hot": ["-2", "-1"], "cold": ["1", "2"]},
            },
            "modelSha256": "a" * 64,
            "studySha256": "b" * 64,
            "factsSha256": "c" * 64,
            "nativeExecuted": False,
            "nativeQualified": False,
            "independentlyCertifiedReference": False,
            "runnerConsumable": False,
        }
        # Q_plat in [100, 200] W, m_s*L = 1000 J => t2 in [5, 10] s; query at duration = 7 s!
        unc = solve_from_law(
            interval_law, "cold", "273.15", "273.15", "1000", "2000", "4000", "1", "0", "7",
        )
        self.assertEqual(unc["trajectory"]["finalStage"], "stage_boundary_uncertain")
        self.assertEqual(unc["trajectory"]["phaseExhaustionTimeBoundsS"], ["5", "10"])
        self.assertEqual(F(unc["trajectory"]["finalTemperatureBoundsK"][0]), F("273.15"))
        self.assertGreater(F(unc["trajectory"]["finalTemperatureBoundsK"][1]), F("273.15"))

    def test_cli_entry_point(self):
        payload = {
            "source": {
                "studyPath": str(LINK[0]),
                "rootPath": str(LINK[1]),
                "factsPath": str(LINK[2]),
                "factsSha256": str(LINK[3]),
            },
            "port": "cold",
            "initialTemperatureK": "273.15",
            "transitionTemperatureK": "273.15",
            "specificLatentHeatJPerKg": "334000",
            "solidSpecificHeatJPerKgK": "2100",
            "liquidSpecificHeatJPerKgK": "4200",
            "initialSolidKg": "0.05",
            "initialLiquidKg": "0.05",
            "durationS": "500",
        }
        with tempfile.TemporaryDirectory() as tmp:
            req_path = Path(tmp) / "staged.json"
            req_path.write_text(json.dumps(payload), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli_main(["--request", str(req_path)])
            out = json.loads(buf.getvalue())
            self.assertEqual(out["schema"], STAGED_SCHEMA)
            self.assertEqual(out["trajectory"]["finalStage"], "liquid_sensible")

    def test_negative_controls_inconsistent_phase_state_unresolved_regime_and_provenance(self):
        law = terminal_response(*LINK)

        # Subcooled T0 < T_tr with nonzero liquid mass
        with self.assertRaisesRegex(ValueError, "subcooled initial state"):
            solve_from_law(law, "cold", "260", "273.15", "334000", "2100", "4200", "0.1", "0.1", "100")

        # Superheated T0 > T_tr with nonzero solid mass
        with self.assertRaisesRegex(ValueError, "superheated initial state"):
            solve_from_law(law, "cold", "290", "273.15", "334000", "2100", "4200", "0.1", "0.1", "100")

        # Zero total mass
        with self.assertRaisesRegex(ValueError, "positive total substance mass"):
            solve_from_law(law, "cold", "273.15", "273.15", "334000", "2100", "4200", "0", "0", "100")

        # Unknown port
        with self.assertRaisesRegex(ValueError, "not in pinned network"):
            solve_from_law(law, "missing", "273.15", "273.15", "334000", "2100", "4200", "0.1", "0", "100")

        # Incomplete maintained_temperatures_k
        with self.assertRaisesRegex(ValueError, "maintained_temperatures_k"):
            solve_from_law(
                law, "cold", "273.15", "273.15", "334000", "2100", "4200", "0.1", "0", "100",
                maintained_temperatures_k={},
            )

        # Forged provenance flag
        for flag in OFFLINE_FLAG_KEYS:
            forged = copy.deepcopy(law)
            forged[flag] = True
            with self.assertRaisesRegex(ValueError, "refuses non-False"):
                solve_from_law(forged, "cold", "273.15", "273.15", "334000", "2100", "4200", "0.1", "0", "100")

        # 3-terminal interval law whose T_eq straddles T_tr or T_0 -> refused cleanly.
        wide_three = {
            "schema": "sim_heat.offline_terminal_response/1",
            "terminals": ["a", "b", "c"],
            "imposedTemperaturesK": {"a": "350", "b": "230", "c": "273.15"},
            "supplyResponseBoundsWPerK": {
                "a": {"a": ["1", "2"], "b": ["0", "0"], "c": ["-2", "-1"]},
                "b": {"a": ["0", "0"], "b": ["1", "2"], "c": ["-2", "-1"]},
                "c": {"a": ["-2", "-1"], "b": ["-2", "-1"], "c": ["2", "4"]},
            },
            "modelSha256": "a" * 64,
            "studySha256": "b" * 64,
            "factsSha256": "c" * 64,
            "nativeExecuted": False,
            "nativeQualified": False,
            "independentlyCertifiedReference": False,
            "runnerConsumable": False,
        }
        # At port c, T_eq spans around [250, 350] straddling 300 K (and T_tr = 273.15 K).
        with self.assertRaisesRegex(ValueError, "unresolved across T_eq enclosure"):
            solve_from_law(wide_three, "c", "200", "273.15", "334000", "2100", "4200", "0.1", "0", "100")
        with self.assertRaisesRegex(ValueError, "initial heat-flow direction is unresolved"):
            solve_from_law(wide_three, "c", "300", "273.15", "334000", "2100", "4200", "0", "0.1", "100")
