"""Tests and independent 110-digit mpmath oracles for tools/multiport_thermal_network.py."""
import contextlib
import copy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase

from mpmath import mp

from qualification.h1_n13.conduction import interval
from tests.test_loaded_thermal_ports import LINK
from tests.test_terminal_response import CASES, STAR, TRIANGLE
from tools.latent_heat_bath import investigate as latent_investigate
from tools.multiport_thermal_network import (
    EVIDENCE_CATEGORY,
    MULTIPORT_SCHEMA,
    investigate,
    main as cli_main,
    solve_from_law,
)
from tools.offline_provenance import OFFLINE_FLAG_KEYS
from tools.radial_phase_bath import investigate as radial_phase_investigate
from tools.radiating_radial_layers import solve as rrl_solve
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


class MultiportThermalNetworkTests(TestCase):
    def test_single_nonlinear_port_matches_existing_radial_phase_and_latent_solvers(self):
        # 1. LINK cylindrical critical-radius radial_phase_bath parity
        for r_out in ("0.12", "0.20", "0.50"):
            ref = radial_phase_investigate(
                LINK, "hot", "cold", "273.15", "334000", "0.02", "0.03", "5000",
                "0.1", [(r_out, "2")], "293.15", "0", "0.0000000567", "1",
                air_k="293.15", h_w_per_m2_k="10",
            )
            res = investigate(
                LINK,
                {
                    "hot": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273.15",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "0.02",
                        "initialLiquidKg": "0.03",
                    },
                    "cold": {
                        "kind": "radial_shell",
                        "geometry": {
                            "kind": "cylinder",
                            "innerRadiusM": "0.1",
                            "cylinderLengthM": "1",
                            "layers": [{"outerRadiusM": r_out, "conductivityWPerMK": "2"}],
                        },
                        "exterior": {
                            "enclosureTemperatureK": "293.15",
                            "emissivity": "0",
                            "sigmaWPerM2K4": "0.0000000567",
                            "airTemperatureK": "293.15",
                            "convectionCoefficientWPerM2K": "10",
                        },
                    },
                },
                duration_s="5000",
            )
            self.assertEqual(res["schema"], MULTIPORT_SCHEMA)
            self.assertEqual(res["evidence"]["category"], EVIDENCE_CATEGORY)
            for flag in OFFLINE_FLAG_KEYS:
                self.assertIs(res[flag], False)
                self.assertIs(res["evidence"][flag], False)
            self.assertEqual(res["ports"]["hot"]["phaseProcess"], ref["phaseProcess"])
            self.assertEqual(res["phaseSystem"]["plateauStatus"], ref["plateauStatus"])
            _assert_intervals_overlap(
                self,
                res["ports"]["hot"]["bathInflowDuringPlateauBoundsW"],
                ref["bathInflowDuringPlateauBoundsW"],
            )
            _assert_intervals_overlap(
                self,
                res["ports"]["cold"]["outwardHeatRateBoundsW"],
                ref["radialShell"]["outwardHeatRateBoundsW"],
            )
            _assert_intervals_overlap(
                self,
                res["ports"]["hot"]["exhaustionTimeBoundsS"],
                ref["exhaustionTimeBoundsS"],
            )
            _assert_intervals_overlap(
                self,
                res["ports"]["hot"]["remainingSolidBoundsKg"],
                ref["remainingSolidBoundsKg"],
            )

        # 2. STAR maintained + phase_bath + radiating_surface parity
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        ref_star = latent_investigate(
            star_inputs, "cool", "273.15", "334000", "0.05", "0.05", "600",
            exterior=("290", "0.5", "0.8", "0.0000000567"), surface_port="warm",
        )
        res_star = investigate(
            star_inputs,
            {
                "cool": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0.05",
                    "initialLiquidKg": "0.05",
                },
                "middle": {"kind": "maintained", "temperatureK": "330"},
                "warm": {
                    "kind": "radiating_surface",
                    "areaM2": "0.5",
                    "enclosureTemperatureK": "290",
                    "emissivity": "0.8",
                    "sigmaWPerM2K4": "0.0000000567",
                },
            },
            duration_s="600",
        )
        _assert_intervals_overlap(
            self,
            res_star["ports"]["cool"]["bathInflowDuringPlateauBoundsW"],
            ref_star["bathInflowDuringPlateauBoundsW"],
        )
        _assert_intervals_overlap(
            self,
            res_star["ports"]["warm"]["temperatureBoundsK"],
            ref_star["radiatingSurface"]["temperatureBoundsK"],
        )

    def test_two_coupled_nonlinear_ports_on_link_verified_against_110_digit_oracle(self):
        # Neither port is fixed: hot = radiating+convecting surface facing a hot furnace,
        # cold = cylindrical radial shell facing cool air+enclosure.
        res = investigate(
            LINK,
            {
                "hot": {
                    "kind": "radiating_surface",
                    "areaM2": "0.4",
                    "enclosureTemperatureK": "800",
                    "emissivity": "0.8",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "600",
                    "convectionCoefficientWPerM2K": "12",
                },
                "cold": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "cylinder",
                        "innerRadiusM": "0.1",
                        "cylinderLengthM": "1",
                        "layers": [{"outerRadiusM": "0.25", "conductivityWPerMK": "2"}],
                    },
                    "exterior": {
                        "enclosureTemperatureK": "290",
                        "emissivity": "0.5",
                        "sigmaWPerM2K4": "0.0000000567",
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "10",
                    },
                },
            },
        )
        self.assertIsNone(res["phaseSystem"])
        self.assertTrue(res["solverMetadata"]["residualCertified"])
        bal_lo, bal_hi = map(F, res["systemEnergyBalanceBoundsW"])
        self.assertLessEqual(bal_lo, F(0))
        self.assertGreaterEqual(bal_hi, F(0))

        # Independent 110-digit mpmath coupled nonlinear root solve.
        # LINK wall conductance is G_link = 2 W/K.
        with mp.workdps(110):
            g_link = mp.mpf("2")
            r_shell = mp.log(mp.mpf("0.25") / mp.mpf("0.1")) / (2 * mp.pi * mp.mpf("2") * mp.mpf("1"))
            g_shell = 1 / r_shell
            a_cold = 2 * mp.pi * mp.mpf("0.25") * mp.mpf("1")
            a_hot = mp.mpf("0.4")
            sigma = mp.mpf("0.0000000567")

            def f1(th, tc, ts):
                return (g_link * (th - tc)
                        + a_hot * mp.mpf("12") * (th - mp.mpf("600"))
                        + a_hot * mp.mpf("0.8") * sigma * (th**4 - mp.mpf("800")**4))

            def f2(th, tc, ts):
                return g_link * (tc - th) + g_shell * (tc - ts)

            def f3(th, tc, ts):
                return (g_shell * (ts - tc)
                        + a_cold * mp.mpf("10") * (ts - mp.mpf("300"))
                        + a_cold * mp.mpf("0.5") * sigma * (ts**4 - mp.mpf("290")**4))

            th, tc, ts = mp.findroot([f1, f2, f3], (mp.mpf("600"), mp.mpf("400"), mp.mpf("350")))
            q_cold = g_shell * (tc - ts)
            _assert_encloses(self, res["ports"]["hot"]["temperatureBoundsK"], th)
            _assert_encloses(self, res["ports"]["cold"]["innerFaceTemperatureBoundsK"], tc)
            _assert_encloses(self, res["ports"]["cold"]["outerFaceTemperatureBoundsK"], ts)
            _assert_encloses(self, res["ports"]["cold"]["outwardHeatRateBoundsW"], q_cold)
            _assert_encloses(self, res["ports"]["hot"]["outwardHeatRateBoundsW"], -q_cold)

    def test_three_terminal_star_two_nonlinear_ports_and_phase_bath_against_oracle(self):
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        res = investigate(
            star_inputs,
            {
                "warm": {
                    "kind": "radiating_surface",
                    "areaM2": "0.5",
                    "enclosureTemperatureK": "700",
                    "emissivity": "0.9",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "500",
                    "convectionCoefficientWPerM2K": "8",
                },
                "middle": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "sphere",
                        "innerRadiusM": "0.1",
                        "layers": [{"outerRadiusM": "0.2", "conductivityWPerMK": "2"}],
                    },
                    "exterior": {
                        "enclosureTemperatureK": "260",
                        "emissivity": "0.7",
                        "sigmaWPerM2K4": "0.0000000567",
                        "airTemperatureK": "280",
                        "convectionCoefficientWPerM2K": "6",
                    },
                },
                "cool": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0.05",
                    "initialLiquidKg": "0.05",
                },
            },
            duration_s="1000",
        )
        self.assertEqual(res["ports"]["cool"]["phaseProcess"], "melting")
        bal_lo, bal_hi = map(F, res["systemEnergyBalanceBoundsW"])
        self.assertLessEqual(bal_lo, F(0))
        self.assertGreaterEqual(bal_hi, F(0))

        # Independent 110-digit oracle using exact STAR leg conductances (first=2, second=3, third=5 W/K)
        # => W_wm = 6/10, W_wc = 10/10 = 1, W_mc = 15/10 = 3/2.
        with mp.workdps(110):
            w_wm, w_wc, w_mc = mp.mpf("0.6"), mp.mpf("1.0"), mp.mpf("1.5")
            t_cool = mp.mpf("273.15")
            r_shell = (1 / mp.mpf("0.1") - 1 / mp.mpf("0.2")) / (4 * mp.pi * mp.mpf("2"))
            g_shell = 1 / r_shell
            a_mid = 4 * mp.pi * mp.mpf("0.2")**2
            a_warm = mp.mpf("0.5")
            sigma = mp.mpf("0.0000000567")

            def f1(tw, tm, ts):
                return (w_wm * (tw - tm) + w_wc * (tw - t_cool)
                        + a_warm * mp.mpf("8") * (tw - mp.mpf("500"))
                        + a_warm * mp.mpf("0.9") * sigma * (tw**4 - mp.mpf("700")**4))

            def f2(tw, tm, ts):
                return w_wm * (tm - tw) + w_mc * (tm - t_cool) + g_shell * (tm - ts)

            def f3(tw, tm, ts):
                return (g_shell * (ts - tm)
                        + a_mid * mp.mpf("6") * (ts - mp.mpf("280"))
                        + a_mid * mp.mpf("0.7") * sigma * (ts**4 - mp.mpf("260")**4))

            tw, tm, ts = mp.findroot([f1, f2, f3], (mp.mpf("550"), mp.mpf("320"), mp.mpf("300")))
            q_bath = w_wc * (tw - t_cool) + w_mc * (tm - t_cool)
            _assert_encloses(self, res["ports"]["warm"]["temperatureBoundsK"], tw)
            _assert_encloses(self, res["ports"]["middle"]["innerFaceTemperatureBoundsK"], tm)
            _assert_encloses(self, res["ports"]["middle"]["outerFaceTemperatureBoundsK"], ts)
            _assert_encloses(self, res["ports"]["cool"]["bathInflowDuringPlateauBoundsW"], q_bath)

    def test_triangle_two_competing_phase_baths_and_radiating_surface_stops_at_first_exhaustion(self):
        tri_inputs = (CASES / "triangle" / "study.json", CASES / "triangle", CASES / "triangle" / "facts.json", TRIANGLE)
        res = investigate(
            tri_inputs,
            {
                "warm": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "400",
                    "specificLatentHeatJPerKg": "200000",
                    "initialSolidKg": "0.05",
                    "initialLiquidKg": "0.001",  # small liquid mass -> freezes & exhausts first!
                },
                "cool": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0.5",  # large solid mass -> still coexisting when warm exhausts
                    "initialLiquidKg": "0.5",
                },
                "middle": {
                    "kind": "radiating_surface",
                    "areaM2": "0.2",
                    "enclosureTemperatureK": "310",
                    "emissivity": "0.6",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "320",
                    "convectionCoefficientWPerM2K": "5",
                },
            },
            duration_s="10000",
        )
        self.assertEqual(res["ports"]["warm"]["phaseProcess"], "freezing")
        self.assertEqual(res["ports"]["cool"]["phaseProcess"], "melting")
        self.assertEqual(res["phaseSystem"]["plateauStatus"], "exhausted")
        self.assertEqual(res["phaseSystem"]["firstExhaustedCandidatePorts"], ["warm"])
        self.assertIs(res["phaseSystem"]["postExhaustionModeled"], False)
        # Certified unique first-exhausted bath has exact 0 remaining liquid.
        self.assertEqual(res["ports"]["warm"]["remainingLiquidBoundsKg"], ["0", "0"])
        # Cool bath stopped at warm's exhaustion time, so plenty of solid remains (> 0.49 kg).
        cool_solid_lo = F(res["ports"]["cool"]["remainingSolidBoundsKg"][0])
        self.assertGreater(cool_solid_lo, F("0.49"))
        self.assertEqual(res["ports"]["warm"]["plateauStatusAtModeledStop"], "exhausted")
        self.assertEqual(res["ports"]["warm"]["statusAtRequestedDuration"], "exhausted")
        self.assertEqual(res["ports"]["cool"]["plateauStatusAtModeledStop"], "coexisting")
        self.assertEqual(res["ports"]["cool"]["statusAtRequestedDuration"], "not_modeled_after_system_exhaustion")

    def test_two_bath_link_does_not_report_counterfactual_exhaustion_for_later_bath(self):
        # P2-2 exact witness: LINK (G=2 W/K), hot freezes out at 0.005 s, cold would
        # only melt out at 5 s under obsolete clamped flows; requested duration is 10 s.
        res = investigate(
            LINK,
            {
                "hot": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "400",
                    "specificLatentHeatJPerKg": "1000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0.001",
                },
                "cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "300",
                    "specificLatentHeatJPerKg": "1000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "1",
                },
            },
            duration_s="10",
        )
        self.assertEqual(res["phaseSystem"]["plateauStatus"], "exhausted")
        self.assertEqual(res["phaseSystem"]["firstExhaustedCandidatePorts"], ["hot"])
        self.assertEqual(res["phaseSystem"]["modeledDurationBoundsS"], ["1/200", "1/200"])
        self.assertIs(res["phaseSystem"]["postExhaustionModeled"], False)

        self.assertEqual(res["ports"]["hot"]["bathInflowDuringPlateauBoundsW"], ["-200", "-200"])
        self.assertEqual(res["ports"]["hot"]["remainingLiquidBoundsKg"], ["0", "0"])
        self.assertEqual(res["ports"]["hot"]["plateauStatusAtModeledStop"], "exhausted")
        self.assertEqual(res["ports"]["hot"]["statusAtRequestedDuration"], "exhausted")

        self.assertEqual(res["ports"]["cold"]["bathInflowDuringPlateauBoundsW"], ["200", "200"])
        self.assertEqual(res["ports"]["cold"]["remainingSolidBoundsKg"], ["999/1000", "999/1000"])
        self.assertEqual(res["ports"]["cold"]["plateauStatusAtModeledStop"], "coexisting")
        self.assertEqual(
            res["ports"]["cold"]["statusAtRequestedDuration"],
            "not_modeled_after_system_exhaustion",
        )

    def test_optional_zero_bridge_unanchored_component_refused_and_anchored_control_accepted(self):
        # P2-1 exact 4-terminal witness: G_AB=1, G_CD=1, G_BC in [0, 1].
        # Passes connected-existence validation (G_BC=1), but G_BC=0 disconnects {C, D}.
        bridge_law = {
            "schema": "sim_heat.offline_terminal_response/1",
            "terminals": ["A", "B", "C", "D"],
            "imposedTemperaturesK": {"A": "300", "B": "300", "C": "300", "D": "300"},
            "supplyResponseBoundsWPerK": {
                "A": {"A": ["1", "1"], "B": ["-1", "-1"], "C": ["0", "0"], "D": ["0", "0"]},
                "B": {"A": ["-1", "-1"], "B": ["1", "2"], "C": ["-1", "0"], "D": ["0", "0"]},
                "C": {"A": ["0", "0"], "B": ["-1", "0"], "C": ["1", "2"], "D": ["-1", "-1"]},
                "D": {"A": ["0", "0"], "B": ["0", "0"], "C": ["-1", "-1"], "D": ["1", "1"]},
            },
            "modelSha256": "a" * 64,
            "studySha256": "b" * 64,
            "factsSha256": "c" * 64,
            "nativeExecuted": False,
            "nativeQualified": False,
            "independentlyCertifiedReference": False,
            "runnerConsumable": False,
        }
        adiabatic = {
            "kind": "radiating_surface",
            "areaM2": "1",
            "enclosureTemperatureK": "300",
            "emissivity": "0",
            "sigmaWPerM2K4": "0.0000000567",
        }
        # Only A is anchored; C and D can float to any temperature when G_BC = 0 -> MUST refuse.
        with self.assertRaisesRegex(ValueError, "not guaranteed to be connected to an active temperature anchor"):
            solve_from_law(
                bridge_law,
                {
                    "A": {"kind": "maintained", "temperatureK": "300"},
                    "B": adiabatic,
                    "C": adiabatic,
                    "D": adiabatic,
                },
            )

        # Positive control: when D is also anchored (maintained at 350 K), every component
        # is anchored via w_lo > 0 edges in EVERY feasible realization -> MUST succeed.
        ok = solve_from_law(
            bridge_law,
            {
                "A": {"kind": "maintained", "temperatureK": "300"},
                "B": adiabatic,
                "C": adiabatic,
                "D": {"kind": "maintained", "temperatureK": "350"},
            },
        )
        self.assertTrue(ok["solverMetadata"]["residualCertified"])
        # When G_BC in [0, 1], T_B in [300, 350/3 + ...] and T_C in [..., 350]; specifically 300 in T_B and 350 in T_C.
        self.assertEqual(F(ok["ports"]["B"]["temperatureBoundsK"][0]), F(300))
        self.assertEqual(F(ok["ports"]["C"]["temperatureBoundsK"][1]), F(350))

    def test_adiabatic_port_anchored_elsewhere_and_cli_entry_point(self):
        res = investigate(
            LINK,
            {
                "hot": {"kind": "maintained", "temperatureK": "400"},
                "cold": {
                    "kind": "radiating_surface",
                    "areaM2": "1",
                    "enclosureTemperatureK": "100",
                    "emissivity": "0",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "100",
                    "convectionCoefficientWPerM2K": "0",
                },
            },
        )
        self.assertEqual(res["ports"]["cold"]["temperatureBoundsK"], ["400", "400"])
        self.assertEqual(res["ports"]["cold"]["outwardHeatRateBoundsW"], ["0", "0"])

        # CLI test
        payload = {
            "source": {
                "studyPath": str(LINK[0]),
                "rootPath": str(LINK[1]),
                "factsPath": str(LINK[2]),
                "factsSha256": str(LINK[3]),
            },
            "ports": {
                "hot": {"kind": "maintained", "temperatureK": "380"},
                "cold": {"kind": "maintained", "temperatureK": "280"},
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            req_path = Path(tmp) / "multi.json"
            req_path.write_text(json.dumps(payload), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli_main(["--request", str(req_path)])
            out = json.loads(buf.getvalue())
            self.assertEqual(out["schema"], MULTIPORT_SCHEMA)
            self.assertEqual(out["ports"]["hot"]["inflowFromNetworkBoundsW"], ["-200", "-200"])
            self.assertEqual(out["ports"]["cold"]["inflowFromNetworkBoundsW"], ["200", "200"])

    def test_negative_controls_unanchored_extra_keys_missing_duration_and_forged_provenance(self):
        law = terminal_response(*LINK)

        # Unanchored adiabatic network (all eps=0, h=0)
        with self.assertRaisesRegex(ValueError, "anchor steady temperatures"):
            solve_from_law(
                law,
                {
                    "hot": {
                        "kind": "radiating_surface",
                        "areaM2": "1",
                        "enclosureTemperatureK": "300",
                        "emissivity": "0",
                        "sigmaWPerM2K4": "0.0000000567",
                    },
                    "cold": {
                        "kind": "radiating_surface",
                        "areaM2": "1",
                        "enclosureTemperatureK": "300",
                        "emissivity": "0",
                        "sigmaWPerM2K4": "0.0000000567",
                    },
                },
            )

        # Missing port
        with self.assertRaisesRegex(ValueError, "every terminal"):
            solve_from_law(law, {"hot": {"kind": "maintained", "temperatureK": "350"}})

        # Extra typo key
        with self.assertRaisesRegex(ValueError, "unsupported keys"):
            solve_from_law(
                law,
                {
                    "hot": {"kind": "maintained", "temperatureK": "350", "typoKey": "1"},
                    "cold": {"kind": "maintained", "temperatureK": "300"},
                },
            )

        # Phase bath without duration_s
        with self.assertRaisesRegex(ValueError, "duration_s is required"):
            solve_from_law(
                law,
                {
                    "hot": {"kind": "maintained", "temperatureK": "350"},
                    "cold": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273.15",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "0.1",
                        "initialLiquidKg": "0.1",
                    },
                },
            )

        # Forged provenance flag
        for flag in OFFLINE_FLAG_KEYS:
            forged = copy.deepcopy(law)
            forged[flag] = True
            with self.assertRaisesRegex(ValueError, "refuses non-False"):
                solve_from_law(
                    forged,
                    {
                        "hot": {"kind": "maintained", "temperatureK": "350"},
                        "cold": {"kind": "maintained", "temperatureK": "300"},
                    },
                )

    def test_f02_i5_radial_shell_grid_and_radiating_radial_layers_equivalence(self):
        # Full 42-case Opus I5 grid: all widths < 1e-9 K, enclosing 45-digit mpmath oracle,
        # residualCertified=True, terminationReason="converged".
        link_law = terminal_response(*LINK)
        with mp.workdps(50):
            eps_mp, sig_mp = mp.mpf("0.8"), mp.mpf("5.67e-8")
            for geom in ("sphere", "cylinder"):
                for k_s in ("0.04", "0.2", "1", "15", "50", "200", "400"):
                    for h_s in ("2", "10", "50"):
                        g = {
                            "kind": geom,
                            "innerRadiusM": "0.1",
                            "layers": [{"outerRadiusM": "0.11", "conductivityWPerMK": k_s}],
                        }
                        if geom == "cylinder":
                            g["cylinderLengthM"] = "1"
                        res = solve_from_law(
                            link_law,
                            {
                                "hot": {"kind": "maintained", "temperatureK": "400"},
                                "cold": {
                                    "kind": "radial_shell",
                                    "geometry": g,
                                    "exterior": {
                                        "enclosureTemperatureK": "300",
                                        "emissivity": "0.8",
                                        "sigmaWPerM2K4": "0.0000000567",
                                        "airTemperatureK": "300",
                                        "convectionCoefficientWPerM2K": h_s,
                                    },
                                },
                            },
                        )
                        meta = res["solverMetadata"]
                        self.assertTrue(meta["residualCertified"])
                        self.assertEqual(meta["terminationReason"], "converged")
                        self.assertLess(F(meta["maxTemperatureWidthK"]), F(1, 10**9))
                        kk, hh = mp.mpf(k_s), mp.mpf(h_s)
                        if geom == "sphere":
                            r_sh = (1 / mp.mpf("0.1") - 1 / mp.mpf("0.11")) / (4 * mp.pi * kk)
                            area = 4 * mp.pi * mp.mpf("0.11") ** 2
                        else:
                            r_sh = mp.log(mp.mpf("0.11") / mp.mpf("0.1")) / (2 * mp.pi * kk)
                            area = 2 * mp.pi * mp.mpf("0.11")
                        ti, ts = mp.findroot(
                            lambda Ti, Ts: [
                                2 * (400 - Ti) - (Ti - Ts) / r_sh,
                                (Ti - Ts) / r_sh - area * (hh * (Ts - 300) + eps_mp * sig_mp * (Ts**4 - 300**4)),
                            ],
                            (mp.mpf(350), mp.mpf(340)),
                        )
                        po = res["ports"]["cold"]
                        _assert_encloses(self, po["innerFaceTemperatureBoundsK"], ti, max_width=F(1, 10**9))
                        _assert_encloses(self, po["outerFaceTemperatureBoundsK"], ts, max_width=F(1, 10**9))

        # Equivalence with radiating_radial_layers.solve to 1e-12 W on copper sphere & cylinder.
        for geom in ("sphere", "cylinder"):
            cyl = "1" if geom == "cylinder" else None
            ref = rrl_solve(
                link_law, "cold", "0.1", [("0.11", "400")], "300", "0.8", "0.0000000567", cyl,
                air_k="300", h_w_per_m2_k="10",
            )
            g = {"kind": geom, "innerRadiusM": "0.1", "layers": [{"outerRadiusM": "0.11", "conductivityWPerMK": "400"}]}
            if cyl is not None:
                g["cylinderLengthM"] = cyl
            res = solve_from_law(
                link_law,
                {
                    "hot": {"kind": "maintained", "temperatureK": link_law["imposedTemperaturesK"]["hot"]},
                    "cold": {
                        "kind": "radial_shell",
                        "geometry": g,
                        "exterior": {
                            "enclosureTemperatureK": "300",
                            "emissivity": "0.8",
                            "sigmaWPerM2K4": "0.0000000567",
                            "airTemperatureK": "300",
                            "convectionCoefficientWPerM2K": "10",
                        },
                    },
                },
            )
            q_ref = list(map(F, ref["outwardHeatRateBoundsW"]))
            q_mp = list(map(F, res["ports"]["cold"]["outwardHeatRateBoundsW"]))
            _assert_intervals_overlap(self, ref["outwardHeatRateBoundsW"], res["ports"]["cold"]["outwardHeatRateBoundsW"])
            self.assertLess(max(abs(q_mp[0] - q_ref[0]), abs(q_mp[1] - q_ref[1])), F(1, 10**12))

    def test_f02_copper_sphere_phase_bath_star_and_exact_linear_and_sweep_limit(self):
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        star_law = terminal_response(*star_inputs)
        link_law = terminal_response(*LINK)

        # 1) Copper sphere + phase bath on STAR at T_ext in {100, 120, 150, 170, 180} K: no refusal.
        for ext_t in ("100", "120", "150", "170", "180"):
            res = solve_from_law(
                star_law,
                {
                    "cool": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273.15",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "1",
                        "initialLiquidKg": "1",
                    },
                    "middle": {"kind": "maintained", "temperatureK": star_law["imposedTemperaturesK"]["middle"]},
                    "warm": {
                        "kind": "radial_shell",
                        "geometry": {
                            "kind": "sphere",
                            "innerRadiusM": "0.1",
                            "layers": [{"outerRadiusM": "0.11", "conductivityWPerMK": "400"}],
                        },
                        "exterior": {
                            "enclosureTemperatureK": ext_t,
                            "emissivity": "0.8",
                            "sigmaWPerM2K4": "0.0000000567",
                            "airTemperatureK": ext_t,
                            "convectionCoefficientWPerM2K": "10",
                        },
                    },
                },
                duration_s="100",
            )
            self.assertEqual(res["solverMetadata"]["terminationReason"], "converged")
            self.assertEqual(res["ports"]["cool"]["phaseProcess"], "melting")
            if ext_t == "180":
                q_lo, q_hi = map(F, res["ports"]["cool"]["bathInflowDuringPlateauBoundsW"])
                self.assertGreater(q_lo, F("46.4"))
                self.assertLess(q_hi, F("46.6"))

        # 2) WEAK_FILMS exact rational linear path.
        weak = solve_from_law(
            link_law,
            {
                "hot": {
                    "kind": "radiating_surface",
                    "areaM2": "0.01",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "350",
                    "convectionCoefficientWPerM2K": "2",
                },
                "cold": {
                    "kind": "radiating_surface",
                    "areaM2": "0.01",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "250",
                    "convectionCoefficientWPerM2K": "2",
                },
            },
        )
        self.assertEqual(weak["solverMetadata"]["terminationReason"], "exact_linear")
        self.assertEqual(weak["solverMetadata"]["maxTemperatureWidthK"], "0")
        self.assertEqual(weak["solverMetadata"]["maxHeatRateWidthW"], "0")
        self.assertEqual(weak["ports"]["hot"]["temperatureBoundsK"], ["60350/201", "60350/201"])
        self.assertEqual(weak["ports"]["cold"]["temperatureBoundsK"], ["60250/201", "60250/201"])

        # 3) eps = 0 radial_shell has interval g_shell and area, so MUST NOT take exact_linear.
        eps0_shell = solve_from_law(
            link_law,
            {
                "hot": {"kind": "maintained", "temperatureK": "400"},
                "cold": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "sphere",
                        "innerRadiusM": "0.1",
                        "layers": [{"outerRadiusM": "0.11", "conductivityWPerMK": "400"}],
                    },
                    "exterior": {
                        "enclosureTemperatureK": "300",
                        "emissivity": "0",
                        "sigmaWPerM2K4": "0.0000000567",
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "10",
                    },
                },
            },
        )
        self.assertEqual(eps0_shell["solverMetadata"]["terminationReason"], "converged")
        self.assertLess(F(eps0_shell["solverMetadata"]["maxTemperatureWidthK"]), F(1, 10**9))

        # 4) 0-sweep cases (all fixed or t_min == t_max) report terminationReason == "converged".
        all_fixed = solve_from_law(
            link_law,
            {"hot": {"kind": "maintained", "temperatureK": "380"}, "cold": {"kind": "maintained", "temperatureK": "280"}},
        )
        self.assertEqual(all_fixed["solverMetadata"]["terminationReason"], "converged")
        self.assertEqual(all_fixed["solverMetadata"]["sweeps"], 0)
        self.assertEqual(all_fixed["solverMetadata"]["maxTemperatureWidthK"], "0")

        # 5) Forced max_sweeps=1: reports sweep_limit, and resolution-limit refusal precedes sign refusal.
        lim = solve_from_law(
            link_law,
            {
                "hot": {
                    "kind": "radiating_surface",
                    "areaM2": "0.01",
                    "enclosureTemperatureK": "400",
                    "emissivity": "0.1",
                    "sigmaWPerM2K4": "0.0000000567",
                },
                "cold": {
                    "kind": "radiating_surface",
                    "areaM2": "0.01",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0.1",
                    "sigmaWPerM2K4": "0.0000000567",
                },
            },
            max_sweeps=1,
        )
        self.assertEqual(lim["solverMetadata"]["terminationReason"], "sweep_limit")
        self.assertEqual(lim["solverMetadata"]["sweeps"], 1)
        self.assertGreater(F(lim["solverMetadata"]["maxTemperatureWidthK"]), F(0))
        self.assertGreater(F(lim["solverMetadata"]["maxHeatRateWidthW"]), F(0))

        # Phase-bath straddle at max_sweeps=1 raises resolution-limit refusal naming sweep_limit & width,
        # while the same problem resolves cleanly at default max_sweeps.
        straddle_ports = {
            "cool": {
                "kind": "phase_bath",
                "transitionTemperatureK": "420",
                "specificLatentHeatJPerKg": "334000",
                "initialSolidKg": "1",
                "initialLiquidKg": "1",
            },
            "warm": {
                "kind": "radiating_surface",
                "areaM2": "0.1",
                "enclosureTemperatureK": "500",
                "emissivity": "0.8",
                "sigmaWPerM2K4": "0.0000000567",
            },
            "middle": {
                "kind": "radiating_surface",
                "areaM2": "0.1",
                "enclosureTemperatureK": "200",
                "emissivity": "0.8",
                "sigmaWPerM2K4": "0.0000000567",
            },
        }
        with self.assertRaisesRegex(ValueError, r"sweep_limit.*max_sweeps=1.*Width"):
            solve_from_law(star_law, straddle_ports, duration_s="100", max_sweeps=1)
        resolved = solve_from_law(star_law, straddle_ports, duration_s="100")
        self.assertEqual(resolved["solverMetadata"]["terminationReason"], "converged")

    def test_f04_pure_phase_bath_regimes_epsilon_limit_and_multi_bath_start_exhaustion(self):
        link_law = terminal_response(*LINK)
        star_inputs = (CASES / "star" / "study.json", CASES / "star", CASES / "star" / "facts.json", STAR)
        star_law = terminal_response(*star_inputs)

        # 1) Pure solid + melting inflow: exact oracle and eps in {1e-9, 1e-12} criterion.
        pure_s = solve_from_law(
            link_law,
            {
                "hot": {"kind": "maintained", "temperatureK": "373"},
                "cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0",
                },
            },
            duration_s="100",
        )
        self.assertEqual(pure_s["phaseSystem"]["plateauStatus"], "coexisting")
        self.assertIs(pure_s["phaseSystem"]["exhaustedAtStart"], False)
        self.assertIs(pure_s["ports"]["cold"]["exhaustedAtStart"], False)
        self.assertIsNone(pure_s["ports"]["cold"]["exhaustedPhase"])
        self.assertEqual(pure_s["ports"]["cold"]["latentEnergyIntoBathBoundsJ"], ["20000", "20000"])
        for eps_s in ("0.000000001", "0.000000000001"):
            eps = F(eps_s)
            ref = solve_from_law(
                link_law,
                {
                    "hot": {"kind": "maintained", "temperatureK": "373"},
                    "cold": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "1",
                        "initialLiquidKg": eps_s,
                    },
                },
                duration_s="100",
            )
            self.assertEqual(
                pure_s["ports"]["cold"]["latentEnergyIntoBathBoundsJ"],
                ref["ports"]["cold"]["latentEnergyIntoBathBoundsJ"],
            )
            self.assertEqual(
                pure_s["ports"]["cold"]["remainingSolidBoundsKg"],
                ref["ports"]["cold"]["remainingSolidBoundsKg"],
            )
            self.assertEqual(
                [F(x) for x in pure_s["ports"]["cold"]["remainingLiquidBoundsKg"]],
                [F(x) - eps for x in ref["ports"]["cold"]["remainingLiquidBoundsKg"]],
            )

        # 2) Pure liquid + freezing outflow mirror.
        pure_l = solve_from_law(
            link_law,
            {
                "hot": {"kind": "maintained", "temperatureK": "200"},
                "cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "0",
                    "initialLiquidKg": "1",
                },
            },
            duration_s="100",
        )
        self.assertEqual(pure_l["phaseSystem"]["plateauStatus"], "coexisting")
        self.assertIs(pure_l["phaseSystem"]["exhaustedAtStart"], False)
        self.assertEqual(pure_l["ports"]["cold"]["phaseProcess"], "freezing")
        self.assertEqual(pure_l["ports"]["cold"]["latentEnergyIntoBathBoundsJ"], ["-14600", "-14600"])

        # 3) Regime (b): pure solid + outflow -> exhaustedAtStart=True (including duration == 0).
        for dur_s in ("100", "0"):
            exh = solve_from_law(
                link_law,
                {
                    "hot": {"kind": "maintained", "temperatureK": "200"},
                    "cold": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "1",
                        "initialLiquidKg": "0",
                    },
                },
                duration_s=dur_s,
            )
            self.assertEqual(exh["phaseSystem"]["plateauStatus"], "exhausted")
            self.assertIs(exh["phaseSystem"]["exhaustedAtStart"], True)
            self.assertEqual(exh["phaseSystem"]["firstExhaustionTimeBoundsS"], ["0", "0"])
            self.assertEqual(exh["phaseSystem"]["modeledDurationBoundsS"], ["0", "0"])
            self.assertEqual(exh["phaseSystem"]["firstExhaustedCandidatePorts"], ["cold"])
            self.assertIs(exh["ports"]["cold"]["exhaustedAtStart"], True)
            self.assertEqual(exh["ports"]["cold"]["exhaustedPhase"], "liquid")
            self.assertEqual(exh["ports"]["cold"]["remainingSolidBoundsKg"], ["1", "1"])
            self.assertEqual(exh["ports"]["cold"]["remainingLiquidBoundsKg"], ["0", "0"])

        # 4) Multi-bath multiport with one pure bath in regime (b): system status exhausted at [0, 0].
        mb = solve_from_law(
            star_law,
            {
                "warm": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "400",
                    "specificLatentHeatJPerKg": "1000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0",  # pure solid losing heat -> regime (b)!
                },
                "cool": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "300",
                    "specificLatentHeatJPerKg": "1000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "1",
                },
                "middle": {"kind": "maintained", "temperatureK": "330"},
            },
            duration_s="100",
        )
        self.assertEqual(mb["phaseSystem"]["plateauStatus"], "exhausted")
        self.assertIs(mb["phaseSystem"]["exhaustedAtStart"], True)
        self.assertEqual(mb["phaseSystem"]["firstExhaustionTimeBoundsS"], ["0", "0"])
        self.assertEqual(mb["phaseSystem"]["firstExhaustedCandidatePorts"], ["warm"])
        self.assertIs(mb["ports"]["warm"]["exhaustedAtStart"], True)
        self.assertEqual(mb["ports"]["warm"]["exhaustedPhase"], "liquid")
        self.assertIs(mb["ports"]["cool"]["exhaustedAtStart"], False)
        self.assertIsNone(mb["ports"]["cool"]["exhaustedPhase"])
        self.assertEqual(mb["ports"]["cool"]["statusAtRequestedDuration"], "not_modeled_after_system_exhaustion")

        # 5) Regime (c) exact equilibrium & duration == 0 in regime (a).
        eq = solve_from_law(
            link_law,
            {
                "hot": {"kind": "maintained", "temperatureK": "273"},
                "cold": {
                    "kind": "phase_bath",
                    "transitionTemperatureK": "273",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0",
                },
            },
            duration_s="100",
        )
        self.assertEqual(eq["phaseSystem"]["plateauStatus"], "coexisting")
        self.assertIs(eq["phaseSystem"]["exhaustedAtStart"], False)
        self.assertEqual(eq["ports"]["cold"]["phaseProcess"], "equilibrium")

        # 6) Regime (d) CR-11: unresolved sign straddle still refuses even at duration == 0.
        with self.assertRaisesRegex(ValueError, "sweep_limit"):
            solve_from_law(star_law, straddle_ports, duration_s="0", max_sweeps=1)

        # 7) Zero total mass still refused.
        with self.assertRaises(ValueError):
            solve_from_law(
                link_law,
                {
                    "hot": {"kind": "maintained", "temperatureK": "373"},
                    "cold": {
                        "kind": "phase_bath",
                        "transitionTemperatureK": "273",
                        "specificLatentHeatJPerKg": "334000",
                        "initialSolidKg": "0",
                        "initialLiquidKg": "0",
                    },
                },
                duration_s="10",
            )
