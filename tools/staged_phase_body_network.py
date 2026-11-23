"""Multi-stage sensible <-> phase-change transient chaining on a pinned steady network.

Composes a finite mass of a phase-changing substance at one port of any pinned
connected passive steady conduction network (with all other terminals maintained)
across up to three consecutive physical stages:
1. Pre-transition sensible heating or cooling (lumped solid or liquid body)
2. Isothermal phase-change plateau at T_tr (melting or freezing until exhaustion)
3. Post-exhaustion sensible heating or cooling (lumped liquid or solid body)

Uses exact rational-interval exponential (exp_neg_interval) and logarithm (radial_log)
enclosures over the certified Thevenin port equivalent (T_eq, R_port), exploiting global
monotonicity in (T_eq, R_port) to guarantee certified enclosures even across stage
boundaries without dependency inflation.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path

from qualification.h1_n13.conduction import ZERO, Box
from tools.body_phase_bath_exchange import exp_neg_interval
from tools.join_thermal_networks import bounds
from tools.offline_investigation import PinnedSourceRef, _expect_exact_keys, validate_pinned_law
from tools.offline_provenance import OFFLINE_FLAG_KEYS, SOURCE_HASH_KEYS
from tools.radiating_surface import decimal_input, physical_port
from tools.spherical_conduction import radial_log
from tools.terminal_response import investigate as terminal_response

STAGED_SCHEMA = "sim_heat.offline_staged_phase_body/1"
EVIDENCE_CATEGORY = "offline_analytical_calculation"


def _box_union(boxes):
    return Box.bounds(min(b.span()[0] for b in boxes), max(b.span()[1] for b in boxes))


def _eval_heating_corner(t_eq, r_port, *, t0, t_tr, latent, c_solid, c_liquid, solid0, liquid0, duration):
    """Evaluate certified interval state at a fixed heating corner (t_eq > t0, r_port > 0)."""
    total_mass = solid0 + liquid0
    cap_s = total_mass * c_solid
    cap_l = total_mass * c_liquid
    tau_s = cap_s * r_port
    tau_l = cap_l * r_port

    # Stage 1: pre-transition solid sensible heating (only if t0 < t_tr).
    if t0 < t_tr:
        if t_eq <= t_tr:
            # Never reaches transition temperature.
            e_box = exp_neg_interval(Box.exact(duration / tau_s)) if duration > 0 else Box.exact(1)
            t_final = Box.exact(t_eq) - Box.exact(t_eq - t0) * e_box
            e_pre = Box.exact(cap_s) * (t_final - t0)
            return {
                "stage": "solid_sensible",
                "t1": None,
                "t2": None,
                "t_final": t_final,
                "solid_final": Box.exact(solid0),
                "liquid_final": Box.exact(liquid0),
                "e_pre": e_pre,
                "e_lat": ZERO,
                "e_post": ZERO,
                "e_total": e_pre,
            }
        # Exact hitting time t1 = tau_s * ln((t_eq - t0) / (t_eq - t_tr)).
        t1 = Box.exact(tau_s) * radial_log((t_eq - t0) / (t_eq - t_tr))
        t1_lo, t1_hi = t1.span()
    else:
        t1 = ZERO
        t1_lo = t1_hi = Fraction(0)

    # Stage 2: melting plateau at t_tr (only if solid0 > 0 and t_eq > t_tr).
    if solid0 > 0 and t_eq > t_tr:
        q_plat = (t_eq - t_tr) / r_port
        dt2 = solid0 * latent / q_plat
        t2 = t1 + dt2
        t2_lo, t2_hi = t2.span()
    else:
        q_plat = None
        dt2 = Fraction(0)
        t2 = t1
        t2_lo, t2_hi = t1_lo, t1_hi

    def _state_at_exact_t1_t2(t1_val, t2_val):
        if t0 < t_tr and duration < t1_val:
            e_box = exp_neg_interval(Box.exact(duration / tau_s)) if duration > 0 else Box.exact(1)
            t_f = Box.exact(t_eq) - Box.exact(t_eq - t0) * e_box
            return (
                "solid_sensible",
                t_f,
                Box.exact(solid0),
                Box.exact(liquid0),
                Box.exact(cap_s) * (t_f - t0),
                ZERO,
                ZERO,
            )
        e_pre_full = Box.exact(cap_s * (t_tr - t0)) if t0 < t_tr else ZERO
        if solid0 > 0 and duration < t2_val:
            dt_plat = max(Fraction(0), duration - t1_val)
            melted = min(solid0, q_plat * dt_plat / latent)
            return (
                "melting_plateau",
                Box.exact(t_tr),
                Box.exact(solid0 - melted),
                Box.exact(liquid0 + melted),
                e_pre_full,
                Box.exact(melted * latent),
                ZERO,
            )
        # Stage 3: post-melting liquid sensible heating (or already pure liquid at t0 >= t_tr).
        e_lat_full = Box.exact(solid0 * latent)
        s = max(Fraction(0), duration - t2_val)
        t_start = max(t0, t_tr)
        e_box = exp_neg_interval(Box.exact(s / tau_l)) if s > 0 else Box.exact(1)
        t_f = Box.exact(t_eq) - Box.exact(t_eq - t_start) * e_box
        e_post = Box.exact(cap_l) * (t_f - t_start)
        return (
            "liquid_sensible",
            t_f,
            ZERO,
            Box.exact(total_mass),
            e_pre_full,
            e_lat_full,
            e_post,
        )

    # Because t1 and t2 are tiny rational intervals (from radial_log), union the two
    # extreme timing endpoints (t1_lo, t2_lo) and (t1_hi, t2_hi) to enclose every realization.
    s_fast = _state_at_exact_t1_t2(t1_lo, t2_lo)
    s_slow = _state_at_exact_t1_t2(t1_hi, t2_hi)
    stage = s_fast[0] if s_fast[0] == s_slow[0] else "stage_boundary_uncertain"
    return {
        "stage": stage,
        "t1": t1 if t0 < t_tr else None,
        "t2": t2 if solid0 > 0 and t_eq > t_tr else None,
        "t_final": _box_union([s_fast[1], s_slow[1]]),
        "solid_final": _box_union([s_fast[2], s_slow[2]]),
        "liquid_final": _box_union([s_fast[3], s_slow[3]]),
        "e_pre": _box_union([s_fast[4], s_slow[4]]),
        "e_lat": _box_union([s_fast[5], s_slow[5]]),
        "e_post": _box_union([s_fast[6], s_slow[6]]),
        "e_total": _box_union([s_fast[4] + s_fast[5] + s_fast[6], s_slow[4] + s_slow[5] + s_slow[6]]),
    }


def _eval_cooling_corner(t_eq, r_port, *, t0, t_tr, latent, c_solid, c_liquid, solid0, liquid0, duration):
    """Evaluate certified interval state at a fixed cooling corner (t_eq < t0, r_port > 0)."""
    total_mass = solid0 + liquid0
    cap_s = total_mass * c_solid
    cap_l = total_mass * c_liquid
    tau_s = cap_s * r_port
    tau_l = cap_l * r_port

    # Stage 1: pre-transition liquid sensible cooling (only if t0 > t_tr).
    if t0 > t_tr:
        if t_eq >= t_tr:
            e_box = exp_neg_interval(Box.exact(duration / tau_l)) if duration > 0 else Box.exact(1)
            t_final = Box.exact(t_eq) + Box.exact(t0 - t_eq) * e_box
            e_pre = Box.exact(cap_l) * (t_final - t0)
            return {
                "stage": "liquid_sensible",
                "t1": None,
                "t2": None,
                "t_final": t_final,
                "solid_final": Box.exact(solid0),
                "liquid_final": Box.exact(liquid0),
                "e_pre": e_pre,
                "e_lat": ZERO,
                "e_post": ZERO,
                "e_total": e_pre,
            }
        t1 = Box.exact(tau_l) * radial_log((t0 - t_eq) / (t_tr - t_eq))
        t1_lo, t1_hi = t1.span()
    else:
        t1 = ZERO
        t1_lo = t1_hi = Fraction(0)

    # Stage 2: freezing plateau at t_tr (only if liquid0 > 0 and t_eq < t_tr).
    if liquid0 > 0 and t_eq < t_tr:
        q_out = (t_tr - t_eq) / r_port  # positive heat extraction rate
        dt2 = liquid0 * latent / q_out
        t2 = t1 + dt2
        t2_lo, t2_hi = t2.span()
    else:
        q_out = None
        dt2 = Fraction(0)
        t2 = t1
        t2_lo, t2_hi = t1_lo, t1_hi

    def _state_at_exact_t1_t2(t1_val, t2_val):
        if t0 > t_tr and duration < t1_val:
            e_box = exp_neg_interval(Box.exact(duration / tau_l)) if duration > 0 else Box.exact(1)
            t_f = Box.exact(t_eq) + Box.exact(t0 - t_eq) * e_box
            return (
                "liquid_sensible",
                t_f,
                Box.exact(solid0),
                Box.exact(liquid0),
                Box.exact(cap_l) * (t_f - t0),
                ZERO,
                ZERO,
            )
        e_pre_full = Box.exact(cap_l * (t_tr - t0)) if t0 > t_tr else ZERO
        if liquid0 > 0 and duration < t2_val:
            dt_plat = max(Fraction(0), duration - t1_val)
            frozen = min(liquid0, q_out * dt_plat / latent)
            return (
                "freezing_plateau",
                Box.exact(t_tr),
                Box.exact(solid0 + frozen),
                Box.exact(liquid0 - frozen),
                e_pre_full,
                Box.exact(-frozen * latent),
                ZERO,
            )
        # Stage 3: post-freezing solid sensible cooling (or already pure solid at t0 <= t_tr).
        e_lat_full = Box.exact(-liquid0 * latent)
        s = max(Fraction(0), duration - t2_val)
        t_start = min(t0, t_tr)
        e_box = exp_neg_interval(Box.exact(s / tau_s)) if s > 0 else Box.exact(1)
        t_f = Box.exact(t_eq) + Box.exact(t_start - t_eq) * e_box
        e_post = Box.exact(cap_s) * (t_f - t_start)
        return (
            "solid_sensible",
            t_f,
            Box.exact(total_mass),
            ZERO,
            e_pre_full,
            e_lat_full,
            e_post,
        )

    s_fast = _state_at_exact_t1_t2(t1_lo, t2_lo)
    s_slow = _state_at_exact_t1_t2(t1_hi, t2_hi)
    stage = s_fast[0] if s_fast[0] == s_slow[0] else "stage_boundary_uncertain"
    return {
        "stage": stage,
        "t1": t1 if t0 > t_tr else None,
        "t2": t2 if liquid0 > 0 and t_eq < t_tr else None,
        "t_final": _box_union([s_fast[1], s_slow[1]]),
        "solid_final": _box_union([s_fast[2], s_slow[2]]),
        "liquid_final": _box_union([s_fast[3], s_slow[3]]),
        "e_pre": _box_union([s_fast[4], s_slow[4]]),
        "e_lat": _box_union([s_fast[5], s_slow[5]]),
        "e_post": _box_union([s_fast[6], s_slow[6]]),
        "e_total": _box_union([s_fast[4] + s_fast[5] + s_fast[6], s_slow[4] + s_slow[5] + s_slow[6]]),
    }


def _validate_substance_inputs(
    initial_k, transition_k, latent_j_per_kg, c_solid_j_per_kg_k, c_liquid_j_per_kg_k,
    solid_kg, liquid_kg, duration_s,
):
    t0 = decimal_input(initial_k, "initial temperature")
    t_tr = decimal_input(transition_k, "transition temperature")
    latent = decimal_input(latent_j_per_kg, "specific latent heat")
    c_solid = decimal_input(c_solid_j_per_kg_k, "solid specific heat")
    c_liquid = decimal_input(c_liquid_j_per_kg_k, "liquid specific heat")
    solid0 = decimal_input(solid_kg, "initial solid mass")
    liquid0 = decimal_input(liquid_kg, "initial liquid mass")
    duration = decimal_input(duration_s, "duration")
    if min(t_tr, latent, c_solid, c_liquid) <= 0:
        raise ValueError("positive transition temperature, latent heat, and solid/liquid specific heats required")
    if solid0 + liquid0 <= 0:
        raise ValueError("positive total substance mass required")
    if t0 < t_tr and (solid0 <= 0 or liquid0 != 0):
        raise ValueError("subcooled initial state (T0 < T_tr) requires positive solid mass and zero liquid mass")
    if t0 > t_tr and (liquid0 <= 0 or solid0 != 0):
        raise ValueError("superheated initial state (T0 > T_tr) requires positive liquid mass and zero solid mass")
    return t0, t_tr, latent, c_solid, c_liquid, solid0, liquid0, duration


def solve_from_law(
    law,
    port,
    initial_k,
    transition_k,
    latent_j_per_kg,
    c_solid_j_per_kg_k,
    c_liquid_j_per_kg_k,
    solid_kg,
    liquid_kg,
    duration_s,
    *,
    maintained_temperatures_k=None,
):
    """Solve multi-stage sensible <-> phase-change transient on a validated pinned network."""
    provenance = validate_pinned_law(law)
    terminals = list(law["terminals"])
    if port not in terminals:
        raise ValueError(f"substance port {port!r} is not in pinned network terminals {terminals}")

    t0, t_tr, latent, c_solid, c_liquid, solid0, liquid0, duration = _validate_substance_inputs(
        initial_k, transition_k, latent_j_per_kg, c_solid_j_per_kg_k, c_liquid_j_per_kg_k,
        solid_kg, liquid_kg, duration_s,
    )

    source_ref_temps = {t: str(law["imposedTemperaturesK"][t]) for t in terminals}
    other_ports = [t for t in terminals if t != port]
    if maintained_temperatures_k is None:
        maintained = {t: source_ref_temps[t] for t in other_ports}
    else:
        if not isinstance(maintained_temperatures_k, dict) or set(maintained_temperatures_k) != set(other_ports):
            raise ValueError("maintained_temperatures_k must specify every terminal except the substance port")
        maintained = {}
        for t in other_ports:
            maintained[t] = str(decimal_input(maintained_temperatures_k[t], f"maintained temperature at {t}"))

    effective_imposed = {**source_ref_temps, **maintained}
    (eq_lo, eq_hi), (r_lo, r_hi) = physical_port({**law, "imposedTemperaturesK": effective_imposed}, port)

    total_mass = solid0 + liquid0
    # Determine global monotone regime.
    if eq_lo == eq_hi == t0:
        regime = "equilibrium"
        final_stage = (
            "solid_sensible" if t0 < t_tr else ("liquid_sensible" if t0 > t_tr else "coexisting_equilibrium")
        )
        t1_box = None
        t2_box = None
        t_final = Box.exact(t0)
        solid_final = Box.exact(solid0)
        liquid_final = Box.exact(liquid0)
        e_pre = ZERO
        e_lat = ZERO
        e_post = ZERO
    elif eq_lo > t0:
        regime = "heating"
        if t0 < t_tr and eq_lo <= t_tr < eq_hi:
            raise ValueError("phase-transition reachability is unresolved across T_eq enclosure")
        # Heating monotonicity: minimum progress at (eq_lo, r_hi), maximum progress at (eq_hi, r_lo).
        c_slow = _eval_heating_corner(
            eq_lo, r_hi, t0=t0, t_tr=t_tr, latent=latent, c_solid=c_solid, c_liquid=c_liquid,
            solid0=solid0, liquid0=liquid0, duration=duration,
        )
        c_fast = _eval_heating_corner(
            eq_hi, r_lo, t0=t0, t_tr=t_tr, latent=latent, c_solid=c_solid, c_liquid=c_liquid,
            solid0=solid0, liquid0=liquid0, duration=duration,
        )
        final_stage = c_slow["stage"] if c_slow["stage"] == c_fast["stage"] else "stage_boundary_uncertain"
        t1_box = None if c_slow["t1"] is None else _box_union([c_slow["t1"], c_fast["t1"]])
        t2_box = None if c_slow["t2"] is None else _box_union([c_slow["t2"], c_fast["t2"]])
        t_final = _box_union([c_slow["t_final"], c_fast["t_final"]])
        solid_final = _box_union([c_slow["solid_final"], c_fast["solid_final"]])
        liquid_final = _box_union([c_slow["liquid_final"], c_fast["liquid_final"]])
        e_pre = _box_union([c_slow["e_pre"], c_fast["e_pre"]])
        e_lat = _box_union([c_slow["e_lat"], c_fast["e_lat"]])
        e_post = _box_union([c_slow["e_post"], c_fast["e_post"]])
    elif eq_hi < t0:
        regime = "cooling"
        if t0 > t_tr and eq_lo < t_tr <= eq_hi:
            raise ValueError("phase-transition reachability is unresolved across T_eq enclosure")
        # Cooling monotonicity: slowest cooling at (eq_hi, r_hi), fastest cooling at (eq_lo, r_lo).
        c_slow = _eval_cooling_corner(
            eq_hi, r_hi, t0=t0, t_tr=t_tr, latent=latent, c_solid=c_solid, c_liquid=c_liquid,
            solid0=solid0, liquid0=liquid0, duration=duration,
        )
        c_fast = _eval_cooling_corner(
            eq_lo, r_lo, t0=t0, t_tr=t_tr, latent=latent, c_solid=c_solid, c_liquid=c_liquid,
            solid0=solid0, liquid0=liquid0, duration=duration,
        )
        final_stage = c_slow["stage"] if c_slow["stage"] == c_fast["stage"] else "stage_boundary_uncertain"
        t1_box = None if c_slow["t1"] is None else _box_union([c_slow["t1"], c_fast["t1"]])
        t2_box = None if c_slow["t2"] is None else _box_union([c_slow["t2"], c_fast["t2"]])
        t_final = _box_union([c_slow["t_final"], c_fast["t_final"]])
        solid_final = _box_union([c_slow["solid_final"], c_fast["solid_final"]])
        liquid_final = _box_union([c_slow["liquid_final"], c_fast["liquid_final"]])
        e_pre = _box_union([c_slow["e_pre"], c_fast["e_pre"]])
        e_lat = _box_union([c_slow["e_lat"], c_fast["e_lat"]])
        e_post = _box_union([c_slow["e_post"], c_fast["e_post"]])
    else:
        raise ValueError("initial heat-flow direction is unresolved across T_eq enclosure")

    # Exact total enthalpy change H(D) - H(0) from monotone corners (tighter than summing 3 boxes).
    if regime == "equilibrium":
        e_total = ZERO
    else:
        e_total = _box_union([c_slow["e_total"], c_fast["e_total"]])

    port_roles = {t: ("staged_phase_substance" if t == port else "maintained_reservoir") for t in terminals}
    active_bcs = {}
    for t in terminals:
        if t == port:
            active_bcs[t] = {
                "role": "staged_phase_substance",
                "constraint": "piecewise_lumped_sensible_and_clamped_plateau",
                "initialTemperatureK": str(t0),
                "transitionTemperatureK": str(t_tr),
                "finalTemperatureBoundsK": bounds(t_final),
            }
        else:
            active_bcs[t] = {
                "role": "maintained_reservoir",
                "constraint": "fixed_dirichlet",
                "temperatureK": maintained[t],
            }

    return {
        "schema": STAGED_SCHEMA,
        "evidence": {
            "category": EVIDENCE_CATEGORY,
            "sourceIdentity": {k: provenance[k] for k in SOURCE_HASH_KEYS},
            **{k: False for k in OFFLINE_FLAG_KEYS},
        },
        "network": {
            "terminals": terminals,
            "portRoles": port_roles,
            "sourceLawReferenceTemperaturesK": source_ref_temps,
            "maintainedReservoirTemperaturesK": maintained,
            "activeBoundaryConditions": active_bcs,
        },
        "substancePort": port,
        "inputs": {
            "initialTemperatureK": str(t0),
            "transitionTemperatureK": str(t_tr),
            "specificLatentHeatJPerKg": str(latent),
            "solidSpecificHeatJPerKgK": str(c_solid),
            "liquidSpecificHeatJPerKgK": str(c_liquid),
            "initialSolidKg": str(solid0),
            "initialLiquidKg": str(liquid0),
            "totalMassKg": str(total_mass),
            "requestedDurationS": str(duration),
        },
        "portEquivalent": {
            "equilibriumTemperatureBoundsK": [str(eq_lo), str(eq_hi)],
            "portResistanceBoundsKPerW": [str(r_lo), str(r_hi)],
            "solidTimeConstantBoundsS": [str(total_mass * c_solid * r_lo), str(total_mass * c_solid * r_hi)],
            "liquidTimeConstantBoundsS": [str(total_mass * c_liquid * r_lo), str(total_mass * c_liquid * r_hi)],
        },
        "trajectory": {
            "regime": regime,
            "finalStage": final_stage,
            "postExhaustionModeled": True,
            "modeledDurationBoundsS": [str(duration), str(duration)],
            "transitionEntryTimeBoundsS": None if t1_box is None else bounds(t1_box),
            "phaseExhaustionTimeBoundsS": None if t2_box is None else bounds(t2_box),
            "finalTemperatureBoundsK": bounds(t_final),
            "remainingSolidBoundsKg": bounds(solid_final),
            "remainingLiquidBoundsKg": bounds(liquid_final),
            "sensibleEnergyPreTransitionBoundsJ": bounds(e_pre),
            "latentEnergyChangeBoundsJ": bounds(e_lat),
            "sensibleEnergyPostTransitionBoundsJ": bounds(e_post),
            "totalEnergyIntoSubstanceBoundsJ": bounds(e_total),
            "energySignConvention": "into_substance_positive",
        },
        **provenance,
    }


def investigate(
    inputs,
    port,
    initial_k,
    transition_k,
    latent_j_per_kg,
    c_solid_j_per_kg_k,
    c_liquid_j_per_kg_k,
    solid_kg,
    liquid_kg,
    duration_s,
    *,
    maintained_temperatures_k=None,
):
    """Resolve a pinned file-backed source tuple/PinnedSourceRef and solve the staged trajectory."""
    law = inputs.resolve_law() if isinstance(inputs, PinnedSourceRef) else terminal_response(*inputs)
    return solve_from_law(
        law,
        port,
        initial_k,
        transition_k,
        latent_j_per_kg,
        c_solid_j_per_kg_k,
        c_liquid_j_per_kg_k,
        solid_kg,
        liquid_kg,
        duration_s,
        maintained_temperatures_k=maintained_temperatures_k,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="Path to JSON staged phase-body request")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
    _expect_exact_keys(
        payload,
        required=(
            "source",
            "port",
            "initialTemperatureK",
            "transitionTemperatureK",
            "specificLatentHeatJPerKg",
            "solidSpecificHeatJPerKgK",
            "liquidSpecificHeatJPerKgK",
            "initialSolidKg",
            "initialLiquidKg",
            "durationS",
        ),
        optional=("maintainedTemperaturesK",),
        label="request",
    )
    src = payload["source"]
    kwargs = dict(maintained_temperatures_k=payload.get("maintainedTemperaturesK"))
    if isinstance(src, dict) and "studyPath" in src:
        _expect_exact_keys(
            src,
            required=("studyPath", "rootPath", "factsPath", "factsSha256"),
            label="request.source",
        )
        ref = PinnedSourceRef(src["studyPath"], src["rootPath"], src["factsPath"], src["factsSha256"])
        res = investigate(
            ref,
            payload["port"],
            payload["initialTemperatureK"],
            payload["transitionTemperatureK"],
            payload["specificLatentHeatJPerKg"],
            payload["solidSpecificHeatJPerKgK"],
            payload["liquidSpecificHeatJPerKgK"],
            payload["initialSolidKg"],
            payload["initialLiquidKg"],
            payload["durationS"],
            **kwargs,
        )
    else:
        res = solve_from_law(
            src,
            payload["port"],
            payload["initialTemperatureK"],
            payload["transitionTemperatureK"],
            payload["specificLatentHeatJPerKg"],
            payload["solidSpecificHeatJPerKgK"],
            payload["liquidSpecificHeatJPerKgK"],
            payload["initialSolidKg"],
            payload["initialLiquidKg"],
            payload["durationS"],
            **kwargs,
        )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
