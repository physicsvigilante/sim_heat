"""Transient exchange between a lumped heat-capacity body and a finite two-phase bath."""
import argparse
from fractions import Fraction as F
import json

from qualification.h1_n13.conduction import ZERO, Box, interval
from simheat.laws import validate_terminal_law
from tools.join_thermal_networks import bounds
from tools.latent_heat_bath import phase_inputs
from tools.offline_provenance import offline_provenance
from tools.radiating_surface import decimal_input, physical_port
from tools.spherical_conduction import radial_log
from tools.terminal_response import investigate as terminal_response


def exp_neg_box(x):
    """Certified rational enclosure of exp(-x) for a nonnegative Fraction x."""
    if x < 0:
        raise ValueError("nonnegative exponent argument required")
    if x == 0:
        return Box.exact(1)
    m = 0
    y = x
    while y > 1:
        y /= 2
        m += 1
    # Alternating Taylor series on y in (0, 1]: stopping at odd index 43 is a
    # strict lower bound and adding even term 44 is a strict upper bound.
    term = F(1)
    partial = F(1)
    for k in range(1, 44):
        term = -term * y / k
        partial += term
    lo = partial
    hi = partial + (-term * y / 44)
    res = Box.bounds(lo, hi)
    for _ in range(m):
        res = res * res
    return res


def exp_neg_interval(x_box):
    """Certified enclosure of exp(-x) for a nonnegative Box x_box."""
    lo, hi = x_box.span()
    if lo < 0:
        raise ValueError("nonnegative exponent interval required")
    return Box.bounds(exp_neg_box(hi).span()[0], exp_neg_box(lo).span()[1])


def _body_temp_box(t_eq, t_0, exp_box):
    """Tight convex-combination enclosure of T_b(t) = (1 - e)*T_eq + e*T_0."""
    eq_lo, eq_hi = t_eq.span()
    e_lo, e_hi = exp_box.span()
    corners = [(1 - e) * eq + e * t_0 for eq in (eq_lo, eq_hi) for e in (e_lo, e_hi)]
    return Box.bounds(min(corners), max(corners))


def _bisect_threshold(eval_fn, target, lo, hi, increasing=True, steps=64, lo_proved_safe=False):
    """Bracket first time in [lo, hi] where a monotonic interval function crosses target.

    By default (lo_proved_safe=False), verifies before(lo); if that fails, returns None
    for the lower bracket instead of certifying lo. Callers may pass lo_proved_safe=True
    only when an analytic proof guarantees no realization crosses at or before lo despite
    interval-dependency widening in eval_fn(lo).
    """
    # Find largest t_lo in [lo, hi] strictly before crossing, and smallest t_hi at/after crossing.
    def before(t):
        v_lo, v_hi = eval_fn(t).span()
        return v_hi < target if increasing else v_lo > target

    def reached(t):
        v_lo, v_hi = eval_fn(t).span()
        return v_lo >= target if increasing else v_hi <= target

    if not lo_proved_safe and not before(lo):
        if reached(lo):
            return None, lo
        if not reached(hi):
            return None, None
        a_hi, b_hi = lo, hi
        for _ in range(steps):
            mid = (a_hi + b_hi) / 2
            if reached(mid):
                b_hi = mid
            else:
                a_hi = mid
        return None, b_hi

    a_lo, b_lo = lo, hi
    for _ in range(steps):
        mid = (a_lo + b_lo) / 2
        if before(mid):
            a_lo = mid
        else:
            b_lo = mid

    a_hi, b_hi = a_lo, hi
    if not reached(hi):
        return a_lo, None
    for _ in range(steps):
        mid = (a_hi + b_hi) / 2
        if reached(mid):
            b_hi = mid
        else:
            a_hi = mid
    return a_lo, b_hi


def solve_from_law(law, phase_port, body_port, transition_k, latent_heat_j_per_kg,
                   solid_kg, liquid_kg, capacity_j_per_k, initial_k, duration_s):
    raw_terms = law.terminals if hasattr(law, "terminals") else (law.get("terminals") if isinstance(law, dict) else None)
    if not raw_terms or phase_port == body_port or not {phase_port, body_port} <= set(raw_terms):
        raise ValueError("distinct phase and body ports required in the pinned network")
    # Preserve explicit coupling diagnostic before full passivity check when the pair conductance is zero.
    if isinstance(law, dict) and isinstance(law.get("supplyResponseBoundsWPerK"), dict):
        row_p_raw = law["supplyResponseBoundsWPerK"].get(phase_port)
        if isinstance(row_p_raw, dict) and body_port in row_p_raw:
            try:
                if (-interval(row_p_raw[body_port])).span()[0] <= 0:
                    raise ValueError("phase bath and body port are not thermally coupled")
            except (TypeError, ValueError) as exc:
                if "not thermally coupled" in str(exc):
                    raise
    resolved_law, _ = validate_terminal_law(law)
    law = resolved_law.to_engine_law()
    if "imposedTemperaturesK" not in law:
        raise ValueError("body_phase_bath_exchange requires imposedTemperaturesK on the law")
    transition, latent, solid, liquid, duration = phase_inputs(
        transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s)
    capacity = decimal_input(capacity_j_per_k, "heat capacity")
    initial = decimal_input(initial_k, "initial body temperature")
    if capacity <= 0:
        raise ValueError("positive heat capacity required")

    maintained = {**law["imposedTemperaturesK"], phase_port: str(transition)}
    other_ports = [n for n in law["terminals"] if n not in (phase_port, body_port)]

    opens, port_r = physical_port({**law, "imposedTemperaturesK": maintained}, body_port)
    t_eq = Box.bounds(*opens)
    r_port = Box.bounds(*port_r)
    tau = Box.exact(capacity) * r_port

    row_p = law["supplyResponseBoundsWPerK"][phase_port]
    row_b = law["supplyResponseBoundsWPerK"][body_port]
    g_pb = -interval(row_p[body_port])
    if g_pb.span()[0] <= 0:
        raise ValueError("phase bath and body port are not thermally coupled")

    e_solid = solid * latent
    e_liquid = -liquid * latent

    if not other_ports:
        # Exact two-terminal reduction: T_eq == transition, Q_inf == 0, G_pb/G_b == 1.
        t_eq = Box.exact(transition)
        q_inf = ZERO
        q_tr = g_pb * (initial - transition)
        tau_q_tr = Box.exact(capacity * (initial - transition))
    else:
        g_bm = sum((-interval(row_b[n]) for n in other_ports), ZERO)
        share = Box.exact(1) / (Box.exact(1) + g_bm / g_pb)
        q_inf = (g_pb * (t_eq - transition)
                 + sum((-interval(row_p[n]) * (F(maintained[n]) - transition)
                        for n in other_ports), ZERO))
        q_tr = g_pb * (initial - t_eq)
        tau_q_tr = Box.exact(capacity) * share * (initial - t_eq)

    def energy_at(t):
        if t == 0:
            return ZERO
        e_box = exp_neg_interval(Box.exact(t) / tau)
        return q_inf * t + tau_q_tr * (Box.exact(1) - e_box)

    def body_temp_at_interval(t_lo, t_hi):
        e_lo = exp_neg_interval(Box.exact(t_hi) / tau).span()[0]
        e_hi = exp_neg_interval(Box.exact(t_lo) / tau).span()[1]
        return _body_temp_box(t_eq, initial, Box.bounds(e_lo, e_hi))

    q0 = q_inf + q_tr
    e_end_exp = exp_neg_interval(Box.exact(duration) / tau) if duration > 0 else Box.exact(1)
    q_end = q_inf + q_tr * e_end_exp

    q0_lo, q0_hi = q0.span()
    qe_lo, qe_hi = q_end.span()
    qi_lo, qi_hi = q_inf.span()

    exhausted_phase = None
    reversal_bounds = None
    exhaustion_bounds = None

    if not other_ports:
        asymp = capacity * (initial - transition)
        if asymp == 0:
            process = "equilibrium"
            status = "coexisting"
            mod_lo = mod_hi = duration
            e_box = ZERO
            t_final = Box.exact(initial)
        elif asymp > 0:
            process = "melting"
            if asymp <= e_solid:
                status = "coexisting"
                mod_lo = mod_hi = duration
                e_box = energy_at(duration)
                t_final = body_temp_at_interval(duration, duration)
            else:
                t_exh = tau * radial_log(asymp / (asymp - e_solid))
                ex_lo, ex_hi = t_exh.span()
                exhaustion_bounds = [str(ex_lo), str(ex_hi)]
                if duration < ex_lo:
                    status = "coexisting"
                    mod_lo = mod_hi = duration
                    e_box = energy_at(duration)
                    t_final = body_temp_at_interval(duration, duration)
                elif duration >= ex_hi:
                    status = "exhausted"
                    exhausted_phase = "solid"
                    mod_lo, mod_hi = ex_lo, ex_hi
                    e_box = Box.exact(e_solid)
                    t_final = Box.exact(initial - e_solid / capacity)
                else:
                    status = "exhaustion_time_uncertain"
                    mod_lo, mod_hi = ex_lo, duration
                    e_raw = energy_at(duration)
                    e_box = Box.bounds(min(e_solid, e_raw.span()[0]), min(e_solid, e_raw.span()[1]))
                    t_final = body_temp_at_interval(ex_lo, duration)
        else:
            process = "freezing"
            if -asymp <= -e_liquid:
                status = "coexisting"
                mod_lo = mod_hi = duration
                e_box = energy_at(duration)
                t_final = body_temp_at_interval(duration, duration)
            else:
                t_exh = tau * radial_log((-asymp) / (-asymp + e_liquid))
                ex_lo, ex_hi = t_exh.span()
                exhaustion_bounds = [str(ex_lo), str(ex_hi)]
                if duration < ex_lo:
                    status = "coexisting"
                    mod_lo = mod_hi = duration
                    e_box = energy_at(duration)
                    t_final = body_temp_at_interval(duration, duration)
                elif duration >= ex_hi:
                    status = "exhausted"
                    exhausted_phase = "liquid"
                    mod_lo, mod_hi = ex_lo, ex_hi
                    e_box = Box.exact(e_liquid)
                    t_final = Box.exact(initial - e_liquid / capacity)
                else:
                    status = "exhaustion_time_uncertain"
                    mod_lo, mod_hi = ex_lo, duration
                    e_raw = energy_at(duration)
                    e_box = Box.bounds(max(e_liquid, e_raw.span()[0]), max(e_liquid, e_raw.span()[1]))
                    t_final = body_temp_at_interval(ex_lo, duration)
    else:
        melting_mono = q0_lo >= 0 and qe_lo >= 0 and (
            q0_lo > 0 or qe_lo > 0 or (q0_hi == 0 and qi_lo > 0))
        freezing_mono = q0_hi <= 0 and qe_hi <= 0 and (
            q0_hi < 0 or qe_hi < 0 or (q0_lo == 0 and qi_hi < 0))
        if q0_lo == q0_hi == 0 and qi_lo == qi_hi == 0:
            process = "equilibrium"
            status = "coexisting"
            mod_lo = mod_hi = duration
            e_box = ZERO
            t_final = body_temp_at_interval(duration, duration)
        elif melting_mono:
            process = "melting"
            e_req = energy_at(duration)
            if e_req.span()[1] < e_solid:
                status = "coexisting"
                mod_lo = mod_hi = duration
                e_box = e_req
                t_final = body_temp_at_interval(duration, duration)
                if qi_lo > 0:
                    hi = max(F(1), duration)
                    while energy_at(hi).span()[0] < e_solid:
                        hi *= 2
                    ex_lo, ex_hi = _bisect_threshold(energy_at, e_solid, duration, hi, increasing=True)
                    if ex_lo is not None and ex_hi is not None:
                        exhaustion_bounds = [str(ex_lo), str(ex_hi)]
            elif e_req.span()[0] >= e_solid:
                ex_lo, ex_hi = _bisect_threshold(energy_at, e_solid, F(0), duration, increasing=True)
                if ex_lo is None or ex_hi is None:
                    status = "exhaustion_time_uncertain"
                    mod_lo, mod_hi = F(0), duration
                    e_box = Box.bounds(min(e_solid, e_req.span()[0]), min(e_solid, e_req.span()[1]))
                    t_final = body_temp_at_interval(F(0), duration)
                else:
                    status = "exhausted"
                    exhausted_phase = "solid"
                    exhaustion_bounds = [str(ex_lo), str(ex_hi)]
                    mod_lo, mod_hi = ex_lo, ex_hi
                    e_box = Box.exact(e_solid)
                    t_final = body_temp_at_interval(ex_lo, ex_hi)
            else:
                status = "exhaustion_time_uncertain"
                ex_lo, _ = _bisect_threshold(energy_at, e_solid, F(0), duration, increasing=True)
                mod_lo = F(0) if ex_lo is None else ex_lo
                mod_hi = duration
                e_box = Box.bounds(min(e_solid, e_req.span()[0]), min(e_solid, e_req.span()[1]))
                t_final = body_temp_at_interval(mod_lo, duration)
        elif freezing_mono:
            process = "freezing"
            e_req = energy_at(duration)
            if e_req.span()[0] > e_liquid:
                status = "coexisting"
                mod_lo = mod_hi = duration
                e_box = e_req
                t_final = body_temp_at_interval(duration, duration)
                if qi_hi < 0:
                    hi = max(F(1), duration)
                    while energy_at(hi).span()[1] > e_liquid:
                        hi *= 2
                    ex_lo, ex_hi = _bisect_threshold(energy_at, e_liquid, duration, hi, increasing=False)
                    if ex_lo is not None and ex_hi is not None:
                        exhaustion_bounds = [str(ex_lo), str(ex_hi)]
            elif e_req.span()[1] <= e_liquid:
                ex_lo, ex_hi = _bisect_threshold(energy_at, e_liquid, F(0), duration, increasing=False)
                if ex_lo is None or ex_hi is None:
                    status = "exhaustion_time_uncertain"
                    mod_lo, mod_hi = F(0), duration
                    e_box = Box.bounds(max(e_liquid, e_req.span()[0]), max(e_liquid, e_req.span()[1]))
                    t_final = body_temp_at_interval(F(0), duration)
                else:
                    status = "exhausted"
                    exhausted_phase = "liquid"
                    exhaustion_bounds = [str(ex_lo), str(ex_hi)]
                    mod_lo, mod_hi = ex_lo, ex_hi
                    e_box = Box.exact(e_liquid)
                    t_final = body_temp_at_interval(ex_lo, ex_hi)
            else:
                status = "exhaustion_time_uncertain"
                ex_lo, _ = _bisect_threshold(energy_at, e_liquid, F(0), duration, increasing=False)
                mod_lo = F(0) if ex_lo is None else ex_lo
                mod_hi = duration
                e_box = Box.bounds(max(e_liquid, e_req.span()[0]), max(e_liquid, e_req.span()[1]))
                t_final = body_temp_at_interval(mod_lo, duration)
        elif (q0_lo > 0 and qe_hi < 0) or (q0_hi < 0 and qe_lo > 0):
            # Genuine sign reversal on (0, duration): unique turning point t* = tau * ln(-Q_tr / Q_inf).
            melting_first = q0_lo > 0
            process = "reversing_melting_to_freezing" if melting_first else "reversing_freezing_to_melting"
            ratio = -q_tr / q_inf
            r_lo, r_hi = ratio.span()
            if r_lo <= 1:
                raise ValueError("phase-bath reversal time is unresolved")
            ln_ratio = Box.bounds(radial_log(r_lo).span()[0], radial_log(r_hi).span()[1])
            t_star = tau * ln_ratio
            ts_lo, ts_hi = t_star.span()
            reversal_bounds = [str(ts_lo), str(ts_hi)]
            e_peak = q_inf * t_star + tau_q_tr + q_inf * tau
            e_req = energy_at(duration)
            if melting_first:
                peak_safe = e_peak.span()[1] < e_solid
                peak_hit = e_peak.span()[0] >= e_solid
                end_safe = e_req.span()[0] > e_liquid
                end_hit = e_req.span()[1] <= e_liquid
            else:
                peak_safe = e_peak.span()[0] > e_liquid
                peak_hit = e_peak.span()[1] <= e_liquid
                end_safe = e_req.span()[1] < e_solid
                end_hit = e_req.span()[0] >= e_solid

            if peak_safe and end_safe:
                status = "coexisting"
                mod_lo = mod_hi = duration
                e_box = e_req
                t_final = body_temp_at_interval(duration, duration)
            elif peak_hit:
                limit = e_solid if melting_first else e_liquid
                # Strictly monotonic on [0, ts_lo] for every realization in the parameter box.
                upper_mono = min(duration, ts_lo)
                ex_lo, ex_hi = _bisect_threshold(
                    energy_at, limit, F(0), upper_mono, increasing=melting_first)
                if ex_lo is None:
                    status = "exhaustion_time_uncertain"
                    mod_lo, mod_hi = F(0), duration
                    e_lo = max(e_liquid, min(e_peak.span()[0], e_req.span()[0], F(0)))
                    e_hi = min(e_solid, max(e_peak.span()[1], e_req.span()[1], F(0)))
                    e_box = Box.bounds(e_lo, e_hi)
                    t_final = body_temp_at_interval(F(0), duration)
                else:
                    status = "exhausted"
                    exhausted_phase = "solid" if melting_first else "liquid"
                    # Even if near-tangent peak uncertainty leaves ex_hi unresolved on [0, ts_lo],
                    # peak_hit and opposite endpoint flow signs certify first exhaustion in
                    # [ex_lo, min(duration, ts_hi)] with exact event energy limit and zero remaining phase.
                    hi_bound = min(duration, ts_hi) if ex_hi is None else ex_hi
                    exhaustion_bounds = [str(ex_lo), str(hi_bound)]
                    mod_lo, mod_hi = ex_lo, hi_bound
                    e_box = Box.exact(limit)
                    t_final = body_temp_at_interval(mod_lo, mod_hi)
            elif peak_safe and end_hit:
                status = "exhausted"
                exhausted_phase = "liquid" if melting_first else "solid"
                limit = e_liquid if melting_first else e_solid
                # Analytic soundness proof for lo = min(duration, ts_lo) with lo_proved_safe=True
                # (stated for melting_first; freezing_first is the exact mirror image):
                # 1. Every realization omega satisfies 0 < ts_lo <= t*(omega) < duration.
                # 2. E(.; omega) is strictly increasing on [0, t*(omega)] from E(0; omega) = 0,
                #    so E(t; omega) > 0 >= e_liquid on (0, ts_lo] (including e_liquid = 0).
                # 3. After t*(omega), E(.; omega) is strictly decreasing, so it crosses e_liquid
                #    at most once on [ts_lo, duration].
                # 4. Hence every realization's true first crossing exceeds ts_lo; before(mid)
                #    holding implies no realization has crossed by mid, and reached(t) holding
                #    implies every realization has crossed by t. Interval dependency in
                #    energy_at(t) can make before(ts_lo) evaluate False even though ts_lo is
                #    analytically safe, so lo_proved_safe=True anchors the lower bracket at
                #    lower_mono and advances it above lower_mono only through before(mid).
                lower_mono = min(duration, ts_lo)
                ex_lo, ex_hi = _bisect_threshold(
                    energy_at, limit, lower_mono, duration,
                    increasing=not melting_first, lo_proved_safe=True)
                lo_bound = lower_mono if ex_lo is None else ex_lo
                hi_bound = duration if ex_hi is None else ex_hi
                exhaustion_bounds = [str(lo_bound), str(hi_bound)]
                mod_lo, mod_hi = lo_bound, hi_bound
                e_box = Box.exact(limit)
                t_final = body_temp_at_interval(mod_lo, mod_hi)
            else:
                status = "exhaustion_time_uncertain"
                mod_lo, mod_hi = F(0), duration
                e_lo = max(e_liquid, min(e_peak.span()[0], e_req.span()[0], F(0)))
                e_hi = min(e_solid, max(e_peak.span()[1], e_req.span()[1], F(0)))
                e_box = Box.bounds(e_lo, e_hi)
                t_final = body_temp_at_interval(F(0), duration)
        else:
            raise ValueError("latent heat-flow direction is unresolved")

    elo, ehi = e_box.span()
    mlo, mhi = elo / latent, ehi / latent

    result = {
        "schema": "sim_heat.offline_body_phase_bath_exchange/1",
        "phaseBathPort": phase_port,
        "bodyPort": body_port,
        "transitionTemperatureK": str(transition),
        "specificLatentHeatJPerKg": str(latent),
        "initialSolidKg": str(solid),
        "initialLiquidKg": str(liquid),
        "heatCapacityJPerK": str(capacity),
        "initialBodyTemperatureK": str(initial),
        "requestedDurationS": str(duration),
        "bodyEquilibriumTemperatureBoundsK": bounds(t_eq),
        "bodyTimeConstantBoundsS": bounds(tau),
        "initialBathInflowBoundsW": bounds(q0),
        "asymptoticBathInflowBoundsW": bounds(q_inf),
        "phaseProcess": process,
        "plateauStatus": status,
        "exhaustedPhase": exhausted_phase,
        "reversalTimeBoundsS": reversal_bounds,
        "exhaustionTimeBoundsS": exhaustion_bounds,
        "modeledDurationBoundsS": [str(mod_lo), str(mod_hi)],
        "finalBodyTemperatureBoundsK": bounds(t_final),
        "bodyEnergyChangeBoundsJ": bounds(Box.exact(capacity) * (t_final - initial)),
        "latentEnergyIntoBathBoundsJ": [str(elo), str(ehi)],
        "remainingSolidBoundsKg": [str(solid - mhi), str(solid - mlo)],
        "remainingLiquidBoundsKg": [str(liquid + mlo), str(liquid + mhi)],
        **offline_provenance(law),
    }
    return result


def investigate(inputs, phase_port, body_port, transition_k, latent_heat_j_per_kg,
                solid_kg, liquid_kg, capacity_j_per_k, initial_k, duration_s):
    return solve_from_law(
        terminal_response(*inputs), phase_port, body_port, transition_k,
        latent_heat_j_per_kg, solid_kg, liquid_kg, capacity_j_per_k, initial_k, duration_s,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "phase-port", "body-port",
                  "transition-k", "latent-heat-j-per-kg", "solid-kg", "liquid-kg",
                  "capacity-j-per-k", "initial-k", "duration-s"):
        p.add_argument("--" + field, required=True)
    a = p.parse_args()
    print(json.dumps(investigate(
        (a.study, a.root, a.facts, a.facts_sha256), a.phase_port, a.body_port,
        a.transition_k, a.latent_heat_j_per_kg, a.solid_kg, a.liquid_kg,
        a.capacity_j_per_k, a.initial_k, a.duration_s), indent=2))
