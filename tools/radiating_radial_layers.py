"""Radial multilayer conduction to a diffuse gray surface facing an isothermal enclosure."""
import argparse
import json

from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.radiating_surface import decimal_input, physical_port, surface_balance
from tools.spherical_conduction import prepare_layers
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, inner_radius_m, layers, enclosure_k, emissivity, sigma,
                cylinder_length_m=None):
    environment = decimal_input(enclosure_k, "enclosure temperature")
    eps = decimal_input(emissivity, "emissivity")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if eps > 1 or constant <= 0:
        raise ValueError("positive sigma and emissivity in [0,1] required")
    shell = prepare_layers(inner_radius_m, layers, cylinder_length_m)
    law = terminal_response(*inputs)
    open_bounds, port_bounds = physical_port(law, port)
    port_resistance = Box.bounds(*port_bounds)
    total = port_resistance + shell.resistances[-1]
    area = shell.outer_area()
    # At fixed open temperature and resistance, increasing the radiation
    # coefficient moves the surface toward the enclosure and increases |Q|.
    solutions = [surface_balance(open_bounds, total.span(), environment, a*eps*constant)
                 for a in area.span()]
    surface_lo = min(t[0] for t, q in solutions)
    surface_hi = max(t[1] for t, q in solutions)
    rate = Box.bounds(min(q[0] for t,q in solutions), max(q[1] for t,q in solutions))
    profile = shell.surface_profile(Box.bounds(*open_bounds), port_resistance, rate)
    profile[-1]["temperatureBoundsK"] = [str(surface_lo), str(surface_hi)]
    return {"schema": "sim_heat.offline_radiating_radial_layers/1", "innerPort": port,
            "geometry": "sphere" if shell.length is None else "cylinder",
            "cylinderLengthM": None if shell.length is None else str(shell.length),
            "layers": shell.material, "surfaces": profile, "exposedAreaBoundsM2": bounds(area),
            "outwardHeatRateBoundsW": bounds(rate), "enclosureTemperatureK": str(environment),
            "emissivity": str(eps), "sigmaWPerM2K4": str(constant),
            **{key: law[key] for key in ("modelSha256", "studySha256", "factsSha256",
                                         "nativeExecuted", "nativeQualified",
                                         "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study","root","facts","facts-sha256","port","inner-radius-m","enclosure-k","emissivity","sigma"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--cylinder-length-m")
    parser.add_argument("--layer", nargs=2, action="append", required=True, metavar=("OUTER_RADIUS_M","K_W_PER_M_K"))
    args = parser.parse_args()
    print(json.dumps(investigate((args.study,args.root,args.facts,args.facts_sha256),args.port,
                                 args.inner_radius_m,args.layer,args.enclosure_k,args.emissivity,
                                 args.sigma,args.cylinder_length_m),indent=2))
