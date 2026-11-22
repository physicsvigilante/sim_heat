"""Infer an external convection coefficient from timed melting or freezing inside a radial shell."""
import argparse
from fractions import Fraction as F
import json

from qualification.h1_n13.conduction import ZERO, Box, interval
from tools.join_thermal_networks import bounds
from tools.latent_heat_bath import phase_inputs, reservoir_inflows
from tools.radiating_surface import decimal_input, physical_port
from tools.spherical_conduction import prepare_layers
from tools.terminal_response import investigate as terminal_response


def signed_decimal(value, label):
    negative = isinstance(value, str) and value.startswith("-")
    magnitude = decimal_input(value[1:] if negative else value, label)
    return -magnitude if negative else magnitude


def intersect_boxes(a, b, message):
    a_lo, a_hi = a.span()
    b_lo, b_hi = b.span()
    lo, hi = max(a_lo, b_lo), min(a_hi, b_hi)
    if lo > hi:
        raise ValueError(message)
    return Box.bounds(lo, hi)


def solve_from_law(law, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                   solid_kg, liquid_kg, duration_s, melted_mass_kg,
                   inner_radius_m, layers, air_k, enclosure_k, emissivity, sigma,
                   cylinder_length_m=None):
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
    # Exhausting either phase ends the isothermal plateau at an unknown time,
    # so the timed mass change no longer identifies the steady plateau heat rate.
    if m_hi >= solid or m_lo <= -liquid:
        raise ValueError("measured conversion must stay strictly below initial solid and liquid inventories")

    air = decimal_input(air_k, "air temperature")
    env = decimal_input(enclosure_k, "enclosure temperature")
    eps = decimal_input(emissivity, "emissivity")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if eps > 1 or constant <= 0:
        raise ValueError("emissivity in [0,1] and positive sigma required")
    if phase_port == surface_port or not {phase_port, surface_port} <= set(law["terminals"]):
        raise ValueError("distinct phase and shell ports required in the pinned network")

    shell = prepare_layers(inner_radius_m, layers, cylinder_length_m)
    maintained = {**law["imposedTemperaturesK"], phase_port: str(transition)}
    opens, port_r = physical_port({**law, "imposedTemperaturesK": maintained}, surface_port)
    r_port = Box.bounds(*port_r)
    r_shell = shell.resistances[-1]
    r_total = r_port + r_shell
    area = shell.outer_area()

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

    q_shell_port = (Box.bounds(*opens) - t_inner) / r_port
    temps = {n: F(t) for n, t in maintained.items() if n != surface_port}
    temps[surface_port] = t_inner
    inflows = reservoir_inflows(law, surface_port, temps)
    inflows.pop(phase_port)
    q_shell_bal = -q_phase - sum((interval(v) for v in inflows.values()), ZERO)
    q_shell = intersect_boxes(
        q_shell_port, q_shell_bal,
        "measured bath conversion violates steady network energy balance")

    surface = intersect_boxes(
        t_inner - r_shell * q_shell, Box.bounds(*opens) - r_total * q_shell,
        "implied outer surface temperature bounds are inconsistent")
    ts_lo, ts_hi = surface.span()
    if t_inner.span()[0] < 0 or ts_lo < 0:
        raise ValueError("implied shell temperature must be nonnegative in Kelvin")
    if ts_lo <= air <= ts_hi:
        raise ValueError("implied outer surface temperature must resolve a nonzero difference from air")

    radiation_flux = eps * constant * Box.bounds(ts_lo**4 - env**4, ts_hi**4 - env**4)
    convective_flux = q_shell / area - radiation_flux
    h = convective_flux / (surface - air)
    if h.span()[0] < 0:
        raise ValueError("measurement cannot establish a nonnegative convection coefficient")
    q_rad = radiation_flux * area
    q_conv = intersect_boxes(
        q_shell - q_rad, convective_flux * area,
        "implied convective heat rate bounds are inconsistent")
    return {
        "schema": "sim_heat.offline_phase_film_calibration/1",
        "phaseBathPort": phase_port,
        "surfacePort": surface_port,
        "geometry": "sphere" if shell.length is None else "cylinder",
        "innerRadiusM": str(shell.radii[0]),
        "layers": shell.material,
        "cylinderLengthM": None if shell.length is None else str(shell.length),
        "transitionTemperatureK": str(transition),
        "specificLatentHeatJPerKg": str(latent),
        "initialSolidKg": str(solid),
        "initialLiquidKg": str(liquid),
        "exposureDurationS": str(duration),
        "measuredMeltedMassBoundsKg": [str(m_lo), str(m_hi)],
        "airTemperatureK": str(air),
        "enclosureTemperatureK": str(env),
        "emissivity": str(eps),
        "sigmaWPerM2K4": str(constant),
        "inferredBathInflowBoundsW": bounds(q_phase),
        "maintainedReservoirInflowBoundsW": {name: list(map(str, pair)) for name, pair in inflows.items()},
        "outwardHeatRateBoundsW": bounds(q_shell),
        "innerSurfaceTemperatureBoundsK": bounds(t_inner),
        "outerSurfaceTemperatureBoundsK": bounds(surface),
        "netHeatToAirBoundsW": bounds(q_conv),
        "netHeatToEnclosureBoundsW": bounds(q_rad),
        "convectionCoefficientBoundsWPerM2K": bounds(h),
        **{key: law[key] for key in ("modelSha256", "studySha256", "factsSha256",
                                     "nativeExecuted", "nativeQualified",
                                     "independentlyCertifiedReference", "runnerConsumable")},
    }


def investigate(inputs, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                solid_kg, liquid_kg, duration_s, melted_mass_kg,
                inner_radius_m, layers, air_k, enclosure_k, emissivity, sigma,
                cylinder_length_m=None):
    return solve_from_law(
        terminal_response(*inputs), phase_port, surface_port, transition_k,
        latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s, melted_mass_kg,
        inner_radius_m, layers, air_k, enclosure_k, emissivity, sigma, cylinder_length_m)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "phase-port", "surface-port",
                  "transition-k", "latent-heat-j-per-kg", "solid-kg", "liquid-kg",
                  "duration-s", "inner-radius-m", "air-k", "enclosure-k", "emissivity", "sigma"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--melted-kg", nargs=2, required=True, metavar=("LOW_KG", "HIGH_KG"))
    p.add_argument("--layer", action="append", nargs=2, required=True,
                   metavar=("R_OUT_M", "K_W_PER_M_K"))
    p.add_argument("--cylinder-length-m")
    a = p.parse_args()
    print(json.dumps(investigate(
        (a.study, a.root, a.facts, a.facts_sha256), a.phase_port, a.surface_port,
        a.transition_k, a.latent_heat_j_per_kg, a.solid_kg, a.liquid_kg, a.duration_s,
        a.melted_kg, a.inner_radius_m, a.layer, a.air_k, a.enclosure_k, a.emissivity,
        a.sigma, a.cylinder_length_m), indent=2))
