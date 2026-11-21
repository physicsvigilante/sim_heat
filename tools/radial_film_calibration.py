"""Infer an external convection coefficient from a steady radial surface thermometer."""
import argparse
import json

from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.radiating_surface import decimal_input, physical_port
from tools.spherical_conduction import prepare_layers
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, inner_radius_m, layers, surface_k, air_k, enclosure_k,
                emissivity, sigma, cylinder_length_m=None):
    low, high = (decimal_input(t, "surface temperature") for t in surface_k)
    air = decimal_input(air_k, "air temperature")
    env = decimal_input(enclosure_k, "enclosure temperature")
    eps = decimal_input(emissivity, "emissivity")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if low > high or eps > 1 or not constant:
        raise ValueError("ordered Kelvin readings, emissivity in [0,1] and positive sigma required")
    if low <= air <= high:
        raise ValueError("surface reading must resolve a nonzero temperature difference from air")
    shell = prepare_layers(inner_radius_m, layers, cylinder_length_m)
    law = terminal_response(*inputs)
    opens, resistance = physical_port(law, port)
    total = Box.bounds(*resistance) + shell.resistances[-1]
    area = shell.outer_area()
    surface = Box.bounds(low, high)
    wall = (Box.bounds(*opens) - surface)/total
    radiation_flux = eps*constant*Box.bounds(low**4-env**4, high**4-env**4)
    convective_flux = wall/area - radiation_flux
    h = convective_flux/(surface-air)
    if h.low < 0:
        raise ValueError("reading cannot establish a nonnegative convection coefficient")
    return {
        "schema": "sim_heat.offline_radial_film_calibration/1", "innerPort": port,
        "geometry": "sphere" if shell.length is None else "cylinder",
        "innerRadiusM": str(shell.radii[0]), "layers": shell.material,
        "cylinderLengthM": None if shell.length is None else str(shell.length),
        "surfaceTemperatureBoundsK": [str(low), str(high)], "airTemperatureK": str(air),
        "enclosureTemperatureK": str(env), "emissivity": str(eps), "sigmaWPerM2K4": str(constant),
        "outwardHeatRateBoundsW": bounds(wall), "netHeatToAirBoundsW": bounds(convective_flux*area),
        "netHeatToEnclosureBoundsW": bounds(radiation_flux*area),
        "convectionCoefficientBoundsWPerM2K": bounds(h),
        **{key: law[key] for key in ("modelSha256", "studySha256", "factsSha256",
                                     "nativeExecuted", "nativeQualified",
                                     "independentlyCertifiedReference", "runnerConsumable")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study","root","facts","facts-sha256","port","inner-radius-m","air-k",
                  "enclosure-k","emissivity","sigma"):
        parser.add_argument("--"+field, required=True)
    parser.add_argument("--layer", action="append", nargs=2, required=True, metavar=("R_OUT_M","K_W_PER_M_K"))
    parser.add_argument("--surface-k", nargs=2, required=True, metavar=("LOW_K","HIGH_K"))
    parser.add_argument("--cylinder-length-m")
    a = parser.parse_args()
    print(json.dumps(investigate((a.study,a.root,a.facts,a.facts_sha256), a.port, a.inner_radius_m,
                                 a.layer, a.surface_k, a.air_k, a.enclosure_k, a.emissivity, a.sigma,
                                 a.cylinder_length_m), indent=2))
