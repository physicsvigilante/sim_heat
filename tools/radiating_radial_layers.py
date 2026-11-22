"""Radial multilayer conduction to a diffuse gray surface facing an isothermal enclosure."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.radiating_surface import decimal_input, exterior_balance, physical_port, surface_balance
from tools.spherical_conduction import prepare_layers
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, inner_radius_m, layers, enclosure_k, emissivity, sigma,
                cylinder_length_m=None, *, radius_sensitivity=False, air_k=None, h_w_per_m2_k=None):
    return solve(terminal_response(*inputs), port, inner_radius_m, layers, enclosure_k, emissivity,
                 sigma, cylinder_length_m, radius_sensitivity=radius_sensitivity,
                 air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)


def solve(law, port, inner_radius_m, layers, enclosure_k, emissivity, sigma,
          cylinder_length_m=None, *, radius_sensitivity=False, air_k=None, h_w_per_m2_k=None):
    environment = decimal_input(enclosure_k, "enclosure temperature")
    eps = decimal_input(emissivity, "emissivity")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if eps > 1 or constant <= 0:
        raise ValueError("positive sigma and emissivity in [0,1] required")
    shell = prepare_layers(inner_radius_m, layers, cylinder_length_m)
    open_bounds, port_bounds = physical_port(law, port)
    port_resistance = Box.bounds(*port_bounds)
    total = port_resistance + shell.resistances[-1]
    area = shell.outer_area()
    if (air_k is None) != (h_w_per_m2_k is None):
        raise ValueError("supply air temperature and film coefficient together")
    h = Fraction(0)
    if air_k is None:
        solutions = [surface_balance(open_bounds, total.span(), environment, a*eps*constant)
                     for a in area.span()]
    else:
        air = decimal_input(air_k, "air temperature")
        h = decimal_input(h_w_per_m2_k, "convective heat transfer coefficient")
        # For fixed port conditions, a larger area moves T toward the zero
        # of the monotone external loss per unit area. T and total Q are
        # therefore enclosed by the two area endpoints even for opposing fluxes.
        solutions = []
        for a in area.span():
            balance = exterior_balance(law, port, open_bounds, total.span(), environment,
                                       a, eps, constant, air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)
            solutions.append((tuple(map(Fraction, balance["surfaceTemperatureBoundsK"])),
                              tuple(map(Fraction, balance["conductorToSurfaceHeatBoundsW"]))))
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

    if air_k is not None:
        # Bound each exchange over the whole T and area enclosures. Individual
        # exchanges can oppose one another even when the total flow is small.
        convection = area*h*Box.bounds(surface_lo-air, surface_hi-air)
        radiation = area*eps*constant*Box.bounds(surface_lo**4-environment**4,
                                                 surface_hi**4-environment**4)
        result.update(schema="sim_heat.offline_convecting_radiating_radial_layers/1",
                      airTemperatureK=str(air), convectionCoefficientWPerM2K=str(h),
                      netHeatToAirBoundsW=bounds(convection), netHeatToEnclosureBoundsW=bounds(radiation))
    if radius_sensitivity:
        # Vary only the final radius, holding the coating material, emissivity,
        # port law, inner radii and (for a cylinder) axial length fixed.
        temperature = Box.bounds(surface_lo,surface_hi)
        surface_slope = h + 4*eps*constant*temperature*temperature*temperature
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


def turning_radius(inputs, port, inner_radius_m, layers, enclosure_k, emissivity, sigma,
                   cylinder_length_m, upper_radius_m, *, air_k=None, h_w_per_m2_k=None):
    law = terminal_response(*inputs)
    def evaluate(stack):
        return solve(law, port, inner_radius_m, stack, enclosure_k, emissivity, sigma,
                     cylinder_length_m, radius_sensitivity=True, air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)

    lower = evaluate(layers)
    lower_m = Fraction(lower["layers"][-1]["outerRadiusM"])
    upper_m = decimal_input(upper_radius_m, "upper search radius")
    if upper_m <= lower_m:
        raise ValueError("upper search radius must exceed the starting outer radius")
    base_layers = list(layers[:-1])
    conductivity = layers[-1][1]
    upper = evaluate([*base_layers,(upper_radius_m,conductivity)])
    def trend(result):
        return result["outerRadiusSensitivity"]["heatRateMagnitudeTrend"]
    if {trend(lower),trend(upper)} != {"increasing","decreasing"}:
        raise ValueError("resolved opposite heat-rate magnitude trends required")

    # The public grammar accepts 18 decimal places. Integer arithmetic keeps
    # every query on this grid, while preserving the two certified endpoint signs.
    scale = 10**18
    a, b = int(lower_m*scale), int(upper_m*scale)
    reason = "iteration_limit"
    for _ in range(64):
        tick = (a+b)//2
        if tick == a:
            reason = "decimal_resolution"
            break
        radius = f"{tick//scale}.{tick%scale:018d}"
        mid = evaluate([*base_layers,(radius,conductivity)])
        if trend(mid) == trend(lower):
            a, lower = tick, mid
        elif trend(mid) == trend(upper):
            b, upper = tick, mid
        else:
            reason = "midpoint_trend_unresolved"
            break
    return {"schema": "sim_heat.offline_insulation_turning_radius/1",
            "searchRadiusBoundsM": [str(lower_m),str(upper_m)],
            "turningRadiusBoundsM": [str(Fraction(a,scale)),str(Fraction(b,scale))],
            "extremumWithinBracket": "maximum" if trend(lower) == "increasing" else "minimum",
            "termination": reason, "lowerEndpoint": lower, "upperEndpoint": upper}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study","root","facts","facts-sha256","port","inner-radius-m","enclosure-k","emissivity","sigma"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--cylinder-length-m")
    parser.add_argument("--layer", nargs=2, action="append", required=True, metavar=("OUTER_RADIUS_M","K_W_PER_M_K"))
    parser.add_argument("--radius-sensitivity", action="store_true")
    parser.add_argument("--bracket-to-radius-m", help="bound an extremum using opposite endpoint slopes")
    parser.add_argument("--air-k")
    parser.add_argument("--h-w-per-m2-k")
    args = parser.parse_args()
    film = dict(air_k=args.air_k, h_w_per_m2_k=args.h_w_per_m2_k)
    inputs = ((args.study,args.root,args.facts,args.facts_sha256),args.port,args.inner_radius_m,
              args.layer,args.enclosure_k,args.emissivity,args.sigma,args.cylinder_length_m)
    if args.bracket_to_radius_m is None:
        result = investigate(*inputs,radius_sensitivity=args.radius_sensitivity, **film)
    else:
        result = turning_radius(*inputs,args.bracket_to_radius_m, **film)
    print(json.dumps(result,indent=2))
