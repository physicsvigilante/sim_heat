"""Measure latent heat delivered through a steady conductor while both phases coexist."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import ZERO, interval
from tools.loaded_thermal_ports import link_conductance
from tools.radiating_surface import decimal_input, exterior_parameters, physical_port, surface_balance
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s, exterior=None, surface_port=None):
    return plateau(terminal_response(*inputs),port,transition_k,latent_heat_j_per_kg,
                   solid_kg,liquid_kg,duration_s,exterior,surface_port)


def plateau_power(law, port, transition, exterior, surface_port):
    if port not in law["terminals"]:
        raise ValueError("unknown phase bath port")
    surface = {}
    if exterior is None:
        if surface_port is not None:
            raise ValueError("a radiating surface port requires exterior parameters")
        row = law["supplyResponseBoundsWPerK"][port]
        power = -sum((interval(row[n])*(Fraction(t)-transition)
                      for n,t in law["imposedTemperaturesK"].items() if n != port), ZERO)
        qlo, qhi = power.span()
    else:
        if not isinstance(exterior, (list, tuple)) or len(exterior) != 4:
            raise ValueError("exterior requires enclosure temperature, area, emissivity and sigma")
        environment, area, eps, sigma = exterior_parameters(*exterior)
        if surface_port is not None and (surface_port == port or surface_port not in law["terminals"]):
            raise ValueError("radiating face must occupy a distinct network terminal")
        if len(law["terminals"]) == 2:
            surface_port = next(n for n in law["terminals"] if n != port)
            glo, ghi = link_conductance(law).span()
            temperature, outgoing = surface_balance((transition, transition), (1/ghi, 1/glo),
                                                    environment, eps*sigma*area)
            qlo, qhi = -outgoing[1], -outgoing[0]
        else:
            if surface_port is None:
                raise ValueError("select the radiating face for a multi-terminal network")
            maintained = {**law["imposedTemperaturesK"], port: str(transition)}
            open_temp, resistance = physical_port({**law, "imposedTemperaturesK": maintained}, surface_port)
            temperature, outgoing = surface_balance(open_temp, resistance, environment, eps*sigma*area)
            temperatures = {n: Fraction(t) for n, t in maintained.items()}
            temperatures[surface_port] = interval(temperature)
            inflows = reservoir_inflows(law, surface_port, temperatures)
            qlo, qhi = inflows.pop(port)
            surface["maintainedReservoirInflowBoundsW"] = {
                name: list(map(str, pair)) for name, pair in inflows.items()}
        surface["radiatingSurface"] = {
            "port": surface_port,
            "temperatureBoundsK": list(map(str, temperature)),
            "netHeatToEnclosureBoundsW": list(map(str, outgoing)),
            "enclosureTemperatureK": str(environment), "areaM2": str(area),
            "emissivity": str(eps), "sigmaWPerM2K4": str(sigma)}
    return qlo, qhi, surface


def reservoir_inflows(law, surface_port, temperatures):
    inflows = {}
    for terminal in law["terminals"]:
        if terminal == surface_port:
            continue
        row = law["supplyResponseBoundsWPerK"][terminal]
        inflow = -sum((interval(row[n]) * (t - temperatures[terminal])
                       for n, t in temperatures.items() if n != terminal), ZERO)
        inflows[terminal] = inflow.span()
    return inflows


def plateau(law, port, transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s, exterior=None, surface_port=None):
    phase = phase_inputs(transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s)
    qlo, qhi, surface = plateau_power(law, port, phase[0], exterior, surface_port)
    return plateau_state(law, port, phase, qlo, qhi, surface)


def phase_inputs(transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s):
    transition = decimal_input(transition_k, "transition temperature")
    latent = decimal_input(latent_heat_j_per_kg, "specific latent heat")
    solid = decimal_input(solid_kg, "initial solid mass")
    liquid = decimal_input(liquid_kg, "initial liquid mass")
    horizon = decimal_input(duration_s, "duration")
    if min(transition,latent,solid,liquid) <= 0:
        raise ValueError("positive transition temperature, latent heat and both initial masses required")
    return transition, latent, solid, liquid, horizon


def plateau_state(law, port, phase, qlo, qhi, surface):
    transition, latent, solid, liquid, horizon = phase
    if qlo > 0:
        mode = "melting"
        start, end = solid*latent/qhi, solid*latent/qlo
    elif qhi < 0:
        mode = "freezing"
        start, end = liquid*latent/(-qlo), liquid*latent/(-qhi)
    elif qlo == qhi == 0:
        mode = "equilibrium"
        start = end = None
    else:
        raise ValueError("latent heat-flow direction is unresolved")

    if start is None or horizon < start:
        status = "coexisting"
    elif horizon >= end:
        status = "exhausted"
    else:
        status = "exhaustion_time_uncertain"
    # Signed mass converted from solid to liquid. Clip at the first exhausted
    # phase. Beyond that time only the state at the plateau endpoint is reported.
    def converted(q):
        return min(solid,max(-liquid,q*horizon/latent))
    mlo,mhi = converted(qlo),converted(qhi)
    def bounds(a,b):
        return [str(a),str(b)]
    return {**surface, "schema": "sim_heat.offline_latent_bath/1", "phaseBathPort": port,
            "transitionTemperatureK": str(transition), "specificLatentHeatJPerKg": str(latent),
            "initialSolidKg": str(solid), "initialLiquidKg": str(liquid),
            "requestedDurationS": str(horizon), "phaseProcess": mode, "plateauStatus": status,
            "bathInflowDuringPlateauBoundsW": bounds(qlo,qhi),
            "exhaustionTimeBoundsS": None if start is None else bounds(start,end),
            "modeledDurationBoundsS": bounds(horizon,horizon) if start is None else
                                      bounds(min(horizon,start),min(horizon,end)),
            "latentEnergyIntoBathBoundsJ": bounds(mlo*latent,mhi*latent),
            "remainingSolidBoundsKg": bounds(solid-mhi,solid-mlo),
            "remainingLiquidBoundsKg": bounds(liquid+mlo,liquid+mhi),
            **{k: law[k] for k in ("studySha256","modelSha256","factsSha256","nativeExecuted",
                                   "nativeQualified","independentlyCertifiedReference","runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study","root","facts","facts-sha256","port","transition-k","latent-heat-j-per-kg",
                  "solid-kg","liquid-kg","duration-s"):
        parser.add_argument("--"+field,required=True)
    parser.add_argument("--radiating-exterior", nargs=4,
                        metavar=("ENCLOSURE_K", "AREA_M2", "EMISSIVITY", "SIGMA"),
                        help="release the opposite terminal to a large isothermal enclosure")
    parser.add_argument("--surface-port", help="terminal exposed to the radiating enclosure")
    args = parser.parse_args()
    print(json.dumps(investigate((args.study,args.root,args.facts,args.facts_sha256),args.port,
                                 args.transition_k,args.latent_heat_j_per_kg,args.solid_kg,
                                 args.liquid_kg,args.duration_s,args.radiating_exterior,args.surface_port),indent=2))
