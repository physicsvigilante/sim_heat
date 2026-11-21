"""Predict a new cooling experiment using a measured air-film calibration."""
import argparse
from decimal import Context, Decimal
from fractions import Fraction as F
from itertools import product
import json

from tools.radiating_surface import decimal_input, physical_port
from tools.terminal_response import investigate as terminal_response
from tools.three_reading_cooling import investigate as calibrate, log_integer_bounds


def decay_bounds(z):
    """Outward bounds for exp(-z) on the nonnegative real axis."""
    if not z:
        return F(1), F(1)
    if z >= 256:
        return F(0), F(1, 2**256)
    ctx = Context(prec=72)
    exponent = ctx.divide(Decimal(-z.numerator), Decimal(z.denominator))
    low = ctx.next_minus(ctx.exp(ctx.next_minus(exponent)))
    high = ctx.next_plus(ctx.exp(ctx.next_plus(exponent)))
    return max(F(0), F(low)), min(F(1), F(high))


def investigate(calibration_inputs, calibration_port, calibration_capacity, calibration_area, spacing_s,
                readings_k, new_inputs, new_port, new_capacity, new_area, initial_k, duration_s):
    fit = calibrate(calibration_inputs, calibration_port, calibration_capacity, calibration_area, spacing_s, readings_k)
    area, capacity, start, duration = (decimal_input(v, label) for v, label in zip(
        (new_area, new_capacity, initial_k, duration_s),
        ("new exposed area", "new heat capacity", "new initial temperature", "new duration"), strict=True))
    if area <= 0 or capacity <= 0:
        raise ValueError("new exposed area and heat capacity must be positive")
    law = terminal_response(*new_inputs)
    opens, resistance = physical_port(law, new_port)
    film = [area*g for g in map(F, fit["filmCoefficientBoundsWPerM2K"])]
    air = list(map(F, fit["airTemperatureBoundsK"]))
    rod = [1/r for r in reversed(resistance)]
    # Boxes also cover the correlation between the fitted air and coefficient.
    equilibria = [(g*t + h*a)/(g+h) for g, t, h, a in product(rod, opens, film, air)]
    eq = min(equilibria), max(equilibria)
    tau = capacity/(rod[1]+film[1]), capacity/(rod[0]+film[0])
    decay = decay_bounds(duration/tau[0])[0], decay_bounds(duration/tau[1])[1]
    final = [d*start + (1-d)*e for d, e in product(decay, eq)]
    log2 = log_integer_bounds(2)
    return {
        "schema": "sim_heat.offline_calibrated_wall_cooling/1", "calibration": fit,
        "newWall": {"releasedPort": new_port, **{k: law[k] for k in ("modelSha256", "studySha256", "factsSha256")}},
        "newAreaM2": str(area), "newCapacityJPerK": str(capacity), "initialTemperatureK": str(start),
        "durationS": str(duration), "newEquilibriumTemperatureBoundsK": list(map(str, eq)),
        "timeConstantBoundsS": list(map(str, tau)),
        "halfLifeBoundsS": list(map(str, (tau[0]*log2[0], tau[1]*log2[1]))),
        "temperatureAfterExposureBoundsK": list(map(str, (min(final), max(final)))),
        "nativeExecuted": False, "nativeQualified": False, "independentlyCertifiedReference": False,
        "runnerConsumable": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "new"):
        parser.add_argument("--" + name, nargs=4, required=True, metavar=("STUDY", "ROOT", "FACTS", "SHA256"))
        for field in ("port", "capacity", "area"):
            parser.add_argument("--" + name + "-" + field, required=True)
    parser.add_argument("--readings-k", nargs=3, required=True)
    for name in ("spacing-s", "initial-k", "duration-s"):
        parser.add_argument("--" + name, required=True)
    a = parser.parse_args()
    print(json.dumps(investigate(a.original, a.original_port, a.original_capacity, a.original_area,
                                 a.spacing_s, a.readings_k, a.new, a.new_port, a.new_capacity, a.new_area,
                                 a.initial_k, a.duration_s), indent=2))
