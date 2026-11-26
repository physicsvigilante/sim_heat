"""Certified quasi-steady Stefan freezing & melting front solver (M06).

Composes a growing or melting quasi-steady phase-change layer (``planar``, ``cylinder``, or
``sphere``) at one terminal of any validated connected passive steady conduction network
(``DerivedLaw``, pinned H1 law, or Schur-joined network) with maintained reservoirs on all
other terminals, plus optional uniform rod heat generation Norton injection at the Stefan port.

Explicitly models the quasi-steady conduction limit (neglecting sensible heat storage inside
the growing solid layer; exact in the limit Stefan number Ste = c_s*|T_tr - T_eq|/L -> 0) and
reports certified Stefan-number bounds whenever ``solidSpecificHeatJPerKgK`` is supplied.

All enclosures use exact rational arithmetic, certified integer ``isqrt`` square roots,
``pi_rational_enclosure``, and ``radial_log``.
"""
from __future__ import annotations

from fractions import Fraction
import math
from typing import Any

from simheat.core import Box, ZERO, pi_rational_enclosure
from simheat.laws import validate_terminal_law
from tools.join_thermal_networks import bounds
from tools.offline_investigation import _expect_exact_keys
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS
from tools.radiating_surface import decimal_input, physical_port
from tools.spherical_conduction import radial_log

STEFAN_SCHEMA = "sim_heat.offline_stefan_layer/1"
EVIDENCE_CATEGORY = "offline_analytical_calculation"
VALID_GEOMETRIES = ("planar", "cylinder", "sphere")

_SQRT_SCALE = 10**40


def _box_union(boxes: list[Box]) -> Box:
    return Box.bounds(min(b.span()[0] for b in boxes), max(b.span()[1] for b in boxes))


def _sqrt_exact_rational(val: Fraction) -> Box:
    """Certified exact outward rational enclosure of sqrt(val) for val >= 0 using integer isqrt."""
    if val < 0:
        raise ValueError(f"cannot take square root of negative rational {val}")
    if val == 0:
        return ZERO
    n = val.numerator
    d = val.denominator
    s2 = _SQRT_SCALE * _SQRT_SCALE
    m = math.isqrt((n * s2) // d)
    # Exact integer verification of m^2 * d <= n * s^2 <= (m+1)^2 * d.
    while (m + 1) * (m + 1) * d <= n * s2:
        m += 1
    while m * m * d > n * s2:
        m -= 1
    lo = Fraction(m, _SQRT_SCALE)
    if m * m * d == n * s2:
        return Box.exact(lo)
    hi = Fraction(m + 1, _SQRT_SCALE)
    return Box.bounds(lo, hi)


def _planar_eval_corner(
    *,
    t_eq: Fraction,
    r_ext: Fraction,
    t_tr: Fraction,
    rho: Fraction,
    latent: Fraction,
    k_layer: Fraction,
    area: Fraction,
    s0: Fraction,
    s_max: Fraction | None,
    duration: Fraction,
) -> dict[str, Any]:
    """Evaluate certified planar Stefan state at one fixed monotone corner."""
    b = k_layer * area * r_ext
    if t_eq < t_tr:
        dt_drive = t_tr - t_eq
        if s_max is not None and s0 >= s_max:
            return {
                "stage": "completely_frozen",
                "t_done": ZERO,
                "coord": Box.exact(s0),
            }
        # Time to reach s_max if capped:
        t_done: Box | None = None
        if s_max is not None:
            t_done_val = (rho * latent * area / dt_drive) * (
                (s_max * s_max - s0 * s0) / (2 * k_layer * area) + r_ext * (s_max - s0)
            )
            t_done = Box.exact(t_done_val)
            if duration >= t_done_val:
                return {"stage": "completely_frozen", "t_done": t_done, "coord": Box.exact(s_max)}
        rad = (s0 + b) * (s0 + b) + (2 * k_layer * dt_drive / (rho * latent)) * duration
        s_box = _sqrt_exact_rational(rad) - b
        lo, hi = s_box.span()
        lo = max(s0, lo)
        if s_max is not None:
            hi = min(s_max, hi)
            lo = min(lo, hi)
        return {"stage": "growing", "t_done": t_done, "coord": Box.bounds(lo, hi)}

    # Melting (t_eq > t_tr)
    dt_drive = t_eq - t_tr
    if s0 == 0:
        return {"stage": "completely_melted", "t_done": ZERO, "coord": ZERO}
    t_melt_val = (rho * latent * area / dt_drive) * (
        (s0 * s0) / (2 * k_layer * area) + r_ext * s0
    )
    t_done = Box.exact(t_melt_val)
    if duration >= t_melt_val:
        return {"stage": "completely_melted", "t_done": t_done, "coord": ZERO}
    rad = (s0 + b) * (s0 + b) - (2 * k_layer * dt_drive / (rho * latent)) * duration
    if rad <= b * b:
        return {"stage": "completely_melted", "t_done": t_done, "coord": ZERO}
    s_box = _sqrt_exact_rational(rad) - b
    lo, hi = s_box.span()
    lo = max(Fraction(0), lo)
    hi = min(s0, max(lo, hi))
    return {"stage": "melting", "t_done": t_done, "coord": Box.bounds(lo, hi)}


def _cyl_F_box(r: Fraction, r0: Fraction, length: Fraction, r_ext: Fraction, k_layer: Fraction, pi_box: Box) -> Box:
    """Exact integral F_cyl(r) = int_{r0}^{r} 2*pi*u*L*(R_ext + ln(u/r0)/(2*pi*k*L)) du for r >= r0."""
    if r == r0:
        return ZERO
    r2_diff = r * r - r0 * r0
    term_ext = pi_box * (length * r_ext * r2_diff)
    ln_box = radial_log(r / r0)
    term_ice = (Box.exact(r * r) * ln_box - Box.exact(r2_diff / 2)) / (2 * k_layer)
    return term_ext + term_ice


def _sph_F_box(r: Fraction, r0: Fraction, r_ext: Fraction, k_layer: Fraction, pi_box: Box) -> Box:
    """Exact integral F_sph(r) = int_{r0}^{r} 4*pi*u^2*(R_ext + 1/(4*pi*k*r0) - 1/(4*pi*k*u)) du."""
    if r == r0:
        return ZERO
    r3_diff = r**3 - r0**3
    r2_diff = r * r - r0 * r0
    term_ext = (pi_box * Fraction(4, 3) * r_ext + Box.exact(Fraction(1, 3) / (k_layer * r0))) * r3_diff
    term_inv = Box.exact(r2_diff / (2 * k_layer))
    return term_ext - term_inv


def _invert_lower(
    f_eval,
    target_lo: Fraction,
    r_lo: Fraction,
    r_hi: Fraction,
    *,
    tol: Fraction = Fraction(1, 10**26),
) -> Fraction:
    """Largest r in [r_lo, r_hi] with f_eval(r).hi <= target_lo."""
    a_l, b_l = r_lo, r_hi
    for _ in range(120):
        if b_l - a_l <= tol:
            break
        mid = (a_l + b_l) / 2
        if f_eval(mid).span()[1] <= target_lo:
            a_l = mid
        else:
            b_l = mid
    return a_l


def _invert_upper(
    f_eval,
    target_hi: Fraction,
    r_lo: Fraction,
    r_hi: Fraction,
    *,
    tol: Fraction = Fraction(1, 10**26),
) -> Fraction:
    """Smallest r in [r_lo, r_hi] with f_eval(r).lo >= target_hi."""
    a_r, b_r = r_lo, r_hi
    for _ in range(120):
        if b_r - a_r <= tol:
            break
        mid = (a_r + b_r) / 2
        if f_eval(mid).span()[0] >= target_hi:
            b_r = mid
        else:
            a_r = mid
    return b_r


def _invert_monotone_F(
    f_eval,
    target: Box,
    r_lo: Fraction,
    r_hi: Fraction,
    *,
    tol: Fraction = Fraction(1, 10**26),
) -> Box:
    """Certified outward bisection inverting strictly increasing interval function f_eval(r) ni target."""
    t_lo, t_hi = target.span()
    a_l = _invert_lower(f_eval, t_lo, r_lo, r_hi, tol=tol)
    b_r = _invert_upper(f_eval, t_hi, a_l, r_hi, tol=tol)
    return Box.bounds(a_l, b_r)


def _radial_eval_corner(
    *,
    geom_kind: str,
    t_eq: Fraction,
    r_ext: Fraction,
    t_tr: Fraction,
    rho: Fraction,
    latent: Fraction,
    k_layer: Fraction,
    r0: Fraction,
    r_init: Fraction,
    r_max: Fraction | None,
    cyl_length: Fraction | None,
    duration: Fraction,
    pi_box: Box,
) -> dict[str, Any]:
    """Evaluate certified cylindrical or spherical radial Stefan state at one monotone corner."""
    if geom_kind == "cylinder":
        assert cyl_length is not None
        f_of = lambda r: _cyl_F_box(r, r0, cyl_length, r_ext, k_layer, pi_box)
    else:
        f_of = lambda r: _sph_F_box(r, r0, r_ext, k_layer, pi_box)

    f_init = f_of(r_init)

    if t_eq < t_tr:
        dt_drive = t_tr - t_eq
        if r_max is not None and r_init >= r_max:
            return {"stage": "completely_frozen", "t_done": ZERO, "coord": Box.exact(r_init)}
        t_done: Box | None = None
        if r_max is not None:
            f_max = f_of(r_max)
            t_done = (f_max - f_init) * (rho * latent / dt_drive)
            if duration >= t_done.span()[1]:
                return {"stage": "completely_frozen", "t_done": t_done, "coord": Box.exact(r_max)}
        rhs = f_init + Box.exact((dt_drive / (rho * latent)) * duration)
        # Bracket upper radius r_hi such that f_of(r_hi).lo >= rhs.hi.
        if r_max is not None:
            r_hi = r_max
            if f_of(r_hi).span()[0] < rhs.span()[1]:
                # Straddles r_max completion boundary across pi/log interval width.
                a_l = _invert_lower(f_of, rhs.span()[0], r_init, r_max)
                return {"stage": "stage_boundary_uncertain", "t_done": t_done, "coord": Box.bounds(a_l, r_max)}
        else:
            r_hi = max(r_init * 2, r0 + Fraction(1, 10))
            while f_of(r_hi).span()[0] < rhs.span()[1]:
                r_hi = r_hi * 2
        r_box = _invert_monotone_F(f_of, rhs, r_init, r_hi)
        if t_done is not None and duration >= t_done.span()[0]:
            return {"stage": "stage_boundary_uncertain", "t_done": t_done, "coord": Box.bounds(r_box.span()[0], r_max)}
        return {"stage": "growing", "t_done": t_done, "coord": r_box}

    # Melting (t_eq > t_tr)
    dt_drive = t_eq - t_tr
    if r_init == r0:
        return {"stage": "completely_melted", "t_done": ZERO, "coord": Box.exact(r0)}
    t_done = f_init * (rho * latent / dt_drive)
    if duration >= t_done.span()[1]:
        return {"stage": "completely_melted", "t_done": t_done, "coord": Box.exact(r0)}
    rhs = f_init - Box.exact((dt_drive / (rho * latent)) * duration)
    if rhs.span()[1] <= 0:
        return {"stage": "completely_melted", "t_done": t_done, "coord": Box.exact(r0)}
    if rhs.span()[0] <= 0:
        b_r = _invert_upper(f_of, rhs.span()[1], r0, r_init)
        return {"stage": "stage_boundary_uncertain", "t_done": t_done, "coord": Box.bounds(r0, b_r)}
    r_box = _invert_monotone_F(f_of, rhs, r0, r_init)
    if duration >= t_done.span()[0]:
        return {"stage": "stage_boundary_uncertain", "t_done": t_done, "coord": Box.bounds(r0, r_box.span()[1])}
    return {"stage": "melting", "t_done": t_done, "coord": r_box}


def parse_stefan_spec(spec: dict[str, Any], label: str) -> dict[str, Any]:
    """Validate and parse a ``stefan_layer`` attachment specification."""
    if not isinstance(spec, dict):
        raise ValueError(f"{label} must be a mapping")
    _expect_exact_keys(
        spec,
        required=(
            "kind",
            "geometry",
            "transitionTemperatureK",
            "densityKgPerM3",
            "specificLatentHeatJPerKg",
            "layerConductivityWPerMK",
        ),
        optional=("solidSpecificHeatJPerKgK", "externalFilmCoefficientWPerM2K"),
        label=label,
    )
    if spec["kind"] != "stefan_layer":
        raise ValueError(f"{label}.kind must be 'stefan_layer'")

    t_tr = decimal_input(spec["transitionTemperatureK"], f"{label}.transitionTemperatureK")
    rho = decimal_input(spec["densityKgPerM3"], f"{label}.densityKgPerM3")
    latent = decimal_input(spec["specificLatentHeatJPerKg"], f"{label}.specificLatentHeatJPerKg")
    k_val = decimal_input(spec["layerConductivityWPerMK"], f"{label}.layerConductivityWPerMK")
    if min(t_tr, rho, latent, k_val) <= 0:
        raise ValueError(f"{label} requires positive transitionTemperatureK, densityKgPerM3, specificLatentHeatJPerKg, and layerConductivityWPerMK")

    c_s = None
    if "solidSpecificHeatJPerKgK" in spec:
        c_s = decimal_input(spec["solidSpecificHeatJPerKgK"], f"{label}.solidSpecificHeatJPerKgK")
        if c_s <= 0:
            raise ValueError(f"{label}.solidSpecificHeatJPerKgK must be positive")
    h_film = None
    if "externalFilmCoefficientWPerM2K" in spec:
        h_film = decimal_input(spec["externalFilmCoefficientWPerM2K"], f"{label}.externalFilmCoefficientWPerM2K")
        if h_film <= 0:
            raise ValueError(f"{label}.externalFilmCoefficientWPerM2K must be positive")

    geom = spec["geometry"]
    if not isinstance(geom, dict):
        raise ValueError(f"{label}.geometry must be a mapping")
    g_kind = geom.get("kind")
    if g_kind not in VALID_GEOMETRIES:
        raise ValueError(f"{label}.geometry.kind must be one of {VALID_GEOMETRIES}, got {g_kind!r}")

    if g_kind == "planar":
        _expect_exact_keys(
            geom,
            required=("kind", "areaM2", "initialThicknessM"),
            optional=("maxThicknessM",),
            label=f"{label}.geometry",
        )
        area = decimal_input(geom["areaM2"], f"{label}.geometry.areaM2")
        s0 = decimal_input(geom["initialThicknessM"], f"{label}.geometry.initialThicknessM")
        if area <= 0:
            raise ValueError(f"{label}.geometry.areaM2 must be positive")
        s_max = None
        if "maxThicknessM" in geom:
            s_max = decimal_input(geom["maxThicknessM"], f"{label}.geometry.maxThicknessM")
            if s_max <= 0 or s_max < s0:
                raise ValueError(f"{label}.geometry.maxThicknessM must be positive and >= initialThicknessM")
        norm_geom = {"kind": "planar", "area": area, "s0": s0, "s_max": s_max}
    elif g_kind == "cylinder":
        _expect_exact_keys(
            geom,
            required=("kind", "coreRadiusM", "initialOuterRadiusM", "cylinderLengthM"),
            optional=("maxOuterRadiusM",),
            label=f"{label}.geometry",
        )
        r0 = decimal_input(geom["coreRadiusM"], f"{label}.geometry.coreRadiusM")
        r_init = decimal_input(geom["initialOuterRadiusM"], f"{label}.geometry.initialOuterRadiusM")
        cyl_len = decimal_input(geom["cylinderLengthM"], f"{label}.geometry.cylinderLengthM")
        if r0 <= 0 or cyl_len <= 0 or r_init < r0:
            raise ValueError(f"{label}.geometry requires positive coreRadiusM, cylinderLengthM, and initialOuterRadiusM >= coreRadiusM")
        r_max = None
        if "maxOuterRadiusM" in geom:
            r_max = decimal_input(geom["maxOuterRadiusM"], f"{label}.geometry.maxOuterRadiusM")
            if r_max < r_init:
                raise ValueError(f"{label}.geometry.maxOuterRadiusM must be >= initialOuterRadiusM")
        norm_geom = {"kind": "cylinder", "r0": r0, "r_init": r_init, "length": cyl_len, "r_max": r_max}
    else:  # sphere
        _expect_exact_keys(
            geom,
            required=("kind", "coreRadiusM", "initialOuterRadiusM"),
            optional=("maxOuterRadiusM",),
            label=f"{label}.geometry",
        )
        r0 = decimal_input(geom["coreRadiusM"], f"{label}.geometry.coreRadiusM")
        r_init = decimal_input(geom["initialOuterRadiusM"], f"{label}.geometry.initialOuterRadiusM")
        if r0 <= 0 or r_init < r0:
            raise ValueError(f"{label}.geometry requires positive coreRadiusM and initialOuterRadiusM >= coreRadiusM")
        r_max = None
        if "maxOuterRadiusM" in geom:
            r_max = decimal_input(geom["maxOuterRadiusM"], f"{label}.geometry.maxOuterRadiusM")
            if r_max < r_init:
                raise ValueError(f"{label}.geometry.maxOuterRadiusM must be >= initialOuterRadiusM")
        norm_geom = {"kind": "sphere", "r0": r0, "r_init": r_init, "r_max": r_max}

    return {
        "kind": "stefan_layer",
        "geometry": norm_geom,
        "t_tr": t_tr,
        "rho": rho,
        "latent": latent,
        "k_layer": k_val,
        "c_s": c_s,
        "h_film": h_film,
    }


def solve_stefan_from_law(
    law: Any,
    port: str,
    stefan_spec: dict[str, Any],
    duration_s: str,
    *,
    maintained_temperatures_k: dict[str, str],
    port_norton_injection_w: tuple[Fraction, Fraction] | None = None,
) -> dict[str, Any]:
    """Solve certified quasi-steady Stefan freezing/melting on a validated terminal network."""
    resolved_law, provenance = validate_terminal_law(law)
    engine_law = resolved_law.to_engine_law()
    terminals = list(engine_law["terminals"])
    if port not in terminals:
        raise ValueError(f"stefan port {port!r} is not in network terminals {terminals}")
    other_ports = [t for t in terminals if t != port]
    if not isinstance(maintained_temperatures_k, dict) or set(maintained_temperatures_k) != set(other_ports):
        raise ValueError("maintained_temperatures_k must specify every terminal except the stefan port")

    maintained: dict[str, str] = {}
    for t in other_ports:
        maintained[t] = str(decimal_input(maintained_temperatures_k[t], f"maintained temperature at {t}"))

    parsed = parse_stefan_spec(stefan_spec, f"attachments[{port}]")
    duration = decimal_input(duration_s, "duration")
    geom = parsed["geometry"]
    g_kind = geom["kind"]
    t_tr = parsed["t_tr"]
    rho = parsed["rho"]
    latent = parsed["latent"]
    k_layer = parsed["k_layer"]
    h_film = parsed["h_film"]

    effective_imposed = {port: str(t_tr), **maintained}
    (eq_lo, eq_hi), (r_port_lo, r_port_hi) = physical_port({**engine_law, "imposedTemperaturesK": effective_imposed}, port)

    # Shift Thevenin equilibrium temperature by optional certified Norton rod-generation injection at port.
    if port_norton_injection_w is not None:
        inj_lo, inj_hi = port_norton_injection_w
        if inj_lo < 0 or inj_lo > inj_hi:
            raise ValueError("port_norton_injection_w must be a valid nonnegative interval")
        eq_lo = eq_lo + r_port_lo * inj_lo
        eq_hi = eq_hi + r_port_hi * inj_hi

    pi_box = Box.bounds(*pi_rational_enclosure())
    if h_film is None:
        r_film = ZERO
    elif g_kind == "planar":
        r_film = Box.exact(Fraction(1) / (h_film * geom["area"]))
    elif g_kind == "cylinder":
        r_film = Box.exact(Fraction(1)) / (pi_box * (2 * geom["r0"] * geom["length"] * h_film))
    else:
        r_film = Box.exact(Fraction(1)) / (pi_box * (4 * geom["r0"] * geom["r0"] * h_film))

    r_ext_lo = r_port_lo + r_film.span()[0]
    r_ext_hi = r_port_hi + r_film.span()[1]

    # Compute optional Stefan-number diagnostic bounds.
    stefan_num_bounds = None
    if parsed["c_s"] is not None:
        dt_box = Box.bounds(eq_lo, eq_hi) - t_tr
        dlo, dhi = dt_box.span()
        abs_lo = Fraction(0) if dlo <= 0 <= dhi else min(abs(dlo), abs(dhi))
        abs_hi = max(abs(dlo), abs(dhi))
        ste_box = Box.bounds(abs_lo, abs_hi) * (parsed["c_s"] / latent)
        stefan_num_bounds = bounds(ste_box)

    source_identity = (
        {k: provenance[k] for k in SOURCE_HASH_KEYS}
        if all(k in provenance for k in SOURCE_HASH_KEYS)
        else {
            "derivedLawSchema": provenance["derivedLawSchema"],
            "derivedLawSha256": provenance["derivedLawSha256"],
            "derivedLawLineage": provenance["derivedLawLineage"],
        }
    )

    def _volume_box(coord_box: Box) -> Box:
        c_lo, c_hi = coord_box.span()
        if g_kind == "planar":
            return Box.bounds(c_lo, c_hi) * geom["area"]
        if g_kind == "cylinder":
            r0 = geom["r0"]
            return pi_box * geom["length"] * Box.bounds(c_lo * c_lo - r0 * r0, c_hi * c_hi - r0 * r0)
        r0 = geom["r0"]
        return pi_box * Fraction(4, 3) * Box.bounds(c_lo**3 - r0**3, c_hi**3 - r0**3)

    init_coord = geom["s0"] if g_kind == "planar" else geom["r_init"]
    init_vol = _volume_box(Box.exact(init_coord))

    # Determine growth/melting direction and evaluate certified monotone corners.
    if eq_lo == eq_hi == t_tr or duration == 0:
        regime = (
            "equilibrium"
            if eq_lo == eq_hi == t_tr
            else ("freezing" if eq_hi < t_tr else ("melting" if eq_lo > t_tr else "unresolved"))
        )
        status = "equilibrium" if eq_lo == eq_hi == t_tr else "resolved"
        term_reason = "resolved"
        final_coord = Box.exact(init_coord)
        t_done_box = None
        mod_bounds = [str(duration), str(duration)]
    elif eq_hi < t_tr:
        regime = "freezing"
        if g_kind == "planar":
            c_slow = _planar_eval_corner(
                t_eq=eq_hi, r_ext=r_ext_hi, t_tr=t_tr, rho=rho, latent=latent,
                k_layer=k_layer, area=geom["area"], s0=geom["s0"], s_max=geom["s_max"], duration=duration,
            )
            c_fast = _planar_eval_corner(
                t_eq=eq_lo, r_ext=r_ext_lo, t_tr=t_tr, rho=rho, latent=latent,
                k_layer=k_layer, area=geom["area"], s0=geom["s0"], s_max=geom["s_max"], duration=duration,
            )
        else:
            c_slow = _radial_eval_corner(
                geom_kind=g_kind, t_eq=eq_hi, r_ext=r_ext_hi, t_tr=t_tr, rho=rho, latent=latent,
                k_layer=k_layer, r0=geom["r0"], r_init=geom["r_init"], r_max=geom["r_max"],
                cyl_length=geom.get("length"), duration=duration, pi_box=pi_box,
            )
            c_fast = _radial_eval_corner(
                geom_kind=g_kind, t_eq=eq_lo, r_ext=r_ext_lo, t_tr=t_tr, rho=rho, latent=latent,
                k_layer=k_layer, r0=geom["r0"], r_init=geom["r_init"], r_max=geom["r_max"],
                cyl_length=geom.get("length"), duration=duration, pi_box=pi_box,
            )
        status = c_slow["stage"] if c_slow["stage"] == c_fast["stage"] else "mode_sequence_uncertain"
        if status == "stage_boundary_uncertain":
            status = "mode_sequence_uncertain"
        term_reason = "mode_sequence_uncertain" if status == "mode_sequence_uncertain" else "resolved"
        final_coord = _box_union([c_slow["coord"], c_fast["coord"]])
        t_done_box = None if c_slow["t_done"] is None else _box_union([c_slow["t_done"], c_fast["t_done"]])
        if status == "completely_frozen" and t_done_box is not None:
            td_lo, td_hi = t_done_box.span()
            mod_bounds = [str(min(duration, td_lo)), str(min(duration, td_hi))]
        elif status == "mode_sequence_uncertain" and t_done_box is not None:
            mod_bounds = [str(min(duration, t_done_box.span()[0])), str(duration)]
        else:
            mod_bounds = [str(duration), str(duration)]
    elif eq_lo > t_tr:
        regime = "melting"
        if g_kind == "planar":
            c_slow = _planar_eval_corner(
                t_eq=eq_lo, r_ext=r_ext_hi, t_tr=t_tr, rho=rho, latent=latent,
                k_layer=k_layer, area=geom["area"], s0=geom["s0"], s_max=geom["s_max"], duration=duration,
            )
            c_fast = _planar_eval_corner(
                t_eq=eq_hi, r_ext=r_ext_lo, t_tr=t_tr, rho=rho, latent=latent,
                k_layer=k_layer, area=geom["area"], s0=geom["s0"], s_max=geom["s_max"], duration=duration,
            )
        else:
            c_slow = _radial_eval_corner(
                geom_kind=g_kind, t_eq=eq_lo, r_ext=r_ext_hi, t_tr=t_tr, rho=rho, latent=latent,
                k_layer=k_layer, r0=geom["r0"], r_init=geom["r_init"], r_max=geom["r_max"],
                cyl_length=geom.get("length"), duration=duration, pi_box=pi_box,
            )
            c_fast = _radial_eval_corner(
                geom_kind=g_kind, t_eq=eq_hi, r_ext=r_ext_lo, t_tr=t_tr, rho=rho, latent=latent,
                k_layer=k_layer, r0=geom["r0"], r_init=geom["r_init"], r_max=geom["r_max"],
                cyl_length=geom.get("length"), duration=duration, pi_box=pi_box,
            )
        status = c_slow["stage"] if c_slow["stage"] == c_fast["stage"] else "mode_sequence_uncertain"
        if status == "stage_boundary_uncertain":
            status = "mode_sequence_uncertain"
        term_reason = "mode_sequence_uncertain" if status == "mode_sequence_uncertain" else "resolved"
        final_coord = _box_union([c_slow["coord"], c_fast["coord"]])
        t_done_box = None if c_slow["t_done"] is None else _box_union([c_slow["t_done"], c_fast["t_done"]])
        if status == "completely_melted" and t_done_box is not None:
            td_lo, td_hi = t_done_box.span()
            mod_bounds = [str(min(duration, td_lo)), str(min(duration, td_hi))]
        elif status == "mode_sequence_uncertain" and t_done_box is not None:
            mod_bounds = [str(min(duration, t_done_box.span()[0])), str(duration)]
        else:
            mod_bounds = [str(duration), str(duration)]
    else:
        # Unresolved direction across T_eq enclosure (straddles T_tr): stop honestly at t = 0.
        regime = "unresolved"
        status = "mode_sequence_uncertain"
        term_reason = "mode_sequence_uncertain"
        final_coord = Box.exact(init_coord)
        t_done_box = None
        mod_bounds = ["0", "0"]

    final_vol = _volume_box(final_coord)
    final_mass = final_vol * rho
    delta_mass = (final_vol - init_vol) * rho
    # Positive INTO layer means melting (+), freezing releases latent heat (-).
    latent_energy_into_layer = -delta_mass * latent

    # Final exposed-face temperature at port p (T_port = T_eq + (T_tr - T_eq) * R_port / R_tot)
    # when growing/melting; clamped at T_eq if completely frozen/melted or T_tr at equilibrium.
    if g_kind == "planar":
        r_ice_final = final_coord / (k_layer * geom["area"])
    elif g_kind == "cylinder":
        c_lo, c_hi = final_coord.span()
        ln_lo = ZERO if c_lo == geom["r0"] else radial_log(c_lo / geom["r0"])
        ln_hi = ZERO if c_hi == geom["r0"] else radial_log(c_hi / geom["r0"])
        r_ice_final = Box.bounds(ln_lo.span()[0], ln_hi.span()[1]) / (pi_box * (2 * k_layer * geom["length"]))
    else:
        c_lo, c_hi = final_coord.span()
        inv_box = Box.bounds(Fraction(1) / geom["r0"] - Fraction(1) / c_lo, Fraction(1) / geom["r0"] - Fraction(1) / c_hi)
        r_ice_final = inv_box / (pi_box * (4 * k_layer))

    r_tot_final = Box.bounds(r_ext_lo, r_ext_hi) + r_ice_final
    eq_box = Box.bounds(eq_lo, eq_hi)
    q_final = (Box.exact(t_tr) - eq_box) / r_tot_final  # positive OUT of freezing front toward cold sink
    t_port_final = eq_box + Box.bounds(r_port_lo, r_port_hi) * q_final
    # Intersect port temperature with hull of [min(T_eq, T_tr), max(T_eq, T_tr)].
    tp_lo = max(min(eq_lo, t_tr), t_port_final.span()[0])
    tp_hi = min(max(eq_hi, t_tr), t_port_final.span()[1])
    t_port_final = Box.bounds(tp_lo, tp_hi) if tp_lo <= tp_hi else t_port_final

    coord_key = "finalThicknessBoundsM" if g_kind == "planar" else "finalOuterRadiusBoundsM"
    init_key = "initialThicknessM" if g_kind == "planar" else "initialOuterRadiusM"
    final_thickness = final_coord if g_kind == "planar" else (final_coord - geom["r0"])

    return {
        "schema": STEFAN_SCHEMA,
        "evidence": {
            "category": EVIDENCE_CATEGORY,
            "sourceIdentity": source_identity,
            **{k: False for k in OFFLINE_FLAG_KEYS},
        },
        "network": {
            "terminals": terminals,
            "stefanPort": port,
            "maintainedReservoirTemperaturesK": maintained,
        },
        "assumptions": {
            "quasiSteadyConduction": True,
            "sensibleStorageInGrowingLayerNeglected": True,
            "stefanNumberBounds": stefan_num_bounds,
        },
        "portEquivalent": {
            "equilibriumTemperatureBoundsK": [str(eq_lo), str(eq_hi)],
            "portResistanceBoundsKPerW": [str(r_port_lo), str(r_port_hi)],
            "externalResistanceBoundsKPerW": [str(r_ext_lo), str(r_ext_hi)],
        },
        "stefan": {
            "geometry": g_kind,
            "regime": regime,
            "status": status,
            "postCompletionModeled": False,
            "requestedDurationS": str(duration),
            "modeledDurationBoundsS": mod_bounds,
            init_key: str(init_coord),
            coord_key: bounds(final_coord),
            "finalSolidThicknessBoundsM": bounds(final_thickness),
            "finalSolidMassBoundsKg": bounds(final_mass),
            "solidMassChangeBoundsKg": bounds(delta_mass),
            "latentEnergyIntoLayerBoundsJ": bounds(latent_energy_into_layer),
            "energySignConvention": "into_layer_positive",
            "completionTimeBoundsS": None if t_done_box is None else bounds(t_done_box),
            "finalPortTemperatureBoundsK": bounds(t_port_final),
            "finalHeatExtractionRateBoundsW": bounds(q_final),
        },
        "solverMetadata": {
            "terminationReason": term_reason,
            "finalThicknessWidthM": str(final_thickness.span()[1] - final_thickness.span()[0]),
            "modeledDurationWidthS": str(Fraction(mod_bounds[1]) - Fraction(mod_bounds[0])),
        },
        **provenance,
    }
