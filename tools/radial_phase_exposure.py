"""Track a two-phase inventory inside an insulated radial vessel through sequential exterior stages."""
import argparse
from fractions import Fraction as F
import json

from tools.offline_provenance import offline_provenance
from tools.radial_phase_bath import bath_inflow_from_law
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


def _pair(a, b):
    return [str(a), str(b)]


def solve_from_law(law, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                   solid_kg, liquid_kg, inner_radius_m, layers, emissivity, sigma, stages,
                   cylinder_length_m=None):
    transition = decimal_input(transition_k, "transition temperature")
    latent = decimal_input(latent_heat_j_per_kg, "specific latent heat")
    solid = decimal_input(solid_kg, "initial solid mass")
    liquid = decimal_input(liquid_kg, "initial liquid mass")
    if min(transition, latent, solid, liquid) <= 0:
        raise ValueError("positive transition temperature, latent heat and both initial masses required")
    stages = tuple(stages)
    if not stages:
        raise ValueError("one or more exterior stages required")
    schedule = []
    for entry in stages:
        if not isinstance(entry, (list, tuple)) or len(entry) != 5:
            raise ValueError("each stage requires name, air K, film coefficient, enclosure K and duration s")
        name, air_k, h_w_per_m2_k, enclosure_k, duration_s = entry
        if type(name) is not str or not name:
            raise ValueError("each stage requires a nonempty string name")
        decimal_input(air_k, "air temperature")
        decimal_input(h_w_per_m2_k, "convective heat transfer coefficient")
        decimal_input(enclosure_k, "enclosure temperature")
        duration = decimal_input(duration_s, "stage duration")
        if duration <= 0:
            raise ValueError("positive stage duration required")
        schedule.append((name, air_k, h_w_per_m2_k, enclosure_k, duration))

    layers = tuple(layers)
    minimum, maximum = -liquid * latent, solid * latent
    low = high = elapsed = F(0)
    history = []
    last_shell = None

    for idx, (name, air_k, h_w_per_m2_k, enclosure_k, duration) in enumerate(schedule):
        qlo, qhi, details = bath_inflow_from_law(
            law, phase_port, surface_port, transition, inner_radius_m, layers,
            enclosure_k, emissivity, sigma, cylinder_length_m,
            air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)
        shell = details["radialShell"]
        last_shell = shell

        status = "coexisting"
        tlo = thi = duration
        if qlo > 0:
            mode = "melting"
            first, last = (maximum - high) / qhi, (maximum - low) / qlo
            if duration >= first:
                status = "exhausted" if duration >= last else "exhaustion_time_uncertain"
                tlo, thi = first, min(duration, last)
        elif qhi < 0:
            mode = "freezing"
            first, last = (low - minimum) / (-qlo), (high - minimum) / (-qhi)
            if duration >= first:
                status = "exhausted" if duration >= last else "exhaustion_time_uncertain"
                tlo, thi = first, min(duration, last)
        elif qlo == qhi == 0:
            mode = "equilibrium"
        else:
            mode = "unresolved"
            can_exhaust_solid = high + max(F(0), qhi) * duration >= maximum
            can_exhaust_liquid = low + min(F(0), qlo) * duration <= minimum
            if can_exhaust_solid or can_exhaust_liquid:
                status = "exhaustion_time_uncertain"
                candidates = []
                if can_exhaust_solid:
                    candidates.append((maximum - high) / qhi)
                if can_exhaust_liquid:
                    candidates.append((low - minimum) / (-qlo))
                tlo, thi = min(candidates), duration

        low = max(minimum, min(maximum, low + qlo * duration))
        high = max(minimum, min(maximum, high + qhi * duration))
        history.append({
            "stageIndex": idx,
            "name": name,
            "airTemperatureK": shell["airTemperatureK"],
            "convectionCoefficientWPerM2K": shell["convectionCoefficientWPerM2K"],
            "enclosureTemperatureK": shell["enclosureTemperatureK"],
            "requestedDurationS": str(duration),
            "startS": str(elapsed),
            "endBoundsS": _pair(elapsed + tlo, elapsed + thi),
            "phaseProcess": mode,
            "plateauStatus": status,
            "bathInflowBoundsW": _pair(qlo, qhi),
            "shellOutwardHeatRateBoundsW": shell["outwardHeatRateBoundsW"],
            "netHeatToAirBoundsW": shell["netHeatToAirBoundsW"],
            "netHeatToEnclosureBoundsW": shell["netHeatToEnclosureBoundsW"],
            "outerSurfaceTemperatureBoundsK": shell["surfaces"][-1]["temperatureBoundsK"],
            "maintainedReservoirInflowBoundsW": details["maintainedReservoirInflowBoundsW"],
            "cumulativeEnergyIntoBathBoundsJ": _pair(low, high),
            "solidMassBoundsKg": _pair(solid - high / latent, solid - low / latent),
            "liquidMassBoundsKg": _pair(liquid + low / latent, liquid + high / latent),
        })
        if status != "coexisting":
            break
        elapsed += duration

    return {
        "schema": "sim_heat.offline_radial_phase_exposure/1",
        "phaseBathPort": phase_port,
        "surfacePort": surface_port,
        "geometry": last_shell["geometry"],
        "cylinderLengthM": last_shell["cylinderLengthM"],
        "innerRadiusM": str(decimal_input(inner_radius_m, "inner radius")),
        "layers": last_shell["layers"],
        "emissivity": last_shell["emissivity"],
        "sigmaWPerM2K4": last_shell["sigmaWPerM2K4"],
        "transitionTemperatureK": str(transition),
        "specificLatentHeatJPerKg": str(latent),
        "initialSolidKg": str(solid),
        "initialLiquidKg": str(liquid),
        "requestedStages": [
            {"name": n, "airTemperatureK": str(F(a)), "convectionCoefficientWPerM2K": str(F(h)),
             "enclosureTemperatureK": str(F(e)), "durationS": str(d)}
            for n, a, h, e, d in schedule
        ],
        "completedAllStages": len(history) == len(schedule) and history[-1]["plateauStatus"] == "coexisting",
        "finalPlateauStatus": history[-1]["plateauStatus"],
        "modeledDurationBoundsS": history[-1]["endBoundsS"],
        "cumulativeEnergyIntoBathBoundsJ": _pair(low, high),
        "finalSolidMassBoundsKg": history[-1]["solidMassBoundsKg"],
        "finalLiquidMassBoundsKg": history[-1]["liquidMassBoundsKg"],
        "stages": history,
        **offline_provenance(law),
    }


def investigate(inputs, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                solid_kg, liquid_kg, inner_radius_m, layers, emissivity, sigma, stages,
                cylinder_length_m=None):
    return solve_from_law(
        terminal_response(*inputs), phase_port, surface_port, transition_k,
        latent_heat_j_per_kg, solid_kg, liquid_kg, inner_radius_m, layers, emissivity,
        sigma, stages, cylinder_length_m)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "phase-port", "surface-port",
                  "transition-k", "latent-heat-j-per-kg", "solid-kg", "liquid-kg",
                  "inner-radius-m", "emissivity", "sigma"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--layer", action="append", nargs=2, required=True,
                   metavar=("R_OUT_M", "K_W_PER_M_K"))
    p.add_argument("--stage", action="append", nargs=5, required=True,
                   metavar=("NAME", "AIR_K", "H_W_PER_M2_K", "ENCLOSURE_K", "DURATION_S"))
    p.add_argument("--cylinder-length-m")
    a = p.parse_args()
    print(json.dumps(investigate(
        (a.study, a.root, a.facts, a.facts_sha256), a.phase_port, a.surface_port,
        a.transition_k, a.latent_heat_j_per_kg, a.solid_kg, a.liquid_kg,
        a.inner_radius_m, a.layer, a.emissivity, a.sigma, a.stage, a.cylinder_length_m),
        indent=2))
