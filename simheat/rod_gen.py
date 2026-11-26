"""Certified uniform rod heat generation Norton reduction and parabolic peak recovery (M06).

Given a connected storage-free conduction rod graph with terminals ``T``, optional internal
junctions ``J``, exact or interval rod conductances ``G_r = [g_lo, g_hi]``, and optional
nonnegative uniform heat generation ``P_r >= 0`` (W) per rod:
1. Computes exact or barrier-certified harmonic influence weights ``H_{k,i} in [0, 1]`` for every
   internal junction ``k in J`` and terminal ``i in T``.
2. Reduces distributed rod generation to certified nonnegative terminal Norton heat injections
   ``I_Norton[i] = s_i + sum_{k in J} H_{k,i} * s_k`` (W, positive INTO terminal ``i``), where
   ``s_u = sum_{r incident to u} P_r / 2``, verifying ``sum_i I_Norton[i] contains sum_r P_r``.
3. Given certified terminal temperature enclosures ``T_i = [lo, hi]``, recovers certified internal
   junction temperature enclosures ``T_k`` (exact rational Gaussian elimination for exact point rods;
   certified monotone M-matrix Gauss-Seidel with residual post-condition for interval rods) and
   exact monotone per-rod parabolic peak temperatures and peak positions.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Any

from simheat.core import Box, ZERO, pi_rational_enclosure
from simheat.laws import _monotone_junction_enclosure, _outward_clamp_fraction, _parse_positive_param
from tools.join_thermal_networks import bounds
from tools.multiport_thermal_network import _solve_exact_linear_fractions as _exact_linear_solve
from tools.radiating_surface import decimal_input


@dataclass(frozen=True)
class RodGenEdge:
    name: str
    a: str
    b: str
    g_lo: Fraction
    g_hi: Fraction
    power_w: Fraction


@dataclass(frozen=True)
class RodGenerationModel:
    """Immutable certified Norton reduction and peak-recovery model for a heated rod graph."""

    nodes: tuple[str, ...]
    terminals: tuple[str, ...]
    junctions: tuple[str, ...]
    edges: tuple[RodGenEdge, ...]
    total_generated_power_w: Fraction
    terminal_injections_w: dict[str, tuple[Fraction, Fraction]]
    endpoint_injections_w: dict[str, Fraction]
    is_exact_point: bool

    def recover_profiles(
        self,
        terminal_temps: dict[str, tuple[Fraction, Fraction]],
        *,
        probe: tuple[str, Fraction] | None = None,
    ) -> dict[str, Any]:
        """Recover certified internal junction temperatures and per-rod parabolic peaks."""
        if set(terminal_temps) != set(self.terminals):
            raise ValueError("terminal_temps keys must match RodGenerationModel.terminals")

        node_temps: dict[str, tuple[Fraction, Fraction]] = dict(terminal_temps)

        if self.junctions:
            j_temps = _solve_junction_temperatures_with_sources(
                self.junctions,
                terminal_temps,
                self.edges,
                self.endpoint_injections_w,
                exact_point=self.is_exact_point and all(lo == hi for lo, hi in terminal_temps.values()),
            )
            node_temps.update(j_temps)

        rod_peaks: dict[str, Any] = {}
        probe_out: dict[str, Any] | None = None
        for edge in self.edges:
            al, ah = node_temps[edge.a]
            bl, bh = node_temps[edge.b]
            p = edge.power_w
            curve_lo = p / (2 * edge.g_hi)
            curve_hi = p / (2 * edge.g_lo)

            hottest_lo = _parabolic_peak(al, bl, curve_lo)
            hottest_hi = _parabolic_peak(ah, bh, curve_hi)

            if p > 0:
                xs = [
                    max(Fraction(0), min(Fraction(1), (Fraction(1) + d / c) / 2))
                    for d, c in product((bl - ah, bh - al), (curve_lo, curve_hi))
                ]
                pos_lo, pos_hi = min(xs), max(xs)
            elif al > bh:
                pos_lo = pos_hi = Fraction(0)
            elif bl > ah:
                pos_lo = pos_hi = Fraction(1)
            else:
                pos_lo, pos_hi = Fraction(0), Fraction(1)

            rod_peaks[edge.name] = {
                "fromNode": edge.a,
                "toNode": edge.b,
                "generatedPowerW": str(p),
                "peakTemperatureBoundsK": [str(hottest_lo), str(hottest_hi)],
                "peakPositionFractionFromABounds": [str(pos_lo), str(pos_hi)],
            }

            if probe is not None and probe[0] == edge.name:
                x = probe[1]
                a_box = Box.bounds(al, ah)
                b_box = Box.bounds(bl, bh)
                c_box = Box.bounds(curve_lo, curve_hi)
                g_box = Box.bounds(edge.g_lo, edge.g_hi)
                t_probe = a_box * (1 - x) + b_box * x + c_box * (x * (1 - x))
                q_probe = g_box * (a_box - b_box) + Box.exact(p * (x - Fraction(1, 2)))
                probe_out = {
                    "rod": edge.name,
                    "fromNode": edge.a,
                    "toNode": edge.b,
                    "positionFractionFromA": str(x),
                    "temperatureBoundsK": bounds(t_probe),
                    "heatCurrentTowardBBoundsW": bounds(q_probe),
                }

        out: dict[str, Any] = {
            "totalGeneratedPowerW": str(self.total_generated_power_w),
            "terminalNortonInjectionsBoundsW": {
                t: [str(self.terminal_injections_w[t][0]), str(self.terminal_injections_w[t][1])]
                for t in self.terminals
            },
            "nodeTemperatureBoundsK": {
                n: [str(node_temps[n][0]), str(node_temps[n][1])] for n in self.nodes
            },
            "rodPeaks": rod_peaks,
        }
        if probe_out is not None:
            out["probe"] = probe_out
        return out


def _parabolic_peak(a: Fraction, b: Fraction, curvature: Fraction) -> Fraction:
    """Exact maximum of (1-x)*a + x*b + curvature*x*(1-x) on x in [0, 1] for curvature >= 0."""
    if curvature == 0:
        return max(a, b)
    x = max(Fraction(0), min(Fraction(1), (Fraction(1) + (b - a) / curvature) / 2))
    return (1 - x) * a + x * b + curvature * x * (1 - x)


def _solve_junction_temperatures_with_sources(
    junctions: tuple[str, ...],
    terminal_temps: dict[str, tuple[Fraction, Fraction]],
    edges: tuple[RodGenEdge, ...],
    endpoint_injections: dict[str, Fraction],
    *,
    exact_point: bool,
) -> dict[str, tuple[Fraction, Fraction]]:
    """Solve certified junction temperatures L_JJ * T_J = -L_JT * T_T + s_J."""
    nj = len(junctions)
    j_idx = {j: i for i, j in enumerate(junctions)}
    if exact_point:
        mat = [[Fraction(0)] * nj for _ in range(nj)]
        rhs = [endpoint_injections[j] for j in junctions]
        for e in edges:
            g = e.g_lo
            if e.a in j_idx and e.b in j_idx:
                ia, ib = j_idx[e.a], j_idx[e.b]
                mat[ia][ia] += g
                mat[ib][ib] += g
                mat[ia][ib] -= g
                mat[ib][ia] -= g
            elif e.a in j_idx:
                ia = j_idx[e.a]
                mat[ia][ia] += g
                rhs[ia] += g * terminal_temps[e.b][0]
            elif e.b in j_idx:
                ib = j_idx[e.b]
                mat[ib][ib] += g
                rhs[ib] += g * terminal_temps[e.a][0]
        sol = _exact_linear_solve(mat, rhs)
        return {junctions[i]: (sol[i], sol[i]) for i in range(nj)}

    # Interval / monotone M-matrix certified enclosure via Gauss-Seidel + residual check.
    adj: dict[str, list[tuple[str, Fraction, Fraction]]] = {j: [] for j in junctions}
    for e in edges:
        if e.a in j_idx:
            adj[e.a].append((e.b, e.g_lo, e.g_hi))
        if e.b in j_idx:
            adj[e.b].append((e.a, e.g_lo, e.g_hi))

    t_min_term = min(lo for lo, _ in terminal_temps.values())
    t_max_term = max(hi for _, hi in terminal_temps.values())

    # Guaranteed sub-solution: T_J = t_min_term (since s_k >= 0).
    lo_map = {j: t_min_term for j in junctions}

    # Guaranteed super-solution via Howard policy iteration on the M-matrix upper residual f_min.
    def _eval_j_res_hi(vals: dict[str, Fraction]) -> dict[str, Fraction]:
        out_r = {}
        for j in junctions:
            r_val = -endpoint_injections[j]
            for nbr, g_lo, g_hi in adj[j]:
                t_n = terminal_temps[nbr][1] if nbr in terminal_temps else vals[nbr]
                diff = vals[j] - t_n
                r_val += (g_lo if diff >= 0 else g_hi) * diff
            out_r[j] = r_val
        return out_r

    hi_map = {j: t_max_term for j in junctions}
    for _ in range(32):
        res_now = _eval_j_res_hi(hi_map)
        if all(v >= 0 for v in res_now.values()):
            break
        mat_hi = [[Fraction(0)] * nj for _ in range(nj)]
        rhs_hi = [endpoint_injections[j] for j in junctions]
        for j_i, j in enumerate(junctions):
            for nbr, g_lo, g_hi in adj[j]:
                t_n = terminal_temps[nbr][1] if nbr in terminal_temps else hi_map[nbr]
                g = g_lo if hi_map[j] >= t_n else g_hi
                mat_hi[j_i][j_i] += g
                if nbr in j_idx:
                    mat_hi[j_i][j_idx[nbr]] -= g
                else:
                    rhs_hi[j_i] += g * t_n
        sol_super = _exact_linear_solve(mat_hi, rhs_hi)
        hi_map = {junctions[i]: max(hi_map[junctions[i]], sol_super[i]) for i in range(nj)}
    else:
        if not all(v >= 0 for v in _eval_j_res_hi(hi_map).values()):
            raise ValueError("failed to construct certified super-solution for internal junction temperatures")

    def _solve_node(j_name: str, vals: dict[str, Fraction], term_idx: int, *, maximize: bool) -> Fraction:
        terms = []
        for nbr, g_lo, g_hi in adj[j_name]:
            t_n = terminal_temps[nbr][term_idx] if nbr in terminal_temps else vals[nbr]
            terms.append((t_n, g_lo, g_hi))
        inj = endpoint_injections[j_name]
        knots = sorted({t_n for t_n, _, _ in terms})

        def _eval(t_val: Fraction) -> Fraction:
            tot = -inj
            for t_n, g_lo, g_hi in terms:
                diff = t_val - t_n
                w = (g_hi if diff >= 0 else g_lo) if maximize else (g_lo if diff >= 0 else g_hi)
                tot += w * diff
            return tot

        for idx, kv in enumerate(knots):
            v = _eval(kv)
            if v == 0:
                return kv
            if v > 0:
                left = knots[idx - 1]
                num = inj
                den = Fraction(0)
                for t_n, g_lo, g_hi in terms:
                    w = (g_hi if t_n <= left else g_lo) if maximize else (g_lo if t_n <= left else g_hi)
                    num += w * t_n
                    den += w
                return num / den
        # Root lies strictly above knots[-1] (all diff >= 0).
        num = inj
        den = Fraction(0)
        for t_n, g_lo, g_hi in terms:
            w = g_hi if maximize else g_lo
            num += w * t_n
            den += w
        return num / den

    tol = Fraction(1, 10**24)
    for _ in range(256):
        max_delta = Fraction(0)
        for j in junctions:
            cand_lo = _outward_clamp_fraction(_solve_node(j, lo_map, 0, maximize=True), round_up=False)
            cand_hi = _outward_clamp_fraction(_solve_node(j, hi_map, 1, maximize=False), round_up=True)
            new_lo = max(lo_map[j], cand_lo)
            new_hi = min(hi_map[j], cand_hi)
            if new_lo > new_hi:
                raise ValueError(f"junction temperature enclosure collapsed inconsistently at {j!r}")
            max_delta = max(max_delta, new_lo - lo_map[j], hi_map[j] - new_hi)
            lo_map[j] = new_lo
            hi_map[j] = new_hi
        if max_delta <= tol:
            break

    # Independent residual certification at every internal junction.
    for j in junctions:
        res_lo = -endpoint_injections[j]
        res_hi = -endpoint_injections[j]
        for nbr, g_lo, g_hi in adj[j]:
            t_n_lo = terminal_temps[nbr][0] if nbr in terminal_temps else lo_map[nbr]
            t_n_hi = terminal_temps[nbr][1] if nbr in terminal_temps else hi_map[nbr]
            d_lo = lo_map[j] - t_n_lo
            d_hi = hi_map[j] - t_n_hi
            res_lo += (g_hi if d_lo >= 0 else g_lo) * d_lo
            res_hi += (g_lo if d_hi >= 0 else g_hi) * d_hi
        if res_lo > 0 or res_hi < 0:
            raise ValueError(f"junction temperature residual certification failed at {j!r}")

    return {j: (lo_map[j], hi_map[j]) for j in junctions}


def build_rod_generation_model(
    nodes: list[str],
    terminals: list[str],
    rods: dict[str, dict[str, Any]],
) -> RodGenerationModel | None:
    """Build certified ``RodGenerationModel`` if any rod specifies positive ``generatedPowerW``."""
    node_set = set(nodes)
    term_list = list(terminals)
    term_set = set(term_list)
    junctions = tuple(n for n in nodes if n not in term_set)

    pi_box = None
    edges: list[RodGenEdge] = []
    endpoint_inj = {n: Fraction(0) for n in nodes}
    total_gen = Fraction(0)

    for name, spec in sorted(rods.items()):
        p_raw = spec.get("generatedPowerW")
        power = decimal_input(p_raw, f"rods[{name}].generatedPowerW") if p_raw is not None else Fraction(0)
        a, b = spec["a"], spec["b"]
        k_lo, k_hi = _parse_positive_param(spec["k"], f"rods[{name}].k")
        l_lo, l_hi = _parse_positive_param(spec["L"], f"rods[{name}].L")
        if spec["kind"] in ("rod_area", "RodArea"):
            a_lo, a_hi = _parse_positive_param(spec["A"], f"rods[{name}].A")
            if k_lo == k_hi and a_lo == a_hi and l_lo == l_hi:
                g_lo = g_hi = k_lo * a_lo / l_lo
            else:
                g_lo, g_hi = (Box.bounds(k_lo, k_hi) * Box.bounds(a_lo, a_hi) / Box.bounds(l_lo, l_hi)).span()
        else:
            d_lo, d_hi = _parse_positive_param(spec["d"], f"rods[{name}].d")
            if pi_box is None:
                pi_box = Box.bounds(*pi_rational_enclosure())
            d_box = Box.bounds(d_lo, d_hi)
            g_lo, g_hi = (Box.bounds(k_lo, k_hi) * (pi_box * d_box * d_box / Fraction(4)) / Box.bounds(l_lo, l_hi)).span()
        edges.append(RodGenEdge(name=name, a=a, b=b, g_lo=g_lo, g_hi=g_hi, power_w=power))
        half = power / 2
        endpoint_inj[a] += half
        endpoint_inj[b] += half
        total_gen += power

    if total_gen == 0:
        return None

    all_exact = all(e.g_lo == e.g_hi for e in edges)
    term_inj: dict[str, tuple[Fraction, Fraction]] = {}
    if not junctions:
        for t in term_list:
            term_inj[t] = (endpoint_inj[t], endpoint_inj[t])
    elif all_exact:
        # Exact rational harmonic influence H[k, t] for each terminal t.
        nj = len(junctions)
        j_idx = {j: i for i, j in enumerate(junctions)}
        l_jj = [[Fraction(0)] * nj for _ in range(nj)]
        for e in edges:
            g = e.g_lo
            if e.a in j_idx and e.b in j_idx:
                ia, ib = j_idx[e.a], j_idx[e.b]
                l_jj[ia][ia] += g
                l_jj[ib][ib] += g
                l_jj[ia][ib] -= g
                l_jj[ib][ia] -= g
            elif e.a in j_idx:
                l_jj[j_idx[e.a]][j_idx[e.a]] += g
            elif e.b in j_idx:
                l_jj[j_idx[e.b]][j_idx[e.b]] += g

        for t in term_list:
            rhs = [Fraction(0)] * nj
            for e in edges:
                g = e.g_lo
                if e.a == t and e.b in j_idx:
                    rhs[j_idx[e.b]] += g
                elif e.b == t and e.a in j_idx:
                    rhs[j_idx[e.a]] += g
            h_col = _exact_linear_solve(l_jj, rhs)
            inj = endpoint_inj[t] + sum(h_col[i] * endpoint_inj[junctions[i]] for i in range(nj))
            term_inj[t] = (inj, inj)
    else:
        # Certified monotone harmonic influence enclosures H[k, t] in [0, 1] for interval rods.
        rational_edges = [(e.name, e.a, e.b, e.g_lo, e.g_hi) for e in edges]
        for t in term_list:
            known = {u: Fraction(1) if u == t else Fraction(0) for u in term_list}
            h_boxes = _monotone_junction_enclosure(list(junctions), known, rational_edges)
            inj_lo = endpoint_inj[t]
            inj_hi = endpoint_inj[t]
            for j in junctions:
                s_j = endpoint_inj[j]
                if s_j > 0:
                    h_lo, h_hi = h_boxes[j]
                    inj_lo += max(Fraction(0), h_lo) * s_j
                    inj_hi += min(Fraction(1), h_hi) * s_j
            term_inj[t] = (inj_lo, inj_hi)

    # Verify global Norton conservation: sum_i I_Norton[i] contains total_gen.
    sum_lo = sum((term_inj[t][0] for t in term_list), Fraction(0))
    sum_hi = sum((term_inj[t][1] for t in term_list), Fraction(0))
    if not (sum_lo <= total_gen <= sum_hi):
        raise ValueError("Norton terminal injections failed global rod-generation conservation check")

    return RodGenerationModel(
        nodes=tuple(nodes),
        terminals=tuple(term_list),
        junctions=junctions,
        edges=tuple(edges),
        total_generated_power_w=total_gen,
        terminal_injections_w=term_inj,
        endpoint_injections_w=endpoint_inj,
        is_exact_point=all_exact,
    )
