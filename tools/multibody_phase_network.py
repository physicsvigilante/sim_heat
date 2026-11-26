"""Coupled multi-body + phase-bath transient conduction on a pinned steady network.

Composes any pinned connected passive steady conduction network with arbitrary
per-terminal attachments of:
- ``lumped_body``: finite heat-capacity body (C_i > 0, initial T_i(0) >= 0)
- ``phase_bath``: isothermal coexisting two-phase bath (clamped at T_tr > 0)
- ``maintained``: fixed Dirichlet temperature reservoir (T_f >= 0)

Evolves the coupled N-body linear ODE + integrated temperatures in one certified
outward-rounded matrix exponential (``qualification.h1_n13.conduction.step_matrix``),
encloses every phase bath's integrated energy over subintervals using certified
maximum-principle Lipschitz bounds (catching intermediate non-monotonic overshoots
and multi-body reversals), and stops at first phase exhaustion without extrapolating
beyond the coexistence plateau.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from qualification.h1_n11.rational_dynamic_proof import apply
from qualification.h1_n13.conduction import ONE, ZERO, Box, step_matrix
from tools.join_thermal_networks import bounds
from tools.latent_heat_bath import phase_inputs
from tools.multiport_thermal_network import _symmetric_conductances
from simheat.enthalpy import (
    DEFAULT_MAX_BISECT_REFINEMENTS as DEFAULT_CONTINUATION_MAX_BISECT_REFINEMENTS,
    DEFAULT_MAX_EVENTS as DEFAULT_CONTINUATION_MAX_EVENTS,
    DEFAULT_MAX_PRUNE_REFINEMENTS as DEFAULT_CONTINUATION_MAX_PRUNE_REFINEMENTS,
    ENTHALPY_CONTINUATION_SCHEMA,
    solve_enthalpy_continuation,
)
from simheat.laws import validate_terminal_law
from tools.offline_investigation import PinnedSourceRef, _expect_exact_keys, validate_pinned_law
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response

MULTIBODY_SCHEMA = "sim_heat.offline_multibody_phase_network/1"
EVIDENCE_CATEGORY = "offline_analytical_calculation"
VALID_PORT_KINDS = ("lumped_body", "phase_bath", "maintained")
MAX_INITIAL_STEPS = 256
DEFAULT_MAX_PRUNE_REFINEMENTS = 160
DEFAULT_MAX_BISECT_REFINEMENTS = 48


def _validate_initial_steps(initial_steps):
    if isinstance(initial_steps, bool) or not isinstance(initial_steps, int) or not (1 <= initial_steps <= MAX_INITIAL_STEPS):
        raise ValueError(f"initial_steps must be an integer in [1, {MAX_INITIAL_STEPS}]")
    return initial_steps


def _validate_refinement_budget(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _box_union(boxes):
    return Box.bounds(min(b.span()[0] for b in boxes), max(b.span()[1] for b in boxes))


def _parse_ports(terminals, ports):
    if not isinstance(ports, dict) or set(ports) != set(terminals):
        raise ValueError("ports mapping must assign an attachment to every terminal in the pinned network")
    parsed = {}
    body_ports = []
    phase_ports = []
    maintained_ports = []

    for name in terminals:
        spec = ports[name]
        if not isinstance(spec, dict):
            raise ValueError(f"port {name!r} specification must be a mapping")
        kind = spec.get("kind")
        if kind not in VALID_PORT_KINDS:
            raise ValueError(f"port {name!r} has unsupported kind {kind!r}; expected one of {VALID_PORT_KINDS}")

        if kind == "lumped_body":
            _expect_exact_keys(
                spec,
                required=("kind", "heatCapacityJPerK", "initialBodyTemperatureK"),
                label=f"ports[{name}]",
            )
            cap = decimal_input(spec["heatCapacityJPerK"], f"heat capacity at {name}")
            if cap <= 0:
                raise ValueError(f"positive heat capacity required at {name}")
            t0 = decimal_input(spec["initialBodyTemperatureK"], f"initial temperature at {name}")
            parsed[name] = {"kind": "lumped_body", "capacity": cap, "t0": t0}
            body_ports.append(name)

        elif kind == "phase_bath":
            _expect_exact_keys(
                spec,
                required=(
                    "kind",
                    "transitionTemperatureK",
                    "specificLatentHeatJPerKg",
                    "initialSolidKg",
                    "initialLiquidKg",
                ),
                label=f"ports[{name}]",
            )
            tr, latent, solid, liquid, _ = phase_inputs(
                spec["transitionTemperatureK"],
                spec["specificLatentHeatJPerKg"],
                spec["initialSolidKg"],
                spec["initialLiquidKg"],
                "0",
                allow_pure=True,
            )
            parsed[name] = {
                "kind": "phase_bath",
                "transition": tr,
                "latent": latent,
                "solid": solid,
                "liquid": liquid,
                "e_solid": solid * latent,
                "e_liquid": -liquid * latent,
            }
            phase_ports.append(name)

        else:  # maintained
            _expect_exact_keys(spec, required=("kind", "temperatureK"), label=f"ports[{name}]")
            temp = decimal_input(spec["temperatureK"], f"maintained temperature at {name}")
            parsed[name] = {"kind": "maintained", "temp": temp}
            maintained_ports.append(name)

    if not body_ports:
        raise ValueError("at least one lumped_body port is required")
    return parsed, body_ports, phase_ports, maintained_ports


class _MultiBodyEvolution:
    """Exact outward-rounded matrix-exponential evaluator for coupled N-body + fixed-port ODE."""

    def __init__(self, terminals, parsed, body_ports, fixed_ports, w_net):
        self.terminals = terminals
        self.parsed = parsed
        self.body_ports = body_ports
        self.fixed_ports = fixed_ports
        self.w_net = w_net
        self.n = len(body_ports)
        self.body_idx = {name: i for i, name in enumerate(body_ports)}

        self.fixed_temps = {}
        for name in fixed_ports:
            p = parsed[name]
            self.fixed_temps[name] = p["transition"] if p["kind"] == "phase_bath" else p["temp"]

        all_temps = [parsed[b]["t0"] for b in body_ports] + list(self.fixed_temps.values())
        self.t_min = min(all_temps)
        self.t_max = max(all_temps)
        self.origin = self.t_min
        self.span = max(Fraction(1), self.t_max - self.t_min)

        self.u0 = [Box.exact((parsed[b]["t0"] - self.origin) / self.span) for b in body_ports]
        self.u_fixed = {f: Box.exact((t - self.origin) / self.span) for f, t in self.fixed_temps.items()}
        self.y0 = self.u0 + [ZERO] * self.n + [ONE]

        # Build the base (2N+1)x(2N+1) rate matrix A (in physical 1/s units for top block,
        # dimensionless integration dI/dt = u for middle block).
        dim = 2 * self.n + 1
        self.base_a = [[ZERO for _ in range(dim)] for _ in range(dim)]
        self.max_slope = []
        for i, b in enumerate(body_ports):
            cap = Box.exact(parsed[b]["capacity"])
            diag_w = ZERO
            affine_u = ZERO
            sum_w_hi = Fraction(0)
            for other in terminals:
                if other == b:
                    continue
                w_lo, w_hi = w_net[(b, other)]
                w_box = Box.bounds(w_lo, w_hi)
                sum_w_hi += w_hi
                diag_w = diag_w + w_box
                if other in self.body_idx:
                    self.base_a[i][self.body_idx[other]] = w_box / cap
                else:
                    affine_u = affine_u + w_box * self.u_fixed[other]
            self.base_a[i][i] = -diag_w / cap
            self.base_a[i][-1] = affine_u / cap
            self.base_a[self.n + i][i] = ONE
            # Global maximum-principle Lipschitz bound on |dT_i/dt| over all t >= 0.
            self.max_slope.append(sum_w_hi * (self.t_max - self.t_min) / parsed[b]["capacity"])

        self._cache = {}

    def state_at(self, t):
        """Return certified (body_temps, body_integrals, fixed_energies, fixed_flows) at time t >= 0."""
        if t in self._cache:
            return self._cache[t]
        if t == 0 or self.t_min == self.t_max:
            body_temps = [Box.exact(self.parsed[b]["t0"]) for b in self.body_ports]
            body_ints = [Box.exact(self.parsed[b]["t0"] * t) for b in self.body_ports]
        else:
            dim = 2 * self.n + 1
            scaled = [[self.base_a[r][c] * t for c in range(dim)] for r in range(dim)]
            # Normalize middle block so step_matrix sees O(1) entries: state[n+i] = (1/t) * int_0^t u_i ds.
            for i in range(self.n):
                scaled[self.n + i][i] = ONE
            y = apply(step_matrix(scaled), self.y0)
            body_temps = []
            for i in range(self.n):
                # Intersect with exact maximum-principle invariant [t_min, t_max].
                raw_t = y[i] * self.span + self.origin
                t_lo = max(self.t_min, raw_t.span()[0])
                t_hi = min(self.t_max, raw_t.span()[1])
                if t_lo > t_hi:
                    raise ValueError("body temperature enclosure violated maximum principle")
                body_temps.append(Box.bounds(t_lo, t_hi))
            # Physical temperature integral: int_0^t T_i(s) ds = t * (y[n+i] * span + origin).
            body_ints = [(y[self.n + i] * self.span + self.origin) * t for i in range(self.n)]

        fixed_energies = {}
        fixed_flows = {}
        for f in self.fixed_ports:
            tf = self.fixed_temps[f]
            e_f = ZERO
            q_f = ZERO
            for i, b in enumerate(self.body_ports):
                w_box = Box.bounds(*self.w_net[(f, b)])
                e_f = e_f + w_box * (body_ints[i] - tf * t)
                q_f = q_f + w_box * (body_temps[i] - tf)
            for other_f in self.fixed_ports:
                if other_f == f:
                    continue
                w_box = Box.bounds(*self.w_net[(f, other_f)])
                diff = self.fixed_temps[other_f] - tf
                e_f = e_f + w_box * (diff * t)
                q_f = q_f + w_box * diff
            fixed_energies[f] = e_f
            fixed_flows[f] = q_f

        # Verify global energy conservation at time t: sum C_i*(T_i(t)-T_i(0)) + sum E_f(t) contains 0.
        body_du = sum(
            (Box.exact(self.parsed[b]["capacity"]) * (body_temps[i] - self.parsed[b]["t0"])
             for i, b in enumerate(self.body_ports)),
            ZERO,
        )
        fixed_sum = sum((fixed_energies[f] for f in self.fixed_ports), ZERO)
        if not (body_du + fixed_sum).contains_zero():
            raise ValueError("multi-body transient global energy conservation check failed")

        result = (body_temps, body_ints, fixed_energies, fixed_flows)
        self._cache[t] = result
        return result

    def subinterval_enclosures_with_flows(self, t_a, t_b, tracked_fixed_ports):
        """Certified enclosures of body temps, fixed-port energies, and fixed-port flows on [t_a, t_b]."""
        h = t_b - t_a
        temps_a, _, energies_a, _ = self.state_at(t_a)
        temps_b, _, energies_b, _ = self.state_at(t_b)

        sub_temps = []
        for i in range(self.n):
            v_h = self.max_slope[i] * h
            lo = max(self.t_min, temps_a[i].span()[0] - v_h, temps_b[i].span()[0] - v_h)
            hi = min(self.t_max, temps_a[i].span()[1] + v_h, temps_b[i].span()[1] + v_h)
            if lo > hi:
                raise ValueError("subinterval temperature enclosure is inconsistent")
            sub_temps.append(Box.bounds(lo, hi))

        sub_energies = {}
        sub_flows = {}
        for p in tracked_fixed_ports:
            tp = self.fixed_temps[p]
            q_sub = ZERO
            for i, b in enumerate(self.body_ports):
                q_sub = q_sub + Box.bounds(*self.w_net[(p, b)]) * (sub_temps[i] - tp)
            for other_f in self.fixed_ports:
                if other_f == p:
                    continue
                q_sub = q_sub + Box.bounds(*self.w_net[(p, other_f)]) * (self.fixed_temps[other_f] - tp)
            q_lo, q_hi = q_sub.span()
            ea_lo, ea_hi = energies_a[p].span()
            eb_lo, eb_hi = energies_b[p].span()
            e_lo = max(ea_lo + min(Fraction(0), q_lo) * h, eb_lo - max(Fraction(0), q_hi) * h)
            e_hi = min(ea_hi + max(Fraction(0), q_hi) * h, eb_hi - min(Fraction(0), q_lo) * h)
            if e_lo > e_hi:
                raise ValueError("subinterval phase-bath energy enclosure is inconsistent")
            sub_energies[p] = Box.bounds(e_lo, e_hi)
            sub_flows[p] = q_sub
        return sub_temps, sub_energies, sub_flows

    def subinterval_enclosures(self, t_a, t_b, phase_ports):
        """Certified enclosures of body temps and phase-bath energies for ALL tau in [t_a, t_b]."""
        sub_temps, sub_energies, _ = self.subinterval_enclosures_with_flows(t_a, t_b, phase_ports)
        return sub_temps, sub_energies


def _bath_exhausted_at(e_box, p_spec):
    lo, hi = e_box.span()
    if lo >= p_spec["e_solid"]:
        return "solid"
    if hi <= p_spec["e_liquid"]:
        return "liquid"
    return None


def _bath_safe_on(e_box, p_spec, *, t_a=None, q_sub=None):
    lo, hi = e_box.span()
    if p_spec["solid"] > 0 and p_spec["liquid"] > 0:
        return hi < p_spec["e_solid"] and lo > p_spec["e_liquid"]
    if p_spec["liquid"] == 0:
        # Pure solid (e_liquid == 0, e_solid > 0): opposite-boundary check always applies.
        if hi >= p_spec["e_solid"]:
            return False
        if lo > 0:
            return True
        if q_sub is not None:
            q_lo, q_hi = q_sub.span()
            if q_lo == 0 and q_hi == 0 and lo == 0 and hi == 0:
                return True
            # CR-10: only a cell [0, b] anchored at t = 0 with strictly inward flux relaxes lo > 0.
            if t_a == 0 and q_lo > 0:
                return True
        return False
    # Pure liquid (e_solid == 0, e_liquid < 0): mirror of pure solid.
    if lo <= p_spec["e_liquid"]:
        return False
    if hi < 0:
        return True
    if q_sub is not None:
        q_lo, q_hi = q_sub.span()
        if q_lo == 0 and q_hi == 0 and lo == 0 and hi == 0:
            return True
        if t_a == 0 and q_hi < 0:
            return True
    return False


def _cell_bath_hits(e_box, p_spec, *, t_a=None, q_sub=None):
    """Return (hit_solid, hit_liquid) on a cell, avoiding spurious t=0 boundary hits on strictly inward [0, b]."""
    lo, hi = e_box.span()
    hit_solid = hi >= p_spec["e_solid"]
    hit_liquid = lo <= p_spec["e_liquid"]
    if t_a == 0 and q_sub is not None:
        q_lo, q_hi = q_sub.span()
        if p_spec["liquid"] == 0 and q_lo > 0:
            hit_liquid = False
        if p_spec["solid"] == 0 and q_hi < 0:
            hit_solid = False
    return hit_solid, hit_liquid


def _locate_first_exhaustion(
    evo,
    phase_ports,
    parsed,
    duration,
    *,
    initial_steps=16,
    max_prune_refinements=DEFAULT_MAX_PRUNE_REFINEMENTS,
    max_bisect_refinements=DEFAULT_MAX_BISECT_REFINEMENTS,
):
    """Locate certified first phase-bath exhaustion on [0, duration] via adaptive interval subdivision.

    Returns (sys_status, mod_lo, mod_hi, first_exhausted_candidates, exhausted_phase_by_port,
             body_temps_at_stop, fixed_energies_at_stop, solver_metadata, exhausted_at_start_ports).
    """
    temps_0, _, energies_0, q_init = evo.state_at(Fraction(0))

    # Regime (b) checked FIRST (even when duration == 0, per F-04 / CR-11):
    # any pure-phase bath with certified initial flow leaving coexistence is exhausted at t = 0.
    start_exh_ports = []
    start_exh_phase = {}
    for p in phase_ports:
        p_spec = parsed[p]
        q0_lo, q0_hi = q_init[p].span()
        if p_spec["liquid"] == 0 and q0_hi < 0:
            start_exh_ports.append(p)
            start_exh_phase[p] = "liquid"
        elif p_spec["solid"] == 0 and q0_lo > 0:
            start_exh_ports.append(p)
            start_exh_phase[p] = "solid"
    if start_exh_ports:
        meta = {
            "terminationReason": "resolved",
            "pruneRefinementsUsed": 0,
            "bisectRefinementsUsed": 0,
            "modeledDurationWidthS": "0",
        }
        return (
            "exhausted",
            Fraction(0),
            Fraction(0),
            start_exh_ports,
            start_exh_phase,
            temps_0,
            energies_0,
            meta,
            set(start_exh_ports),
        )

    if duration == 0:
        meta = {
            "terminationReason": "resolved",
            "pruneRefinementsUsed": 0,
            "bisectRefinementsUsed": 0,
            "modeledDurationWidthS": "0",
        }
        return "coexisting", Fraction(0), Fraction(0), [], {}, temps_0, energies_0, meta, set()

    # Build initial uniform grid on [0, duration].
    grid = [duration * k / initial_steps for k in range(initial_steps + 1)]

    # Scan left-to-right to find the earliest subinterval not proven strictly safe.
    first_unsafe_idx = None
    for k in range(initial_steps):
        _, sub_e, sub_q = evo.subinterval_enclosures_with_flows(grid[k], grid[k + 1], phase_ports)
        if not all(_bath_safe_on(sub_e[p], parsed[p], t_a=grid[k], q_sub=sub_q[p]) for p in phase_ports):
            first_unsafe_idx = k
            break

    if first_unsafe_idx is None:
        # Mathematically proven: NO phase bath exhausts anywhere on [0, duration] (covers exact equilibrium too).
        temps, _, energies, _ = evo.state_at(duration)
        meta = {
            "terminationReason": "resolved",
            "pruneRefinementsUsed": 0,
            "bisectRefinementsUsed": 0,
            "modeledDurationWidthS": "0",
        }
        return "coexisting", duration, duration, [], {}, temps, energies, meta, set()

    # Regime (d) (OQ-C3 closed decision): if any pure bath has unresolved or zero initial flux
    # (and did not already prove exact equilibrium above), departure from t = 0 cannot be certified
    # by any cell [0, b']. Return conservative exhaustion_time_uncertain modeled from t = 0.
    unresolved_pure_start = []
    for p in phase_ports:
        p_spec = parsed[p]
        if p_spec["liquid"] == 0 or p_spec["solid"] == 0:
            q0_lo, q0_hi = q_init[p].span()
            if q0_lo <= 0 <= q0_hi:
                unresolved_pure_start.append(p)
    if unresolved_pure_start:
        all_fixed = evo.fixed_ports
        cell_temps = []
        cell_fixed = []
        cell_flows = []
        for k in range(initial_steps):
            ct, cf, cq = evo.subinterval_enclosures_with_flows(grid[k], grid[k + 1], all_fixed)
            cell_temps.append(ct)
            cell_fixed.append(cf)
            cell_flows.append(cq)
        temps_end, _, energies_end, _ = evo.state_at(duration)
        stop_temps = [_box_union([ct[i] for ct in cell_temps] + [temps_end[i]]) for i in range(evo.n)]
        stop_fixed_raw = {f: _box_union([cf[f] for cf in cell_fixed] + [energies_end[f]]) for f in all_fixed}
        candidates = []
        for p in phase_ports:
            if p in unresolved_pure_start or any(
                not _bath_safe_on(cell_fixed[k][p], parsed[p], t_a=grid[k], q_sub=cell_flows[k][p])
                for k in range(initial_steps)
            ):
                candidates.append(p)
        stop_fixed = dict(stop_fixed_raw)
        for p in phase_ports:
            p_spec = parsed[p]
            lo, hi = stop_fixed_raw[p].span()
            stop_fixed[p] = Box.bounds(
                max(p_spec["e_liquid"], min(p_spec["e_solid"], lo)),
                max(p_spec["e_liquid"], min(p_spec["e_solid"], hi)),
            )
        meta = {
            "terminationReason": "resolved",
            "pruneRefinementsUsed": 0,
            "bisectRefinementsUsed": 0,
            "modeledDurationWidthS": str(duration),
        }
        return (
            "exhaustion_time_uncertain",
            Fraction(0),
            duration,
            candidates,
            {},
            stop_temps,
            stop_fixed,
            meta,
            set(),
        )

    # Check if any grid point at or after first_unsafe_idx+1 certifies exhaustion.
    cert_hi = None
    stop_idx = initial_steps
    for k in range(first_unsafe_idx + 1, initial_steps + 1):
        _, _, energies_k, _ = evo.state_at(grid[k])
        if any(_bath_exhausted_at(energies_k[p], parsed[p]) is not None for p in phase_ports):
            cert_hi = grid[k]
            stop_idx = k
            break

    # Adaptive left-to-right branch-and-prune subdivision with separate pruning and bisection budgets.
    # Invariant: every point in [0, intervals[0][0]) (or [0, duration] if intervals is empty
    # and cert_hi is None) is mathematically proven strictly safe for ALL phase baths.
    intervals = []
    for k in range(first_unsafe_idx, stop_idx):
        _, sub_e, sub_q = evo.subinterval_enclosures_with_flows(grid[k], grid[k + 1], phase_ports)
        if not all(_bath_safe_on(sub_e[p], parsed[p], t_a=grid[k], q_sub=sub_q[p]) for p in phase_ports):
            intervals.append((grid[k], grid[k + 1]))

    bisect_tol = max(Fraction(1, 10**9), duration / (10**9))
    uncertain_tol = max(Fraction(1, 10**6), duration / (10**6))
    prune_used = 0
    bisect_used = 0
    budget_exhausted = False

    # Phase 1: prune earlier unsafe cells (e.g., near-miss peaks) before bisecting the exhaustion bracket.
    while intervals:
        if cert_hi is not None and len(intervals) == 1 and intervals[0][1] == cert_hi:
            break
        a, b = intervals[0]
        if cert_hi is None and b - a <= uncertain_tol:
            break
        if prune_used >= max_prune_refinements:
            budget_exhausted = True
            break
        prune_used += 1
        intervals.pop(0)
        mid = (a + b) / 2
        _, _, energies_mid, _ = evo.state_at(mid)
        if any(_bath_exhausted_at(energies_mid[p], parsed[p]) is not None for p in phase_ports):
            cert_hi = mid
            intervals = [(lo, min(hi, mid)) for lo, hi in intervals if lo < mid]
            _, sub_left, q_left = evo.subinterval_enclosures_with_flows(a, mid, phase_ports)
            if not all(_bath_safe_on(sub_left[p], parsed[p], t_a=a, q_sub=q_left[p]) for p in phase_ports):
                intervals.insert(0, (a, mid))
            continue

        new_front = []
        _, sub_left, q_left = evo.subinterval_enclosures_with_flows(a, mid, phase_ports)
        if not all(_bath_safe_on(sub_left[p], parsed[p], t_a=a, q_sub=q_left[p]) for p in phase_ports):
            new_front.append((a, mid))
        _, sub_right, q_right = evo.subinterval_enclosures_with_flows(mid, b, phase_ports)
        if not all(_bath_safe_on(sub_right[p], parsed[p], t_a=mid, q_sub=q_right[p]) for p in phase_ports):
            new_front.append((mid, b))
        intervals = new_front + intervals

    # Phase 2: bisect the certified exhaustion bracket under its own budget.
    if cert_hi is not None and intervals:
        while intervals:
            if cert_hi - intervals[0][0] <= bisect_tol:
                break
            if bisect_used >= max_bisect_refinements:
                budget_exhausted = True
                break
            if len(intervals) > 1 and intervals[-1][1] == cert_hi and intervals[-1][1] - intervals[-1][0] > bisect_tol:
                idx = len(intervals) - 1
            elif not budget_exhausted:
                idx = 0
            else:
                break
            a, b = intervals.pop(idx)
            if b - a <= bisect_tol:
                intervals.insert(idx, (a, b))
                break
            bisect_used += 1
            mid = (a + b) / 2
            _, _, energies_mid, _ = evo.state_at(mid)
            if any(_bath_exhausted_at(energies_mid[p], parsed[p]) is not None for p in phase_ports):
                cert_hi = mid
                intervals = [(lo, min(hi, mid)) for lo, hi in intervals if lo < mid]
                _, sub_left, q_left = evo.subinterval_enclosures_with_flows(a, mid, phase_ports)
                if not all(_bath_safe_on(sub_left[p], parsed[p], t_a=a, q_sub=q_left[p]) for p in phase_ports):
                    intervals.insert(min(idx, len(intervals)), (a, mid))
                continue

            new_cells = []
            _, sub_left, q_left = evo.subinterval_enclosures_with_flows(a, mid, phase_ports)
            if not all(_bath_safe_on(sub_left[p], parsed[p], t_a=a, q_sub=q_left[p]) for p in phase_ports):
                new_cells.append((a, mid))
            _, sub_right, q_right = evo.subinterval_enclosures_with_flows(mid, b, phase_ports)
            if not all(_bath_safe_on(sub_right[p], parsed[p], t_a=mid, q_sub=q_right[p]) for p in phase_ports):
                new_cells.append((mid, b))
            intervals[idx:idx] = new_cells

    if not intervals and cert_hi is None:
        temps, _, energies, _ = evo.state_at(duration)
        meta = {
            "terminationReason": "resolved",
            "pruneRefinementsUsed": prune_used,
            "bisectRefinementsUsed": bisect_used,
            "modeledDurationWidthS": "0",
        }
        return "coexisting", duration, duration, [], {}, temps, energies, meta, set()

    safe_hi = intervals[0][0] if intervals else cert_hi
    all_fixed = evo.fixed_ports
    cell_temps = []
    cell_fixed = []
    cell_flows = []
    for a, b in intervals:
        ct, cf, cq = evo.subinterval_enclosures_with_flows(a, b, all_fixed)
        cell_temps.append(ct)
        cell_fixed.append(cf)
        cell_flows.append(cq)

    if cert_hi is not None:
        # Exhaustion is mathematically proven in union(intervals) U {cert_hi}.
        temps_end, _, energies_end, _ = evo.state_at(cert_hi)
        stop_temps = [_box_union([ct[i] for ct in cell_temps] + [temps_end[i]]) for i in range(evo.n)]
        stop_fixed_raw = {f: _box_union([cf[f] for cf in cell_fixed] + [energies_end[f]]) for f in all_fixed}
        candidates = []
        exh_phase_by_port = {}
        for p in phase_ports:
            p_spec = parsed[p]
            hit_solid = energies_end[p].span()[1] >= p_spec["e_solid"]
            hit_liquid = energies_end[p].span()[0] <= p_spec["e_liquid"]
            for idx_c, (a, _) in enumerate(intervals):
                hs, hl = _cell_bath_hits(cell_fixed[idx_c][p], p_spec, t_a=a, q_sub=cell_flows[idx_c][p])
                hit_solid = hit_solid or hs
                hit_liquid = hit_liquid or hl
            if hit_solid or hit_liquid:
                candidates.append(p)
                if hit_solid and not hit_liquid:
                    exh_phase_by_port[p] = "solid"
                elif hit_liquid and not hit_solid:
                    exh_phase_by_port[p] = "liquid"
        # Clip each bath's energy to its physical inventory bounds; if unique first-exhausted bath
        # with resolved exhausted phase, its exact event energy at exhaustion is e_solid or e_liquid.
        stop_fixed = dict(stop_fixed_raw)
        for p in phase_ports:
            p_spec = parsed[p]
            if candidates == [p] and p in exh_phase_by_port:
                limit = p_spec["e_solid"] if exh_phase_by_port[p] == "solid" else p_spec["e_liquid"]
                stop_fixed[p] = Box.exact(limit)
            else:
                lo, hi = stop_fixed_raw[p].span()
                stop_fixed[p] = Box.bounds(
                    max(p_spec["e_liquid"], min(p_spec["e_solid"], lo)),
                    max(p_spec["e_liquid"], min(p_spec["e_solid"], hi)),
                )
        meta = {
            "terminationReason": "refinement_budget" if budget_exhausted else "resolved",
            "pruneRefinementsUsed": prune_used,
            "bisectRefinementsUsed": bisect_used,
            "modeledDurationWidthS": str(cert_hi - safe_hi),
        }
        return "exhausted", safe_hi, cert_hi, candidates, exh_phase_by_port, stop_temps, stop_fixed, meta, set()

    # Exhaustion could not be ruled out on union(intervals) nor certified at any point;
    # any realization that never exhausts stops at duration, so include state_at(duration).
    temps_end, _, energies_end, _ = evo.state_at(duration)
    stop_temps = [_box_union([ct[i] for ct in cell_temps] + [temps_end[i]]) for i in range(evo.n)]
    stop_fixed_raw = {f: _box_union([cf[f] for cf in cell_fixed] + [energies_end[f]]) for f in all_fixed}
    candidates = []
    for p in phase_ports:
        if any(
            not _bath_safe_on(cell_fixed[idx_c][p], parsed[p], t_a=a, q_sub=cell_flows[idx_c][p])
            for idx_c, (a, _) in enumerate(intervals)
        ) or not _bath_safe_on(energies_end[p], parsed[p]):
            candidates.append(p)
    stop_fixed = dict(stop_fixed_raw)
    for p in phase_ports:
        p_spec = parsed[p]
        lo, hi = stop_fixed_raw[p].span()
        stop_fixed[p] = Box.bounds(
            max(p_spec["e_liquid"], min(p_spec["e_solid"], lo)),
            max(p_spec["e_liquid"], min(p_spec["e_solid"], hi)),
        )
    meta = {
        "terminationReason": "refinement_budget" if budget_exhausted else "resolved",
        "pruneRefinementsUsed": prune_used,
        "bisectRefinementsUsed": bisect_used,
        "modeledDurationWidthS": str(duration - safe_hi),
    }
    return "exhaustion_time_uncertain", safe_hi, duration, candidates, {}, stop_temps, stop_fixed, meta, set()


def solve_from_law(
    law,
    ports,
    duration_s,
    *,
    initial_steps=16,
    max_prune_refinements=DEFAULT_MAX_PRUNE_REFINEMENTS,
    max_bisect_refinements=DEFAULT_MAX_BISECT_REFINEMENTS,
):
    """Compose and solve a coupled multi-body + phase-bath transient over a validated pinned law."""
    _validate_initial_steps(initial_steps)
    _validate_refinement_budget(max_prune_refinements, "max_prune_refinements")
    _validate_refinement_budget(max_bisect_refinements, "max_bisect_refinements")
    resolved_law, provenance = validate_terminal_law(law)
    law = resolved_law.to_engine_law()
    terminals = list(law["terminals"])
    parsed, body_ports, phase_ports, maintained_ports = _parse_ports(terminals, ports)
    duration = decimal_input(duration_s, "duration")
    w_net = _symmetric_conductances(terminals, law)
    fixed_ports = phase_ports + maintained_ports

    evo = _MultiBodyEvolution(terminals, parsed, body_ports, fixed_ports, w_net)
    _, _, _, q_init_fixed = evo.state_at(Fraction(0))

    if phase_ports:
        (
            sys_status,
            mod_lo,
            mod_hi,
            candidates,
            exh_phase_by_port,
            body_temps_stop,
            fixed_energies_stop,
            solver_meta,
            exhausted_at_start_ports,
        ) = _locate_first_exhaustion(
            evo,
            phase_ports,
            parsed,
            duration,
            initial_steps=initial_steps,
            max_prune_refinements=max_prune_refinements,
            max_bisect_refinements=max_bisect_refinements,
        )
    else:
        sys_status = None
        mod_lo = mod_hi = duration
        candidates = []
        exh_phase_by_port = {}
        body_temps_stop, _, fixed_energies_stop, _ = evo.state_at(duration)
        solver_meta = {
            "terminationReason": "resolved",
            "pruneRefinementsUsed": 0,
            "bisectRefinementsUsed": 0,
            "modeledDurationWidthS": "0",
        }
        exhausted_at_start_ports = set()

    source_ref_temps = (
        {t: str(resolved_law.reference_temperatures_k[t]) for t in terminals}
        if resolved_law.reference_temperatures_k is not None
        else None
    )
    port_kinds = {t: parsed[t]["kind"] for t in terminals}
    active_bcs = {}
    ports_out = {}

    for i, b in enumerate(body_ports):
        p = parsed[b]
        tf_box = body_temps_stop[i]
        du_box = Box.exact(p["capacity"]) * (tf_box - p["t0"])
        active_bcs[b] = {
            "role": "lumped_body",
            "constraint": "coupled_lumped_transient_ode",
            "initialTemperatureK": str(p["t0"]),
            "finalTemperatureBoundsK": bounds(tf_box),
        }
        ports_out[b] = {
            "kind": "lumped_body",
            "heatCapacityJPerK": str(p["capacity"]),
            "initialBodyTemperatureK": str(p["t0"]),
            "finalBodyTemperatureBoundsK": bounds(tf_box),
            "bodyEnergyChangeBoundsJ": bounds(du_box),
            "energySignConvention": "into_body_positive",
        }

    for f in maintained_ports:
        p = parsed[f]
        active_bcs[f] = {
            "role": "maintained",
            "constraint": "fixed_dirichlet",
            "temperatureK": str(p["temp"]),
        }
        e_m = fixed_energies_stop[f]
        ports_out[f] = {
            "kind": "maintained",
            "temperatureK": str(p["temp"]),
            "initialInflowFromNetworkBoundsW": bounds(q_init_fixed[f]),
            "integratedEnergyIntoReservoirBoundsJ": bounds(e_m),
            "energySignConvention": "into_maintained_reservoir_positive",
        }

    for p_name in phase_ports:
        p = parsed[p_name]
        e_box = fixed_energies_stop[p_name]
        e_lo, e_hi = e_box.span()
        m_lo, m_hi = e_lo / p["latent"], e_hi / p["latent"]
        if p_name in exhausted_at_start_ports:
            stop_status = "exhausted"
            req_status = "exhausted"
            port_exh_phase = exh_phase_by_port.get(p_name)
        elif sys_status == "coexisting":
            stop_status = "coexisting"
            req_status = "coexisting"
            port_exh_phase = None
        elif sys_status == "exhausted" and candidates == [p_name]:
            stop_status = "exhausted"
            req_status = "exhausted"
            port_exh_phase = exh_phase_by_port.get(p_name)
        elif sys_status == "exhausted" and p_name in candidates:
            stop_status = "exhaustion_time_uncertain"
            req_status = "exhaustion_time_uncertain"
            port_exh_phase = None
        elif sys_status == "exhausted":
            stop_status = "coexisting"
            req_status = "not_modeled_after_system_exhaustion"
            port_exh_phase = None
        else:
            stop_status = "exhaustion_time_uncertain" if p_name in candidates else "coexisting"
            req_status = "not_certified_beyond_possible_exhaustion"
            port_exh_phase = None
        active_bcs[p_name] = {
            "role": "phase_bath",
            "constraint": "clamped_during_coexistence",
            "temperatureK": str(p["transition"]),
        }
        ports_out[p_name] = {
            "kind": "phase_bath",
            "transitionTemperatureK": str(p["transition"]),
            "specificLatentHeatJPerKg": str(p["latent"]),
            "initialSolidKg": str(p["solid"]),
            "initialLiquidKg": str(p["liquid"]),
            "initialBathInflowBoundsW": bounds(q_init_fixed[p_name]),
            "plateauStatusAtModeledStop": stop_status,
            "statusAtRequestedDuration": req_status,
            "exhaustedAtStart": p_name in exhausted_at_start_ports,
            "exhaustedPhase": port_exh_phase,
            "latentEnergyIntoBathBoundsJ": [str(e_lo), str(e_hi)],
            "remainingSolidBoundsKg": [str(p["solid"] - m_hi), str(p["solid"] - m_lo)],
            "remainingLiquidBoundsKg": [str(p["liquid"] + m_lo), str(p["liquid"] + m_hi)],
            "energySignConvention": "into_phase_bath_positive",
        }

    phase_system = None
    if phase_ports:
        phase_system = {
            "phaseBathPorts": phase_ports,
            "requestedDurationS": str(duration),
            "plateauStatus": sys_status,
            "exhaustedAtStart": bool(exhausted_at_start_ports),
            "postExhaustionModeled": False,
            "firstExhaustionTimeBoundsS": [str(mod_lo), str(mod_hi)] if sys_status == "exhausted" else None,
            "firstExhaustedCandidatePorts": candidates,
            "modeledDurationBoundsS": [str(mod_lo), str(mod_hi)],
        }

    source_identity = (
        {k: provenance[k] for k in SOURCE_HASH_KEYS}
        if all(k in provenance for k in SOURCE_HASH_KEYS)
        else {
            "derivedLawSchema": provenance["derivedLawSchema"],
            "derivedLawSha256": provenance["derivedLawSha256"],
            "derivedLawLineage": provenance["derivedLawLineage"],
        }
    )

    return {
        "schema": MULTIBODY_SCHEMA,
        "evidence": {
            "category": EVIDENCE_CATEGORY,
            "sourceIdentity": source_identity,
            **{k: False for k in OFFLINE_FLAG_KEYS},
        },
        "network": {
            "terminals": terminals,
            "portKinds": port_kinds,
            "sourceLawReferenceTemperaturesK": source_ref_temps,
            "activeBoundaryConditions": active_bcs,
        },
        "requestedDurationS": str(duration),
        "modeledDurationBoundsS": [str(mod_lo), str(mod_hi)],
        "ports": ports_out,
        "phaseSystem": phase_system,
        "solverMetadata": solver_meta,
        **provenance,
    }


def investigate(
    inputs,
    ports,
    duration_s,
    *,
    initial_steps=16,
    max_prune_refinements=DEFAULT_MAX_PRUNE_REFINEMENTS,
    max_bisect_refinements=DEFAULT_MAX_BISECT_REFINEMENTS,
):
    """Resolve a pinned file-backed source tuple/PinnedSourceRef and solve the coupled multi-body ODE."""
    _validate_initial_steps(initial_steps)
    law = inputs.resolve_law() if isinstance(inputs, PinnedSourceRef) else terminal_response(*inputs)
    return solve_from_law(
        law,
        ports,
        duration_s,
        initial_steps=initial_steps,
        max_prune_refinements=max_prune_refinements,
        max_bisect_refinements=max_bisect_refinements,
    )


def solve_continuation_from_law(
    law,
    ports,
    duration_s,
    *,
    initial_steps=16,
    max_events=DEFAULT_CONTINUATION_MAX_EVENTS,
    max_prune_refinements=DEFAULT_CONTINUATION_MAX_PRUNE_REFINEMENTS,
    max_bisect_refinements=DEFAULT_CONTINUATION_MAX_BISECT_REFINEMENTS,
):
    """Solve coupled multi-body / multi-phase linear enthalpy-mode continuation (M04)."""
    return solve_enthalpy_continuation(
        law,
        ports,
        duration_s,
        initial_steps=initial_steps,
        max_events=max_events,
        max_prune_refinements=max_prune_refinements,
        max_bisect_refinements=max_bisect_refinements,
    )


def investigate_continuation(
    inputs,
    ports,
    duration_s,
    *,
    initial_steps=16,
    max_events=DEFAULT_CONTINUATION_MAX_EVENTS,
    max_prune_refinements=DEFAULT_CONTINUATION_MAX_PRUNE_REFINEMENTS,
    max_bisect_refinements=DEFAULT_CONTINUATION_MAX_BISECT_REFINEMENTS,
):
    """Resolve a pinned file-backed source tuple/PinnedSourceRef and solve enthalpy-mode continuation."""
    law = inputs.resolve_law() if isinstance(inputs, PinnedSourceRef) else terminal_response(*inputs)
    return solve_continuation_from_law(
        law,
        ports,
        duration_s,
        initial_steps=initial_steps,
        max_events=max_events,
        max_prune_refinements=max_prune_refinements,
        max_bisect_refinements=max_bisect_refinements,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="Path to JSON multi-body phase-network request")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
    _expect_exact_keys(
        payload,
        required=("source", "ports", "durationS"),
        optional=("initialSteps",),
        label="request",
    )
    src = payload["source"]
    steps = _validate_initial_steps(payload.get("initialSteps", 16))
    if isinstance(src, dict) and "studyPath" in src:
        _expect_exact_keys(
            src,
            required=("studyPath", "rootPath", "factsPath", "factsSha256"),
            label="request.source",
        )
        ref = PinnedSourceRef(src["studyPath"], src["rootPath"], src["factsPath"], src["factsSha256"])
        res = investigate(ref, payload["ports"], payload["durationS"], initial_steps=steps)
    else:
        res = solve_from_law(src, payload["ports"], payload["durationS"], initial_steps=steps)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
