"""Infer sample specific heat from an observed time to reach a known temperature."""
import argparse
from fractions import Fraction
import json

from tools.radiating_body_time import investigate as target_time
from tools.radiating_surface import decimal_input


def unit_passage(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma, initial_k, target_k):
    unit = target_time(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma,
                       "1", initial_k, target_k)
    if unit["status"] != "reached":
        raise ValueError("a distinct target with certified finite passage is required: "+unit["status"])
    a, b = map(Fraction, unit["timeBoundsS"])
    if a <= 0:
        raise ValueError("unit-capacity passage lower bound unresolved")
    return unit, a, b


def investigate(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma,
                initial_k, target_k, time_low_s, time_high_s, calorimeter_j_per_k, sample_kg):
    low = decimal_input(time_low_s, "lower measured time")
    high = decimal_input(time_high_s, "upper measured time")
    tare = decimal_input(calorimeter_j_per_k, "empty calorimeter heat capacity")
    mass = decimal_input(sample_kg, "sample mass")
    if not 0 < low <= high or mass <= 0:
        raise ValueError("positive ordered measurement times and positive sample mass required")
    unit, a, b = unit_passage(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma,
                              initial_k, target_k)
    # With a time-independent heat law P(T), the transit time scales exactly
    # with the combined heat capacity C_cal + m*c of the isothermal contents.
    total = low/b, high/a
    sample = tuple((value-tare)/mass for value in total)
    if sample[1] <= 0:
        raise ValueError("measurement incompatible with positive sample heat capacity")
    if sample[0] <= 0:
        raise ValueError("positive sample heat capacity unresolved within measurement bounds")
    return {"schema": "sim_heat.offline_timed_specific_heat/1", "measuredTimeBoundsS": list(map(str, (low, high))),
            "emptyCalorimeterCapacityJPerK": str(tare), "sampleMassKg": str(mass),
            "combinedCapacityBoundsJPerK": list(map(str, total)),
            "sampleSpecificHeatBoundsJPerKgK": list(map(str, sample)), "unitCapacityPassage": unit,
            **{key: unit[key] for key in ("nativeExecuted", "nativeQualified", "runnerConsumable",
                                          "independentlyCertifiedReference")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256", "port", "reference-k", "slope-per-k",
              "enclosure-k", "area-m2", "emissivity", "sigma", "initial-k", "target-k", "time-low-s",
              "time-high-s", "calorimeter-j-per-k", "sample-kg")
    for field in fields:
        parser.add_argument("--"+field, required=True)
    args = vars(parser.parse_args())
    values = [args[field.replace("-", "_")] for field in fields]
    print(json.dumps(investigate(values[:4], *values[4:]), indent=2))
