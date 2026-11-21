"""Find the enclosure temperature that leaves a supported phase bath in balance."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import ZERO, interval
from tools.join_thermal_networks import bounds
from tools.radiating_surface import decimal_input, radiative_properties
from tools.radiative_gap import fourth_root_bounds
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, bath_port, surface_port, transition_k, area_m2, emissivity, sigma):
    law = terminal_response(*inputs)
    rows = law["supplyResponseBoundsWPerK"]
    if bath_port == surface_port or bath_port not in rows or surface_port not in rows:
        raise ValueError("choose distinct bath and surface terminals")
    transition = decimal_input(transition_k, "transition temperature")
    area, eps, constant = radiative_properties(area_m2, emissivity, sigma)
    if not transition or not eps:
        raise ValueError("positive transition temperature and emissivity required")
    coupling = interval(rows[bath_port][surface_port])
    if coupling.high >= 0:
        raise ValueError("resolved thermal coupling between bath and surface required")

    # Shift every maintained temperature by the transition temperature. A zero
    # bath supply then determines the required surface temperature directly.
    offsets = {n: Fraction(t) - transition for n, t in law["imposedTemperaturesK"].items()
               if n not in (bath_port, surface_port)}
    def maintained_supply(row):
        return sum((interval(row[n]) * delta for n, delta in offsets.items()), ZERO)
    delta = -maintained_supply(rows[bath_port]) / coupling
    low, high = (transition + delta).span()
    if low < 0:
        raise ValueError("balance requires a negative or unresolved absolute surface temperature")
    supplied = interval(rows[surface_port][surface_port]) * delta + maintained_supply(rows[surface_port])
    qlo, qhi = supplied.span()
    coefficient = area * eps * constant
    lo4, hi4 = low**4 + qlo/coefficient, high**4 + qhi/coefficient
    if lo4 < 0:
        raise ValueError("balance requires a negative or unresolved enclosure fourth power")
    return {"schema": "sim_heat.offline_phase_balance_temperature/1", "bathPort": bath_port,
            "radiatingSurfacePort": surface_port, "transitionTemperatureK": str(transition),
            "surfaceTemperatureBoundsK": [str(low), str(high)],
            "netHeatFromEnclosureBoundsW": bounds(supplied),
            "balanceEnclosureTemperatureBoundsK": fourth_root_bounds(lo4, hi4),
            "areaM2": str(area), "emissivity": str(eps), "sigmaWPerM2K4": str(constant),
            **{k: law[k] for k in ("modelSha256", "studySha256", "factsSha256", "nativeExecuted",
                                    "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "bath-port", "surface-port",
                  "transition-k", "area-m2", "emissivity", "sigma"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(investigate((args.study, args.root, args.facts, args.facts_sha256),
                                 args.bath_port, args.surface_port, args.transition_k,
                                 args.area_m2, args.emissivity, args.sigma), indent=2))
