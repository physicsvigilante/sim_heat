"""Infer an unknown radial insulation layer's conductivity from timed melting or freezing."""
import argparse
from fractions import Fraction as F
import json

from qualification.h1_n4.static_physical import pi_rational_enclosure
from qualification.h1_n13.conduction import ZERO, Box, interval
from tools.join_thermal_networks import bounds
from tools.latent_heat_bath import phase_inputs, reservoir_inflows
from tools.offline_provenance import offline_provenance
from tools.phase_film_calibration import intersect_boxes, signed_decimal
from tools.radiating_surface import decimal_input, physical_port
from tools.spherical_conduction import radial_log
from tools.terminal_response import investigate as terminal_response


def invert_exterior_flux(flux, air, h, env, eps, sigma):
    """Bracket the unique nonnegative Kelvin surface temperature for a given outward flux."""
    if h == 0 and eps == 0:
        raise ValueError("nonzero exterior heat exchange coefficient or emissivity required")
    min_flux = -h * air - eps * sigma * (env**4)
    if flux < min_flux:
        raise ValueError("implied outer surface temperature must be nonnegative in Kelvin")
    if flux == min_flux:
        return F(0), F(0)
    if eps == 0:
        t = air + flux / h
        return t, t
    lo = F(0)
    hi = max(F(1), air, env)
    while h * (hi - air) + eps * sigma * (hi**4 - env**4) < flux:
        hi *= 2
    for _ in range(64):
        mid = (lo + hi) / 2
        val = h * (mid - air) + eps * sigma * (mid**4 - env**4)
        if val == flux:
            return mid, mid
        if val > flux:
            hi = mid
        else:
            lo = mid
    return lo, hi


def _prepare_shell_with_unknown(inner_radius_m, layers, cylinder_length_m):
    radius = decimal_input(inner_radius_m, "inner radius")
    if radius <= 0 or not isinstance(layers, (tuple, list)) or not 1 <= len(layers) <= 32:
        raise ValueError("positive inner radius and one to 32 layers required")
    length = None
    if cylinder_length_m is not None:
        length = decimal_input(cylinder_length_m, "cylinder length")
        if length <= 0:
            raise ValueError("cylinder length must be positive")
    pi = Box.bounds(*pi_rational_enclosure())
    known_resistance = Box.exact(0)
    unknown_index = None
    unknown_geometry_factor = None
    specs = []
    for idx, pair in enumerate(layers):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("each layer needs an outer radius and conductivity or '?'")
        outer = decimal_input(pair[0], "outer radius")
        if outer <= radius:
            raise ValueError("strictly increasing layer radii required")
        geom = (Box.exact(1 / radius - 1 / outer) / (4 * pi) if length is None
                else radial_log(outer / radius) / (2 * length * pi))
        if pair[1] in (None, "?"):
            if unknown_index is not None:
                raise ValueError("exactly one unknown layer required")
            unknown_index = idx
            unknown_geometry_factor = geom
            specs.append({"layerIndex": idx, "innerRadiusM": str(radius), "outerRadiusM": str(outer),
                          "conductivityWPerMK": None})
        else:
            k = decimal_input(pair[1], "conductivity")
            if k <= 0:
                raise ValueError("positive conductivity required for known layers")
            known_resistance = known_resistance + geom / k
            specs.append({"layerIndex": idx, "innerRadiusM": str(radius), "outerRadiusM": str(outer),
                          "conductivityWPerMK": str(k)})
        radius = outer
    if unknown_index is None:
        raise ValueError("exactly one unknown layer required")
    area_factor = 4 * radius**2 if length is None else 2 * length * radius
    area = pi * area_factor
    return length, specs, unknown_index, unknown_geometry_factor, known_resistance, area


def solve_from_law(law, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                   solid_kg, liquid_kg, duration_s, melted_mass_kg,
                   inner_radius_m, layers, enclosure_k, emissivity, sigma,
                   cylinder_length_m=None, *, air_k=None, h_w_per_m2_k=None):
    transition, latent, solid, liquid, duration = phase_inputs(
        transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s)
    if duration <= 0:
        raise ValueError("positive exposure duration required")
    if not isinstance(melted_mass_kg, (list, tuple)) or len(melted_mass_kg) != 2:
        raise ValueError("melted mass bounds require two signed decimal values")
    m_lo = signed_decimal(melted_mass_kg[0], "melted mass")
    m_hi = signed_decimal(melted_mass_kg[1], "melted mass")
    if m_lo > m_hi:
        raise ValueError("ordered melted mass bounds required")
    if m_hi >= solid or m_lo <= -liquid:
        raise ValueError("measured conversion must stay strictly below initial solid and liquid inventories")
    if (air_k is None) != (h_w_per_m2_k is None):
        raise ValueError("supply air temperature and film coefficient together")

    env = decimal_input(enclosure_k, "enclosure temperature")
    eps = decimal_input(emissivity, "emissivity")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if eps > 1 or constant <= 0:
        raise ValueError("emissivity in [0,1] and positive sigma required")
    air = F(0) if air_k is None else decimal_input(air_k, "air temperature")
    h = F(0) if h_w_per_m2_k is None else decimal_input(h_w_per_m2_k, "convective heat transfer coefficient")
    if h == 0 and eps == 0:
        raise ValueError("nonzero exterior heat exchange coefficient or emissivity required")
    if phase_port == surface_port or not {phase_port, surface_port} <= set(law["terminals"]):
        raise ValueError("distinct phase and shell ports required in the pinned network")

    length, specs, unknown_idx, geom_u, r_known, area = _prepare_shell_with_unknown(
        inner_radius_m, list(layers), cylinder_length_m)

    maintained = {**law["imposedTemperaturesK"], phase_port: str(transition)}
    opens, port_r = physical_port({**law, "imposedTemperaturesK": maintained}, surface_port)
    r_port = Box.bounds(*port_r)

    q_phase = Box.bounds(m_lo * latent / duration, m_hi * latent / duration)
    row = law["supplyResponseBoundsWPerK"][phase_port]
    g_ps = -interval(row[surface_port])
    if g_ps.span()[0] <= 0:
        raise ValueError("phase bath and shell port are not thermally coupled")
    q_fixed = sum(
        (-interval(row[n]) * (F(t) - transition)
         for n, t in maintained.items() if n not in (phase_port, surface_port)),
        ZERO,
    )
    t_inner = Box.bounds(transition, transition) + (q_phase - q_fixed) / g_ps
    if t_inner.span()[0] < 0:
        raise ValueError("implied inner shell temperature must be nonnegative in Kelvin")

    q_shell_port = (Box.bounds(*opens) - t_inner) / r_port
    temps = {n: F(t) for n, t in maintained.items() if n != surface_port}
    temps[surface_port] = t_inner
    inflows = reservoir_inflows(law, surface_port, temps)
    inflows.pop(phase_port)
    q_shell_bal = -q_phase - sum((interval(v) for v in inflows.values()), ZERO)
    q_shell = intersect_boxes(
        q_shell_port, q_shell_bal,
        "measured bath conversion violates steady network energy balance")
    q_lo, q_hi = q_shell.span()
    if q_lo <= 0 <= q_hi:
        raise ValueError("nonzero shell heat rate required to identify layer conductivity")

    flux_lo, flux_hi = (q_shell / area).span()
    ts_lo = invert_exterior_flux(flux_lo, air, h, env, eps, constant)[0]
    ts_hi = invert_exterior_flux(flux_hi, air, h, env, eps, constant)[1]
    surface = Box.bounds(ts_lo, ts_hi)

    r_shell_inner = (t_inner - surface) / q_shell
    r_shell_open = (Box.bounds(*opens) - surface) / q_shell - r_port
    r_shell_total = intersect_boxes(
        r_shell_inner, r_shell_open,
        "implied shell resistance bounds are inconsistent")
    r_unknown = r_shell_total - r_known
    if r_unknown.span()[0] <= 0:
        raise ValueError("measurement cannot establish a positive thermal resistance for the unknown layer")
    k_unknown = geom_u / r_unknown

    result = {
        "schema": "sim_heat.offline_phase_shell_conductivity/1",
        "phaseBathPort": phase_port,
        "surfacePort": surface_port,
        "geometry": "sphere" if length is None else "cylinder",
        "cylinderLengthM": None if length is None else str(length),
        "innerRadiusM": str(decimal_input(inner_radius_m, "inner radius")),
        "layers": specs,
        "unknownLayerIndex": unknown_idx,
        "transitionTemperatureK": str(transition),
        "specificLatentHeatJPerKg": str(latent),
        "initialSolidKg": str(solid),
        "initialLiquidKg": str(liquid),
        "exposureDurationS": str(duration),
        "measuredMeltedMassBoundsKg": [str(m_lo), str(m_hi)],
        "enclosureTemperatureK": str(env),
        "emissivity": str(eps),
        "sigmaWPerM2K4": str(constant),
        "inferredBathInflowBoundsW": bounds(q_phase),
        "maintainedReservoirInflowBoundsW": {name: list(map(str, pair)) for name, pair in inflows.items()},
        "outwardHeatRateBoundsW": bounds(q_shell),
        "innerSurfaceTemperatureBoundsK": bounds(t_inner),
        "outerSurfaceTemperatureBoundsK": bounds(surface),
        "unknownLayerResistanceBoundsKPerW": bounds(r_unknown),
        "inferredConductivityBoundsWPerMK": bounds(k_unknown),
        **offline_provenance(law),
    }
    if air_k is not None:
        result.update(airTemperatureK=str(air), convectionCoefficientWPerM2K=str(h))
    return result


def investigate(inputs, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                solid_kg, liquid_kg, duration_s, melted_mass_kg,
                inner_radius_m, layers, enclosure_k, emissivity, sigma,
                cylinder_length_m=None, *, air_k=None, h_w_per_m2_k=None):
    return solve_from_law(
        terminal_response(*inputs), phase_port, surface_port, transition_k,
        latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s, melted_mass_kg,
        inner_radius_m, layers, enclosure_k, emissivity, sigma, cylinder_length_m,
        air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "phase-port", "surface-port",
                  "transition-k", "latent-heat-j-per-kg", "solid-kg", "liquid-kg",
                  "duration-s", "inner-radius-m", "enclosure-k", "emissivity", "sigma"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--melted-kg", nargs=2, required=True, metavar=("LOW_KG", "HIGH_KG"))
    p.add_argument("--layer", action="append", nargs=2, required=True,
                   metavar=("R_OUT_M", "K_OR_QUESTION"))
    p.add_argument("--cylinder-length-m")
    p.add_argument("--air-k")
    p.add_argument("--h-w-per-m2-k")
    a = p.parse_args()
    print(json.dumps(investigate(
        (a.study, a.root, a.facts, a.facts_sha256), a.phase_port, a.surface_port,
        a.transition_k, a.latent_heat_j_per_kg, a.solid_kg, a.liquid_kg, a.duration_s,
        a.melted_kg, a.inner_radius_m, a.layer, a.enclosure_k, a.emissivity, a.sigma,
        a.cylinder_length_m, air_k=a.air_k, h_w_per_m2_k=a.h_w_per_m2_k), indent=2))
