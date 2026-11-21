"""Bound the time for an isothermal body on a rod network to reach a temperature."""
import argparse
from fractions import Fraction
import json
import math

from tools.join_variable_conductors import Material
from tools.radiative_gap import shield_exchange
from tools.radiating_surface import decimal_input, exterior_parameters
from tools.terminal_response import investigate as terminal_response


def prepare_body(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma, start, target=None, *, shield_stack=None):
    env, area, eps, constant = exterior_parameters(enclosure_k, area_m2, emissivity, sigma)
    coefficient = area*eps*constant
    shields = []
    if shield_stack is not None:
        if not isinstance(shield_stack, (tuple, list)) or not shield_stack:
            raise ValueError("one or more two-sided shields required")
        # The far side is a black plane at the enclosure temperature. Thin
        # shields equilibrate instantaneously and store no energy.
        shields, _, coefficient = shield_exchange(area*constant, eps, Fraction(1), shield_stack)
    law = terminal_response(*inputs)
    if port not in law["terminals"]:
        raise ValueError("unknown body terminal")
    baths = {p: Fraction(t) for p, t in law["imposedTemperaturesK"].items() if p != port}
    # Radiation acts directly on the body. Only the rods need positive conductivity.
    domain = [start, *baths.values()]
    if target is not None:
        domain.append(target)
    elif coefficient:
        domain.append(env)
    material = Material(reference_k, slope_per_k, min(domain), max(domain))
    row = law["supplyResponseBoundsWPerK"][port]
    couplings = []
    for p, bath in baths.items():
        low, high = map(Fraction, row[p])
        if low > 0:
            raise ValueError("inconsistent passive network coupling")
        couplings.append((material.potential(bath), max(0, -high), -low))

    def radiation(t):
        return coefficient*(env-t)*(env+t)*(env*env+t*t)

    def power(t):
        # Response rows sum to zero. Temperature differences also preserve exact equilibrium.
        value = material.potential(t)
        low = high = radiation(t)
        for bath, gmin, gmax in couplings:
            endpoints = (gmin*(bath-value), gmax*(bath-value))
            low += min(endpoints)
            high += max(endpoints)
        return low, high

    data = {"bodyPort": port,
            "referenceTemperatureK": str(material.reference), "relativeSlopePerK": str(material.slope),
            "exterior": {"enclosureTemperatureK": str(env), "areaM2": str(area), "emissivity": str(eps),
                         "sigmaWPerM2K4": str(constant)},
            "initialTemperatureK": str(start),
            **{k: law[k] for k in ("modelSha256", "studySha256", "factsSha256", "nativeExecuted",
                                   "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")}}
    if shields:
        data["exterior"].update(
            shieldFacesBodyToEnclosure=[list(map(str, pair)) for pair in shields],
            radiantExchangeCoefficientWPerK4=str(coefficient),
            enclosureEmissivity="1", shieldHeatStorage="zero",
        )
    return data, power, radiation, (min(domain), max(domain))


def investigate(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma,
                capacity_j_per_k, initial_k, target_k, *, track_energy=False, shield_stack=None):
    capacity = decimal_input(capacity_j_per_k, "heat capacity")
    start = decimal_input(initial_k, "initial temperature")
    target = decimal_input(target_k, "target temperature")
    if capacity <= 0:
        raise ValueError("positive heat capacity required")
    data, power, radiation, _ = prepare_body(inputs, port, reference_k, slope_per_k, enclosure_k,
                                             area_m2, emissivity, sigma, start, target, shield_stack=shield_stack)
    data.update(schema="sim_heat.offline_radiating_body_target/1", capacityJPerK=str(capacity),
                targetTemperatureK=str(target))

    if shield_stack is not None:
        data["schema"] = "sim_heat.offline_shielded_body_target/1"

    def directed_power(t):
        low, high = power(t)
        return (low, high) if target >= start else (-high, -low)

    if track_energy:
        data["energyToBodyBoundsJ"] = None
    if target == start:
        if track_energy:
            data["energyToBodyBoundsJ"] = {"radiation": ["0", "0"], "conduction": ["0", "0"]}
        return {**data, "status": "already_at_target", "timeBoundsS": ["0", "0"]}
    end_low, end_high = directed_power(target)
    if end_high <= 0:
        return {**data, "status": "unreachable_in_finite_time", "timeBoundsS": None}
    if end_low <= 0:
        return {**data, "status": "unresolved_near_equilibrium", "timeBoundsS": None}

    # Along either reachable path the directed heating/cooling power decreases.
    # Endpoint sums enclose C integral d|T|/P. Round each term outward so the
    # denominators from hundreds of unrelated reciprocals cannot grow unbounded.
    panels = 512
    step = (target-start)/panels
    energy = capacity*abs(step)
    quantum = 10**18
    previous_high = directed_power(start)[1]
    lower_ticks = upper_ticks = 0
    rad_low_ticks = rad_high_ticks = 0
    previous_rad = radiation(start)
    for i in range(1, panels+1):
        low, high = directed_power(start+i*step)
        lower_ticks += math.floor(quantum*energy/previous_high)
        upper_ticks += math.ceil(quantum*energy/low)
        if track_energy:
            current_rad = radiation(start+i*step)
            # Radiation is monotone in temperature, including across a sign change.
            # Combining both power endpoints with both residence-time bounds
            # also encloses panels on which radiation opposes the net heat flow.
            products = [p*energy/denom for p in (previous_rad, current_rad)
                        for denom in (previous_high, low)]
            rad_low_ticks += math.floor(quantum*min(products))
            rad_high_ticks += math.ceil(quantum*max(products))
            previous_rad = current_rad
        previous_high = high
    if track_energy:
        rad_low, rad_high = (Fraction(ticks, quantum) for ticks in (rad_low_ticks, rad_high_ticks))
        stored = capacity*(target-start)
        data["energyToBodyBoundsJ"] = {"radiation": [str(rad_low), str(rad_high)],
                                      "conduction": [str(stored-rad_high), str(stored-rad_low)]}
    return {**data, "status": "reached", "bodyEnergyChangeJ": str(capacity*(target-start)),
            "timeBoundsS": [str(Fraction(v, quantum)) for v in (lower_ticks, upper_ticks)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256", "port", "reference-k", "slope-per-k",
              "enclosure-k", "area-m2", "emissivity", "sigma", "capacity-j-per-k", "initial-k", "target-k")
    for field in fields:
        parser.add_argument("--"+field, required=True)
    parser.add_argument('--shield', nargs=2, action='append', metavar=('BODY_SIDE', 'ENCLOSURE_SIDE'))
    parser.add_argument('--track-energy', action='store_true')
    args = vars(parser.parse_args())
    values = [args[field.replace("-", "_")] for field in fields]
    print(json.dumps(investigate(values[:4], *values[4:], track_energy=args["track_energy"], shield_stack=args["shield"]), indent=2))
