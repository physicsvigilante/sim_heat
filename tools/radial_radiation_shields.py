"""Steady concentric spherical or cylindrical diffuse-gray radiation shields and Dewar phase bath."""
import argparse
from fractions import Fraction as F
import json

from qualification.h1_n4.static_physical import pi_rational_enclosure
from qualification.h1_n13.conduction import ZERO, Box, interval
from tools.join_thermal_networks import bounds
from tools.latent_heat_bath import phase_inputs, plateau_state, reservoir_inflows
from tools.offline_provenance import offline_provenance
from tools.radiating_surface import decimal_input, physical_port, surface_balance
from tools.radiative_gap import fourth_root_bounds
from tools.spherical_conduction import prepare_layers
from tools.terminal_response import investigate as terminal_response


def _area_prefactor(radius, length):
    """Exact rational factor a such that surface area A = pi * a."""
    return 4 * radius * radius if length is None else 2 * length * radius


def _concentric_shield_chain(inner_radius, surface_emissivity, shields,
                             enclosure_radius_m, enclosure_emissivity, length):
    eps_0 = decimal_input(surface_emissivity, "surface emissivity")
    r_enc = decimal_input(enclosure_radius_m, "enclosure radius")
    eps_enc = decimal_input(enclosure_emissivity, "enclosure emissivity")
    if max(eps_0, eps_enc) > 1:
        raise ValueError("emissivities in [0,1] required")
    if not isinstance(shields, (tuple, list)) or len(shields) > 64:
        raise ValueError("shields must be a sequence of up to 64 (radius, inner_eps, outer_eps) entries")

    parsed_shields = []
    prev_r = inner_radius
    for entry in shields:
        if not isinstance(entry, (tuple, list)) or len(entry) != 3:
            raise ValueError("each shield requires radius, inner emissivity, and outer emissivity")
        r = decimal_input(entry[0], "shield radius")
        e_in = decimal_input(entry[1], "shield inner emissivity")
        e_out = decimal_input(entry[2], "shield outer emissivity")
        if r <= prev_r:
            raise ValueError("strictly increasing concentric radii required")
        if max(e_in, e_out) > 1:
            raise ValueError("emissivities in [0,1] required")
        parsed_shields.append((r, e_in, e_out))
        prev_r = r

    if r_enc <= prev_r:
        raise ValueError("enclosure radius must exceed the outermost shell or shield radius")

    # Nodes j = 0 (shell outer surface), 1..N (shields), N+1 (outer enclosure).
    radii = [inner_radius, *(r for r, _, _ in parsed_shields), r_enc]
    out_eps = [eps_0, *(e_out for _, _, e_out in parsed_shields)]
    in_eps = [*(e_in for _, e_in, _ in parsed_shields), eps_enc]

    # Exact rational pi-scaled radiative resistance per vacuum gap:
    # R_rad,j = (1 / (A_j * e_out) + (1 / e_in - 1) / A_{j+1}) = rho_j / pi.
    gap_rhos = []
    for j in range(len(out_eps)):
        eo, ei = out_eps[j], in_eps[j]
        if eo == 0 or ei == 0:
            gap_rhos.append(None)
        else:
            a_inner = _area_prefactor(radii[j], length)
            a_outer = _area_prefactor(radii[j + 1], length)
            gap_rhos.append(F(1) / (a_inner * eo) + (F(1) / ei - 1) / a_outer)

    return eps_0, r_enc, eps_enc, parsed_shields, gap_rhos


def solve(law, port, inner_radius_m, layers, surface_emissivity, enclosure_radius_m,
          enclosure_emissivity, enclosure_k, sigma, shields=(), cylinder_length_m=None):
    environment = decimal_input(enclosure_k, "enclosure temperature")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if constant <= 0:
        raise ValueError("positive sigma required")
    shell = prepare_layers(inner_radius_m, layers, cylinder_length_m)
    open_bounds, port_bounds = physical_port(law, port)
    port_resistance = Box.bounds(*port_bounds)
    total = port_resistance + shell.resistances[-1]
    area = shell.outer_area()

    eps_0, r_enc, eps_enc, parsed_shields, gap_rhos = _concentric_shield_chain(
        shell.radii[-1], surface_emissivity, list(shields),
        enclosure_radius_m, enclosure_emissivity, shell.length,
    )
    breaks = [j for j, rho in enumerate(gap_rhos) if rho is None]

    if not breaks:
        rho_tot = sum(gap_rhos, F(0))
        pi_lo, pi_hi = pi_rational_enclosure()
        c_lo, c_hi = pi_lo * constant / rho_tot, pi_hi * constant / rho_tot
        solutions = [surface_balance(open_bounds, total.span(), environment, c)
                     for c in (c_lo, c_hi)]
        surface_lo = min(t[0] for t, _ in solutions)
        surface_hi = max(t[1] for t, _ in solutions)
        rate = Box.bounds(min(q[0] for _, q in solutions), max(q[1] for _, q in solutions))
        c_rad_bounds = [str(c_lo), str(c_hi)]
    else:
        surface_lo, surface_hi = open_bounds
        rate = Box.exact(0)
        c_rad_bounds = ["0", "0"]

    profile = shell.surface_profile(Box.bounds(*open_bounds), port_resistance, rate)
    profile[-1]["temperatureBoundsK"] = [str(surface_lo), str(surface_hi)]

    shield_records = []
    if parsed_shields:
        if not breaks:
            rho_tot = sum(gap_rhos, F(0))
            suffix = rho_tot
            for idx, (r, e_in, e_out) in enumerate(parsed_shields):
                suffix -= gap_rhos[idx]
                # T_k^4 = (1 - w_k) * T_enc^4 + w_k * T_s^4 where pi cancels identically.
                weight = suffix / rho_tot
                m_lo = (1 - weight) * environment**4 + weight * surface_lo**4
                m_hi = (1 - weight) * environment**4 + weight * surface_hi**4
                t_bounds = fourth_root_bounds(m_lo, m_hi)
                shield_records.append({
                    "radiusM": str(r),
                    "innerEmissivity": str(e_in),
                    "outerEmissivity": str(e_out),
                    "temperatureBoundsK": t_bounds,
                    "temperatureStatus": "bounded",
                })
        else:
            for idx, (r, e_in, e_out) in enumerate(parsed_shields):
                if idx < breaks[0]:
                    t_bounds = [str(surface_lo), str(surface_hi)]
                elif idx >= breaks[-1]:
                    t_bounds = [str(environment), str(environment)]
                else:
                    t_bounds = None
                shield_records.append({
                    "radiusM": str(r),
                    "innerEmissivity": str(e_in),
                    "outerEmissivity": str(e_out),
                    "temperatureBoundsK": t_bounds,
                    "temperatureStatus": "undetermined" if t_bounds is None else "bounded",
                })

    return {
        "schema": "sim_heat.offline_radial_radiation_shields/1",
        "innerPort": port,
        "geometry": "sphere" if shell.length is None else "cylinder",
        "cylinderLengthM": None if shell.length is None else str(shell.length),
        "layers": shell.material,
        "surfaces": profile,
        "exposedAreaBoundsM2": bounds(area),
        "surfaceEmissivity": str(eps_0),
        "enclosureRadiusM": str(r_enc),
        "enclosureEmissivity": str(eps_enc),
        "enclosureTemperatureK": str(environment),
        "sigmaWPerM2K4": str(constant),
        "shieldsInnerToOuter": shield_records,
        "effectiveRadiativeConductanceBoundsWPerK4": c_rad_bounds,
        "outwardHeatRateBoundsW": bounds(rate),
        **offline_provenance(law),
    }


def investigate(inputs, port, inner_radius_m, layers, surface_emissivity, enclosure_radius_m,
                enclosure_emissivity, enclosure_k, sigma, shields=(), cylinder_length_m=None):
    return solve(
        terminal_response(*inputs), port, inner_radius_m, layers, surface_emissivity,
        enclosure_radius_m, enclosure_emissivity, enclosure_k, sigma, shields, cylinder_length_m,
    )


def solve_phase_dewar(law, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                      solid_kg, liquid_kg, duration_s, inner_radius_m, layers, surface_emissivity,
                      enclosure_radius_m, enclosure_emissivity, enclosure_k, sigma,
                      shields=(), cylinder_length_m=None):
    if phase_port == surface_port or not {phase_port, surface_port} <= set(law["terminals"]):
        raise ValueError("distinct phase and shell ports required in the pinned network")
    phase = phase_inputs(transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s)
    maintained = {**law["imposedTemperaturesK"], phase_port: str(phase[0])}
    shielded = solve(
        {**law, "imposedTemperaturesK": maintained}, surface_port, inner_radius_m, layers,
        surface_emissivity, enclosure_radius_m, enclosure_emissivity, enclosure_k, sigma,
        shields, cylinder_length_m,
    )
    temperatures = {name: F(t) for name, t in maintained.items()}
    temperatures[surface_port] = interval(shielded["surfaces"][0]["temperatureBoundsK"])
    inflows = reservoir_inflows(law, surface_port, temperatures)
    low, high = inflows.pop(phase_port)
    balanced = (-interval(shielded["outwardHeatRateBoundsW"])
                - sum((interval(v) for v in inflows.values()), ZERO))
    bal_low, bal_high = balanced.span()
    low, high = max(low, bal_low), min(high, bal_high)
    if low > high:
        raise ValueError("phase, maintained reservoirs and shielded radial surface violate steady energy balance")
    details = {
        "shieldedRadialShell": shielded,
        "maintainedReservoirInflowBoundsW": {name: list(map(str, v)) for name, v in inflows.items()},
    }
    result = plateau_state(law, phase_port, phase, low, high, details)
    result["schema"] = "sim_heat.offline_radial_shielded_phase_bath/1"
    return result


def investigate_phase_dewar(inputs, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                            solid_kg, liquid_kg, duration_s, inner_radius_m, layers,
                            surface_emissivity, enclosure_radius_m, enclosure_emissivity,
                            enclosure_k, sigma, shields=(), cylinder_length_m=None):
    return solve_phase_dewar(
        terminal_response(*inputs), phase_port, surface_port, transition_k, latent_heat_j_per_kg,
        solid_kg, liquid_kg, duration_s, inner_radius_m, layers, surface_emissivity,
        enclosure_radius_m, enclosure_emissivity, enclosure_k, sigma, shields, cylinder_length_m,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "inner-radius-m",
                  "surface-emissivity", "enclosure-radius-m", "enclosure-emissivity",
                  "enclosure-k", "sigma"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--layer", action="append", nargs=2, required=True, metavar=("R_OUT_M", "K_W_PER_M_K"))
    p.add_argument("--shield", action="append", nargs=3, default=[],
                   metavar=("R_M", "INNER_EPS", "OUTER_EPS"))
    p.add_argument("--cylinder-length-m")
    p.add_argument("--port")
    p.add_argument("--phase-port")
    p.add_argument("--surface-port")
    p.add_argument("--transition-k")
    p.add_argument("--latent-heat-j-per-kg")
    p.add_argument("--solid-kg")
    p.add_argument("--liquid-kg")
    p.add_argument("--duration-s")
    a = p.parse_args()
    inputs = (a.study, a.root, a.facts, a.facts_sha256)
    if a.phase_port is not None:
        if a.port is not None:
            p.error("use either --port or --phase-port, not both")
        required = (a.surface_port, a.transition_k, a.latent_heat_j_per_kg,
                    a.solid_kg, a.liquid_kg, a.duration_s)
        if any(v is None for v in required):
            p.error("phase Dewar mode requires --surface-port, --transition-k, --latent-heat-j-per-kg, --solid-kg, --liquid-kg, and --duration-s")
        out = investigate_phase_dewar(
            inputs, a.phase_port, a.surface_port, a.transition_k, a.latent_heat_j_per_kg,
            a.solid_kg, a.liquid_kg, a.duration_s, a.inner_radius_m, a.layer,
            a.surface_emissivity, a.enclosure_radius_m, a.enclosure_emissivity,
            a.enclosure_k, a.sigma, a.shield, a.cylinder_length_m,
        )
    else:
        if a.port is None:
            p.error("supply --port for steady shielded shell or --phase-port for Dewar phase bath")
        out = investigate(
            inputs, a.port, a.inner_radius_m, a.layer, a.surface_emissivity,
            a.enclosure_radius_m, a.enclosure_emissivity, a.enclosure_k, a.sigma,
            a.shield, a.cylinder_length_m,
        )
    print(json.dumps(out, indent=2))
