"""Milestone M08 tests: temperature-dependent conductivity k(T) via exact Kirchhoff potential."""
from __future__ import annotations

from fractions import Fraction
from itertools import product
import json
import threading
import unittest
from urllib.request import Request, urlopen

import mpmath as mp

import simheat
from simheat.kirchhoff import (
    KIRCHHOFF_STEADY_SCHEMA,
    KirchhoffEdge,
    KirchhoffRodModel,
    build_kirchhoff_model,
    solve_kirchhoff_steady,
)
from simheat.lesson_server import create_server
from simheat.system import THERMAL_SYSTEM_SCHEMA, describe_equations, solve_system
from tools.offline_provenance import OFFLINE_FLAG_KEYS

mp.mp.dps = 60


def _assert_enclosed(tc: unittest.TestCase, bounds_pair: list[str], truth: mp.mpf, *, msg: str = "") -> None:
    lo = Fraction(bounds_pair[0])
    hi = Fraction(bounds_pair[1])
    tc.assertLessEqual(lo, hi, f"inverted bounds {bounds_pair} ({msg})")
    lo_mp = mp.mpf(lo.numerator) / mp.mpf(lo.denominator)
    hi_mp = mp.mpf(hi.numerator) / mp.mpf(hi.denominator)
    tc.assertLessEqual(lo_mp, truth, f"truth {truth} below lo {lo_mp} ({msg})")
    tc.assertGreaterEqual(hi_mp, truth, f"truth {truth} above hi {hi_mp} ({msg})")


def _mp_psi(t: mp.mpf, alpha: mp.mpf, t_ref: mp.mpf) -> mp.mpf:
    u = t - t_ref
    return u + (alpha / 2) * u * u


def _mp_dpsi(t: mp.mpf, alpha: mp.mpf, t_ref: mp.mpf) -> mp.mpf:
    return mp.mpf(1) + alpha * (t - t_ref)


def _mp_newton(res_fn, jac_fn, x0: list[mp.mpf], *, iters: int = 50) -> list[mp.mpf]:
    x = list(x0)
    for _ in range(iters):
        r = res_fn(x)
        if max(abs(v) for v in r) < mp.mpf("1e-50"):
            return x
        j = mp.matrix(jac_fn(x))
        dx = mp.lu_solve(j, mp.matrix([-v for v in r]))
        x = [x[i] + dx[i] for i in range(len(x))]
    return x


class TestM08KirchhoffConductivity(unittest.TestCase):
    # ------------------------------------------------------------------
    # 1. Classic single-rod positive & negative alpha + midpoint probe
    # ------------------------------------------------------------------
    def test_single_rod_positive_and_negative_alpha_exact_kirchhoff_and_probe(self) -> None:
        ta, tb = mp.mpf("600"), mp.mpf("300")
        k0, length, area, t_ref = mp.mpf("50"), mp.mpf("1"), mp.mpf("0.02"), mp.mpf("300")
        g0 = k0 * area / length

        for alpha_str, expected_concavity in (("0.002", "above"), ("-0.002", "below")):
            alpha = mp.mpf(alpha_str)
            sys_doc = {
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": f"m08_single_rod_{alpha_str}",
                "nodes": ["hot", "cold"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["hot", "cold"],
                    "rods": {
                        "bar": {
                            "kind": "rod_area",
                            "a": "hot",
                            "b": "cold",
                            "k": "50",
                            "L": "1",
                            "A": "0.02",
                            "alphaPerK": alpha_str,
                            "referenceTemperatureK": "300",
                        }
                    },
                },
                "attachments": {
                    "hot": {"kind": "maintained", "temperatureK": "600"},
                    "cold": {"kind": "maintained", "temperatureK": "300"},
                },
                "solve": {"mode": "steady"},
            }
            res = solve_system(sys_doc, rod_probe=("bar", "0.5"))
            self.assertEqual(res["backend"], "kirchhoff")
            self.assertEqual(res["status"], "resolved")
            self.assertEqual(res["terminationReason"], "converged")
            for flag in OFFLINE_FLAG_KEYS:
                self.assertIs(res[flag], False)

            # Exact analytical Kirchhoff flux and midpoint temperature
            q_exact = g0 * (_mp_psi(ta, alpha, t_ref) - _mp_psi(tb, alpha, t_ref))
            psi_mid = (_mp_psi(ta, alpha, t_ref) + _mp_psi(tb, alpha, t_ref)) / 2
            t_mid_exact = t_ref + (mp.sqrt(1 + 2 * alpha * psi_mid) - 1) / alpha

            raw = res["backendResult"]
            _assert_enclosed(self, raw["ports"]["cold"]["inflowFromNetworkBoundsW"], q_exact, msg=f"Q alpha={alpha_str}")
            _assert_enclosed(self, raw["ports"]["hot"]["inflowFromNetworkBoundsW"], -q_exact, msg=f"-Q alpha={alpha_str}")
            bal_lo, bal_hi = map(Fraction, raw["globalEnergyBalanceBoundsW"])
            self.assertLessEqual(bal_lo, 0)
            self.assertGreaterEqual(bal_hi, 0)

            probe = res["kirchhoffSummary"]["probe"]
            _assert_enclosed(self, probe["temperatureBoundsK"], t_mid_exact, msg=f"T(0.5) alpha={alpha_str}")
            _assert_enclosed(self, probe["heatCurrentTowardBBoundsW"], q_exact, msg=f"Q(0.5) alpha={alpha_str}")
            t_mid_lo, t_mid_hi = map(Fraction, probe["temperatureBoundsK"])
            self.assertLess(float(t_mid_hi - t_mid_lo), 1e-20)
            if expected_concavity == "above":
                self.assertGreater(t_mid_lo, Fraction(450))
            else:
                self.assertLess(t_mid_hi, Fraction(450))

    # ------------------------------------------------------------------
    # 2. Heterogeneous 5-node bridge with internal junctions vs mpmath
    # ------------------------------------------------------------------
    def test_heterogeneous_bridge_with_internal_junctions_vs_mpmath_newton(self) -> None:
        sys_doc = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_hetero_bridge",
            "nodes": ["hot", "cold", "mid", "j1", "j2"],
            "conduction": {
                "kind": "rods",
                "terminals": ["hot", "cold", "mid"],
                "rods": {
                    "r1": {"kind": "rod_area", "a": "hot", "b": "j1", "k": "80", "L": "0.5", "A": "0.01", "alphaPerK": "0.002", "referenceTemperatureK": "300"},
                    "r2": {"kind": "rod_area", "a": "j1", "b": "cold", "k": "40", "L": "0.4", "A": "0.01", "alphaPerK": "-0.0015", "referenceTemperatureK": "300"},
                    "r3": {"kind": "rod_area", "a": "hot", "b": "j2", "k": "60", "L": "0.6", "A": "0.01", "alphaPerK": "0"},
                    "r4": {"kind": "rod_circular", "a": "j2", "b": "cold", "k": "100", "L": "0.5", "d": "0.1", "alphaPerK": "0.001", "referenceTemperatureK": "400"},
                    "r5": {"kind": "rod_area", "a": "j1", "b": "j2", "k": "50", "L": "0.25", "A": "0.01", "alphaPerK": "-0.001", "referenceTemperatureK": "500"},
                    "r6": {"kind": "rod_area", "a": "j2", "b": "mid", "k": "30", "L": "0.3", "A": "0.01", "alphaPerK": "0.003", "referenceTemperatureK": "350"},
                },
            },
            "attachments": {
                "hot": {"kind": "maintained", "temperatureK": "700"},
                "cold": {"kind": "maintained", "temperatureK": "300"},
                "mid": {"kind": "maintained", "temperatureK": "420"},
            },
            "solve": {"mode": "steady"},
        }
        res = solve_system(sys_doc)
        self.assertEqual(res["backend"], "kirchhoff")
        self.assertEqual(res["status"], "resolved")

        # 60-digit mpmath Newton oracle for (T_j1, T_j2)
        t_hot, t_cold, t_mid = mp.mpf("700"), mp.mpf("300"), mp.mpf("420")
        g1 = mp.mpf("80") * mp.mpf("0.01") / mp.mpf("0.5")
        g2 = mp.mpf("40") * mp.mpf("0.01") / mp.mpf("0.4")
        g3 = mp.mpf("60") * mp.mpf("0.01") / mp.mpf("0.6")
        g4 = mp.mpf("100") * (mp.pi * mp.mpf("0.1") ** 2 / 4) / mp.mpf("0.5")
        g5 = mp.mpf("50") * mp.mpf("0.01") / mp.mpf("0.25")
        g6 = mp.mpf("30") * mp.mpf("0.01") / mp.mpf("0.3")

        def res_fn(x: list[mp.mpf]) -> list[mp.mpf]:
            tj1, tj2 = x
            f1 = (
                g1 * (_mp_psi(tj1, mp.mpf("0.002"), mp.mpf("300")) - _mp_psi(t_hot, mp.mpf("0.002"), mp.mpf("300")))
                + g2 * (_mp_psi(tj1, mp.mpf("-0.0015"), mp.mpf("300")) - _mp_psi(t_cold, mp.mpf("-0.0015"), mp.mpf("300")))
                + g5 * (_mp_psi(tj1, mp.mpf("-0.001"), mp.mpf("500")) - _mp_psi(tj2, mp.mpf("-0.001"), mp.mpf("500")))
            )
            f2 = (
                g3 * (tj2 - t_hot)
                + g4 * (_mp_psi(tj2, mp.mpf("0.001"), mp.mpf("400")) - _mp_psi(t_cold, mp.mpf("0.001"), mp.mpf("400")))
                + g5 * (_mp_psi(tj2, mp.mpf("-0.001"), mp.mpf("500")) - _mp_psi(tj1, mp.mpf("-0.001"), mp.mpf("500")))
                + g6 * (_mp_psi(tj2, mp.mpf("0.003"), mp.mpf("350")) - _mp_psi(t_mid, mp.mpf("0.003"), mp.mpf("350")))
            )
            return [f1, f2]

        def jac_fn(x: list[mp.mpf]) -> list[list[mp.mpf]]:
            tj1, tj2 = x
            j11 = (
                g1 * _mp_dpsi(tj1, mp.mpf("0.002"), mp.mpf("300"))
                + g2 * _mp_dpsi(tj1, mp.mpf("-0.0015"), mp.mpf("300"))
                + g5 * _mp_dpsi(tj1, mp.mpf("-0.001"), mp.mpf("500"))
            )
            j12 = -g5 * _mp_dpsi(tj2, mp.mpf("-0.001"), mp.mpf("500"))
            j21 = -g5 * _mp_dpsi(tj1, mp.mpf("-0.001"), mp.mpf("500"))
            j22 = (
                g3
                + g4 * _mp_dpsi(tj2, mp.mpf("0.001"), mp.mpf("400"))
                + g5 * _mp_dpsi(tj2, mp.mpf("-0.001"), mp.mpf("500"))
                + g6 * _mp_dpsi(tj2, mp.mpf("0.003"), mp.mpf("350"))
            )
            return [[j11, j12], [j21, j22]]

        tj1_ex, tj2_ex = _mp_newton(res_fn, jac_fn, [mp.mpf("500"), mp.mpf("500")])
        nodes_t = res["kirchhoffSummary"]["nodeTemperatureBoundsK"]
        _assert_enclosed(self, nodes_t["j1"], tj1_ex, msg="T_j1")
        _assert_enclosed(self, nodes_t["j2"], tj2_ex, msg="T_j2")
        self.assertLess(float(Fraction(res["achievedWidths"]["maxTemperatureWidthK"])), 1e-18)

    # ------------------------------------------------------------------
    # 3. Coupled Kirchhoff rods + radiation + 2-layer Kirchhoff radial_shell + phase_bath
    # ------------------------------------------------------------------
    def test_coupled_kirchhoff_rods_radiation_radial_shell_and_phase_bath(self) -> None:
        sys_doc = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_coupled_full",
            "nodes": ["hot", "ice", "rad", "sh", "j"],
            "conduction": {
                "kind": "rods",
                "terminals": ["hot", "ice", "rad", "sh"],
                "rods": {
                    "hj": {"kind": "rod_area", "a": "hot", "b": "j", "k": "60", "L": "0.5", "A": "0.02", "alphaPerK": "0.001", "referenceTemperatureK": "400"},
                    "ji": {"kind": "rod_area", "a": "j", "b": "ice", "k": "20", "L": "0.5", "A": "0.01", "alphaPerK": "-0.0005", "referenceTemperatureK": "300"},
                    "jr": {"kind": "rod_area", "a": "j", "b": "rad", "k": "30", "L": "0.4", "A": "0.01", "alphaPerK": "0.002", "referenceTemperatureK": "300"},
                    "js": {"kind": "rod_area", "a": "j", "b": "sh", "k": "40", "L": "0.4", "A": "0.01", "alphaPerK": "0"},
                },
            },
            "attachments": {
                "hot": {"kind": "maintained", "temperatureK": "800"},
                "ice": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "initialSolidKg": "2",
                    "initialLiquidKg": "0.5",
                },
                "rad": {
                    "kind": "exterior_surface",
                    "areaM2": "0.25",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0.85",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "295",
                    "convectionCoefficientWPerM2K": "12",
                },
                "sh": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "sphere",
                        "innerRadiusM": "0.08",
                        "layers": [
                            {"outerRadiusM": "0.11", "conductivityWPerMK": "1.2", "alphaPerK": "0.0015", "referenceTemperatureK": "300"},
                            {"outerRadiusM": "0.15", "conductivityWPerMK": "0.6", "alphaPerK": "-0.0008", "referenceTemperatureK": "300"},
                        ],
                    },
                    "exterior": {
                        "enclosureTemperatureK": "300",
                        "emissivity": "0.7",
                        "sigmaWPerM2K4": "0.0000000567",
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "10",
                    },
                },
            },
            "solve": {"mode": "steady", "durationS": "3600"},
        }
        res = solve_system(sys_doc)
        self.assertEqual(res["backend"], "kirchhoff")
        self.assertEqual(res["status"], "coexisting")
        raw = res["backendResult"]

        # 60-digit mpmath 5-unknown Newton oracle: x = [T_j, T_rad, T_sh_in, T_sh_mid, T_sh_out]
        t_hot, t_ice = mp.mpf("800"), mp.mpf("273.15")
        g_hj = mp.mpf("60") * mp.mpf("0.02") / mp.mpf("0.5")
        g_ji = mp.mpf("20") * mp.mpf("0.01") / mp.mpf("0.5")
        g_jr = mp.mpf("30") * mp.mpf("0.01") / mp.mpf("0.4")
        g_js = mp.mpf("40") * mp.mpf("0.01") / mp.mpf("0.4")
        g_s1 = 4 * mp.pi * mp.mpf("1.2") / (1 / mp.mpf("0.08") - 1 / mp.mpf("0.11"))
        g_s2 = 4 * mp.pi * mp.mpf("0.6") / (1 / mp.mpf("0.11") - 1 / mp.mpf("0.15"))
        sig = mp.mpf("0.0000000567")
        a_rad = mp.mpf("0.25")
        a_sh = 4 * mp.pi * mp.mpf("0.15") ** 2

        def q_rad_ext(t: mp.mpf) -> mp.mpf:
            return a_rad * (mp.mpf("12") * (t - mp.mpf("295")) + mp.mpf("0.85") * sig * (t**4 - mp.mpf("300") ** 4))

        def dq_rad_ext(t: mp.mpf) -> mp.mpf:
            return a_rad * (mp.mpf("12") + 4 * mp.mpf("0.85") * sig * t**3)

        def q_sh_ext(t: mp.mpf) -> mp.mpf:
            return a_sh * (mp.mpf("10") * (t - mp.mpf("300")) + mp.mpf("0.7") * sig * (t**4 - mp.mpf("300") ** 4))

        def dq_sh_ext(t: mp.mpf) -> mp.mpf:
            return a_sh * (mp.mpf("10") + 4 * mp.mpf("0.7") * sig * t**3)

        def res_fn(x: list[mp.mpf]) -> list[mp.mpf]:
            tj, trad, tsin, tsmid, tsout = x
            f0 = (
                g_hj * (_mp_psi(tj, mp.mpf("0.001"), mp.mpf("400")) - _mp_psi(t_hot, mp.mpf("0.001"), mp.mpf("400")))
                + g_ji * (_mp_psi(tj, mp.mpf("-0.0005"), mp.mpf("300")) - _mp_psi(t_ice, mp.mpf("-0.0005"), mp.mpf("300")))
                + g_jr * (_mp_psi(tj, mp.mpf("0.002"), mp.mpf("300")) - _mp_psi(trad, mp.mpf("0.002"), mp.mpf("300")))
                + g_js * (tj - tsin)
            )
            f1 = g_jr * (_mp_psi(trad, mp.mpf("0.002"), mp.mpf("300")) - _mp_psi(tj, mp.mpf("0.002"), mp.mpf("300"))) + q_rad_ext(trad)
            f2 = g_js * (tsin - tj) + g_s1 * (_mp_psi(tsin, mp.mpf("0.0015"), mp.mpf("300")) - _mp_psi(tsmid, mp.mpf("0.0015"), mp.mpf("300")))
            f3 = (
                g_s1 * (_mp_psi(tsmid, mp.mpf("0.0015"), mp.mpf("300")) - _mp_psi(tsin, mp.mpf("0.0015"), mp.mpf("300")))
                + g_s2 * (_mp_psi(tsmid, mp.mpf("-0.0008"), mp.mpf("300")) - _mp_psi(tsout, mp.mpf("-0.0008"), mp.mpf("300")))
            )
            f4 = g_s2 * (_mp_psi(tsout, mp.mpf("-0.0008"), mp.mpf("300")) - _mp_psi(tsmid, mp.mpf("-0.0008"), mp.mpf("300"))) + q_sh_ext(tsout)
            return [f0, f1, f2, f3, f4]

        def jac_fn(x: list[mp.mpf]) -> list[list[mp.mpf]]:
            tj, trad, tsin, tsmid, tsout = x
            d_hj = g_hj * _mp_dpsi(tj, mp.mpf("0.001"), mp.mpf("400"))
            d_ji = g_ji * _mp_dpsi(tj, mp.mpf("-0.0005"), mp.mpf("300"))
            d_jr_j = g_jr * _mp_dpsi(tj, mp.mpf("0.002"), mp.mpf("300"))
            d_jr_r = g_jr * _mp_dpsi(trad, mp.mpf("0.002"), mp.mpf("300"))
            d_s1_i = g_s1 * _mp_dpsi(tsin, mp.mpf("0.0015"), mp.mpf("300"))
            d_s1_m = g_s1 * _mp_dpsi(tsmid, mp.mpf("0.0015"), mp.mpf("300"))
            d_s2_m = g_s2 * _mp_dpsi(tsmid, mp.mpf("-0.0008"), mp.mpf("300"))
            d_s2_o = g_s2 * _mp_dpsi(tsout, mp.mpf("-0.0008"), mp.mpf("300"))
            return [
                [d_hj + d_ji + d_jr_j + g_js, -d_jr_r, -g_js, mp.mpf(0), mp.mpf(0)],
                [-d_jr_j, d_jr_r + dq_rad_ext(trad), mp.mpf(0), mp.mpf(0), mp.mpf(0)],
                [-g_js, mp.mpf(0), g_js + d_s1_i, -d_s1_m, mp.mpf(0)],
                [mp.mpf(0), mp.mpf(0), -d_s1_i, d_s1_m + d_s2_m, -d_s2_o],
                [mp.mpf(0), mp.mpf(0), mp.mpf(0), -d_s2_m, d_s2_o + dq_sh_ext(tsout)],
            ]

        sol = _mp_newton(res_fn, jac_fn, [mp.mpf("500")] * 5)
        tj_ex, trad_ex, tsin_ex, tsmid_ex, tsout_ex = sol

        _assert_enclosed(self, res["kirchhoffSummary"]["nodeTemperatureBoundsK"]["j"], tj_ex, msg="T_j")
        _assert_enclosed(self, raw["ports"]["rad"]["temperatureBoundsK"], trad_ex, msg="T_rad")
        _assert_enclosed(self, raw["ports"]["sh"]["innerFaceTemperatureBoundsK"], tsin_ex, msg="T_sh_in")
        _assert_enclosed(self, raw["ports"]["sh"]["surfaceProfile"][1]["temperatureBoundsK"], tsmid_ex, msg="T_sh_mid")
        _assert_enclosed(self, raw["ports"]["sh"]["outerFaceTemperatureBoundsK"], tsout_ex, msg="T_sh_out")
        q_ice_ex = g_ji * (_mp_psi(tj_ex, mp.mpf("-0.0005"), mp.mpf("300")) - _mp_psi(t_ice, mp.mpf("-0.0005"), mp.mpf("300")))
        _assert_enclosed(self, raw["ports"]["ice"]["inflowFromNetworkBoundsW"], q_ice_ex, msg="Q_ice")
        _assert_enclosed(self, raw["ports"]["ice"]["convertedMassBoundsKg"], q_ice_ex * mp.mpf("3600") / mp.mpf("334000"), msg="melted_kg")
        self.assertLess(float(Fraction(res["achievedWidths"]["maxTemperatureWidthK"])), 1e-18)

    # ------------------------------------------------------------------
    # 4. Kirchhoff rod with uniform generatedPowerW, peak, and rod_probe
    # ------------------------------------------------------------------
    def test_kirchhoff_heated_rod_generation_peak_and_probe_vs_mpmath_bvp(self) -> None:
        sys_doc = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_heated_composite",
            "nodes": ["a", "j", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {
                    "r1": {
                        "kind": "rod_area", "a": "a", "b": "j", "k": "40", "L": "1", "A": "0.5",
                        "alphaPerK": "-0.001", "referenceTemperatureK": "300", "generatedPowerW": "2500",
                    },
                    "r2": {
                        "kind": "rod_area", "a": "j", "b": "b", "k": "30", "L": "1", "A": "0.5",
                        "alphaPerK": "0.002", "referenceTemperatureK": "300", "generatedPowerW": "1000",
                    },
                },
            },
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "400"},
                "b": {"kind": "maintained", "temperatureK": "350"},
            },
            "solve": {"mode": "steady"},
        }
        res = solve_system(sys_doc, rod_probe=("r1", "0.35"))
        self.assertEqual(res["backend"], "kirchhoff")
        self.assertEqual(res["status"], "resolved")

        # 60-digit exact Kirchhoff BVP oracle
        ta, tb = mp.mpf("400"), mp.mpf("350")
        g1, a1, p1 = mp.mpf("20"), mp.mpf("-0.001"), mp.mpf("2500")
        g2, a2, p2 = mp.mpf("15"), mp.mpf("0.002"), mp.mpf("1000")
        tref = mp.mpf("300")

        tj_ex = _mp_newton(
            lambda x: [
                g1 * (_mp_psi(x[0], a1, tref) - _mp_psi(ta, a1, tref)) - p1 / 2
                + g2 * (_mp_psi(x[0], a2, tref) - _mp_psi(tb, a2, tref)) - p2 / 2
            ],
            lambda x: [[g1 * _mp_dpsi(x[0], a1, tref) + g2 * _mp_dpsi(x[0], a2, tref)]],
            [mp.mpf("500")],
        )[0]

        psi_a = _mp_psi(ta, a1, tref)
        psi_j1 = _mp_psi(tj_ex, a1, tref)
        c1 = p1 / (2 * g1)
        x_pk1 = max(mp.mpf(0), min(mp.mpf(1), (1 + (psi_j1 - psi_a) / c1) / 2))
        psi_pk1 = (1 - x_pk1) * psi_a + x_pk1 * psi_j1 + c1 * x_pk1 * (1 - x_pk1)
        t_pk1 = tref + (mp.sqrt(1 + 2 * a1 * psi_pk1) - 1) / a1

        xp = mp.mpf("0.35")
        psi_pr = (1 - xp) * psi_a + xp * psi_j1 + c1 * xp * (1 - xp)
        t_pr = tref + (mp.sqrt(1 + 2 * a1 * psi_pr) - 1) / a1
        q_pr = g1 * (psi_a - psi_j1) + p1 * (xp - mp.mpf("0.5"))

        ks = res["kirchhoffSummary"]
        _assert_enclosed(self, ks["nodeTemperatureBoundsK"]["j"], tj_ex, msg="T_j heated")
        _assert_enclosed(self, ks["rods"]["r1"]["peakTemperatureBoundsK"], t_pk1, msg="T_peak r1")
        _assert_enclosed(self, ks["rods"]["r1"]["peakPositionFractionFromABounds"], x_pk1, msg="x_peak r1")
        _assert_enclosed(self, ks["probe"]["temperatureBoundsK"], t_pr, msg="probe T(0.35)")
        _assert_enclosed(self, ks["probe"]["heatCurrentTowardBBoundsW"], q_pr, msg="probe Q(0.35)")

        # Global conservation: sum Q_in_maintained = P_1 + P_2 = 3500 W
        qa_lo, qa_hi = map(Fraction, res["backendResult"]["ports"]["a"]["inflowFromNetworkBoundsW"])
        qb_lo, qb_hi = map(Fraction, res["backendResult"]["ports"]["b"]["inflowFromNetworkBoundsW"])
        self.assertLessEqual(qa_lo + qb_lo, Fraction(3500))
        self.assertGreaterEqual(qa_hi + qb_hi, Fraction(3500))

    # ------------------------------------------------------------------
    # 5. Interval parameters (k, L, A, d) + generation enclose all 32 extreme corners
    # ------------------------------------------------------------------
    def test_interval_parameters_and_rod_circular_enclose_all_extreme_corners(self) -> None:
        sys_doc = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_interval_corners",
            "nodes": ["hot", "rad", "cold", "j"],
            "conduction": {
                "kind": "rods",
                "terminals": ["hot", "rad", "cold"],
                "rods": {
                    "r1": {
                        "kind": "rod_area", "a": "hot", "b": "j",
                        "k": {"low": "48", "high": "52"}, "L": {"low": "0.49", "high": "0.51"}, "A": "0.02",
                        "alphaPerK": "0.0015", "referenceTemperatureK": "300", "generatedPowerW": "400",
                    },
                    "r2": {
                        "kind": "rod_circular", "a": "j", "b": "rad",
                        "k": {"low": "38", "high": "42"}, "L": "0.5", "d": {"low": "0.095", "high": "0.105"},
                        "alphaPerK": "-0.001", "referenceTemperatureK": "300",
                    },
                    "r3": {
                        "kind": "rod_area", "a": "j", "b": "cold",
                        "k": "30", "L": "0.5", "A": {"low": "0.019", "high": "0.021"},
                        "alphaPerK": "0.001", "referenceTemperatureK": "350",
                    },
                },
            },
            "attachments": {
                "hot": {"kind": "maintained", "temperatureK": "650"},
                "cold": {"kind": "maintained", "temperatureK": "300"},
                "rad": {
                    "kind": "exterior_surface",
                    "areaM2": "0.5",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0.8",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "300",
                    "convectionCoefficientWPerM2K": "15",
                },
            },
            "solve": {"mode": "steady"},
        }
        res = solve_system(sys_doc)
        self.assertEqual(res["backend"], "kirchhoff")
        self.assertEqual(res["status"], "resolved")
        raw = res["backendResult"]
        ks = res["kirchhoffSummary"]

        # Independently solve all 2^5 = 32 extreme parameter corners via 60-digit mpmath Newton!
        sig = mp.mpf("0.0000000567")
        t_hot, t_cold = mp.mpf("650"), mp.mpf("300")
        for k1, l1, k2, d2, a3 in product(
            (mp.mpf("48"), mp.mpf("52")),
            (mp.mpf("0.49"), mp.mpf("0.51")),
            (mp.mpf("38"), mp.mpf("42")),
            (mp.mpf("0.095"), mp.mpf("0.105")),
            (mp.mpf("0.019"), mp.mpf("0.021")),
        ):
            g1 = k1 * mp.mpf("0.02") / l1
            g2 = k2 * (mp.pi * d2 * d2 / 4) / mp.mpf("0.5")
            g3 = mp.mpf("30") * a3 / mp.mpf("0.5")

            def _res(x: list[mp.mpf]) -> list[mp.mpf]:
                tj, tr = x
                f0 = (
                    g1 * (_mp_psi(tj, mp.mpf("0.0015"), mp.mpf("300")) - _mp_psi(t_hot, mp.mpf("0.0015"), mp.mpf("300"))) - mp.mpf("200")
                    + g2 * (_mp_psi(tj, mp.mpf("-0.001"), mp.mpf("300")) - _mp_psi(tr, mp.mpf("-0.001"), mp.mpf("300")))
                    + g3 * (_mp_psi(tj, mp.mpf("0.001"), mp.mpf("350")) - _mp_psi(t_cold, mp.mpf("0.001"), mp.mpf("350")))
                )
                f1 = (
                    g2 * (_mp_psi(tr, mp.mpf("-0.001"), mp.mpf("300")) - _mp_psi(tj, mp.mpf("-0.001"), mp.mpf("300")))
                    + mp.mpf("0.5") * (mp.mpf("15") * (tr - 300) + mp.mpf("0.8") * sig * (tr**4 - mp.mpf("300") ** 4))
                )
                return [f0, f1]

            def _jac(x: list[mp.mpf]) -> list[list[mp.mpf]]:
                tj, tr = x
                d1 = g1 * _mp_dpsi(tj, mp.mpf("0.0015"), mp.mpf("300"))
                d2j = g2 * _mp_dpsi(tj, mp.mpf("-0.001"), mp.mpf("300"))
                d2r = g2 * _mp_dpsi(tr, mp.mpf("-0.001"), mp.mpf("300"))
                d3 = g3 * _mp_dpsi(tj, mp.mpf("0.001"), mp.mpf("350"))
                dq = mp.mpf("0.5") * (mp.mpf("15") + 4 * mp.mpf("0.8") * sig * tr**3)
                return [[d1 + d2j + d3, -d2r], [-d2j, d2r + dq]]

            tj_c, tr_c = _mp_newton(_res, _jac, [mp.mpf("500"), mp.mpf("400")])
            _assert_enclosed(self, ks["nodeTemperatureBoundsK"]["j"], tj_c, msg="corner T_j")
            _assert_enclosed(self, raw["ports"]["rad"]["temperatureBoundsK"], tr_c, msg="corner T_rad")

            # Also check heated rod r1 interior peak encloses this corner!
            pa = _mp_psi(t_hot, mp.mpf("0.0015"), mp.mpf("300"))
            pj = _mp_psi(tj_c, mp.mpf("0.0015"), mp.mpf("300"))
            c1 = mp.mpf("400") / (2 * g1)
            xp = max(mp.mpf(0), min(mp.mpf(1), (1 + (pj - pa) / c1) / 2))
            psip = (1 - xp) * pa + xp * pj + c1 * xp * (1 - xp)
            tpk = mp.mpf("300") + (mp.sqrt(1 + 2 * mp.mpf("0.0015") * psip) - 1) / mp.mpf("0.0015")
            _assert_enclosed(self, ks["rods"]["r1"]["peakTemperatureBoundsK"], tpk, msg="corner r1 peak")

    # ------------------------------------------------------------------
    # 6. Constant-k joined DerivedLaw composed with Kirchhoff cylindrical radial_shell
    # ------------------------------------------------------------------
    def test_joined_derived_law_composed_with_kirchhoff_cylindrical_radial_shell(self) -> None:
        sys_doc = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_join_plus_kirchhoff_cyl",
            "conduction": {
                "kind": "join",
                "left": {
                    "kind": "rods",
                    "nodes": ["src", "mid"],
                    "terminals": ["src", "mid"],
                    "rods": {"l1": {"kind": "rod_area", "a": "src", "b": "mid", "k": "50", "L": "0.5", "A": "0.1"}},
                },
                "right": {
                    "kind": "rods",
                    "nodes": ["mid", "pipe"],
                    "terminals": ["mid", "pipe"],
                    "rods": {"r1": {"kind": "rod_area", "a": "mid", "b": "pipe", "k": "50", "L": "0.5", "A": "0.1"}},
                },
                "contacts": [{"leftPort": "mid", "rightPort": "mid"}],
            },
            "attachments": {
                "left.src": {"kind": "maintained", "temperatureK": "700"},
                "right.pipe": {
                    "kind": "radial_shell",
                    "geometry": {
                        "kind": "cylinder",
                        "innerRadiusM": "0.05",
                        "cylinderLengthM": "1.0",
                        "layers": [
                            {"outerRadiusM": "0.08", "conductivityWPerMK": "0.5", "alphaPerK": "0.002", "referenceTemperatureK": "300"},
                            {"outerRadiusM": "0.10", "conductivityWPerMK": "0.3"},
                        ],
                    },
                    "exterior": {
                        "enclosureTemperatureK": "300",
                        "emissivity": "0.6",
                        "sigmaWPerM2K4": "0.0000000567",
                        "airTemperatureK": "300",
                        "convectionCoefficientWPerM2K": "12",
                    },
                },
            },
            "solve": {"mode": "steady"},
        }
        res = solve_system(sys_doc)
        self.assertEqual(res["backend"], "kirchhoff")
        self.assertEqual(res["status"], "resolved")
        self.assertIsNotNone(res["derivedLaw"]["contentSha256"])

        # 60-digit mpmath cylindrical Kirchhoff oracle: g_net = 5 W/K (two 10 W/K rods in series)
        g_net = mp.mpf("5")
        g_l1 = 2 * mp.pi * mp.mpf("1.0") * mp.mpf("0.5") / mp.log(mp.mpf("0.08") / mp.mpf("0.05"))
        g_l2 = 2 * mp.pi * mp.mpf("1.0") * mp.mpf("0.3") / mp.log(mp.mpf("0.10") / mp.mpf("0.08"))
        a_out = 2 * mp.pi * mp.mpf("0.10") * mp.mpf("1.0")
        sig = mp.mpf("0.0000000567")

        def _res(x: list[mp.mpf]) -> list[mp.mpf]:
            tin, tmid, tout = x
            f0 = g_net * (tin - mp.mpf("700")) + g_l1 * (_mp_psi(tin, mp.mpf("0.002"), mp.mpf("300")) - _mp_psi(tmid, mp.mpf("0.002"), mp.mpf("300")))
            f1 = g_l1 * (_mp_psi(tmid, mp.mpf("0.002"), mp.mpf("300")) - _mp_psi(tin, mp.mpf("0.002"), mp.mpf("300"))) + g_l2 * (tmid - tout)
            f2 = g_l2 * (tout - tmid) + a_out * (mp.mpf("12") * (tout - 300) + mp.mpf("0.6") * sig * (tout**4 - mp.mpf("300") ** 4))
            return [f0, f1, f2]

        def _jac(x: list[mp.mpf]) -> list[list[mp.mpf]]:
            tin, tmid, tout = x
            d1i = g_l1 * _mp_dpsi(tin, mp.mpf("0.002"), mp.mpf("300"))
            d1m = g_l1 * _mp_dpsi(tmid, mp.mpf("0.002"), mp.mpf("300"))
            dq = a_out * (mp.mpf("12") + 4 * mp.mpf("0.6") * sig * tout**3)
            return [
                [g_net + d1i, -d1m, mp.mpf(0)],
                [-d1i, d1m + g_l2, -g_l2],
                [mp.mpf(0), -g_l2, g_l2 + dq],
            ]

        tin_ex, tmid_ex, tout_ex = _mp_newton(_res, _jac, [mp.mpf("600"), mp.mpf("500"), mp.mpf("400")])
        sh_out = res["backendResult"]["ports"]["right.pipe"]
        _assert_enclosed(self, sh_out["innerFaceTemperatureBoundsK"], tin_ex, msg="cyl T_in")
        _assert_enclosed(self, sh_out["surfaceProfile"][1]["temperatureBoundsK"], tmid_ex, msg="cyl T_mid")
        _assert_enclosed(self, sh_out["outerFaceTemperatureBoundsK"], tout_ex, msg="cyl T_out")
        self.assertLess(float(Fraction(res["achievedWidths"]["maxTemperatureWidthK"])), 1e-18)

    # ------------------------------------------------------------------
    # 7. Negative / refusal controls (nonpositive k(T), missing T_ref, transient, join)
    # ------------------------------------------------------------------
    def test_negative_controls_nonpositive_conductivity_and_refusals(self) -> None:
        # 7a. Fixed boundary hits k(T) = 0 -> ValueError
        with self.assertRaisesRegex(ValueError, "positive thermal conductivity"):
            solve_system({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "m08_neg_k_boundary",
                "nodes": ["a", "b"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["a", "b"],
                    "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1", "alphaPerK": "-0.005", "referenceTemperatureK": "300"}},
                },
                "attachments": {
                    "a": {"kind": "maintained", "temperatureK": "500"},
                    "b": {"kind": "maintained", "temperatureK": "300"},
                },
                "solve": {"mode": "steady"},
            })

        # 7b. Heated rod with negative alpha: both ends have k > 0, but interior parabolic peak crosses k <= 0 -> ValueError!
        with self.assertRaisesRegex(ValueError, "nonpositive"):
            solve_system({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "m08_neg_k_peak",
                "nodes": ["a", "b"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["a", "b"],
                    "rods": {
                        "r": {
                            "kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1",
                            "alphaPerK": "-0.005", "referenceTemperatureK": "300", "generatedPowerW": "10000",
                        }
                    },
                },
                "attachments": {
                    "a": {"kind": "maintained", "temperatureK": "350"},
                    "b": {"kind": "maintained", "temperatureK": "350"},
                },
                "solve": {"mode": "steady"},
            })

        # 7c. Positive alpha with cold boundary below T_ref - 1/alpha -> ValueError
        with self.assertRaisesRegex(ValueError, "positive thermal conductivity"):
            solve_system({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "m08_pos_alpha_cold_k_neg",
                "nodes": ["a", "b"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["a", "b"],
                    "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1", "alphaPerK": "0.01", "referenceTemperatureK": "300"}},
                },
                "attachments": {
                    "a": {"kind": "maintained", "temperatureK": "400"},
                    "b": {"kind": "maintained", "temperatureK": "150"},
                },
                "solve": {"mode": "steady"},
            })

        # 7d. Missing referenceTemperatureK when alphaPerK != 0 (rod and radial_shell)
        with self.assertRaisesRegex(ValueError, "referenceTemperatureK"):
            solve_system({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "m08_missing_tref_rod",
                "nodes": ["a", "b"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["a", "b"],
                    "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1", "alphaPerK": "0.001"}},
                },
                "attachments": {
                    "a": {"kind": "maintained", "temperatureK": "400"},
                    "b": {"kind": "maintained", "temperatureK": "300"},
                },
                "solve": {"mode": "steady"},
            })

        with self.assertRaisesRegex(ValueError, "referenceTemperatureK"):
            solve_system({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "m08_missing_tref_shell",
                "nodes": ["a", "b"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["a", "b"],
                    "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1"}},
                },
                "attachments": {
                    "a": {"kind": "maintained", "temperatureK": "400"},
                    "b": {
                        "kind": "radial_shell",
                        "geometry": {
                            "kind": "sphere",
                            "innerRadiusM": "0.1",
                            "layers": [{"outerRadiusM": "0.2", "conductivityWPerMK": "1", "alphaPerK": "0.002"}],
                        },
                        "exterior": {"enclosureTemperatureK": "300", "emissivity": "0.5", "sigmaWPerM2K4": "0.0000000567"},
                    },
                },
                "solve": {"mode": "steady"},
            })

        # 7e. alphaPerK inside conduction(join) refused
        with self.assertRaisesRegex(ValueError, "conduction.join"):
            solve_system({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "m08_alpha_in_join",
                "conduction": {
                    "kind": "join",
                    "left": {
                        "kind": "rods",
                        "nodes": ["a", "c"],
                        "terminals": ["a", "c"],
                        "rods": {"r1": {"kind": "rod_area", "a": "a", "b": "c", "k": "10", "L": "1", "A": "1", "alphaPerK": "0.001", "referenceTemperatureK": "300"}},
                    },
                    "right": {
                        "kind": "rods",
                        "nodes": ["c", "b"],
                        "terminals": ["c", "b"],
                        "rods": {"r2": {"kind": "rod_area", "a": "c", "b": "b", "k": "10", "L": "1", "A": "1"}},
                    },
                    "contacts": [{"leftPort": "c", "rightPort": "c"}],
                },
                "attachments": {
                    "left.a": {"kind": "maintained", "temperatureK": "400"},
                    "right.b": {"kind": "maintained", "temperatureK": "300"},
                },
                "solve": {"mode": "steady"},
            })

        # 7f. Transient mode with temperature-dependent conductivity -> structured unsupported_regime
        tr_unsup = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_transient_unsup",
            "nodes": ["a", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1", "alphaPerK": "0.001", "referenceTemperatureK": "300"}},
            },
            "attachments": {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "400"},
                "b": {"kind": "maintained", "temperatureK": "300"},
            },
            "solve": {"mode": "transient", "durationS": "10"},
        })
        self.assertEqual(tr_unsup["status"], "unsupported_regime")
        self.assertEqual(tr_unsup["unsupportedMechanismPair"], ["transient_mode", "temperature_dependent_conductivity"])

        # 7g. Steady sensible_body with alphaPerK -> structured unsupported_regime
        st_unsup = solve_system({
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_steady_body_unsup",
            "nodes": ["a", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1", "alphaPerK": "0.001", "referenceTemperatureK": "300"}},
            },
            "attachments": {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "400"},
                "b": {"kind": "maintained", "temperatureK": "300"},
            },
            "solve": {"mode": "steady"},
        })
        self.assertEqual(st_unsup["status"], "unsupported_regime")
        self.assertEqual(st_unsup["unsupportedMechanismPair"], ["steady_mode", "sensible_body"])

        # 7h. Unanchored Kirchhoff network (adiabatic exteriors only) -> ValueError
        with self.assertRaisesRegex(ValueError, "anchor"):
            solve_system({
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "m08_unanchored",
                "nodes": ["a", "b"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["a", "b"],
                    "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1", "alphaPerK": "0.001", "referenceTemperatureK": "300"}},
                },
                "attachments": {
                    "a": {"kind": "exterior_surface", "areaM2": "1", "enclosureTemperatureK": "300", "emissivity": "0", "sigmaWPerM2K4": "0.0000000567"},
                    "b": {"kind": "exterior_surface", "areaM2": "1", "enclosureTemperatureK": "300", "emissivity": "0", "sigmaWPerM2K4": "0.0000000567"},
                },
                "solve": {"mode": "steady"},
            })

    # ------------------------------------------------------------------
    # 8. Equations, exports, alpha=0 fallback, and live HTTP loopback
    # ------------------------------------------------------------------
    def test_equations_exports_zero_alpha_fallback_and_live_http_loopback(self) -> None:
        self.assertIs(simheat.KIRCHHOFF_STEADY_SCHEMA, KIRCHHOFF_STEADY_SCHEMA)
        self.assertIs(simheat.KirchhoffEdge, KirchhoffEdge)
        self.assertIs(simheat.KirchhoffRodModel, KirchhoffRodModel)
        self.assertIs(simheat.build_kirchhoff_model, build_kirchhoff_model)
        self.assertIs(simheat.solve_kirchhoff_steady, solve_kirchhoff_steady)

        # Explicit alphaPerK="0" routes cleanly to existing multiport backend (exact_linear on pure convection)
        zero_doc = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_zero_alpha",
            "nodes": ["a", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "10", "L": "1", "A": "1", "alphaPerK": "0", "referenceTemperatureK": "300"}},
            },
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "400"},
                "b": {
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
        r0 = solve_system(zero_doc)
        self.assertEqual(r0["backend"], "multiport")
        self.assertEqual(r0["terminationReason"], "exact_linear")

        # Nonzero alphaPerK equations check
        k_doc = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "m08_eq_http",
            "nodes": ["a", "b"],
            "conduction": {
                "kind": "rods",
                "terminals": ["a", "b"],
                "rods": {"r": {"kind": "rod_area", "a": "a", "b": "b", "k": "25", "L": "1", "A": "0.1", "alphaPerK": "0.002", "referenceTemperatureK": "300"}},
            },
            "attachments": {
                "a": {"kind": "maintained", "temperatureK": "500"},
                "b": {
                    "kind": "exterior_surface",
                    "areaM2": "0.2",
                    "enclosureTemperatureK": "300",
                    "emissivity": "0.8",
                    "sigmaWPerM2K4": "0.0000000567",
                    "airTemperatureK": "300",
                    "convectionCoefficientWPerM2K": "10",
                },
            },
            "solve": {"mode": "steady"},
        }
        eq = describe_equations(k_doc)
        self.assertEqual(eq["selectedBackend"], "kirchhoff")
        self.assertIsNone(eq["derivedLawSha256"])
        self.assertTrue(eq["conductionSummary"]["nonlinearConductivity"])
        self.assertIn("psi_r(T)", eq["equationsText"])

        # Live loopback HTTP POST /api/solve check
        server = create_server(0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            req = Request(
                f"http://127.0.0.1:{port}/api/solve",
                data=json.dumps(k_doc).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=15) as resp:
                self.assertEqual(resp.status, 200)
                payload = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["result"]["backend"], "kirchhoff")
            self.assertEqual(payload["result"]["status"], "resolved")
            for flag in OFFLINE_FLAG_KEYS:
                self.assertIs(payload[flag], False)
                self.assertIs(payload["result"][flag], False)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
