"""Time to reach a new single-phase temperature after a latent plateau."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import Box
from tools.join_thermal_networks import bounds
from tools.latent_heat_bath import plateau
from tools.radiating_surface import decimal_input, physical_port
from tools.spherical_conduction import radial_log
from tools.terminal_response import investigate as terminal_response


def investigate(inputs, port, transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg,
                final_specific_heat_j_per_kg_k, target_k):
    cp = decimal_input(final_specific_heat_j_per_kg_k, "specific heat of final phase")
    target = decimal_input(target_k, "target temperature")
    if min(cp,target) <= 0:
        raise ValueError("positive final-phase heat capacity and target temperature required")
    law = terminal_response(*inputs)
    initial = plateau(law,port,transition_k,latent_heat_j_per_kg,solid_kg,liquid_kg,"0")
    tm = Fraction(initial["transitionTemperatureK"])
    heating = initial["phaseProcess"] == "melting"
    if initial["phaseProcess"] == "equilibrium" or (target-tm)*(1 if heating else -1) <= 0:
        raise ValueError("target must lie beyond the plateau in the direction of heat transfer")
    (low,high), r = physical_port(law, port)
    if (heating and low <= target) or (not heating and high >= target):
        raise ValueError("finite target passage before equilibrium is unresolved or unreachable")
    mass = Fraction(initial["initialSolidKg"])+Fraction(initial["initialLiquidKg"])
    # T(t) approaches the maintained network's open temperature with tau = RC.
    ratios = [(t-tm)/(t-target) for t in (low,high)]
    log_lo = radial_log(min(ratios)).span()[0]
    log_hi = radial_log(max(ratios)).span()[1]
    sensible = Box.bounds(*r)*(mass*cp)*Box.bounds(log_lo,log_hi)
    phase_time = Box.bounds(*map(Fraction,initial["exhaustionTimeBoundsS"]))
    latent = Fraction(initial["specificLatentHeatJPerKg"])
    converted = Fraction(initial["initialSolidKg"] if heating else initial["initialLiquidKg"])
    q_latent = converted*latent*(1 if heating else -1)
    q_sensible = mass*cp*(target-tm)
    return {"schema": "sim_heat.offline_phase_bath_target/1", "phaseBathPort": port,
            "finalPhase": "liquid" if heating else "solid", "targetTemperatureK": str(target),
            "finalSpecificHeatJPerKgK": str(cp), "transitionTemperatureK": str(tm),
            "initialSolidKg": initial["initialSolidKg"], "initialLiquidKg": initial["initialLiquidKg"],
            "specificLatentHeatJPerKg": initial["specificLatentHeatJPerKg"],
            "plateauDurationBoundsS": initial["exhaustionTimeBoundsS"],
            "sensibleDurationBoundsS": bounds(sensible), "totalDurationBoundsS": bounds(phase_time+sensible),
            "latentEnergyIntoBathJ": str(q_latent), "sensibleEnergyIntoBathJ": str(q_sensible),
            "totalEnergyIntoBathJ": str(q_latent+q_sensible),
            **{k: law[k] for k in ("modelSha256","studySha256","factsSha256","nativeExecuted",
                                   "nativeQualified","independentlyCertifiedReference","runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("study","root","facts","facts-sha256","port","transition-k","latent-heat-j-per-kg",
                "solid-kg","liquid-kg","final-specific-heat-j-per-kg-k","target-k"):
        parser.add_argument("--"+key,required=True)
    a = parser.parse_args()
    print(json.dumps(investigate((a.study,a.root,a.facts,a.facts_sha256),a.port,a.transition_k,
                                 a.latent_heat_j_per_kg,a.solid_kg,a.liquid_kg,
                                 a.final_specific_heat_j_per_kg_k,a.target_k),indent=2))
