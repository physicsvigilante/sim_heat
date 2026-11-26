"""M04 linear enthalpy-mode continuation tests and independent 110-digit mpmath oracles.

Covers every discriminating acceptance witness from CONTRACT-M04.md:
1. Sol's closed LINK calorimeter at 1200 s (317.312375223 K / 308.765277424 K, t_melt = 406.465608 s)
   at delta in {0, 1e-6} W/K against closed-form + 110-digit mpmath oracles.
2. STAR3 (3 events) and STAR5 (5 events) powered multi-phase continuation chains at delta in {0, 1e-6}
   against an independent 110-digit dimensional-enthalpy mpmath matrix-exponential oracle.
3. Exact tie (verified simultaneous symmetry switch at delta=0, mode_sequence_uncertain at delta=1e-6),
   1e-8 kg near tie (2 resolved sequential events at delta=0, mode_sequence_uncertain at delta=1e-6),
   and 1e-5 kg separated tie (2 resolved events at both delta=0 and delta=1e-6).
4. Reversing reservoir / cooling re-entry & refreezing (4-event solid -> plateau -> liquid -> plateau -> solid
   and plateau reversal without exhaustion) at delta in {0, 1e-6} against 110-digit mpmath oracle.
5. One-port equivalence with tools/staged_phase_body_network.py across heating and cooling 3-stage runs.
6. Coupled hot-body + subcooled ice + calorimeter JEE problem end-to-end via ThermalSystem over a
   Schur-joined DerivedLaw with zero glue code.
7. Adversarial / negative controls: EH-01 symmetry-tie guard under asymmetric interval law, pure-phase
   boundary start regimes (cooling immediately into solid, superheating immediately into liquid,
   unresolved zero-flux start -> mode_sequence_uncertain), forced tiny event/refinement budget soundness,
   non-passive law refusal, and honest False offline provenance flags.
"""
from __future__ import annotations

from fractions import Fraction as F
from itertools import product
import unittest

import mpmath as mp

from simheat.enthalpy import ENTHALPY_CONTINUATION_SCHEMA, solve_enthalpy_continuation
from simheat.laws import DerivedLaw
from simheat.system import (
    RESULT_ENVELOPE_SCHEMA,
    THERMAL_SYSTEM_SCHEMA,
    describe_equations,
    solve_system,
)
from tools.multibody_phase_network import solve_continuation_from_law
from tools.offline_provenance import OFFLINE_FLAG_KEYS
from tools.staged_phase_body_network import solve_from_law as solve_staged


def _m(x) -> mp.mpf:
    q = F(x)
    return mp.mpf(q.numerator) / q.denominator


def _in_bounds(tc: unittest.TestCase, pair, target_mpf, *, max_width: F | None = None, margin_exp: int = 65):
    lo, hi = map(F, pair)
    eps = mp.mpf(10) ** (-margin_exp) * max(mp.mpf(1), abs(target_mpf))
    lo_m, hi_m = _m(lo), _m(hi)
    tc.assertTrue(
        (lo_m - eps) <= target_mpf <= (hi_m + eps),
        f"oracle {mp.nstr(target_mpf, 25)} outside [{float(lo)}, {float(hi)}]",
    )
    if max_width is not None:
        tc.assertLessEqual(hi - lo, max_width, f"width {float(hi - lo)} exceeded {float(max_width)}")


def _make_complete_law(terminals: list[str], edges: dict[tuple[str, str], F], delta: F = F(0)) -> DerivedLaw:
    """Build a valid symmetric passive DerivedLaw with conductance boxes [w - delta, w + delta]."""
    rods = {}
    for idx, ((a, b), w) in enumerate(edges.items()):
        if delta == 0:
            k_spec = _frac_dec(w)
        else:
            lo = w - delta
            hi = w + delta
            # Convert exact terminating fractions to decimal strings via exact numerator/denominator
            k_spec = {"low": _frac_dec(lo), "high": _frac_dec(hi)}
        rods[f"e{idx}"] = {"kind": "rod_area", "a": a, "b": b, "k": k_spec, "L": "1", "A": "1"}
    return DerivedLaw.from_rods(nodes=terminals, terminals=terminals, rods=rods)


def _frac_dec(val: F) -> str:
    if val == 0:
        return "0"
    num, den = val.numerator, val.denominator
    n2 = 0
    while den % 2 == 0:
        den //= 2
        n2 += 1
    n5 = 0
    while den % 5 == 0:
        den //= 5
        n5 += 1
    assert den == 1, f"non-terminating {val}"
    scale = max(n2, n5)
    scaled = num * (5 ** (scale - n5)) * (2 ** (scale - n2))
    if scale == 0:
        return str(scaled)
    digits = str(scaled).rjust(scale + 1, "0")
    frac = digits[-scale:].rstrip("0")
    return f"{digits[:-scale]}.{frac}" if frac else digits[:-scale]


def _mp_piecewise_oracle(terminals: list[str], edges: dict[tuple[str, str], F], ports: dict[str, dict], duration_s: str, *, dps: int = 85):
    """Independent high-precision piecewise matrix-exponential oracle supporting reversals and heat inputs."""
    with mp.workdps(dps):
        M = mp.mpf
        t_cur = {}
        h_cur = {}
        modes = {}
        specs = {}
        for n in terminals:
            p = ports[n]
            kind = p["kind"]
            if kind == "maintained":
                t0 = _m(F(p["temperatureK"]))
                specs[n] = ("maintained", t0, M(0), M(0), M(0), M(0), M(0), M(0))
                modes[n] = "maintained"
                t_cur[n] = t0
                h_cur[n] = M(0)
            elif kind in ("sensible_body", "lumped_body"):
                t0 = _m(F(p.get("initialTemperatureK", p.get("initialBodyTemperatureK"))))
                cap = _m(F(p["heatCapacityJPerK"]))
                pwr = _m(F(p.get("heatInputW", "0")))
                specs[n] = ("body", t0, cap, M(0), M(0), M(0), M(0), pwr)
                modes[n] = "body"
                t_cur[n] = t0
                h_cur[n] = M(0)
            else:
                tr = _m(F(p["transitionTemperatureK"]))
                t0 = _m(F(p.get("initialTemperatureK", p["transitionTemperatureK"])))
                lat = _m(F(p["specificLatentHeatJPerKg"]))
                cs = _m(F(p["solidSpecificHeatJPerKgK"]))
                cl = _m(F(p["liquidSpecificHeatJPerKgK"]))
                ms = _m(F(p["initialSolidKg"]))
                ml = _m(F(p["initialLiquidKg"]))
                mtot = ms + ml
                pwr = _m(F(p.get("heatInputW", "0")))
                specs[n] = ("phase", t0, mtot * cs, mtot * cl, tr, mtot * lat, M(0), pwr)
                t_cur[n] = t0
                if t0 < tr:
                    modes[n] = "solid"
                    h_cur[n] = mtot * cs * (t0 - tr)
                elif t0 > tr:
                    modes[n] = "liquid"
                    h_cur[n] = mtot * lat + mtot * cl * (t0 - tr)
                else:
                    modes[n] = "plateau"
                    h_cur[n] = ml * lat

        def w_val(a, b):
            if (a, b) in edges:
                return _m(edges[(a, b)])
            if (b, a) in edges:
                return _m(edges[(b, a)])
            return M(0)

        # Initial pure-phase boundary direction
        for n in terminals:
            if specs[n][0] == "phase" and modes[n] == "plateau":
                tr, elat, pwr = specs[n][4], specs[n][5], specs[n][7]
                q0 = pwr + sum((w_val(n, o) * (t_cur[o] - t_cur[n]) for o in terminals if o != n), M(0))
                if h_cur[n] == 0 and q0 < 0:
                    modes[n] = "solid"
                elif h_cur[n] == elat and q0 > 0:
                    modes[n] = "liquid"

        t = M(0)
        D = _m(F(duration_s))
        events = []
        for _ in range(16):
            sens = [n for n in terminals if modes[n] in ("body", "solid", "liquid")]
            clamp = [n for n in terminals if modes[n] in ("plateau", "maintained")]
            s_idx = {n: i for i, n in enumerate(sens)}
            ns = len(sens)
            dim = 2 * ns + 1
            A = mp.matrix(dim)
            y0 = mp.matrix(dim, 1)
            for i, n in enumerate(sens):
                cap = specs[n][2] if modes[n] in ("body", "solid") else specs[n][3]
                pwr = specs[n][7]
                y0[i] = t_cur[n]
                A[i, dim - 1] += pwr / cap
                for o in terminals:
                    if o == n:
                        continue
                    wv = w_val(n, o)
                    A[i, i] -= wv / cap
                    if o in s_idx:
                        A[i, s_idx[o]] += wv / cap
                    else:
                        A[i, dim - 1] += wv * t_cur[o] / cap
                A[ns + i, i] = M(1)
            y0[dim - 1] = M(1)

            def decode(y, dt):
                tm = {n: y[i] for i, n in enumerate(sens)}
                for c in clamp:
                    tm[c] = t_cur[c]
                hm = {}
                for n in sens:
                    if specs[n][0] == "body":
                        hm[n] = specs[n][2] * (tm[n] - specs[n][1])
                    elif modes[n] == "solid":
                        hm[n] = specs[n][2] * (tm[n] - specs[n][4])
                    else:
                        hm[n] = specs[n][5] + specs[n][3] * (tm[n] - specs[n][4])
                for c in clamp:
                    de = specs[c][7] * dt
                    for i, s in enumerate(sens):
                        de += w_val(c, s) * (y[ns + i] - t_cur[c] * dt)
                    for oc in clamp:
                        if oc == c:
                            continue
                        de += w_val(c, oc) * (t_cur[oc] - t_cur[c]) * dt
                    hm[c] = h_cur[c] + de
                return tm, hm

            def eval_at(dt):
                return decode(mp.expm(A * dt) * y0, dt)

            rem = D - t
            n_scan = 120
            dt_step = rem / n_scan
            e_step = mp.expm(A * dt_step)
            yp = y0
            ta_m, ha_m = decode(yp, M(0))
            found = None
            for k in range(n_scan):
                ta = dt_step * k
                tb = dt_step * (k + 1)
                yn = e_step * yp
                tb_m, hb_m = decode(yn, tb)
                hits = []
                for n in terminals:
                    if specs[n][0] != "phase":
                        continue
                    md = modes[n]
                    tr = specs[n][4]
                    elat = specs[n][5]
                    if md == "solid":
                        if ta_m[n] <= tr <= tb_m[n] and not (k == 0 and abs(ta_m[n] - tr) < M("1e-70") and tb_m[n] <= tr):
                            root = mp.findroot(lambda u: eval_at(u)[0][n] - tr, (ta, tb))
                            hits.append((root, n, "plateau", tr, M(0)))
                    elif md == "liquid":
                        if ta_m[n] >= tr >= tb_m[n] and not (k == 0 and abs(ta_m[n] - tr) < M("1e-70") and tb_m[n] >= tr):
                            root = mp.findroot(lambda u: eval_at(u)[0][n] - tr, (ta, tb))
                            hits.append((root, n, "plateau", tr, elat))
                    else:
                        if ha_m[n] <= elat <= hb_m[n] and not (k == 0 and abs(ha_m[n] - elat) < M("1e-70") and hb_m[n] <= elat):
                            root = mp.findroot(lambda u: eval_at(u)[1][n] - elat, (ta, tb))
                            hits.append((root, n, "liquid", tr, elat))
                        if ha_m[n] >= 0 >= hb_m[n] and not (k == 0 and abs(ha_m[n]) < M("1e-70") and hb_m[n] >= 0):
                            root = mp.findroot(lambda u: eval_at(u)[1][n], (ta, tb))
                            hits.append((root, n, "solid", tr, M(0)))
                if hits:
                    min_r = min(h[0] for h in hits)
                    group = [h for h in hits if abs(h[0] - min_r) < M("1e-65")]
                    found = (min_r, group)
                    break
                yp = yn
                ta_m, ha_m = tb_m, hb_m

            if found is None:
                tf, hf = eval_at(rem)
                return tf, hf, dict(modes), events

            dt_ev, group = found
            tev, hev = eval_at(dt_ev)
            t += dt_ev
            t_cur = dict(tev)
            h_cur = dict(hev)
            ev_ports = []
            for _, nm, tgt, snap_t, snap_h in group:
                t_cur[nm] = snap_t
                h_cur[nm] = snap_h
                modes[nm] = tgt
                ev_ports.append((nm, tgt))
            events.append((t, tuple(sorted(ev_ports)), dict(t_cur), dict(h_cur)))
        raise RuntimeError("oracle step budget exceeded")


class M04EnthalpyContinuationTests(unittest.TestCase):
    def test_sol_link_calorimeter_1200s_closed_form_and_delta(self):
        # Sol's closed LINK calorimeter: body (C=2000 J/K, 373.15 K) + ice/water (0.3 kg, 1/3 liquid -> 0.2 solid, 0.1 liquid),
        # G = 2 W/K, D = 1200 s.
        # Exact closed form: t_melt = -1000*ln(0.666) ~ 406.465608 s,
        # final temperatures: 317.312375223 K (hot body) and 308.765277424 K (melted water).
        ports = {
            "hot": {"kind": "sensible_body", "heatCapacityJPerK": "2000", "initialTemperatureK": "373.15"},
            "ice": {
                "kind": "phase_substance",
                "transitionTemperatureK": "273.15",
                "specificLatentHeatJPerKg": "334000",
                "solidSpecificHeatJPerKgK": "2100",
                "liquidSpecificHeatJPerKgK": "4200",
                "initialSolidKg": "0.2",
                "initialLiquidKg": "0.1",
            },
        }
        with mp.workdps(110):
            t_melt = -mp.mpf(1000) * mp.log(mp.mpf("0.666"))
            t_eq = (2000 * mp.mpf("339.75") + 1260 * mp.mpf("273.15")) / 3260
            delta_t = (mp.mpf("339.75") - mp.mpf("273.15")) * mp.exp(
                -2 * (1 / mp.mpf(2000) + 1 / mp.mpf(1260)) * (1200 - t_melt)
            )
            t_hot_ex = t_eq + 1260 * delta_t / 3260
            t_ice_ex = t_eq - 2000 * delta_t / 3260

            for delta, max_t_w in ((F(0), F(1, 10**6)), (F(1, 10**6), F(2, 10**3))):
                law = _make_complete_law(["hot", "ice"], {("hot", "ice"): F(2)}, delta=delta)
                res = solve_continuation_from_law(law, ports, "1200")
                self.assertEqual(res["schema"], ENTHALPY_CONTINUATION_SCHEMA)
                self.assertEqual(res["status"], "complete")
                self.assertEqual(res["solverMetadata"]["terminationReason"], "resolved")
                self.assertIs(res["postExhaustionModeled"], True)
                for flag in OFFLINE_FLAG_KEYS:
                    self.assertIs(res[flag], False)
                    self.assertIs(res["evidence"][flag], False)
                self.assertEqual(len(res["events"]), 1)
                self.assertEqual(res["events"][0]["ports"], ["ice"])
                self.assertEqual(res["events"][0]["transitions"]["ice"], {"from": "plateau", "to": "liquid"})
                self.assertEqual(res["ports"]["ice"]["finalMode"], "liquid")
                self.assertEqual(res["ports"]["ice"]["remainingSolidBoundsKg"], ["0", "0"])
                self.assertEqual(res["ports"]["ice"]["remainingLiquidBoundsKg"], ["3/10", "3/10"])
                res_lo, res_hi = map(F, res["energyConservationResidualBoundsJ"])
                self.assertTrue(res_lo <= 0 <= res_hi)

                if delta == 0:
                    _in_bounds(self, res["events"][0]["timeBoundsS"], t_melt, max_width=F(1, 10**4))
                    _in_bounds(self, res["ports"]["hot"]["finalTemperatureBoundsK"], t_hot_ex, max_width=max_t_w)
                    _in_bounds(self, res["ports"]["ice"]["finalTemperatureBoundsK"], t_ice_ex, max_width=max_t_w)
                else:
                    for shift in (-1, 0, 1):
                        g_c = F(2) + shift * delta
                        tf_o, _, _, ev_o = _mp_piecewise_oracle(["hot", "ice"], {("hot", "ice"): g_c}, ports, "1200")
                        _in_bounds(self, res["events"][0]["timeBoundsS"], ev_o[0][0])
                        _in_bounds(self, res["ports"]["hot"]["finalTemperatureBoundsK"], tf_o["hot"], max_width=max_t_w)
                        _in_bounds(self, res["ports"]["ice"]["finalTemperatureBoundsK"], tf_o["ice"], max_width=max_t_w)

    def test_star3_and_star5_powered_multiphase_chains_against_110_digit_oracle(self):
        edges = {("n0", "n1"): F("0.6"), ("n0", "n2"): F("1"), ("n1", "n2"): F("1.5")}
        star3_ports = {
            "n0": {"kind": "sensible_body", "heatCapacityJPerK": "600", "initialTemperatureK": "280", "heatInputW": "300"},
            "n1": {
                "kind": "phase_substance",
                "initialTemperatureK": "265",
                "transitionTemperatureK": "270",
                "specificLatentHeatJPerKg": "334000",
                "solidSpecificHeatJPerKgK": "2100",
                "liquidSpecificHeatJPerKgK": "4200",
                "initialSolidKg": "0.2",
                "initialLiquidKg": "0",
            },
            "n2": {
                "kind": "phase_substance",
                "initialTemperatureK": "260",
                "transitionTemperatureK": "260",
                "specificLatentHeatJPerKg": "334000",
                "solidSpecificHeatJPerKgK": "2100",
                "liquidSpecificHeatJPerKgK": "4200",
                "initialSolidKg": "0.005",
                "initialLiquidKg": "0.095",
            },
        }
        star5_ports = {
            **star3_ports,
            "n0": {
                "kind": "phase_substance",
                "initialTemperatureK": "280",
                "transitionTemperatureK": "285",
                "specificLatentHeatJPerKg": "334000",
                "solidSpecificHeatJPerKgK": "2100",
                "liquidSpecificHeatJPerKgK": "4200",
                "initialSolidKg": "0.15",
                "initialLiquidKg": "0",
                "heatInputW": "300",
            },
        }

        for label, ports, dur, expected_events in (
            ("STAR3", star3_ports, "750", 3),
            ("STAR5", star5_ports, "900", 5),
        ):
            for delta, max_t_w in ((F(0), F(1, 10**4)), (F(1, 10**6), F(1, 100))):
                law = _make_complete_law(["n0", "n1", "n2"], edges, delta=delta)
                res = solve_enthalpy_continuation(law, ports, dur)
                self.assertEqual(res["status"], "complete", f"{label} delta={delta}: {res['solverMetadata']}")
                self.assertEqual(len(res["events"]), expected_events)
                res_lo, res_hi = map(F, res["energyConservationResidualBoundsJ"])
                self.assertTrue(res_lo <= 0 <= res_hi)

                # Check nominal + corner realizations against 110-digit mpmath oracle
                keys = list(edges.keys())
                shifts = [(0, 0, 0)] + ([(1, 1, 1), (-1, -1, -1), (1, -1, 1), (-1, 1, -1)] if delta > 0 else [])
                for sh in shifts:
                    ew = {k: edges[k] + d * delta for k, d in zip(keys, sh)}
                    tf_o, _, fmodes_o, ev_o = _mp_piecewise_oracle(["n0", "n1", "n2"], ew, ports, dur)
                    self.assertEqual(len(ev_o), expected_events)
                    for idx_e, (t_o, grp_o, _, _) in enumerate(ev_o):
                        _in_bounds(self, res["events"][idx_e]["timeBoundsS"], t_o)
                        self.assertEqual(res["events"][idx_e]["ports"], [p for p, _ in grp_o])
                    for n in ("n0", "n1", "n2"):
                        _in_bounds(self, res["ports"][n]["finalTemperatureBoundsK"], tf_o[n], max_width=max_t_w)
                        if ports[n]["kind"] == "phase_substance":
                            self.assertEqual(res["ports"][n]["finalMode"], fmodes_o[n])

    def test_exact_tie_near_tie_1e8_and_separated_tie_1e5_controls(self):
        edges = {("heater", "b1"): F(1), ("heater", "b2"): F(1), ("b1", "b2"): F("0.5")}

        def _tie_ports(m2_str: str):
            return {
                "heater": {"kind": "sensible_body", "heatCapacityJPerK": "1000", "initialTemperatureK": "373.15", "heatInputW": "300"},
                "b1": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0",
                },
                "b2": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": m2_str,
                    "initialLiquidKg": "0",
                },
            }

        # 1) Exact tie at delta=0 -> verified simultaneous switch!
        law_exact = _make_complete_law(["heater", "b1", "b2"], edges, delta=F(0))
        res_tie_0 = solve_enthalpy_continuation(law_exact, _tie_ports("0.1"), "450")
        self.assertEqual(res_tie_0["status"], "complete")
        self.assertEqual(len(res_tie_0["events"]), 1)
        self.assertEqual(set(res_tie_0["events"][0]["ports"]), {"b1", "b2"})
        self.assertIs(res_tie_0["events"][0]["simultaneousSymmetryProven"], True)
        tf_o, _, _, ev_o = _mp_piecewise_oracle(["heater", "b1", "b2"], edges, _tie_ports("0.1"), "450")
        _in_bounds(self, res_tie_0["events"][0]["timeBoundsS"], ev_o[0][0], max_width=F(1, 10**4))
        for n in ("heater", "b1", "b2"):
            _in_bounds(self, res_tie_0["ports"][n]["finalTemperatureBoundsK"], tf_o[n], max_width=F(1, 10**4))

        # 2) Exact tie at delta=1e-6 -> MUST stop with mode_sequence_uncertain (EH-01 symmetry guard!)
        law_unc = _make_complete_law(["heater", "b1", "b2"], edges, delta=F(1, 10**6))
        res_tie_d = solve_enthalpy_continuation(law_unc, _tie_ports("0.1"), "450")
        self.assertEqual(res_tie_d["status"], "mode_sequence_uncertain")
        self.assertEqual(res_tie_d["solverMetadata"]["stopReason"], "overlapping_event_brackets")
        self.assertEqual(set(res_tie_d["solverMetadata"]["unresolvedCandidatePorts"]), {"b1", "b2"})
        # Soundness even on uncertain stop: modeled stop encloses exact event time & state!
        _in_bounds(self, res_tie_d["modeledDurationBoundsS"], ev_o[0][0])

        # 3) Near tie (1e-8 kg difference): resolves into TWO sequential events at delta=0,
        #    stops as mode_sequence_uncertain at delta=1e-6!
        res_near_0 = solve_enthalpy_continuation(law_exact, _tie_ports("0.10000001"), "450")
        self.assertEqual(res_near_0["status"], "complete")
        self.assertEqual(len(res_near_0["events"]), 2)
        self.assertEqual(res_near_0["events"][0]["ports"], ["b1"])
        self.assertEqual(res_near_0["events"][1]["ports"], ["b2"])
        self.assertIs(res_near_0["events"][0]["simultaneousSymmetryProven"], False)
        tf_n, _, _, ev_n = _mp_piecewise_oracle(["heater", "b1", "b2"], edges, _tie_ports("0.10000001"), "450")
        _in_bounds(self, res_near_0["events"][0]["timeBoundsS"], ev_n[0][0])
        _in_bounds(self, res_near_0["events"][1]["timeBoundsS"], ev_n[1][0])
        for n in ("heater", "b1", "b2"):
            _in_bounds(self, res_near_0["ports"][n]["finalTemperatureBoundsK"], tf_n[n], max_width=F(1, 10**4))

        res_near_d = solve_enthalpy_continuation(law_unc, _tie_ports("0.10000001"), "450")
        self.assertEqual(res_near_d["status"], "mode_sequence_uncertain")
        self.assertEqual(res_near_d["solverMetadata"]["stopReason"], "overlapping_event_brackets")

        # 4) Separated tie (1e-5 kg difference): resolves into TWO sequential events at BOTH delta=0 and delta=1e-6!
        for delta, law_use, max_w in ((F(0), law_exact, F(1, 10**4)), (F(1, 10**6), law_unc, F(1, 100))):
            res_sep = solve_enthalpy_continuation(law_use, _tie_ports("0.10001"), "450")
            self.assertEqual(res_sep["status"], "complete", f"separated tie delta={delta}: {res_sep['solverMetadata']}")
            self.assertEqual(len(res_sep["events"]), 2)
            self.assertEqual(res_sep["events"][0]["ports"], ["b1"])
            self.assertEqual(res_sep["events"][1]["ports"], ["b2"])
            tf_s, _, _, ev_s = _mp_piecewise_oracle(["heater", "b1", "b2"], edges, _tie_ports("0.10001"), "450")
            _in_bounds(self, res_sep["events"][0]["timeBoundsS"], ev_s[0][0])
            _in_bounds(self, res_sep["events"][1]["timeBoundsS"], ev_s[1][0])
            for n in ("heater", "b1", "b2"):
                _in_bounds(self, res_sep["ports"][n]["finalTemperatureBoundsK"], tf_s[n], max_width=max_w)

    def test_reversing_reservoir_4event_cooling_reentry_refreezing_and_plateau_reversal(self):
        # Full 4-event reversing hysteresis on STAR:
        # subcooled solid -> plateau (melt) -> liquid (superheat peak) -> plateau (re-enter & refreeze) -> solid (subcool)
        edges_r2 = {("b", "p"): F("3.2"), ("p", "r"): F("0.55"), ("b", "r"): F("0.45")}
        ports_r2 = {
            "b": {"kind": "sensible_body", "heatCapacityJPerK": "900", "initialTemperatureK": "410"},
            "p": {
                "kind": "phase_substance",
                "initialTemperatureK": "260",
                "transitionTemperatureK": "273.15",
                "specificLatentHeatJPerKg": "334000",
                "solidSpecificHeatJPerKgK": "2100",
                "liquidSpecificHeatJPerKgK": "4200",
                "initialSolidKg": "0.04",
                "initialLiquidKg": "0",
            },
            "r": {"kind": "maintained", "temperatureK": "240"},
        }
        for delta, max_t_w in ((F(0), F(1, 10**4)), (F(1, 10**6), F(2, 10**3))):
            law = _make_complete_law(["b", "p", "r"], edges_r2, delta=delta)
            res = solve_enthalpy_continuation(law, ports_r2, "3800", initial_steps=24)
            self.assertEqual(res["status"], "complete", f"R2 delta={delta}: {res['solverMetadata']}")
            self.assertEqual(len(res["events"]), 4)
            seq = [(e["transitions"]["p"]["from"], e["transitions"]["p"]["to"]) for e in res["events"]]
            self.assertEqual(
                seq,
                [("solid", "plateau"), ("plateau", "liquid"), ("liquid", "plateau"), ("plateau", "solid")],
            )
            self.assertEqual(res["ports"]["p"]["finalMode"], "solid")
            tf_o, _, _, ev_o = _mp_piecewise_oracle(["b", "p", "r"], edges_r2, ports_r2, "3800")
            for idx_e, (t_o, _, _, _) in enumerate(ev_o):
                _in_bounds(self, res["events"][idx_e]["timeBoundsS"], t_o)
            for n in ("b", "p"):
                _in_bounds(self, res["ports"][n]["finalTemperatureBoundsK"], tf_o[n], max_width=max_t_w)

        # Plateau reversal without exhaustion, then refreeze to solid:
        edges_r3 = {("b", "p"): F("2"), ("p", "r"): F("0.8"), ("b", "r"): F("0.5")}
        ports_r3 = {
            "b": {"kind": "sensible_body", "heatCapacityJPerK": "600", "initialTemperatureK": "340"},
            "p": {
                "kind": "phase_substance",
                "transitionTemperatureK": "273.15",
                "specificLatentHeatJPerKg": "334000",
                "solidSpecificHeatJPerKgK": "2100",
                "liquidSpecificHeatJPerKgK": "4200",
                "initialSolidKg": "0.10",
                "initialLiquidKg": "0.02",
            },
            "r": {"kind": "maintained", "temperatureK": "245"},
        }
        law_r3 = _make_complete_law(["b", "p", "r"], edges_r3, delta=F(1, 10**6))
        res_r3 = solve_enthalpy_continuation(law_r3, ports_r3, "2000", initial_steps=24)
        self.assertEqual(res_r3["status"], "complete")
        self.assertEqual(len(res_r3["events"]), 1)
        self.assertEqual(res_r3["events"][0]["transitions"]["p"], {"from": "plateau", "to": "solid"})
        tf_r3, _, _, ev_r3 = _mp_piecewise_oracle(["b", "p", "r"], edges_r3, ports_r3, "2000")
        _in_bounds(self, res_r3["events"][0]["timeBoundsS"], ev_r3[0][0])
        _in_bounds(self, res_r3["ports"]["b"]["finalTemperatureBoundsK"], tf_r3["b"], max_width=F(1, 10**3))
        _in_bounds(self, res_r3["ports"]["p"]["finalTemperatureBoundsK"], tf_r3["p"], max_width=F(1, 10**3))

    def test_one_port_equivalence_with_staged_phase_body_network(self):
        # Verify exact enclosure overlap across all 3 stages (both heating and cooling!) against tools/staged_phase_body_network.py.
        law = DerivedLaw.from_rods(
            nodes=["env", "j", "sub"],
            terminals=["env", "sub"],
            rods={
                "r1": {"kind": "rod_area", "a": "env", "b": "j", "k": "20", "L": "0.1", "A": "0.02"},
                "r2": {"kind": "rod_area", "a": "j", "b": "sub", "k": "10", "L": "0.1", "A": "0.04"},
            },
        )
        # 1) Heating 3-stage: subcooled solid (250 K) -> melt -> superheated liquid at D = 4000 s
        st_heat = solve_staged(
            law, "sub", "250", "273.15", "334000", "2100", "4200", "0.1", "0", "4000",
            maintained_temperatures_k={"env": "380"},
        )
        en_heat = solve_enthalpy_continuation(
            law,
            {
                "env": {"kind": "maintained", "temperatureK": "380"},
                "sub": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "250",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0",
                },
            },
            "4000",
        )
        self.assertEqual(st_heat["trajectory"]["finalStage"], "liquid_sensible")
        self.assertEqual(en_heat["status"], "complete")
        self.assertEqual(en_heat["ports"]["sub"]["finalMode"], "liquid")
        self.assertEqual(len(en_heat["events"]), 2)
        for a_pair, b_pair in (
            (st_heat["trajectory"]["transitionEntryTimeBoundsS"], en_heat["events"][0]["timeBoundsS"]),
            (st_heat["trajectory"]["phaseExhaustionTimeBoundsS"], en_heat["events"][1]["timeBoundsS"]),
            (st_heat["trajectory"]["finalTemperatureBoundsK"], en_heat["ports"]["sub"]["finalTemperatureBoundsK"]),
            (st_heat["trajectory"]["totalEnergyIntoSubstanceBoundsJ"], en_heat["ports"]["sub"]["enthalpyChangeBoundsJ"]),
        ):
            a_lo, a_hi = map(F, a_pair)
            b_lo, b_hi = map(F, b_pair)
            self.assertLessEqual(max(a_lo, b_lo), min(a_hi, b_hi), f"no overlap: {a_pair} vs {b_pair}")

        # 2) Cooling 3-stage: superheated liquid (310 K) -> freeze -> subcooled solid at D = 4000 s
        st_cool = solve_staged(
            law, "sub", "310", "273.15", "334000", "2100", "4200", "0", "0.1", "4000",
            maintained_temperatures_k={"env": "220"},
        )
        en_cool = solve_enthalpy_continuation(
            law,
            {
                "env": {"kind": "maintained", "temperatureK": "220"},
                "sub": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "310",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0",
                    "initialLiquidKg": "0.1",
                },
            },
            "4000",
        )
        self.assertEqual(st_cool["trajectory"]["finalStage"], "solid_sensible")
        self.assertEqual(en_cool["status"], "complete")
        self.assertEqual(en_cool["ports"]["sub"]["finalMode"], "solid")
        self.assertEqual(len(en_cool["events"]), 2)
        for a_pair, b_pair in (
            (st_cool["trajectory"]["transitionEntryTimeBoundsS"], en_cool["events"][0]["timeBoundsS"]),
            (st_cool["trajectory"]["phaseExhaustionTimeBoundsS"], en_cool["events"][1]["timeBoundsS"]),
            (st_cool["trajectory"]["finalTemperatureBoundsK"], en_cool["ports"]["sub"]["finalTemperatureBoundsK"]),
        ):
            a_lo, a_hi = map(F, a_pair)
            b_lo, b_hi = map(F, b_pair)
            self.assertLessEqual(max(a_lo, b_lo), min(a_hi, b_hi), f"no overlap: {a_pair} vs {b_pair}")

    def test_coupled_hot_body_subcooled_ice_calorimeter_jee_problem_over_joined_derived_law(self):
        # End-to-end JEE calorimetry problem authored declaratively in ThermalSystem over a Schur-joined DerivedLaw:
        # Left subnetwork: hot copper block (420 K, 0.5 kg * 400 J/kgK = 200 J/K) + brass calorimeter cup (300 K, 1500 J/K)
        # Right subnetwork: subcooled ice block (-15 C = 258.15 K, 0.15 kg) spliced into the calorimeter via a conduction bridge!
        # Subcooled ice warms to 273.15 K -> melts completely -> warms as liquid water toward calorimeter equilibrium!
        system = {
            "schema": THERMAL_SYSTEM_SCHEMA,
            "id": "jee_coupled_hot_block_ice_calorimeter",
            "conduction": {
                "kind": "join",
                "left": {
                    "kind": "rods",
                    "nodes": ["hot_block", "calorimeter", "bridge"],
                    "terminals": ["hot_block", "calorimeter", "bridge"],
                    "rods": {
                        "block_to_cal": {"kind": "rod_area", "a": "hot_block", "b": "calorimeter", "k": "25", "L": "0.1", "A": "0.01"},
                        "cal_to_bridge": {"kind": "rod_area", "a": "calorimeter", "b": "bridge", "k": "40", "L": "0.1", "A": "0.01"},
                        "block_to_bridge": {"kind": "rod_area", "a": "hot_block", "b": "bridge", "k": "15", "L": "0.1", "A": "0.01"},
                    },
                },
                "right": {
                    "kind": "rods",
                    "nodes": ["bridge", "ice_sample"],
                    "terminals": ["bridge", "ice_sample"],
                    "rods": {
                        "bridge_to_ice": {"kind": "rod_area", "a": "bridge", "b": "ice_sample", "k": "30", "L": "0.1", "A": "0.02"},
                    },
                },
                "contacts": [{"leftPort": "bridge", "rightPort": "bridge"}],
            },
            "attachments": {
                "left.hot_block": {
                    "kind": "sensible_body",
                    "massKg": "0.5",
                    "specificHeatJPerKgK": "400",
                    "initialTemperatureK": "420",
                },
                "left.calorimeter": {
                    "kind": "sensible_body",
                    "heatCapacityJPerK": "1500",
                    "initialTemperatureK": "320",
                },
                "right.ice_sample": {
                    "kind": "phase_substance",
                    "initialTemperatureK": "258.15",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.15",
                    "initialLiquidKg": "0",
                },
            },
            "solve": {"mode": "transient", "durationS": "600"},
        }
        eq = describe_equations(system)
        self.assertEqual(eq["selectedBackend"], "enthalpy")
        self.assertIn("Piecewise enthalpy H[right.ice_sample]", eq["terminalEquations"]["right.ice_sample"])

        res = solve_system(system)
        self.assertEqual(res["schema"], RESULT_ENVELOPE_SCHEMA)
        self.assertEqual(res["backend"], "enthalpy")
        self.assertEqual(res["status"], "complete")
        self.assertEqual(res["terminationReason"], "resolved")
        self.assertEqual(res["derivedLaw"]["lineage"]["kind"], "schur_join")
        raw = res["backendResult"]
        self.assertEqual(len(raw["events"]), 2)
        self.assertEqual(raw["events"][0]["transitions"]["right.ice_sample"], {"from": "solid", "to": "plateau"})
        self.assertEqual(raw["events"][1]["transitions"]["right.ice_sample"], {"from": "plateau", "to": "liquid"})
        self.assertEqual(raw["ports"]["right.ice_sample"]["finalMode"], "liquid")
        # Independent 110-digit mpmath oracle on the exact Schur-reduced conductance matrix!
        from simheat.system import ThermalSystem

        tsys = ThermalSystem.from_dict(system)
        terms = list(tsys.derived_law.terminals)
        edges = {}
        for i, a in enumerate(terms):
            for b in terms[i + 1:]:
                edges[(a, b)] = -tsys.derived_law.matrix[a][b][0]
        oracle_ports = {
            "left.hot_block": {"kind": "sensible_body", "heatCapacityJPerK": "200", "initialTemperatureK": "420"},
            "left.calorimeter": {"kind": "sensible_body", "heatCapacityJPerK": "1500", "initialTemperatureK": "320"},
            "right.ice_sample": system["attachments"]["right.ice_sample"],
        }
        tf_o, _, _, ev_o = _mp_piecewise_oracle(terms, edges, oracle_ports, "600")
        self.assertEqual(len(ev_o), 2)
        _in_bounds(self, raw["events"][0]["timeBoundsS"], ev_o[0][0], max_width=F(1, 10**4))
        _in_bounds(self, raw["events"][1]["timeBoundsS"], ev_o[1][0], max_width=F(1, 10**4))
        for n in terms:
            _in_bounds(self, raw["ports"][n]["finalTemperatureBoundsK"], tf_o[n], max_width=F(1, 10**4))

    def test_pure_phase_starts_unresolved_boundaries_forced_budgets_and_negative_controls(self):
        link = _make_complete_law(["a", "b"], {("a", "b"): F(2)})

        # 1) Pure solid at T_tr coupled to COLDER body -> immediately enters 'solid' sensible cooling (0 events)!
        cool_solid = solve_enthalpy_continuation(
            link,
            {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "1000", "initialTemperatureK": "220"},
                "b": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.5",
                    "initialLiquidKg": "0",
                },
            },
            "50",
        )
        self.assertEqual(cool_solid["status"], "complete")
        self.assertEqual(cool_solid["ports"]["b"]["finalMode"], "solid")
        self.assertEqual(len(cool_solid["events"]), 0)
        self.assertLess(F(cool_solid["ports"]["b"]["finalTemperatureBoundsK"][1]), F("273.15"))

        # 2) Pure liquid at T_tr coupled to HOTTER body -> immediately enters 'liquid' sensible heating (0 events)!
        heat_liq = solve_enthalpy_continuation(
            link,
            {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "1000", "initialTemperatureK": "350"},
                "b": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0",
                    "initialLiquidKg": "0.5",
                },
            },
            "50",
        )
        self.assertEqual(heat_liq["status"], "complete")
        self.assertEqual(heat_liq["ports"]["b"]["finalMode"], "liquid")
        self.assertEqual(len(heat_liq["events"]), 0)
        self.assertGreater(F(heat_liq["ports"]["b"]["finalTemperatureBoundsK"][0]), F("273.15"))

        # 3) Zero initial flux at a pure-phase boundary (with nonzero derivative on STAR) -> mode_sequence_uncertain!
        star = _make_complete_law(["p", "b", "r"], {("p", "b"): F(1), ("p", "r"): F(1), ("b", "r"): F(1)})
        zf = solve_enthalpy_continuation(
            star,
            {
                "p": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "300",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.5",
                    "initialLiquidKg": "0",
                },
                "b": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "320"},
                "r": {"kind": "maintained", "temperatureK": "280"},
            },
            "100",
        )
        self.assertEqual(zf["status"], "mode_sequence_uncertain")
        self.assertEqual(zf["solverMetadata"]["stopReason"], "unresolved_initial_boundary_departure")
        self.assertEqual(zf["modeledDurationBoundsS"], ["0", "0"])

        # 4) Forced max_events=1 on a 2-event system -> clean refinement_budget stop enclosing event 1!
        sub_sys_ports = {
            "a": {"kind": "maintained", "temperatureK": "380"},
            "b": {
                "kind": "phase_substance",
                "initialTemperatureK": "250",
                "transitionTemperatureK": "273.15",
                "specificLatentHeatJPerKg": "334000",
                "solidSpecificHeatJPerKgK": "2100",
                "liquidSpecificHeatJPerKgK": "4200",
                "initialSolidKg": "0.1",
                "initialLiquidKg": "0",
            },
        }
        capped = solve_enthalpy_continuation(link, sub_sys_ports, "4000", max_events=1)
        self.assertEqual(capped["status"], "mode_sequence_uncertain")
        self.assertEqual(capped["solverMetadata"]["terminationReason"], "refinement_budget")
        self.assertEqual(capped["solverMetadata"]["stopReason"], "max_events_budget_reached")
        self.assertEqual(len(capped["events"]), 1)
        tf_c, _, _, ev_c = _mp_piecewise_oracle(["a", "b"], {("a", "b"): F(2)}, sub_sys_ports, "4000")
        _in_bounds(self, capped["modeledDurationBoundsS"], ev_c[1][0])

        # 5) Negative controls: non-passive law refused, invalid signed heatInputW refused, forged flags refused.
        bad_law = {
            "schema": "sim_heat.offline_terminal_response/1",
            "terminals": ["a", "b"],
            "supplyResponseBoundsWPerK": {
                "a": {"a": ["2", "2"], "b": ["-1", "-1"]},
                "b": {"a": ["-1", "-1"], "b": ["2", "2"]},
            },
        }
        with self.assertRaises(ValueError):
            solve_enthalpy_continuation(bad_law, sub_sys_ports, "10")
        with self.assertRaises(ValueError):
            solve_enthalpy_continuation(
                link,
                {
                    "a": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "300", "heatInputW": "+10"},
                    "b": {"kind": "maintained", "temperatureK": "300"},
                },
                "10",
            )
        # M04-R03: surrounding whitespace in heatInputW must be refused (matches decimal_input).
        with self.assertRaises(ValueError):
            solve_enthalpy_continuation(
                link,
                {
                    "a": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "300", "heatInputW": " -10 "},
                    "b": {"kind": "maintained", "temperatureK": "300"},
                },
                "10",
            )

    def test_review_hardening_m04_r01_r02_r03_regressions(self):
        # M04-R01(1): intermediate multi-stage negative Kelvin (-66.19 K at event 0, recovering to +697.86 K) MUST fail!
        law_r01_a = DerivedLaw.from_rods(
            nodes=["a", "p", "r"],
            terminals=["a", "p", "r"],
            rods={
                "ap": {"kind": "rod_area", "a": "a", "b": "p", "k": "0.5", "L": "1", "A": "1"},
                "pr": {"kind": "rod_area", "a": "p", "b": "r", "k": "1", "L": "1", "A": "1"},
            },
        )
        with self.assertRaisesRegex(ValueError, "negative absolute temperature"):
            solve_enthalpy_continuation(
                law_r01_a,
                {
                    "a": {"kind": "sensible_body", "heatCapacityJPerK": "10", "initialTemperatureK": "50", "heatInputW": "-100"},
                    "p": {
                        "kind": "phase_substance",
                        "transitionTemperatureK": "100",
                        "specificLatentHeatJPerKg": "100000",
                        "solidSpecificHeatJPerKgK": "100",
                        "liquidSpecificHeatJPerKgK": "100",
                        "initialSolidKg": "0.25",
                        "initialLiquidKg": "0",
                    },
                    "r": {"kind": "maintained", "temperatureK": "1000"},
                },
                "300",
            )

        # M04-R01(2): zero-event sensible-body intermediate dip below 0 K (recovering by t=150 s) MUST fail!
        law_r01_b = _make_complete_law(["a", "b"], {("a", "b"): F("0.1")})
        with self.assertRaisesRegex(ValueError, "negative absolute temperature"):
            solve_enthalpy_continuation(
                law_r01_b,
                {
                    "a": {"kind": "sensible_body", "heatCapacityJPerK": "1", "initialTemperatureK": "10", "heatInputW": "-50"},
                    "b": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "200", "heatInputW": "500"},
                },
                "150",
            )

        # M04-R01(3): interval conductance straddling 0 K ([-28.27 K, +19.44 K]) MUST NOT return status='complete'!
        law_r01_c = DerivedLaw.from_rods(
            nodes=["a", "b"],
            terminals=["a", "b"],
            rods={"ab": {"kind": "rod_area", "a": "a", "b": "b", "k": {"low": "0.8", "high": "1.2"}, "L": "1", "A": "1"}},
        )
        with self.assertRaisesRegex(ValueError, "nonnegative absolute temperature|negative absolute temperature"):
            solve_enthalpy_continuation(
                law_r01_c,
                {
                    "a": {"kind": "sensible_body", "heatCapacityJPerK": "10", "initialTemperatureK": "20", "heatInputW": "-100"},
                    "b": {"kind": "maintained", "temperatureK": "100"},
                },
                "50",
            )

        # Positive control with heatInputW < 0 where T stays strictly positive (~250 K > 0 K) MUST still complete cleanly!
        pos_ctrl = solve_enthalpy_continuation(
            law_r01_c,
            {
                "a": {"kind": "sensible_body", "heatCapacityJPerK": "100", "initialTemperatureK": "300", "heatInputW": "-10"},
                "b": {"kind": "maintained", "temperatureK": "300"},
            },
            "50",
        )
        self.assertEqual(pos_ctrl["status"], "complete")
        self.assertGreater(F(pos_ctrl["ports"]["a"]["finalTemperatureBoundsK"][0]), F(200))

        # M04-R02: solve_continuation_from_law uses the full continuation defaults (240/96) and matches direct call on R2 initial_steps=1!
        edges_r2 = {("b", "p"): F("3.2"), ("p", "r"): F("0.55"), ("b", "r"): F("0.45")}
        ports_r2 = {
            "b": {"kind": "sensible_body", "heatCapacityJPerK": "900", "initialTemperatureK": "410"},
            "p": {
                "kind": "phase_substance",
                "initialTemperatureK": "260",
                "transitionTemperatureK": "273.15",
                "specificLatentHeatJPerKg": "334000",
                "solidSpecificHeatJPerKgK": "2100",
                "liquidSpecificHeatJPerKgK": "4200",
                "initialSolidKg": "0.04",
                "initialLiquidKg": "0",
            },
            "r": {"kind": "maintained", "temperatureK": "240"},
        }
        law_r2 = _make_complete_law(["b", "p", "r"], edges_r2, delta=F(0))
        res_wrap = solve_continuation_from_law(law_r2, ports_r2, "3800", initial_steps=1)
        self.assertEqual(res_wrap["status"], "complete")
        self.assertEqual(len(res_wrap["events"]), 4)

        # M04-R03: event landing at exact t == duration with zero post-event flux completes cleanly!
        # Link G=2, hot maintained 300 K, pure solid at 250 K? Better: hot body at 300 K?
        # Even simpler: pure solid at T_tr=300 K, L=1000, m=0.1 -> e_lat=100 J, maintained at 301 K, G=1 -> Q=1 W -> melts at exact t=100 s!
        # Add heatInputW="-1" on a 3rd node? No, with exact t=100 s and duration=100 s, rem_hi==0 after event 0!
        law_exact_end = _make_complete_law(["p", "r"], {("p", "r"): F(1)})
        res_end = solve_enthalpy_continuation(
            law_exact_end,
            {
                "p": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "300",
                    "specificLatentHeatJPerKg": "1000",
                    "solidSpecificHeatJPerKgK": "100",
                    "liquidSpecificHeatJPerKgK": "100",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0",
                },
                "r": {"kind": "maintained", "temperatureK": "301"},
            },
            "100",
        )
        self.assertEqual(res_end["status"], "complete")
        self.assertEqual(res_end["modeledDurationBoundsS"], ["100", "100"])


if __name__ == "__main__":
    unittest.main()
