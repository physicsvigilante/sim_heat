"""Select a stocked radial insulation outer radius to meet a phase-change hold time."""
import argparse
from fractions import Fraction as F
import json

from tools.latent_heat_bath import phase_inputs, plateau_state
from tools.radial_phase_bath import bath_inflow_from_law
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


HOLD_STATUS = {
    "coexisting": "meets_hold_time",
    "exhausted": "fails_hold_time",
    "exhaustion_time_uncertain": "unresolved",
}


def smallest_established_hold(rows):
    for row in rows:
        if row["holdStatus"] == "meets_hold_time":
            return row["outerRadiusM"]
        if row["holdStatus"] == "unresolved":
            break
    return None


def _size_row(radius, law, phase_port, surface_port, phase, qlo, qhi, details):
    shell = details["radialShell"]
    if qlo > 0 or qhi < 0 or qlo == qhi == 0:
        state = plateau_state(law, phase_port, phase, qlo, qhi, details)
        return {
            "outerRadiusM": str(radius),
            "holdStatus": HOLD_STATUS[state["plateauStatus"]],
            "phaseProcess": state["phaseProcess"],
            "plateauStatus": state["plateauStatus"],
            "bathInflowDuringPlateauBoundsW": state["bathInflowDuringPlateauBoundsW"],
            "shellOutwardHeatRateBoundsW": shell["outwardHeatRateBoundsW"],
            "exhaustionTimeBoundsS": state["exhaustionTimeBoundsS"],
            "remainingSolidBoundsKg": state["remainingSolidBoundsKg"],
            "remainingLiquidBoundsKg": state["remainingLiquidBoundsKg"],
            "maintainedReservoirInflowBoundsW": details["maintainedReservoirInflowBoundsW"],
        }
    _, latent, solid, liquid, horizon = phase
    # Direction is unresolved (qlo <= 0 <= qhi, qlo < qhi). Neither phase can
    # exhaust if even the worst-case flow in both directions stays below the
    # respective latent capacity; otherwise hold status remains unresolved.
    meets = (max(F(0), qhi) * horizon < solid * latent
             and max(F(0), -qlo) * horizon < liquid * latent)
    mlo = max(-liquid, qlo * horizon / latent)
    mhi = min(solid, qhi * horizon / latent)
    return {
        "outerRadiusM": str(radius),
        "holdStatus": "meets_hold_time" if meets else "unresolved",
        "phaseProcess": "unresolved",
        "plateauStatus": "coexisting" if meets else "exhaustion_time_uncertain",
        "bathInflowDuringPlateauBoundsW": [str(qlo), str(qhi)],
        "shellOutwardHeatRateBoundsW": shell["outwardHeatRateBoundsW"],
        "exhaustionTimeBoundsS": None,
        "remainingSolidBoundsKg": [str(solid - mhi), str(solid - mlo)],
        "remainingLiquidBoundsKg": [str(liquid + mlo), str(liquid + mhi)],
        "maintainedReservoirInflowBoundsW": details["maintainedReservoirInflowBoundsW"],
    }


def select_from_law(law, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                    solid_kg, liquid_kg, hold_duration_s, inner_radius_m, inner_layers,
                    coating_k, radii, enclosure_k, emissivity, sigma, cylinder_length_m=None,
                    *, air_k=None, h_w_per_m2_k=None):
    phase = phase_inputs(transition_k, latent_heat_j_per_kg, solid_kg, liquid_kg, hold_duration_s)
    if phase[4] <= 0:
        raise ValueError("positive target hold duration required")
    options = sorted((decimal_input(r, "outer radius"), r) for r in radii)
    if not options or len({r for r, _ in options}) != len(options):
        raise ValueError("one or more distinct available outer radii required")
    fixed = list(inner_layers)
    rows = []
    last_shell = None
    for radius, token in options:
        qlo, qhi, details = bath_inflow_from_law(
            law, phase_port, surface_port, phase[0], inner_radius_m, [*fixed, (token, coating_k)],
            enclosure_k, emissivity, sigma, cylinder_length_m, air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)
        last_shell = details["radialShell"]
        rows.append(_size_row(radius, law, phase_port, surface_port, phase, qlo, qhi, details))
    return {
        "schema": "sim_heat.offline_phase_shell_sizing/1",
        "phaseBathPort": phase_port,
        "surfacePort": surface_port,
        "geometry": last_shell["geometry"],
        "cylinderLengthM": last_shell["cylinderLengthM"],
        "innerRadiusM": str(decimal_input(inner_radius_m, "inner radius")),
        "innerLayers": last_shell["layers"][:-1],
        "coatingConductivityWPerMK": str(decimal_input(coating_k, "coating k")),
        "transitionTemperatureK": str(phase[0]),
        "specificLatentHeatJPerKg": str(phase[1]),
        "initialSolidKg": str(phase[2]),
        "initialLiquidKg": str(phase[3]),
        "targetHoldDurationS": str(phase[4]),
        "enclosureTemperatureK": last_shell["enclosureTemperatureK"],
        "emissivity": last_shell["emissivity"],
        "sigmaWPerM2K4": last_shell["sigmaWPerM2K4"],
        **{key: last_shell[key] for key in ("airTemperatureK", "convectionCoefficientWPerM2K")
           if key in last_shell},
        "sizes": rows,
        "smallestEstablishedMeetingHoldRadiusM": smallest_established_hold(rows),
        **{key: law[key] for key in ("studySha256", "modelSha256", "factsSha256", "nativeExecuted",
                                     "nativeQualified", "independentlyCertifiedReference",
                                     "runnerConsumable")},
    }


def investigate(inputs, phase_port, surface_port, transition_k, latent_heat_j_per_kg,
                solid_kg, liquid_kg, hold_duration_s, inner_radius_m, inner_layers,
                coating_k, radii, enclosure_k, emissivity, sigma, cylinder_length_m=None,
                *, air_k=None, h_w_per_m2_k=None):
    return select_from_law(
        terminal_response(*inputs), phase_port, surface_port, transition_k, latent_heat_j_per_kg,
        solid_kg, liquid_kg, hold_duration_s, inner_radius_m, inner_layers, coating_k, radii,
        enclosure_k, emissivity, sigma, cylinder_length_m, air_k=air_k, h_w_per_m2_k=h_w_per_m2_k)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "phase-port", "surface-port",
                  "transition-k", "latent-heat-j-per-kg", "solid-kg", "liquid-kg",
                  "hold-duration-s", "inner-radius-m", "coating-k", "enclosure-k",
                  "emissivity", "sigma"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--inner-layer", action="append", nargs=2, default=[],
                   metavar=("R_OUT_M", "K_W_PER_M_K"))
    p.add_argument("--radius-m", action="append", required=True)
    p.add_argument("--cylinder-length-m")
    p.add_argument("--air-k")
    p.add_argument("--h-w-per-m2-k")
    a = p.parse_args()
    print(json.dumps(investigate(
        (a.study, a.root, a.facts, a.facts_sha256), a.phase_port, a.surface_port,
        a.transition_k, a.latent_heat_j_per_kg, a.solid_kg, a.liquid_kg, a.hold_duration_s,
        a.inner_radius_m, a.inner_layer, a.coating_k, a.radius_m, a.enclosure_k,
        a.emissivity, a.sigma, a.cylinder_length_m, air_k=a.air_k, h_w_per_m2_k=a.h_w_per_m2_k),
        indent=2))
