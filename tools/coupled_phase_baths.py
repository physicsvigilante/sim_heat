"""Follow two finite phase baths through a common storage-free conducting network."""
import argparse
import json

from tools.loaded_thermal_ports import link_conductance
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


def bath(spec):
    if not isinstance(spec, (list, tuple)) or len(spec) != 5:
        raise ValueError("each bath requires port, transition K, latent heat, solid kg and liquid kg")
    port, *values = spec
    labels = ("transition temperature", "specific latent heat", "solid mass", "liquid mass")
    temperature, latent, solid, liquid = [decimal_input(v,k) for k,v in zip(labels,values,strict=True)]
    if min(temperature,latent,solid,liquid) <= 0:
        raise ValueError("both phases and positive transition temperature and latent heat required")
    return port, temperature, latent, solid, liquid


def investigate(inputs, left_bath, right_bath, duration_s):
    left, right = bath(left_bath), bath(right_bath)
    horizon = decimal_input(duration_s,"duration")
    law = terminal_response(*inputs)
    g = link_conductance(law)
    if set(law["terminals"]) != {left[0],right[0]}:
        raise ValueError("phase baths must occupy both distinct terminals")
    difference = left[1]-right[1]
    qlo,qhi = (g*difference).span()
    rate_low,rate_high = sorted((abs(qlo),abs(qhi)))
    if difference and rate_low <= 0:
        raise ValueError("positive through-rate magnitude unresolved")
    limiting = []
    if difference:
        donor,receiver = (left,right) if difference > 0 else (right,left)
        # The donor freezes its available liquid and the receiver melts its solid.
        capacities = {donor[0]: donor[2]*donor[4], receiver[0]: receiver[2]*receiver[3]}
        budget = min(capacities.values())
        limiting = [name for name,capacity in capacities.items() if capacity == budget]
        first,last = budget/rate_high,budget/rate_low
        event = [str(first),str(last)]
        modeled = [str(min(horizon,t)) for t in (first,last)]
        status = "coexisting" if horizon < first else "exhausted" if horizon >= last else "exhaustion_time_uncertain"
        elo,ehi = min(budget,horizon*rate_low), min(budget,horizon*rate_high)
        if difference < 0:
            elo,ehi = -ehi,-elo
    else:
        event,modeled,status = None,[str(horizon)]*2,"coexisting"
        elo = ehi = 0

    inventories = {}
    for (name,t,latent,solid,liquid), (low,high) in ((left,(-ehi,-elo)),(right,(elo,ehi))):
        inventories[name] = {"transitionTemperatureK": str(t), "specificLatentHeatJPerKg": str(latent),
                             "initialSolidKg": str(solid), "initialLiquidKg": str(liquid),
                             "latentEnergyIntoBathBoundsJ": [str(low),str(high)],
                             "remainingSolidBoundsKg": [str(solid-high/latent),str(solid-low/latent)],
                             "remainingLiquidBoundsKg": [str(liquid+low/latent),str(liquid+high/latent)]}
    return {"schema":"sim_heat.offline_coupled_phase_baths/1","leftPort":left[0],"rightPort":right[0],
            "leftToRightHeatRateDuringCoexistenceBoundsW":[str(qlo),str(qhi)],
            "firstExhaustionTimeBoundsS":event,"firstExhaustingPorts":limiting,
            "requestedDurationS":str(horizon),"modeledDurationBoundsS":modeled,
            "plateauStatus":status,"baths":inventories,
            **{key: law[key] for key in ("studySha256","modelSha256","factsSha256","nativeExecuted",
                                         "nativeQualified","independentlyCertifiedReference","runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study","root","facts","facts-sha256","duration-s"):
        parser.add_argument("--"+name,required=True)
    for side in ("left","right"):
        parser.add_argument("--"+side+"-bath",nargs=5,required=True,
                            metavar=("PORT","TRANSITION_K","LATENT_J_PER_KG","SOLID_KG","LIQUID_KG"))
    args = parser.parse_args()
    print(json.dumps(investigate((args.study,args.root,args.facts,args.facts_sha256),
                                 args.left_bath,args.right_bath,args.duration_s),indent=2))
