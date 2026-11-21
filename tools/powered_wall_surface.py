"""Balance an exposed surface of an internally heated conducting network."""
import argparse
from fractions import Fraction as F
from itertools import product
import json

from qualification.h1_n13.conduction import Box
from tools.rod_temperature_profile import rod_peaks
from tools.radiating_surface import exterior_balance, exterior_parameters, physical_port
from tools.rod_generation import generation_from_network
from tools.terminal_response import prepare_steady_network, response_from_network


def investigate(inputs, port, rod_powers, enclosure_k, area_m2, emissivity, sigma, *, air_k=None, h_w_per_m2_k=None, profiles=False):
    facts, candidate, net = prepare_steady_network(*inputs)
    law = response_from_network(facts, candidate, net)
    fixed = generation_from_network(facts, candidate, net, rod_powers)
    opens, resistance = physical_port(law, port)
    absorbed = list(map(F, fixed["generatedPowerToBathBoundsW"][port]))
    # Releasing the port removes this bath's fixed-temperature heat sink.
    # Uniform generation offsets the port's heat supply and raises its open temperature.
    heated = opens[0] + resistance[0]*absorbed[0], opens[1] + resistance[1]*absorbed[1]
    result = exterior_balance(law, port, heated, resistance, *exterior_parameters(
        enclosure_k, area_m2, emissivity, sigma), air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)
    surface = list(map(F, result["surfaceTemperatureBoundsK"]))
    original = F(law["imposedTemperaturesK"][port])
    delta = [t-original for t in surface]
    supplies = {}
    for bath in law["terminals"]:
        if bath == port:
            continue
        start = list(map(F, fixed["netBathSupplyBoundsW"][bath]))
        slope = map(F, law["supplyResponseBoundsWPerK"][bath][port])
        variations = [g*d for g, d in product(slope, delta)]
        supplies[bath] = (start[0]+min(variations), start[1]+max(variations))
    generated = F(fixed["totalGeneratedPowerW"])
    wall = list(map(F, result.get("conductorToSurfaceHeatBoundsW", result["netHeatToEnclosureBoundsW"])))
    lo = max(wall[0], generated + sum(q[0] for q in supplies.values()))
    hi = min(wall[1], generated + sum(q[1] for q in supplies.values()))
    if lo > hi:
        raise ValueError("generation, reservoir and surface heat rates violate steady energy balance")
    result.update(schema="sim_heat.offline_powered_wall_surface/1",
                  rodPowersW={name: source["uniformGeneratedPowerW"] for name, source in fixed["rodsWithGeneration"].items()},
                  totalGeneratedPowerW=str(generated), heatedOpenTemperatureBoundsK=list(map(str, heated)),
                  maintainedBathSupplyBoundsW={name: list(map(str, q)) for name, q in supplies.items()},
                  conductorToSurfaceHeatBoundsW=list(map(str, (lo, hi))))
    if profiles:
        powered = {name: F(watts) for name, watts in result["rodPowersW"].items()}
        port_node = facts["boundaries"][port]["node"]
        result.update(rod_peaks(net, powered, fixed_temperatures={port_node: Box.bounds(*surface)}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "port", "enclosure-k", "area-m2", "emissivity", "sigma"):
        parser.add_argument("--"+field, required=True)
    parser.add_argument("--generate", nargs=2, action="append", required=True, metavar=("ROD", "TOTAL_W"))
    parser.add_argument("--air-k")
    parser.add_argument("--h-w-per-m2-k")
    parser.add_argument('--profiles', action='store_true')
    a = parser.parse_args()
    print(json.dumps(investigate((a.study, a.root, a.facts, a.facts_sha256), a.port, a.generate, a.enclosure_k,
                                 a.area_m2, a.emissivity, a.sigma, air_k=a.air_k, h_w_per_m2_k=a.h_w_per_m2_k, profiles=a.profiles),
                     indent=2))
