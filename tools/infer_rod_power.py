"""Infer one rod's uniform generation from a surface thermometer and known heat losses."""
import argparse
from fractions import Fraction as F
from itertools import product
import json

from tools.radiating_surface import decimal_input, exterior_parameters, physical_port
from tools.rod_generation import generation_from_network
from tools.terminal_response import prepare_steady_network, response_from_network


def investigate(inputs, port, unknown_rod, known_powers, surface_low_k, surface_high_k,
                enclosure_k, area_m2, emissivity, sigma, *, air_k=None, h_w_per_m2_k=None):
    temperatures = tuple(decimal_input(x, "surface temperature") for x in (surface_low_k, surface_high_k))
    if temperatures[0] > temperatures[1]:
        raise ValueError("surface temperature bounds must be ordered")
    env, area, eps, constant = exterior_parameters(enclosure_k, area_m2, emissivity, sigma)
    if (air_k is None) != (h_w_per_m2_k is None):
        raise ValueError("air temperature and film coefficient required together")
    air = decimal_input(air_k, "air temperature") if air_k is not None else None
    h = decimal_input(h_w_per_m2_k, "film coefficient") if air is not None else F(0)
    exterior = {"enclosureTemperatureK": str(env), "areaM2": str(area),
                "emissivity": str(eps), "sigmaWPerM2K4": str(constant)}
    if air is not None:
        exterior.update(airTemperatureK=str(air), convectionCoefficientWPerM2K=str(h))

    facts, candidate, net = prepare_steady_network(*inputs)
    law = response_from_network(facts, candidate, net)
    opens, resistances = physical_port(law, port)
    unit = generation_from_network(facts, candidate, net, [(unknown_rod, "1")])
    share = tuple(map(F, unit["generatedPowerToBathBoundsW"][port]))
    if share[0] <= 0:
        raise ValueError("surface sensitivity to the chosen rod is zero or unresolved")
    known_powers = list(known_powers)
    if any(rod == unknown_rod for rod, _ in known_powers):
        raise ValueError("the inferred rod cannot also have a prescribed power")
    offset = (F(0), F(0))
    known = {}
    if known_powers:
        background = generation_from_network(facts, candidate, net, known_powers)
        offset = tuple(map(F, background["generatedPowerToBathBoundsW"][port]))
        known = {rod: record["uniformGeneratedPowerW"] for rod, record in background["rodsWithGeneration"].items()}

    def required_at(t, open_k, r, fixed_heat):
        loss = area*eps*constant*(t**4-env**4)
        if air is not None:
            loss += area*h*(t-air)
        return loss + (t-open_k)/r - fixed_heat

    # Loss to each external bath and the wall's passive load both increase
    # with the thermometer reading. Evaluate the enclosing port parameters.
    powers = [required_at(t, o, r, q)/s for t, o, r, q, s in
              product(temperatures, opens, resistances, offset, share)]
    if min(powers) < 0:
        raise ValueError("temperature band cannot establish a nonnegative rod source")
    return {
        "schema": "sim_heat.offline_rod_power_from_surface/1", "releasedPort": port, "unknownRod": unknown_rod,
        "surfaceTemperatureBoundsK": list(map(str, temperatures)), "knownRodPowersW": known,
        "unitSourceShareAtPortBounds": list(map(str, share)), "exterior": exterior,
        "inferredRodPowerBoundsW": list(map(str, (min(powers), max(powers)))),
        **{k: candidate[k] for k in ("modelSha256", "studySha256", "factsSha256", "nativeExecuted",
                                      "nativeQualified", "independentlyCertifiedReference", "runnerConsumable")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "port", "unknown-rod", "enclosure-k",
                  "area-m2", "emissivity", "sigma"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--surface-k", nargs=2, required=True, metavar=("LOW", "HIGH"))
    parser.add_argument("--generate", nargs=2, action="append", default=[], metavar=("KNOWN_ROD", "TOTAL_W"))
    parser.add_argument("--air-k")
    parser.add_argument("--h-w-per-m2-k")
    a = parser.parse_args()
    print(json.dumps(investigate((a.study, a.root, a.facts, a.facts_sha256), a.port, a.unknown_rod, a.generate,
                                 *a.surface_k, a.enclosure_k, a.area_m2, a.emissivity, a.sigma,
                                 air_k=a.air_k, h_w_per_m2_k=a.h_w_per_m2_k), indent=2))
