"""Follow two finite phase baths through a common storage-free conducting network."""
from fractions import Fraction
import argparse
import json

from qualification.h1_n13.conduction import Box
from tools.spherical_conduction import radial_log
from tools.join_thermal_networks import bounds
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


def investigate(inputs, left_bath, right_bath, duration_s, equilibrium_cp=None, transfer_target_j=None, track_duration=False, track_rods=False):
    left, right = bath(left_bath), bath(right_bath)
    horizon = decimal_input(duration_s,"duration")
    law = terminal_response(*inputs, include_rods=track_rods)
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
    result = {"schema":"sim_heat.offline_coupled_phase_baths/1","leftPort":left[0],"rightPort":right[0],
            "leftToRightHeatRateDuringCoexistenceBoundsW":[str(qlo),str(qhi)],
            "firstExhaustionTimeBoundsS":event,"firstExhaustingPorts":limiting,
            "requestedDurationS":str(horizon),"modeledDurationBoundsS":modeled,
            "plateauStatus":status,"baths":inventories,
            **{key: law[key] for key in ("studySha256","modelSha256","factsSha256","nativeExecuted",
                                         "nativeQualified","independentlyCertifiedReference","runnerConsumable")}}


    if equilibrium_cp is not None:
        result["equilibrium"] = equilibrium(left,right,equilibrium_cp)
    if transfer_target_j is not None:
        if equilibrium_cp is None:
            raise ValueError("specific heats required for transfer passage")
        result["transferPassage"] = transfer_passage(left,right,g,result["equilibrium"],transfer_target_j)
    if track_duration or track_rods:
        if equilibrium_cp is None:
            raise ValueError("specific heats required for elapsed-time bath state")
        result["stateAtDuration"] = state_at_time(left, right, g, result["equilibrium"], horizon)
    if track_rods:
        state = result["stateAtDuration"]
        state["rods"] = rod_transfers(law, g, left, right, state)
    return result


def rod_transfers(law, conductance, left, right, state):
    """Scale the donor unit-temperature field on the storage-free network."""
    donor, receiver = sorted((left, right), key=lambda row: row[1], reverse=True)
    def interval(pair):
        return Box.bounds(*map(Fraction, pair))
    baths = state["baths"]
    drive = (interval(baths[donor[0]]["temperatureBoundsK"]) -
             interval(baths[receiver[0]]["temperatureBoundsK"]))
    energy = interval(state["transferredEnergyMagnitudeBoundsJ"])
    result = {}
    for rod, columns in law["rodResponseBoundsWPerK"].items():
        response = interval(columns[donor[0]])
        # For a fixed network the signed fraction of total heat is constant.
        result[rod] = {"heatFlowBoundsW": bounds(response * drive),
                       "transferredHeatBoundsJ": bounds((response / conductance) * energy)}
    return result


def transfer_passage(left,right,conductance,final,target_j):
    target = decimal_input(target_j,"transferred energy")
    return passage_at_energy(left, right, conductance, final, target)


def passage_at_energy(left, right, conductance, final, target):
    hot,cold = sorted((left,right),key=lambda x:x[1],reverse=True)
    limit = -Fraction(final["baths"][hot[0]]["energyIntoBathJ"])
    if target > 0 and target >= limit:
        raise ValueError("target must be strictly below limiting transferred energy for finite passage")
    freeze = hot[2]*hot[4]
    melt = cold[2]*cold[3]
    ch = Fraction(final["hotSolidSpecificHeatJPerKgK"])*(hot[3]+hot[4])
    cc = Fraction(final["coldLiquidSpecificHeatJPerKgK"])*(cold[3]+cold[4])
    def temperatures(energy):
        return (hot[1]-max(0,energy-freeze)/ch,
                cold[1]+max(0,energy-melt)/cc)
    points = sorted({0,target,min(freeze,target),min(melt,target)})
    elapsed = Box.exact(0)
    segments = []
    for a,b in zip(points,points[1:]):
        th,tc = temperatures(a)
        initial = th-tc
        th,tc = temperatures(b)
        end = th-tc
        # The temperature difference is affine in energy between phase events.
        # Integrate dE/(G*deltaT) exactly up to the bounded logarithm.
        if end == initial:
            scaled_time = Box.exact((b-a)/initial)
        else:
            scaled_time = radial_log(initial/end)*((b-a)/(initial-end))
        duration = scaled_time/conductance
        segments.append({"fromJ":str(a),"toJ":str(b),"durationBoundsS":bounds(duration)})
        elapsed += duration
    th,tc = temperatures(target)
    return {"transferredEnergyMagnitudeJ":str(target),"durationBoundsS":bounds(elapsed),
            "segments":segments,"terminalTemperaturesK":{hot[0]:str(th),cold[0]:str(tc)}}


def state_at_time(left, right, conductance, final, horizon):
    hot, cold = sorted((left, right), key=lambda row: row[1], reverse=True)
    maximum = -Fraction(final["baths"][hot[0]]["energyIntoBathJ"])
    # The temperature drive only decreases, so even after a phase transition
    # the initial rate times the elapsed duration bounds the transferred energy.
    rate = conductance * (hot[1] - cold[1])
    rate_low, rate_high = rate.span()
    high = min(maximum, horizon * rate_high)
    plateau_budget = min(hot[2] * hot[4], cold[2] * cold[3])
    low = min(plateau_budget, horizon * rate_low)
    if horizon * rate_high > plateau_budget:
        # Monotone passage time brackets the energy even near asymptotic equilibrium.
        for _ in range(64):
            trial = (low + high) / 2
            passage = passage_at_energy(hot, cold, conductance, final, trial)
            earliest, latest = map(Fraction, passage["durationBoundsS"])
            if horizon < earliest:
                high = trial
            elif horizon > latest:
                low = trial
            else:
                # The rate cannot exceed its initial value as the baths approach.
                low = max(low, trial - rate_high * (latest - horizon))
                high = min(high, trial + rate_high * (horizon - earliest))
                break

    states = {}
    for row, sign, cp_field in ((hot, -1, "hotSolidSpecificHeatJPerKgK"),
                                (cold, 1, "coldLiquidSpecificHeatJPerKgK")):
        port, temperature, latent, solid, liquid = row
        capacity = Fraction(final[cp_field]) * (solid + liquid)
        inventory = liquid if sign < 0 else solid
        endpoints = []
        for energy in (low, high):
            transferred_mass = sign * min(energy / latent, inventory)
            sensible = sign * energy - transferred_mass * latent
            endpoints.append((temperature + sensible / capacity, solid - transferred_mass,
                              liquid + transferred_mass, sign * energy))
        fields = ("temperatureBoundsK", "solidMassBoundsKg", "liquidMassBoundsKg", "energyIntoBathBoundsJ")
        states[port] = {field: list(map(str, sorted(pair)))
                        for field, pair in zip(fields, zip(*endpoints), strict=True)}
    return {"elapsedS": str(horizon), "transferredEnergyMagnitudeBoundsJ": [str(low), str(high)],
            "baths": states}


def equilibrium(left,right,specific_heats):
    if not isinstance(specific_heats,(tuple,list)) or len(specific_heats) != 2:
        raise ValueError("supply hot solid and cold liquid specific heats")
    cs,cl = (decimal_input(value,"specific heat") for value in specific_heats)
    if min(cs,cl) <= 0:
        raise ValueError("positive specific heats required")
    hot,cold = sorted((left,right),key=lambda x:x[1],reverse=True)
    dt = hot[1]-cold[1]
    freeze, melt = hot[2]*hot[4], cold[2]*cold[3]
    ch,cc = cs*(hot[3]+hot[4]),cl*(cold[3]+cold[4])
    if not dt:
        temperature, transfer = hot[1], 0
    elif freeze+ch*dt <= melt:
        temperature, transfer = cold[1], freeze+ch*dt
    elif melt+cc*dt <= freeze:
        temperature, transfer = hot[1], melt+cc*dt
    else:
        # Equate heat lost by the fully solid donor to heat absorbed by
        # the fully liquid receiver, including both completed transitions.
        temperature = (freeze-melt+ch*hot[1]+cc*cold[1])/(ch+cc)
        transfer = freeze+ch*(hot[1]-temperature)
    frozen = min(transfer,freeze)/hot[2]
    melted = min(transfer,melt)/cold[2]
    final = {}
    for row, change, energy in ((hot,-frozen,-transfer),(cold,melted,transfer)):
        name,t,latent,solid,liquid = row
        final[name] = {"solidKg":str(solid-change),"liquidKg":str(liquid+change),
                       "energyIntoBathJ":str(energy),"latentEnergyIntoBathJ":str(change*latent),
                       "sensibleEnergyIntoBathJ":str(energy-change*latent)}
    return {"commonTemperatureK":str(temperature),"baths":final,
            "hotSolidSpecificHeatJPerKgK":str(cs),"coldLiquidSpecificHeatJPerKgK":str(cl)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study","root","facts","facts-sha256","duration-s"):
        parser.add_argument("--"+name,required=True)
    for side in ("left","right"):
        parser.add_argument("--"+side+"-bath",nargs=5,required=True,
                            metavar=("PORT","TRANSITION_K","LATENT_J_PER_KG","SOLID_KG","LIQUID_KG"))
    parser.add_argument("--equilibrium-cp",nargs=2,metavar=("HOT_SOLID_CP","COLD_LIQUID_CP"))
    parser.add_argument("--transfer-target-j")
    parser.add_argument("--track-duration", action="store_true")
    parser.add_argument("--track-rod-flows", action="store_true",
                        help="include signed instantaneous rate and cumulative heat for each rod")
    args = parser.parse_args()
    print(json.dumps(investigate((args.study,args.root,args.facts,args.facts_sha256),
                                 args.left_bath,args.right_bath,args.duration_s,args.equilibrium_cp,args.transfer_target_j,args.track_duration,args.track_rod_flows),indent=2))
