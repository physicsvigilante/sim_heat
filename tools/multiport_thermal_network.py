"""General multi-port composable steady thermal network engine with certified rational enclosures.

Composes any pinned connected passive steady conduction network with arbitrary
per-terminal physical attachments:
- ``maintained``: fixed Dirichlet temperature reservoir
- ``phase_bath``: isothermal coexisting two-phase bath with latent inventory accounting
- ``radiating_surface``: direct diffuse-gray radiating and/or convecting exterior face
- ``radial_shell``: multilayer spherical or cylindrical shell with radiating/convecting exterior

Solves the coupled nonlinear M-function system via exact rational monotone sub-/super-solution
iteration (interval Gauss-Seidel with outward rounding) and independently certifies the final
enclosure against the pointwise parameter-box residuals and global steady energy conservation.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from qualification.h1_n13.conduction import ZERO, Box
from tools.join_thermal_networks import bounds
from tools.latent_heat_bath import phase_inputs
from tools.offline_investigation import PinnedSourceRef, _expect_exact_keys, validate_pinned_law
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS
from tools.radiating_surface import decimal_input
from tools.spherical_conduction import prepare_layers
from tools.terminal_response import investigate as terminal_response

MULTIPORT_SCHEMA = "sim_heat.offline_multiport_network/1"
EVIDENCE_CATEGORY = "offline_analytical_calculation"
VALID_PORT_KINDS = ("maintained", "phase_bath", "radiating_surface", "radial_shell")
_ROUND_SCALE = 10**30


def _floor_fraction(x):
    """Outward-round a Fraction downward onto the 10^-30 rational grid."""
    num = x.numerator * _ROUND_SCALE
    den = x.denominator
    return Fraction(num // den, _ROUND_SCALE)


def _ceil_fraction(x):
    """Outward-round a Fraction upward onto the 10^-30 rational grid."""
    num = x.numerator * _ROUND_SCALE
    den = x.denominator
    return Fraction(-((-num) // den), _ROUND_SCALE)


def _bisect_monotone_bound(eval_fn, lo, hi, *, find_leftmost_zero, steps=80):
    """Find a sound outer bound on the zero set of a non-decreasing function on [lo, hi].

    When find_leftmost_zero=True, returns a certified lower bound <= inf{t : f(t) >= 0}.
    When find_leftmost_zero=False, returns a certified upper bound >= sup{t : f(t) <= 0}.
    """
    f_lo = eval_fn(lo)
    if f_lo > 0:
        raise ValueError("monotone residual is already positive at lower bracket")
    f_hi = eval_fn(hi)
    if f_hi < 0:
        raise ValueError("monotone residual is still negative at upper bracket")
    if find_leftmost_zero:
        if f_lo == 0:
            return lo
        a, b = lo, hi
        for _ in range(steps):
            mid = (a + b) / 2
            if eval_fn(mid) >= 0:
                b = mid
            else:
                a = mid
        return a
    if f_hi == 0:
        return hi
    a, b = lo, hi
    for _ in range(steps):
        mid = (a + b) / 2
        if eval_fn(mid) <= 0:
            a = mid
        else:
            b = mid
    return b


def _exterior_flux_per_area(temp, env_k, eps, sigma, air_k, h):
    """Outward heat flux per unit area at temperature temp (strictly increasing in temp >= 0)."""
    q = eps * sigma * (temp**4 - env_k**4)
    if air_k is not None:
        q += h * (temp - air_k)
    return q


def _parse_exterior(ext):
    if not isinstance(ext, dict):
        raise ValueError("exterior mapping required")
    env_k = decimal_input(ext.get("enclosureTemperatureK"), "enclosure temperature")
    eps = decimal_input(ext.get("emissivity"), "emissivity")
    sigma = decimal_input(ext.get("sigmaWPerM2K4"), "Stefan-Boltzmann constant")
    if eps > 1 or sigma <= 0:
        raise ValueError("positive sigma and emissivity in [0,1] required")
    air_raw = ext.get("airTemperatureK")
    h_raw = ext.get("convectionCoefficientWPerM2K")
    if (air_raw is None) != (h_raw is None):
        raise ValueError("supply airTemperatureK and convectionCoefficientWPerM2K together")
    air_k = decimal_input(air_raw, "air temperature") if air_raw is not None else None
    h = decimal_input(h_raw, "convective heat transfer coefficient") if h_raw is not None else Fraction(0)
    return {
        "env_k": env_k,
        "eps": eps,
        "sigma": sigma,
        "air_k": air_k,
        "h": h,
    }


def _parse_port_specs(terminals, ports):
    if not isinstance(ports, dict) or set(ports) != set(terminals):
        raise ValueError("ports mapping must assign an attachment to every terminal in the pinned network")
    parsed = {}
    has_phase = False
    anchored = False

    for name in terminals:
        spec = ports[name]
        if not isinstance(spec, dict):
            raise ValueError(f"port {name!r} specification must be a mapping")
        kind = spec.get("kind")
        if kind not in VALID_PORT_KINDS:
            raise ValueError(f"port {name!r} has unsupported kind {kind!r}; expected one of {VALID_PORT_KINDS}")

        if kind == "maintained":
            _expect_exact_keys(spec, required=("kind", "temperatureK"), label=f"ports[{name}]")
            temp = decimal_input(spec.get("temperatureK"), f"maintained temperature at {name}")
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
            # Use dummy duration "0" here; actual shared duration_s is validated once at system level.
            tr, latent, solid, liquid, _ = phase_inputs(
                spec.get("transitionTemperatureK"),
                spec.get("specificLatentHeatJPerKg"),
                spec.get("initialSolidKg"),
                spec.get("initialLiquidKg"),
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
            area = decimal_input(spec.get("areaM2"), f"surface area at {name}")
            if area <= 0:
                raise ValueError(f"positive surface area required at {name}")
            ext = _parse_exterior(spec)
            if ext["eps"] > 0 or ext["h"] > 0:
                anchored = True
            parsed[name] = {
                "kind": "radiating_surface",
                "area": (area, area),
                **ext,
            }

        else:  # radial_shell
            _expect_exact_keys(spec, required=("kind", "geometry", "exterior"), label=f"ports[{name}]")
            geom = spec.get("geometry")
            _expect_exact_keys(
                geom,
                required=("kind", "innerRadiusM", "layers"),
                optional=("cylinderLengthM",),
                label=f"ports[{name}].geometry",
            )
            _expect_exact_keys(
                spec.get("exterior"),
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
            if not isinstance(raw_layers, list) or not raw_layers:
                raise ValueError(f"radial_shell at {name!r} requires non-empty layers list")
            layer_pairs = []
            for idx, lyr in enumerate(raw_layers):
                if isinstance(lyr, dict):
                    _expect_exact_keys(
                        lyr,
                        required=("outerRadiusM", "conductivityWPerMK"),
                        label=f"ports[{name}].geometry.layers[{idx}]",
                    )
                    layer_pairs.append((lyr.get("outerRadiusM"), lyr.get("conductivityWPerMK")))
                elif isinstance(lyr, (list, tuple)) and len(lyr) == 2:
                    layer_pairs.append((lyr[0], lyr[1]))
                else:
                    raise ValueError(f"radial_shell layer[{idx}] at {name!r} is malformed")
            shell = prepare_layers(geom.get("innerRadiusM"), layer_pairs, cyl_len)
            ext = _parse_exterior(spec.get("exterior"))
            if ext["eps"] > 0 or ext["h"] > 0:
                anchored = True
            r_lo, r_hi = shell.resistances[-1].span()
            g_shell = (Fraction(1) / r_hi, Fraction(1) / r_lo)
            parsed[name] = {
                "kind": "radial_shell",
                "shell": shell,
                "g_shell": g_shell,
                "area": shell.outer_area().span(),
                **ext,
            }

    if not anchored:
        raise ValueError(
            "at least one maintained, phase_bath, or active exterior-exchange port is required "
            "to anchor steady temperatures"
        )
    return parsed, has_phase


def _symmetric_conductances(terminals, law):
    """Extract certified reciprocal passive conductance intervals W_ij >= 0 from a validated law."""
    matrix = law["supplyResponseBoundsWPerK"]
    w = {}
    for idx_i, i in enumerate(terminals):
        for j in terminals[idx_i + 1:]:
            ij_lo, ij_hi = map(Fraction, matrix[i][j])
            ji_lo, ji_hi = map(Fraction, matrix[j][i])
            lo = max(Fraction(0), -min(ij_hi, ji_hi))
            hi = -max(ij_lo, ji_lo)
            if lo > hi:
                raise ValueError(f"nonreciprocal passive conductance between {i!r} and {j!r}")
            w[(i, j)] = (lo, hi)
            w[(j, i)] = (lo, hi)
    return w


def _eval_node_residual(u_k, neighbors, fixed_neighbors, exterior, u_vec, *, maximize):
    """Pointwise upper (maximize=True) or lower (maximize=False) residual f_k(u_k) over parameter box."""
    total = Fraction(0)
    for m, (w_lo, w_hi) in neighbors:
        diff = u_k - u_vec[m]
        if maximize:
            total += (w_hi if diff >= 0 else w_lo) * diff
        else:
            total += (w_lo if diff >= 0 else w_hi) * diff
    for t_fixed, (w_lo, w_hi) in fixed_neighbors:
        diff = u_k - t_fixed
        if maximize:
            total += (w_hi if diff >= 0 else w_lo) * diff
        else:
            total += (w_lo if diff >= 0 else w_hi) * diff
    if exterior is not None:
        a_lo, a_hi = exterior["area"]
        q = _exterior_flux_per_area(
            u_k, exterior["env_k"], exterior["eps"], exterior["sigma"], exterior["air_k"], exterior["h"]
        )
        if maximize:
            total += (a_hi if q >= 0 else a_lo) * q
        else:
            total += (a_lo if q >= 0 else a_hi) * q
    return total


def _verify_guaranteed_anchoring(terminals, parsed_ports, w_net):
    """Verify every terminal is reachable from an active temperature anchor via w_lo > 0 edges."""
    anchored = set()
    for name in terminals:
        p = parsed_ports[name]
        if p["kind"] in ("maintained", "phase_bath"):
            anchored.add(name)
        elif p["eps"] > 0 or p["h"] > 0:
            anchored.add(name)
    if not anchored:
        raise ValueError(
            "at least one maintained, phase_bath, or active exterior-exchange port is required "
            "to anchor steady temperatures"
        )
    visited = set(anchored)
    stack = list(anchored)
    while stack:
        cur = stack.pop()
        for other in terminals:
            if other != cur and other not in visited and w_net[(cur, other)][0] > 0:
                visited.add(other)
                stack.append(other)
    if visited != set(terminals):
        unanchored = sorted(set(terminals) - visited)
        raise ValueError(
            f"independent-edge lower-bound anchoring test inconclusive for terminals {unanchored}; "
            "the correlated feasible set may still be anchored"
        )


def _solve_exact_linear_fractions(matrix, rhs):
    """Exact rational Gaussian elimination with partial pivoting for nonsingular M-matrix systems."""
    n = len(rhs)
    aug = [list(matrix[i]) + [rhs[i]] for i in range(n)]
    for col in range(n):
        pivot = None
        for r in range(col, n):
            if aug[r][col] != 0:
                if pivot is None or abs(aug[r][col]) > abs(aug[pivot][col]):
                    pivot = r
        if pivot is None:
            raise ValueError("singular linear steady thermal system")
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        piv_val = aug[col][col]
        for r in range(col + 1, n):
            factor = aug[r][col] / piv_val
            if factor != 0:
                for c in range(col, n + 1):
                    aug[r][c] -= factor * aug[col][c]
    sol = [Fraction(0)] * n
    for r in range(n - 1, -1, -1):
        s = aug[r][n] - sum(aug[r][c] * sol[c] for c in range(r + 1, n))
        sol[r] = s / aug[r][r]
    return sol


def _solve_piecewise_linear_root(terms, *, maximize):
    """Exact rational root of sum_r w_r*(T - t_r) = 0 with strictly positive total slope."""
    knots = sorted({t_r for t_r, _, _ in terms})
    if len(knots) == 1:
        return knots[0]

    def _eval(t_val):
        total = Fraction(0)
        for t_r, w_lo, w_hi in terms:
            diff = t_val - t_r
            if maximize:
                total += (w_hi if diff >= 0 else w_lo) * diff
            else:
                total += (w_lo if diff >= 0 else w_hi) * diff
        return total

    for j, k_val in enumerate(knots):
        val = _eval(k_val)
        if val == 0:
            return k_val
        if val > 0:
            left = knots[j - 1]
            num = Fraction(0)
            den = Fraction(0)
            for t_r, w_lo, w_hi in terms:
                if t_r <= left:
                    w = w_hi if maximize else w_lo
                else:
                    w = w_lo if maximize else w_hi
                num += w * t_r
                den += w
            return num / den
    return knots[-1]


def _solve_monotone_network(terminals, parsed_ports, w_net, *, max_sweeps=120):
    """Solve coupled multi-port steady temperatures via exact rational linear or monotone block sweeps."""
    _verify_guaranteed_anchoring(terminals, parsed_ports, w_net)
    fixed_temps = {}
    unknown_ids = []
    for name in terminals:
        p = parsed_ports[name]
        if p["kind"] == "maintained":
            fixed_temps[name] = p["temp"]
        elif p["kind"] == "phase_bath":
            fixed_temps[name] = p["transition"]
        elif p["kind"] == "radiating_surface":
            unknown_ids.append(f"port:{name}")
        else:
            unknown_ids.append(f"port:{name}")
            unknown_ids.append(f"surface:{name}")

    if not unknown_ids:
        return {}, 0, "converged"

    idx_of = {uid: k for k, uid in enumerate(unknown_ids)}
    n_u = len(unknown_ids)
    neighbors = [[] for _ in range(n_u)]
    port_net_neighbors = [[] for _ in range(n_u)]
    fixed_neighbors = [[] for _ in range(n_u)]
    exteriors = [None] * n_u
    single_nodes = []
    shell_pairs = []

    for name in terminals:
        p = parsed_ports[name]
        if p["kind"] in ("maintained", "phase_bath"):
            continue
        k_port = idx_of[f"port:{name}"]
        for other in terminals:
            if other == name:
                continue
            w_pair = w_net[(name, other)]
            if w_pair == (Fraction(0), Fraction(0)):
                continue
            if other in fixed_temps:
                fixed_neighbors[k_port].append((fixed_temps[other], w_pair))
            else:
                nbr = (idx_of[f"port:{other}"], w_pair)
                neighbors[k_port].append(nbr)
                port_net_neighbors[k_port].append(nbr)
        if p["kind"] == "radiating_surface":
            exteriors[k_port] = p
            single_nodes.append(k_port)
        else:
            k_surf = idx_of[f"surface:{name}"]
            g_shell = p["g_shell"]
            neighbors[k_port].append((k_surf, g_shell))
            neighbors[k_surf].append((k_port, g_shell))
            exteriors[k_surf] = p
            shell_pairs.append((k_port, k_surf, g_shell))

    # Collect all active anchor temperatures to build a guaranteed global bracket [t_min, t_max].
    anchors = list(fixed_temps.values())
    for name in terminals:
        p = parsed_ports[name]
        if p["kind"] in ("radiating_surface", "radial_shell"):
            if p["eps"] > 0:
                anchors.append(p["env_k"])
            if p["air_k"] is not None and p["h"] > 0:
                anchors.append(p["air_k"])
    t_min = min(anchors)
    t_max = max(anchors)

    u_lo = [t_min] * n_u
    u_hi = [t_max] * n_u

    sweeps = 0
    if t_min == t_max:
        termination_reason = "converged"
    else:
        # Exact linear path applies ONLY when every conductance and area interval has zero width
        # (every pair in w_net, including fixed-to-fixed edges, and every port attachment,
        # excluding radial_shell) and every exterior has eps == 0.
        is_exact_linear = (
            all(w_lo == w_hi for w_lo, w_hi in w_net.values())
            and all(p["kind"] != "radial_shell" for p in parsed_ports.values())
            and all(
                p["area"][0] == p["area"][1] and p["eps"] == 0
                for p in parsed_ports.values()
                if "area" in p
            )
        )
        if is_exact_linear:
            mat = [[Fraction(0)] * n_u for _ in range(n_u)]
            rhs = [Fraction(0)] * n_u
            for k in range(n_u):
                diag = Fraction(0)
                for m, (w_val, _) in neighbors[k]:
                    diag += w_val
                    mat[k][m] -= w_val
                for t_fix, (w_val, _) in fixed_neighbors[k]:
                    diag += w_val
                    rhs[k] += w_val * t_fix
                ext = exteriors[k]
                if ext is not None and ext["air_k"] is not None and ext["h"] > 0:
                    ah = ext["area"][0] * ext["h"]
                    diag += ah
                    rhs[k] += ah * ext["air_k"]
                mat[k][k] = diag
            exact_sol = _solve_exact_linear_fractions(mat, rhs)
            u_lo = list(exact_sol)
            u_hi = list(exact_sol)
            termination_reason = "exact_linear"
        else:
            tol = Fraction(1, 10**24)
            eps_round = Fraction(1, _ROUND_SCALE)
            converged = False
            for sweep in range(1, max_sweeps + 1):
                sweeps = sweep
                max_delta = Fraction(0)
                for k in single_nodes:
                    # Lower bound update: leftmost zero of f_k^max(u_k; u_lo) on [u_lo[k], u_hi[k]].
                    lo_a = _bisect_monotone_bound(
                        lambda t, k=k: _eval_node_residual(
                            t, neighbors[k], fixed_neighbors[k], exteriors[k], u_lo, maximize=True
                        ),
                        u_lo[k],
                        u_hi[k],
                        find_leftmost_zero=True,
                    )
                    new_lo = max(u_lo[k], _floor_fraction(lo_a))
                    # Upper bound update: rightmost zero of f_k^min(u_k; u_hi) on [new_lo, u_hi[k]].
                    hi_b = _bisect_monotone_bound(
                        lambda t, k=k: _eval_node_residual(
                            t, neighbors[k], fixed_neighbors[k], exteriors[k], u_hi, maximize=False
                        ),
                        new_lo,
                        u_hi[k],
                        find_leftmost_zero=False,
                    )
                    new_hi = min(u_hi[k], _ceil_fraction(hi_b))
                    if new_lo > new_hi:
                        raise ValueError("monotone multi-port enclosure collapsed inconsistently")
                    delta = max(new_lo - u_lo[k], u_hi[k] - new_hi)
                    if delta > max_delta:
                        max_delta = delta
                    u_lo[k] = new_lo
                    u_hi[k] = new_hi

                for k_port, k_surf, g_shell in shell_pairs:
                    g_lo, g_hi = g_shell
                    ext = exteriors[k_surf]
                    a_lo, a_hi = ext["area"]

                    def _f_s(ti, ts, maximize, g_lo=g_lo, g_hi=g_hi, ext=ext, a_lo=a_lo, a_hi=a_hi):
                        diff = ts - ti
                        g = (g_hi if diff >= 0 else g_lo) if maximize else (g_lo if diff >= 0 else g_hi)
                        q = _exterior_flux_per_area(
                            ts, ext["env_k"], ext["eps"], ext["sigma"], ext["air_k"], ext["h"]
                        )
                        a = (a_hi if q >= 0 else a_lo) if maximize else (a_lo if q >= 0 else a_hi)
                        return g * diff + a * q

                    old_lo_i, old_lo_s = u_lo[k_port], u_lo[k_surf]
                    old_hi_i, old_hi_s = u_hi[k_port], u_hi[k_surf]

                    # Coupled 2x2 sub-solution block update with clamped -10^-30 outward-rounding slack.
                    base_lo = (
                        [(u_lo[m], w[0], w[1]) for m, w in port_net_neighbors[k_port]]
                        + [(tf, w[0], w[1]) for tf, w in fixed_neighbors[k_port]]
                    )

                    def _psi_max(ts, base_lo=base_lo, g_lo=g_lo, g_hi=g_hi):
                        return _solve_piecewise_linear_root(base_lo + [(ts, g_lo, g_hi)], maximize=True)

                    ts_a = _bisect_monotone_bound(
                        lambda ts: _f_s(max(old_lo_i, _psi_max(ts) - eps_round), ts, True),
                        old_lo_s,
                        old_hi_s,
                        find_leftmost_zero=True,
                        steps=100,
                    )
                    new_lo_s = max(old_lo_s, _floor_fraction(ts_a))
                    new_lo_i = max(old_lo_i, _floor_fraction(_psi_max(new_lo_s)))
                    if new_lo_i > old_hi_i or new_lo_s > old_hi_s:
                        raise ValueError("monotone multi-port enclosure collapsed inconsistently")
                    u_lo[k_port] = new_lo_i
                    u_lo[k_surf] = new_lo_s

                    # Coupled 2x2 super-solution block update with clamped +10^-30 outward-rounding slack.
                    base_hi = (
                        [(u_hi[m], w[0], w[1]) for m, w in port_net_neighbors[k_port]]
                        + [(tf, w[0], w[1]) for tf, w in fixed_neighbors[k_port]]
                    )

                    def _psi_min(ts, base_hi=base_hi, g_lo=g_lo, g_hi=g_hi):
                        return _solve_piecewise_linear_root(base_hi + [(ts, g_lo, g_hi)], maximize=False)

                    ts_b = _bisect_monotone_bound(
                        lambda ts: _f_s(min(old_hi_i, _psi_min(ts) + eps_round), ts, False),
                        new_lo_s,
                        old_hi_s,
                        find_leftmost_zero=False,
                        steps=100,
                    )
                    new_hi_s = min(old_hi_s, _ceil_fraction(ts_b))
                    new_hi_i = min(old_hi_i, _ceil_fraction(_psi_min(new_hi_s)))
                    if new_lo_i > new_hi_i or new_lo_s > new_hi_s:
                        raise ValueError("monotone multi-port enclosure collapsed inconsistently")
                    u_hi[k_port] = new_hi_i
                    u_hi[k_surf] = new_hi_s

                    delta = max(new_lo_i - old_lo_i, new_lo_s - old_lo_s, old_hi_i - new_hi_i, old_hi_s - new_hi_s)
                    if delta > max_delta:
                        max_delta = delta

                if max_delta <= tol:
                    converged = True
                    break
            termination_reason = "converged" if converged else "sweep_limit"

    # Independent mathematical certification of the final box [u_lo, u_hi]:
    # f_k^max(u_lo[k]; u_lo) <= 0 and f_k^min(u_hi[k]; u_hi) >= 0 for every k.
    for k in range(n_u):
        if u_lo[k] > u_hi[k]:
            raise ValueError("multi-port steady enclosure is inverted")
        if _eval_node_residual(u_lo[k], neighbors[k], fixed_neighbors[k], exteriors[k], u_lo, maximize=True) > 0:
            raise ValueError("multi-port steady lower-bound residual certification failed")
        if _eval_node_residual(u_hi[k], neighbors[k], fixed_neighbors[k], exteriors[k], u_hi, maximize=False) < 0:
            raise ValueError("multi-port steady upper-bound residual certification failed")

    return {uid: (u_lo[k], u_hi[k]) for k, uid in enumerate(unknown_ids)}, sweeps, termination_reason


def _exterior_outflow_box(t_lo, t_hi, ext):
    """Exact monotone enclosure of outward heat rate A * (h*(T - T_air) + eps*sigma*(T^4 - T_env^4))."""
    q_lo = _exterior_flux_per_area(t_lo, ext["env_k"], ext["eps"], ext["sigma"], ext["air_k"], ext["h"])
    q_hi = _exterior_flux_per_area(t_hi, ext["env_k"], ext["eps"], ext["sigma"], ext["air_k"], ext["h"])
    a_lo, a_hi = ext["area"]
    corners = [a * q for a in (a_lo, a_hi) for q in (q_lo, q_hi)]
    return Box.bounds(min(corners), max(corners))


def _intersect_boxes(boxes, label):
    lo = max(b.span()[0] for b in boxes)
    hi = min(b.span()[1] for b in boxes)
    if lo > hi:
        raise ValueError(f"{label} steady energy enclosures are inconsistent")
    return Box.bounds(lo, hi)


def solve_from_law(law, ports, *, duration_s=None, max_sweeps=120):
    """Compose and solve a multi-port steady thermal network over a validated pinned law."""
    if isinstance(max_sweeps, bool) or not isinstance(max_sweeps, int) or max_sweeps < 1:
        raise ValueError("max_sweeps must be a positive integer")
    provenance = validate_pinned_law(law)
    terminals = list(law["terminals"])
    parsed_ports, has_phase = _parse_port_specs(terminals, ports)

    duration = None
    if has_phase:
        if duration_s is None:
            raise ValueError("duration_s is required when one or more phase_bath ports are present")
        duration = decimal_input(duration_s, "duration")
    elif duration_s is not None:
        duration = decimal_input(duration_s, "duration")

    w_net = _symmetric_conductances(terminals, law)
    solved_u, sweeps, termination_reason = _solve_monotone_network(
        terminals, parsed_ports, w_net, max_sweeps=max_sweeps
    )

    # Assemble certified terminal temperatures as exact (lo, hi) Fraction pairs and Boxes.
    port_temp_spans = {}
    port_temps = {}
    for name in terminals:
        p = parsed_ports[name]
        if p["kind"] == "maintained":
            port_temp_spans[name] = (p["temp"], p["temp"])
            port_temps[name] = Box.exact(p["temp"])
        elif p["kind"] == "phase_bath":
            port_temp_spans[name] = (p["transition"], p["transition"])
            port_temps[name] = Box.exact(p["transition"])
        else:
            t_lo, t_hi = solved_u[f"port:{name}"]
            port_temp_spans[name] = (t_lo, t_hi)
            port_temps[name] = Box.bounds(t_lo, t_hi)

    # Compute port outflows, exterior splits, radial profiles, and global steady balance.
    port_outflow_spans = {}
    radial_profiles = {}
    exterior_splits = {}
    if termination_reason == "exact_linear":
        # Every conductance, area, temperature, and linear film flux is an exact rational.
        for name in terminals:
            t_i = port_temp_spans[name][0]
            q_net = Fraction(0)
            for other in terminals:
                if other == name:
                    continue
                w_val = w_net[(name, other)][0]
                q_net += w_val * (port_temp_spans[other][0] - t_i)
            p = parsed_ports[name]
            if p["kind"] == "radiating_surface":
                q_ext = p["area"][0] * _exterior_flux_per_area(
                    t_i, p["env_k"], p["eps"], p["sigma"], p["air_k"], p["h"]
                )
                if q_net != q_ext:
                    raise ValueError(f"port {name} steady energy enclosures are inconsistent")
                split = {"netHeatToEnclosureBoundsW": ["0", "0"]}
                if p["air_k"] is not None:
                    split["netHeatToAirBoundsW"] = [str(q_ext), str(q_ext)]
                exterior_splits[name] = split
            port_outflow_spans[name] = (q_net, q_net)
        bal_val = sum((port_outflow_spans[name][0] for name in terminals), Fraction(0))
        bal_lo = bal_hi = bal_val
        if bal_lo > 0 or bal_hi < 0:
            raise ValueError("multi-port steady global energy balance does not contain zero")
        global_balance_bounds = [str(bal_lo), str(bal_hi)]
    else:
        # Compute network-side outflow into each port: Q_{net -> i} = sum_{j != i} W_ij * (T_j - T_i).
        net_outflows = {}
        for name in terminals:
            q_net = ZERO
            for other in terminals:
                if other == name:
                    continue
                w_box = Box.bounds(*w_net[(name, other)])
                q_net = q_net + w_box * (port_temps[other] - port_temps[name])
            net_outflows[name] = q_net

        # Reconcile port outflows with exterior / radial-shell laws.
        port_outflows = {}
        for name in terminals:
            p = parsed_ports[name]
            if p["kind"] in ("maintained", "phase_bath"):
                port_outflows[name] = net_outflows[name]
            elif p["kind"] == "radiating_surface":
                t_lo, t_hi = port_temps[name].span()
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
                ts_lo, ts_hi = solved_u[f"surface:{name}"]
                ts_box = Box.bounds(ts_lo, ts_hi)
                g_shell_box = Box.bounds(*p["g_shell"])
                q_cond = g_shell_box * (port_temps[name] - ts_box)
                q_ext = _exterior_outflow_box(ts_lo, ts_hi, p)
                q_comb = _intersect_boxes([net_outflows[name], q_cond, q_ext], f"radial_shell {name}")
                port_outflows[name] = q_comb
                profile = p["shell"].surface_profile(port_temps[name], ZERO, q_comb)
                profile[-1]["temperatureBoundsK"] = [str(ts_lo), str(ts_hi)]
                radial_profiles[name] = profile
                area_box = Box.bounds(*p["area"])
                q_rad = area_box * p["eps"] * p["sigma"] * Box.bounds(ts_lo**4 - p["env_k"]**4, ts_hi**4 - p["env_k"]**4)
                split = {"netHeatToEnclosureBoundsW": bounds(q_rad)}
                if p["air_k"] is not None:
                    q_conv = area_box * p["h"] * Box.bounds(ts_lo - p["air_k"], ts_hi - p["air_k"])
                    split["netHeatToAirBoundsW"] = bounds(q_conv)
                exterior_splits[name] = split

        # Tighten each phase bath inflow via global energy conservation Q_b = -sum_{j != b} Q_j.
        for name in terminals:
            if parsed_ports[name]["kind"] == "phase_bath":
                others_sum = sum((port_outflows[o] for o in terminals if o != name), ZERO)
                port_outflows[name] = _intersect_boxes([port_outflows[name], -others_sum], f"phase_bath {name}")

        # Verify global steady energy balance contains 0.
        global_balance = sum((port_outflows[name] for name in terminals), ZERO)
        bal_lo, bal_hi = global_balance.span()
        if bal_lo > 0 or bal_hi < 0:
            raise ValueError("multi-port steady global energy balance does not contain zero")
        global_balance_bounds = bounds(global_balance)
        for name in terminals:
            port_outflow_spans[name] = port_outflows[name].span()

    max_temp_width = max((hi - lo for lo, hi in solved_u.values()), default=Fraction(0))
    max_heat_width = max(
        (port_outflow_spans[name][1] - port_outflow_spans[name][0] for name in terminals),
        default=Fraction(0),
    )

    # Multi-phase-bath plateau & earliest-exhaustion accounting.
    phase_ports = [name for name in terminals if parsed_ports[name]["kind"] == "phase_bath"]
    phase_details = {}
    phase_system = None
    if phase_ports:
        bath_meta = {}
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
                if termination_reason == "sweep_limit":
                    raise ValueError(
                        f"phase_bath {name!r} inflow straddles zero at solver sweep_limit "
                        f"(max_sweeps={max_sweeps}, maxTemperatureWidthK={max_temp_width}, "
                        f"maxHeatRateWidthW={max_heat_width}, bathInflowWidthW={q_hi - q_lo})"
                    )
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
            first_exhausted_ports = []
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
                # Ports whose individual exhaustion interval overlaps [first_lo, first_hi] (or <= first_hi).
                first_exhausted_ports = [
                    item[0] for item in active_exh if item[1] <= first_hi
                ]
            else:
                sys_status = "exhaustion_time_uncertain"
                mod_lo, mod_hi = first_lo, duration
                first_exhausted_ports = [
                    item[0] for item in active_exh if item[1] <= duration
                ]

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
                # Certified unique first-exhausted bath: exact event energy & zero remaining exhausted phase.
                mlo = mhi = solid if m["process"] == "melting" else -liquid
                stop_status = "exhausted"
                req_status = "exhausted"
            else:
                # Evaluate converted mass over the system modeled duration [mod_lo, mod_hi], clipped to inventory.
                def _clip(q, t):
                    return min(solid, max(-liquid, q * t / latent))
                conv_vals = [_clip(q, t) for q in (q_lo, q_hi) for t in (mod_lo, mod_hi)]
                mlo, mhi = min(conv_vals), max(conv_vals)
                if m["t_lo"] is None or mod_hi < m["t_lo"]:
                    stop_status = "coexisting"
                elif mod_lo >= m["t_hi"]:
                    stop_status = "exhausted"
                else:
                    stop_status = "exhaustion_time_uncertain"
                if sys_status == "coexisting":
                    req_status = "coexisting"
                elif sys_status == "exhausted" and name in first_exhausted_ports:
                    req_status = stop_status
                else:
                    req_status = "not_modeled_after_system_exhaustion"
            phase_details[name] = {
                "transitionTemperatureK": str(p["transition"]),
                "specificLatentHeatJPerKg": str(latent),
                "initialSolidKg": str(solid),
                "initialLiquidKg": str(liquid),
                "phaseProcess": m["process"],
                "plateauStatusAtModeledStop": stop_status,
                "statusAtRequestedDuration": req_status,
                "exhaustedAtStart": m["exhausted_at_start"],
                "exhaustedPhase": m["exh_phase"] if stop_status == "exhausted" else None,
                "exhaustionTimeBoundsS": None if m["t_lo"] is None else [str(m["t_lo"]), str(m["t_hi"])],
                "latentEnergyIntoBathBoundsJ": [str(mlo * latent), str(mhi * latent)],
                "remainingSolidBoundsKg": [str(solid - mhi), str(solid - mlo)],
                "remainingLiquidBoundsKg": [str(liquid + mlo), str(liquid + mhi)],
            }

        phase_system = {
            "phaseBathPorts": phase_ports,
            "requestedDurationS": str(duration),
            "plateauStatus": sys_status,
            "exhaustedAtStart": sys_exh_at_start,
            "postExhaustionModeled": False,
            "firstExhaustionTimeBoundsS": None if first_lo is None else [str(first_lo), str(first_hi)],
            "firstExhaustedCandidatePorts": first_exhausted_ports,
            "modeledDurationBoundsS": [str(mod_lo), str(mod_hi)],
        }

    # Build explicit per-port output records and active boundary conditions.
    source_ref_temps = {t: str(law["imposedTemperaturesK"][t]) for t in terminals}
    port_kinds = {t: parsed_ports[t]["kind"] for t in terminals}
    active_bcs = {}
    ports_out = {}

    for name in terminals:
        p = parsed_ports[name]
        kind = p["kind"]
        q_bounds = [str(port_outflow_spans[name][0]), str(port_outflow_spans[name][1])]
        t_bounds = [str(port_temp_spans[name][0]), str(port_temp_spans[name][1])]
        if kind == "maintained":
            active_bcs[name] = {
                "role": "maintained",
                "constraint": "fixed_dirichlet",
                "temperatureK": str(p["temp"]),
            }
            ports_out[name] = {
                "kind": "maintained",
                "temperatureBoundsK": t_bounds,
                "inflowFromNetworkBoundsW": q_bounds,
                "signConvention": "into_maintained_reservoir_positive",
            }
        elif kind == "phase_bath":
            active_bcs[name] = {
                "role": "phase_bath",
                "constraint": "clamped_during_coexistence",
                "temperatureK": str(p["transition"]),
            }
            ports_out[name] = {
                "kind": "phase_bath",
                "temperatureBoundsK": t_bounds,
                "bathInflowDuringPlateauBoundsW": q_bounds,
                "signConvention": "into_phase_bath_positive",
                **phase_details[name],
            }
        elif kind == "radiating_surface":
            active_bcs[name] = {
                "role": "radiating_surface",
                "constraint": "coupled_exterior_surface_balance",
                "temperatureBoundsK": t_bounds,
            }
            ports_out[name] = {
                "kind": "radiating_surface",
                "temperatureBoundsK": t_bounds,
                "outwardHeatRateBoundsW": q_bounds,
                "signConvention": "outward_from_surface_positive",
                "areaM2": str(p["area"][0]),
                "enclosureTemperatureK": str(p["env_k"]),
                "emissivity": str(p["eps"]),
                "sigmaWPerM2K4": str(p["sigma"]),
                "airTemperatureK": None if p["air_k"] is None else str(p["air_k"]),
                "convectionCoefficientWPerM2K": None if p["air_k"] is None else str(p["h"]),
                **exterior_splits[name],
            }
        else:  # radial_shell
            ts_lo, ts_hi = solved_u[f"surface:{name}"]
            shell = p["shell"]
            active_bcs[name] = {
                "role": "radial_shell",
                "constraint": "coupled_radial_shell_exterior_balance",
                "innerFaceTemperatureBoundsK": t_bounds,
                "outerFaceTemperatureBoundsK": [str(ts_lo), str(ts_hi)],
            }
            ports_out[name] = {
                "kind": "radial_shell",
                "innerFaceTemperatureBoundsK": t_bounds,
                "outerFaceTemperatureBoundsK": [str(ts_lo), str(ts_hi)],
                "outwardHeatRateBoundsW": q_bounds,
                "signConvention": "outward_from_radial_surface_positive",
                "geometry": "sphere" if shell.length is None else "cylinder",
                "cylinderLengthM": None if shell.length is None else str(shell.length),
                "layers": shell.material,
                "surfaces": radial_profiles[name],
                "exposedAreaBoundsM2": bounds(shell.outer_area()),
                "enclosureTemperatureK": str(p["env_k"]),
                "emissivity": str(p["eps"]),
                "sigmaWPerM2K4": str(p["sigma"]),
                "airTemperatureK": None if p["air_k"] is None else str(p["air_k"]),
                "convectionCoefficientWPerM2K": None if p["air_k"] is None else str(p["h"]),
                **exterior_splits[name],
            }

    return {
        "schema": MULTIPORT_SCHEMA,
        "evidence": {
            "category": EVIDENCE_CATEGORY,
            "sourceIdentity": {k: provenance[k] for k in SOURCE_HASH_KEYS},
            **{k: False for k in OFFLINE_FLAG_KEYS},
        },
        "network": {
            "terminals": terminals,
            "portKinds": port_kinds,
            "sourceLawReferenceTemperaturesK": source_ref_temps,
            "activeBoundaryConditions": active_bcs,
        },
        "ports": ports_out,
        "systemEnergyBalanceBoundsW": global_balance_bounds,
        "phaseSystem": phase_system,
        "solverMetadata": {
            "method": "exact_rational_monotone_sub_super_solution_gauss_seidel",
            "sweeps": sweeps,
            "terminationReason": termination_reason,
            "maxTemperatureWidthK": str(max_temp_width),
            "maxHeatRateWidthW": str(max_heat_width),
            "residualCertified": True,
        },
        **provenance,
    }


def investigate(inputs, ports, *, duration_s=None, max_sweeps=120):
    """Resolve a pinned file-backed source tuple/PinnedSourceRef and solve the multi-port system."""
    if isinstance(inputs, PinnedSourceRef):
        law = inputs.resolve_law()
    else:
        law = terminal_response(*inputs)
    return solve_from_law(law, ports, duration_s=duration_s, max_sweeps=max_sweeps)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="Path to JSON multi-port network request")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
    _expect_exact_keys(
        payload,
        required=("source", "ports"),
        optional=("durationS", "maxSweeps"),
        label="request",
    )
    src = payload["source"]
    sweeps = payload.get("maxSweeps", 120)
    if isinstance(src, dict) and "studyPath" in src:
        _expect_exact_keys(
            src,
            required=("studyPath", "rootPath", "factsPath", "factsSha256"),
            label="request.source",
        )
        ref = PinnedSourceRef(src["studyPath"], src["rootPath"], src["factsPath"], src["factsSha256"])
        result = investigate(ref, payload["ports"], duration_s=payload.get("durationS"), max_sweeps=sweeps)
    else:
        result = solve_from_law(src, payload["ports"], duration_s=payload.get("durationS"), max_sweeps=sweeps)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
