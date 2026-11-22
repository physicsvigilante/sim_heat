"""Select one stocked insulation radius for several specified steady exterior conditions."""
import argparse
from fractions import Fraction as F
import json

from tools.radiating_surface import decimal_input
from tools.shell_size_selection import budget_status, select_from_law, smallest_established
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, inner_radius_m, layers, coating_k, radii, limit_w,
                emissivity, sigma, environments, cylinder_length_m=None):
    environments = tuple(environments)
    if not environments:
        raise ValueError("at least one exterior condition required")
    law = terminal_response(*inputs)
    layers, radii = tuple(layers), tuple(radii)
    runs = {}
    for name, air, h, enclosure in environments:
        if type(name) is not str or not name or name in runs:
            raise ValueError("unique nonempty string condition names required")
        if air is None or h is None:
            raise ValueError('each environment requires air temperature and film coefficient')
        runs[name] = select_from_law(law, port, inner_radius_m, layers, coating_k, radii, limit_w,
                                     enclosure, emissivity, sigma, cylinder_length_m,
                                     air_k=air, h_w_per_m2_k=h)
    first = next(iter(runs.values()))
    budget = decimal_input(limit_w, "heat-rate magnitude budget")
    sizes = []
    for index, option in enumerate(first["sizes"]):
        cases = {name: run["sizes"][index] for name,run in runs.items()}
        # The worst load is the maximum of the magnitudes in the specified
        # steady environments. Opposite directions do not cancel.
        lo = max(F(row["magnitudeBoundsW"][0]) for row in cases.values())
        hi = max(F(row["magnitudeBoundsW"][1]) for row in cases.values())
        sizes.append({"outerRadiusM": option["outerRadiusM"],
                      "worstMagnitudeBoundsW": [str(lo), str(hi)],
                      "status": budget_status(lo, hi, budget), "environments": cases})
    return {
        "schema": "sim_heat.offline_multi_environment_shell_selection/1",
        **{k:first[k] for k in ("innerPort","geometry","cylinderLengthM","innerRadiusM","innerLayers",
                                "coatingConductivityWPerMK","heatRateMagnitudeBudgetW","emissivity","sigmaWPerM2K4",
                                "modelSha256","studySha256","factsSha256","nativeExecuted","nativeQualified",
                                "independentlyCertifiedReference","runnerConsumable")},
        "environments": {name:{k:run[k] for k in ("airTemperatureK","enclosureTemperatureK",
                                                   "convectionCoefficientWPerM2K")} for name,run in runs.items()},
        "sizes": sizes, "smallestEstablishedWithinBudgetRadiusM": smallest_established(sizes),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study","root","facts","facts-sha256","port","inner-radius-m","coating-k","limit-w",
                  "emissivity","sigma"):
        p.add_argument("--"+field, required=True)
    p.add_argument("--inner-layer", action="append", nargs=2, default=[], metavar=("R_OUT_M","K_W_PER_M_K"))
    p.add_argument("--radius-m", action="append", required=True)
    p.add_argument("--environment", action="append", required=True, nargs=4,
                   metavar=("NAME","AIR_K","H_W_PER_M2_K","ENCLOSURE_K"))
    p.add_argument("--cylinder-length-m")
    a = p.parse_args()
    print(json.dumps(investigate((a.study,a.root,a.facts,a.facts_sha256), a.port, a.inner_radius_m,
                                 a.inner_layer,a.coating_k,a.radius_m,a.limit_w,a.emissivity,a.sigma,
                                 a.environment,a.cylinder_length_m), indent=2))
