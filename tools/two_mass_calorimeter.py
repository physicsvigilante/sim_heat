"""Calibrate an empty calorimeter and one material from two timed sample masses."""
import argparse
import json

from tools.radiating_surface import decimal_input
from tools.timed_specific_heat import unit_passage


def investigate(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma,
                initial_k, target_k, trials):
    if len(trials) != 2:
        raise ValueError("two trials with distinct sample masses required")
    parsed = []
    for kg, earliest, latest in trials:
        mass = decimal_input(kg, "sample mass")
        low = decimal_input(earliest, "lower measured time")
        high = decimal_input(latest, "upper measured time")
        if not 0 < low <= high:
            raise ValueError("positive ordered timing bounds required")
        parsed.append((mass, low, high))
    (m1, a, b), (m2, c, d) = sorted(parsed)
    if m1 == m2:
        raise ValueError("distinct sample masses required")
    unit, fastest, slowest = unit_passage(inputs, port, reference_k, slope_per_k, enclosure_k,
                                          area_m2, emissivity, sigma, initial_k, target_k)
    # The two times share the same transit factor. Eliminate slope/intercept
    # in time units first so that the factor enters each final ratio only once.
    delta = m2-m1
    slope = (c-b)/delta, (d-a)/delta
    intercept = (m2*a-m1*d)/delta, (m2*b-m1*c)/delta
    if slope[1] <= 0 or intercept[1] < 0:
        raise ValueError("timings incompatible with physical heat capacities")
    if slope[0] <= 0 or intercept[0] < 0:
        raise ValueError("positive sample heat or nonnegative calorimeter capacity unresolved")

    def scaled(pair):
        return [str(pair[0]/slowest), str(pair[1]/fastest)]

    return {"schema": "sim_heat.offline_two_mass_calorimeter/1", "unitCapacityPassage": unit,
            "trials": [{"sampleMassKg": str(m), "measuredTimeBoundsS": [str(lo), str(hi)]}
                       for m, lo, hi in sorted(parsed)],
            "sampleSpecificHeatBoundsJPerKgK": scaled(slope), "emptyCalorimeterCapacityBoundsJPerK": scaled(intercept),
            **{key: unit[key] for key in ("nativeExecuted", "nativeQualified", "runnerConsumable",
                                          "independentlyCertifiedReference")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256", "port", "reference-k", "slope-per-k",
              "enclosure-k", "area-m2", "emissivity", "sigma", "initial-k", "target-k")
    for field in fields:
        parser.add_argument("--"+field, required=True)
    parser.add_argument("--trial", nargs=3, action="append", required=True, metavar=("KG", "EARLIEST_S", "LATEST_S"))
    args = vars(parser.parse_args())
    values = [args[field.replace("-", "_")] for field in fields]
    print(json.dumps(investigate(values[:4], *values[4:], args["trial"]), indent=2))
