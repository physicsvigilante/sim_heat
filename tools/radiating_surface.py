"""Balance a released conductor-network port against one large isothermal enclosure."""
import argparse
from fractions import Fraction
import json
import re

from tools.loaded_thermal_ports import port_equivalent
from tools.terminal_response import investigate as terminal_response


def decimal_input(text, label):
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,18})?", text):
        raise ValueError(f"{label} requires an unsigned SI decimal")
    return Fraction(text)


def surface_root(open_k, resistance, enclosure_k, coefficient):
    # The residual increases strictly for nonnegative Kelvin temperatures.
    low, high = sorted((open_k, enclosure_k))
    for _ in range(64):
        mid = (low+high)/2
        residual = mid-open_k + resistance*coefficient*(mid**4-enclosure_k**4)
        if residual == 0:
            return mid, mid
        if residual > 0:
            high = mid
        else:
            low = mid
    return low, high


def physical_port(law, port):
    open_temp, resistance = port_equivalent(law, port)
    # Passive conduction puts the open temperature within the maintained bath range.
    baths = [Fraction(t) for name, t in law["imposedTemperaturesK"].items() if name != port]
    low = max(open_temp.span()[0], min(baths))
    high = min(open_temp.span()[1], max(baths))
    rlo, rhi = resistance.span()
    if low < 0 or low > high or rlo <= 0:
        raise ValueError("physical open-port enclosure unresolved")
    return (low, high), (rlo, rhi)


def investigate(study, root, facts, facts_sha256, port, enclosure_k, area_m2, emissivity, sigma):
    environment = decimal_input(enclosure_k, "enclosure temperature")
    area = decimal_input(area_m2, "surface area")
    eps = decimal_input(emissivity, "emissivity")
    constant = decimal_input(sigma, "Stefan-Boltzmann constant")
    if area <= 0 or eps > 1 or constant <= 0:
        raise ValueError("positive area and sigma and emissivity in [0,1] required")
    law = terminal_response(study, root, facts, facts_sha256)
    (open_low, open_high), (rlo, rhi) = physical_port(law, port)
    low, high = open_low, open_high
    coefficient = eps*constant*area
    if coefficient:
        # The root grows with open temperature. At fixed open temperature it
        # moves monotonically toward the enclosure temperature as resistance grows.
        brackets = [surface_root(t, r, environment, coefficient)
                    for t in (low, high) for r in (rlo, rhi)]
        low, high = min(x[0] for x in brackets), max(x[1] for x in brackets)
    flux = [coefficient*(t**4-environment**4) for t in (low, high)]
    # Both powers describe the same steady energy transfer. At very high
    # temperatures a narrow temperature bracket can span a wide range in T^4.
    conductive = [drop/r for drop in (open_low-high, open_high-low) for r in (rlo,rhi)]
    flux = [max(flux[0], min(conductive)), min(flux[1], max(conductive))]
    if flux[0] > flux[1]:
        raise ValueError("steady surface heat-rate enclosures are inconsistent")
    return {"schema": "sim_heat.offline_radiating_surface/1", "releasedPort": port,
            "exterior": {"enclosureTemperatureK": str(environment), "areaM2": str(area),
                         "emissivity": str(eps), "sigmaWPerM2K4": str(constant)},
            "surfaceTemperatureBoundsK": [str(low), str(high)],
            "netHeatToEnclosureBoundsW": list(map(str, flux)),
            **{k: law[k] for k in ("modelSha256", "studySha256", "factsSha256", "nativeExecuted",
                                   "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study", "root", "facts", "facts-sha256", "port", "enclosure-k",
                 "area-m2", "emissivity", "sigma"):
        parser.add_argument("--"+name, required=True)
    args = vars(parser.parse_args())
    print(json.dumps(investigate(**args), indent=2))
