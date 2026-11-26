"""Latent heat transfer through a steady network and a radial insulating shell."""
import argparse
from fractions import Fraction as F
import json

from qualification.h1_n13.conduction import ZERO, interval
from simheat.laws import validate_terminal_law
from tools.latent_heat_bath import phase_inputs, plateau_state, reservoir_inflows
from tools.radiating_radial_layers import solve
from tools.terminal_response import investigate as terminal_response


def bath_inflow_from_law(law, phase_port, surface_port, transition, inner_radius_m, layers,
                         enclosure_k, emissivity, sigma, cylinder_length_m=None, *,
                         air_k=None, h_w_per_m2_k=None):
    resolved_law, _ = validate_terminal_law(law)
    law = resolved_law.to_engine_law()
    if "imposedTemperaturesK" not in law:
        raise ValueError("radial_phase_bath requires imposedTemperaturesK on the law")
    if phase_port == surface_port or not {phase_port, surface_port} <= set(law["terminals"]):
        raise ValueError("distinct phase and shell ports required in the pinned network")
    maintained = {**law["imposedTemperaturesK"], phase_port: str(transition)}
    shell = solve({**law, "imposedTemperaturesK": maintained}, surface_port, inner_radius_m, layers,
                  enclosure_k, emissivity, sigma, cylinder_length_m, air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)
    # The network terminates at the shell's inner face. The outer face
    # exchanges heat with the environment and generally has a different T.
    temperatures = {name:F(t) for name,t in maintained.items()}
    temperatures[surface_port] = interval(shell["surfaces"][0]["temperatureBoundsK"])
    inflows = reservoir_inflows(law, surface_port, temperatures)
    low, high = inflows.pop(phase_port)
    balanced = -interval(shell["outwardHeatRateBoundsW"])-sum((interval(v) for v in inflows.values()),ZERO)
    bal_low, bal_high = balanced.span()
    low, high = max(low,bal_low), min(high,bal_high)
    if low > high:
        raise ValueError("phase, maintained reservoirs and radial surface violate steady energy balance")
    details = {"radialShell": shell, "maintainedReservoirInflowBoundsW": {
        name:list(map(str,v)) for name,v in inflows.items()}}
    return low, high, details


def solve_from_law(law, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                   solid_kg, liquid_kg, duration_s, inner_radius_m, layers, enclosure_k,
                   emissivity, sigma, cylinder_length_m=None, *, air_k=None, h_w_per_m2_k=None):
    phase = phase_inputs(transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s)
    low, high, details = bath_inflow_from_law(
        law, phase_port, surface_port, phase[0], inner_radius_m, layers, enclosure_k,
        emissivity, sigma, cylinder_length_m, air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)
    result = plateau_state(law, phase_port, phase, low, high, details)
    result["schema"] = "sim_heat.offline_radial_phase_bath/1"
    return result


def investigate(inputs, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                solid_kg, liquid_kg, duration_s, inner_radius_m, layers, enclosure_k,
                emissivity, sigma, cylinder_length_m=None, *, air_k=None, h_w_per_m2_k=None):
    return solve_from_law(terminal_response(*inputs), phase_port, surface_port, transition_k,
                          latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s, inner_radius_m,
                          layers, enclosure_k, emissivity, sigma, cylinder_length_m,
                          air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study","root","facts","facts-sha256","phase-port","surface-port","transition-k",
                  "latent-heat-j-per-kg","solid-kg","liquid-kg","duration-s","inner-radius-m",
                  "enclosure-k","emissivity","sigma"):
        p.add_argument("--"+field, required=True)
    p.add_argument("--layer", action="append", nargs=2, required=True, metavar=("R_OUT_M","K_W_PER_M_K"))
    p.add_argument("--cylinder-length-m")
    p.add_argument("--air-k")
    p.add_argument("--h-w-per-m2-k")
    a = p.parse_args()
    print(json.dumps(investigate((a.study,a.root,a.facts,a.facts_sha256), a.phase_port,a.surface_port,
                                 a.transition_k,a.latent_heat_j_per_kg,a.solid_kg,a.liquid_kg,a.duration_s,
                                 a.inner_radius_m,a.layer,a.enclosure_k,a.emissivity,a.sigma,
                                 a.cylinder_length_m,air_k=a.air_k,h_w_per_m2_k=a.h_w_per_m2_k), indent=2))
