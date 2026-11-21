"""Radial multilayer conduction to a diffuse gray surface facing an isothermal enclosure."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.radiating_surface import decimal_input, physical_port, surface_balance
from tools.spherical_conduction import prepare_layers
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, inner_radius_m, layers, enclosure_k, emissivity, sigma,
                cylinder_length_m=None, *, radius_sensitivity=False):
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
    result = {"schema": "sim_heat.offline_radiating_radial_layers/1", "innerPort": port,
            "geometry": "sphere" if shell.length is None else "cylinder",
            "cylinderLengthM": None if shell.length is None else str(shell.length),
            "layers": shell.material, "surfaces": profile, "exposedAreaBoundsM2": bounds(area),
            "outwardHeatRateBoundsW": bounds(rate), "enclosureTemperatureK": str(environment),
            "emissivity": str(eps), "sigmaWPerM2K4": str(constant),
            **{key: law[key] for key in ("modelSha256", "studySha256", "factsSha256",
                                         "nativeExecuted", "nativeQualified",
                                         "independentlyCertifiedReference", "runnerConsumable")}}

    if radius_sensitivity:
        # Vary only the final radius, holding the coating material, emissivity,
        # port law, inner radii and (for a cylinder) axial length fixed.
        temperature = Box.bounds(surface_lo,surface_hi)
        surface_slope = 4*eps*constant*temperature*temperature*temperature
        k = Fraction(shell.material[-1]["conductivityWPerMK"])
        dimension = 2 if shell.length is None else 1
        slope_factor = (dimension/shell.radii[-1]-surface_slope/k)/(1+surface_slope*area*total)
        signed_slope = rate*slope_factor
        qlo,qhi = rate.span()
        magnitude = Box.bounds(Fraction(0) if qlo <= 0 <= qhi else min(abs(qlo),abs(qhi)),
                               max(abs(qlo),abs(qhi)))
        absolute_slope = magnitude*slope_factor
        if absolute_slope.low > 0:
            trend = "increasing"
        elif absolute_slope.high < 0:
            trend = "decreasing"
        elif absolute_slope.low == absolute_slope.high == 0:
            trend = "stationary"
        else:
            trend = "unresolved"
        result["outerRadiusSensitivity"] = {
            "outwardHeatRateDerivativeBoundsWPerM": bounds(signed_slope),
            "heatRateMagnitudeDerivativeBoundsWPerM": bounds(absolute_slope),
            "heatRateMagnitudeTrend": trend}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study","root","facts","facts-sha256","port","inner-radius-m","enclosure-k","emissivity","sigma"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--cylinder-length-m")
    parser.add_argument("--layer", nargs=2, action="append", required=True, metavar=("OUTER_RADIUS_M","K_W_PER_M_K"))
    parser.add_argument("--radius-sensitivity", action="store_true")
    args = parser.parse_args()
    print(json.dumps(investigate((args.study,args.root,args.facts,args.facts_sha256),args.port,
                                 args.inner_radius_m,args.layer,args.enclosure_k,args.emissivity,
                                 args.sigma,args.cylinder_length_m, radius_sensitivity=args.radius_sensitivity),indent=2))
