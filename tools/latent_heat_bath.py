"""Measure latent heat delivered through a steady conductor while both phases coexist."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import ZERO, interval
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, duration_s):
    transition = decimal_input(transition_k, "transition temperature")
    latent = decimal_input(latent_heat_j_per_kg, "specific latent heat")
    solid = decimal_input(solid_kg, "initial solid mass")
    liquid = decimal_input(liquid_kg, "initial liquid mass")
    horizon = decimal_input(duration_s, "duration")
    if min(transition,latent,solid,liquid) <= 0:
        raise ValueError("positive transition temperature, latent heat and both initial masses required")
    law = terminal_response(*inputs)
    if port not in law["terminals"]:
        raise ValueError("unknown phase bath port")
    # The terminal law gives supply into the conductor. Shift all temperatures
    # by the new bath temperature; negate supply for heat entering the bath.
    row = law["supplyResponseBoundsWPerK"][port]
    power = -sum((interval(row[n])*(Fraction(t)-transition)
                  for n,t in law["imposedTemperaturesK"].items() if n != port), ZERO)
    qlo,qhi = power.span()
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
    return {"schema": "sim_heat.offline_latent_bath/1", "phaseBathPort": port,
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
    args = parser.parse_args()
    print(json.dumps(investigate((args.study,args.root,args.facts,args.facts_sha256),args.port,
                                 args.transition_k,args.latent_heat_j_per_kg,args.solid_kg,
                                 args.liquid_kg,args.duration_s),indent=2))
