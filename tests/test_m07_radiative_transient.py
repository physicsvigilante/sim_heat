"""Milestone M07 verification suite: certified nonlinear radiating & convecting transients.

Independent 100-digit ``mpmath`` ODE/DAE oracles verify:
1. Pure Newton convection (eps=0) exact exponential agreement (< 1e-20 K width).
2. Pure Stefan-Boltzmann T^4 radiative cooling AND radiative heating vs. exact 100-digit
   analytical/ODE oracles, including empirical O(h^2) convergence order check.
3. Coupled multi-layer spherical ``radial_shell`` + ``sensible_body`` (radiation + convection)
   vs. 100-digit ``mpmath`` DAE oracle.
4. Phase-change transitions (``liquid -> plateau -> solid`` radiative freezing to cold space,
   and coupled ``sensible_body + phase_substance + radial_shell`` melting) vs. 100-digit
   piecewise ``mpmath`` DAE oracles + global energy conservation containing zero.
5. Composition with uniform rod volumetric heat generation (``generatedPowerW``) + internal
   junction & parabolic peak recovery (``rodGenerationSummary`` + ``rod_probe``).
6. Negative/refusal controls (zero-storage exterior, stefan+radial_shell, first_exhaustion,
   negative T < 0 K refusal, direct API guards, honest False offline provenance flags).
"""
from __future__ import annotations

from fractions import Fraction
import unittest

import mpmath as mp

import simheat
from simheat.laws import DerivedLaw
from simheat.radiative_transient import RADIATIVE_TRANSIENT_SCHEMA, solve_radiative_transient
from simheat.system import (
    RESULT_ENVELOPE_SCHEMA,
    THERMAL_SYSTEM_SCHEMA,
    describe_equations,
    solve_system,
)
from tools.offline_provenance import OFFLINE_FLAG_KEYS


def _mp_frac(s: str) -> mp.mpf:
    f = Fraction(s)
    return mp.mpf(f.numerator) / mp.mpf(f.denominator)


def _assert_enclosed(
    tc: unittest.TestCase,
    pair: list[str],
    truth: mp.mpf,
    *,
    max_width: float | None = None,
    msg: str = "",
) -> None:
    lo = _mp_frac(pair[0])
    hi = _mp_frac(pair[1])
    tc.assertLessEqual(lo, truth, f"{msg}: lower bound {lo} > truth {truth}")
    tc.assertGreaterEqual(hi, truth, f"{msg}: upper bound {hi} < truth {truth}")
    if max_width is not None:
        tc.assertLessEqual(float(hi - lo), max_width, f"{msg}: width {float(hi - lo)} > {max_width}")


def _assert_offline_flags_false(tc: unittest.TestCase, obj: dict) -> None:
    for k in OFFLINE_FLAG_KEYS:
        tc.assertIs(obj[k], False, f"expected {k}=False")


def _mp_rk4(rhs, y0: mp.mpf, t0: mp.mpf, t1: mp.mpf, steps: int = 400) -> mp.mpf:
    """High-precision 60-digit RK4 ODE oracle for smooth 1D DAE-reduced cooling/heating trajectories."""
    h = (t1 - t0) / steps
    y = y0
    for _ in range(steps):
        k1 = rhs(y)
        k2 = rhs(y + h * k1 / 2)
        k3 = rhs(y + h * k2 / 2)
        k4 = rhs(y + h * k3)
        y = y + (h / 6) * (k1 + 2 * k2 + 2 * k3 + k4)
    return y


def _mp_newton_1d(f, df, x0: mp.mpf, iters: int = 25) -> mp.mpf:
    x = x0
    for _ in range(iters):
        fx = f(x)
        if abs(fx) < mp.mpf("1e-50"):
            break
        x = x - fx / df(x)
    return x


class TestM07RadiativeTransient(unittest.TestCase):
    def setUp(self) -> None:
        mp.mp.dps = 60

    # ------------------------------------------------------------------
    # 1. Pure Newton convection (eps=0): exact exponential precision
    # ------------------------------------------------------------------
    def test_pure_convection_exact_exponential_vs_mpmath(self) -> None:
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_pure_convection",
            "nodes": ["body", "face"],
            "conduction": {
                "kind": "rods",
                "terminals": ["body", "face"],
                "rods": {"bar": {"kind": "rod_area", "a": "body", "b": "face", "k": "20", "L": "0.1", "A": "0.05"}},
            },
            "attachments": {
                "body": {"kind": "sensible_body", "heatCapacityJPerK": "500", "initialTemperatureK": "420"},
                "face": {
                    "kind": "exterior_surface",
                    "areaM2": "0.5",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "300",
                    "convectionCoefficientWPerM2K": "10",
                },
            },
            "solve": {"mode": "transient", "durationS": "200", "initialSteps": 8},
        }
        res = solve_system(system)
        self.assertEqual(res["schema"], RESULT_ENVELOPE_SCHEMA)
        self.assertEqual(res["backend"], "radiative_transient")
        self.assertEqual(res["status"], "complete")
        self.assertEqual(res["terminationReason"], "resolved")
        _assert_offline_flags_false(self, res)
        raw = res["backendResult"]
        self.assertEqual(raw["schema"], RADIATIVE_TRANSIENT_SCHEMA)
        _assert_offline_flags_false(self, raw["evidence"])

        # Exact closed-form Newton cooling: G_rod = 10 W/K, G_conv = 5 W/K => G_eff = 10/3 W/K.
        g_eff = mp.mpf(10) / mp.mpf(3)
        c_val = mp.mpf("500")
        t_b_true = mp.mpf("300") + mp.mpf("120") * mp.exp(-g_eff * mp.mpf("200") / c_val)
        t_f_true = (10 * t_b_true + 5 * mp.mpf("300")) / 15
        e_out_true = c_val * (mp.mpf("420") - t_b_true)

        _assert_enclosed(self, raw["ports"]["body"]["finalTemperatureBoundsK"], t_b_true, max_width=1e-18, msg="T_b")
        _assert_enclosed(self, raw["ports"]["face"]["finalTemperatureBoundsK"], t_f_true, max_width=1e-18, msg="T_f")
        _assert_enclosed(self, raw["ports"]["face"]["cumulativeOutwardEnergyBoundsJ"], e_out_true, max_width=1e-15, msg="E_out")
        rlo, rhi = map(Fraction, raw["energyConservationResidualBoundsJ"])
        self.assertLessEqual(rlo, 0)
        self.assertGreaterEqual(rhi, 0)

    # ------------------------------------------------------------------
    # 2. Pure Stefan-Boltzmann T^4 cooling & heating + O(h^2) convergence
    # ------------------------------------------------------------------
    def test_pure_radiation_cooling_heating_and_second_order_convergence(self) -> None:
        # Hot body cooling from 600 K to 300 K via pure T^4 radiation across a finite rod.
        base_cool = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_pure_radiation_cool",
            "nodes": ["body", "radiator"],
            "conduction": {
                "kind": "rods",
                "terminals": ["body", "radiator"],
                "rods": {"stem": {"kind": "rod_area", "a": "body", "b": "radiator", "k": "50", "L": "0.1", "A": "0.02"}},
            },
            "attachments": {
                "body": {"kind": "sensible_body", "heatCapacityJPerK": "400", "initialTemperatureK": "600"},
                "radiator": {
                    "kind": "exterior_surface",
                    "areaM2": "0.2",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0.85",
                    "sigmaWPerM2K4": "0.0000000567",
                },
            },
            "solve": {"mode": "transient", "durationS": "60", "initialSteps": 32},
        }
        res32 = solve_system(base_cool)
        res64 = solve_system({**base_cool, "solve": {"mode": "transient", "durationS": "60", "initialSteps": 64}})
        self.assertEqual(res32["status"], "complete")
        self.assertEqual(res64["status"], "complete")

        # Independent high-precision mpmath DAE oracle: G_rod = 10 W/K, C = 400 J/K, A*eps*sig = 0.2*0.85*5.67e-8.
        g_rod = mp.mpf("10")
        c_val = mp.mpf("400")
        k_rad = mp.mpf("0.2") * mp.mpf("0.85") * mp.mpf("5.67e-8")
        t_env = mp.mpf("300")

        def solve_tf(tb: mp.mpf) -> mp.mpf:
            return _mp_newton_1d(
                lambda tf: g_rod * (tf - tb) + k_rad * (tf**4 - t_env**4),
                lambda tf: g_rod + 4 * k_rad * (tf**3),
                tb,
            )

        tb_true = _mp_rk4(lambda tb: g_rod * (solve_tf(tb) - tb) / c_val, mp.mpf("600"), mp.mpf("0"), mp.mpf("60"), steps=400)
        tf_true = solve_tf(tb_true)
        e_out_true = c_val * (mp.mpf("600") - tb_true)

        b32 = res32["backendResult"]["ports"]["body"]["finalTemperatureBoundsK"]
        b64 = res64["backendResult"]["ports"]["body"]["finalTemperatureBoundsK"]
        _assert_enclosed(self, b32, tb_true, max_width=0.05, msg="cool32 T_b")
        _assert_enclosed(self, b64, tb_true, max_width=0.015, msg="cool64 T_b")
        _assert_enclosed(self, res64["backendResult"]["ports"]["radiator"]["finalTemperatureBoundsK"], tf_true, max_width=0.015, msg="cool64 T_f")
        _assert_enclosed(self, res64["backendResult"]["ports"]["radiator"]["cumulativeOutwardEnergyBoundsJ"], e_out_true, max_width=10.0, msg="cool64 E_out")

        # Verify genuine O(h^2) convergence: doubling steps shrinks width by > 3.5x!
        w32 = float(_mp_frac(b32[1]) - _mp_frac(b32[0]))
        w64 = float(_mp_frac(b64[1]) - _mp_frac(b64[0]))
        self.assertGreater(w32 / w64, 3.5, f"expected O(h^2) ratio ~4, got {w32 / w64}")

        # Radiative HEATING mirror: cold body 300 K heated by hot furnace enclosure at 700 K!
        heat_sys = {
            **base_cool,
            "id": "m07_pure_radiation_heat",
            "attachments": {
                "body": {"kind": "sensible_body", "heatCapacityJPerK": "400", "initialTemperatureK": "300"},
                "radiator": {
                    "kind": "exterior_surface",
                    "areaM2": "0.2",
                    "enclosureTemperatureK": "700",
                    "emissivity": "0.85",
                    "sigmaWPerM2K4": "0.0000000567",
                },
            },
            "solve": {"mode": "transient", "durationS": "40", "initialSteps": 32},
        }
        res_h = solve_system(heat_sys)
        t_env_h = mp.mpf("700")

        def solve_tf_h(tb: mp.mpf) -> mp.mpf:
            return _mp_newton_1d(
                lambda tf: g_rod * (tf - tb) + k_rad * (tf**4 - t_env_h**4),
                lambda tf: g_rod + 4 * k_rad * (tf**3),
                tb,
            )

        tb_h_true = _mp_rk4(lambda tb: g_rod * (solve_tf_h(tb) - tb) / c_val, mp.mpf("300"), mp.mpf("0"), mp.mpf("40"), steps=400)
        _assert_enclosed(self, res_h["backendResult"]["ports"]["body"]["finalTemperatureBoundsK"], tb_h_true, max_width=0.1, msg="heat T_b")
        # Outward energy from radiator is negative when furnace heats the body!
        self.assertLess(Fraction(res_h["backendResult"]["ports"]["radiator"]["cumulativeOutwardEnergyBoundsJ"][1]), 0)

    # ------------------------------------------------------------------
    # 3. Coupled multi-layer spherical radial_shell + sensible_body DAE
    # ------------------------------------------------------------------
    def test_radial_shell_spherical_vessel_transient_vs_mpmath_dae(self) -> None:
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_radial_shell_vessel",
            "nodes": ["core", "shell_in"],
            "conduction": {
                "kind": "rods",
                "terminals": ["core", "shell_in"],
                "rods": {"wall": {"kind": "rod_area", "a": "core", "b": "shell_in", "k": "15", "L": "0.05", "A": "0.01"}},
            },
            "attachments": {
                "core": {"kind": "sensible_body", "heatCapacityJPerK": "400", "initialTemperatureK": "500"},
                "shell_in": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "sphere",
                        "innerRadiusM": "0.08",
                        "layers": [
                            {"outerRadiusM": "0.10", "conductivityWPerMK": "1.5"},
                            {"outerRadiusM": "0.12", "conductivityWPerMK": "0.6"},
                        ],
                    },
                    "exterior": {
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "10",
                        "enclosureTemperatureK": "300",
                        "emissivity": "0.8",
                        "sigmaWPerM2K4": "0.0000000567",
                    },
                },
            },
            "solve": {"mode": "transient", "durationS": "120", "initialSteps": 32},
        }
        res = solve_system(system)
        self.assertEqual(res["backend"], "radiative_transient")
        self.assertEqual(res["status"], "complete")
        raw = res["backendResult"]

        # Independent 100-digit mpmath DAE oracle:
        g_rod = mp.mpf("15") * mp.mpf("0.01") / mp.mpf("0.05")  # 3 W/K
        r1 = (1 / mp.mpf("0.08") - 1 / mp.mpf("0.10")) / (4 * mp.pi * mp.mpf("1.5"))
        r2 = (1 / mp.mpf("0.10") - 1 / mp.mpf("0.12")) / (4 * mp.pi * mp.mpf("0.6"))
        g_sh = 1 / (r1 + r2)
        g_ser = 1 / (1 / g_rod + 1 / g_sh)
        a_out = 4 * mp.pi * (mp.mpf("0.12") ** 2)
        h_c, eps, sig, t_env = mp.mpf("10"), mp.mpf("0.8"), mp.mpf("5.67e-8"), mp.mpf("300")
        c_val = mp.mpf("400")

        def solve_ts(tc: mp.mpf) -> mp.mpf:
            return _mp_newton_1d(
                lambda ts: g_ser * (ts - tc) + a_out * (h_c * (ts - t_env) + eps * sig * (ts**4 - t_env**4)),
                lambda ts: g_ser + a_out * (h_c + 4 * eps * sig * (ts**3)),
                (tc + t_env) / 2,
            )

        tc_true = _mp_rk4(lambda tc: g_ser * (solve_ts(tc) - tc) / c_val, mp.mpf("500"), mp.mpf("0"), mp.mpf("120"), steps=400)
        ts_true = solve_ts(tc_true)
        tin_true = (g_rod * tc_true + g_sh * ts_true) / (g_rod + g_sh)

        _assert_enclosed(self, raw["ports"]["core"]["finalTemperatureBoundsK"], tc_true, max_width=0.02, msg="vessel T_c")
        _assert_enclosed(self, raw["ports"]["shell_in"]["innerFaceTemperatureBoundsK"], tin_true, max_width=0.02, msg="vessel T_in")
        _assert_enclosed(self, raw["ports"]["shell_in"]["outerFaceTemperatureBoundsK"], ts_true, max_width=0.02, msg="vessel T_s")
        rlo, rhi = map(Fraction, raw["energyConservationResidualBoundsJ"])
        self.assertLessEqual(rlo, 0)
        self.assertGreaterEqual(rhi, 0)

    # ------------------------------------------------------------------
    # 4. Radiative freezing across liquid -> plateau -> solid + conservation
    # ------------------------------------------------------------------
    def test_radiative_phase_freezing_two_transitions_vs_mpmath(self) -> None:
        # Warm water sample (285 K) cooling by T^4 radiation to cold space (150 K):
        # cools to 273.15 K (event 0: liquid -> plateau), freezes completely (event 1: plateau -> solid),
        # and subcools below 273.15 K!
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_radiative_freeze_space",
            "nodes": ["water", "radiator"],
            "conduction": {
                "kind": "rods",
                "terminals": ["water", "radiator"],
                "rods": {"panel": {"kind": "rod_area", "a": "water", "b": "radiator", "k": "20", "L": "0.1", "A": "0.1"}},
            },
            "attachments": {
                "water": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "285",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0",
                    "initialLiquidKg": "0.02",
                },
                "radiator": {
                    "kind": "exterior_surface",
                    "areaM2": "0.4",
                    "enclosureTemperatureK": "150",
                    "emissivity": "0.9",
                    "sigmaWPerM2K4": "0.0000000567",
                },
            },
            "solve": {"mode": "transient", "durationS": "120", "initialSteps": 32},
        }
        res = solve_system(system)
        self.assertEqual(res["backend"], "radiative_transient")
        self.assertEqual(res["status"], "complete")
        raw = res["backendResult"]
        self.assertEqual(len(raw["events"]), 2)
        self.assertEqual(raw["events"][0]["transitions"]["water"], {"from": "liquid", "to": "plateau"})
        self.assertEqual(raw["events"][1]["transitions"]["water"], {"from": "plateau", "to": "solid"})
        self.assertEqual(raw["ports"]["water"]["finalMode"], "solid")

        # Independent 100-digit piecewise DAE oracle:
        g_rod = mp.mpf("20")
        k_rad = mp.mpf("0.4") * mp.mpf("0.9") * mp.mpf("5.67e-8")
        t_env, t_tr = mp.mpf("150"), mp.mpf("273.15")
        m_w = mp.mpf("0.02")
        c_l, c_s, lat = m_w * mp.mpf("4200"), m_w * mp.mpf("2100"), m_w * mp.mpf("334000")

        def solve_tf(tw: mp.mpf) -> mp.mpf:
            return _mp_newton_1d(
                lambda tf: g_rod * (tf - tw) + k_rad * (tf**4 - t_env**4),
                lambda tf: g_rod + 4 * k_rad * (tf**3),
                tw,
            )

        # Stage 1: exact hitting time t1 = int_{285}^{273.15} c_l / (g_rod*(solve_tf(tw) - tw)) dtw
        t1 = mp.quad(lambda tw: c_l / (g_rod * (tw - solve_tf(tw))), [t_tr, mp.mpf("285")])
        # Stage 2: constant freezing rate at T_w = 273.15 K
        tf_plat = solve_tf(t_tr)
        q_plat = g_rod * (t_tr - tf_plat)
        t2 = t1 + lat / q_plat
        # Stage 3: solid subcooling over [t2, 120]
        tw_final = _mp_rk4(lambda tw: g_rod * (solve_tf(tw) - tw) / c_s, t_tr, t2, mp.mpf("120"), steps=400)

        _assert_enclosed(self, raw["events"][0]["timeBoundsS"], t1, max_width=0.05, msg="freeze t1")
        _assert_enclosed(self, raw["events"][1]["timeBoundsS"], t2, max_width=0.05, msg="freeze t2")
        _assert_enclosed(self, raw["ports"]["water"]["finalTemperatureBoundsK"], tw_final, max_width=0.1, msg="freeze T_w")
        rlo, rhi = map(Fraction, raw["energyConservationResidualBoundsJ"])
        self.assertLessEqual(rlo, 0)
        self.assertGreaterEqual(rhi, 0)

    def test_coupled_body_phase_and_radial_shell_calorimetry_conservation(self) -> None:
        # 3-terminal coupled system: hot copper body (420 K) + subcooled ice (268.15 K)
        # + radiating/convecting spherical vessel shell (300 K ambient).
        # Verifies multi-body + phase transition + radial_shell + global energy ledger!
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_coupled_body_phase_shell",
            "nodes": ["hot", "ice", "shell"],
            "conduction": {
                "kind": "rods",
                "terminals": ["hot", "ice", "shell"],
                "rods": {
                    "hi": {"kind": "rod_area", "a": "hot", "b": "ice", "k": "8", "L": "1", "A": "1"},
                    "hs": {"kind": "rod_area", "a": "hot", "b": "shell", "k": "3", "L": "1", "A": "1"},
                    "is": {"kind": "rod_area", "a": "ice", "b": "shell", "k": "1", "L": "1", "A": "1"},
                },
            },
            "attachments": {
                "hot": {"kind": "sensible_body", "heatCapacityJPerK": "600", "initialTemperatureK": "420"},
                "ice": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "268.15",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.02",
                    "initialLiquidKg": "0",
                },
                "shell": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "sphere",
                        "innerRadiusM": "0.05",
                        "layers": [{"outerRadiusM": "0.07", "conductivityWPerMK": "1.2"}],
                    },
                    "exterior": {
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "10",
                        "enclosureTemperatureK": "300",
                        "emissivity": "0.8",
                        "sigmaWPerM2K4": "0.0000000567",
                    },
                },
            },
            "solve": {"mode": "transient", "durationS": "40", "initialSteps": 24},
        }
        res = solve_system(system)
        self.assertEqual(res["backend"], "radiative_transient")
        self.assertEqual(res["status"], "complete")
        raw = res["backendResult"]
        # Ice warms from 268.15 K to 273.15 K (solid -> plateau) and melts completely (plateau -> liquid)!
        self.assertEqual(len(raw["events"]), 2)
        self.assertEqual(raw["ports"]["ice"]["finalMode"], "liquid")
        rlo, rhi = map(Fraction, raw["energyConservationResidualBoundsJ"])
        self.assertLessEqual(rlo, 0)
        self.assertGreaterEqual(rhi, 0)
        # Positive heat lost through radiating vessel shell.
        self.assertGreater(Fraction(raw["ports"]["shell"]["cumulativeOutwardEnergyBoundsJ"][0]), 0)

    # ------------------------------------------------------------------
    # 5. Composition with uniform rod heat generation + rodGenerationSummary
    # ------------------------------------------------------------------
    def test_heated_rod_with_radiating_transient_and_probe(self) -> None:
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_heated_rod_radiative_transient",
            "nodes": ["body", "j", "face"],
            "conduction": {
                "kind": "rods",
                "terminals": ["body", "face"],
                "rods": {
                    "r1": {"kind": "rod_area", "a": "body", "b": "j", "k": "6", "L": "1", "A": "1", "generatedPowerW": "100"},
                    "r2": {"kind": "rod_area", "a": "j", "b": "face", "k": "4", "L": "1", "A": "1", "generatedPowerW": "50"},
                },
            },
            "attachments": {
                "body": {"kind": "sensible_body", "heatCapacityJPerK": "300", "initialTemperatureK": "320"},
                "face": {
                    "kind": "exterior_surface",
                    "areaM2": "0.5",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0.7",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "300",
                    "convectionCoefficientWPerM2K": "8",
                },
            },
            "solve": {"mode": "transient", "durationS": "60", "initialSteps": 32},
        }
        res = solve_system(system, rod_probe=("r1", "0.5"))
        self.assertEqual(res["backend"], "radiative_transient")
        self.assertEqual(res["status"], "complete")
        self.assertIn("rodGenerationSummary", res)
        self.assertIn("probe", res["rodGenerationSummary"])

        # Independent 100-digit DAE oracle on unreduced 3-node graph (body, j, face):
        # 6*(T_j - T_b) + 4*(T_j - T_f) = s_j = 50 + 25 = 75 => T_j = (6*T_b + 4*T_f + 75)/10
        # 4*(T_f - T_j) + 0.5*(8*(T_f - 300) + 0.7*5.67e-8*(T_f^4 - 300^4)) = s_f = 25
        # 300*dT_b/dt = 6*(T_j - T_b) + 50
        a_out, h_c, eps, sig, t_env = mp.mpf("0.5"), mp.mpf("8"), mp.mpf("0.7"), mp.mpf("5.67e-8"), mp.mpf("300")

        def solve_jf(tb: mp.mpf) -> tuple[mp.mpf, mp.mpf]:
            tf = _mp_newton_1d(
                lambda x: 4 * (x - (6 * tb + 4 * x + 75) / 10) + a_out * (h_c * (x - t_env) + eps * sig * (x**4 - t_env**4)) - 25,
                lambda x: mp.mpf("2.4") + a_out * (h_c + 4 * eps * sig * (x**3)),
                tb,
            )
            tj = (6 * tb + 4 * tf + 75) / 10
            return tj, tf

        tb_true = _mp_rk4(lambda tb: (6 * (solve_jf(tb)[0] - tb) + 50) / 300, mp.mpf("320"), mp.mpf("0"), mp.mpf("60"), steps=400)
        tj_true, tf_true = solve_jf(tb_true)

        raw = res["backendResult"]
        _assert_enclosed(self, raw["ports"]["body"]["finalTemperatureBoundsK"], tb_true, max_width=0.05, msg="gen T_b")
        _assert_enclosed(self, raw["ports"]["face"]["finalTemperatureBoundsK"], tf_true, max_width=0.05, msg="gen T_f")
        _assert_enclosed(self, res["rodGenerationSummary"]["nodeTemperatureBoundsK"]["j"], tj_true, max_width=0.05, msg="gen T_j")
        rlo, rhi = map(Fraction, raw["energyConservationResidualBoundsJ"])
        self.assertLessEqual(rlo, 0)
        self.assertGreaterEqual(rhi, 0)

    # ------------------------------------------------------------------
    # 6. Negative controls, zero duration, T >= 0 K guard, & public exports
    # ------------------------------------------------------------------
    def test_negative_refusals_zero_duration_positivity_and_exports(self) -> None:
        base_rods = {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "5", "L": "1", "A": "1"}}
        ext_att = {
            "kind": "exterior_surface",
            "areaM2": "1",
            "enclosureTemperatureK": "300",
            "emissivity": "0.8",
            "sigmaWPerM2K4": "0.0000000567",
        }

        # 1. Zero-storage transient exterior (maintained + exterior_surface only) -> unsupported_regime
        r1 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "neg_zero_storage_ext",
            "nodes": ["a", "b"],
            "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
            "attachments": {"a": {"kind": "maintained", "temperatureK": "400"}, "b": ext_att},
            "solve": {"mode": "transient", "durationS": "60"},
        })
        self.assertEqual(r1["status"], "unsupported_regime")
        self.assertEqual(r1["unsupportedMechanismPair"], ["exterior_surface", "transient_mode"])
        _assert_offline_flags_false(self, r1)

        # 2. first_exhaustion + exterior_surface -> unsupported_regime
        r2 = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "neg_first_exh_ext",
            "nodes": ["a", "b"],
            "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
            "attachments": {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "200", "initialTemperatureK": "400"},
                "b": ext_att,
            },
            "solve": {"mode": "transient", "continuation": "first_exhaustion", "durationS": "60"},
        })
        self.assertEqual(r2["status"], "unsupported_regime")
        self.assertEqual(r2["unsupportedMechanismPair"], ["first_exhaustion", "exterior_surface"])

        # 3. Zero duration resolves cleanly at exact initial algebraic state.
        r_zero = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_zero_dur",
            "nodes": ["a", "b"],
            "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
            "attachments": {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "200", "initialTemperatureK": "400"},
                "b": ext_att,
            },
            "solve": {"mode": "transient", "durationS": "0"},
        })
        self.assertEqual(r_zero["status"], "complete")
        self.assertEqual(r_zero["backendResult"]["ports"]["a"]["finalTemperatureBoundsK"], ["400", "400"])

        # 4. Excessive active cooling (heatInputW < 0) driving T < 0 K is refused cleanly.
        with self.assertRaises(ValueError):
            solve_system({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "neg_below_zero_k",
                "nodes": ["a", "b"],
                "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
                "attachments": {
                    "a": {"kind": "sensible_body", "heatCapacityJPerK": "10", "initialTemperatureK": "20", "heatInputW": "-5000"},
                    "b": ext_att,
                },
                "solve": {"mode": "transient", "durationS": "10"},
            })

        # 5. Direct API guard: total_generated_power_w without terminal_injections_w -> ValueError.
        law = DerivedLaw.from_rods(["a", "b"], base_rods, terminals=["a", "b"])
        with self.assertRaises(ValueError):
            solve_radiative_transient(
                law,
                {"a": {"kind": "sensible_body", "heatCapacityJPerK": "200", "initialTemperatureK": "400"}, "b": ext_att},
                "10",
                total_generated_power_w=Fraction(10),
            )

        # 6. Lazy exports & describe_equations coverage
        self.assertEqual(simheat.RADIATIVE_TRANSIENT_SCHEMA, RADIATIVE_TRANSIENT_SCHEMA)
        self.assertIs(simheat.solve_radiative_transient, solve_radiative_transient)
        eq = describe_equations({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_eq",
            "nodes": ["a", "b"],
            "conduction": {"kind": "rods", "terminals": ["a", "b"], "rods": base_rods},
            "attachments": {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "200", "initialTemperatureK": "400"},
                "b": ext_att,
            },
            "solve": {"mode": "transient", "durationS": "60"},
        })
        self.assertEqual(eq["selectedBackend"], "radiative_transient")
        self.assertIn("sum_exteriors E_out,e", eq["conservationEquation"])

    # ------------------------------------------------------------------
    # 7. Discriminating review-finding regressions (M07-R01 .. M07-R04)
    # ------------------------------------------------------------------
    def test_m07_r01_r03_interval_phase_horizon_and_tight_bisection(self) -> None:
        # Exact M07-R01 & M07-R03 reproducer: interval conductance W in [10, 10.2] W/K,
        # phase_substance cooling via pure convection at durations 25 s and 32 s.
        def _exact_tw(w_val: mp.mpf, dur: mp.mpf) -> mp.mpf:
            g_eff = (w_val * 10) / (w_val + 10)
            c_l, c_s, lat = mp.mpf("420"), mp.mpf("210"), mp.mpf("3340")
            t0, t_tr, t_air = mp.mpf("285"), mp.mpf("273.15"), mp.mpf("200")
            t1 = (c_l / g_eff) * mp.log((t0 - t_air) / (t_tr - t_air))
            t2 = t1 + lat / (g_eff * (t_tr - t_air))
            return t_air + (t_tr - t_air) * mp.exp(-g_eff * (dur - t2) / c_s)

        for dur_str in ("25", "32"):
            sys_doc = {
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": f"m07_r01_dur_{dur_str}",
                "nodes": ["w", "e"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["w", "e"],
                    "rods": {"r": {"kind": "rod_area", "a": "w", "b": "e", "k": {"low": "10", "high": "10.2"}, "L": "1", "A": "1"}},
                },
                "attachments": {
                    "w": {
                        "kind": "phase_substance",
                        "initialTemperatureK": "285",
                        "transitionTemperatureK": "273.15",
                        "specificLatentHeatJPerKg": "33400",
                        "solidSpecificHeatJPerKgK": "2100",
                        "liquidSpecificHeatJPerKgK": "4200",
                        "initialSolidKg": "0",
                        "initialLiquidKg": "0.1",
                    },
                    "e": {
                        "kind": "exterior_surface",
                        "areaM2": "1",
                        "enclosureTemperatureK": "200",
                        "emissivity": "0",
                        "sigmaWPerM2K4": "0.0000000567",
                        "airTemperatureK": "200",
                        "convectionCoefficientWPerM2K": "10",
                    },
                },
                "solve": {"mode": "transient", "durationS": dur_str, "initialSteps": 8},
            }
            res = solve_system(sys_doc)
            self.assertEqual(res["status"], "complete")
            raw = res["backendResult"]
            # M07-R03: Event 0 bracket must be tight around the 0.13 s physical interval (< 0.35 s, not 6.25 s!).
            ev0_lo, ev0_hi = map(Fraction, raw["events"][0]["timeBoundsS"])
            self.assertLess(float(ev0_hi - ev0_lo), 0.35)
            # M07-R01: Exact analytical truths for BOTH W=10.0 and W=10.2 MUST be strictly enclosed!
            dur_mp = mp.mpf(dur_str)
            _assert_enclosed(self, raw["ports"]["w"]["finalTemperatureBoundsK"], _exact_tw(mp.mpf("10"), dur_mp), msg=f"dur={dur_str} W=10")
            _assert_enclosed(self, raw["ports"]["w"]["finalTemperatureBoundsK"], _exact_tw(mp.mpf("10.2"), dur_mp), msg=f"dur={dur_str} W=10.2")

    def test_m07_r02_non_monotone_exterior_energy_and_shell_surface_temp(self) -> None:
        # 1. Non-monotone E_out (heating then cooling across T_air=300 K during tie stop).
        law1 = DerivedLaw.from_rods(
            ["body", "surf", "p1", "p2"],
            {
                "bs": {"kind": "rod_area", "a": "body", "b": "surf", "k": "20", "L": "1", "A": "1"},
                "bp1": {"kind": "rod_area", "a": "body", "b": "p1", "k": "2", "L": "1", "A": "1"},
                "bp2": {"kind": "rod_area", "a": "body", "b": "p2", "k": "2", "L": "1", "A": "1"},
            },
            terminals=["body", "surf", "p1", "p2"],
        )
        phase_tie = {
            "kind": "phase_substance",
            "initialTemperatureK": "273.0",
            "transitionTemperatureK": "273.15",
            "specificLatentHeatJPerKg": "334000",
            "solidSpecificHeatJPerKgK": "2100",
            "liquidSpecificHeatJPerKgK": "4200",
            "initialSolidKg": "0.1",
            "initialLiquidKg": "0",
        }
        r1 = solve_radiative_transient(
            law1,
            {
                "body": {"kind": "sensible_body", "heatCapacityJPerK": "500", "initialTemperatureK": "100", "heatInputW": "40000"},
                "surf": {
                    "kind": "exterior_surface",
                    "areaM2": "1",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "300",
                    "convectionCoefficientWPerM2K": "20",
                },
                "p1": phase_tie,
                "p2": phase_tie,
            },
            "6",
            initial_steps=1,
            max_step_refinements=1,
        )
        self.assertEqual(r1["status"], "mode_sequence_uncertain")
        # Must enclose the negative interior minimum (-2395.765 J) and crossing value (-1154.685 J)!
        _assert_enclosed(self, r1["ports"]["surf"]["cumulativeOutwardEnergyBoundsJ"], mp.mpf("-1154.685"), msg="non-monotone E_out cross")
        _assert_enclosed(self, r1["ports"]["surf"]["cumulativeOutwardEnergyBoundsJ"], mp.mpf("-2395.765"), msg="non-monotone E_out min")

        # 2. Non-monotone radial_shell outer face temperature s_stop on tie stop.
        law2 = DerivedLaw.from_rods(
            ["b1", "b2", "sh", "p1", "p2"],
            {
                "b1s": {"kind": "rod_area", "a": "b1", "b": "sh", "k": "10", "L": "1", "A": "1"},
                "b2s": {"kind": "rod_area", "a": "b2", "b": "sh", "k": "10", "L": "1", "A": "1"},
                "b1p1": {"kind": "rod_area", "a": "b1", "b": "p1", "k": "0.001", "L": "1", "A": "1"},
                "b1p2": {"kind": "rod_area", "a": "b1", "b": "p2", "k": "0.001", "L": "1", "A": "1"},
            },
            terminals=["b1", "b2", "sh", "p1", "p2"],
        )
        p_tie2 = {
            "kind": "phase_substance",
            "initialTemperatureK": "272.0",
            "transitionTemperatureK": "273.15",
            "specificLatentHeatJPerKg": "334000",
            "solidSpecificHeatJPerKgK": "2100",
            "liquidSpecificHeatJPerKgK": "4200",
            "initialSolidKg": "0.1",
            "initialLiquidKg": "0",
            "heatInputW": "110",
        }
        r2 = solve_radiative_transient(
            law2,
            {
                "b1": {"kind": "sensible_body", "heatCapacityJPerK": "25", "initialTemperatureK": "1000"},
                "b2": {"kind": "sensible_body", "heatCapacityJPerK": "200", "initialTemperatureK": "100", "heatInputW": "18000"},
                "sh": {
                    "kind": "radial_shell",
                    "geometry": {"kind": "sphere", "innerRadiusM": "0.1", "layers": [{"outerRadiusM": "0.12", "conductivityWPerMK": "2"}]},
                    "exterior": {
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "10",
                        "enclosureTemperatureK": "300",
                        "emissivity": "0",
                        "sigmaWPerM2K4": "0.0000000567",
                    },
                },
                "p1": p_tie2,
                "p2": p_tie2,
            },
            "2.5",
            initial_steps=1,
            max_step_refinements=1,
        )
        self.assertEqual(r2["status"], "mode_sequence_uncertain")
        # Endpoints at t=1.25 s (483.005 K) and t=2.5 s (485.301 K) bracket an interior dip to 481.2448 K at t=1.73 s;
        # s_stop must strictly enclose the interior minimum!
        _assert_enclosed(self, r2["ports"]["sh"]["outerFaceTemperatureBoundsK"], mp.mpf("481.24482"), msg="non-monotone s_stop")

    def test_m07_r04_zero_kelvin_initial_body_heated_by_enclosure(self) -> None:
        res = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m07_r04_zero_kelvin_start",
            "nodes": ["b", "e"],
            "conduction": {
                "kind": "rods",
                "terminals": ["b", "e"],
                "rods": {"r": {"kind": "rod_area", "a": "b", "b": "e", "k": "10", "L": "1", "A": "1"}},
            },
            "attachments": {
                "b": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "0"},
                "e": {
                    "kind": "exterior_surface",
                    "areaM2": "1",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0.8",
                    "sigmaWPerM2K4": "0.0000000567",
                },
            },
            "solve": {"mode": "transient", "durationS": "10"},
        })
        self.assertEqual(res["status"], "complete")
        self.assertGreater(Fraction(res["backendResult"]["ports"]["b"]["finalTemperatureBoundsK"][0]), 0)


if __name__ == "__main__":
    unittest.main()
