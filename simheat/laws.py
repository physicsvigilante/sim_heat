"""First-class validated terminal conductance laws and physical composition (M03).

Provides ``DerivedLaw`` (schema ``sim_heat.derived_terminal_law/1``): an immutable,
exact-rational, interval-certified passive terminal conductance law representing a
storage-free conduction subnetwork reduced to its external terminals via Schur/Kron
elimination, read-only H1 AST adaptation, ideal storage-free joins, or validated
legacy pinned-law ingestion.

Physical sign convention (Architecture Record v2):
    Q_supply[i] = sum_j W[i][j] * T[j]   (W)
where Q_supply[i] is positive INTO the conduction network at terminal i, W[i][i] > 0,
W[i][j] <= 0 for i != j, W[i][j] == W[j][i], and sum_j W[i][j] == 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from h1.study import checked_path, load_study
from simheat.core import (
    ONE,
    ZERO,
    Box,
    ExactBindings,
    pi_rational_enclosure,
    verified_barrier_enclosure,
)
from tools.offline_provenance import OFFLINE_FLAG_KEYS, _SHA256_RE, offline_provenance
from tools.radiating_surface import decimal_input

ENDPOINT_MEANING = "exact_rational_closed_enclosure"
PINNED_LAW_SCHEMA = "sim_heat.offline_terminal_response/1"
DERIVED_LAW_SCHEMA = "sim_heat.derived_terminal_law/1"
JOINED_LAW_SCHEMA = "sim_heat.offline_joined_terminal_response/1"
ACCEPTED_LAW_SCHEMAS = (DERIVED_LAW_SCHEMA, PINNED_LAW_SCHEMA, JOINED_LAW_SCHEMA)

LAW_UNIT = "W/K"
LAW_SIGN_CONVENTION = "terminal_supply_positive_into_network"


def _parse_rational_str(value: Any, label: str) -> Fraction:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a rational string")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{label} must be a valid rational string") from exc


def parse_interval_bounds(pair: Any, label: str) -> tuple[Fraction, Fraction]:
    """Validate a 2-element exact rational closed enclosure [low, high] with low <= high."""
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise ValueError(f"{label} must be a 2-element [low, high] rational interval")
    low = _parse_rational_str(pair[0], f"{label} lower bound")
    high = _parse_rational_str(pair[1], f"{label} upper bound")
    if low > high:
        raise ValueError(f"{label} has inverted interval bounds: {low} > {high}")
    return low, high


def _simplex_pivot(tableau, basis, obj, p_row, p_col):
    piv = tableau[p_row][p_col]
    n_cols = len(tableau[p_row])
    tableau[p_row] = [v / piv for v in tableau[p_row]]
    for r in range(len(tableau)):
        if r != p_row:
            factor = tableau[r][p_col]
            if factor != 0:
                tableau[r] = [tableau[r][c] - factor * tableau[p_row][c] for c in range(n_cols)]
    factor = obj[p_col]
    if factor != 0:
        for c in range(n_cols):
            obj[c] -= factor * tableau[p_row][c]
    basis[p_row] = p_col


def _simplex_minimize(tableau, basis, obj):
    """Run exact rational simplex with Bland's rule to minimize objective row."""
    n_cols = len(obj) - 1
    while True:
        enter = None
        for c in range(n_cols):
            if obj[c] < 0:
                enter = c
                break
        if enter is None:
            return True
        leave = None
        best_ratio = None
        for r in range(len(tableau)):
            coeff = tableau[r][enter]
            if coeff > 0:
                ratio = tableau[r][-1] / coeff
                if leave is None or ratio < best_ratio or (ratio == best_ratio and basis[r] < basis[leave]):
                    best_ratio = ratio
                    leave = r
        if leave is None:
            return False
        _simplex_pivot(tableau, basis, obj, leave, enter)


def _lp_feasible_basis(rows, rhs):
    """Exact rational Phase-I simplex (Bland's rule) for A x <= b, x >= 0."""
    n_rows = len(rows)
    n_vars = len(rows[0]) if n_rows else 0
    if n_rows == 0:
        return [], [], n_vars
    if all(b >= 0 for b in rhs):
        tableau = []
        basis = []
        for r in range(n_rows):
            row = [Fraction(v) for v in rows[r]] + [Fraction(0)] * n_rows + [Fraction(rhs[r])]
            row[n_vars + r] = Fraction(1)
            tableau.append(row)
            basis.append(n_vars + r)
        return tableau, basis, n_vars

    aux = n_vars + n_rows
    total_cols = aux + 1
    tableau = []
    basis = []
    for r in range(n_rows):
        row = [Fraction(v) for v in rows[r]] + [Fraction(0)] * n_rows + [Fraction(-1), Fraction(rhs[r])]
        row[n_vars + r] = Fraction(1)
        tableau.append(row)
        basis.append(n_vars + r)
    obj = [Fraction(0)] * (total_cols + 1)
    obj[aux] = Fraction(1)

    leave = min(range(n_rows), key=lambda r: (tableau[r][-1], basis[r]))
    _simplex_pivot(tableau, basis, obj, leave, aux)
    if not _simplex_minimize(tableau, basis, obj) or -obj[-1] > 0:
        return None

    if aux in basis:
        r_aux = basis.index(aux)
        pivot_col = next((c for c in range(aux) if tableau[r_aux][c] != 0), None)
        if pivot_col is not None:
            _simplex_pivot(tableau, basis, obj, r_aux, pivot_col)
        else:
            tableau.pop(r_aux)
            basis.pop(r_aux)
    clean_tableau = [row[:aux] + [row[-1]] for row in tableau]
    return clean_tableau, basis, n_vars


def _lp_extract(tableau, basis, n_vars):
    n_cols = (len(tableau[0]) - 1) if tableau else n_vars
    sol = [Fraction(0)] * n_cols
    for r, col in enumerate(basis):
        sol[col] = tableau[r][-1]
    return sol[:n_vars]


def _lp_maximize_var(base_tableau, base_basis, n_vars, target_col):
    """Exact rational Phase-II simplex maximizing x[target_col] from a feasible basis."""
    tableau = [list(row) for row in base_tableau]
    basis = list(base_basis)
    n_cols = len(tableau[0]) - 1
    obj = [Fraction(0)] * (n_cols + 1)
    obj[target_col] = Fraction(-1)
    if target_col in basis:
        r_t = basis.index(target_col)
        for c in range(n_cols + 1):
            obj[c] += tableau[r_t][c]
    _simplex_minimize(tableau, basis, obj)
    return _lp_extract(tableau, basis, n_vars)


def _verify_joint_passive_feasibility(terminals, parsed):
    """Verify exact joint feasibility of a CONNECTED reciprocal passive zero-sum matrix."""
    edges = []
    g_lo = {}
    g_hi = {}
    for idx_i, i in enumerate(terminals):
        for j in terminals[idx_i + 1:]:
            ij_lo, ij_hi = parsed[i][j]
            ji_lo, ji_hi = parsed[j][i]
            lo = max(Fraction(0), -min(ij_hi, ji_hi))
            hi = -max(ij_lo, ji_lo)
            if lo > hi:
                raise ValueError(
                    f"nonreciprocal passive terminal response between {i!r} and {j!r}"
                )
            edge = (i, j)
            edges.append(edge)
            g_lo[edge] = lo
            g_hi[edge] = hi

    free_edges = [e for e in edges if g_hi[e] > g_lo[e]]
    free_idx = {e: k for k, e in enumerate(free_edges)}
    n_free = len(free_edges)
    rows = []
    rhs = []
    for e in free_edges:
        row = [Fraction(0)] * n_free
        row[free_idx[e]] = Fraction(1)
        rows.append(row)
        rhs.append(g_hi[e] - g_lo[e])
    for i in terminals:
        d_lo, d_hi = parsed[i][i]
        incident = [e for e in edges if i in e]
        base = sum((g_lo[e] for e in incident), Fraction(0))
        low_req = d_lo - base
        high_req = d_hi - base
        if high_req < 0:
            raise ValueError(
                f"no jointly consistent passive reciprocal response exists at terminal {i!r}"
            )
        inc_free = [e for e in incident if e in free_idx]
        if not inc_free:
            if low_req > 0:
                raise ValueError(
                    f"no jointly consistent passive reciprocal response exists at terminal {i!r}"
                )
            continue
        up_row = [Fraction(0)] * n_free
        for e in inc_free:
            up_row[free_idx[e]] = Fraction(1)
        rows.append(up_row)
        rhs.append(high_req)
        if low_req > 0:
            rows.append([-v for v in up_row])
            rhs.append(-low_req)

    feasible = _lp_feasible_basis(rows, rhs)
    if feasible is None:
        raise ValueError("no jointly consistent passive reciprocal zero-sum response matrix exists")
    base_tableau, base_basis, _ = feasible
    witnesses = [_lp_extract(base_tableau, base_basis, n_free)]

    for e in free_edges:
        if g_lo[e] == 0:
            col = free_idx[e]
            if all(w[col] == 0 for w in witnesses):
                sol_e = _lp_maximize_var(base_tableau, base_basis, n_free, col)
                if sol_e[col] > 0:
                    witnesses.append(sol_e)

    n_w = len(witnesses)
    avg_sol = [sum((w[k] for w in witnesses), Fraction(0)) / n_w for k in range(n_free)]
    g_val = {e: g_lo[e] + (avg_sol[free_idx[e]] if e in free_idx else Fraction(0)) for e in edges}

    for e in edges:
        if not (g_lo[e] <= g_val[e] <= g_hi[e]):
            raise ValueError("passive feasibility witness out of edge bounds")
    for i in terminals:
        diag = sum((g_val[e] for e in edges if i in e), Fraction(0))
        d_lo, d_hi = parsed[i][i]
        if not (d_lo <= diag <= d_hi):
            raise ValueError("passive feasibility witness out of diagonal bounds")

    adj = {t: set() for t in terminals}
    for i, j in edges:
        if g_val[(i, j)] > 0:
            adj[i].add(j)
            adj[j].add(i)
    visited = {terminals[0]}
    stack = [terminals[0]]
    while stack:
        cur = stack.pop()
        for nxt in adj[cur]:
            if nxt not in visited:
                visited.add(nxt)
                stack.append(nxt)
    if visited != set(terminals):
        raise ValueError("passive terminal response network is disconnected in every feasible realization")


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _parse_positive_param(value: Any, label: str) -> tuple[Fraction, Fraction]:
    """Parse a positive SI decimal string, exact Fraction, or [low, high] / {low, high} interval."""
    if isinstance(value, Fraction):
        if value <= 0:
            raise ValueError(f"positive {label} required")
        return value, value
    if isinstance(value, str):
        v = decimal_input(value, label)
        if v <= 0:
            raise ValueError(f"positive {label} required")
        return v, v
    if isinstance(value, dict):
        if set(value) != {"low", "high"}:
            raise ValueError(f"{label} interval dict must have exact keys ['high', 'low']")
        lo = value["low"] if isinstance(value["low"], Fraction) else decimal_input(value["low"], f"{label}.low")
        hi = value["high"] if isinstance(value["high"], Fraction) else decimal_input(value["high"], f"{label}.high")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        lo = value[0] if isinstance(value[0], Fraction) else decimal_input(value[0], f"{label}[0]")
        hi = value[1] if isinstance(value[1], Fraction) else decimal_input(value[1], f"{label}[1]")
    else:
        raise ValueError(f"{label} must be a decimal string or {{low, high}} interval")
    if lo <= 0 or hi <= 0:
        raise ValueError(f"positive {label} required")
    if lo > hi:
        raise ValueError(f"{label} interval has low > high: {lo} > {hi}")
    return lo, hi


def _solve_junction_extremum(
    neighbors: list[tuple[Fraction, Fraction, Fraction]],
    *,
    maximize: bool,
) -> Fraction:
    """Solve exact piecewise-linear monotone junction equilibrium for u_k in [0, 1].

    Each neighbor entry is ``(u_nbr, g_lo, g_hi)`` with ``g_lo > 0``.
    - For ``maximize=False`` (lower barrier): solve
        sum_{u_j < u} g_hi * (u - u_j) = sum_{u_j > u} g_lo * (u_j - u)
      (minimizes u_k over all g in [g_lo, g_hi] for fixed u_j).
    - For ``maximize=True`` (upper barrier): solve
        sum_{u_j < u} g_lo * (u - u_j) = sum_{u_j > u} g_hi * (u_j - u)
      (maximizes u_k over all g in [g_lo, g_hi] for fixed u_j).
    """
    ordered = sorted(neighbors, key=lambda item: item[0])
    # Evaluate residual r(u) = sum_{u_j < u} g_below*(u - u_j) - sum_{u_j > u} g_above*(u_j - u)
    # which is strictly increasing and piecewise linear in u with breakpoints at u_j.
    def residual(u: Fraction) -> Fraction:
        total = Fraction(0)
        for u_j, g_lo, g_hi in ordered:
            if u > u_j:
                w = g_lo if maximize else g_hi
                total += w * (u - u_j)
            elif u < u_j:
                w = g_hi if maximize else g_lo
                total -= w * (u_j - u)
        return total

    # Find exact interval [u_a, u_b] where residual changes sign from <= 0 to >= 0.
    pts = [item[0] for item in ordered]
    for idx, u_pt in enumerate(pts):
        r_pt = residual(u_pt)
        if r_pt == 0:
            return u_pt
        if r_pt > 0:
            # Root lies strictly in (pts[idx - 1], u_pt); linear formula is exact there!
            num = Fraction(0)
            den = Fraction(0)
            for u_j, g_lo, g_hi in ordered:
                w = (g_lo if maximize else g_hi) if u_j <= pts[idx - 1] else (g_hi if maximize else g_lo)
                num += w * u_j
                den += w
            return num / den
    return pts[-1]


def _outward_clamp_fraction(val: Fraction, *, round_up: bool, scale: int = 10**30) -> Fraction:
    """Bound rational denominator safely outward (down for lo, up for hi)."""
    if val.denominator <= scale:
        return val
    num = val.numerator * scale
    den = val.denominator
    if round_up:
        q = -(-num // den)
    else:
        q = num // den
    return Fraction(q, scale)


def _monotone_junction_enclosure(
    junctions: list[str],
    known: dict[str, Fraction],
    rational_edges: list[tuple[str, str, str, Fraction, Fraction]],
    *,
    max_sweeps: int = 200,
) -> dict[str, tuple[Fraction, Fraction]]:
    """Exact-rational certified discrete-maximum-principle junction enclosure for arbitrary widths."""
    adj: dict[str, list[tuple[str, Fraction, Fraction]]] = {j: [] for j in junctions}
    for _, a, b, g_lo, g_hi in rational_edges:
        if a in adj:
            adj[a].append((b, g_lo, g_hi))
        if b in adj:
            adj[b].append((a, g_lo, g_hi))

    k_min = min(known.values())
    k_max = max(known.values())
    u_lo: dict[str, Fraction] = {**known, **{j: k_min for j in junctions}}
    u_hi: dict[str, Fraction] = {**known, **{j: k_max for j in junctions}}
    tol = Fraction(1, 10**28)

    for sweep in range(max_sweeps):
        max_delta = Fraction(0)
        for j in junctions:
            nbrs_lo = [(u_lo[nbr], g_lo, g_hi) for nbr, g_lo, g_hi in adj[j]]
            new_lo = _solve_junction_extremum(nbrs_lo, maximize=False)
            if len(junctions) > 1 and sweep > 0:
                new_lo = _outward_clamp_fraction(new_lo, round_up=False)
            if new_lo > u_lo[j]:
                max_delta = max(max_delta, new_lo - u_lo[j])
                u_lo[j] = new_lo

            nbrs_hi = [(u_hi[nbr], g_lo, g_hi) for nbr, g_lo, g_hi in adj[j]]
            new_hi = _solve_junction_extremum(nbrs_hi, maximize=True)
            if len(junctions) > 1 and sweep > 0:
                new_hi = _outward_clamp_fraction(new_hi, round_up=True)
            if new_hi < u_hi[j]:
                max_delta = max(max_delta, u_hi[j] - new_hi)
                u_hi[j] = new_hi
        if max_delta <= tol:
            break

    # Independent post-condition barrier certification (discrete maximum principle):
    # For every junction j, f_j^{max}(u_lo) >= 0 (net inflow at worst-case g is >= 0 => u_lo <= u)
    # and f_j^{min}(u_hi) <= 0 (net inflow at worst-case g is <= 0 => u_hi >= u).
    for j in junctions:
        if u_lo[j] > u_hi[j]:
            raise ValueError(f"junction barrier inverted at {j!r}")
        inflow_lo_min = Fraction(0)
        inflow_hi_max = Fraction(0)
        for nbr, g_lo, g_hi in adj[j]:
            diff_lo = u_lo[nbr] - u_lo[j]
            inflow_lo_min += (g_lo if diff_lo >= 0 else g_hi) * diff_lo
            diff_hi = u_hi[nbr] - u_hi[j]
            inflow_hi_max += (g_hi if diff_hi >= 0 else g_lo) * diff_hi
        if inflow_lo_min < 0 or inflow_hi_max > 0:
            raise ValueError(f"junction maximum-principle barrier check failed at {j!r}")
    return {j: (u_lo[j], u_hi[j]) for j in junctions}


def _exact_invert(matrix: list[list[Fraction]]) -> list[list[Fraction]]:
    """Exact Fraction Gauss-Jordan inversion; raises ValueError if singular."""
    n = len(matrix)
    aug = [
        [matrix[r][c] for c in range(n)] + [Fraction(1 if r == c else 0) for c in range(n)]
        for r in range(n)
    ]
    for col in range(n):
        pivot = None
        for r in range(col, n):
            if aug[r][col] != 0:
                pivot = r
                break
        if pivot is None:
            raise ValueError("singular matrix in exact rational inversion")
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        pv = aug[col][col]
        aug[col] = [x / pv for x in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                factor = aug[r][col]
                aug[r] = [aug[r][c] - factor * aug[col][c] for c in range(2 * n)]
    return [row[n:] for row in aug]


def _exact_schur_from_conductances(
    terminals: list[str],
    junctions: list[str],
    edge_conductances: list[tuple[str, str, Fraction]],
) -> dict[str, dict[str, Fraction]]:
    """Exact Fraction Schur/Kron reduction of a connected passive conduction graph."""
    all_nodes = terminals + junctions
    idx = {n: k for k, n in enumerate(all_nodes)}
    n_tot = len(all_nodes)
    lap = [[Fraction(0)] * n_tot for _ in range(n_tot)]
    for a, b, g in edge_conductances:
        ia, ib = idx[a], idx[b]
        lap[ia][ia] += g
        lap[ib][ib] += g
        lap[ia][ib] -= g
        lap[ib][ia] -= g
    nt = len(terminals)
    nj = len(junctions)
    if nj == 0:
        return {
            terminals[i]: {terminals[j]: lap[i][j] for j in range(nt)}
            for i in range(nt)
        }
    l_tt = [[lap[i][j] for j in range(nt)] for i in range(nt)]
    l_ti = [[lap[i][nt + j] for j in range(nj)] for i in range(nt)]
    l_ii = [[lap[nt + i][nt + j] for j in range(nj)] for i in range(nj)]
    l_it = [[lap[nt + i][j] for j in range(nt)] for i in range(nj)]
    l_ii_inv = _exact_invert(l_ii)
    # tmp = L_II^{-1} * L_IT
    tmp = [
        [sum((l_ii_inv[r][k] * l_it[k][c] for k in range(nj)), Fraction(0)) for c in range(nt)]
        for r in range(nj)
    ]
    w = [
        [
            l_tt[i][j] - sum((l_ti[i][k] * tmp[k][j] for k in range(nj)), Fraction(0))
            for j in range(nt)
        ]
        for i in range(nt)
    ]
    return {terminals[i]: {terminals[j]: w[i][j] for j in range(nt)} for i in range(nt)}


def _tighten_passive_interval_matrix(
    terminals: list[str],
    parsed: dict[str, dict[str, tuple[Fraction, Fraction]]],
) -> dict[str, dict[str, tuple[Fraction, Fraction]]]:
    """Apply sound physical-invariant tightening: reciprocity, off-diag <= 0, zero row sum."""
    out = {i: dict(parsed[i]) for i in terminals}
    for idx_i, i in enumerate(terminals):
        for j in terminals[idx_i + 1:]:
            lo = max(out[i][j][0], out[j][i][0])
            hi = min(out[i][j][1], out[j][i][1], Fraction(0))
            if lo > hi:
                raise ValueError(f"inconsistent reciprocal/passive bounds on ({i!r}, {j!r})")
            out[i][j] = (lo, hi)
            out[j][i] = (lo, hi)
    for i in terminals:
        sum_neg_hi = sum((-out[i][j][1] for j in terminals if j != i), Fraction(0))
        sum_neg_lo = sum((-out[i][j][0] for j in terminals if j != i), Fraction(0))
        d_lo = max(out[i][i][0], sum_neg_hi)
        d_hi = min(out[i][i][1], sum_neg_lo)
        if d_lo > d_hi or d_lo <= 0:
            raise ValueError(f"inconsistent passive diagonal/row-sum bounds at {i!r}")
        out[i][i] = (d_lo, d_hi)
    return out


def validate_passive_matrix(
    terminals: list[str] | tuple[str, ...],
    matrix: dict[str, dict[str, tuple[Fraction, Fraction]]],
    *,
    run_simplex: bool = True,
) -> None:
    """Certify positive diagonals, non-positive off-diagonals, reciprocity, zero-sum, connectivity."""
    term_list = list(terminals)
    if (
        len(term_list) < 2
        or any(not isinstance(t, str) or not t for t in term_list)
        or len(set(term_list)) != len(term_list)
    ):
        raise ValueError("terminal law requires at least two unique non-empty terminal names")
    tset = set(term_list)
    if set(matrix) != tset:
        raise ValueError("terminal law matrix rows must match terminals exactly")
    for i in term_list:
        if set(matrix[i]) != tset:
            raise ValueError(f"terminal law matrix row {i!r} columns must match terminals")
        d_lo, d_hi = matrix[i][i]
        if d_lo > d_hi or d_lo <= 0:
            raise ValueError(f"passive terminal response requires positive diagonal at {i!r}")
        for j in term_list:
            lo, hi = matrix[i][j]
            if lo > hi:
                raise ValueError(f"inverted interval at ({i!r}, {j!r})")
            if i != j and hi > 0:
                raise ValueError(
                    f"passive terminal response requires non-positive off-diagonal at ({i!r}, {j!r})"
                )
    for idx_i, i in enumerate(term_list):
        for j in term_list[idx_i + 1:]:
            if max(matrix[i][j][0], matrix[j][i][0]) > min(matrix[i][j][1], matrix[j][i][1]):
                raise ValueError(f"nonreciprocal passive terminal response between {i!r} and {j!r}")
    for i in term_list:
        row_lo = sum((matrix[i][j][0] for j in term_list), Fraction(0))
        row_hi = sum((matrix[i][j][1] for j in term_list), Fraction(0))
        if row_lo > 0 or row_hi < 0:
            raise ValueError(f"passive terminal response row {i!r} violates zero-sum conservation")
        col_lo = sum((matrix[j][i][0] for j in term_list), Fraction(0))
        col_hi = sum((matrix[j][i][1] for j in term_list), Fraction(0))
        if col_lo > 0 or col_hi < 0:
            raise ValueError(f"passive terminal response column {i!r} violates zero-sum conservation")
    if run_simplex:
        _verify_joint_passive_feasibility(term_list, matrix)
    else:
        # Connectivity check on strictly positive upper-bound conductances when freshly reduced
        # from a connected positive-conductance rod graph.
        adj = {t: set() for t in term_list}
        for i in term_list:
            for j in term_list:
                if i != j and matrix[i][j][0] < 0:
                    adj[i].add(j)
                    adj[j].add(i)
        visited = {term_list[0]}
        stack = [term_list[0]]
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
        if visited != tset:
            raise ValueError("passive terminal response network is disconnected")


def _check_offline_flags(mapping: dict[str, Any], *, require_present: bool = True) -> dict[str, bool]:
    flags = {}
    for key in OFFLINE_FLAG_KEYS:
        if key in mapping:
            if mapping[key] is not False:
                raise ValueError(f"offline calculation refuses non-False {key}")
        elif require_present:
            raise ValueError(f"offline calculation refuses non-False {key}")
        flags[key] = False
    return flags


def _serialize_matrix(
    terminals: tuple[str, ...],
    matrix: dict[str, dict[str, tuple[Fraction, Fraction]]],
) -> dict[str, dict[str, list[str]]]:
    return {
        i: {j: [str(matrix[i][j][0]), str(matrix[i][j][1])] for j in terminals}
        for i in terminals
    }


def _compute_law_sha256(
    terminals: tuple[str, ...],
    matrix: dict[str, dict[str, tuple[Fraction, Fraction]]],
    lineage: dict[str, Any],
) -> str:
    payload = {
        "schema": DERIVED_LAW_SCHEMA,
        "terminals": list(terminals),
        "unit": LAW_UNIT,
        "signConvention": LAW_SIGN_CONVENTION,
        "endpointMeaning": ENDPOINT_MEANING,
        "supplyResponseBoundsWPerK": _serialize_matrix(terminals, matrix),
        "lineage": lineage,
    }
    return sha256(_canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class DerivedLaw:
    """Validated, immutable, exact-rational passive terminal conductance law."""

    terminals: tuple[str, ...]
    matrix: dict[str, dict[str, tuple[Fraction, Fraction]]]
    lineage: dict[str, Any]
    content_sha256: str
    reference_temperatures_k: dict[str, Fraction] | None = None
    law_id: str | None = None
    legacy_provenance: dict[str, Any] | None = None

    @classmethod
    def _build(
        cls,
        terminals: list[str] | tuple[str, ...],
        matrix: dict[str, dict[str, tuple[Fraction, Fraction]]],
        lineage: dict[str, Any],
        *,
        reference_temperatures_k: dict[str, Fraction] | None = None,
        law_id: str | None = None,
        legacy_provenance: dict[str, Any] | None = None,
        run_simplex: bool = True,
    ) -> DerivedLaw:
        term_tuple = tuple(terminals)
        validate_passive_matrix(term_tuple, matrix, run_simplex=run_simplex)
        if reference_temperatures_k is not None:
            if set(reference_temperatures_k) != set(term_tuple):
                raise ValueError("reference_temperatures_k must match terminals exactly")
            for name, temp in reference_temperatures_k.items():
                if not isinstance(temp, Fraction) or temp < 0:
                    raise ValueError(f"reference temperature at {name!r} must be a nonnegative Fraction")
        digest = _compute_law_sha256(term_tuple, matrix, lineage)
        frozen_matrix = {i: {j: matrix[i][j] for j in term_tuple} for i in term_tuple}
        frozen_refs = (
            {k: reference_temperatures_k[k] for k in term_tuple}
            if reference_temperatures_k is not None
            else None
        )
        return cls(
            terminals=term_tuple,
            matrix=frozen_matrix,
            lineage=lineage,
            content_sha256=digest,
            reference_temperatures_k=frozen_refs,
            law_id=law_id,
            legacy_provenance=legacy_provenance,
        )

    @property
    def is_exact_point(self) -> bool:
        return all(
            self.matrix[i][j][0] == self.matrix[i][j][1]
            for i in self.terminals
            for j in self.terminals
        )

    def lineage_ref(self) -> dict[str, Any]:
        ref: dict[str, Any] = {
            "kind": self.lineage.get("kind"),
            "contentSha256": self.content_sha256,
            "terminals": list(self.terminals),
        }
        if self.law_id is not None:
            ref["lawId"] = self.law_id
        return ref

    def to_dict(self) -> dict[str, Any]:
        """Serialize as canonical ``sim_heat.derived_terminal_law/1`` payload."""
        out: dict[str, Any] = {
            "schema": DERIVED_LAW_SCHEMA,
            "terminals": list(self.terminals),
            "unit": LAW_UNIT,
            "signConvention": LAW_SIGN_CONVENTION,
            "endpointMeaning": ENDPOINT_MEANING,
            "supplyResponseBoundsWPerK": _serialize_matrix(self.terminals, self.matrix),
            "lineage": self.lineage,
            "contentSha256": self.content_sha256,
            "nativeExecuted": False,
            "nativeQualified": False,
            "independentlyCertifiedReference": False,
            "runnerConsumable": False,
        }
        if self.law_id is not None:
            out["lawId"] = self.law_id
        if self.reference_temperatures_k is not None:
            out["imposedTemperaturesK"] = {k: str(v) for k, v in self.reference_temperatures_k.items()}
        if self.legacy_provenance is not None:
            for key in ("modelSha256", "studySha256", "factsSha256"):
                if key in self.legacy_provenance:
                    out[key] = self.legacy_provenance[key]
        return out

    def to_engine_law(self, imposed_temperatures_k: dict[str, str] | None = None) -> dict[str, Any]:
        """Return a dict view directly consumable by existing engines with full physical metadata."""
        out = self.to_dict()
        if imposed_temperatures_k is not None:
            out["imposedTemperaturesK"] = dict(imposed_temperatures_k)
        return out

    def provenance_block(self) -> dict[str, Any]:
        """Uniform offline provenance block for engines consuming this law."""
        if self.legacy_provenance is not None:
            return dict(self.legacy_provenance)
        return {
            "derivedLawSchema": DERIVED_LAW_SCHEMA,
            "derivedLawSha256": self.content_sha256,
            "derivedLawLineage": self.lineage,
            "nativeExecuted": False,
            "nativeQualified": False,
            "independentlyCertifiedReference": False,
            "runnerConsumable": False,
        }

    @classmethod
    def from_rods(
        cls,
        nodes: list[str],
        rods: dict[str, dict[str, Any]],
        *,
        terminals: list[str] | None = None,
        law_id: str | None = None,
        lineage_extra: dict[str, Any] | None = None,
        reference_temperatures_k: dict[str, Fraction] | None = None,
    ) -> DerivedLaw:
        """Build a certified ``DerivedLaw`` by Schur/Kron reduction of storage-free rods."""
        if not isinstance(nodes, (list, tuple)) or len(nodes) < 2:
            raise ValueError("at least two nodes are required")
        if any(not isinstance(n, str) or not n for n in nodes) or len(set(nodes)) != len(nodes):
            raise ValueError("nodes must be unique non-empty strings")
        if not isinstance(rods, dict) or not rods:
            raise ValueError("at least one rod is required")

        node_set = set(nodes)
        if terminals is None:
            term_list = list(nodes)
        else:
            if not isinstance(terminals, (list, tuple)) or len(terminals) < 2:
                raise ValueError("at least two terminals are required")
            if any(not isinstance(t, str) or t not in node_set for t in terminals) or len(set(terminals)) != len(terminals):
                raise ValueError("terminals must be unique members of nodes")
            term_list = list(terminals)
        term_set = set(term_list)
        junctions = [n for n in nodes if n not in term_set]

        pi_box = None
        rational_edges: list[tuple[str, str, str, Fraction, Fraction]] = []
        adj: dict[str, set[str]] = {n: set() for n in nodes}
        rod_records: dict[str, dict[str, Any]] = {}

        for name, spec in sorted(rods.items()):
            if not isinstance(name, str) or not name or not isinstance(spec, dict):
                raise ValueError(f"invalid rod specification for {name!r}")
            kind = spec.get("kind")
            a = spec.get("a")
            b = spec.get("b")
            if a not in node_set or b not in node_set or a == b:
                raise ValueError(f"rod {name!r} endpoints ({a!r}, {b!r}) must be distinct declared nodes")
            k_lo, k_hi = _parse_positive_param(spec.get("k"), f"rods[{name}].k")
            l_lo, l_hi = _parse_positive_param(spec.get("L"), f"rods[{name}].L")
            if kind in ("rod_area", "RodArea"):
                a_lo, a_hi = _parse_positive_param(spec.get("A"), f"rods[{name}].A")
                if k_lo == k_hi and a_lo == a_hi and l_lo == l_hi:
                    g_lo = g_hi = k_lo * a_lo / l_lo
                else:
                    g_box = Box.bounds(k_lo, k_hi) * Box.bounds(a_lo, a_hi) / Box.bounds(l_lo, l_hi)
                    g_lo, g_hi = g_box.span()
                rod_records[name] = {
                    "kind": "rod_area", "a": a, "b": b,
                    "k": [str(k_lo), str(k_hi)], "L": [str(l_lo), str(l_hi)], "A": [str(a_lo), str(a_hi)],
                }
            elif kind in ("rod_circular", "RodCircular"):
                d_lo, d_hi = _parse_positive_param(spec.get("d"), f"rods[{name}].d")
                if pi_box is None:
                    pi_lo, pi_hi = pi_rational_enclosure()
                    pi_box = Box.bounds(pi_lo, pi_hi)
                d_box = Box.bounds(d_lo, d_hi)
                area_box = pi_box * d_box * d_box / Fraction(4)
                g_box = Box.bounds(k_lo, k_hi) * area_box / Box.bounds(l_lo, l_hi)
                g_lo, g_hi = g_box.span()
                rod_records[name] = {
                    "kind": "rod_circular", "a": a, "b": b,
                    "k": [str(k_lo), str(k_hi)], "L": [str(l_lo), str(l_hi)], "d": [str(d_lo), str(d_hi)],
                }
            else:
                raise ValueError(f"unsupported rod kind {kind!r} on rod {name!r}")
            if g_lo <= 0:
                raise ValueError(f"rod {name!r} conductance lower bound must be positive")
            rational_edges.append((name, a, b, g_lo, g_hi))
            adj[a].add(b)
            adj[b].add(a)

        # Require one single connected component covering every declared node.
        visited = {term_list[0]}
        stack = [term_list[0]]
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
        if visited != node_set:
            missing = sorted(node_set - visited)
            raise ValueError(f"conduction network must be a single connected component; unreachable: {missing}")

        all_exact = all(g_lo == g_hi for _, _, _, g_lo, g_hi in rational_edges)
        if all_exact:
            exact_w = _exact_schur_from_conductances(
                term_list,
                junctions,
                [(a, b, g_lo) for _, a, b, g_lo, _ in rational_edges],
            )
            parsed = {
                i: {j: (exact_w[i][j], exact_w[i][j]) for j in term_list}
                for i in term_list
            }
        elif not junctions:
            parsed = {i: {j: (Fraction(0), Fraction(0)) for j in term_list} for i in term_list}
            for _, a, b, g_lo, g_hi in rational_edges:
                g_box = Box.bounds(g_lo, g_hi)
                for n in (a, b):
                    cur = Box.bounds(*parsed[n][n]) + g_box
                    parsed[n][n] = cur.span()
                ab = Box.bounds(*parsed[a][b]) - g_box
                parsed[a][b] = ab.span()
                parsed[b][a] = ab.span()
        else:
            # Certified monotone discrete-maximum-principle enclosure for every terminal basis column.
            raw_cols: dict[str, dict[str, tuple[Fraction, Fraction]]] = {i: {} for i in term_list}
            for selected in term_list:
                known = {t: Fraction(1 if t == selected else 0) for t in term_list}
                j_boxes = _monotone_junction_enclosure(junctions, known, rational_edges)
                u_span: dict[str, tuple[Fraction, Fraction]] = {
                    **{t: (known[t], known[t]) for t in term_list},
                    **j_boxes,
                }
                for t in term_list:
                    if t == selected:
                        # Compute upper/lower supply out of selected terminal directly; tightened by Rayleigh below.
                        sup_lo = Fraction(0)
                        sup_hi = Fraction(0)
                        for _, a, b, g_lo, g_hi in rational_edges:
                            if a == t or b == t:
                                nbr = b if a == t else a
                                u_n_lo, u_n_hi = u_span[nbr]
                                # u[t] == 1 >= u[nbr] >= 0
                                sup_lo += g_lo * (Fraction(1) - u_n_hi)
                                sup_hi += g_hi * (Fraction(1) - u_n_lo)
                        raw_cols[t][selected] = (sup_lo, sup_hi)
                    else:
                        # u[t] == 0 <= u[nbr] => supply into network at t is -sum g_e * u[nbr] <= 0.
                        neg_lo = Fraction(0)
                        neg_hi = Fraction(0)
                        for _, a, b, g_lo, g_hi in rational_edges:
                            if a == t or b == t:
                                nbr = b if a == t else a
                                u_n_lo, u_n_hi = u_span[nbr]
                                neg_lo += g_lo * u_n_lo
                                neg_hi += g_hi * u_n_hi
                        raw_cols[t][selected] = (-neg_hi, -neg_lo)

            # Rayleigh Monotonicity Law: diagonal driving-point conductance W_ii(g)
            # is monotonically non-decreasing in every edge conductance g_e >= 0.
            # Intersecting with exact g_lo and g_hi endpoint Schur reductions is 100% sound
            # and gives exact zero-overestimation diagonal bounds.
            w_at_lo = _exact_schur_from_conductances(
                term_list, junctions, [(a, b, g_lo) for _, a, b, g_lo, _ in rational_edges]
            )
            w_at_hi = _exact_schur_from_conductances(
                term_list, junctions, [(a, b, g_hi) for _, a, b, _, g_hi in rational_edges]
            )
            for t in term_list:
                lo_r, hi_r = raw_cols[t][t]
                d_lo = max(lo_r, w_at_lo[t][t])
                d_hi = min(hi_r, w_at_hi[t][t])
                if d_lo > d_hi:
                    raise ValueError(f"Rayleigh diagonal certification mismatch at {t!r}")
                raw_cols[t][t] = (d_lo, d_hi)
            parsed = _tighten_passive_interval_matrix(term_list, raw_cols)

        lineage: dict[str, Any] = {
            "kind": "primitive_rods",
            "nodes": list(nodes),
            "eliminatedJunctions": list(junctions),
            "rods": rod_records,
        }
        if lineage_extra:
            lineage.update(lineage_extra)
        return cls._build(
            term_list,
            parsed,
            lineage,
            reference_temperatures_k=reference_temperatures_k,
            law_id=law_id,
            run_simplex=False,
        )

    @classmethod
    def from_h1_study(
        cls,
        study_path: str | Path,
        root_path: str | Path,
        *,
        terminals: list[str] | None = None,
        law_id: str | None = None,
    ) -> DerivedLaw:
        """Read-only H1 AST adapter: derive a certified ``DerivedLaw`` directly from
        ``model.mo`` + ``study.json`` without hand-written ``facts.json`` or editing ``h1/*``.
        """
        study = load_study(Path(study_path), Path(root_path))
        if not study.request_report.get("admitted"):
            raise ValueError(f"H1 study was refused: {study.request_report}")
        folder = study.path.parent
        model_path = checked_path(folder, study.data["model"]["path"], folder, ".mo")
        raw_model = model_path.read_bytes()
        if sha256(raw_model).hexdigest() != study.model_sha256:
            raise ValueError("H1 model bytes changed relative to study digest")
        model = ExactBindings(raw_model.decode("utf-8")).parse()

        # Union-find over declared component ports from connect() statements.
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for port_name in sorted(model.ports()):
            find(port_name)
        for p1, p2 in model.connections:
            union(p1, p2)

        groups: dict[str, list[str]] = {}
        for port_name in sorted(parent):
            groups.setdefault(find(port_name), []).append(port_name)

        # Assign canonical node names: owner name for Body/FixedTemperature ports,
        # deterministic junction_<k> for ownerless junctions.
        root_to_node: dict[str, str] = {}
        owner_terminals: list[str] = []
        ref_temps: dict[str, Fraction] = {}
        junction_counter = 0

        for root_key in sorted(groups):
            members = groups[root_key]
            owners = []
            for m in members:
                comp_name, _ = m.split(".", 1)
                comp = model.components[comp_name]
                if comp.kind in ("FixedTemperature", "Body"):
                    owners.append((comp_name, comp))
            if len(owners) > 1:
                raise ValueError(f"multiple owners connected to one ideal node: {[o[0] for o in owners]}")
            if len(owners) == 1:
                owner_name, comp = owners[0]
                root_to_node[root_key] = owner_name
                owner_terminals.append(owner_name)
                t_val = comp.fields["T"].value if comp.kind == "FixedTemperature" else comp.fields["T_initial"].value
                ref_temps[owner_name] = Fraction(t_val)
            else:
                junction_counter += 1
                root_to_node[root_key] = f"junction_{junction_counter}"

        nodes = sorted(root_to_node.values())
        term_list = sorted(owner_terminals) if terminals is None else list(terminals)
        if len(term_list) < 2:
            raise ValueError("H1 study must contain at least two external terminals for a terminal law")

        rods: dict[str, dict[str, Any]] = {}
        for comp_name, comp in sorted(model.components.items()):
            if comp.kind not in ("RodArea", "RodCircular"):
                continue
            node_a = root_to_node[find(f"{comp_name}.port_a")]
            node_b = root_to_node[find(f"{comp_name}.port_b")]
            if comp.kind == "RodArea":
                rods[comp_name] = {
                    "kind": "rod_area",
                    "a": node_a,
                    "b": node_b,
                    "k": Fraction(comp.fields["k"].value),
                    "L": Fraction(comp.fields["L"].value),
                    "A": Fraction(comp.fields["A"].value),
                }
            else:
                rods[comp_name] = {
                    "kind": "rod_circular",
                    "a": node_a,
                    "b": node_b,
                    "k": Fraction(comp.fields["k"].value),
                    "L": Fraction(comp.fields["L"].value),
                    "d": Fraction(comp.fields["d"].value),
                }

        selected_refs = (
            {t: ref_temps[t] for t in term_list}
            if all(t in ref_temps for t in term_list)
            else None
        )
        return cls.from_rods(
            nodes,
            rods,
            terminals=term_list,
            law_id=law_id or study.data["id"],
            lineage_extra={
                "kind": "h1_study_ast",
                "studyId": study.data["id"],
                "studyMode": study.data["mode"],
                "studySha256": study.sha256,
                "modelSha256": study.model_sha256,
            },
            reference_temperatures_k=selected_refs,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DerivedLaw:
        """Validate any accepted law mapping (derived, legacy pinned, or joined) into a ``DerivedLaw``."""
        if not isinstance(payload, dict):
            raise ValueError("terminal law must be a mapping or DerivedLaw")
        schema = payload.get("schema")
        if schema not in ACCEPTED_LAW_SCHEMAS:
            raise ValueError(f"unsupported terminal law schema {schema!r}; expected one of {ACCEPTED_LAW_SCHEMAS}")

        _check_offline_flags(payload, require_present=(schema != PINNED_LAW_SCHEMA))
        terminals = payload.get("terminals")
        if (
            not isinstance(terminals, list)
            or len(terminals) < 2
            or any(not isinstance(t, str) or not t for t in terminals)
            or len(set(terminals)) != len(terminals)
        ):
            raise ValueError("terminal law requires at least two unique non-empty terminal names")
        tset = set(terminals)

        raw_matrix = payload.get("supplyResponseBoundsWPerK")
        if not isinstance(raw_matrix, dict) or set(raw_matrix) != tset:
            raise ValueError("supplyResponseBoundsWPerK rows must match terminals exactly")
        parsed: dict[str, dict[str, tuple[Fraction, Fraction]]] = {}
        for i in terminals:
            row = raw_matrix[i]
            if not isinstance(row, dict) or set(row) != tset:
                raise ValueError(f"supplyResponseBoundsWPerK[{i}] columns must match terminals")
            parsed[i] = {
                j: parse_interval_bounds(row[j], f"supplyResponseBoundsWPerK[{i}][{j}]")
                for j in terminals
            }

        ref_temps: dict[str, Fraction] | None = None
        if "imposedTemperaturesK" in payload and payload["imposedTemperaturesK"] is not None:
            imposed = payload["imposedTemperaturesK"]
            if not isinstance(imposed, dict) or set(imposed) != tset:
                raise ValueError("imposedTemperaturesK must match terminals exactly")
            ref_temps = {}
            for name, temp_str in imposed.items():
                temp = _parse_rational_str(temp_str, f"imposedTemperaturesK[{name}]")
                if temp < 0:
                    raise ValueError(f"imposedTemperaturesK[{name}] must be nonnegative")
                ref_temps[name] = temp

        legacy_prov = None
        if schema == PINNED_LAW_SCHEMA:
            legacy_prov = offline_provenance(payload)
            if ref_temps is None:
                raise ValueError("pinned law imposedTemperaturesK is required")
            lineage: dict[str, Any] = {
                "kind": "legacy_pinned_law",
                "modelSha256": legacy_prov["modelSha256"],
                "studySha256": legacy_prov["studySha256"],
                "factsSha256": legacy_prov["factsSha256"],
            }
            law_id = None
        elif schema == JOINED_LAW_SCHEMA:
            sources = payload.get("sources")
            if not isinstance(sources, dict) or set(sources) != {"left", "right"}:
                raise ValueError("joined terminal law requires sources.{left, right}")
            for side in ("left", "right"):
                src = sources[side]
                if not isinstance(src, dict):
                    raise ValueError(f"joined terminal law sources.{side} must be a mapping")
                for key in ("modelSha256", "studySha256", "factsSha256"):
                    digest = src.get(key)
                    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
                        raise ValueError(f"joined terminal law sources.{side}.{key} must be 64-hex SHA-256")
                if not isinstance(src.get("contact"), str) or not src["contact"]:
                    raise ValueError(f"joined terminal law sources.{side}.contact must be a non-empty string")
            lineage = {
                "kind": "legacy_joined_law",
                "sources": sources,
            }
            law_id = None
        else:
            # sim_heat.derived_terminal_law/1
            if payload.get("unit") != LAW_UNIT:
                raise ValueError(f"derived law unit must be {LAW_UNIT!r}")
            if payload.get("signConvention") != LAW_SIGN_CONVENTION:
                raise ValueError(f"derived law signConvention must be {LAW_SIGN_CONVENTION!r}")
            if payload.get("endpointMeaning") != ENDPOINT_MEANING:
                raise ValueError(f"derived law endpointMeaning must be {ENDPOINT_MEANING!r}")
            lineage_raw = payload.get("lineage")
            if not isinstance(lineage_raw, dict) or not isinstance(lineage_raw.get("kind"), str):
                raise ValueError("derived law requires lineage mapping with string kind")
            lineage = lineage_raw
            law_id = payload.get("lawId")
            if law_id is not None and (not isinstance(law_id, str) or not law_id.strip()):
                raise ValueError("derived law lawId must be a non-empty string when provided")
            declared_sha = payload.get("contentSha256")
            if declared_sha is not None:
                if not isinstance(declared_sha, str) or not _SHA256_RE.fullmatch(declared_sha):
                    raise ValueError("derived law contentSha256 must be a 64-lowercase-hex SHA-256")
                expected_sha = _compute_law_sha256(tuple(terminals), parsed, lineage)
                if declared_sha != expected_sha:
                    raise ValueError(
                        f"derived law contentSha256 mismatch: declared {declared_sha}, computed {expected_sha}"
                    )

        return cls._build(
            terminals,
            parsed,
            lineage,
            reference_temperatures_k=ref_temps,
            law_id=law_id,
            legacy_provenance=legacy_prov,
            run_simplex=True,
        )

    @classmethod
    def from_file(cls, path: str | Path, *, expected_sha256: str | None = None) -> DerivedLaw:
        """Load and validate a serialized law JSON file with optional byte-exact SHA-256 check."""
        file_path = Path(path)
        if not file_path.is_file() or any(p.is_symlink() for p in (file_path, *file_path.parents)):
            raise ValueError(f"invalid law file path: {path}")
        raw = file_path.read_bytes()
        if expected_sha256 is not None:
            if not isinstance(expected_sha256, str) or not _SHA256_RE.fullmatch(expected_sha256):
                raise ValueError("expected_sha256 must be a 64-lowercase-hex SHA-256")
            actual = sha256(raw).hexdigest()
            if actual != expected_sha256:
                raise ValueError(f"law file SHA-256 mismatch: expected {expected_sha256}, got {actual}")
        payload = json.loads(raw.decode("utf-8"))
        return cls.from_dict(payload)


def ensure_derived_law(law: DerivedLaw | dict[str, Any]) -> DerivedLaw:
    """Return a certified ``DerivedLaw`` from either a ``DerivedLaw`` or validated law dict."""
    if isinstance(law, DerivedLaw):
        return law
    return DerivedLaw.from_dict(law)


def validate_terminal_law(law: DerivedLaw | dict[str, Any]) -> tuple[DerivedLaw, dict[str, Any]]:
    """Validate any accepted law input and return ``(derived_law, provenance_block)``."""
    resolved = ensure_derived_law(law)
    return resolved, resolved.provenance_block()


def join_laws(
    left: DerivedLaw | dict[str, Any],
    right: DerivedLaw | dict[str, Any],
    contacts: list[tuple[str, str]] | list[dict[str, str]],
    *,
    left_prefix: str = "left",
    right_prefix: str = "right",
    law_id: str | None = None,
) -> DerivedLaw:
    """Join two validated ``DerivedLaw``s across one or more ideal storage-free contacts.

    Eliminates every contact pair ``(left_port, right_port)`` by imposing
    ``T_left = T_right`` and zero net external heat supply at each contact, yielding
    the certified Schur-complement passive terminal law on all retained external ports.
    """
    left_law = ensure_derived_law(left)
    right_law = ensure_derived_law(right)

    if not isinstance(contacts, (list, tuple)) or not contacts:
        raise ValueError("join_laws requires at least one (left_port, right_port) contact")

    contact_pairs: list[tuple[str, str]] = []
    used_left: set[str] = set()
    used_right: set[str] = set()
    for entry in contacts:
        if isinstance(entry, dict):
            if set(entry) != {"leftPort", "rightPort"}:
                raise ValueError("contact dict must have exact keys ['leftPort', 'rightPort']")
            lp, rp = entry["leftPort"], entry["rightPort"]
        elif isinstance(entry, (list, tuple)) and len(entry) == 2:
            lp, rp = entry
        else:
            raise ValueError("each contact must be a (left_port, right_port) pair or {leftPort, rightPort}")
        if lp not in left_law.terminals:
            raise ValueError(f"unknown left contact terminal {lp!r}")
        if rp not in right_law.terminals:
            raise ValueError(f"unknown right contact terminal {rp!r}")
        if lp in used_left or rp in used_right:
            raise ValueError(f"duplicate contact port in ({lp!r}, {rp!r})")
        used_left.add(lp)
        used_right.add(rp)
        contact_pairs.append((lp, rp))

    def _label(prefix: str, port: str) -> str:
        return f"{prefix}.{port}" if prefix else port

    ext_left = [(p, _label(left_prefix, p)) for p in left_law.terminals if p not in used_left]
    ext_right = [(p, _label(right_prefix, p)) for p in right_law.terminals if p not in used_right]
    external = [lbl for _, lbl in ext_left] + [lbl for _, lbl in ext_right]
    if len(external) < 2:
        raise ValueError("joined terminal law must retain at least two external terminals")
    if len(set(external)) != len(external):
        raise ValueError("joined external terminal labels collide; choose distinct prefixes")

    n_ext = len(external)
    n_c = len(contact_pairs)
    left_ext_map = {p: lbl for p, lbl in ext_left}
    right_ext_map = {p: lbl for p, lbl in ext_right}
    ext_idx = {lbl: k for k, lbl in enumerate(external)}

    # Assemble combined block matrices (EE, EC, CE, CC) in exact (lo, hi) pairs.
    w_ee = [[(Fraction(0), Fraction(0)) for _ in range(n_ext)] for _ in range(n_ext)]
    w_ec = [[(Fraction(0), Fraction(0)) for _ in range(n_c)] for _ in range(n_ext)]
    w_ce = [[(Fraction(0), Fraction(0)) for _ in range(n_ext)] for _ in range(n_c)]
    w_cc = [[(Fraction(0), Fraction(0)) for _ in range(n_c)] for _ in range(n_c)]

    def _add_interval(cur: tuple[Fraction, Fraction], delta: tuple[Fraction, Fraction]) -> tuple[Fraction, Fraction]:
        return (cur[0] + delta[0], cur[1] + delta[1])

    # Left contributions
    for p, lbl_p in ext_left:
        ip = ext_idx[lbl_p]
        for q, lbl_q in ext_left:
            w_ee[ip][ext_idx[lbl_q]] = left_law.matrix[p][q]
        for c_k, (lp, _) in enumerate(contact_pairs):
            w_ec[ip][c_k] = left_law.matrix[p][lp]
            w_ce[c_k][ip] = left_law.matrix[lp][p]
    for c_i, (lp_i, _) in enumerate(contact_pairs):
        for c_j, (lp_j, _) in enumerate(contact_pairs):
            w_cc[c_i][c_j] = _add_interval(w_cc[c_i][c_j], left_law.matrix[lp_i][lp_j])

    # Right contributions
    for p, lbl_p in ext_right:
        ip = ext_idx[lbl_p]
        for q, lbl_q in ext_right:
            w_ee[ip][ext_idx[lbl_q]] = right_law.matrix[p][q]
        for c_k, (_, rp) in enumerate(contact_pairs):
            w_ec[ip][c_k] = right_law.matrix[p][rp]
            w_ce[c_k][ip] = right_law.matrix[rp][p]
    for c_i, (_, rp_i) in enumerate(contact_pairs):
        for c_j, (_, rp_j) in enumerate(contact_pairs):
            w_cc[c_i][c_j] = _add_interval(w_cc[c_i][c_j], right_law.matrix[rp_i][rp_j])

    if left_law.is_exact_point and right_law.is_exact_point:
        # Exact Fraction Schur complement W_EE - W_EC * W_CC^{-1} * W_CE (zero width).
        m_cc = [[w_cc[i][j][0] for j in range(n_c)] for i in range(n_c)]
        m_cc_inv = _exact_invert(m_cc)
        tmp = [
            [sum((m_cc_inv[r][k] * w_ce[k][j][0] for k in range(n_c)), Fraction(0)) for j in range(n_ext)]
            for r in range(n_c)
        ]
        parsed: dict[str, dict[str, tuple[Fraction, Fraction]]] = {}
        for i, lbl_i in enumerate(external):
            parsed[lbl_i] = {}
            for j, lbl_j in enumerate(external):
                val = w_ee[i][j][0] - sum((w_ec[i][k][0] * tmp[k][j] for k in range(n_c)), Fraction(0))
                parsed[lbl_i][lbl_j] = (val, val)
    elif n_c == 1:
        # Single-contact certified Box Schur complement.
        pivot = Box.bounds(*w_cc[0][0])
        if pivot.span()[0] <= 0:
            raise ValueError("contact conductance is unresolved")
        raw_mat: dict[str, dict[str, tuple[Fraction, Fraction]]] = {}
        for i, lbl_i in enumerate(external):
            raw_mat[lbl_i] = {}
            ec_i = Box.bounds(*w_ec[i][0])
            for j, lbl_j in enumerate(external):
                ee_ij = Box.bounds(*w_ee[i][j])
                ce_j = Box.bounds(*w_ce[0][j])
                # Note: ec_i <= 0 and ce_j <= 0 so ec_i * ce_j >= 0; subtract from ee_ij.
                val = ee_ij - (ec_i * ce_j) / pivot
                raw_mat[lbl_i][lbl_j] = val.span()
        parsed = _tighten_passive_interval_matrix(external, raw_mat)
    else:
        # Multi-contact certified M-matrix interval enclosure:
        # For M in [M_lo, M_hi] with M_lo^{-1} >= 0 and M_hi^{-1} >= 0,
        # 0 <= M_hi^{-1} <= M^{-1} <= M_lo^{-1} elementwise.
        # With B = -W_CE >= 0, 0 <= M_hi^{-1} B_lo <= M^{-1} B <= M_lo^{-1} B_hi.
        m_lo = [[w_cc[i][j][0] for j in range(n_c)] for i in range(n_c)]
        m_hi = [[w_cc[i][j][1] for j in range(n_c)] for i in range(n_c)]
        try:
            inv_lo = _exact_invert(m_lo)
            inv_hi = _exact_invert(m_hi)
        except ValueError as exc:
            raise ValueError("multi-contact interval join pivot matrix is singular") from exc
        if any(inv_lo[i][j] < 0 or inv_hi[i][j] < 0 for i in range(n_c) for j in range(n_c)):
            raise ValueError("multi-contact interval join pivot matrix is not certified M-matrix invertible")
        # Compute X = -W_CC^{-1} * W_CE = M^{-1} * B >= 0.
        x_box = [[ZERO for _ in range(n_ext)] for _ in range(n_c)]
        for r in range(n_c):
            for j in range(n_ext):
                x_lo = sum((inv_hi[r][k] * max(Fraction(0), -w_ce[k][j][1]) for k in range(n_c)), Fraction(0))
                x_hi = sum((inv_lo[r][k] * max(Fraction(0), -w_ce[k][j][0]) for k in range(n_c)), Fraction(0))
                if x_lo > x_hi:
                    raise ValueError("multi-contact interval join M-matrix enclosure inverted")
                x_box[r][j] = Box.bounds(x_lo, x_hi)
        raw_mat = {}
        for i, lbl_i in enumerate(external):
            raw_mat[lbl_i] = {}
            for j, lbl_j in enumerate(external):
                val = Box.bounds(*w_ee[i][j])
                for k in range(n_c):
                    val = val + Box.bounds(*w_ec[i][k]) * x_box[k][j]
                raw_mat[lbl_i][lbl_j] = val.span()
        parsed = _tighten_passive_interval_matrix(external, raw_mat)

    ref_temps: dict[str, Fraction] | None = None
    if left_law.reference_temperatures_k is not None and right_law.reference_temperatures_k is not None:
        ref_temps = {}
        for p, lbl in ext_left:
            ref_temps[lbl] = left_law.reference_temperatures_k[p]
        for p, lbl in ext_right:
            ref_temps[lbl] = right_law.reference_temperatures_k[p]

    lineage = {
        "kind": "schur_join",
        "contacts": [{"leftPort": lp, "rightPort": rp} for lp, rp in contact_pairs],
        "leftPrefix": left_prefix,
        "rightPrefix": right_prefix,
        "left": left_law.lineage_ref(),
        "right": right_law.lineage_ref(),
    }
    return DerivedLaw._build(
        external,
        parsed,
        lineage,
        reference_temperatures_k=ref_temps,
        law_id=law_id,
        run_simplex=True,
    )
