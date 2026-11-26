"""Certified nonlinear radiating & convecting transient thermal network solver (M07).

Composes any validated connected passive steady conduction law (``DerivedLaw``, pinned H1
terminal response, or Schur-joined network, with optional uniform rod heat generation Norton
injections) with arbitrary per-terminal attachments of:
- ``sensible_body``: finite heat-capacity body (C_i > 0, T_i(0) >= 0, optional signed ``heatInputW``)
- ``phase_substance``: piecewise-linear enthalpy substance (``solid`` <-> ``plateau`` <-> ``liquid``)
- ``maintained``: fixed Dirichlet reservoir with cumulative energy ledger
- ``exterior_surface``: storage-free diffuse-gray radiating (eps*sigma*(T^4 - T_env^4)) and/or
  convecting (h*(T - T_air)) exterior boundary
- ``radial_shell``: storage-free multi-layer spherical or cylindrical shell with radiating and/or
  convecting exterior boundary

Mathematical method (100% exact-rational, zero floating-point approximation):
1. At each step [t, t + h], certifies an a-priori Picard-Lindelof state box [L_S, U_S] and
   algebraic surface box [L_A, U_A] using the monotone M-function steady algebraic solver.
2. Uses the exact global convexity of T^4 on [a_s, b_s]:
   - Secant chord on [a_s, b_s] gives a certified linear UPPER exterior flux bound -> linear
     Metzler LOWER comparison ODE (y_lo(t + h) <= T_S(t + h) unconditionally by Duhamel positivity).
   - Tangent line at (a_s + b_s)/2 gives a certified linear LOWER exterior flux bound -> linear
     Metzler UPPER comparison ODE (T_S(t + h) <= y_hi(t + h) unconditionally by Duhamel positivity).
3. Eliminates the linearized storage-free algebraic nodes via certified Schur/harmonic reduction
   (exact rational Gaussian elimination for exact-point networks; monotone M-matrix enclosure with
   residual certification for interval networks / radial shells) and advances both comparison ODEs
   with outward-rounded ``simheat.core.step_matrix`` + outward 10^-24 rational grid clamping.
4. Supports exact sequential ``solid`` <-> ``plateau`` <-> ``liquid`` phase transitions via
   certified step-halving event bracketing and verifies global energy conservation containing zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from qualification.h1_n11.rational_dynamic_proof import apply
from simheat.core import Box, ONE, ZERO, step_matrix
from simheat.enthalpy import (
    DEFAULT_MAX_EVENTS,
    _PortSpec,
    _node_event_check,
    _phase_masses_from_state,
    _validate_positive_int,
    signed_decimal_input,
)
from simheat.laws import _monotone_junction_enclosure, _outward_clamp_fraction, validate_terminal_law
from tools.join_thermal_networks import bounds
from tools.multiport_thermal_network import (
    _exterior_flux_per_area,
    _exterior_outflow_box,
    _parse_exterior,
    _solve_exact_linear_fractions,
    _solve_monotone_network,
    _symmetric_conductances,
)
from tools.offline_investigation import _expect_exact_keys
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS
from tools.radiating_surface import decimal_input
from tools.spherical_conduction import prepare_layers

RADIATIVE_TRANSIENT_SCHEMA = "sim_heat.offline_radiative_transient/1"
EVIDENCE_CATEGORY = "offline_analytical_calculation"
VALID_PORT_KINDS = ("sensible_body", "phase_substance", "maintained", "exterior_surface", "radial_shell")

MAX_INITIAL_STEPS = 256
DEFAULT_INITIAL_STEPS = 32
DEFAULT_MAX_STEP_REFINEMENTS = 192
_CLAMP_SCALE = 10**24


def _clamp_box(box: Box, *, scale: int = _CLAMP_SCALE) -> Box:
    lo, hi = box.span()
    return Box.bounds(
        _outward_clamp_fraction(lo, round_up=False, scale=scale),
        _outward_clamp_fraction(hi, round_up=True, scale=scale),
    )


def _box_union(boxes: list[Box]) -> Box:
    return Box.bounds(min(b.span()[0] for b in boxes), max(b.span()[1] for b in boxes))


def _box_intersect(a: Box, b: Box, label: str) -> Box:
    lo = max(a.span()[0], b.span()[0])
    hi = min(a.span()[1], b.span()[1])
    if lo > hi:
        raise ValueError(f"{label} enclosures are inconsistent: [{lo}, {hi}]")
    return Box.bounds(lo, hi)


def _parse_radiative_ports(
    terminals: list[str], ports: dict[str, Any]
) -> tuple[dict[str, _PortSpec], dict[str, dict[str, Any]], list[str], list[str], list[str], list[str]]:
    """Parse all terminal specs for radiative transient integration."""
    if not isinstance(ports, dict) or set(ports) != set(terminals):
        raise ValueError("ports mapping must assign an attachment to every terminal in the network")

    dyn_specs: dict[str, _PortSpec] = {}
    ext_specs: dict[str, dict[str, Any]] = {}
    body_ports: list[str] = []
    phase_ports: list[str] = []
    maintained_ports: list[str] = []
    exterior_ports: list[str] = []

    for name in terminals:
        spec = ports[name]
        if not isinstance(spec, dict):
            raise ValueError(f"port {name!r} specification must be a mapping")
        kind = spec.get("kind")
        if kind not in VALID_PORT_KINDS:
            raise ValueError(f"port {name!r} has unsupported kind {kind!r}; expected one of {VALID_PORT_KINDS}")

        if kind == "sensible_body":
            _expect_exact_keys(
                spec,
                required=("kind", "initialTemperatureK"),
                optional=("heatCapacityJPerK", "massKg", "specificHeatJPerKgK", "heatInputW"),
                label=f"ports[{name}]",
            )
            t0 = decimal_input(spec["initialTemperatureK"], f"initial temperature at {name}")
            has_c = "heatCapacityJPerK" in spec
            has_mc = "massKg" in spec or "specificHeatJPerKgK" in spec
            if has_mc and ("massKg" not in spec or "specificHeatJPerKgK" not in spec):
                raise ValueError(f"ports[{name}] requires both massKg and specificHeatJPerKgK")
            if not has_c and not has_mc:
                raise ValueError(f"ports[{name}] requires heatCapacityJPerK or (massKg and specificHeatJPerKgK)")
            if has_c:
                cap = decimal_input(spec["heatCapacityJPerK"], f"heat capacity at {name}")
                if cap <= 0:
                    raise ValueError(f"positive heat capacity required at {name}")
                if has_mc:
                    m = decimal_input(spec["massKg"], f"mass at {name}")
                    c = decimal_input(spec["specificHeatJPerKgK"], f"specific heat at {name}")
                    if m <= 0 or c <= 0 or m * c != cap:
                        raise ValueError(f"ports[{name}] massKg * specificHeatJPerKgK disagrees with heatCapacityJPerK")
            else:
                m = decimal_input(spec["massKg"], f"mass at {name}")
                c = decimal_input(spec["specificHeatJPerKgK"], f"specific heat at {name}")
                if m <= 0 or c <= 0:
                    raise ValueError(f"positive massKg and specificHeatJPerKgK required at {name}")
                cap = m * c
            power = signed_decimal_input(spec["heatInputW"], f"heatInputW at {name}") if "heatInputW" in spec else Fraction(0)
            dyn_specs[name] = _PortSpec(name=name, kind="sensible_body", t0=t0, capacity=cap, heat_input=power)
            body_ports.append(name)

        elif kind == "phase_substance":
            _expect_exact_keys(
                spec,
                required=(
                    "kind",
                    "transitionTemperatureK",
                    "specificLatentHeatJPerKg",
                    "solidSpecificHeatJPerKgK",
                    "liquidSpecificHeatJPerKgK",
                    "initialSolidKg",
                    "initialLiquidKg",
                ),
                optional=("initialTemperatureK", "heatInputW"),
                label=f"ports[{name}]",
            )
            t_tr = decimal_input(spec["transitionTemperatureK"], f"transition temperature at {name}")
            latent = decimal_input(spec["specificLatentHeatJPerKg"], f"specific latent heat at {name}")
            c_s = decimal_input(spec["solidSpecificHeatJPerKgK"], f"solid specific heat at {name}")
            c_l = decimal_input(spec["liquidSpecificHeatJPerKgK"], f"liquid specific heat at {name}")
            solid0 = decimal_input(spec["initialSolidKg"], f"initial solid mass at {name}")
            liquid0 = decimal_input(spec["initialLiquidKg"], f"initial liquid mass at {name}")
            if min(t_tr, latent, c_s, c_l) <= 0 or solid0 < 0 or liquid0 < 0 or (solid0 + liquid0) <= 0:
                raise ValueError(f"invalid phase_substance parameters at {name}")
            t0 = (
                decimal_input(spec["initialTemperatureK"], f"initial temperature at {name}")
                if "initialTemperatureK" in spec
                else t_tr
            )
            if t0 < t_tr and (solid0 <= 0 or liquid0 != 0):
                raise ValueError(f"subcooled phase_substance at {name} requires positive solid and zero liquid")
            if t0 > t_tr and (liquid0 <= 0 or solid0 != 0):
                raise ValueError(f"superheated phase_substance at {name} requires positive liquid and zero solid")
            power = signed_decimal_input(spec["heatInputW"], f"heatInputW at {name}") if "heatInputW" in spec else Fraction(0)
            dyn_specs[name] = _PortSpec(
                name=name,
                kind="phase_substance",
                t0=t0,
                t_tr=t_tr,
                latent=latent,
                c_s=c_s,
                c_l=c_l,
                solid0=solid0,
                liquid0=liquid0,
                heat_input=power,
            )
            phase_ports.append(name)

        elif kind == "maintained":
            _expect_exact_keys(spec, required=("kind", "temperatureK"), label=f"ports[{name}]")
            temp = decimal_input(spec["temperatureK"], f"maintained temperature at {name}")
            dyn_specs[name] = _PortSpec(name=name, kind="maintained", t0=temp)
            maintained_ports.append(name)

        elif kind == "exterior_surface":
            _expect_exact_keys(
                spec,
                required=("kind", "areaM2", "enclosureTemperatureK", "emissivity", "sigmaWPerM2K4"),
                optional=("airTemperatureK", "convectionCoefficientWPerM2K"),
                label=f"ports[{name}]",
            )
            area = decimal_input(spec["areaM2"], f"surface area at {name}")
            if area <= 0:
                raise ValueError(f"positive surface area required at {name}")
            ext = _parse_exterior(spec)
            ext_specs[name] = {
                "kind": "radiating_surface",
                "orig_kind": "exterior_surface",
                "area": (area, area),
                **ext,
            }
            exterior_ports.append(name)

        else:  # radial_shell
            _expect_exact_keys(spec, required=("kind", "geometry", "exterior"), label=f"ports[{name}]")
            geom = spec["geometry"]
            ext_raw = spec["exterior"]
            if not isinstance(geom, dict) or not isinstance(ext_raw, dict):
                raise ValueError(f"ports[{name}] geometry and exterior must be mappings")
            _expect_exact_keys(
                geom,
                required=("kind", "innerRadiusM", "layers"),
                optional=("cylinderLengthM",),
                label=f"ports[{name}].geometry",
            )
            _expect_exact_keys(
                ext_raw,
                required=("enclosureTemperatureK", "emissivity", "sigmaWPerM2K4"),
                optional=("airTemperatureK", "convectionCoefficientWPerM2K"),
                label=f"ports[{name}].exterior",
            )
            g_kind = geom.get("kind")
            if g_kind not in ("sphere", "cylinder"):
                raise ValueError(f"radial_shell geometry.kind at {name!r} must be 'sphere' or 'cylinder'")
            cyl_len = geom.get("cylinderLengthM")
            if g_kind == "sphere" and cyl_len is not None:
                raise ValueError(f"sphere radial_shell at {name!r} does not accept cylinderLengthM")
            if g_kind == "cylinder" and cyl_len is None:
                raise ValueError(f"cylinder radial_shell at {name!r} requires cylinderLengthM")
            raw_layers = geom.get("layers")
            if not isinstance(raw_layers, list) or not (1 <= len(raw_layers) <= 32):
                raise ValueError(f"radial_shell at {name!r} requires 1 to 32 layers")
            layer_pairs = []
            for idx, lyr in enumerate(raw_layers):
                if not isinstance(lyr, dict):
                    raise ValueError(f"ports[{name}].geometry.layers[{idx}] must be a mapping")
                _expect_exact_keys(
                    lyr,
                    required=("outerRadiusM", "conductivityWPerMK"),
                    label=f"ports[{name}].geometry.layers[{idx}]",
                )
                layer_pairs.append((lyr["outerRadiusM"], lyr["conductivityWPerMK"]))
            shell = prepare_layers(geom["innerRadiusM"], layer_pairs, cyl_len)
            ext = _parse_exterior(ext_raw)
            r_lo, r_hi = shell.resistances[-1].span()
            g_shell = (Fraction(1) / r_hi, Fraction(1) / r_lo)
            ext_specs[name] = {
                "kind": "radial_shell",
                "orig_kind": "radial_shell",
                "shell": shell,
                "g_shell": g_shell,
                "area": shell.outer_area().span(),
                **ext,
            }
            exterior_ports.append(name)

    if not body_ports and not phase_ports:
        raise ValueError("at least one sensible_body or phase_substance port is required")
    if not exterior_ports:
        raise ValueError("at least one exterior_surface or radial_shell port is required")
    return dyn_specs, ext_specs, body_ports, phase_ports, maintained_ports, exterior_ports


def _solve_algebraic_box(
    terminals: list[str],
    dyn_nodes: list[str],
    ext_specs: dict[str, dict[str, Any]],
    t_dyn_box: dict[str, Box],
    w_net: dict[tuple[str, str], tuple[Fraction, Fraction]],
    inj_map: dict[str, tuple[Fraction, Fraction]],
    *,
    max_sweeps: int = 120,
) -> tuple[dict[str, Box], dict[str, Box]]:
    """Solve certified algebraic steady box for all exterior/shell unknowns given dynamic temperature boxes.

    Exploits cooperativity of the steady M-function:
    - lower algebraic bound solved with dynamic nodes clamped at t_dyn_box[d].lo;
    - upper algebraic bound solved with dynamic nodes clamped at t_dyn_box[d].hi.
    Returns ``(port_temps, surface_temps)`` for every exterior port.
    """
    mp_lo: dict[str, dict[str, Any]] = {}
    mp_hi: dict[str, dict[str, Any]] = {}
    for name in terminals:
        if name in ext_specs:
            mp_lo[name] = ext_specs[name]
            mp_hi[name] = ext_specs[name]
        else:
            lo, hi = t_dyn_box[name].span()
            mp_lo[name] = {"kind": "maintained", "temp": lo}
            mp_hi[name] = {"kind": "maintained", "temp": hi}

    u_lo_sol, _, _ = _solve_monotone_network(terminals, mp_lo, w_net, max_sweeps=max_sweeps, inj_map=inj_map)
    if all(t_dyn_box[d].span()[0] == t_dyn_box[d].span()[1] for d in dyn_nodes):
        u_hi_sol = u_lo_sol
    else:
        u_hi_sol, _, _ = _solve_monotone_network(terminals, mp_hi, w_net, max_sweeps=max_sweeps, inj_map=inj_map)

    port_temps: dict[str, Box] = {}
    surf_temps: dict[str, Box] = {}
    for name, es in ext_specs.items():
        p_lo = u_lo_sol[f"port:{name}"][0]
        p_hi = u_hi_sol[f"port:{name}"][1]
        if p_lo > p_hi:
            raise ValueError(f"algebraic exterior enclosure inverted at port {name!r}")
        port_temps[name] = _clamp_box(Box.bounds(p_lo, p_hi))
        if es["kind"] == "radial_shell":
            s_lo = u_lo_sol[f"surface:{name}"][0]
            s_hi = u_hi_sol[f"surface:{name}"][1]
            if s_lo > s_hi:
                raise ValueError(f"algebraic radial_shell surface enclosure inverted at port {name!r}")
            surf_temps[name] = _clamp_box(Box.bounds(s_lo, s_hi))
        else:
            surf_temps[name] = port_temps[name]
    return port_temps, surf_temps


def _linearize_exterior_flux(ext: dict[str, Any], a_s: Fraction, b_s: Fraction, *, mode: str) -> tuple[Fraction, Fraction]:
    """Return exact nonnegative linear flux parameters ``(h_eff, c_const)`` on ``[a_s, b_s]``.

    Such that ``q_ext(T) = h*(T - T_air) + eps*sigma*(T^4 - T_env^4)`` satisfies:
    - ``mode == "secant"`` (UPPER flux bound -> LOWER temperature comparison ODE):
      ``q_ext(T) <= h_eff * T - c_const`` for all ``T in [a_s, b_s]``;
    - ``mode == "tangent"`` (LOWER flux bound -> UPPER temperature comparison ODE):
      ``q_ext(T) >= h_eff * T - c_const`` for all ``T in R``.
    Both have ``h_eff >= 0`` and ``c_const >= 0``.
    """
    h = ext["h"]
    air_k = ext["air_k"]
    eps = ext["eps"]
    sig = ext["sigma"]
    env_k = ext["env_k"]

    c_conv = h * air_k if air_k is not None else Fraction(0)
    if eps == 0:
        return h, c_conv

    if mode == "secant":
        alpha = (a_s + b_s) * (a_s * a_s + b_s * b_s)
        beta = a_s * b_s * (a_s * a_s + a_s * b_s + b_s * b_s) + env_k**4
    else:  # tangent at midpoint
        m_s = (a_s + b_s) / 2
        alpha = 4 * (m_s**3)
        beta = 3 * (m_s**4) + env_k**4

    return h + eps * sig * alpha, c_conv + eps * sig * beta


def _solve_interval_linear_m_system(
    alg_ids: list[str],
    adj: dict[str, list[tuple[str, Fraction, Fraction]]],
    diag_anchors: dict[str, list[tuple[Fraction, Fraction, Fraction]]],
    sources: dict[str, tuple[Fraction, Fraction]],
    *,
    exact_point: bool,
) -> dict[str, Box]:
    """Solve certified nonnegative box for M-matrix system L_AA * x = rhs_fixed + sources.

    ``adj[u]`` holds ``(v, g_lo, g_hi)`` for ``v in alg_ids``.
    ``diag_anchors[u]`` holds ``(t_anchor, g_lo, g_hi)`` with ``t_anchor >= 0, g_lo >= 0``.
    ``sources[u]`` holds ``(s_lo, s_hi)`` with ``0 <= s_lo <= s_hi``.
    """
    n_a = len(alg_ids)
    idx_of = {u: i for i, u in enumerate(alg_ids)}

    if exact_point:
        mat = [[Fraction(0)] * n_a for _ in range(n_a)]
        rhs = [sources[u][0] for u in alg_ids]
        for i, u in enumerate(alg_ids):
            diag = Fraction(0)
            for v, g_lo, _ in adj[u]:
                diag += g_lo
                mat[i][idx_of[v]] -= g_lo
            for t_anc, g_lo, _ in diag_anchors[u]:
                diag += g_lo
                rhs[i] += g_lo * t_anc
            mat[i][i] = diag
        sol = _solve_exact_linear_fractions(mat, rhs)
        return {alg_ids[i]: Box.exact(sol[i]) for i in range(n_a)}

    # Interval M-matrix certified enclosure: pure Howard policy iteration for sub-solution & super-solution,
    # followed by independent residual post-condition certification!
    all_t = [t_anc for u in alg_ids for t_anc, _, _ in diag_anchors[u]]
    t_min_anc = min(all_t) if all_t else Fraction(0)

    def _eval_res(vals: dict[str, Fraction], *, maximize: bool) -> dict[str, Fraction]:
        out = {}
        for u in alg_ids:
            tot = -(sources[u][0] if maximize else sources[u][1])
            for v, g_lo, g_hi in adj[u]:
                diff = vals[u] - vals[v]
                w = (g_hi if diff >= 0 else g_lo) if maximize else (g_lo if diff >= 0 else g_hi)
                tot += w * diff
            for t_anc, g_lo, g_hi in diag_anchors[u]:
                diff = vals[u] - t_anc
                w = (g_hi if diff >= 0 else g_lo) if maximize else (g_lo if diff >= 0 else g_hi)
                tot += w * diff
            out[u] = tot
        return out

    def _policy_solve(start_val: Fraction, *, maximize: bool) -> dict[str, Fraction]:
        vals = {u: start_val for u in alg_ids}
        for _ in range(max(32, 4 * n_a + 16)):
            res = _eval_res(vals, maximize=maximize)
            if (maximize and all(v <= 0 for v in res.values())) or (not maximize and all(v >= 0 for v in res.values())):
                break
            mat = [[Fraction(0)] * n_a for _ in range(n_a)]
            rhs = [sources[u][0] if maximize else sources[u][1] for u in alg_ids]
            for i, u in enumerate(alg_ids):
                diag = Fraction(0)
                for v, g_lo, g_hi in adj[u]:
                    diff = vals[u] - vals[v]
                    w = (g_hi if diff >= 0 else g_lo) if maximize else (g_lo if diff >= 0 else g_hi)
                    diag += w
                    mat[i][idx_of[v]] -= w
                for t_anc, g_lo, g_hi in diag_anchors[u]:
                    diff = vals[u] - t_anc
                    w = (g_hi if diff >= 0 else g_lo) if maximize else (g_lo if diff >= 0 else g_hi)
                    diag += w
                    rhs[i] += w * t_anc
                mat[i][i] = diag
            sol = _solve_exact_linear_fractions(mat, rhs)
            vals = {alg_ids[i]: sol[i] for i in range(n_a)}
        # Independent exact residual certification!
        res_f = _eval_res(vals, maximize=maximize)
        if maximize and any(v > 0 for v in res_f.values()):
            raise ValueError("linearized algebraic lower-bound residual certification failed")
        if not maximize and any(v < 0 for v in res_f.values()):
            raise ValueError("linearized algebraic upper-bound residual certification failed")
        return vals

    # For f_max(u) = 0 (lower bound u_lo), start at high value (or run pure Howard from t_max_anc + source bound).
    # Wait: for maximize=True, f_max(u) = max_p (A_p u - b_p) is convex max-of-linear -> pure Howard from ANY
    # super-solution decreases monotonically to the exact fixed point!
    # For maximize=False, f_min(u) = min_p (A_p u - b_p) is concave min-of-linear -> pure Howard from ANY
    # sub-solution (t_min_anc) increases monotonically to the exact fixed point!
    hi_vals = _policy_solve(t_min_anc, maximize=False)
    # hi_vals is a guaranteed super-solution of f_max(u) = 0 because f_max(hi) >= f_min(hi) >= 0!
    # Start maximize=True from hi_vals (actually compute exact policy descent starting at max(hi_vals)):
    start_hi = max(hi_vals.values()) if hi_vals else t_min_anc
    lo_vals = _policy_solve(start_hi, maximize=True)

    out_boxes: dict[str, Box] = {}
    for u in alg_ids:
        if lo_vals[u] > hi_vals[u]:
            raise ValueError(f"linearized algebraic enclosure inverted at {u!r}")
        out_boxes[u] = _clamp_box(Box.bounds(lo_vals[u], hi_vals[u]))
    return out_boxes


def _build_linearized_comparison_ode(
    terminals: list[str],
    sensible: list[str],
    clamped: list[str],
    clamped_t: dict[str, Fraction],
    ext_specs: dict[str, dict[str, Any]],
    caps: dict[str, Fraction],
    p_box: dict[str, Box],
    w_net: dict[tuple[str, str], tuple[Fraction, Fraction]],
    inj_map: dict[str, tuple[Fraction, Fraction]],
    surf_box: dict[str, Box],
    *,
    lin_mode: str,
) -> tuple[list[list[Box]], list[Box], dict[str, dict[str, Box]], dict[str, Box]]:
    """Build certified linearized Schur-reduced ODE ``dT_S/dt = M*T_S + r`` for ``secant`` or ``tangent``.

    Returns ``(M_mat, r_vec, H_basis, v0_map)`` where for every algebraic unknown ``u``:
        ``T_u(t) in sum_{j in sensible} H_basis[j][u] * T_j(t) + v0_map[u]``.
    """
    alg_ids: list[str] = []
    for name in terminals:
        if name in ext_specs:
            alg_ids.append(f"port:{name}")
            if ext_specs[name]["kind"] == "radial_shell":
                alg_ids.append(f"surface:{name}")

    adj: dict[str, list[tuple[str, Fraction, Fraction]]] = {u: [] for u in alg_ids}
    # Separate anchors by dynamic sensible terminal (for H^(j)) vs constant clamped/ambient (for v0).
    sens_anchors: dict[str, dict[str, tuple[Fraction, Fraction]]] = {u: {} for u in alg_ids}
    const_anchors: dict[str, list[tuple[Fraction, Fraction, Fraction]]] = {u: [] for u in alg_ids}
    alg_sources: dict[str, tuple[Fraction, Fraction]] = {u: (Fraction(0), Fraction(0)) for u in alg_ids}

    for name in terminals:
        if name not in ext_specs:
            continue
        es = ext_specs[name]
        u_port = f"port:{name}"
        alg_sources[u_port] = inj_map[name]
        for other in terminals:
            if other == name:
                continue
            w_pair = w_net[(name, other)]
            if w_pair == (Fraction(0), Fraction(0)):
                continue
            if other in ext_specs:
                adj[u_port].append((f"port:{other}", w_pair[0], w_pair[1]))
            elif other in clamped_t:
                const_anchors[u_port].append((clamped_t[other], w_pair[0], w_pair[1]))
            else:
                sens_anchors[u_port][other] = w_pair

        a_s, b_s = surf_box[name].span()
        h_eff, c_const = _linearize_exterior_flux(es, a_s, b_s, mode=lin_mode)
        a_lo, a_hi = es["area"]
        u_ext = f"surface:{name}" if es["kind"] == "radial_shell" else u_port
        if es["kind"] == "radial_shell":
            g_lo, g_hi = es["g_shell"]
            adj[u_port].append((u_ext, g_lo, g_hi))
            adj[u_ext].append((u_port, g_lo, g_hi))
        if h_eff > 0:
            t_amb_eff = c_const / h_eff
            const_anchors[u_ext].append((t_amb_eff, a_lo * h_eff, a_hi * h_eff))
        elif c_const > 0:
            s_lo, s_hi = alg_sources[u_ext]
            alg_sources[u_ext] = (s_lo + a_lo * c_const, s_hi + a_hi * c_const)

    # Check if all conductances, areas, and algebraic injections are exact points.
    exact_all = (
        all(lo == hi for lo, hi in w_net.values())
        and all(es["area"][0] == es["area"][1] for es in ext_specs.values())
        and all(es["kind"] != "radial_shell" for es in ext_specs.values())
        and all(lo == hi for lo, hi in alg_sources.values())
    )

    # Compute H_basis[j][u] in [0, 1] for each sensible node j: T_j = 1, all other terminals/ambients = 0, sources = 0.
    zero_sources = {u: (Fraction(0), Fraction(0)) for u in alg_ids}
    h_basis: dict[str, dict[str, Box]] = {}
    for j in sensible:
        diag_j: dict[str, list[tuple[Fraction, Fraction, Fraction]]] = {}
        for u in alg_ids:
            items = [(Fraction(0), g_lo, g_hi) for _, g_lo, g_hi in const_anchors[u]]
            for s_name, (g_lo, g_hi) in sens_anchors[u].items():
                items.append((Fraction(1) if s_name == j else Fraction(0), g_lo, g_hi))
            diag_j[u] = items
        h_sol = _solve_interval_linear_m_system(alg_ids, adj, diag_j, zero_sources, exact_point=exact_all)
        h_basis[j] = {
            u: Box.bounds(max(Fraction(0), h_sol[u].span()[0]), min(Fraction(1), h_sol[u].span()[1]))
            for u in alg_ids
        }

    # Compute v0_map[u] >= 0: all sensible T_j = 0, clamped at T_c, ambients at T_amb_eff, sources = alg_sources.
    diag_v0: dict[str, list[tuple[Fraction, Fraction, Fraction]]] = {}
    for u in alg_ids:
        items = list(const_anchors[u])
        for _, (g_lo, g_hi) in sens_anchors[u].items():
            items.append((Fraction(0), g_lo, g_hi))
        diag_v0[u] = items
    v0_map = _solve_interval_linear_m_system(alg_ids, adj, diag_v0, alg_sources, exact_point=exact_all)

    # Assemble Schur-reduced Metzler ODE dT_S/dt = M * T_S + r.
    n_s = len(sensible)
    m_mat: list[list[Box]] = [[ZERO for _ in range(n_s)] for _ in range(n_s)]
    r_vec: list[Box] = [ZERO for _ in range(n_s)]
    w_box = {k: Box.bounds(v[0], v[1]) for k, v in w_net.items()}

    for i, bi in enumerate(sensible):
        cap = Box.exact(caps[bi])
        # Diagonal: -(sum_{u != bi} W_{bi, u} - sum_{a in ext} W_{bi, a} * H_a^(bi)) / C_i
        diag_out = ZERO
        for other in terminals:
            if other == bi:
                continue
            wb = w_box[(bi, other)]
            if other in ext_specs:
                diag_out = diag_out + wb * (ONE - h_basis[bi][f"port:{other}"])
            else:
                diag_out = diag_out + wb
        m_mat[i][i] = -diag_out / cap

        # Off-diagonal (j != i): +(W_{bi, bj} + sum_{a in ext} W_{bi, a} * H_a^(bj)) / C_i >= 0
        for j, bj in enumerate(sensible):
            if j == i:
                continue
            coeff = w_box[(bi, bj)]
            for e_name in ext_specs:
                wb = w_box[(bi, e_name)]
                if wb != ZERO:
                    coeff = coeff + wb * h_basis[bj][f"port:{e_name}"]
            m_mat[i][j] = coeff / cap

        # Affine forcing r_i = (sum_{c in clamped} W_{bi, c}*T_c + sum_{a in ext} W_{bi, a}*v0_a + P_i + I_i) / C_i
        rhs_i = p_box[bi]
        for c in clamped:
            rhs_i = rhs_i + w_box[(bi, c)] * clamped_t[c]
        for e_name in ext_specs:
            wb = w_box[(bi, e_name)]
            if wb != ZERO:
                rhs_i = rhs_i + wb * v0_map[f"port:{e_name}"]
        r_vec[i] = rhs_i / cap

    return m_mat, r_vec, h_basis, v0_map


def _advance_linear_system(
    m_mat: list[list[Box]],
    r_vec: list[Box],
    t_start: list[Fraction],
    dt: Fraction,
) -> tuple[list[Box], list[Box]]:
    """Advance linear ODE ``dT/dt = M*T + r`` from exact point ``t_start`` over ``[0, dt]`` via ``step_matrix``.

    Returns ``(t_end_boxes, integral_boxes)`` where ``integral_boxes[i]`` encloses ``int_0^dt T_i(tau) dtau``.
    """
    n = len(t_start)
    if n == 0 or dt == 0:
        return [Box.exact(v) for v in t_start], [Box.exact(v * dt) for v in t_start]

    origin = min(t_start)
    span = max(Fraction(1), max(t_start) - origin)
    dim = 2 * n + 1
    scaled = [[ZERO for _ in range(dim)] for _ in range(dim)]
    for i in range(n):
        row_sum_m = ZERO
        for j in range(n):
            scaled[i][j] = m_mat[i][j] * dt
            row_sum_m = row_sum_m + m_mat[i][j]
        # Shift u = (T - origin)/span => du/dt = M*u + (M*origin*1 + r)/span
        scaled[i][-1] = ((row_sum_m * origin + r_vec[i]) / span) * dt
        scaled[n + i][i] = ONE

    y0 = [Box.exact((v - origin) / span) for v in t_start] + [ZERO] * n + [ONE]
    y = apply(step_matrix(scaled), y0)
    t_end = [y[i] * span + origin for i in range(n)]
    int_t = [(y[n + i] * span + origin) * dt for i in range(n)]
    return t_end, int_t


def _certify_picard_step_box(
    terminals: list[str],
    sensible: list[str],
    clamped: list[str],
    clamped_t: dict[str, Fraction],
    ext_specs: dict[str, dict[str, Any]],
    caps: dict[str, Fraction],
    p_box: dict[str, Box],
    w_net: dict[tuple[str, str], tuple[Fraction, Fraction]],
    inj_map: dict[str, tuple[Fraction, Fraction]],
    t_start_box: dict[str, Box],
    dt: Fraction,
    *,
    max_sweeps: int = 120,
) -> tuple[dict[str, Box], dict[str, Box], dict[str, Box]] | None:
    """Certify a-priori Picard-Lindelof state box on ``[0, dt]``; returns ``None`` if ``dt`` must be halved."""
    dyn_nodes = sensible + clamped
    w_box = {k: Box.bounds(v[0], v[1]) for k, v in w_net.items()}

    def _rhs_on_box(t_s_box: dict[str, Box]) -> tuple[dict[str, Box], dict[str, Box], dict[str, Box]]:
        full_dyn = {**{c: Box.exact(clamped_t[c]) for c in clamped}, **t_s_box}
        p_alg, s_alg = _solve_algebraic_box(
            terminals, dyn_nodes, ext_specs, full_dyn, w_net, inj_map, max_sweeps=max_sweeps
        )
        all_t = {**full_dyn, **p_alg}
        f_box: dict[str, Box] = {}
        for b in sensible:
            q = p_box[b]
            for other in terminals:
                if other == b:
                    continue
                q = q + w_box[(b, other)] * (all_t[other] - all_t[b])
            f_box[b] = q / caps[b]
        return f_box, p_alg, s_alg

    if not sensible:
        full_dyn = {c: Box.exact(clamped_t[c]) for c in clamped}
        p_alg, s_alg = _solve_algebraic_box(
            terminals, dyn_nodes, ext_specs, full_dyn, w_net, inj_map, max_sweeps=max_sweeps
        )
        return {}, p_alg, s_alg

    f0, _, _ = _rhs_on_box(t_start_box)
    # Construct initial candidate box B = T0 + [0, dt]*F0 widened by 50% (plus small floor slack).
    cand: dict[str, Box] = {}
    for b in sensible:
        t_lo, t_hi = t_start_box[b].span()
        d_lo, d_hi = f0[b].span()
        lo_shift = min(Fraction(0), d_lo) * dt
        hi_shift = max(Fraction(0), d_hi) * dt
        slack = max(Fraction(1, 1000), (hi_shift - lo_shift) / 2)
        c_lo = t_lo + lo_shift - slack
        c_hi = t_hi + hi_shift + slack
        if c_lo < 0:
            # Clamp candidate trial at 0 only if start is positive; verify containment honestly below!
            if t_lo > 0 and t_lo + lo_shift > 0:
                c_lo = Fraction(0)
            else:
                return None  # Step too large near 0 K; halve dt!
        cand[b] = _clamp_box(Box.bounds(c_lo, c_hi))

    # Try up to 4 widenings to establish strict Picard inclusion B0 + [0, dt]*F(B) <= B.
    certified = False
    p_alg_cert: dict[str, Box] = {}
    s_alg_cert: dict[str, Box] = {}
    for _ in range(4):
        f_cand, p_alg, s_alg = _rhs_on_box(cand)
        ok = True
        next_cand: dict[str, Box] = {}
        for b in sensible:
            t_lo, t_hi = t_start_box[b].span()
            d_lo, d_hi = f_cand[b].span()
            img_lo = t_lo + min(Fraction(0), d_lo) * dt
            img_hi = t_hi + max(Fraction(0), d_hi) * dt
            c_lo, c_hi = cand[b].span()
            if img_lo < 0:
                return None  # Must halve step to certify T >= 0 K or catch negative T cleanly
            if img_lo < c_lo or img_hi > c_hi:
                ok = False
                span_w = max(Fraction(1, 100), img_hi - img_lo)
                n_lo = max(Fraction(0), min(c_lo, img_lo) - span_w / 2)
                n_hi = max(c_hi, img_hi) + span_w / 2
                next_cand[b] = _clamp_box(Box.bounds(n_lo, n_hi))
            else:
                next_cand[b] = _clamp_box(Box.bounds(max(c_lo, img_lo), min(c_hi, img_hi)))
        if ok:
            cand = next_cand
            p_alg_cert, s_alg_cert = p_alg, s_alg
            certified = True
            break
        cand = next_cand

    if not certified:
        return None

    # 2 Picard contraction sweeps to tighten [L_S, U_S] and [L_A, U_A] before tangent/secant linearization.
    for _ in range(2):
        f_cand, p_alg_cert, s_alg_cert = _rhs_on_box(cand)
        changed = False
        for b in sensible:
            t_lo, t_hi = t_start_box[b].span()
            d_lo, d_hi = f_cand[b].span()
            img_lo = t_lo + min(Fraction(0), d_lo) * dt
            img_hi = t_hi + max(Fraction(0), d_hi) * dt
            c_lo, c_hi = cand[b].span()
            n_lo = max(c_lo, img_lo)
            n_hi = min(c_hi, img_hi)
            if n_lo > n_hi:
                raise ValueError(f"Picard step box collapsed inconsistently at {b!r}")
            new_b = _clamp_box(Box.bounds(n_lo, n_hi))
            if new_b.span() != cand[b].span():
                changed = True
            cand[b] = new_b
        if not changed:
            break
    # Final algebraic box matching the tightened dynamic box.
    full_dyn = {**{c: Box.exact(clamped_t[c]) for c in clamped}, **cand}
    p_alg_cert, s_alg_cert = _solve_algebraic_box(
        terminals, dyn_nodes, ext_specs, full_dyn, w_net, inj_map, max_sweeps=max_sweeps
    )
    return cand, p_alg_cert, s_alg_cert


def _step_radiative_mode(
    terminals: list[str],
    specs: dict[str, _PortSpec],
    ext_specs: dict[str, dict[str, Any]],
    modes: dict[str, str],
    w_net: dict[tuple[str, str], tuple[Fraction, Fraction]],
    inj_map: dict[str, tuple[Fraction, Fraction]],
    p_box: dict[str, Box],
    t_cur: dict[str, Box],
    h_cur: dict[str, Box],
    e_ext_cur: dict[str, Box],
    dt: Fraction,
    *,
    max_sweeps: int = 120,
) -> dict[str, Any] | None:
    """Execute one certified cooperative tangent/secant step over ``dt``.

    Returns ``None`` if Picard step inclusion fails (caller halves ``dt``).
    """
    sensible = [n for n in terminals if n in specs and modes[n] in ("body", "solid", "liquid")]
    clamped = [n for n in terminals if n in specs and modes[n] in ("plateau", "maintained")]
    ext_ports = [n for n in terminals if n in ext_specs]

    caps: dict[str, Fraction] = {}
    for n in sensible:
        sp = specs[n]
        caps[n] = sp.capacity if modes[n] == "body" else (sp.cap_s if modes[n] == "solid" else sp.cap_l)
    clamped_t: dict[str, Fraction] = {
        n: (specs[n].t_tr if modes[n] == "plateau" else specs[n].t0) for n in clamped
    }
    t_s_start = {n: t_cur[n] for n in sensible}

    picard = _certify_picard_step_box(
        terminals, sensible, clamped, clamped_t, ext_specs, caps, p_box, w_net, inj_map,
        t_s_start, dt, max_sweeps=max_sweeps,
    )
    if picard is None:
        return None
    t_s_box, p_alg_box, s_alg_box = picard

    # Build certified secant (lower) and tangent (upper) Metzler comparison ODEs!
    m_sec, r_sec, h_sec, v0_sec = _build_linearized_comparison_ode(
        terminals, sensible, clamped, clamped_t, ext_specs, caps, p_box, w_net, inj_map, s_alg_box, lin_mode="secant"
    )
    m_tan, r_tan, h_tan, v0_tan = _build_linearized_comparison_ode(
        terminals, sensible, clamped, clamped_t, ext_specs, caps, p_box, w_net, inj_map, s_alg_box, lin_mode="tangent"
    )

    t_lo_start = [t_cur[n].span()[0] for n in sensible]
    t_hi_start = [t_cur[n].span()[1] for n in sensible]

    y_lo_end, int_lo_s = _advance_linear_system(m_sec, r_sec, t_lo_start, dt)
    y_hi_end, int_hi_s = _advance_linear_system(m_tan, r_tan, t_hi_start, dt)

    t_next: dict[str, Box] = {}
    int_s_box: dict[str, Box] = {}
    for i, n in enumerate(sensible):
        raw_lo = y_lo_end[i].span()[0]
        raw_hi = y_hi_end[i].span()[1]
        # Intersect with certified Picard step box [L_S, U_S].
        p_lo, p_hi = t_s_box[n].span()
        lo = max(p_lo, raw_lo)
        hi = min(p_hi, raw_hi)
        if lo > hi:
            raise ValueError(f"radiative comparison ODE endpoint enclosure inconsistent at {n!r}")
        t_next[n] = _clamp_box(Box.bounds(lo, hi))

        # Integral enclosure int_0^dt T_n(tau) dtau intersected with [L_S*dt, U_S*dt].
        i_lo = max(p_lo * dt, int_lo_s[i].span()[0])
        i_hi = min(p_hi * dt, int_hi_s[i].span()[1])
        if i_lo > i_hi:
            raise ValueError(f"radiative comparison ODE integral enclosure inconsistent at {n!r}")
        int_s_box[n] = _clamp_box(Box.bounds(i_lo, i_hi))

    for c in clamped:
        t_next[c] = Box.exact(clamped_t[c])

    # Certified integrals of every algebraic exterior port & surface temperature over [0, dt].
    int_alg_port: dict[str, Box] = {}
    int_alg_surf: dict[str, Box] = {}
    for e_name in ext_ports:
        u_p = f"port:{e_name}"
        lo_p = v0_sec[u_p] * dt + sum((h_sec[j][u_p] * int_lo_s[i] for i, j in enumerate(sensible)), ZERO)
        hi_p = v0_tan[u_p] * dt + sum((h_tan[j][u_p] * int_hi_s[i] for i, j in enumerate(sensible)), ZERO)
        pb_lo, pb_hi = p_alg_box[e_name].span()
        ip_lo = max(pb_lo * dt, lo_p.span()[0])
        ip_hi = min(pb_hi * dt, hi_p.span()[1])
        if ip_lo > ip_hi:
            raise ValueError(f"algebraic port integral inconsistent at {e_name!r}")
        int_alg_port[e_name] = _clamp_box(Box.bounds(ip_lo, ip_hi))

        if ext_specs[e_name]["kind"] == "radial_shell":
            u_s = f"surface:{e_name}"
            lo_s = v0_sec[u_s] * dt + sum((h_sec[j][u_s] * int_lo_s[i] for i, j in enumerate(sensible)), ZERO)
            hi_s = v0_tan[u_s] * dt + sum((h_tan[j][u_s] * int_hi_s[i] for i, j in enumerate(sensible)), ZERO)
            sb_lo, sb_hi = s_alg_box[e_name].span()
            is_lo = max(sb_lo * dt, lo_s.span()[0])
            is_hi = min(sb_hi * dt, hi_s.span()[1])
            if is_lo > is_hi:
                raise ValueError(f"algebraic surface integral inconsistent at {e_name!r}")
            int_alg_surf[e_name] = _clamp_box(Box.bounds(is_lo, is_hi))
        else:
            int_alg_surf[e_name] = int_alg_port[e_name]

    # Step-end algebraic temperatures from t_next.
    p_end_alg, s_end_alg = _solve_algebraic_box(
        terminals, sensible + clamped, ext_specs, t_next, w_net, inj_map, max_sweeps=max_sweeps
    )
    for e_name in ext_ports:
        t_next[e_name] = p_end_alg[e_name]

    w_box = {k: Box.bounds(v[0], v[1]) for k, v in w_net.items()}

    # Update enthalpies/energies for sensible and clamped nodes + cumulative exterior outward energy!
    h_next: dict[str, Box] = {}
    for n in sensible:
        h_next[n] = _clamp_box(specs[n].enthalpy_from_temp(modes[n], t_next[n]))

    for c in clamped:
        tc = clamped_t[c]
        de = p_box[c] * dt
        for s in sensible:
            de = de + w_box[(c, s)] * (int_s_box[s] - tc * dt)
        for oc in clamped:
            if oc != c:
                de = de + w_box[(c, oc)] * ((clamped_t[oc] - tc) * dt)
        for e_name in ext_ports:
            de = de + w_box[(c, e_name)] * (int_alg_port[e_name] - tc * dt)
        h_next[c] = _clamp_box(h_cur[c] + de)

    e_ext_next: dict[str, Box] = {}
    for e_name in ext_ports:
        # 1. Network-side cumulative outflow over [0, dt]
        de_net = p_box[e_name] * dt
        for s in sensible:
            de_net = de_net + w_box[(e_name, s)] * (int_s_box[s] - int_alg_port[e_name])
        for c in clamped:
            de_net = de_net + w_box[(e_name, c)] * (clamped_t[c] * dt - int_alg_port[e_name])
        for oe in ext_ports:
            if oe != e_name:
                de_net = de_net + w_box[(e_name, oe)] * (int_alg_port[oe] - int_alg_port[e_name])

        # 2. Exterior-law cumulative outflow over [0, dt] via tangent/secant flux bounds & monotonic box
        es = ext_specs[e_name]
        a_s, b_s = s_alg_box[e_name].span()
        q_ext_box = _exterior_outflow_box(a_s, b_s, es) * dt
        h_lo_f, c_lo_f = _linearize_exterior_flux(es, a_s, b_s, mode="tangent")
        h_hi_f, c_hi_f = _linearize_exterior_flux(es, a_s, b_s, mode="secant")
        area_box = Box.bounds(*es["area"])
        e_lo_lin = area_box * (int_alg_surf[e_name] * h_lo_f - c_lo_f * dt)
        e_hi_lin = area_box * (int_alg_surf[e_name] * h_hi_f - c_hi_f * dt)
        e_lin_box = Box.bounds(e_lo_lin.span()[0], e_hi_lin.span()[1])
        de_comb = _box_intersect(_box_intersect(de_net, q_ext_box, f"ext {e_name}"), e_lin_box, f"ext_lin {e_name}")
        e_ext_next[e_name] = _clamp_box(e_ext_cur[e_name] + de_comb)

    # Compute subinterval state boxes (T_sub, H_sub, Q_sub) on [0, dt] for exact event checking.
    t_sub: dict[str, Box] = {**{c: Box.exact(clamped_t[c]) for c in clamped}, **t_s_box, **p_alg_box}
    q_sub: dict[str, Box] = {}
    for n in terminals:
        q = p_box[n]
        for other in terminals:
            if other != n:
                q = q + w_box[(n, other)] * (t_sub[other] - t_sub[n])
        q_sub[n] = q

    h_sub: dict[str, Box] = {}
    for n in sensible:
        h_sub[n] = specs[n].enthalpy_from_temp(modes[n], t_s_box[n])
    for c in clamped:
        qlo, qhi = q_sub[c].span()
        alo, ahi = h_cur[c].span()
        blo, bhi = h_next[c].span()
        elo = max(alo + min(Fraction(0), qlo) * dt, blo - max(Fraction(0), qhi) * dt)
        ehi = min(ahi + max(Fraction(0), qhi) * dt, bhi - min(Fraction(0), qlo) * dt)
        if elo > ehi:
            raise ValueError(f"subinterval enthalpy enclosure inconsistent at {c!r}")
        h_sub[c] = Box.bounds(elo, ehi)

    q_end: dict[str, Box] = {}
    for n in terminals:
        q = p_box[n]
        for other in terminals:
            if other != n:
                q = q + w_box[(n, other)] * (t_next[other] - t_next[n])
        q_end[n] = q

    return {
        "t_next": t_next,
        "h_next": h_next,
        "e_ext_next": e_ext_next,
        "s_end_alg": s_end_alg,
        "t_sub": t_sub,
        "h_sub": h_sub,
        "q_sub": q_sub,
        "q_end": q_end,
    }


def _global_radiative_conservation_residual(
    terminals: list[str],
    specs: dict[str, _PortSpec],
    ext_specs: dict[str, dict[str, Any]],
    t_map: dict[str, Box],
    h_map: dict[str, Box],
    e_ext: dict[str, Box],
    t_lo: Fraction,
    t_hi: Fraction,
    total_power_box: Box,
) -> Box:
    """Global energy conservation residual: sum(dU_body + dH_phase + E_maint + E_ext_out) - P_tot*t."""
    tot = ZERO
    for n in terminals:
        if n in ext_specs:
            tot = tot + e_ext[n]
        else:
            sp = specs[n]
            if sp.kind == "sensible_body":
                tot = tot + Box.exact(sp.capacity) * (t_map[n] - sp.t0)
            elif sp.kind == "phase_substance":
                tot = tot + (h_map[n] - sp.h0)
            else:
                tot = tot + h_map[n]
    return tot - Box.bounds(t_lo, t_hi) * total_power_box


def solve_radiative_transient(
    law: Any,
    ports: dict[str, Any],
    duration_s: str,
    *,
    initial_steps: int = DEFAULT_INITIAL_STEPS,
    max_events: int = DEFAULT_MAX_EVENTS,
    max_sweeps: int = 120,
    max_step_refinements: int = DEFAULT_MAX_STEP_REFINEMENTS,
    terminal_injections_w: dict[str, tuple[Fraction, Fraction]] | None = None,
    total_generated_power_w: Fraction | None = None,
) -> dict[str, Any]:
    """Solve coupled nonlinear radiating/convecting transient thermal network with certified enclosures."""
    _validate_positive_int(initial_steps, "initial_steps", upper=MAX_INITIAL_STEPS)
    _validate_positive_int(max_events, "max_events")
    _validate_positive_int(max_sweeps, "max_sweeps")
    _validate_positive_int(max_step_refinements, "max_step_refinements")

    resolved_law, provenance = validate_terminal_law(law)
    engine_law = resolved_law.to_engine_law()
    terminals = list(engine_law["terminals"])
    specs, ext_specs, body_ports, phase_ports, maintained_ports, exterior_ports = _parse_radiative_ports(
        terminals, ports
    )
    duration = decimal_input(duration_s, "duration")
    w_net = _symmetric_conductances(terminals, engine_law)

    if terminal_injections_w is None:
        if total_generated_power_w not in (None, 0):
            raise ValueError("total_generated_power_w requires terminal_injections_w")
        inj_map = {t: (Fraction(0), Fraction(0)) for t in terminals}
        total_gen_box = ZERO
    else:
        if not isinstance(terminal_injections_w, dict) or set(terminal_injections_w) != set(terminals):
            raise ValueError("terminal_injections_w keys must match network terminals")
        inj_map = {}
        for t in terminals:
            lo, hi = terminal_injections_w[t]
            if lo < 0 or lo > hi:
                raise ValueError(f"terminal_injections_w[{t!r}] must be a valid nonnegative interval")
            inj_map[t] = (lo, hi)
        sum_lo = sum((inj_map[t][0] for t in terminals), Fraction(0))
        sum_hi = sum((inj_map[t][1] for t in terminals), Fraction(0))
        if total_generated_power_w is not None:
            if not (sum_lo <= total_generated_power_w <= sum_hi):
                raise ValueError("total_generated_power_w disagrees with terminal_injections_w sum")
            total_gen_box = Box.exact(total_generated_power_w)
        else:
            total_gen_box = Box.bounds(sum_lo, sum_hi)

    p_box: dict[str, Box] = {}
    for n in terminals:
        base_p = (
            Box.exact(specs[n].heat_input)
            if (n in specs and specs[n].kind != "maintained")
            else ZERO
        )
        p_box[n] = base_p + Box.bounds(*inj_map[n])

    port_power = sum((specs[n].heat_input for n in specs if specs[n].kind != "maintained"), Fraction(0))
    total_power_box = Box.exact(port_power) + total_gen_box

    # Initialize temperatures, enthalpies, modes, and initial algebraic exterior state.
    t_cur: dict[str, Box] = {}
    h_cur: dict[str, Box] = {}
    modes: dict[str, str] = {}
    for n, sp in specs.items():
        t_cur[n] = Box.exact(sp.t0)
        if sp.kind == "maintained":
            modes[n] = "maintained"
            h_cur[n] = ZERO
        elif sp.kind == "sensible_body":
            modes[n] = "body"
            h_cur[n] = ZERO
        else:
            h_cur[n] = Box.exact(sp.h0)
            if sp.t0 < sp.t_tr:
                modes[n] = "solid"
            elif sp.t0 > sp.t_tr:
                modes[n] = "liquid"
            else:
                modes[n] = "plateau"

    dyn_nodes = list(specs.keys())
    p_alg_0, s_alg_0 = _solve_algebraic_box(
        terminals, dyn_nodes, ext_specs, t_cur, w_net, inj_map, max_sweeps=max_sweeps
    )
    for e_name in exterior_ports:
        t_cur[e_name] = p_alg_0[e_name]
    s_cur = dict(s_alg_0)
    e_ext_cur: dict[str, Box] = {e_name: ZERO for e_name in exterior_ports}

    w_box = {k: Box.bounds(v[0], v[1]) for k, v in w_net.items()}
    q_init: dict[str, Box] = {}
    for n in terminals:
        q = p_box[n]
        for other in terminals:
            if other != n:
                q = q + w_box[(n, other)] * (t_cur[other] - t_cur[n])
        q_init[n] = q

    source_ref_temps = (
        {t: str(resolved_law.reference_temperatures_k[t]) for t in terminals}
        if resolved_law.reference_temperatures_k is not None
        else None
    )
    source_identity = (
        {k: provenance[k] for k in SOURCE_HASH_KEYS}
        if all(k in provenance for k in SOURCE_HASH_KEYS)
        else {
            "derivedLawSchema": provenance["derivedLawSchema"],
            "derivedLawSha256": provenance["derivedLawSha256"],
            "derivedLawLineage": provenance["derivedLawLineage"],
        }
    )

    events_out: list[dict[str, Any]] = []
    steps_taken = 0
    refinements_used = 0

    def _finish(
        status: str,
        termination_reason: str,
        stop_reason: str | None,
        mod_lo: Fraction,
        mod_hi: Fraction,
        final_t: dict[str, Box],
        final_h: dict[str, Box],
        final_e_ext: dict[str, Box],
        final_s_alg: dict[str, Box],
        final_modes: dict[str, str],
        *,
        unresolved_candidates: list[str] | None = None,
    ) -> dict[str, Any]:
        for n in terminals:
            lo_n, hi_n = final_t[n].span()
            if hi_n < 0:
                raise ValueError(f"negative absolute temperature reached at port {n!r}")
            if lo_n < 0:
                raise ValueError(f"cannot certify nonnegative absolute temperature (T >= 0 K) at port {n!r}")

        residual = _global_radiative_conservation_residual(
            terminals, specs, ext_specs, final_t, final_h, final_e_ext, mod_lo, mod_hi, total_power_box
        )
        if not residual.contains_zero():
            raise ValueError(f"global radiative transient energy conservation check failed: residual={bounds(residual)}")

        active_bcs: dict[str, Any] = {}
        ports_out: dict[str, Any] = {}
        for n in terminals:
            if n in specs:
                sp = specs[n]
                if sp.kind == "sensible_body":
                    tf = final_t[n]
                    du = Box.exact(sp.capacity) * (tf - sp.t0)
                    active_bcs[n] = {
                        "role": "sensible_body",
                        "constraint": "coupled_radiative_lumped_ode",
                        "initialTemperatureK": str(sp.t0),
                        "finalTemperatureBoundsK": bounds(tf),
                        "heatInputW": str(sp.heat_input),
                    }
                    ports_out[n] = {
                        "kind": "sensible_body",
                        "heatCapacityJPerK": str(sp.capacity),
                        "initialTemperatureK": str(sp.t0),
                        "heatInputW": str(sp.heat_input),
                        "finalTemperatureBoundsK": bounds(tf),
                        "bodyEnergyChangeBoundsJ": bounds(du),
                        "energySignConvention": "into_body_positive",
                    }
                elif sp.kind == "maintained":
                    active_bcs[n] = {
                        "role": "maintained",
                        "constraint": "fixed_dirichlet",
                        "temperatureK": str(sp.t0),
                    }
                    ports_out[n] = {
                        "kind": "maintained",
                        "temperatureK": str(sp.t0),
                        "initialInflowFromNetworkBoundsW": bounds(q_init[n]),
                        "integratedEnergyIntoReservoirBoundsJ": bounds(final_h[n]),
                        "energySignConvention": "into_maintained_reservoir_positive",
                    }
                else:  # phase_substance
                    md = final_modes[n]
                    tf = final_t[n]
                    hf = final_h[n]
                    ms_box, ml_box = _phase_masses_from_state(sp, md, hf)
                    dh = hf - sp.h0
                    active_bcs[n] = {
                        "role": "phase_substance",
                        "constraint": "piecewise_linear_enthalpy_mode",
                        "initialTemperatureK": str(sp.t0),
                        "transitionTemperatureK": str(sp.t_tr),
                        "finalMode": md,
                        "finalTemperatureBoundsK": bounds(tf),
                        "heatInputW": str(sp.heat_input),
                    }
                    ports_out[n] = {
                        "kind": "phase_substance",
                        "transitionTemperatureK": str(sp.t_tr),
                        "specificLatentHeatJPerKg": str(sp.latent),
                        "solidSpecificHeatJPerKgK": str(sp.c_s),
                        "liquidSpecificHeatJPerKgK": str(sp.c_l),
                        "initialTemperatureK": str(sp.t0),
                        "initialSolidKg": str(sp.solid0),
                        "initialLiquidKg": str(sp.liquid0),
                        "totalMassKg": str(sp.total_mass),
                        "heatInputW": str(sp.heat_input),
                        "finalMode": md,
                        "finalTemperatureBoundsK": bounds(tf),
                        "enthalpyChangeBoundsJ": bounds(dh),
                        "remainingSolidBoundsKg": bounds(ms_box),
                        "remainingLiquidBoundsKg": bounds(ml_box),
                        "energySignConvention": "into_substance_positive",
                    }
            else:
                es = ext_specs[n]
                tp = final_t[n]
                ts = final_s_alg[n]
                q_final_ext = _exterior_outflow_box(ts.span()[0], ts.span()[1], es)
                if es["orig_kind"] == "exterior_surface":
                    active_bcs[n] = {
                        "role": "exterior_surface",
                        "constraint": "algebraic_radiative_convective_boundary",
                        "finalTemperatureBoundsK": bounds(tp),
                    }
                    ports_out[n] = {
                        "kind": "exterior_surface",
                        "finalTemperatureBoundsK": bounds(tp),
                        "finalOutwardHeatRateBoundsW": bounds(q_final_ext),
                        "cumulativeOutwardEnergyBoundsJ": bounds(final_e_ext[n]),
                        "energySignConvention": "outward_from_surface_positive",
                    }
                else:  # radial_shell
                    active_bcs[n] = {
                        "role": "radial_shell",
                        "constraint": "algebraic_radial_shell_radiative_boundary",
                        "innerFaceTemperatureBoundsK": bounds(tp),
                        "outerFaceTemperatureBoundsK": bounds(ts),
                    }
                    ports_out[n] = {
                        "kind": "radial_shell",
                        "innerFaceTemperatureBoundsK": bounds(tp),
                        "outerFaceTemperatureBoundsK": bounds(ts),
                        "finalOutwardHeatRateBoundsW": bounds(q_final_ext),
                        "cumulativeOutwardEnergyBoundsJ": bounds(final_e_ext[n]),
                        "energySignConvention": "outward_from_radial_surface_positive",
                    }

        max_t_width = max((final_t[n].span()[1] - final_t[n].span()[0]) for n in terminals)
        return {
            "schema": RADIATIVE_TRANSIENT_SCHEMA,
            "evidence": {
                "category": EVIDENCE_CATEGORY,
                "sourceIdentity": source_identity,
                **{k: False for k in OFFLINE_FLAG_KEYS},
            },
            "network": {
                "terminals": terminals,
                "portKinds": {
                    t: (specs[t].kind if t in specs else ext_specs[t]["orig_kind"]) for t in terminals
                },
                "sourceLawReferenceTemperaturesK": source_ref_temps,
                "activeBoundaryConditions": active_bcs,
            },
            "status": status,
            "requestedDurationS": str(duration),
            "modeledDurationBoundsS": [str(mod_lo), str(mod_hi)],
            "postExhaustionModeled": True,
            "events": events_out,
            "ports": ports_out,
            "energyConservationResidualBoundsJ": bounds(residual),
            "solverMetadata": {
                "method": "certified_cooperative_tangent_secant_metzler_ode",
                "terminationReason": termination_reason,
                "stopReason": stop_reason,
                "stepsTaken": steps_taken,
                "refinementsUsed": refinements_used,
                "eventsCommitted": len(events_out),
                "modeledDurationWidthS": str(mod_hi - mod_lo),
                "maxFinalTemperatureWidthK": str(max_t_width),
                "unresolvedCandidatePorts": unresolved_candidates or [],
            },
            **provenance,
        }

    if duration == 0:
        return _finish("complete", "resolved", None, ZERO.span()[0], ZERO.span()[0], t_cur, h_cur, e_ext_cur, s_cur, modes)

    # Resolve pure-phase boundary starts at t = 0.
    unresolved_start: list[str] = []
    for n in phase_ports:
        sp = specs[n]
        if sp.t0 != sp.t_tr or (sp.solid0 > 0 and sp.liquid0 > 0):
            continue
        q0_lo, q0_hi = q_init[n].span()
        if sp.liquid0 == 0:
            if q0_lo > 0:
                modes[n] = "plateau"
            elif q0_hi < 0:
                modes[n] = "solid"
            else:
                unresolved_start.append(n)
        else:
            if q0_lo > 0:
                modes[n] = "liquid"
            elif q0_hi < 0:
                modes[n] = "plateau"
            else:
                unresolved_start.append(n)
    if unresolved_start:
        return _finish(
            "mode_sequence_uncertain",
            "mode_sequence_uncertain",
            "unresolved_initial_boundary_departure",
            Fraction(0),
            Fraction(0),
            t_cur,
            h_cur,
            e_ext_cur,
            s_cur,
            modes,
            unresolved_candidates=unresolved_start,
        )

    # Time-stepping with adaptive Picard step halving and certified phase-event bracketing.
    t_lo = Fraction(0)
    t_hi = Fraction(0)
    # Use at least 32 base steps when radiation (eps > 0) is active for tight O(h^2) enclosures.
    has_radiation = any(es["eps"] > 0 for es in ext_specs.values())
    n_base = max(initial_steps, 32) if has_radiation else initial_steps
    base_dt = duration / n_base
    min_dt = max(Fraction(1, 10**9), duration / (10**8))

    def _check_step_events(
        step_res: dict[str, Any], at_stage_start: bool
    ) -> tuple[bool, dict[str, str | None], dict[str, set[str]], set[str]]:
        all_safe = True
        cert_map: dict[str, str | None] = {}
        hit_map: dict[str, set[str]] = {}
        end_hit_ports: set[str] = set()
        for n in phase_ports:
            safe_sub, _, hits_sub = _node_event_check(
                specs[n], modes[n], step_res["t_sub"][n], step_res["h_sub"][n], step_res["q_sub"][n],
                t_init_box=t_cur[n], h_init_box=h_cur[n], at_start=at_stage_start,
            )
            _, cert_end, hits_end = _node_event_check(
                specs[n], modes[n], step_res["t_next"][n], step_res["h_next"][n], step_res["q_end"][n],
                t_init_box=t_cur[n], h_init_box=h_cur[n], at_start=False,
            )
            if not safe_sub:
                all_safe = False
            cert_map[n] = cert_end
            if hits_end:
                end_hit_ports.add(n)
            h_all = hits_sub | hits_end
            if h_all:
                hit_map[n] = h_all
        return all_safe, cert_map, hit_map, end_hit_ports

    at_stage_start = True
    while t_lo < duration:
        rem_hi = duration - t_lo
        rem_lo = max(Fraction(0), duration - t_hi)
        dt = min(base_dt, rem_hi)

        # If t_lo < t_hi and remaining horizon straddles t_hi, evaluate final window hull cleanly.
        step_res = _step_radiative_mode(
            terminals, specs, ext_specs, modes, w_net, inj_map, p_box,
            t_cur, h_cur, e_ext_cur, dt, max_sweeps=max_sweeps,
        )
        while step_res is None:
            refinements_used += 1
            if refinements_used > max_step_refinements or dt <= min_dt:
                raise ValueError("radiative transient Picard step certification failed (step hit minimum tolerance or negative T)")
            dt = dt / 2
            step_res = _step_radiative_mode(
                terminals, specs, ext_specs, modes, w_net, inj_map, p_box,
                t_cur, h_cur, e_ext_cur, dt, max_sweeps=max_sweeps,
            )

        if not phase_ports:
            if t_lo + dt >= duration and t_lo < t_hi:
                # Propagate across remaining duration uncertainty [rem_lo, rem_hi] if any.
                t_cur = step_res["t_next"]
                h_cur = step_res["h_next"]
                e_ext_cur = step_res["e_ext_next"]
                s_cur = step_res["s_end_alg"]
                t_lo = duration
                t_hi = duration
            else:
                t_cur = step_res["t_next"]
                h_cur = step_res["h_next"]
                e_ext_cur = step_res["e_ext_next"]
                s_cur = step_res["s_end_alg"]
                t_lo = t_lo + dt
                t_hi = min(duration, t_hi + dt)
            steps_taken += 1
            at_stage_start = False
            continue

        safe, cert_map, hit_map, _ = _check_step_events(step_res, at_stage_start)
        if safe:
            if t_lo + dt >= duration and t_lo < t_hi:
                # Certified window hull over [rem_lo, rem_hi] (sound even for non-monotone trajectories).
                if rem_lo > 0 and rem_lo < rem_hi:
                    s1 = _step_radiative_mode(
                        terminals, specs, ext_specs, modes, w_net, inj_map, p_box,
                        t_cur, h_cur, e_ext_cur, rem_lo, max_sweeps=max_sweeps,
                    )
                    s2 = (
                        None
                        if s1 is None
                        else _step_radiative_mode(
                            terminals, specs, ext_specs, modes, w_net, inj_map, p_box,
                            s1["t_next"], s1["h_next"], s1["e_ext_next"], rem_hi - rem_lo, max_sweeps=max_sweeps,
                        )
                    )
                    if s1 is not None and s2 is not None:
                        t_cur = s2["t_sub"]
                        h_cur = s2["h_sub"]
                        e_ext_cur = {n: _box_union([s1["e_ext_next"][n], s2["e_ext_next"][n]]) for n in exterior_ports}
                        _, s_cur = _solve_algebraic_box(
                            terminals, dyn_nodes, ext_specs, {n: t_cur[n] for n in dyn_nodes}, w_net, inj_map, max_sweeps=max_sweeps
                        )
                    else:
                        t_cur = {n: _box_union([t_cur[n], step_res["t_sub"][n]]) for n in terminals}
                        h_cur = {n: _box_union([h_cur[n], step_res["h_sub"][n]]) for n in specs}
                        e_ext_cur = {n: _box_union([e_ext_cur[n], step_res["e_ext_next"][n]]) for n in exterior_ports}
                        _, s_cur = _solve_algebraic_box(
                            terminals, dyn_nodes, ext_specs, {n: t_cur[n] for n in dyn_nodes}, w_net, inj_map, max_sweeps=max_sweeps
                        )
                else:
                    t_cur = {n: _box_union([t_cur[n], step_res["t_sub"][n]]) for n in terminals}
                    h_cur = {n: _box_union([h_cur[n], step_res["h_sub"][n]]) for n in specs}
                    e_ext_cur = {n: _box_union([e_ext_cur[n], step_res["e_ext_next"][n]]) for n in exterior_ports}
                    _, s_cur = _solve_algebraic_box(
                        terminals, dyn_nodes, ext_specs, {n: t_cur[n] for n in dyn_nodes}, w_net, inj_map, max_sweeps=max_sweeps
                    )
                t_lo = duration
                t_hi = duration
            else:
                t_cur = step_res["t_next"]
                h_cur = step_res["h_next"]
                e_ext_cur = step_res["e_ext_next"]
                s_cur = step_res["s_end_alg"]
                t_lo = t_lo + dt
                t_hi = min(duration, t_hi + dt)
            steps_taken += 1
            at_stage_start = False
            continue

        # Phase event touched/crossed inside [0, dt]: first ensure step_res certifies a crossing if possible,
        # then binary-search [0, dt] to advance safe prefix and tighten the certified crossing bracket.
        if not any(cert_map.values()) and dt < rem_hi and refinements_used < max_step_refinements:
            dt_ext = min(rem_hi, dt * 2)
            ext_step = _step_radiative_mode(
                terminals, specs, ext_specs, modes, w_net, inj_map, p_box,
                t_cur, h_cur, e_ext_cur, dt_ext, max_sweeps=max_sweeps,
            )
            if ext_step is not None:
                _, c_ext, h_ext, _ = _check_step_events(ext_step, at_stage_start)
                if any(c_ext.values()):
                    step_res, cert_map, hit_map, dt = ext_step, c_ext, h_ext, dt_ext

        ev_tol = max(Fraction(1, 10**5), duration / (10**5))
        if dt > ev_tol and refinements_used < max_step_refinements:
            cur_dt = dt / 2
            advanced = False
            while cur_dt > ev_tol and refinements_used < max_step_refinements:
                refinements_used += 1
                try_step = _step_radiative_mode(
                    terminals, specs, ext_specs, modes, w_net, inj_map, p_box,
                    t_cur, h_cur, e_ext_cur, cur_dt, max_sweeps=max_sweeps,
                )
                if try_step is None:
                    cur_dt = cur_dt / 2
                    continue
                s_try, c_try, h_try, end_hits_try = _check_step_events(try_step, at_stage_start)
                if s_try:
                    t_cur = try_step["t_next"]
                    h_cur = try_step["h_next"]
                    e_ext_cur = try_step["e_ext_next"]
                    s_cur = try_step["s_end_alg"]
                    t_lo = t_lo + cur_dt
                    t_hi = min(duration, t_hi + cur_dt)
                    steps_taken += 1
                    at_stage_start = False
                    # Re-bracket the remaining crossing window dt - cur_dt from the advanced state!
                    rem_after = min(duration - t_lo, dt - cur_dt)
                    if rem_after <= 0:
                        advanced = True
                        break
                    dt = rem_after
                    rem_step = _step_radiative_mode(
                        terminals, specs, ext_specs, modes, w_net, inj_map, p_box,
                        t_cur, h_cur, e_ext_cur, dt, max_sweeps=max_sweeps,
                    )
                    if rem_step is None:
                        advanced = True
                        break
                    s_rem, c_rem, h_rem, _ = _check_step_events(rem_step, at_stage_start)
                    if s_rem:
                        t_cur = rem_step["t_next"]
                        h_cur = rem_step["h_next"]
                        e_ext_cur = rem_step["e_ext_next"]
                        s_cur = rem_step["s_end_alg"]
                        t_lo = t_lo + dt
                        t_hi = min(duration, t_hi + dt)
                        steps_taken += 1
                        advanced = True
                        break
                    step_res, cert_map, hit_map = rem_step, c_rem, h_rem
                    cur_dt = dt / 2
                elif any(c_try.values()):
                    step_res, cert_map, hit_map = try_step, c_try, h_try
                    dt = cur_dt
                    cur_dt = cur_dt / 2
                elif not end_hits_try:
                    # Endpoint is still strictly before the threshold; only Picard subinterval touched it.
                    # Halve cur_dt to step safely forward!
                    cur_dt = cur_dt / 2
                else:
                    # Endpoint itself straddles the threshold (minimum certifiable width reached).
                    break
            if advanced:
                continue

        # Check if an event is strictly certified before rem_lo and has a unique crossing port & target!
        cert_nodes = [n for n, tgt in cert_map.items() if tgt is not None]
        hit_nodes = list(hit_map.keys())
        budget_hit = refinements_used >= max_step_refinements or len(events_out) >= max_events

        if (
            not cert_nodes
            or dt > max(Fraction(0), duration - t_hi)
            or len(hit_nodes) != 1
            or len(hit_map[hit_nodes[0]]) != 1
            or len(events_out) >= max_events
        ):
            # Honest stop: enclose union of pre-step and subinterval state!
            t_stop = {n: _box_union([t_cur[n], step_res["t_sub"][n]]) for n in terminals}
            h_stop = {n: _box_union([h_cur[n], step_res["h_sub"][n]]) for n in specs}
            e_stop = {n: _box_union([e_ext_cur[n], step_res["e_ext_next"][n]]) for n in exterior_ports}
            s_stop = {n: _box_union([s_cur[n], step_res["s_end_alg"][n]]) for n in exterior_ports}
            term = "refinement_budget" if budget_hit else "mode_sequence_uncertain"
            reason = (
                "max_events_budget_reached"
                if len(events_out) >= max_events
                else ("refinement_budget" if budget_hit else "event_order_or_horizon_unresolved")
            )
            return _finish(
                "mode_sequence_uncertain",
                term,
                reason,
                t_lo,
                min(duration, t_hi + dt),
                t_stop,
                h_stop,
                e_stop,
                s_stop,
                modes,
                unresolved_candidates=hit_nodes,
            )

        # Commit certified unique phase transition!
        ev_node = hit_nodes[0]
        ev_target = next(iter(hit_map[ev_node]))
        old_mode = modes[ev_node]
        sp_ev = specs[ev_node]

        t_ev = {n: _box_union([t_cur[n], step_res["t_sub"][n]]) for n in terminals}
        h_ev = {n: _box_union([h_cur[n], step_res["h_sub"][n]]) for n in specs}
        e_ev = {n: _box_union([e_ext_cur[n], step_res["e_ext_next"][n]]) for n in exterior_ports}
        s_ev = {n: _box_union([s_cur[n], step_res["s_end_alg"][n]]) for n in exterior_ports}

        t_ev[ev_node] = Box.exact(sp_ev.t_tr)
        if ev_target == "plateau":
            h_ev[ev_node] = ZERO if old_mode == "solid" else Box.exact(sp_ev.e_latent)
        elif ev_target == "solid":
            h_ev[ev_node] = ZERO
        else:
            h_ev[ev_node] = Box.exact(sp_ev.e_latent)

        modes[ev_node] = ev_target
        new_t_lo = t_lo
        new_t_hi = min(duration, t_hi + dt)

        # Refresh algebraic exterior bounds at snapped transition state.
        p_ev_alg, s_ev_alg = _solve_algebraic_box(
            terminals, dyn_nodes, ext_specs, {n: t_ev[n] for n in dyn_nodes}, w_net, inj_map, max_sweeps=max_sweeps
        )
        for e_name in exterior_ports:
            t_ev[e_name] = p_ev_alg[e_name]
            s_ev[e_name] = s_ev_alg[e_name]

        ev_res = _global_radiative_conservation_residual(
            terminals, specs, ext_specs, t_ev, h_ev, e_ev, new_t_lo, new_t_hi, total_power_box
        )
        if not ev_res.contains_zero():
            raise ValueError(f"radiative event conservation check failed: residual={bounds(ev_res)}")

        events_out.append({
            "index": len(events_out),
            "ports": [ev_node],
            "transitions": {ev_node: {"from": old_mode, "to": ev_target}},
            "timeBoundsS": [str(new_t_lo), str(new_t_hi)],
            "localBracketWidthS": str(dt),
            "temperaturesBoundsK": {n: bounds(t_ev[n]) for n in terminals},
            "enthalpiesBoundsJ": {n: bounds(h_ev[n]) for n in phase_ports},
            "energyConservationResidualBoundsJ": bounds(ev_res),
        })

        t_lo = new_t_lo
        t_hi = new_t_hi
        t_cur = t_ev
        h_cur = h_ev
        e_ext_cur = e_ev
        s_cur = s_ev
        at_stage_start = True

        # Verify strict departure from snapped boundary before continuing.
        q_dep: dict[str, Box] = {}
        for n in phase_ports:
            q = p_box[n]
            for other in terminals:
                if other != n:
                    q = q + w_box[(n, other)] * (t_cur[other] - t_cur[n])
            q_dep[n] = q
        qlo, qhi = q_dep[ev_node].span()
        bad_dep = (
            (ev_target == "plateau" and h_cur[ev_node].span()[0] == 0 and qlo <= 0)
            or (ev_target == "plateau" and h_cur[ev_node].span()[1] == sp_ev.e_latent and qhi >= 0)
            or (ev_target == "solid" and qhi >= 0)
            or (ev_target == "liquid" and qlo <= 0)
        )
        if bad_dep:
            return _finish(
                "mode_sequence_uncertain",
                "mode_sequence_uncertain",
                "unresolved_boundary_departure",
                t_lo,
                t_hi,
                t_cur,
                h_cur,
                e_ext_cur,
                s_cur,
                modes,
                unresolved_candidates=[ev_node],
            )

    return _finish("complete", "resolved", None, t_lo, t_hi, t_cur, h_cur, e_ext_cur, s_cur, modes)
