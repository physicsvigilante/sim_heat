"""Infer an air film from three equally spaced body temperatures and a known conducting port."""
import argparse
from decimal import Context, Decimal
from fractions import Fraction as F
from itertools import product
import json

from tools.radiating_surface import decimal_input, physical_port
from tools.terminal_response import investigate as terminal_response


def log_integer_bounds(n):
    if n == 1:
        return F(0), F(0)
    context = Context(prec=72)
    # Decimal.ln is correctly rounded. Its adjacent decimal numbers enclose
    # the natural logarithm of this exactly represented positive integer.
    rounded = context.ln(Decimal(n))
    return F(context.next_minus(rounded)), F(context.next_plus(rounded))


def investigate(inputs, port, capacity_j_per_k, area_m2, spacing_s, readings_k):
    capacity, area, dt = (decimal_input(x, label) for x, label in zip(
        (capacity_j_per_k, area_m2, spacing_s), ("body heat capacity", "film area", "reading interval"), strict=True))
    if not capacity or not area or not dt:
        raise ValueError("positive capacity, area and equal reading interval required")
    if not isinstance(readings_k, (tuple, list)) or len(readings_k) != 3:
        raise ValueError("exactly three chronological temperature readings required")
    first, middle, last = (decimal_input(v, "body temperature") for v in readings_k)
    change = middle-first
    if not change:
        raise ValueError("a constant first pair cannot identify a relaxation rate")
    ratio = (last-middle)/change
    if not 0 < ratio < 1:
        raise ValueError("increments must have the same sign and decrease in magnitude")
    equilibrium = first + change/(1-ratio)
    if equilibrium < 0:
        raise ValueError("inferred equilibrium below absolute zero")

    law = terminal_response(*inputs)
    opens, resistances = physical_port(law, port)
    rods = 1/resistances[1], 1/resistances[0]
    a, b = log_integer_bounds(ratio.denominator)
    c, d = log_integer_bounds(ratio.numerator)
    total = capacity*(a-d)/dt, capacity*(b-c)/dt
    film = total[0]-rods[1], total[1]-rods[0]
    if film[0] <= 0:
        raise ValueError("readings do not resolve a positive air-film conductance")
    air = [equilibrium + g*(equilibrium-t)/(combined-g)
           for t, g, combined in product(opens, rods, total)]
    if min(air) < 0:
        raise ValueError("nonnegative air temperature unresolved")
    return {
        "schema": "sim_heat.offline_three_reading_cooling/1",
        "releasedPort": port, "capacityJPerK": str(capacity), "filmAreaM2": str(area),
        "spacingS": str(dt), "temperatureReadingsK": list(map(str, (first, middle, last))),
        "successiveIncrementRatio": str(ratio), "equilibriumTemperatureK": str(equilibrium),
        "totalConductanceBoundsWPerK": list(map(str, total)),
        "filmConductanceBoundsWPerK": list(map(str, film)),
        "filmCoefficientBoundsWPerM2K": [str(g/area) for g in film],
        "airTemperatureBoundsK": list(map(str, (min(air), max(air)))),
        "wallOpenTemperatureBoundsK": list(map(str, opens)),
        "wallResistanceBoundsKPerW": list(map(str, resistances)),
        "radiationIncluded": False,
        **{k: law[k] for k in ("modelSha256", "studySha256", "factsSha256", "nativeExecuted",
                                "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "port", "capacity-j-per-k", "area-m2", "spacing-s"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--readings-k", nargs=3, required=True, metavar=("FIRST", "SECOND", "THIRD"))
    args = parser.parse_args()
    print(json.dumps(investigate((args.study, args.root, args.facts, args.facts_sha256), args.port,
                                 args.capacity_j_per_k, args.area_m2, args.spacing_s, args.readings_k), indent=2))
