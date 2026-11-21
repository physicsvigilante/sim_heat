"""Identify a common air-film coefficient and emissivity from two steady shell trials."""
import argparse
import json

from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.radiating_surface import decimal_input, physical_port
from tools.spherical_conduction import prepare_layers
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, inner_radius_m, layers, sigma, trials, cylinder_length_m=None):
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if not constant or len(trials) != 2:
        raise ValueError("positive sigma and two steady environmental trials required")
    shell = prepare_layers(inner_radius_m, layers, cylinder_length_m)
    law = terminal_response(*inputs)
    opens, resistance = physical_port(law, port)
    open_temp = Box.bounds(*opens)
    area_resistance = shell.outer_area()*(Box.bounds(*resistance) + shell.resistances[-1])
    rows, drops, readings = [], [], []
    for low, high, air_k, enclosure_k in trials:
        lo, hi, air, env = (decimal_input(t, "temperature in kelvin")
                            for t in (low, high, air_k, enclosure_k))
        if lo > hi:
            raise ValueError("ordered thermometer bounds required")
        surface = Box.bounds(lo, hi)
        rows.append((surface-air, constant*Box.bounds(lo**4-env**4, hi**4-env**4)))
        drops.append(open_temp-surface)
        readings.append({"surfaceTemperatureBoundsK": [str(lo), str(hi)],
                         "airTemperatureK": str(air), "enclosureTemperatureK": str(env)})
    # The two balances have the same shell conductance and area. Factor the
    # common 1/(R A) out of the inverse to keep the units and correlation.
    (a,b), (c,d) = rows
    det = a*d-b*c
    if det.contains_zero():
        raise ValueError("trials do not distinguish convection and radiation within the readings")
    denominator = det*area_resistance
    h = (drops[0]*d-b*drops[1])/denominator
    eps = (a*drops[1]-drops[0]*c)/denominator
    if h.low < 0 or eps.low < 0 or eps.span()[1] > 1:
        raise ValueError("readings do not establish a nonnegative film coefficient and emissivity in [0,1]")
    return {
        "schema": "sim_heat.offline_two_environment_calibration/1",
        "innerPort": port, "innerRadiusM": str(shell.radii[0]), "layers": shell.material,
        "geometry": "sphere" if shell.length is None else "cylinder",
        "cylinderLengthM": None if shell.length is None else str(shell.length),
        "sigmaWPerM2K4": str(constant), "trials": readings,
        "convectionCoefficientBoundsWPerM2K": bounds(h), "emissivityBounds": bounds(eps),
        **{k: law[k] for k in ("modelSha256", "studySha256", "factsSha256",
                               "nativeExecuted", "nativeQualified",
                               "independentlyCertifiedReference", "runnerConsumable")},
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study","root","facts","facts-sha256","port","inner-radius-m","sigma"):
        p.add_argument("--"+field, required=True)
    p.add_argument("--layer", nargs=2, action="append", required=True, metavar=("R_OUT_M","K_W_PER_M_K"))
    p.add_argument("--trial", nargs=4, action="append", required=True, metavar=("LOW_K","HIGH_K","AIR_K","ENCLOSURE_K"))
    p.add_argument("--cylinder-length-m")
    a = p.parse_args()
    print(json.dumps(investigate((a.study,a.root,a.facts,a.facts_sha256), a.port, a.inner_radius_m,
                                 a.layer,a.sigma,a.trial,a.cylinder_length_m), indent=2))
