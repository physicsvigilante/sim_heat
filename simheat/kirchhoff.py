"""Certified steady thermal network engine with temperature-dependent conductivity via Kirchhoff potential (M08).

Models steady heat conduction through connected storage-free networks where any rod or radial-shell
layer may have affine temperature-dependent conductivity:

    k_r(T) = k_{0,r} * (1 + alpha_r * (T - T_{ref,r}))

with exact Kirchhoff potential:

    psi_r(T) = (T - T_{ref,r}) + (alpha_r / 2) * (T - T_{ref,r})^2
    Phi_r(T) = k_{0,r} * psi_r(T)

Along each rod r = (a, b) with base conductance g_r = k_{0,r} * g_{geom,r} and optional uniform
heat generation P_r >= 0:

    Q_{a -> r} = g_r * (psi_r(T_a) - psi_r(T_b)) - P_r / 2
    Q_{b -> r} = g_r * (psi_r(T_b) - psi_r(T_a)) - P_r / 2
    Q_{a -> r} + Q_{b -> r} = -P_r

On the strictly positive-conductivity domain D = {T >= 0 : 1 + alpha_r*(T - T_{ref,r}) > 0},
the coupled balance vector F(T; p) = 0 (combining heterogeneous rods, arbitrary internal junctions,
maintained reservoirs, coexisting phase baths, radiating/convecting exterior surfaces, and
multi-layer spherical/cylindrical radial shells) is an exact strictly diagonal-monotone,
off-diagonally antitone M-function. Every returned enclosure is independently certified against
exact rational pointwise extremal residuals F_max(u_lo) <= 0 and F_min(u_hi) >= 0, strict k(T) > 0
across all nodes and heated-rod interior peaks, and global steady energy conservation.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
from itertools import product
import json
import math
from typing import Any

from simheat.core import Box, ZERO, pi_rational_enclosure
from simheat.enthalpy import signed_decimal_input
from simheat.laws import _parse_positive_param, validate_terminal_law
from tools.join_thermal_networks import bounds
from tools.latent_heat_bath import phase_inputs
from tools.multiport_thermal_network import (
    _bisect_monotone_bound,
    _ceil_fraction,
    _exterior_flux_per_area,
    _exterior_outflow_box,
    _floor_fraction,
    _intersect_boxes,
    _parse_exterior,
    _solve_exact_linear_fractions,
    _symmetric_conductances,
)
from tools.offline_investigation import _expect_exact_keys
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS
from tools.radiating_surface import decimal_input
from tools.spherical_conduction import radial_log

KIRCHHOFF_STEADY_SCHEMA = "sim_heat.offline_kirchhoff_steady/1"
EVIDENCE_CATEGORY = "offline_analytical_calculation"
VALID_KIRCHHOFF_PORT_KINDS = ("maintained", "phase_bath", "radiating_surface", "radial_shell")
_SQRT_SCALE = 10**28
_NEWTON_CLAMP_SCALE = 10**28


@dataclass(frozen=True)
class KirchhoffEdge:
    """One passive (optionally heated) steady Kirchhoff conduction edge."""

    name: str
    a: str
    b: str
    g_lo: Fraction
    g_hi: Fraction
    alpha: Fraction
    t_ref: Fraction
    power_w: Fraction = Fraction(0)
    k0_lo: Fraction = Fraction(1)
    k0_hi: Fraction = Fraction(1)
    is_rod: bool = True


@dataclass(frozen=True)
class KirchhoffRodModel:
    """Immutable validated steady Kirchhoff rod graph model."""

    nodes: tuple[str, ...]
    terminals: tuple[str, ...]
    junctions: tuple[str, ...]
    edges: tuple[KirchhoffEdge, ...]
    total_generated_power_w: Fraction
    has_nonlinear_k: bool
    is_exact_point: bool
    content_sha256: str


def _clamp_fraction(x: Fraction, scale: int = _NEWTON_CLAMP_SCALE) -> Fraction:
    """Round an approximate Newton iterate to a bounded denominator (untrusted candidate only)."""
    if x.denominator <= scale:
        return x
    return Fraction(round(x * scale), scale)


def _psi(temp: Fraction, alpha: Fraction, t_ref: Fraction) -> Fraction:
    """Dimensionless Kirchhoff potential psi(T) = (T - T_ref) + (alpha/2)*(T - T_ref)^2."""
    u = temp - t_ref
    if alpha == 0:
        return u
    return u + (alpha * u * u) / 2


def _dpsi(temp: Fraction, alpha: Fraction, t_ref: Fraction) -> Fraction:
    """Dimensionless conductivity ratio k(T)/k_0 = d(psi)/dT = 1 + alpha*(T - T_ref)."""
    return Fraction(1) + alpha * (temp - t_ref)


def _isqrt_enclosure(q: Fraction, scale: int = _SQRT_SCALE) -> tuple[Fraction, Fraction]:
    """Return exact rational enclosure [lo, hi] for sqrt(q) with q > 0, verified by lo^2 <= q <= hi^2."""
    if q < 0:
        raise ValueError("square root requires nonnegative rational argument")
    if q == 0:
        return Fraction(0), Fraction(0)
    p, r = q.numerator, q.denominator
    scaled_int = p * r * scale * scale
    m = math.isqrt(scaled_int)
    denom = r * scale
    if m * m == scaled_int:
        exact = Fraction(m, denom)
        return exact, exact
    lo = Fraction(m, denom)
    hi = Fraction(m + 1, denom)
    if lo * lo > q or hi * hi < q:
        raise RuntimeError("integer square-root rational enclosure verification failed")
    return lo, hi


def _invert_psi_box(
    psi_lo: Fraction,
    psi_hi: Fraction,
    alpha: Fraction,
    t_ref: Fraction,
    *,
    label: str = "Kirchhoff rod",
) -> tuple[Fraction, Fraction]:
    """Invert strictly increasing psi(T) over [psi_lo, psi_hi] on the positive-conductivity branch."""
    if psi_lo > psi_hi:
        raise ValueError(f"{label}: inverted Kirchhoff potential bounds")
    if alpha == 0:
        t_lo = t_ref + psi_lo
        t_hi = t_ref + psi_hi
        if t_lo < 0:
            raise ValueError(f"{label}: inverted temperature fell below 0 K")
        return t_lo, t_hi

    def _inv_point(p_val: Fraction) -> tuple[Fraction, Fraction]:
        disc = Fraction(1) + 2 * alpha * p_val
        if disc <= 0:
            raise ValueError(
                f"{label}: thermal conductivity k(T) became nonpositive "
                f"(1 + 2*alpha*psi = {float(disc):.6g} <= 0)"
            )
        s_lo, s_hi = _isqrt_enclosure(disc)
        if alpha > 0:
            return t_ref + (s_lo - 1) / alpha, t_ref + (s_hi - 1) / alpha
        return t_ref + (s_hi - 1) / alpha, t_ref + (s_lo - 1) / alpha

    lo_a, _ = _inv_point(psi_lo)
    _, hi_b = _inv_point(psi_hi)
    if lo_a > hi_b:
        raise ValueError(f"{label}: Kirchhoff temperature inversion collapsed inconsistently")
    if lo_a < 0:
        raise ValueError(f"{label}: inverted temperature fell below 0 K")
    if _dpsi(lo_a, alpha, t_ref) <= 0 or _dpsi(hi_b, alpha, t_ref) <= 0:
        raise ValueError(f"{label}: inverted temperature violates positive thermal conductivity k(T) > 0")
    return lo_a, hi_b


def _parabolic_peak(a: Fraction, b: Fraction, curvature: Fraction) -> Fraction:
    """Exact maximum of (1-x)*a + x*b + curvature*x*(1-x) on x in [0, 1] for curvature >= 0."""
    if curvature == 0:
        return max(a, b)
    x = max(Fraction(0), min(Fraction(1), (Fraction(1) + (b - a) / curvature) / 2))
    return (1 - x) * a + x * b + curvature * x * (1 - x)


def _edge_flow_out_of_a_box(
    ta_lo: Fraction,
    ta_hi: Fraction,
    tb_lo: Fraction,
    tb_hi: Fraction,
    edge: KirchhoffEdge,
) -> Box:
    """Exact monotone enclosure of Q_{a -> edge} = g*(psi(T_a) - psi(T_b)) - P/2 on D_edge."""
    dpsi_lo = _psi(ta_lo, edge.alpha, edge.t_ref) - _psi(tb_hi, edge.alpha, edge.t_ref)
    dpsi_hi = _psi(ta_hi, edge.alpha, edge.t_ref) - _psi(tb_lo, edge.alpha, edge.t_ref)
    q_lo = (edge.g_lo if dpsi_lo >= 0 else edge.g_hi) * dpsi_lo - edge.power_w / 2
    q_hi = (edge.g_hi if dpsi_hi >= 0 else edge.g_lo) * dpsi_hi - edge.power_w / 2
    if q_lo > q_hi:
        raise ValueError(f"Kirchhoff flow enclosure inverted on edge {edge.name!r}")
    return Box.bounds(q_lo, q_hi)


def build_kirchhoff_model(
    nodes: list[str],
    terminals: list[str],
    rods: dict[str, dict[str, Any]],
) -> KirchhoffRodModel:
    """Validate a connected rod graph with optional affine k(T) and optional uniform heat generation."""
    if not isinstance(nodes, (list, tuple)) or len(nodes) < 2 or any(not isinstance(n, str) or not n for n in nodes):
        raise ValueError("nodes must be a list of at least 2 non-empty node name strings")
    if len(set(nodes)) != len(nodes):
        raise ValueError("nodes must contain unique names")
    node_set = set(nodes)
    if not isinstance(terminals, (list, tuple)) or len(terminals) < 2:
        raise ValueError("terminals must be a list of at least 2 node names")
    if len(set(terminals)) != len(terminals) or not set(terminals).issubset(node_set):
        raise ValueError("terminals must be unique members of nodes")
    if not isinstance(rods, dict) or not rods:
        raise ValueError("rods must be a non-empty mapping")

    term_list = list(terminals)
    term_set = set(term_list)
    junctions = tuple(n for n in nodes if n not in term_set)

    pi_box = None
    edges: list[KirchhoffEdge] = []
    total_gen = Fraction(0)
    has_nonlinear = False
    conn_adj: dict[str, set[str]] = {n: set() for n in nodes}
    canonical_edges: list[dict[str, Any]] = []

    for name, spec in sorted(rods.items()):
        if not isinstance(spec, dict):
            raise ValueError(f"rods[{name}] must be a mapping")
        kind = spec.get("kind")
        if kind in ("rod_area", "RodArea"):
            _expect_exact_keys(
                spec,
                required=("kind", "a", "b", "k", "L", "A"),
                optional=("generatedPowerW", "alphaPerK", "referenceTemperatureK"),
                label=f"rods[{name}]",
            )
        elif kind in ("rod_circular", "RodCircular"):
            _expect_exact_keys(
                spec,
                required=("kind", "a", "b", "k", "L", "d"),
                optional=("generatedPowerW", "alphaPerK", "referenceTemperatureK"),
                label=f"rods[{name}]",
            )
        else:
            raise ValueError(
                f"rods[{name}].kind must be one of ('rod_area', 'RodArea', 'rod_circular', 'RodCircular'), got {kind!r}"
            )
        a, b = spec["a"], spec["b"]
        if a not in node_set or b not in node_set or a == b:
            raise ValueError(f"rods[{name}] endpoints ({a!r}, {b!r}) must be distinct declared nodes")
        conn_adj[a].add(b)
        conn_adj[b].add(a)

        k_lo, k_hi = _parse_positive_param(spec["k"], f"rods[{name}].k")
        l_lo, l_hi = _parse_positive_param(spec["L"], f"rods[{name}].L")
        if kind in ("rod_area", "RodArea"):
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

        p_raw = spec.get("generatedPowerW")
        power = decimal_input(p_raw, f"rods[{name}].generatedPowerW") if p_raw is not None else Fraction(0)

        alpha_raw = spec.get("alphaPerK")
        alpha = signed_decimal_input(alpha_raw, f"rods[{name}].alphaPerK") if alpha_raw is not None else Fraction(0)
        if alpha != 0:
            if "referenceTemperatureK" not in spec:
                raise ValueError(
                    f"rods[{name}].referenceTemperatureK is required whenever alphaPerK is nonzero"
                )
            t_ref = decimal_input(spec["referenceTemperatureK"], f"rods[{name}].referenceTemperatureK")
            has_nonlinear = True
        else:
            t_ref = (
                decimal_input(spec["referenceTemperatureK"], f"rods[{name}].referenceTemperatureK")
                if "referenceTemperatureK" in spec
                else Fraction(0)
            )

        edges.append(
            KirchhoffEdge(
                name=name,
                a=a,
                b=b,
                g_lo=g_lo,
                g_hi=g_hi,
                alpha=alpha,
                t_ref=t_ref,
                power_w=power,
                k0_lo=k_lo,
                k0_hi=k_hi,
                is_rod=True,
            )
        )
        total_gen += power
        canonical_edges.append({
            "name": name,
            "a": a,
            "b": b,
            "g": [str(g_lo), str(g_hi)],
            "alpha": str(alpha),
            "t_ref": str(t_ref),
            "power_w": str(power),
        })

    visited = {nodes[0]}
    stack = [nodes[0]]
    while stack:
        cur = stack.pop()
        for nxt in conn_adj[cur]:
            if nxt not in visited:
                visited.add(nxt)
                stack.append(nxt)
    if visited != node_set:
        raise ValueError(f"rod graph is disconnected; unreachable nodes: {sorted(node_set - visited)}")

    digest = hashlib.sha256(
        json.dumps(
            {"nodes": list(nodes), "terminals": term_list, "edges": canonical_edges},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return KirchhoffRodModel(
        nodes=tuple(nodes),
        terminals=tuple(term_list),
        junctions=junctions,
        edges=tuple(edges),
        total_generated_power_w=total_gen,
        has_nonlinear_k=has_nonlinear,
        is_exact_point=all(e.g_lo == e.g_hi for e in edges),
        content_sha256=digest,
    )


def _parse_kirchhoff_ports(
    terminals: list[str],
    ports: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], bool]:
    """Parse steady port specs (identical to multiport, plus optional alphaPerK/referenceTemperatureK on radial_shell layers)."""
    if not isinstance(ports, dict) or set(ports) != set(terminals):
        raise ValueError("ports mapping must assign an attachment to every terminal in the network")
    parsed: dict[str, dict[str, Any]] = {}
    has_phase = False
    anchored = False
    pi_box = None

    for name in terminals:
        spec = ports[name]
        if not isinstance(spec, dict):
            raise ValueError(f"port {name!r} specification must be a mapping")
        kind = spec.get("kind")
        if kind not in VALID_KIRCHHOFF_PORT_KINDS:
            raise ValueError(f"port {name!r} has unsupported kind {kind!r}; expected one of {VALID_KIRCHHOFF_PORT_KINDS}")

        if kind == "maintained":
            _expect_exact_keys(spec, required=("kind", "temperatureK"), label=f"ports[{name}]")
            temp = decimal_input(spec["temperatureK"], f"maintained temperature at {name}")
            parsed[name] = {"kind": "maintained", "temp": temp}
            anchored = True

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
            }
            has_phase = True
            anchored = True

        elif kind == "radiating_surface":
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
            if ext["eps"] > 0 or ext["h"] > 0:
                anchored = True
            parsed[name] = {"kind": "radiating_surface", "area": (area, area), **ext}

        else:  # radial_shell
            _expect_exact_keys(spec, required=("kind", "geometry", "exterior"), label=f"ports[{name}]")
            geom = spec["geometry"]
            ext_raw = spec["exterior"]
            if not isinstance(geom, dict) or not isinstance(ext_raw, dict):
                raise ValueError(f"radial_shell at {name!r} requires geometry and exterior mappings")
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
            g_kind = geom["kind"]
            if g_kind not in ("sphere", "cylinder"):
                raise ValueError(f"radial_shell geometry.kind at {name!r} must be 'sphere' or 'cylinder'")
            cyl_raw = geom.get("cylinderLengthM")
            if g_kind == "sphere" and cyl_raw is not None:
                raise ValueError(f"sphere radial_shell at {name!r} does not accept cylinderLengthM")
            if g_kind == "cylinder" and cyl_raw is None:
                raise ValueError(f"cylinder radial_shell at {name!r} requires cylinderLengthM")
            cyl_len = decimal_input(cyl_raw, f"cylinder length at {name}") if cyl_raw is not None else None
            if cyl_len is not None and cyl_len <= 0:
                raise ValueError(f"cylinder length at {name!r} must be positive")
            r_prev = decimal_input(geom["innerRadiusM"], f"inner radius at {name}")
            if r_prev <= 0:
                raise ValueError(f"positive inner radius required at {name}")
            raw_layers = geom["layers"]
            if not isinstance(raw_layers, list) or not (1 <= len(raw_layers) <= 32):
                raise ValueError(f"radial_shell at {name!r} requires 1 to 32 layers")
            if pi_box is None:
                pi_box = Box.bounds(*pi_rational_enclosure())

            radii = [r_prev]
            layers_parsed = []
            for idx, lyr in enumerate(raw_layers):
                if not isinstance(lyr, dict):
                    raise ValueError(f"radial_shell layer[{idx}] at {name!r} must be a mapping")
                _expect_exact_keys(
                    lyr,
                    required=("outerRadiusM", "conductivityWPerMK"),
                    optional=("alphaPerK", "referenceTemperatureK"),
                    label=f"ports[{name}].geometry.layers[{idx}]",
                )
                r_out = decimal_input(lyr["outerRadiusM"], f"layer {idx} outerRadiusM at {name}")
                k0 = decimal_input(lyr["conductivityWPerMK"], f"layer {idx} conductivityWPerMK at {name}")
                if r_out <= r_prev or k0 <= 0:
                    raise ValueError(
                        f"radial_shell layer[{idx}] at {name!r} requires strictly increasing outerRadiusM and positive conductivity"
                    )
                alpha_raw = lyr.get("alphaPerK")
                alpha = (
                    signed_decimal_input(alpha_raw, f"layer {idx} alphaPerK at {name}")
                    if alpha_raw is not None
                    else Fraction(0)
                )
                if alpha != 0:
                    if "referenceTemperatureK" not in lyr:
                        raise ValueError(
                            f"ports[{name}].geometry.layers[{idx}].referenceTemperatureK is required whenever alphaPerK is nonzero"
                        )
                    t_ref = decimal_input(lyr["referenceTemperatureK"], f"layer {idx} referenceTemperatureK at {name}")
                else:
                    t_ref = (
                        decimal_input(lyr["referenceTemperatureK"], f"layer {idx} referenceTemperatureK at {name}")
                        if "referenceTemperatureK" in lyr
                        else Fraction(0)
                    )
                if g_kind == "sphere":
                    g_layer_box = (4 * pi_box) * Box.exact(k0 / (Fraction(1) / r_prev - Fraction(1) / r_out))
                else:
                    g_layer_box = (2 * pi_box) * Box.exact(k0 * cyl_len) / radial_log(r_out / r_prev)
                layers_parsed.append({
                    "r_in": r_prev,
                    "r_out": r_out,
                    "k0": k0,
                    "alpha": alpha,
                    "t_ref": t_ref,
                    "g_box": g_layer_box,
                })
                radii.append(r_out)
                r_prev = r_out

            ext = _parse_exterior(ext_raw)
            if ext["eps"] > 0 or ext["h"] > 0:
                anchored = True
            r_last = radii[-1]
            area_box = pi_box * (4 * r_last * r_last if g_kind == "sphere" else 2 * cyl_len * r_last)
            parsed[name] = {
                "kind": "radial_shell",
                "g_kind": g_kind,
                "cyl_len": cyl_len,
                "radii": radii,
                "layers": layers_parsed,
                "pi_box": pi_box,
                "area": area_box.span(),
                **ext,
            }

    if not anchored:
        raise ValueError(
            "at least one maintained, phase_bath, or active exterior-exchange port is required "
            "to anchor steady temperatures"
        )
    return parsed, has_phase


def _solve_kirchhoff_graph(
    unknown_ids: list[str],
    fixed_temps: dict[str, Fraction],
    edges: list[KirchhoffEdge],
    exteriors: dict[str, dict[str, Any]],
    node_inj: dict[str, tuple[Fraction, Fraction]],
    *,
    max_sweeps: int = 120,
) -> tuple[dict[str, tuple[Fraction, Fraction]], int, str]:
    """Solve coupled nonlinear Kirchhoff M-function system with exact rational post-condition certification."""
    n_u = len(unknown_ids)
    idx_of = {uid: i for i, uid in enumerate(unknown_ids)}

    # Build adjacency lists and strict positive-conductivity domain per node.
    unk_edges: list[list[tuple[int, KirchhoffEdge]]] = [[] for _ in range(n_u)]
    fix_edges: list[list[tuple[Fraction, KirchhoffEdge]]] = [[] for _ in range(n_u)]
    node_all_edges: list[list[KirchhoffEdge]] = [[] for _ in range(n_u)]

    # Verify every fixed boundary strictly lies in the positive-conductivity domain of every incident edge!
    for e in edges:
        if e.a in fixed_temps:
            t_a = fixed_temps[e.a]
            if t_a < 0 or _dpsi(t_a, e.alpha, e.t_ref) <= 0:
                raise ValueError(
                    f"fixed temperature {t_a} K at {e.a!r} violates positive thermal conductivity k(T) > 0 on edge {e.name!r}"
                )
        if e.b in fixed_temps:
            t_b = fixed_temps[e.b]
            if t_b < 0 or _dpsi(t_b, e.alpha, e.t_ref) <= 0:
                raise ValueError(
                    f"fixed temperature {t_b} K at {e.b!r} violates positive thermal conductivity k(T) > 0 on edge {e.name!r}"
                )
        a_unk = e.a in idx_of
        b_unk = e.b in idx_of
        if a_unk and b_unk:
            ia, ib = idx_of[e.a], idx_of[e.b]
            unk_edges[ia].append((ib, e))
            unk_edges[ib].append((ia, e))
            node_all_edges[ia].append(e)
            node_all_edges[ib].append(e)
        elif a_unk and e.b in fixed_temps:
            ia = idx_of[e.a]
            fix_edges[ia].append((fixed_temps[e.b], e))
            node_all_edges[ia].append(e)
        elif b_unk and e.a in fixed_temps:
            ib = idx_of[e.b]
            fix_edges[ib].append((fixed_temps[e.a], e))
            node_all_edges[ib].append(e)

    if n_u == 0:
        return {}, 0, "converged"

    # Verify every unknown node is reachable from an anchor via g_lo > 0 edges.
    anchored_u: set[int] = set()
    for i, uid in enumerate(unknown_ids):
        if any(e.g_lo > 0 for _, e in fix_edges[i]):
            anchored_u.add(i)
        ext = exteriors.get(uid)
        if ext is not None and (ext["eps"] > 0 or ext["h"] > 0):
            anchored_u.add(i)
    visited = set(anchored_u)
    stack = list(anchored_u)
    while stack:
        cur = stack.pop()
        for m, e in unk_edges[cur]:
            if m not in visited and e.g_lo > 0:
                visited.add(m)
                stack.append(m)
    if len(visited) != n_u:
        unanchored = [unknown_ids[i] for i in range(n_u) if i not in visited]
        raise ValueError(
            f"independent-edge lower-bound anchoring test inconclusive for Kirchhoff nodes {unanchored}"
        )

    # Strict open conductivity domain (dom_lo_strict, dom_hi_strict) per unknown node.
    dom_lo_strict: list[Fraction | None] = []
    dom_hi_strict: list[Fraction | None] = []
    for i in range(n_u):
        lo_s: Fraction | None = None
        hi_s: Fraction | None = None
        for e in node_all_edges[i]:
            if e.alpha > 0:
                crit = e.t_ref - Fraction(1) / e.alpha
                if lo_s is None or crit > lo_s:
                    lo_s = crit
            elif e.alpha < 0:
                crit = e.t_ref - Fraction(1) / e.alpha
                if hi_s is None or crit < hi_s:
                    hi_s = crit
        if hi_s is not None and (hi_s <= 0 or (lo_s is not None and lo_s >= hi_s)):
            raise ValueError(f"empty positive-conductivity temperature domain at node {unknown_ids[i]!r}")
        dom_lo_strict.append(lo_s)
        dom_hi_strict.append(hi_s)

    def _in_domain_node(i: int, t_val: Fraction) -> bool:
        if t_val < 0:
            return False
        if dom_lo_strict[i] is not None and t_val <= dom_lo_strict[i]:
            return False
        if dom_hi_strict[i] is not None and t_val >= dom_hi_strict[i]:
            return False
        return True

    def _in_domain_vec(vec: list[Fraction]) -> bool:
        return all(_in_domain_node(i, vec[i]) for i in range(n_u))

    def _eval_res_i(i: int, t_val: Fraction, vec: list[Fraction], *, maximize: bool) -> Fraction:
        uid = unknown_ids[i]
        inj_lo, inj_hi = node_inj[uid]
        tot = -(inj_lo if maximize else inj_hi)
        for m, e in unk_edges[i]:
            dpsi_val = _psi(t_val, e.alpha, e.t_ref) - _psi(vec[m], e.alpha, e.t_ref)
            w = (e.g_hi if dpsi_val >= 0 else e.g_lo) if maximize else (e.g_lo if dpsi_val >= 0 else e.g_hi)
            tot += w * dpsi_val - e.power_w / 2
        for tf, e in fix_edges[i]:
            dpsi_val = _psi(t_val, e.alpha, e.t_ref) - _psi(tf, e.alpha, e.t_ref)
            w = (e.g_hi if dpsi_val >= 0 else e.g_lo) if maximize else (e.g_lo if dpsi_val >= 0 else e.g_hi)
            tot += w * dpsi_val - e.power_w / 2
        ext = exteriors.get(uid)
        if ext is not None:
            q = _exterior_flux_per_area(t_val, ext["env_k"], ext["eps"], ext["sigma"], ext["air_k"], ext["h"])
            a_lo, a_hi = ext["area"]
            a_w = (a_hi if q >= 0 else a_lo) if maximize else (a_lo if q >= 0 else a_hi)
            tot += a_w * q
        return tot

    def _eval_res_vec(vec: list[Fraction], *, maximize: bool) -> list[Fraction]:
        return [_eval_res_i(i, vec[i], vec, maximize=maximize) for i in range(n_u)]

    def _build_jacobian(vec: list[Fraction], *, maximize: bool) -> list[list[Fraction]]:
        jac = [[Fraction(0)] * n_u for _ in range(n_u)]
        for i in range(n_u):
            t_i = vec[i]
            diag = Fraction(0)
            for m, e in unk_edges[i]:
                dpsi_val = _psi(t_i, e.alpha, e.t_ref) - _psi(vec[m], e.alpha, e.t_ref)
                w = (e.g_hi if dpsi_val >= 0 else e.g_lo) if maximize else (e.g_lo if dpsi_val >= 0 else e.g_hi)
                diag += w * _dpsi(t_i, e.alpha, e.t_ref)
                jac[i][m] -= w * _dpsi(vec[m], e.alpha, e.t_ref)
            for tf, e in fix_edges[i]:
                dpsi_val = _psi(t_i, e.alpha, e.t_ref) - _psi(tf, e.alpha, e.t_ref)
                w = (e.g_hi if dpsi_val >= 0 else e.g_lo) if maximize else (e.g_lo if dpsi_val >= 0 else e.g_hi)
                diag += w * _dpsi(t_i, e.alpha, e.t_ref)
            ext = exteriors.get(unknown_ids[i])
            if ext is not None:
                q = _exterior_flux_per_area(t_i, ext["env_k"], ext["eps"], ext["sigma"], ext["air_k"], ext["h"])
                a_lo, a_hi = ext["area"]
                a_w = (a_hi if q >= 0 else a_lo) if maximize else (a_lo if q >= 0 else a_hi)
                dq = ext["h"] + 4 * ext["eps"] * ext["sigma"] * (t_i**3)
                diag += a_w * dq
            jac[i][i] = diag
        return jac

    # Collect boundary anchor temperatures for initial guess & maximum-principle fallback.
    anchor_temps: list[Fraction] = list(fixed_temps.values())
    for uid, ext in exteriors.items():
        if ext["eps"] > 0:
            anchor_temps.append(ext["env_k"])
        if ext["air_k"] is not None and ext["h"] > 0:
            anchor_temps.append(ext["air_k"])
    t_min_bc = min(anchor_temps)
    t_max_bc = max(anchor_temps)
    t_avg_bc = (t_min_bc + t_max_bc) / 2

    def _safe_interior_seed() -> list[Fraction]:
        seed: list[Fraction] = []
        for i in range(n_u):
            lo_eff = Fraction(0) if dom_lo_strict[i] is None else max(Fraction(0), dom_lo_strict[i])
            hi_eff = dom_hi_strict[i]
            t_cand = t_avg_bc
            if hi_eff is not None:
                if t_cand >= hi_eff:
                    t_cand = (lo_eff + hi_eff) / 2
                if t_cand <= lo_eff:
                    t_cand = (lo_eff + hi_eff) / 2
                if not _in_domain_node(i, t_cand):
                    t_cand = (lo_eff + hi_eff) / 2
            else:
                if t_cand <= lo_eff:
                    t_cand = lo_eff + Fraction(1)
            seed.append(t_cand)
        return seed

    def _newton_candidate(start: list[Fraction], *, maximize: bool) -> tuple[list[Fraction], int]:
        vec = list(start)
        iters = 0
        tol_n = Fraction(1, 10**23)
        for it in range(1, 45):
            iters = it
            res = _eval_res_vec(vec, maximize=maximize)
            norm_inf = max((abs(v) for v in res), default=Fraction(0))
            if norm_inf <= tol_n:
                break
            jac = _build_jacobian(vec, maximize=maximize)
            try:
                step = _solve_exact_linear_fractions(jac, [-v for v in res])
            except ValueError:
                break
            lam = Fraction(1)
            accepted = False
            for _ in range(28):
                cand = [_clamp_fraction(vec[i] + lam * step[i]) for i in range(n_u)]
                if _in_domain_vec(cand):
                    cand_res = _eval_res_vec(cand, maximize=maximize)
                    cand_norm = max((abs(v) for v in cand_res), default=Fraction(0))
                    if cand_norm < norm_inf or cand_norm <= tol_n:
                        vec = cand
                        accepted = True
                        break
                lam = lam / 2
            if not accepted:
                break
        return vec, iters

    def _certify_barrier(cand: list[Fraction], *, maximize: bool) -> list[Fraction] | None:
        if not _in_domain_vec(cand):
            return None
        res = _eval_res_vec(cand, maximize=maximize)
        if maximize and all(v <= 0 for v in res):
            return list(cand)
        if not maximize and all(v >= 0 for v in res):
            return list(cand)
        jac = _build_jacobian(cand, maximize=maximize)
        try:
            delta = _solve_exact_linear_fractions(jac, [Fraction(1)] * n_u)
        except ValueError:
            return None
        if any(d <= 0 for d in delta):
            return None
        if maximize:
            err = max((v for v in res if v > 0), default=Fraction(0))
        else:
            err = max((-v for v in res if v < 0), default=Fraction(0))
        base_eps = max(err, Fraction(1, 10**26))
        for mult in (
            Fraction(2),
            Fraction(8),
            Fraction(64),
            Fraction(1024),
            Fraction(1, 10**18) / base_eps,
            Fraction(1, 10**12) / base_eps,
            Fraction(1, 10**6) / base_eps,
        ):
            eps = base_eps * mult
            if eps <= 0:
                continue
            if maximize:
                trial = [_floor_fraction(cand[i] - eps * delta[i]) for i in range(n_u)]
                if _in_domain_vec(trial) and all(v <= 0 for v in _eval_res_vec(trial, maximize=True)):
                    return trial
            else:
                trial = [_ceil_fraction(cand[i] + eps * delta[i]) for i in range(n_u)]
                if _in_domain_vec(trial) and all(v >= 0 for v in _eval_res_vec(trial, maximize=False)):
                    return trial
        return None

    exact_params = (
        all(e.g_lo == e.g_hi for e in edges)
        and all(ext["area"][0] == ext["area"][1] for ext in exteriors.values())
        and all(lo == hi for lo, hi in node_inj.values())
    )

    seed = _safe_interior_seed()
    sweeps_used = 0
    if exact_params:
        cand, it_c = _newton_candidate(seed, maximize=True)
        sweeps_used = it_c
        u_lo = _certify_barrier(cand, maximize=True)
        u_hi = _certify_barrier(cand, maximize=False)
    else:
        cand_lo, it_lo = _newton_candidate(seed, maximize=True)
        cand_hi, it_hi = _newton_candidate(cand_lo if _in_domain_vec(cand_lo) else seed, maximize=False)
        sweeps_used = max(it_lo, it_hi)
        u_lo = _certify_barrier(cand_lo, maximize=True)
        u_hi = _certify_barrier(cand_hi, maximize=False)

    termination_reason = "converged"
    need_gs = (
        u_lo is None
        or u_hi is None
        or any(u_lo[i] > u_hi[i] for i in range(n_u))
        or max((abs(v) for v in _eval_res_vec(u_lo, maximize=True)), default=Fraction(0)) > Fraction(1, 10**16)
        or max((abs(v) for v in _eval_res_vec(u_hi, maximize=False)), default=Fraction(0)) > Fraction(1, 10**16)
    )
    if need_gs:
        # Monotone Gauss-Seidel refinement/fallback starting from certified outer bracket inside D.
        has_power = any(e.power_w > 0 for e in edges) or any(hi > 0 for _, hi in node_inj.values())
        if u_lo is None or (u_hi is not None and any(u_lo[i] > u_hi[i] for i in range(n_u))):
            cand_lo_fb = [t_min_bc] * n_u
            if _in_domain_vec(cand_lo_fb) and all(v <= 0 for v in _eval_res_vec(cand_lo_fb, maximize=True)):
                u_lo = cand_lo_fb
            else:
                raise ValueError(
                    "cannot certify positive-conductivity lower bound (solution may violate k(T) > 0)"
                )
        if u_hi is None or any(u_lo[i] > u_hi[i] for i in range(n_u)):
            cand_hi_fb = [t_max_bc] * n_u
            if (
                not has_power
                and _in_domain_vec(cand_hi_fb)
                and all(v >= 0 for v in _eval_res_vec(cand_hi_fb, maximize=False))
            ):
                u_hi = cand_hi_fb
            else:
                raise ValueError(
                    "cannot certify positive-conductivity upper bound (solution may violate k(T) > 0)"
                )
        tol_gs = Fraction(1, 10**22)
        converged = False
        for sw in range(1, max_sweeps + 1):
            sweeps_used = sw
            max_delta = Fraction(0)
            for i in range(n_u):
                old_lo, old_hi = u_lo[i], u_hi[i]
                lo_root = _bisect_monotone_bound(
                    lambda t, idx=i: _eval_res_i(idx, t, u_lo, maximize=True),
                    old_lo,
                    old_hi,
                    find_leftmost_zero=True,
                    steps=90,
                )
                new_lo = max(old_lo, _floor_fraction(lo_root))
                if new_lo > old_hi:
                    raise ValueError("Kirchhoff monotone enclosure collapsed inconsistently")
                u_lo[i] = new_lo

                hi_root = _bisect_monotone_bound(
                    lambda t, idx=i: _eval_res_i(idx, t, u_hi, maximize=False),
                    new_lo,
                    old_hi,
                    find_leftmost_zero=False,
                    steps=90,
                )
                new_hi = min(old_hi, _ceil_fraction(hi_root))
                if new_lo > new_hi:
                    raise ValueError("Kirchhoff monotone enclosure collapsed inconsistently")
                u_hi[i] = new_hi
                delta = max(new_lo - old_lo, old_hi - new_hi)
                if delta > max_delta:
                    max_delta = delta
            if max_delta <= tol_gs:
                converged = True
                break
        termination_reason = "converged" if converged else "sweep_limit"

    # Independent exact rational post-condition certification (NEVER skipped!).
    for i in range(n_u):
        if u_lo[i] > u_hi[i]:
            raise ValueError(f"Kirchhoff steady enclosure inverted at node {unknown_ids[i]!r}")
        if not _in_domain_node(i, u_lo[i]) or not _in_domain_node(i, u_hi[i]):
            raise ValueError(
                f"Kirchhoff steady temperature enclosure violates positive conductivity k(T) > 0 at node {unknown_ids[i]!r}"
            )
        if _eval_res_i(i, u_lo[i], u_lo, maximize=True) > 0:
            raise ValueError(f"Kirchhoff steady lower-bound residual certification failed at {unknown_ids[i]!r}")
        if _eval_res_i(i, u_hi[i], u_hi, maximize=False) < 0:
            raise ValueError(f"Kirchhoff steady upper-bound residual certification failed at {unknown_ids[i]!r}")

    return {unknown_ids[i]: (u_lo[i], u_hi[i]) for i in range(n_u)}, sweeps_used, termination_reason


def _recover_rod_profiles(
    model: KirchhoffRodModel,
    node_temps: dict[str, tuple[Fraction, Fraction]],
    *,
    probe: tuple[str, Fraction] | None = None,
) -> dict[str, Any]:
    """Recover certified per-rod Kirchhoff profiles, peak temperatures, conductivity spans, and optional probe."""
    if probe is not None:
        if not isinstance(probe, (tuple, list)) or len(probe) != 2:
            raise ValueError("rod_probe must be a (rod_name, position_fraction) pair")
        p_name, p_x = probe
        edge_names = {e.name for e in model.edges}
        if p_name not in edge_names:
            raise ValueError(f"probe rod {p_name!r} not found in rods {sorted(edge_names)}")
        if not isinstance(p_x, Fraction) or not (0 <= p_x <= 1):
            raise ValueError("probe position fraction must be a Fraction in [0, 1]")

    rod_summaries: dict[str, Any] = {}
    probe_out: dict[str, Any] | None = None

    for edge in model.edges:
        al, ah = node_temps[edge.a]
        bl, bh = node_temps[edge.b]
        psi_al = _psi(al, edge.alpha, edge.t_ref)
        psi_ah = _psi(ah, edge.alpha, edge.t_ref)
        psi_bl = _psi(bl, edge.alpha, edge.t_ref)
        psi_bh = _psi(bh, edge.alpha, edge.t_ref)

        p = edge.power_w
        curve_lo = p / (2 * edge.g_hi)
        curve_hi = p / (2 * edge.g_lo)

        psi_peak_lo = _parabolic_peak(psi_al, psi_bl, curve_lo)
        psi_peak_hi = _parabolic_peak(psi_ah, psi_bh, curve_hi)
        t_peak_lo, t_peak_hi = _invert_psi_box(
            psi_peak_lo, psi_peak_hi, edge.alpha, edge.t_ref, label=f"rod {edge.name!r} peak"
        )

        if p > 0:
            xs = [
                max(Fraction(0), min(Fraction(1), (Fraction(1) + d / c) / 2))
                for d, c in product((psi_bl - psi_ah, psi_bh - psi_al), (curve_lo, curve_hi))
            ]
            pos_lo, pos_hi = min(xs), max(xs)
        elif al > bh:
            pos_lo = pos_hi = Fraction(0)
        elif bl > ah:
            pos_lo = pos_hi = Fraction(1)
        else:
            pos_lo, pos_hi = Fraction(0), Fraction(1)

        # Conductivity range k(T) along the entire rod (T in [min(al, bl), t_peak_hi]).
        t_rod_lo = min(al, bl)
        t_rod_hi = t_peak_hi
        dpsi_vals = [_dpsi(t_rod_lo, edge.alpha, edge.t_ref), _dpsi(t_rod_hi, edge.alpha, edge.t_ref)]
        if min(dpsi_vals) <= 0:
            raise ValueError(f"rod {edge.name!r} violates positive thermal conductivity k(T) > 0 along its span")
        k_corners = [k0 * r for k0 in (edge.k0_lo, edge.k0_hi) for r in dpsi_vals]
        q_a_to_b = _edge_flow_out_of_a_box(al, ah, bl, bh, edge)

        rod_summaries[edge.name] = {
            "fromNode": edge.a,
            "toNode": edge.b,
            "alphaPerK": str(edge.alpha),
            "referenceTemperatureK": str(edge.t_ref),
            "generatedPowerW": str(p),
            "conductivityBoundsWPerMK": [str(min(k_corners)), str(max(k_corners))],
            "heatCurrentAtATowardBBoundsW": bounds(q_a_to_b),
            "peakTemperatureBoundsK": [str(t_peak_lo), str(t_peak_hi)],
            "peakPositionFractionFromABounds": [str(pos_lo), str(pos_hi)],
        }

        if probe is not None and probe[0] == edge.name:
            x = probe[1]
            psi_x_lo = (1 - x) * psi_al + x * psi_bl + curve_lo * (x * (1 - x))
            psi_x_hi = (1 - x) * psi_ah + x * psi_bh + curve_hi * (x * (1 - x))
            tx_lo, tx_hi = _invert_psi_box(
                psi_x_lo, psi_x_hi, edge.alpha, edge.t_ref, label=f"rod {edge.name!r} probe at x={x}"
            )
            # Q(x) toward b = g*(psi(T_a) - psi(T_b)) + P*(x - 1/2) = Q_{a -> edge} + P*x
            q_probe = q_a_to_b + Box.exact(p * x)
            probe_out = {
                "rod": edge.name,
                "fromNode": edge.a,
                "toNode": edge.b,
                "positionFractionFromA": str(x),
                "temperatureBoundsK": [str(tx_lo), str(tx_hi)],
                "heatCurrentTowardBBoundsW": bounds(q_probe),
            }

    out: dict[str, Any] = {
        "totalGeneratedPowerW": str(model.total_generated_power_w),
        "nodeTemperatureBoundsK": {
            n: [str(node_temps[n][0]), str(node_temps[n][1])] for n in model.nodes
        },
        "rods": rod_summaries,
    }
    if probe_out is not None:
        out["probe"] = probe_out
    return out


def solve_kirchhoff_steady(
    conduction: KirchhoffRodModel | Any,
    ports: dict[str, Any],
    *,
    duration_s: str | None = None,
    max_sweeps: int = 120,
    rod_probe: tuple[str, Fraction] | None = None,
    terminal_injections_w: dict[str, tuple[Fraction, Fraction]] | None = None,
    total_generated_power_w: Fraction | None = None,
) -> dict[str, Any]:
    """Solve a steady thermal network with temperature-dependent conductivity via exact Kirchhoff potential.

    ``conduction`` may be either a ``KirchhoffRodModel`` (full rod graph with arbitrary internal junctions,
    optional ``alphaPerK``, and optional ``generatedPowerW``) OR a validated constant-k ``DerivedLaw``
    (composed with one or more Kirchhoff ``radial_shell`` attachments).
    """
    if isinstance(max_sweeps, bool) or not isinstance(max_sweeps, int) or max_sweeps < 1:
        raise ValueError("max_sweeps must be a positive integer")

    is_rod_model = isinstance(conduction, KirchhoffRodModel)
    if is_rod_model:
        if terminal_injections_w is not None or total_generated_power_w not in (None, 0):
            raise ValueError(
                "terminal_injections_w/total_generated_power_w are built into KirchhoffRodModel edges directly"
            )
        terminals = list(conduction.terminals)
        provenance: dict[str, Any] = {
            "kirchhoffModelSha256": conduction.content_sha256,
        }
        source_identity: dict[str, Any] = {
            "kirchhoffModelSha256": conduction.content_sha256,
            "conductionKind": "kirchhoff_rod_graph",
        }
        source_ref_temps = None
        total_gen_box = Box.exact(conduction.total_generated_power_w)
        inj_by_term = {t: (Fraction(0), Fraction(0)) for t in terminals}
    else:
        if rod_probe is not None:
            raise ValueError("rod_probe requires a conduction.rods KirchhoffRodModel")
        resolved_law, provenance = validate_terminal_law(conduction)
        engine_law = resolved_law.to_engine_law()
        terminals = list(engine_law["terminals"])
        w_net = _symmetric_conductances(terminals, engine_law)
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
        if terminal_injections_w is None:
            if total_generated_power_w not in (None, 0):
                raise ValueError("total_generated_power_w requires terminal_injections_w")
            inj_by_term = {t: (Fraction(0), Fraction(0)) for t in terminals}
            total_gen_box = ZERO
        else:
            if not isinstance(terminal_injections_w, dict) or set(terminal_injections_w) != set(terminals):
                raise ValueError("terminal_injections_w keys must match network terminals")
            inj_by_term = {}
            for t in terminals:
                lo, hi = terminal_injections_w[t]
                if lo < 0 or lo > hi:
                    raise ValueError(f"terminal_injections_w[{t!r}] must be a valid nonnegative interval")
                inj_by_term[t] = (lo, hi)
            sum_lo = sum((inj_by_term[t][0] for t in terminals), Fraction(0))
            sum_hi = sum((inj_by_term[t][1] for t in terminals), Fraction(0))
            if total_generated_power_w is not None:
                if not (sum_lo <= total_generated_power_w <= sum_hi):
                    raise ValueError("total_generated_power_w disagrees with terminal_injections_w sum")
                total_gen_box = Box.exact(total_generated_power_w)
            else:
                total_gen_box = Box.bounds(sum_lo, sum_hi)

    parsed_ports, has_phase = _parse_kirchhoff_ports(terminals, ports)
    duration = None
    if has_phase:
        if duration_s is None:
            raise ValueError("duration_s is required when one or more phase_bath ports are present")
        duration = decimal_input(duration_s, "duration")
    elif duration_s is not None:
        duration = decimal_input(duration_s, "duration")

    # Assemble unified node IDs, fixed temperatures, Kirchhoff edges, exteriors, and injections.
    fixed_temps: dict[str, Fraction] = {}
    unknown_ids: list[str] = []
    exteriors: dict[str, dict[str, Any]] = {}
    node_inj: dict[str, tuple[Fraction, Fraction]] = {}
    net_edges: list[KirchhoffEdge] = []
    all_shell_edges: list[KirchhoffEdge] = []
    term_set = set(terminals)

    def _node_uid(n: str) -> str:
        return f"port:{n}" if n in term_set else f"junc:{n}"

    if is_rod_model:
        for j in conduction.junctions:
            uid = f"junc:{j}"
            unknown_ids.append(uid)
            node_inj[uid] = (Fraction(0), Fraction(0))
        for e in conduction.edges:
            net_edges.append(
                KirchhoffEdge(
                    name=e.name,
                    a=_node_uid(e.a),
                    b=_node_uid(e.b),
                    g_lo=e.g_lo,
                    g_hi=e.g_hi,
                    alpha=e.alpha,
                    t_ref=e.t_ref,
                    power_w=e.power_w,
                    k0_lo=e.k0_lo,
                    k0_hi=e.k0_hi,
                    is_rod=True,
                )
            )
    else:
        for idx_i, i in enumerate(terminals):
            for j in terminals[idx_i + 1:]:
                w_lo, w_hi = w_net[(i, j)]
                if w_hi > 0:
                    net_edges.append(
                        KirchhoffEdge(
                            name=f"law:{i}:{j}",
                            a=f"port:{i}",
                            b=f"port:{j}",
                            g_lo=w_lo,
                            g_hi=w_hi,
                            alpha=Fraction(0),
                            t_ref=Fraction(0),
                            power_w=Fraction(0),
                            is_rod=False,
                        )
                    )

    shell_layer_edges: dict[str, list[KirchhoffEdge]] = {}
    shell_node_chain: dict[str, list[str]] = {}
    for name in terminals:
        p = parsed_ports[name]
        u_port = f"port:{name}"
        node_inj[u_port] = inj_by_term[name]
        if p["kind"] == "maintained":
            fixed_temps[u_port] = p["temp"]
        elif p["kind"] == "phase_bath":
            fixed_temps[u_port] = p["transition"]
        elif p["kind"] == "radiating_surface":
            unknown_ids.append(u_port)
            exteriors[u_port] = p
        else:  # radial_shell
            unknown_ids.append(u_port)
            layers = p["layers"]
            n_l = len(layers)
            chain = [u_port]
            for idx in range(1, n_l):
                u_mid = f"shell:{name}:{idx}"
                unknown_ids.append(u_mid)
                node_inj[u_mid] = (Fraction(0), Fraction(0))
                chain.append(u_mid)
            u_surf = f"surface:{name}"
            unknown_ids.append(u_surf)
            node_inj[u_surf] = (Fraction(0), Fraction(0))
            exteriors[u_surf] = p
            chain.append(u_surf)
            shell_node_chain[name] = chain
            s_edges: list[KirchhoffEdge] = []
            for idx, lyr in enumerate(layers):
                g_lo, g_hi = lyr["g_box"].span()
                se = KirchhoffEdge(
                    name=f"shell:{name}:layer{idx}",
                    a=chain[idx],
                    b=chain[idx + 1],
                    g_lo=g_lo,
                    g_hi=g_hi,
                    alpha=lyr["alpha"],
                    t_ref=lyr["t_ref"],
                    power_w=Fraction(0),
                    k0_lo=lyr["k0"],
                    k0_hi=lyr["k0"],
                    is_rod=False,
                )
                all_shell_edges.append(se)
                s_edges.append(se)
            shell_layer_edges[name] = s_edges

    graph_edges = net_edges + all_shell_edges
    solved_u, sweeps, termination_reason = _solve_kirchhoff_graph(
        unknown_ids, fixed_temps, graph_edges, exteriors, node_inj, max_sweeps=max_sweeps
    )

    # Assemble all node temperature spans (fixed + solved).
    all_u: dict[str, tuple[Fraction, Fraction]] = {uid: (val, val) for uid, val in fixed_temps.items()}
    all_u.update(solved_u)

    # Compute network-side heat flowing INTO each terminal port from the conduction graph:
    # Q_{net -> t} = I_t + sum_{e incident to t in conduction graph} (-Q_{t -> e}).
    net_edges_only = net_edges
    net_outflows: dict[str, Box] = {}
    for name in terminals:
        u_t = f"port:{name}"
        q_net = Box.bounds(*inj_by_term[name])
        for e in net_edges_only:
            if e.a == u_t:
                al, ah = all_u[e.a]
                bl, bh = all_u[e.b]
                q_net = q_net - _edge_flow_out_of_a_box(al, ah, bl, bh, e)
            elif e.b == u_t:
                al, ah = all_u[e.a]
                bl, bh = all_u[e.b]
                # -Q_{b -> e} = Q_{a -> e} + P_e
                q_net = q_net + _edge_flow_out_of_a_box(al, ah, bl, bh, e) + Box.exact(e.power_w)
        net_outflows[name] = q_net

    port_outflows: dict[str, Box] = {}
    radial_profiles: dict[str, list[dict[str, Any]]] = {}
    exterior_splits: dict[str, dict[str, Any]] = {}
    for name in terminals:
        p = parsed_ports[name]
        u_t = f"port:{name}"
        t_lo, t_hi = all_u[u_t]
        if p["kind"] in ("maintained", "phase_bath"):
            port_outflows[name] = net_outflows[name]
        elif p["kind"] == "radiating_surface":
            q_ext = _exterior_outflow_box(t_lo, t_hi, p)
            q_comb = _intersect_boxes([net_outflows[name], q_ext], f"port {name}")
            port_outflows[name] = q_comb
            area_box = Box.bounds(*p["area"])
            q_rad = area_box * p["eps"] * p["sigma"] * Box.bounds(t_lo**4 - p["env_k"]**4, t_hi**4 - p["env_k"]**4)
            split = {"netHeatToEnclosureBoundsW": bounds(q_rad)}
            if p["air_k"] is not None:
                q_conv = area_box * p["h"] * Box.bounds(t_lo - p["air_k"], t_hi - p["air_k"])
                split["netHeatToAirBoundsW"] = bounds(q_conv)
            exterior_splits[name] = split
        else:  # radial_shell
            chain = shell_node_chain[name]
            ts_lo, ts_hi = all_u[chain[-1]]
            q_ext = _exterior_outflow_box(ts_lo, ts_hi, p)
            layer_q_boxes = [
                _edge_flow_out_of_a_box(*all_u[se.a], *all_u[se.b], se) for se in shell_layer_edges[name]
            ]
            q_comb = _intersect_boxes([net_outflows[name], q_ext, *layer_q_boxes], f"radial_shell {name}")
            port_outflows[name] = q_comb

            # Exact certified radial interface temperature & outward heat flux profile.
            pi_b = p["pi_box"]
            profile = []
            for r_val, u_if in zip(p["radii"], chain, strict=True):
                if p["g_kind"] == "sphere":
                    flux = q_comb * (Fraction(1) / (r_val * r_val)) / (4 * pi_b)
                else:
                    flux = q_comb * (Fraction(1) / (2 * p["cyl_len"] * r_val)) / pi_b
                t_if_lo, t_if_hi = all_u[u_if]
                profile.append({
                    "radiusM": str(r_val),
                    "temperatureBoundsK": [str(t_if_lo), str(t_if_hi)],
                    "outwardHeatFluxBoundsWPerM2": bounds(flux),
                })
            radial_profiles[name] = profile

            area_box = Box.bounds(*p["area"])
            q_rad = area_box * p["eps"] * p["sigma"] * Box.bounds(ts_lo**4 - p["env_k"]**4, ts_hi**4 - p["env_k"]**4)
            split = {"netHeatToEnclosureBoundsW": bounds(q_rad)}
            if p["air_k"] is not None:
                q_conv = area_box * p["h"] * Box.bounds(ts_lo - p["air_k"], ts_hi - p["air_k"])
                split["netHeatToAirBoundsW"] = bounds(q_conv)
            exterior_splits[name] = split

    # Tighten each phase_bath inflow via global steady energy conservation.
    for name in terminals:
        if parsed_ports[name]["kind"] == "phase_bath":
            others_sum = sum((port_outflows[o] for o in terminals if o != name), ZERO)
            port_outflows[name] = _intersect_boxes(
                [port_outflows[name], total_gen_box - others_sum], f"phase_bath {name}"
            )

    # Verify global steady energy conservation residual contains 0.
    global_balance = sum((port_outflows[name] for name in terminals), ZERO) - total_gen_box
    bal_lo, bal_hi = global_balance.span()
    if bal_lo > 0 or bal_hi < 0:
        raise ValueError(f"Kirchhoff steady global energy balance does not contain zero: {bounds(global_balance)}")
    global_balance_bounds = bounds(global_balance)
    port_outflow_spans = {name: port_outflows[name].span() for name in terminals}

    # Recover certified rod profiles (also verifies k(T) > 0 at heated-rod interior peaks!).
    rod_summary: dict[str, Any] | None = None
    if is_rod_model:
        rod_node_temps = {n: all_u[_node_uid(n)] for n in conduction.nodes}
        rod_summary = _recover_rod_profiles(conduction, rod_node_temps, probe=rod_probe)

    max_temp_width = max((hi - lo for lo, hi in solved_u.values()), default=Fraction(0))
    max_heat_width = max(
        (port_outflow_spans[name][1] - port_outflow_spans[name][0] for name in terminals),
        default=Fraction(0),
    )

    # Multi-phase-bath plateau & earliest-exhaustion accounting (mirrors multiport_thermal_network).
    phase_ports = [name for name in terminals if parsed_ports[name]["kind"] == "phase_bath"]
    phase_details: dict[str, dict[str, Any]] = {}
    phase_system: dict[str, Any] | None = None
    if phase_ports:
        bath_meta: dict[str, dict[str, Any]] = {}
        active_exh = []
        for name in phase_ports:
            p = parsed_ports[name]
            q_lo, q_hi = port_outflow_spans[name]
            if q_lo > 0:
                proc = "melting"
                t_lo = p["solid"] * p["latent"] / q_hi
                t_hi = p["solid"] * p["latent"] / q_lo
                exh_phase = "solid"
                exh_at_start = p["solid"] == 0
                active_exh.append((name, t_lo, t_hi, exh_phase))
            elif q_hi < 0:
                proc = "freezing"
                t_lo = p["liquid"] * p["latent"] / (-q_lo)
                t_hi = p["liquid"] * p["latent"] / (-q_hi)
                exh_phase = "liquid"
                exh_at_start = p["liquid"] == 0
                active_exh.append((name, t_lo, t_hi, exh_phase))
            elif q_lo == q_hi == 0:
                proc = "equilibrium"
                t_lo = t_hi = None
                exh_phase = None
                exh_at_start = False
            else:
                raise ValueError(f"latent heat-flow direction is unresolved at phase_bath {name!r}")
            bath_meta[name] = {
                "process": proc,
                "q_lo": q_lo,
                "q_hi": q_hi,
                "t_lo": t_lo,
                "t_hi": t_hi,
                "exh_phase": exh_phase,
                "exhausted_at_start": exh_at_start,
            }

        if not active_exh:
            sys_status = "coexisting"
            first_lo = first_hi = None
            mod_lo = mod_hi = duration
            first_exhausted_ports: list[str] = []
        else:
            first_lo = min(item[1] for item in active_exh)
            first_hi = min(item[2] for item in active_exh)
            if duration < first_lo:
                sys_status = "coexisting"
                mod_lo = mod_hi = duration
                first_exhausted_ports = []
            elif duration >= first_hi:
                sys_status = "exhausted"
                mod_lo, mod_hi = first_lo, first_hi
                first_exhausted_ports = [item[0] for item in active_exh if item[1] <= first_hi]
            else:
                sys_status = "exhaustion_time_uncertain"
                mod_lo, mod_hi = first_lo, duration
                first_exhausted_ports = [item[0] for item in active_exh if item[1] <= duration]

        sys_exh_at_start = any(bath_meta[n]["exhausted_at_start"] for n in phase_ports)

        for name in phase_ports:
            p = parsed_ports[name]
            m = bath_meta[name]
            q_lo, q_hi = m["q_lo"], m["q_hi"]
            solid, liquid, latent = p["solid"], p["liquid"], p["latent"]
            if m["exhausted_at_start"]:
                mlo = mhi = Fraction(0)
                stop_status = "exhausted"
                req_status = "exhausted"
            elif sys_status == "exhausted" and first_exhausted_ports == [name]:
                mlo = mhi = solid if m["process"] == "melting" else -liquid
                stop_status = "exhausted"
                req_status = "exhausted"
            else:
                def _clip(q: Fraction, t: Fraction) -> Fraction:
                    return min(solid, max(-liquid, q * t / latent))

                conv_vals = [_clip(q, t) for q in (q_lo, q_hi) for t in (mod_lo, mod_hi)]
                mlo, mhi = min(conv_vals), max(conv_vals)
                if m["t_lo"] is None:
                    stop_status = req_status = "coexisting"
                else:
                    stop_status = (
                        "exhausted"
                        if mod_lo >= m["t_hi"]
                        else ("coexisting" if mod_hi < m["t_lo"] else "exhaustion_time_uncertain")
                    )
                    req_status = (
                        "exhausted"
                        if duration >= m["t_hi"]
                        else ("coexisting" if duration < m["t_lo"] else "exhaustion_time_uncertain")
                    )

            rem_s = [str(solid - mhi), str(solid - mlo)]
            rem_l = [str(liquid + mlo), str(liquid + mhi)]
            lat_e = [str(mlo * latent), str(mhi * latent)]
            phase_details[name] = {
                "process": m["process"],
                "exhaustedPhase": m["exh_phase"],
                "exhaustedAtStart": m["exhausted_at_start"],
                "individualExhaustionTimeBoundsS": None if m["t_lo"] is None else [str(m["t_lo"]), str(m["t_hi"])],
                "plateauStatusAtModeledStop": stop_status,
                "plateauStatusAtRequestedDuration": req_status,
                "convertedMassBoundsKg": [str(mlo), str(mhi)],
                "remainingSolidBoundsKg": rem_s,
                "remainingLiquidBoundsKg": rem_l,
                "latentEnergyIntoBathBoundsJ": lat_e,
            }

        phase_system = {
            "requestedDurationS": str(duration),
            "modeledDurationBoundsS": [str(mod_lo), str(mod_hi)],
            "plateauStatus": sys_status,
            "exhaustedAtStart": sys_exh_at_start,
            "firstExhaustedPorts": first_exhausted_ports,
            "firstExhaustionTimeBoundsS": None if first_lo is None else [str(first_lo), str(first_hi)],
            "postExhaustionModeled": False,
        }

    # Build per-port output dictionary matching multiport schema conventions.
    active_bcs: dict[str, Any] = {}
    ports_out: dict[str, Any] = {}
    for name in terminals:
        p = parsed_ports[name]
        t_lo, t_hi = all_u[f"port:{name}"]
        q_lo, q_hi = port_outflow_spans[name]
        if p["kind"] == "maintained":
            active_bcs[name] = {"role": "maintained", "constraint": "fixed_dirichlet", "temperatureK": str(p["temp"])}
            ports_out[name] = {
                "kind": "maintained",
                "temperatureBoundsK": [str(t_lo), str(t_hi)],
                "inflowFromNetworkBoundsW": [str(q_lo), str(q_hi)],
                "energySignConvention": "into_maintained_reservoir_positive",
            }
        elif p["kind"] == "phase_bath":
            active_bcs[name] = {
                "role": "phase_bath",
                "constraint": "isothermal_coexistence_plateau",
                "transitionTemperatureK": str(p["transition"]),
            }
            ports_out[name] = {
                "kind": "phase_bath",
                "transitionTemperatureK": str(p["transition"]),
                "temperatureBoundsK": [str(t_lo), str(t_hi)],
                "inflowFromNetworkBoundsW": [str(q_lo), str(q_hi)],
                "energySignConvention": "into_phase_bath_positive",
                **phase_details[name],
            }
        elif p["kind"] == "radiating_surface":
            active_bcs[name] = {
                "role": "radiating_surface",
                "constraint": "nonlinear_radiative_convective_kirchhoff_balance",
                "temperatureBoundsK": [str(t_lo), str(t_hi)],
            }
            ports_out[name] = {
                "kind": "radiating_surface",
                "temperatureBoundsK": [str(t_lo), str(t_hi)],
                "outwardHeatRateBoundsW": [str(q_lo), str(q_hi)],
                "energySignConvention": "outward_from_surface_positive",
                **exterior_splits[name],
            }
        else:  # radial_shell
            ts_lo, ts_hi = all_u[shell_node_chain[name][-1]]
            active_bcs[name] = {
                "role": "radial_shell",
                "constraint": "nonlinear_kirchhoff_radial_shell_balance",
                "innerFaceTemperatureBoundsK": [str(t_lo), str(t_hi)],
                "outerFaceTemperatureBoundsK": [str(ts_lo), str(ts_hi)],
            }
            ports_out[name] = {
                "kind": "radial_shell",
                "geometryKind": p["g_kind"],
                "innerFaceTemperatureBoundsK": [str(t_lo), str(t_hi)],
                "outerFaceTemperatureBoundsK": [str(ts_lo), str(ts_hi)],
                "outwardHeatRateBoundsW": [str(q_lo), str(q_hi)],
                "surfaceProfile": radial_profiles[name],
                "energySignConvention": "outward_from_radial_surface_positive",
                **exterior_splits[name],
            }

    result: dict[str, Any] = {
        "schema": KIRCHHOFF_STEADY_SCHEMA,
        "evidence": {
            "category": EVIDENCE_CATEGORY,
            "sourceIdentity": source_identity,
            **{k: False for k in OFFLINE_FLAG_KEYS},
        },
        "network": {
            "terminals": terminals,
            "portKinds": {t: parsed_ports[t]["kind"] for t in terminals},
            "sourceLawReferenceTemperaturesK": source_ref_temps,
            "activeBoundaryConditions": active_bcs,
        },
        "ports": ports_out,
        "globalEnergyBalanceBoundsW": global_balance_bounds,
        "solverMetadata": {
            "method": "certified_kirchhoff_m_function_barrier_and_monotone_sweeps",
            "terminationReason": termination_reason,
            "sweepsExecuted": sweeps,
            "unknownCount": len(unknown_ids),
            "maxTemperatureWidthK": str(max_temp_width),
            "maxHeatRateWidthW": str(max_heat_width),
        },
        **provenance,
    }
    if phase_system is not None:
        result["phaseSystem"] = phase_system
    if rod_summary is not None:
        result["kirchhoffSummary"] = rod_summary
    return result
