"""Carry one finite body's temperature through successive timed enclosure exposures."""
import argparse
from fractions import Fraction
import json
import math

from tools.body_exposure_temperature import exposure
from tools.radiating_surface import decimal_input


def investigate(inputs, port, reference_k, slope_per_k, area_m2, emissivity, sigma, capacity_j_per_k,
                initial_k, stages, *, shield_stack=None):
    capacity = decimal_input(capacity_j_per_k, "heat capacity")
    start = decimal_input(initial_k, "initial temperature")
    if capacity <= 0 or not stages:
        raise ValueError("positive heat capacity and at least one exposure required")
    records = []
    low = high = start
    elapsed = Fraction(0)
    grid = 10**18
    mixed = shield_stack is not None
    for stage in stages:
        if len(stage) == 2:
            enclosure, seconds = stage
            film = None
        elif len(stage) == 5:
            enclosure, air, area, h, seconds = stage
            film = (air, area, h)
            mixed = True
        else:
            raise ValueError("stage requires enclosure and duration, optionally with air, area and h")
        duration = decimal_input(seconds, "stage duration")
        before = low, high
        # Scalar trajectories cannot cross for the same smooth bath law. The two
        # endpoint trajectories therefore enclose every admissible incoming state.
        def advance(t):
            return exposure(inputs, port, reference_k, slope_per_k, enclosure, area_m2, emissivity,
                            sigma, capacity, t, duration, air_film=film, shield_stack=shield_stack)
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
        if film:
            records[-1]["airFilm"] = left["airFilm"]
    exterior = left["exterior"]
    shield_data = ({k: exterior[k] for k in ("shieldFacesBodyToEnclosure", "radiantExchangeCoefficientWPerK4",
                                              "enclosureEmissivity", "shieldHeatStorage")}
                   if shield_stack is not None else {})
    schema = "sim_heat.offline_mixed_exposure_sequence/1" if mixed else "sim_heat.offline_body_exposure_sequence/1"
    return {"schema": schema, **shield_data, "initialTemperatureK": str(start),
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
    parser.add_argument("--stage", dest="stages", nargs=2, action="append", metavar=("ENCLOSURE_K", "SECONDS"))
    parser.add_argument("--air-stage", dest="stages", nargs=5, action="append",
                        metavar=("ENCLOSURE_K", "AIR_K", "AREA_M2", "H_W_PER_M2_K", "SECONDS"))
    parser.add_argument("--shield", nargs=2, action="append", metavar=("BODY_SIDE", "ENCLOSURE_SIDE"))
    args = vars(parser.parse_args())
    values = [args[field.replace("-", "_")] for field in fields]
    print(json.dumps(investigate(values[:4], *values[4:], args["stages"], shield_stack=args["shield"]), indent=2))
