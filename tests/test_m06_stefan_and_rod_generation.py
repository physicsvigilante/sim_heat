"""Milestone M06 verification suite: quasi-steady Stefan fronts & rod heat generation.

Independent 100-digit ``mpmath`` oracles verify:
1. Planar, cylindrical, and spherical quasi-steady Stefan freezing & melting fronts,
   including completion caps (``maxThicknessM`` / ``maxOuterRadiusM``), convective film
   resistance, Stefan-number diagnostics, and ``mode_sequence_uncertain`` direction/boundary stops.
2. Uniform volumetric rod heat generation Norton reduction through eliminated internal
   junctions (exact-point and multi-junction interval rods) and certified parabolic peak recovery.
3. Cross-engine composition of heated rods with ``multiport`` (nonlinear radial shell + phase bath),
   M04 ``enthalpy`` continuation (with multi-stage phase transitions and global energy conservation),
   ``staged``, and ``stefan``.
4. Fast-path gating (EH-01), symmetry-tie guards, structured ``unsupported_regime`` refusals,
   strict input validation, and honest ``False`` offline provenance flags.
"""
from __future__ import annotations

from fractions import Fraction
import random
import unittest

import mpmath as mp

import simheat
from simheat.enthalpy import solve_enthalpy_continuation
from simheat.laws import DerivedLaw
from simheat.rod_gen import build_rod_generation_model
from simheat.stefan import STEFAN_SCHEMA, solve_stefan_from_law
from simheat.system import (
    RESULT_ENVELOPE_SCHEMA,
    THERMAL_SYSTEM_SCHEMA,
    ThermalSystem,
    describe_equations,
    solve_system,
)
from tools.multiport_thermal_network import solve_from_law as solve_multiport
from tools.offline_provenance import OFFLINE_FLAG_KEYS


def _mp_frac(s: str) -> mp.mpf:
    f = Fraction(s)
    return mp.mpf(f.numerator) / mp.mpf(f.denominator)


def _assert_enclosed(tc: unittest.TestCase, pair: list[str], truth: mp.mpf, *, max_width: float | None = None, msg: str = "") -> None:
    lo = _mp_frac(pair[0])
    hi = _mp_frac(pair[1])
    tc.assertLessEqual(lo, truth, f"{msg}: lower bound {lo} > truth {truth}")
    tc.assertGreaterEqual(hi, truth, f"{msg}: upper bound {hi} < truth {truth}")
    if max_width is not None:
        tc.assertLessEqual(float(hi - lo), max_width, f"{msg}: width {float(hi - lo)} > {max_width}")


def _assert_offline_flags_false(tc: unittest.TestCase, obj: dict) -> None:
    for k in OFFLINE_FLAG_KEYS:
        tc.assertIs(obj[k], False, f"expected {k}=False")


class TestM06StefanAndRodGeneration(unittest.TestCase):
    def setUp(self) -> None:
        mp.mp.dps = 100

    # ------------------------------------------------------------------
    # 1. Planar Stefan ice growth & melting vs. 100-digit mpmath oracles
    # ------------------------------------------------------------------
    def test_planar_stefan_freezing_and_film_vs_mpmath_oracle(self) -> None:
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_planar_lake_ice",
            "nodes": ["air", "ice_top"],
            "conduction": {
                "kind": "rods",
                "terminals": ["air", "ice_top"],
                "rods": {
                    "snow_blanket": {"kind": "rod_area", "a": "air", "b": "ice_top", "k": "0.25", "L": "0.05", "A": "2"},
                },
            },
            "attachments": {
                "air": {"kind": "maintained", "temperatureK": "253.15"},
                "ice_top": {
                    "kind": "stefan_layer",
                    "geometry": {"kind": "planar", "areaM2": "2", "initialThicknessM": "0.02"},
                    "transitionTemperatureK": "273.15",
                    "densityKgPerM3": "917",
                    "specificLatentHeatJPerKg": "334000",
                    "layerConductivityWPerMK": "2.2",
                    "solidSpecificHeatJPerKgK": "2100",
                    "externalFilmCoefficientWPerM2K": "25",
                },
            },
            "solve": {"mode": "transient", "durationS": "7200"},
        }
        res = solve_system(system)
        self.assertEqual(res["schema"], RESULT_ENVELOPE_SCHEMA)
        self.assertEqual(res["backend"], "stefan")
        self.assertEqual(res["status"], "growing")
        self.assertEqual(res["terminationReason"], "resolved")
        _assert_offline_flags_false(self, res)
        raw = res["backendResult"]
        self.assertEqual(raw["schema"], STEFAN_SCHEMA)
        _assert_offline_flags_false(self, raw["evidence"])
        self.assertTrue(raw["assumptions"]["quasiSteadyConduction"])
        self.assertTrue(raw["assumptions"]["sensibleStorageInGrowingLayerNeglected"])

        # 100-digit exact planar quadratic oracle
        k_snow, l_snow, a_val = mp.mpf("0.25"), mp.mpf("0.05"), mp.mpf("2")
        r_port = l_snow / (k_snow * a_val)
        r_film = mp.mpf(1) / (mp.mpf("25") * a_val)
        r_ext = r_port + r_film
        k_ice = mp.mpf("2.2")
        rho = mp.mpf("917")
        latent = mp.mpf("334000")
        t_tr, t_eq = mp.mpf("273.15"), mp.mpf("253.15")
        dt_drive = t_tr - t_eq
        s0 = mp.mpf("0.02")
        dur = mp.mpf("7200")
        b_len = k_ice * a_val * r_ext
        s_true = mp.sqrt((s0 + b_len) ** 2 + (2 * k_ice * dt_drive / (rho * latent)) * dur) - b_len
        m_true = rho * a_val * s_true
        lat_true = -rho * a_val * (s_true - s0) * latent
        q_true = dt_drive / (r_ext + s_true / (k_ice * a_val))
        t_port_true = t_eq + r_port * q_true
        ste_true = mp.mpf("2100") * dt_drive / latent

        st = raw["stefan"]
        _assert_enclosed(self, st["finalThicknessBoundsM"], s_true, max_width=1e-35, msg="planar s")
        _assert_enclosed(self, st["finalSolidMassBoundsKg"], m_true, max_width=1e-30, msg="planar mass")
        _assert_enclosed(self, st["latentEnergyIntoLayerBoundsJ"], lat_true, max_width=1e-20, msg="planar latent")
        _assert_enclosed(self, st["finalHeatExtractionRateBoundsW"], q_true, max_width=1e-30, msg="planar Q")
        _assert_enclosed(self, st["finalPortTemperatureBoundsK"], t_port_true, max_width=1e-30, msg="planar T_port")
        _assert_enclosed(self, raw["assumptions"]["stefanNumberBounds"], ste_true, max_width=1e-35, msg="Ste")

    def test_planar_stefan_cap_completion_and_melting_mirror(self) -> None:
        # Freezing past maxThicknessM -> completely_frozen, modeledDuration stops at exact completion time.
        base_freeze = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_planar_capped",
            "nodes": ["air", "pond"],
            "conduction": {
                "kind": "rods",
                "terminals": ["air", "pond"],
                "rods": {"contact": {"kind": "rod_area", "a": "air", "b": "pond", "k": "200", "L": "0.01", "A": "1"}},
            },
            "attachments": {
                "air": {"kind": "maintained", "temperatureK": "263.15"},
                "pond": {
                    "kind": "stefan_layer",
                    "geometry": {"kind": "planar", "areaM2": "1", "initialThicknessM": "0", "maxThicknessM": "0.05"},
                    "transitionTemperatureK": "273.15",
                    "densityKgPerM3": "917",
                    "specificLatentHeatJPerKg": "334000",
                    "layerConductivityWPerMK": "2.2",
                },
            },
            "solve": {"mode": "transient", "durationS": "100000"},
        }
        res_f = solve_system(base_freeze)
        self.assertEqual(res_f["status"], "completely_frozen")
        self.assertEqual(res_f["terminationReason"], "resolved")
        st = res_f["backendResult"]["stefan"]
        self.assertIs(st["postCompletionModeled"], False)
        r_ext = mp.mpf("0.01") / mp.mpf("200")
        t_done_true = (mp.mpf("917") * mp.mpf("334000") / mp.mpf("10")) * (
            mp.mpf("0.05") ** 2 / (2 * mp.mpf("2.2")) + r_ext * mp.mpf("0.05")
        )
        _assert_enclosed(self, st["completionTimeBoundsS"], t_done_true, max_width=1e-35, msg="t_done")
        self.assertEqual(st["modeledDurationBoundsS"], st["completionTimeBoundsS"])
        self.assertEqual(st["finalThicknessBoundsM"], ["1/20", "1/20"])

        # Melting mirror: warm air at 283.15 K melting an initial 0.04 m ice slab.
        melt_sys = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_planar_melt",
            "nodes": ["warm", "ice"],
            "conduction": {
                "kind": "rods",
                "terminals": ["warm", "ice"],
                "rods": {"air_gap": {"kind": "rod_area", "a": "warm", "b": "ice", "k": "2", "L": "0.05", "A": "1"}},
            },
            "attachments": {
                "warm": {"kind": "maintained", "temperatureK": "283.15"},
                "ice": {
                    "kind": "stefan_layer",
                    "geometry": {"kind": "planar", "areaM2": "1", "initialThicknessM": "0.04"},
                    "transitionTemperatureK": "273.15",
                    "densityKgPerM3": "917",
                    "specificLatentHeatJPerKg": "334000",
                    "layerConductivityWPerMK": "2.2",
                },
            },
            "solve": {"mode": "transient", "durationS": "15000"},
        }
        res_m = solve_system(melt_sys)
        self.assertEqual(res_m["status"], "melting")
        st_m = res_m["backendResult"]["stefan"]
        self.assertEqual(st_m["regime"], "melting")
        r_ext_m = mp.mpf("0.05") / mp.mpf("2")
        b_m = mp.mpf("2.2") * r_ext_m
        s_m_true = mp.sqrt((mp.mpf("0.04") + b_m) ** 2 - (2 * mp.mpf("2.2") * mp.mpf("10") / (mp.mpf("917") * mp.mpf("334000"))) * mp.mpf("15000")) - b_m
        _assert_enclosed(self, st_m["finalThicknessBoundsM"], s_m_true, max_width=1e-35, msg="melt s")
        # Melting absorbs positive latent energy into the layer.
        self.assertGreater(Fraction(st_m["latentEnergyIntoLayerBoundsJ"][0]), 0)

        # Past full melt -> completely_melted with s=0 and modeledDuration = completionTime.
        melt_sys["solve"]["durationS"] = "500000"
        res_m2 = solve_system(melt_sys)
        self.assertEqual(res_m2["status"], "completely_melted")
        st_m2 = res_m2["backendResult"]["stefan"]
        self.assertEqual(st_m2["finalThicknessBoundsM"], ["0", "0"])
        self.assertEqual(st_m2["modeledDurationBoundsS"], st_m2["completionTimeBoundsS"])

    # ------------------------------------------------------------------
    # 2. Cylindrical & spherical radial Stefan vs. 100-digit mpmath oracles
    # ------------------------------------------------------------------
    def test_cylindrical_and_spherical_stefan_vs_mpmath_oracles(self) -> None:
        # Cylindrical chilled pipe freezing water radially outward.
        cyl_sys = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_cyl_freeze",
            "nodes": ["coolant", "pipe_wall"],
            "conduction": {
                "kind": "rods",
                "terminals": ["coolant", "pipe_wall"],
                "rods": {"wall": {"kind": "rod_area", "a": "coolant", "b": "pipe_wall", "k": "20", "L": "0.02", "A": "0.05"}},
            },
            "attachments": {
                "coolant": {"kind": "maintained", "temperatureK": "258.15"},
                "pipe_wall": {
                    "kind": "stefan_layer",
                    "geometry": {
                        "kind": "cylinder",
                        "coreRadiusM": "0.02",
                        "initialOuterRadiusM": "0.025",
                        "cylinderLengthM": "1.5",
                        "maxOuterRadiusM": "0.10",
                    },
                    "transitionTemperatureK": "273.15",
                    "densityKgPerM3": "917",
                    "specificLatentHeatJPerKg": "334000",
                    "layerConductivityWPerMK": "2.2",
                    "externalFilmCoefficientWPerM2K": "40",
                },
            },
            "solve": {"mode": "transient", "durationS": "3600"},
        }
        res_c = solve_system(cyl_sys)
        self.assertEqual(res_c["status"], "growing")
        st_c = res_c["backendResult"]["stefan"]
        r0 = mp.mpf("0.02")
        r_init = mp.mpf("0.025")
        cyl_l = mp.mpf("1.5")
        k_ice = mp.mpf("2.2")
        rho, latent = mp.mpf("917"), mp.mpf("334000")
        dt_drive = mp.mpf("15")
        r_ext = mp.mpf("0.02") / (mp.mpf("20") * mp.mpf("0.05")) + mp.mpf(1) / (2 * mp.pi * r0 * cyl_l * mp.mpf("40"))

        def f_cyl(r: mp.mpf) -> mp.mpf:
            return mp.pi * cyl_l * r_ext * (r**2 - r0**2) + (r**2 * mp.log(r / r0) - (r**2 - r0**2) / 2) / (2 * k_ice)

        rhs_c = f_cyl(r_init) + (dt_drive / (rho * latent)) * mp.mpf("3600")
        r_c_true = mp.findroot(lambda r: f_cyl(r) - rhs_c, mp.mpf("0.05"))
        _assert_enclosed(self, st_c["finalOuterRadiusBoundsM"], r_c_true, max_width=1e-22, msg="cyl r")
        _assert_enclosed(
            self,
            st_c["finalSolidMassBoundsKg"],
            rho * mp.pi * cyl_l * (r_c_true**2 - r0**2),
            max_width=1e-18,
            msg="cyl mass",
        )

        # Spherical chilled probe freezing water radially outward + spherical melting mirror.
        sph_sys = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_sph_freeze",
            "nodes": ["cryo", "probe"],
            "conduction": {
                "kind": "rods",
                "terminals": ["cryo", "probe"],
                "rods": {"stem": {"kind": "rod_area", "a": "cryo", "b": "probe", "k": "50", "L": "0.05", "A": "0.01"}},
            },
            "attachments": {
                "cryo": {"kind": "maintained", "temperatureK": "243.15"},
                "probe": {
                    "kind": "stefan_layer",
                    "geometry": {
                        "kind": "sphere",
                        "coreRadiusM": "0.03",
                        "initialOuterRadiusM": "0.03",
                        "maxOuterRadiusM": "0.08",
                    },
                    "transitionTemperatureK": "273.15",
                    "densityKgPerM3": "917",
                    "specificLatentHeatJPerKg": "334000",
                    "layerConductivityWPerMK": "2.2",
                },
            },
            "solve": {"mode": "transient", "durationS": "4000"},
        }
        res_s = solve_system(sph_sys)
        self.assertEqual(res_s["status"], "growing")
        st_s = res_s["backendResult"]["stefan"]
        r0_s = mp.mpf("0.03")
        r_ext_s = mp.mpf("0.05") / (mp.mpf("50") * mp.mpf("0.01"))

        def f_sph(r: mp.mpf) -> mp.mpf:
            return (mp.mpf(4) / 3 * mp.pi * r_ext_s + mp.mpf(1) / (3 * k_ice * r0_s)) * (r**3 - r0_s**3) - (r**2 - r0_s**2) / (2 * k_ice)

        rhs_s = (mp.mpf("30") / (rho * latent)) * mp.mpf("4000")
        r_s_true = mp.findroot(lambda r: f_sph(r) - rhs_s, mp.mpf("0.05"))
        _assert_enclosed(self, st_s["finalOuterRadiusBoundsM"], r_s_true, max_width=1e-22, msg="sph r")

        # Spherical melting mirror from r_init = 0.06 m at warm reservoir 293.15 K.
        sph_melt = {
            **sph_sys,
            "id": "m06_sph_melt",
            "attachments": {
                "cryo": {"kind": "maintained", "temperatureK": "293.15"},
                "probe": {
                    **sph_sys["attachments"]["probe"],
                    "geometry": {"kind": "sphere", "coreRadiusM": "0.03", "initialOuterRadiusM": "0.06"},
                },
            },
            "solve": {"mode": "transient", "durationS": "2000"},
        }
        res_sm = solve_system(sph_melt)
        self.assertEqual(res_sm["status"], "melting")
        rhs_sm = f_sph(mp.mpf("0.06")) - (mp.mpf("20") / (rho * latent)) * mp.mpf("2000")
        r_sm_true = mp.findroot(lambda r: f_sph(r) - rhs_sm, mp.mpf("0.045"))
        _assert_enclosed(self, res_sm["backendResult"]["stefan"]["finalOuterRadiusBoundsM"], r_sm_true, max_width=1e-22, msg="sph melt r")

    def test_stefan_unresolved_direction_straddling_transition_stops_honestly(self) -> None:
        # 3-terminal tee where interval rod k causes T_eq to straddle T_tr = 273.15 K.
        sys_straddle = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_stefan_straddle",
            "nodes": ["cold", "warm", "ice"],
            "conduction": {
                "kind": "rods",
                "terminals": ["cold", "warm", "ice"],
                "rods": {
                    "c_rod": {"kind": "rod_area", "a": "cold", "b": "ice", "k": {"low": "9", "high": "11"}, "L": "1", "A": "1"},
                    "w_rod": {"kind": "rod_area", "a": "warm", "b": "ice", "k": "10", "L": "1", "A": "1"},
                },
            },
            "attachments": {
                "cold": {"kind": "maintained", "temperatureK": "263.15"},
                "warm": {"kind": "maintained", "temperatureK": "283.15"},
                "ice": {
                    "kind": "stefan_layer",
                    "geometry": {"kind": "planar", "areaM2": "1", "initialThicknessM": "0.05"},
                    "transitionTemperatureK": "273.15",
                    "densityKgPerM3": "917",
                    "specificLatentHeatJPerKg": "334000",
                    "layerConductivityWPerMK": "2.2",
                },
            },
            "solve": {"mode": "transient", "durationS": "1000"},
        }
        res = solve_system(sys_straddle)
        self.assertEqual(res["status"], "mode_sequence_uncertain")
        self.assertEqual(res["terminationReason"], "mode_sequence_uncertain")
        st = res["backendResult"]["stefan"]
        self.assertEqual(st["regime"], "unresolved")
        self.assertEqual(st["modeledDurationBoundsS"], ["0", "0"])
        self.assertEqual(st["finalThicknessBoundsM"], ["1/20", "1/20"])

        # Zero duration edge case resolves cleanly at s0 without throwing.
        sys_zero = {**sys_straddle, "solve": {"mode": "transient", "durationS": "0"}}
        res_z = solve_system(sys_zero)
        self.assertEqual(res_z["status"], "resolved")
        self.assertEqual(res_z["terminationReason"], "resolved")

    # ------------------------------------------------------------------
    # 3. Rod volumetric heat generation: exact parity & multi-junction intervals
    # ------------------------------------------------------------------
    def test_rod_generation_exact_composite_wall_and_probe(self) -> None:
        # Two rods in series a -- j -- b with G1 = 4 W/K, P1 = 80 W; G2 = 6 W/K, P2 = 40 W.
        # Maintained T_a = 300 K, T_b = 320 K.
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_heated_composite_wall",
            "nodes": ["a", "j", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {
                    "r1": {"kind": "rod_area", "a": "a", "b": "j", "k": "4", "L": "1", "A": "1", "generatedPowerW": "80"},
                    "r2": {"kind": "rod_area", "a": "j", "b": "b", "k": "6", "L": "1", "A": "1", "generatedPowerW": "40"},
                },
            },
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "300"},
                "b": {"kind": "maintained", "temperatureK": "320"},
            },
            "solve": {"mode": "steady"},
        }
        res = solve_system(system, rod_probe=("r1", "0.5"))
        self.assertEqual(res["backend"], "multiport")
        self.assertEqual(res["status"], "resolved")
        rg = res["rodGenerationSummary"]
        self.assertEqual(rg["totalGeneratedPowerW"], "120")

        # Exact hand calculation:
        # s_a = 40, s_j = 40 + 20 = 60, s_b = 20.
        # H_{j,a} = 4/(4+6) = 2/5, H_{j,b} = 6/10 = 3/5.
        # I_a = 40 + (2/5)*60 = 64 W, I_b = 20 + (3/5)*60 = 56 W (sum = 120 W).
        # Junction balance: 4*(T_j - 300) + 6*(T_j - 320) = 60 => 10*T_j = 3180 => T_j = 318 K.
        # Rod r1: T_a = 300, T_j = 318, curvature = 80/(2*4) = 10 K.
        # T_1(x) = 300 + 18*x + 10*x*(1-x) = 300 + 28*x - 10*x^2 => peak at x = 1.4 clamped to x = 1 -> T_peak = 318 K!
        # Wait: at x = 0.5: T_1(0.5) = 309 + 2.5 = 311.5 K; Q_1(0.5) = 4*(300-318) + 80*(0) = -72 W.
        # Rod r2: T_j = 318, T_b = 320, curvature = 40/(2*6) = 10/3 K.
        # Peak x = (1 + 2/(10/3))/2 = (1 + 3/5)/2 = 4/5 = 0.8; T_peak = 318 + 2*(4/5) + (10/3)*(4/5)*(1/5) = 318 + 8/5 + 8/15 = 320 + 2/15 K!
        self.assertEqual(rg["terminalNortonInjectionsBoundsW"]["a"], ["64", "64"])
        self.assertEqual(rg["terminalNortonInjectionsBoundsW"]["b"], ["56", "56"])
        self.assertEqual(rg["nodeTemperatureBoundsK"]["j"], ["318", "318"])
        self.assertEqual(rg["rodPeaks"]["r1"]["peakTemperatureBoundsK"], ["318", "318"])
        self.assertEqual(rg["rodPeaks"]["r1"]["peakPositionFractionFromABounds"], ["1", "1"])
        self.assertEqual(rg["rodPeaks"]["r2"]["peakTemperatureBoundsK"], [str(Fraction(4802, 15)), str(Fraction(4802, 15))])
        self.assertEqual(rg["rodPeaks"]["r2"]["peakPositionFractionFromABounds"], ["4/5", "4/5"])
        self.assertEqual(rg["probe"]["temperatureBoundsK"], ["623/2", "623/2"])
        self.assertEqual(rg["probe"]["heatCurrentTowardBBoundsW"], ["-72", "-72"])
        # Multiport steady global conservation: Q_out[a] + Q_out[b] = 120 W -> residual = 0!
        self.assertEqual(res["backendResult"]["systemEnergyBalanceBoundsW"], ["0", "0"])
        q_a = Fraction(res["backendResult"]["ports"]["a"]["inflowFromNetworkBoundsW"][0])
        q_b = Fraction(res["backendResult"]["ports"]["b"]["inflowFromNetworkBoundsW"][0])
        self.assertEqual(q_a + q_b, Fraction(120))
        # Exact Q_out[a] = 4*(318 - 300) + 40 = 112 W? Wait: passive W_ab = (4*6)/10 = 2.4 -> 2.4*(320-300) + 64 = 48 + 64 = 112 W!
        self.assertEqual(q_a, Fraction(112))
        self.assertEqual(q_b, Fraction(8))

    def test_multi_junction_interval_rod_generation_encloses_all_corners(self) -> None:
        # 2 internal junctions j1, j2 with wide interval conductances + circular rod:
        # stresses Howard policy iteration super-solution and residual certification.
        nodes = ["left", "j1", "j2", "right"]
        terminals = ["left", "right"]
        rods = {
            "r1": {"kind": "rod_area", "a": "left", "b": "j1", "k": {"low": "2", "high": "5"}, "L": "1", "A": "1", "generatedPowerW": "30"},
            "r2": {"kind": "rod_circular", "a": "j1", "b": "j2", "k": {"low": "8", "high": "12"}, "L": "1", "d": "0.5", "generatedPowerW": "50"},
            "r3": {"kind": "rod_area", "a": "j2", "b": "right", "k": {"low": "3", "high": "6"}, "L": "1", "A": "1", "generatedPowerW": "20"},
        }
        model = build_rod_generation_model(nodes, terminals, rods)
        assert model is not None
        term_temps = {"left": (Fraction(300), Fraction(300)), "right": (Fraction(310), Fraction(310))}
        prof = model.recover_profiles(term_temps)

        # Verify every corner (g1, g2, g3) of the interval box lies strictly inside the certified enclosures!
        g_ranges = [(e.g_lo, e.g_hi) for e in model.edges]
        for g1 in g_ranges[0]:
            for g2 in g_ranges[1]:
                for g3 in g_ranges[2]:
                    # Exact linear 2x2 junction solve:
                    # (g1+g2)*T1 - g2*T2 = g1*300 + s1 (s1 = 15 + 25 = 40)
                    # -g2*T1 + (g2+g3)*T2 = g3*310 + s2 (s2 = 25 + 10 = 35)
                    a11, a12 = g1 + g2, -g2
                    a21, a22 = -g2, g2 + g3
                    b1, b2 = g1 * 300 + 40, g3 * 310 + 35
                    det = a11 * a22 - a12 * a21
                    t1 = (a22 * b1 - a12 * b2) / det
                    t2 = (-a21 * b1 + a11 * b2) / det
                    _assert_enclosed(self, prof["nodeTemperatureBoundsK"]["j1"], mp.mpf(t1.numerator) / t1.denominator, msg="j1")
                    _assert_enclosed(self, prof["nodeTemperatureBoundsK"]["j2"], mp.mpf(t2.numerator) / t2.denominator, msg="j2")
                    # Exact parabolic peak on r2
                    c2 = Fraction(50) / (2 * g2)
                    x2 = max(Fraction(0), min(Fraction(1), (Fraction(1) + (t2 - t1) / c2) / 2))
                    peak2 = (1 - x2) * t1 + x2 * t2 + c2 * x2 * (1 - x2)
                    _assert_enclosed(self, prof["rodPeaks"]["r2"]["peakTemperatureBoundsK"], mp.mpf(peak2.numerator) / peak2.denominator, msg="peak2")

    # ------------------------------------------------------------------
    # 4. Cross-engine rod generation composition vs. 100-digit oracles
    # ------------------------------------------------------------------
    def test_heated_rod_with_nonlinear_radial_shell_and_phase_bath_multiport(self) -> None:
        # 3-terminal rod graph with internal junction j, heated rods, radiating/convecting spherical shell,
        # maintained cold sink, and coexisting ice bath!
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_heated_rod_shell_bath",
            "nodes": ["sink", "j", "vessel", "bath"],
            "conduction": {
                "kind": "rods",
                "terminals": ["sink", "vessel", "bath"],
                "rods": {
                    "s_j": {"kind": "rod_area", "a": "sink", "b": "j", "k": "2", "L": "1", "A": "1", "generatedPowerW": "40"},
                    "j_v": {"kind": "rod_area", "a": "j", "b": "vessel", "k": "3", "L": "1", "A": "1", "generatedPowerW": "60"},
                    "j_b": {"kind": "rod_area", "a": "j", "b": "bath", "k": "1", "L": "1", "A": "1", "generatedPowerW": "20"},
                },
            },
            "attachments": {
                "sink": {"kind": "maintained", "temperatureK": "300"},
                "bath": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "1",
                    "initialLiquidKg": "0.5",
                },
                "vessel": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "sphere",
                        "innerRadiusM": "0.05",
                        "layers": [{"outerRadiusM": "0.08", "conductivityWPerMK": "1.2"}],
                    },
                    "exterior": {
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "12",
                        "enclosureTemperatureK": "300",
                        "emissivity": "0.8",
                        "sigmaWPerM2K4": "0.0000000567",
                    },
                },
            },
            "solve": {"mode": "steady", "durationS": "600"},
        }
        res = solve_system(system)
        self.assertEqual(res["backend"], "multiport")
        self.assertEqual(res["terminationReason"], "converged")
        _assert_offline_flags_false(self, res)

        # Independent 100-digit mpmath nonlinear steady oracle (solving directly on the unreduced 4-node graph + shell!)
        r_in, r_out, k_sh = mp.mpf("0.05"), mp.mpf("0.08"), mp.mpf("1.2")
        g_sh = 4 * mp.pi * k_sh / (1 / r_in - 1 / r_out)
        a_out = 4 * mp.pi * r_out**2
        t_sink, t_bath = mp.mpf("300"), mp.mpf("273.15")
        h_c, eps, sig, t_env = mp.mpf("12"), mp.mpf("0.8"), mp.mpf("5.67e-8"), mp.mpf("300")
        # Nodal equations for (T_j, T_v, T_s):
        # 2*(T_j - 300) + 3*(T_j - T_v) + 1*(T_j - 273.15) = s_j = 20 + 30 + 10 = 60
        # 3*(T_v - T_j) + g_sh*(T_v - T_s) = s_v = 30
        # g_sh*(T_s - T_v) + a_out*(h_c*(T_s - 300) + eps*sig*(T_s^4 - 300^4)) = 0
        def resid(tj, tv, ts):
            return [
                2 * (tj - t_sink) + 3 * (tj - tv) + 1 * (tj - t_bath) - 60,
                3 * (tv - tj) + g_sh * (tv - ts) - 30,
                g_sh * (ts - tv) + a_out * (h_c * (ts - t_env) + eps * sig * (ts**4 - t_env**4)),
            ]

        tj_t, tv_t, ts_t = mp.findroot(resid, (mp.mpf("330"), mp.mpf("335"), mp.mpf("325")))
        q_bath_true = 1 * (tj_t - t_bath) + 10
        q_shell_true = g_sh * (tv_t - ts_t)
        # Parabolic peak on j_v (G = 3, P = 60 => c = 10)
        c_jv = mp.mpf("10")
        x_jv = (1 + (tv_t - tj_t) / c_jv) / 2
        peak_jv = (1 - x_jv) * tj_t + x_jv * tv_t + c_jv * x_jv * (1 - x_jv)

        mp_raw = res["backendResult"]
        _assert_enclosed(self, mp_raw["ports"]["vessel"]["innerFaceTemperatureBoundsK"], tv_t, max_width=1e-20, msg="T_v")
        _assert_enclosed(self, mp_raw["ports"]["vessel"]["outerFaceTemperatureBoundsK"], ts_t, max_width=1e-20, msg="T_s")
        _assert_enclosed(self, mp_raw["ports"]["vessel"]["outwardHeatRateBoundsW"], q_shell_true, max_width=1e-18, msg="Q_sh")
        _assert_enclosed(self, mp_raw["ports"]["bath"]["bathInflowDuringPlateauBoundsW"], q_bath_true, max_width=1e-18, msg="Q_bath")
        bal_lo, bal_hi = map(Fraction, mp_raw["systemEnergyBalanceBoundsW"])
        self.assertLessEqual(bal_lo, 0)
        self.assertGreaterEqual(bal_hi, 0)

        rg = res["rodGenerationSummary"]
        _assert_enclosed(self, rg["nodeTemperatureBoundsK"]["j"], tj_t, max_width=1e-20, msg="T_j")
        _assert_enclosed(self, rg["rodPeaks"]["j_v"]["peakTemperatureBoundsK"], peak_jv, max_width=1e-20, msg="peak j_v")

    def test_heated_rod_enthalpy_continuation_and_conservation_vs_mpmath(self) -> None:
        # Heated rod with internal junction connecting sensible body b and subcooled ice p (closed system).
        # Exact rod generation P_r1 = 200 W, P_r2 = 100 W -> total 300 W melts subcooled ice across solid -> plateau -> liquid!
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_heated_rod_enthalpy",
            "nodes": ["b", "j", "p"],
            "conduction": {
                "kind": "rods",
                "terminals": ["b", "p"],
                "rods": {
                    "r1": {"kind": "rod_area", "a": "b", "b": "j", "k": "4", "L": "1", "A": "1", "generatedPowerW": "200"},
                    "r2": {"kind": "rod_area", "a": "j", "b": "p", "k": "6", "L": "1", "A": "1", "generatedPowerW": "100"},
                },
            },
            "attachments": {
                "b": {"kind": "sensible_body", "heatCapacityJPerK": "200", "initialTemperatureK": "290"},
                "p": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "263.15",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.05",
                    "initialLiquidKg": "0",
                },
            },
            "solve": {"mode": "transient", "durationS": "200"},
        }
        res = solve_system(system)
        self.assertEqual(res["backend"], "enthalpy")
        self.assertEqual(res["status"], "complete")
        raw = res["backendResult"]
        # Should cross solid -> plateau AND plateau -> liquid!
        self.assertEqual(len(raw["events"]), 2)
        self.assertEqual(raw["ports"]["p"]["finalMode"], "liquid")

        # Verify global conservation residual contains 0 (with P_gen = 300 W).
        rlo, rhi = map(Fraction, raw["energyConservationResidualBoundsJ"])
        self.assertLessEqual(rlo, 0)
        self.assertGreaterEqual(rhi, 0)

        # Independent 100-digit piecewise exact ODE oracle:
        # W_bp = 4*6/(4+6) = 2.4; I_b = 100 + (4/10)*150 = 160 W; I_p = 50 + (6/10)*150 = 140 W.
        w_bp = mp.mpf("2.4")
        i_b, i_p = mp.mpf("160"), mp.mpf("140")
        cb = mp.mpf("200")
        m_p = mp.mpf("0.05")
        cs, cl, lat, t_tr = m_p * mp.mpf("2100"), m_p * mp.mpf("4200"), m_p * mp.mpf("334000"), mp.mpf("273.15")

        # Stage 1: linear 2-body ODE with constant sources i_b, i_p.
        # C_tot = cb + cs; let S(t) = (cb*Tb + cs*Tp)/C_tot = S0 + (i_b+i_p)/C_tot * t
        # D(t) = Tb - Tp satisfies dD/dt = -w_bp*(1/cb + 1/cs)*D + (i_b/cb - i_p/cs)
        def stage1_state(t: mp.mpf):
            lam = w_bp * (1 / cb + 1 / cs)
            d_inf = (i_b / cb - i_p / cs) / lam
            d0 = mp.mpf("290") - mp.mpf("263.15")
            d_t = d_inf + (d0 - d_inf) * mp.exp(-lam * t)
            s_t = (cb * mp.mpf("290") + cs * mp.mpf("263.15") + (i_b + i_p) * t) / (cb + cs)
            tb = s_t + (cs / (cb + cs)) * d_t
            tp = s_t - (cb / (cb + cs)) * d_t
            return tb, tp

        t1 = mp.findroot(lambda t: stage1_state(t)[1] - t_tr, mp.mpf("6"))
        tb1, _ = stage1_state(t1)

        # Stage 2: Tp clamped at t_tr; cb*dTb/dt = -w_bp*(Tb - t_tr) + i_b => Tb(dt) = tb_inf + (tb1 - tb_inf)*exp(-w_bp/cb * dt)
        tb_inf = t_tr + i_b / w_bp
        tau_b = cb / w_bp

        def h_plat(dt: mp.mpf):
            # H(dt) = int_0^dt (w_bp*(Tb(s) - t_tr) + i_p) ds = (i_b + i_p)*dt + w_bp*(tb1 - tb_inf)*tau_b*(1 - exp(-dt/tau_b))
            return (i_b + i_p) * dt + w_bp * (tb1 - tb_inf) * tau_b * (1 - mp.exp(-dt / tau_b))

        dt2 = mp.findroot(lambda dt: h_plat(dt) - lat, mp.mpf("80"))
        t2 = t1 + dt2
        tb2 = tb_inf + (tb1 - tb_inf) * mp.exp(-dt2 / tau_b)

        # Stage 3: liquid sensible for remaining dt3 = 200 - t2.
        dt3 = mp.mpf("200") - t2
        lam3 = w_bp * (1 / cb + 1 / cl)
        d3_inf = (i_b / cb - i_p / cl) / lam3
        d3_0 = tb2 - t_tr
        d3_f = d3_inf + (d3_0 - d3_inf) * mp.exp(-lam3 * dt3)
        s3_f = (cb * tb2 + cl * t_tr + (i_b + i_p) * dt3) / (cb + cl)
        tb_f = s3_f + (cl / (cb + cl)) * d3_f
        tp_f = s3_f - (cb / (cb + cl)) * d3_f
        tj_f = (4 * tb_f + 6 * tp_f + 150) / 10

        _assert_enclosed(self, raw["events"][0]["timeBoundsS"], t1, max_width=1e-5, msg="t1")
        _assert_enclosed(self, raw["events"][1]["timeBoundsS"], t2, max_width=1e-4, msg="t2")
        _assert_enclosed(self, raw["ports"]["b"]["finalTemperatureBoundsK"], tb_f, max_width=1e-4, msg="Tb_f")
        _assert_enclosed(self, raw["ports"]["p"]["finalTemperatureBoundsK"], tp_f, max_width=1e-4, msg="Tp_f")
        _assert_enclosed(self, res["rodGenerationSummary"]["nodeTemperatureBoundsK"]["j"], tj_f, max_width=1e-4, msg="Tj_f")

    def test_heated_rod_composes_with_stefan_and_staged(self) -> None:
        # 1. Heated rod + stefan_layer: Norton injection shifts T_eq_eff upward from 253.15 K to 263.15 K!
        # Single rod G = 2 W/K, P = 40 W => I_Norton = 20 W at each end => R_port * I_Norton = (1/2)*20 = 10 K shift!
        sys_st = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_heated_rod_stefan",
            "nodes": ["air", "ice"],
            "conduction": {
                "kind": "rods",
                "terminals": ["air", "ice"],
                "rods": {"slab": {"kind": "rod_area", "a": "air", "b": "ice", "k": "2", "L": "1", "A": "1", "generatedPowerW": "40"}},
            },
            "attachments": {
                "air": {"kind": "maintained", "temperatureK": "253.15"},
                "ice": {
                    "kind": "stefan_layer",
                    "geometry": {"kind": "planar", "areaM2": "1", "initialThicknessM": "0.01"},
                    "transitionTemperatureK": "273.15",
                    "densityKgPerM3": "917",
                    "specificLatentHeatJPerKg": "334000",
                    "layerConductivityWPerMK": "2.2",
                },
            },
            "solve": {"mode": "transient", "durationS": "5000"},
        }
        res_st = solve_system(sys_st)
        self.assertEqual(res_st["backend"], "stefan")
        self.assertEqual(res_st["status"], "growing")
        self.assertEqual(res_st["backendResult"]["portEquivalent"]["equilibriumTemperatureBoundsK"], ["5263/20", "5263/20"])  # 263.15 K
        b_len = mp.mpf("2.2") * mp.mpf("0.5")
        s_true = mp.sqrt((mp.mpf("0.01") + b_len) ** 2 + (2 * mp.mpf("2.2") * mp.mpf("10") / (mp.mpf("917") * mp.mpf("334000"))) * mp.mpf("5000")) - b_len
        _assert_enclosed(self, res_st["backendResult"]["stefan"]["finalThicknessBoundsM"], s_true, max_width=1e-35, msg="heated stefan s")
        self.assertIn("rodGenerationSummary", res_st)

        # 2. Heated rod + staged: rod heats subcooled ice even though cold reservoir is at 273.15 K!
        # G = 2 W/K, P = 40 W => I_Norton = 20 W => T_eq_eff = 273.15 + 10 = 283.15 K!
        sys_stg = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_heated_rod_staged",
            "nodes": ["res", "ice"],
            "conduction": {
                "kind": "rods",
                "terminals": ["res", "ice"],
                "rods": {"bar": {"kind": "rod_area", "a": "res", "b": "ice", "k": "2", "L": "1", "A": "1", "generatedPowerW": "40"}},
            },
            "attachments": {
                "res": {"kind": "maintained", "temperatureK": "273.15"},
                "ice": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "263.15",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.02",
                    "initialLiquidKg": "0",
                },
            },
            "solve": {"mode": "transient", "durationS": "600"},
        }
        res_stg = solve_system(sys_stg)
        self.assertEqual(res_stg["backend"], "staged")
        self.assertEqual(res_stg["backendResult"]["portEquivalent"]["equilibriumTemperatureBoundsK"], ["5663/20", "5663/20"])  # 283.15 K
        self.assertEqual(res_stg["status"], "liquid_sensible")
        self.assertIn("rodGenerationSummary", res_stg)

    # ------------------------------------------------------------------
    # 5. Fast-path gating (EH-01), symmetry-tie guard, and negative controls
    # ------------------------------------------------------------------
    def test_eh01_fast_path_gate_and_asymmetric_rod_gen_tie_guard(self) -> None:
        # Pure linear convection with interval rod conductance + internal junction -> interval Norton injection.
        # MUST NOT take exact_linear fast path!
        sys_int = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_eh01_interval_gen",
            "nodes": ["sink", "j", "face"],
            "conduction": {
                "kind": "rods",
                "terminals": ["sink", "face"],
                "rods": {
                    "r1": {"kind": "rod_area", "a": "sink", "b": "j", "k": {"low": "4", "high": "6"}, "L": "1", "A": "1", "generatedPowerW": "50"},
                    "r2": {"kind": "rod_area", "a": "j", "b": "face", "k": "5", "L": "1", "A": "1"},
                },
            },
            "attachments": {
                "sink": {"kind": "maintained", "temperatureK": "300"},
                "face": {
                    "kind": "exterior_surface",
                    "areaM2": "1",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "300",
                    "convectionCoefficientWPerM2K": "10",
                },
            },
            "solve": {"mode": "steady"},
        }
        res_int = solve_system(sys_int)
        self.assertEqual(res_int["terminationReason"], "converged")
        t_lo, t_hi = map(Fraction, res_int["backendResult"]["ports"]["face"]["temperatureBoundsK"])
        self.assertLess(t_lo, t_hi)

        # Exact-point version DOES take exact_linear fast path.
        sys_pt = {
            **sys_int,
            "conduction": {
                "kind": "rods",
                "terminals": ["sink", "face"],
                "rods": {
                    "r1": {"kind": "rod_area", "a": "sink", "b": "j", "k": "5", "L": "1", "A": "1", "generatedPowerW": "50"},
                    "r2": {"kind": "rod_area", "a": "j", "b": "face", "k": "5", "L": "1", "A": "1"},
                },
            },
        }
        res_pt = solve_system(sys_pt)
        self.assertEqual(res_pt["terminationReason"], "exact_linear")
        t_pt = Fraction(res_pt["backendResult"]["ports"]["face"]["temperatureBoundsK"][0])
        self.assertLessEqual(t_lo, t_pt)
        self.assertLessEqual(t_pt, t_hi)

        # Enthalpy symmetry-tie guard: symmetric passive W, identical phase specs,
        # slightly asymmetric rod generation -> MUST NOT claim simultaneousSymmetryProven!
        sys_asym = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_asym_rod_tie",
            "nodes": ["hot", "p1", "p2"],
            "conduction": {
                "kind": "rods",
                "terminals": ["hot", "p1", "p2"],
                "rods": {
                    "h1": {"kind": "rod_area", "a": "hot", "b": "p1", "k": "5", "L": "1", "A": "1", "generatedPowerW": "10"},
                    "h2": {"kind": "rod_area", "a": "hot", "b": "p2", "k": "5", "L": "1", "A": "1", "generatedPowerW": "9.99"},
                },
            },
            "attachments": {
                "hot": {"kind": "maintained", "temperatureK": "320"},
                "p1": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "263.15",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0",
                },
                "p2": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "263.15",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0",
                },
            },
            "solve": {"mode": "transient", "durationS": "20"},
        }
        res_asym = solve_system(sys_asym)
        for ev in res_asym["backendResult"]["events"]:
            self.assertFalse(ev["simultaneousSymmetryProven"])

    def test_negative_and_refusal_controls(self) -> None:
        base_stefan_att = {
            "kind": "stefan_layer",
            "geometry": {"kind": "planar", "areaM2": "1", "initialThicknessM": "0.01"},
            "transitionTemperatureK": "273.15",
            "densityKgPerM3": "917",
            "specificLatentHeatJPerKg": "334000",
            "layerConductivityWPerMK": "2.2",
        }
        base_rods = {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "5", "L": "1", "A": "1"}}

        # 1. steady + stefan_layer -> unsupported_regime
        r1 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "neg_steady_stefan",
            "nodes": ["a", "b"],
            "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
            "attachments": {"a": {"kind": "maintained", "temperatureK": "260"}, "b": base_stefan_att},
            "solve": {"mode": "steady"},
        })
        self.assertEqual(r1["status"], "unsupported_regime")
        self.assertEqual(r1["unsupportedMechanismPair"], ["steady_mode", "stefan_layer"])
        _assert_offline_flags_false(self, r1)

        # 2. transient + stefan_layer + sensible_body -> unsupported_regime
        r2 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "neg_stefan_body",
            "nodes": ["a", "b"],
            "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
            "attachments": {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "500", "initialTemperatureK": "260"},
                "b": base_stefan_att,
            },
            "solve": {"mode": "transient", "durationS": "60"},
        })
        self.assertEqual(r2["status"], "unsupported_regime")
        self.assertEqual(r2["unsupportedMechanismPair"], ["stefan_layer", "sensible_body"])

        # 3. transient + 2 stefan_layers -> unsupported_regime
        r3 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "neg_two_stefan",
            "nodes": ["a", "b"],
            "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
            "attachments": {"a": base_stefan_att, "b": base_stefan_att},
            "solve": {"mode": "transient", "durationS": "60"},
        })
        self.assertEqual(r3["status"], "unsupported_regime")
        self.assertEqual(r3["unsupportedMechanismPair"], ["stefan_layer", "multiple_stefan_layers"])

        # 4. transient + first_exhaustion + sensible_body + rod_generation -> unsupported_regime
        r4 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "neg_first_exh_gen",
            "nodes": ["a", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "5", "L": "1", "A": "1", "generatedPowerW": "10"}},
            },
            "attachments": {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "500", "initialTemperatureK": "300"},
                "b": {"kind": "maintained", "temperatureK": "280"},
            },
            "solve": {"mode": "transient", "durationS": "60", "continuation": "first_exhaustion"},
        })
        self.assertEqual(r4["status"], "unsupported_regime")
        self.assertEqual(r4["unsupportedMechanismPair"], ["first_exhaustion", "rod_generation"])

        # 5. generatedPowerW inside conduction.join -> ValueError
        with self.assertRaises(ValueError):
            ThermalSystem.from_dict({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "neg_join_gen",
                "conduction": {
                    "kind": "join",
                    "left": {
                        "kind": "rods",
                        "nodes": ["a", "c"],
                        "terminals": ["a", "c"],
                        "rods": {"r1": {"kind": "rod_area", "a": "a", "b": "c", "k": "5", "L": "1", "A": "1", "generatedPowerW": "10"}},
                    },
                    "right": {
                        "kind": "rods",
                        "nodes": ["c", "b"],
                        "terminals": ["c", "b"],
                        "rods": {"r2": {"kind": "rod_area", "a": "c", "b": "b", "k": "5", "L": "1", "A": "1"}},
                    },
                    "contacts": [{"leftPort": "c", "rightPort": "c"}],
                },
                "attachments": {
                    "left.a": {"kind": "maintained", "temperatureK": "300"},
                    "right.b": {"kind": "maintained", "temperatureK": "280"},
                },
                "solve": {"mode": "steady"},
            })

        # 6. Strict schema validation on stefan_layer (unknown key, maxThicknessM < initialThicknessM, r_init < r0)
        with self.assertRaises(ValueError):
            ThermalSystem.from_dict({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "neg_bad_key",
                "nodes": ["a", "b"],
                "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
                "attachments": {
                    "a": {"kind": "maintained", "temperatureK": "260"},
                    "b": {**base_stefan_att, "unknownField": "1"},
                },
                "solve": {"mode": "transient", "durationS": "60"},
            })
        with self.assertRaises(ValueError):
            ThermalSystem.from_dict({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "neg_bad_cap",
                "nodes": ["a", "b"],
                "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
                "attachments": {
                    "a": {"kind": "maintained", "temperatureK": "260"},
                    "b": {
                        **base_stefan_att,
                        "geometry": {"kind": "planar", "areaM2": "1", "initialThicknessM": "0.05", "maxThicknessM": "0.02"},
                    },
                },
                "solve": {"mode": "transient", "durationS": "60"},
            })

        # 7. Public lazy exports & describe_equations coverage
        self.assertEqual(simheat.STEFAN_SCHEMA, STEFAN_SCHEMA)
        self.assertIs(simheat.solve_stefan_from_law, solve_stefan_from_law)
        self.assertIs(simheat.build_rod_generation_model, build_rod_generation_model)
        eq = describe_equations({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_eq_check",
            "nodes": ["a", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "5", "L": "1", "A": "1", "generatedPowerW": "25"}},
            },
            "attachments": {"a": {"kind": "maintained", "temperatureK": "260"}, "b": base_stefan_att},
            "solve": {"mode": "transient", "durationS": "100"},
        })
        self.assertEqual(eq["selectedBackend"], "stefan")
        self.assertEqual(eq["conductionSummary"]["rodGenerationTotalPowerW"], "25")
        self.assertIn("I_Norton[b]", eq["equationsText"])
        self.assertIn("Quasi-steady planar Stefan front", eq["equationsText"])
        # M06-R04: per-terminal maintained equation includes + I_Norton[a] when rod generation is active.
        self.assertIn("+ I_Norton[a]", eq["terminalEquations"]["a"])

    # ------------------------------------------------------------------
    # 6. Review-finding discriminating regressions (M06-R01 .. M06-R05)
    # ------------------------------------------------------------------
    def test_m06_r01_howard_supersolution_and_random_multi_junction_interval_sweep(self) -> None:
        # Exact deterministic 4-node witness from M06-R01 where t_max_term > u*[j1] while s[j2] > 0.
        witness = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_r01_witness",
            "nodes": ["a", "b", "j1", "j2"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {
                    "a_j1": {"kind": "rod_area", "a": "a", "b": "j1", "k": "1", "L": "1", "A": "1"},
                    "j1_j2": {"kind": "rod_area", "a": "j1", "b": "j2", "k": {"low": "1", "high": "2"}, "L": "1", "A": "1"},
                    "a_j2": {"kind": "rod_area", "a": "a", "b": "j2", "k": "1", "L": "1", "A": "1", "generatedPowerW": "2400"},
                    "b_j1": {"kind": "rod_area", "a": "b", "b": "j1", "k": "0.001", "L": "1", "A": "1"},
                },
            },
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "300"},
                "b": {"kind": "maintained", "temperatureK": "1300"},
            },
            "solve": {"mode": "steady"},
        }
        res = solve_system(witness)
        self.assertEqual(res["status"], "resolved")
        rg = res["rodGenerationSummary"]
        # Check exact corner solutions for g(j1_j2) in {1, 2}.
        for g12 in (Fraction(1), Fraction(2)):
            # (1 + g12 + 1/1000)*T1 - g12*T2 = 300 + 1300/1000
            # -g12*T1 + (1 + g12)*T2 = 300 + 1200
            a11, a12 = Fraction(1001, 1000) + g12, -g12
            a21, a22 = -g12, Fraction(1) + g12
            b1, b2 = Fraction(3013, 10), Fraction(1500)
            det = a11 * a22 - a12 * a21
            t1 = (a22 * b1 - a12 * b2) / det
            t2 = (-a21 * b1 + a11 * b2) / det
            _assert_enclosed(self, rg["nodeTemperatureBoundsK"]["j1"], mp.mpf(t1.numerator) / t1.denominator, msg="r01 j1")
            _assert_enclosed(self, rg["nodeTemperatureBoundsK"]["j2"], mp.mpf(t2.numerator) / t2.denominator, msg="r01 j2")

        # 50-trial deterministic randomized 2-4 junction interval rod graph sweep (seed=42).
        rng = random.Random(42)
        for trial in range(50):
            nj = rng.randint(2, 4)
            terms = ["t0", "t1"]
            juncs = [f"j{k}" for k in range(nj)]
            nodes = terms + juncs
            rods = {}
            # Build random spanning tree first for guaranteed connectivity, plus 1-2 extra chords.
            order = list(nodes)
            rng.shuffle(order)
            edge_pairs = [(order[i], order[i + 1]) for i in range(len(order) - 1)]
            for _ in range(rng.randint(1, 2)):
                u, v = rng.sample(nodes, 2)
                edge_pairs.append((u, v))
            for idx, (u, v) in enumerate(edge_pairs):
                lo_k = rng.randint(1, 5)
                hi_k = lo_k + rng.randint(0, 5)
                pwr = rng.choice(["0", "0", "25", "120", "800"])
                if idx == 0:
                    pwr = "150"
                rods[f"e{idx}"] = {
                    "kind": "rod_area",
                    "a": u,
                    "b": v,
                    "k": str(lo_k) if lo_k == hi_k else {"low": str(lo_k), "high": str(hi_k)},
                    "L": "1",
                    "A": "1",
                    "generatedPowerW": pwr,
                }
            model = build_rod_generation_model(nodes, terms, rods)
            assert model is not None
            t_lo0 = Fraction(rng.randint(250, 350))
            t_hi1 = Fraction(rng.randint(400, 1200))
            prof = model.recover_profiles({"t0": (t_lo0, t_lo0), "t1": (t_hi1, t_hi1)})
            # Sample 3 exact realizations inside the conductance box and verify containment.
            from tools.multiport_thermal_network import _solve_exact_linear_fractions
            j_idx = {j: i for i, j in enumerate(juncs)}
            for mode_pick in (0, 1, 2):
                mat = [[Fraction(0)] * nj for _ in range(nj)]
                rhs = [model.endpoint_injections_w[j] for j in juncs]
                for e in model.edges:
                    g = e.g_lo if mode_pick == 0 else (e.g_hi if mode_pick == 1 else (e.g_lo + e.g_hi) / 2)
                    if e.a in j_idx and e.b in j_idx:
                        ia, ib = j_idx[e.a], j_idx[e.b]
                        mat[ia][ia] += g
                        mat[ib][ib] += g
                        mat[ia][ib] -= g
                        mat[ib][ia] -= g
                    elif e.a in j_idx:
                        ia = j_idx[e.a]
                        mat[ia][ia] += g
                        rhs[ia] += g * (t_lo0 if e.b == "t0" else t_hi1)
                    elif e.b in j_idx:
                        ib = j_idx[e.b]
                        mat[ib][ib] += g
                        rhs[ib] += g * (t_lo0 if e.a == "t0" else t_hi1)
                sol = _solve_exact_linear_fractions(mat, rhs)
                for i, j in enumerate(juncs):
                    lo_b, hi_b = map(Fraction, prof["nodeTemperatureBoundsK"][j])
                    self.assertLessEqual(lo_b, sol[i], f"trial {trial} {j}")
                    self.assertGreaterEqual(hi_b, sol[i], f"trial {trial} {j}")

    def test_m06_r02_r03_r04_r05_validation_and_equation_consistency(self) -> None:
        # M06-R02: unknown rod_probe, out-of-range x, and rod_probe on unheated system raise ValueError.
        heated_sys = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m06_r02_heated",
            "nodes": ["a", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {"r1": {"kind": "rod_area", "a": "a", "b": "b", "k": "5", "L": "1", "A": "1", "generatedPowerW": "20"}},
            },
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "300"},
                "b": {"kind": "maintained", "temperatureK": "310"},
            },
            "solve": {"mode": "steady"},
        }
        with self.assertRaises(ValueError):
            solve_system(heated_sys, rod_probe=("nonexistent", "0.5"))
        with self.assertRaises(ValueError):
            solve_system(heated_sys, rod_probe=("r1", "1.5"))

        unheated_sys = {
            **heated_sys,
            "id": "m06_r02_unheated",
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {"r1": {"kind": "rod_area", "a": "a", "b": "b", "k": "5", "L": "1", "A": "1"}},
            },
        }
        with self.assertRaises(ValueError):
            solve_system(unheated_sys, rod_probe=("r1", "0.5"))

        # M06-R03: standalone build_rod_generation_model rejects self-loops, bogus kind, disconnected graph.
        with self.assertRaises(ValueError):
            build_rod_generation_model(
                ["a", "b"], ["a", "b"],
                {"r1": {"kind": "rod_area", "a": "a", "b": "a", "k": "1", "L": "1", "A": "1", "generatedPowerW": "10"}},
            )
        with self.assertRaises(ValueError):
            build_rod_generation_model(
                ["a", "b"], ["a", "b"],
                {"r1": {"kind": "bogus", "a": "a", "b": "b", "k": "1", "L": "1", "d": "1", "generatedPowerW": "10"}},
            )
        with self.assertRaises(ValueError):
            build_rod_generation_model(
                ["a", "b", "isolated"], ["a", "b"],
                {"r1": {"kind": "rod_area", "a": "a", "b": "b", "k": "1", "L": "1", "A": "1", "generatedPowerW": "10"}},
            )

        # M06-R04: describe_equations includes + I_Norton[t] on heated terminal equations, omits on unheated.
        eq_h = describe_equations(heated_sys)
        eq_u = describe_equations(unheated_sys)
        self.assertIn("+ I_Norton[a]", eq_h["terminalEquations"]["a"])
        self.assertIn("+ I_Norton[b]", eq_h["terminalEquations"]["b"])
        self.assertNotIn("I_Norton", eq_u["terminalEquations"]["a"])

        # M06-R05: direct engine calls reject nonzero total_generated_power_w without terminal_injections_w.
        law = DerivedLaw.from_rods(
            ["a", "b"],
            {"r1": {"kind": "rod_area", "a": "a", "b": "b", "k": "5", "L": "1", "A": "1"}},
            terminals=["a", "b"],
        )
        with self.assertRaises(ValueError):
            solve_multiport(
                law,
                {"a": {"kind": "maintained", "temperatureK": "300"}, "b": {"kind": "maintained", "temperatureK": "310"}},
                total_generated_power_w=Fraction(10),
            )
        with self.assertRaises(ValueError):
            solve_enthalpy_continuation(
                law,
                {
                    "a": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "300"},
                    "b": {"kind": "maintained", "temperatureK": "310"},
                },
                "10",
                total_generated_power_w=Fraction(10),
            )


if __name__ == "__main__":
    unittest.main()
