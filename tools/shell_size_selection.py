"""Compare available outer shell sizes against a steady radial heat-transfer budget."""
import argparse
from fractions import Fraction as F
import json

from tools.radiating_radial_layers import solve
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, inner_radius_m, inner_layers, coating_k, radii, limit_w,
                enclosure_k, emissivity, sigma, cylinder_length_m=None, *, air_k=None, h_w_per_m2_k=None):
    return select_from_law(terminal_response(*inputs), port, inner_radius_m, inner_layers, coating_k,
                           radii, limit_w, enclosure_k, emissivity, sigma, cylinder_length_m,
                           air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)


def budget_status(low, high, budget):
    if high <= budget:
        return "within_budget"
    if low > budget:
        return "over_budget"
    return "unresolved"


def smallest_established(rows):
    for row in rows:
        if row["status"] == "within_budget":
            return row["outerRadiusM"]
        if row["status"] == "unresolved":
            break
    return None


def select_from_law(law, port, inner_radius_m, inner_layers, coating_k, radii, limit_w,
                    enclosure_k, emissivity, sigma, cylinder_length_m=None, *, air_k=None, h_w_per_m2_k=None):
    budget = decimal_input(limit_w, "heat-rate magnitude budget")
    options = sorted((decimal_input(r, "outer radius"), r) for r in radii)
    if not options or len({r for r, _ in options}) != len(options):
        raise ValueError("one or more distinct available outer radii required")
    fixed = list(inner_layers)
    results = []
    for radius, token in options:
        shell = solve(law, port, inner_radius_m, [*fixed,(token,coating_k)], enclosure_k,
                      emissivity, sigma, cylinder_length_m, air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)
        low, high = map(F, shell["outwardHeatRateBoundsW"])
        minimum = F(0) if low <= 0 <= high else min(abs(low),abs(high))
        maximum = max(abs(low),abs(high))
        status = budget_status(minimum, maximum, budget)
        results.append({"outerRadiusM": str(radius), "outwardHeatRateBoundsW": shell["outwardHeatRateBoundsW"],
                        "magnitudeBoundsW": list(map(str,(minimum,maximum))), "status": status})

    # An unresolved smaller size prevents a claim about the minimum available
    # size. Keep the per-size enclosures even when that claim is unavailable.
    return {
        "schema": "sim_heat.offline_shell_size_selection/1", "innerPort": port,
        "geometry": shell["geometry"], "cylinderLengthM": shell["cylinderLengthM"],
        "innerRadiusM": str(decimal_input(inner_radius_m, "inner radius")),
        "innerLayers": shell["layers"][:-1], "coatingConductivityWPerMK": str(decimal_input(coating_k, "coating k")),
        "heatRateMagnitudeBudgetW": str(budget), "sizes": results,
        "smallestEstablishedWithinBudgetRadiusM": smallest_established(results),
        "enclosureTemperatureK": shell["enclosureTemperatureK"], "emissivity": shell["emissivity"],
        "sigmaWPerM2K4": shell["sigmaWPerM2K4"],
        **{key: shell[key] for key in ("airTemperatureK","convectionCoefficientWPerM2K") if key in shell},
        **{key: law[key] for key in ("modelSha256","studySha256","factsSha256","nativeExecuted",
                                     "nativeQualified","independentlyCertifiedReference","runnerConsumable")},
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study","root","facts","facts-sha256","port","inner-radius-m","coating-k","limit-w",
                  "enclosure-k","emissivity","sigma"):
        p.add_argument("--"+field, required=True)
    p.add_argument("--inner-layer", action="append", nargs=2, default=[], metavar=("R_OUT_M","K_W_PER_M_K"))
    p.add_argument("--radius-m", action="append", required=True)
    p.add_argument("--cylinder-length-m")
    p.add_argument("--air-k")
    p.add_argument("--h-w-per-m2-k")
    a = p.parse_args()
    print(json.dumps(investigate((a.study,a.root,a.facts,a.facts_sha256), a.port, a.inner_radius_m,
                                 a.inner_layer,a.coating_k,a.radius_m,a.limit_w,a.enclosure_k,a.emissivity,
                                 a.sigma,a.cylinder_length_m,air_k=a.air_k,h_w_per_m2_k=a.h_w_per_m2_k), indent=2))
