"""Carry one finite body's temperature through successive timed enclosure exposures."""
import argparse
from fractions import Fraction
import json
import math

from tools.body_exposure_temperature import exposure
from tools.radiating_surface import decimal_input


def investigate(inputs, port, reference_k, slope_per_k, area_m2, emissivity, sigma, capacity_j_per_k,
                initial_k, stages):
    capacity = decimal_input(capacity_j_per_k, "heat capacity")
    start = decimal_input(initial_k, "initial temperature")
    if capacity <= 0 or not stages:
        raise ValueError("positive heat capacity and at least one exposure required")
    records = []
    low = high = start
    elapsed = Fraction(0)
    grid = 10**18
    for enclosure, seconds in stages:
        duration = decimal_input(seconds, "stage duration")
        before = low, high
        # Scalar trajectories cannot cross for the same smooth bath law. The two
        # endpoint trajectories therefore enclose every admissible incoming state.
        def advance(t):
            return exposure(inputs, port, reference_k, slope_per_k, enclosure, area_m2, emissivity,
                            sigma, capacity, t, duration)
        left = advance(low)
        right = left if low == high else advance(high)
        low = Fraction(left["temperatureBoundsK"][0])
        high = Fraction(right["temperatureBoundsK"][1])
        # Bound denominator growth over long schedules. Rounding is outward.
        low, high = Fraction(math.floor(grid*low), grid), Fraction(math.ceil(grid*high), grid)
        elapsed += duration
        records.append({"enclosureTemperatureK": left["exterior"]["enclosureTemperatureK"],
                        "durationS": str(duration), "elapsedS": str(elapsed),
                        "initialTemperatureBoundsK": list(map(str, before)),
                        "temperatureBoundsK": list(map(str, (low, high))),
                        "cumulativeBodyEnergyChangeBoundsJ": [str(capacity*(t-start)) for t in (low, high)]})
    exterior = left["exterior"]
    return {"schema": "sim_heat.offline_body_exposure_sequence/1", "initialTemperatureK": str(start),
            "capacityJPerK": str(capacity), "stages": records,
            **{key: exterior[key] for key in ("areaM2", "emissivity", "sigmaWPerM2K4")},
            **{key: left[key] for key in ("bodyPort", "referenceTemperatureK", "relativeSlopePerK",
                                         "modelSha256", "studySha256", "factsSha256", "nativeExecuted",
                                         "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256", "port", "reference-k", "slope-per-k",
              "area-m2", "emissivity", "sigma", "capacity-j-per-k", "initial-k")
    for field in fields:
        parser.add_argument("--"+field, required=True)
    parser.add_argument("--stage", nargs=2, action="append", required=True, metavar=("ENCLOSURE_K", "SECONDS"))
    args = vars(parser.parse_args())
    values = [args[field.replace("-", "_")] for field in fields]
    print(json.dumps(investigate(values[:4], *values[4:], args["stage"]), indent=2))
