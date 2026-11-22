"""Select a stocked radial insulation outer radius that survives a multi-stage exterior schedule."""
import argparse
import json

from tools.offline_provenance import offline_provenance
from tools.radial_phase_exposure import solve_from_law as solve_exposure_from_law
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


SCHEDULE_STATUS = {
    "coexisting": "survives_schedule",
    "exhausted": "exhausts_during_schedule",
    "exhaustion_time_uncertain": "unresolved",
}


def smallest_established_surviving(rows):
    for row in rows:
        if row["scheduleStatus"] == "survives_schedule":
            return row["outerRadiusM"]
        if row["scheduleStatus"] == "unresolved":
            break
    return None


def select_from_law(law, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                    solid_kg, liquid_kg, inner_radius_m, inner_layers, coating_k, radii,
                    emissivity, sigma, stages, cylinder_length_m=None):
    options = sorted((decimal_input(r, "outer radius"), r) for r in radii)
    if not options or len({r for r, _ in options}) != len(options):
        raise ValueError("one or more distinct available outer radii required")
    fixed = list(inner_layers)
    schedule = tuple(stages)
    rows = []
    last = None
    for radius, token in options:
        exp = solve_exposure_from_law(
            law, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
            solid_kg, liquid_kg, inner_radius_m, [*fixed, (token, coating_k)],
            emissivity, sigma, schedule, cylinder_length_m)
        last = exp
        status = (
            "survives_schedule" if exp["completedAllStages"]
            else SCHEDULE_STATUS[exp["finalPlateauStatus"]]
        )
        last_stage = exp["stages"][-1]
        halted = status != "survives_schedule"
        rows.append({
            "outerRadiusM": str(radius),
            "scheduleStatus": status,
            "completedAllStages": exp["completedAllStages"],
            "finalPlateauStatus": exp["finalPlateauStatus"],
            "haltingStageIndex": last_stage["stageIndex"] if halted else None,
            "haltingStageName": last_stage["name"] if halted else None,
            "modeledDurationBoundsS": exp["modeledDurationBoundsS"],
            "cumulativeEnergyIntoBathBoundsJ": exp["cumulativeEnergyIntoBathBoundsJ"],
            "finalSolidMassBoundsKg": exp["finalSolidMassBoundsKg"],
            "finalLiquidMassBoundsKg": exp["finalLiquidMassBoundsKg"],
            "stages": exp["stages"],
        })
    return {
        "schema": "sim_heat.offline_radial_exposure_sizing/1",
        "phaseBathPort": phase_port,
        "surfacePort": surface_port,
        "geometry": last["geometry"],
        "cylinderLengthM": last["cylinderLengthM"],
        "innerRadiusM": last["innerRadiusM"],
        "innerLayers": last["layers"][:-1],
        "coatingConductivityWPerMK": str(decimal_input(coating_k, "coating k")),
        "emissivity": last["emissivity"],
        "sigmaWPerM2K4": last["sigmaWPerM2K4"],
        "transitionTemperatureK": last["transitionTemperatureK"],
        "specificLatentHeatJPerKg": last["specificLatentHeatJPerKg"],
        "initialSolidKg": last["initialSolidKg"],
        "initialLiquidKg": last["initialLiquidKg"],
        "requestedStages": last["requestedStages"],
        "sizes": rows,
        "smallestEstablishedSurvivingRadiusM": smallest_established_surviving(rows),
        **offline_provenance(law),
    }


def investigate(inputs, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                solid_kg, liquid_kg, inner_radius_m, inner_layers, coating_k, radii,
                emissivity, sigma, stages, cylinder_length_m=None):
    return select_from_law(
        terminal_response(*inputs), phase_port, surface_port, transition_k,
        latent_heat_j_per_kg, solid_kg, liquid_kg, inner_radius_m, inner_layers,
        coating_k, radii, emissivity, sigma, stages, cylinder_length_m)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "phase-port", "surface-port",
                  "transition-k", "latent-heat-j-per-kg", "solid-kg", "liquid-kg",
                  "inner-radius-m", "coating-k", "emissivity", "sigma"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--inner-layer", action="append", nargs=2, default=[],
                   metavar=("R_OUT_M", "K_W_PER_M_K"))
    p.add_argument("--radius-m", action="append", required=True)
    p.add_argument("--stage", action="append", nargs=5, required=True,
                   metavar=("NAME", "AIR_K", "H_W_PER_M2_K", "ENCLOSURE_K", "DURATION_S"))
    p.add_argument("--cylinder-length-m")
    a = p.parse_args()
    print(json.dumps(investigate(
        (a.study, a.root, a.facts, a.facts_sha256), a.phase_port, a.surface_port,
        a.transition_k, a.latent_heat_j_per_kg, a.solid_kg, a.liquid_kg,
        a.inner_radius_m, a.inner_layer, a.coating_k, a.radius_m,
        a.emissivity, a.sigma, a.stage, a.cylinder_length_m), indent=2))
