"""Temperature of an isothermal body after a fixed exposure to conducting and radiative baths."""
import argparse
from fractions import Fraction
import json
import math

from tools.radiating_body_time import prepare_air_film, prepare_body
from tools.radiating_surface import decimal_input


def investigate(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma,
                capacity_j_per_k, initial_k, duration_s, *, air_film=None, shield_stack=None):
    start = decimal_input(initial_k, "initial temperature")
    capacity = decimal_input(capacity_j_per_k, "heat capacity")
    duration = decimal_input(duration_s, "exposure duration")
    if capacity <= 0:
        raise ValueError("positive heat capacity required")
    return exposure(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma,
                    capacity, start, duration, air_film=air_film, shield_stack=shield_stack)


def exposure(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma,
             capacity, start, duration, *, air_film=None, shield_stack=None):
    data, power, _, (cold, hot) = prepare_body(inputs, port, reference_k, slope_per_k, enclosure_k,
                                               area_m2, emissivity, sigma, start, shield_stack=shield_stack, film=prepare_air_film(air_film))
    initial_low, initial_high = power(start)
    # A passive scalar body approaches equilibrium monotonically. Its initial
    # speed and the extreme bath temperatures therefore bound all displacements.
    low = max(cold, start + min(0, initial_low)*duration/capacity)
    high = min(hot, start + max(0, initial_high)*duration/capacity)
    if low != high and (initial_low > 0 or initial_high < 0):
        sign = 1 if initial_low > 0 else -1
        limit = high-start if sign == 1 else start-low
        step = limit/1024
        certain, possible = Fraction(0), limit
        lower_time = upper_time = 0
        quantum = 10**18
        previous_fast = initial_high if sign == 1 else -initial_low
        for i in range(1, 1025):
            distance = i*step
            a, b = power(start+sign*distance)
            slow, fast = (a, b) if sign == 1 else (-b, -a)
            # If even the fastest trajectory cannot finish the panel, its entry
            # time and entry speed bound how far it can have advanced.
            remaining = duration-Fraction(lower_time, quantum)
            if remaining*previous_fast < capacity*step:
                possible = distance-step + remaining*previous_fast/capacity
                break
            lower_time += math.floor(quantum*capacity*step/previous_fast)
            if fast <= 0:
                possible = distance
                break
            if slow > 0 and upper_time is not None:
                upper_time += math.ceil(quantum*capacity*step/slow)
                if upper_time <= duration*quantum:
                    certain = distance
            else:
                upper_time = None
            previous_fast = fast
        low, high = sorted((start+sign*certain, start+sign*possible))
    schema = ("sim_heat.offline_mixed_body_exposure/1" if air_film is not None or shield_stack is not None
              else "sim_heat.offline_body_exposure/1")
    return {**data, "schema": schema, "durationS": str(duration),
            "capacityJPerK": str(capacity), "temperatureBoundsK": list(map(str, (low, high))),
            "bodyEnergyChangeBoundsJ": [str(capacity*(t-start)) for t in (low, high)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256", "port", "reference-k", "slope-per-k",
              "enclosure-k", "area-m2", "emissivity", "sigma", "capacity-j-per-k", "initial-k", "duration-s")
    for field in fields:
        parser.add_argument("--"+field, required=True)
    parser.add_argument('--air-film', nargs=3, metavar=('AIR_K', 'AREA_M2', 'H_W_PER_M2_K'))
    parser.add_argument('--shield', nargs=2, action='append', metavar=('BODY_SIDE', 'ENCLOSURE_SIDE'))
    args = vars(parser.parse_args())
    values = [args[field.replace("-", "_")] for field in fields]
    print(json.dumps(investigate(values[:4], *values[4:], air_film=args["air_film"], shield_stack=args["shield"]), indent=2))
