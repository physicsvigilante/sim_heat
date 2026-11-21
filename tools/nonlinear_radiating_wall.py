"""Release one terminal of a linear-k(T) rod network to a large isothermal enclosure."""
import argparse
from fractions import Fraction
import json

from tools.join_variable_conductors import Material, response
from tools.radiating_surface import exterior_parameters
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, reference_k, slope_per_k, enclosure_k, area_m2, emissivity, sigma):
    environment, area, eps, constant = exterior_parameters(enclosure_k, area_m2, emissivity, sigma)
    coefficient = area * eps * constant
    law = terminal_response(*inputs, include_rods=True)
    if port not in law["terminals"]:
        raise ValueError("unknown surface terminal")
    retained = {p: Fraction(t) for p, t in law["imposedTemperaturesK"].items() if p != port}
    temperatures = list(retained.values())
    if coefficient:
        temperatures.append(environment)
    cold, hot = min(temperatures), max(temperatures)
    material = Material(reference_k, slope_per_k, cold, hot)
    fixed = {p: (material.potential(t),)*2 for p, t in retained.items()}
    row = law["supplyResponseBoundsWPerK"][port]
    pivot = tuple(map(Fraction, row[port]))
    if pivot[0] <= 0:
        raise ValueError("surface conductance unresolved")
    offset = response(row, {**fixed, port: (0, 0)})

    def radiation(t):
        return coefficient*(t-environment)*(t+environment)*(t*t+environment*environment)

    def root(index):
        low, high = cold, hot
        for _ in range(128):
            mid = (low+high)/2
            residual = pivot[index]*material.potential(mid) + offset[index] + radiation(mid)
            if residual == 0:
                return mid, mid
            if residual < 0:
                low = mid
            else:
                high = mid
        return low, high

    # The upper residual crosses zero first. Passivity also bounds each root estimate.
    surface = root(1)[0], root(0)[1]
    potentials = {**fixed, port: tuple(map(material.potential, surface))}
    supplies = {p: response(row, potentials) for p, row in law["supplyResponseBoundsWPerK"].items()}
    supplied = supplies.pop(port)
    flux = max(radiation(surface[0]), -supplied[1]), min(radiation(surface[1]), -supplied[0])
    if flux[0] > flux[1]:
        raise ValueError("conductive and radiative heat rates inconsistent")
    return {"schema": "sim_heat.offline_variable_conductivity_surface/1", "releasedPort": port,
            "referenceTemperatureK": str(material.reference), "relativeSlopePerK": str(material.slope),
            "exterior": {"enclosureTemperatureK": str(environment), "areaM2": str(area),
                         "emissivity": str(eps), "sigmaWPerM2K4": str(constant)},
            "surfaceTemperatureBoundsK": list(map(str, surface)), "netHeatToEnclosureBoundsW": list(map(str, flux)),
            "terminalSupplyBoundsW": {p: list(map(str, value)) for p, value in supplies.items()},
            "rodHeatFlowBoundsW": {p: list(map(str, response(row, potentials)))
                                   for p, row in law["rodResponseBoundsWPerK"].items()},
            **{k: law[k] for k in ("modelSha256", "studySha256", "factsSha256", "nativeExecuted",
                                   "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256", "port", "reference-k", "slope-per-k",
              "enclosure-k", "area-m2", "emissivity", "sigma")
    for field in fields:
        parser.add_argument("--"+field, required=True)
    args = vars(parser.parse_args())
    values = [args[field.replace("-", "_")] for field in fields]
    print(json.dumps(investigate(values[:4], *values[4:]), indent=2))
