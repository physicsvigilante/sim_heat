"""Follow a two-phase inventory through successive isothermal enclosure exposures."""
import argparse
from fractions import Fraction
import json

from tools.latent_heat_bath import plateau_power
from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


def pair(low, high):
    return [str(low), str(high)]


def reservoir_energies(stages, recovery):
    """Accumulate signed energy entering the exterior and each maintained support."""
    exterior = [Fraction(0), Fraction(0)]
    supports = {}
    for row in [*stages, *recovery.values()]:
        if "durationBoundsS" in row:
            times = tuple(map(Fraction, row["durationBoundsS"]))
        else:
            start = Fraction(row["startS"])
            times = tuple(Fraction(t) - start for t in row["endBoundsS"])

        def accumulate(rates, total):
            products = [Fraction(q) * t for q in rates for t in times]
            low, high = min(products), max(products)
            total[0] += low
            total[1] += high
            return pair(low, high)

        row["energyIntoEnclosureBoundsJ"] = accumulate(row["radiatingSurface"]["netHeatToEnclosureBoundsW"],
                                                       exterior)
        row["energyIntoSupportsBoundsJ"] = {
            name: accumulate(power, supports.setdefault(name, [Fraction(0), Fraction(0)]))
            for name, power in row.get("maintainedReservoirInflowBoundsW", {}).items()}
    return {"energyIntoEnclosuresBoundsJ": pair(*exterior),
            "energyIntoSupportsBoundsJ": {name: pair(*total) for name, total in supports.items()}}


def entropy_ledger(stages, recovery, energy, transition, maintained):
    """Entropy change of the bath and ideal reservoirs during heat exchange."""
    def heat_over_temperature(heat, kelvin):
        if kelvin <= 0:
            raise ValueError("entropy accounting requires positive reservoir temperatures")
        return tuple(Fraction(q) / kelvin for q in heat)

    bath = heat_over_temperature(energy["energyIntoBathBoundsJ"], transition)
    supports = {name: heat_over_temperature(heat, Fraction(maintained[name]))
                for name, heat in energy["energyIntoSupportsBoundsJ"].items()}
    enclosures = []
    for row in [*stages, *recovery.values()]:
        kelvin = Fraction(row["radiatingSurface"]["enclosureTemperatureK"])
        change = heat_over_temperature(row["energyIntoEnclosureBoundsJ"], kelvin)
        enclosures.append(change)
        row["enclosureEntropyChangeBoundsJPerK"] = pair(*change)
    # Each exposure has its own isothermal exterior. Include heat exchange
    # during modeled time only, including the optional recovery exposure.
    terms = [bath, *supports.values(), *enclosures]
    total = [sum(endpoints) for endpoints in zip(*terms)]
    return {"bathChangeBoundsJPerK": pair(*bath),
            "supportChangeBoundsJPerK": {name: pair(*value) for name, value in supports.items()},
            "enclosuresChangeBoundsJPerK": pair(*(sum(column) for column in zip(*enclosures))),
            "generatedBoundsJPerK": pair(*total)}


def investigate(inputs, port, face, transition_k, latent_j_kg, solid_kg, liquid_kg, properties, stages, recovery_k=None,
                track_reservoir_energy=False, track_entropy=False):
    if not isinstance(stages, (list, tuple)) or not stages:
        raise ValueError("one or more enclosure exposures required")
    schedule = []
    for stage in stages:
        if not isinstance(stage, (list, tuple)) or len(stage) != 2:
            raise ValueError("each stage requires enclosure K and duration s")
        env, seconds = stage
        decimal_input(env, "enclosure temperature")
        duration = decimal_input(seconds, "exposure duration")
        if duration <= 0:
            raise ValueError("positive exposure duration required")
        schedule.append((env, duration))
    if not isinstance(properties, (list, tuple)) or len(properties) != 3:
        raise ValueError("surface requires area, emissivity and sigma")
    transition = decimal_input(transition_k, "transition temperature")
    latent = decimal_input(latent_j_kg, "specific latent heat")
    solid = decimal_input(solid_kg, "solid mass")
    liquid = decimal_input(liquid_kg, "liquid mass")
    if min(transition, latent, solid, liquid) <= 0:
        raise ValueError("positive bath temperature, latent heat and both phase masses required")
    law = terminal_response(*inputs)
    minimum, maximum = -liquid * latent, solid * latent
    low = high = elapsed = Fraction(0)
    history = []
    for env, duration in schedule:
        qlo, qhi, surface = plateau_power(law, port, transition, (env, *properties), face)
        if qlo > 0:
            first, last = (maximum-high)/qhi, (maximum-low)/qlo
        elif qhi < 0:
            first, last = (low-minimum)/(-qlo), (high-minimum)/(-qhi)
        elif qlo == qhi == 0:
            first = last = None
        else:
            raise ValueError("latent heat-flow direction is unresolved")
        status = "coexisting"
        tlo = thi = duration
        if first is not None and duration >= first:
            status = "exhausted" if duration >= last else "exhaustion_time_uncertain"
            tlo, thi = first, min(duration, last)
        low = max(minimum, min(maximum, low + qlo*duration))
        high = max(minimum, min(maximum, high + qhi*duration))
        history.append({**surface, "startS": str(elapsed), "endBoundsS": pair(elapsed+tlo, elapsed+thi),
                        "plateauStatus": status, "bathInflowBoundsW": pair(qlo, qhi),
                        "cumulativeEnergyIntoBathBoundsJ": pair(low, high),
                        "solidMassBoundsKg": pair(solid-high/latent, solid-low/latent),
                        "liquidMassBoundsKg": pair(liquid+low/latent, liquid+high/latent)})
        if status != "coexisting":
            break
        elapsed += duration
    recovery = {}
    if recovery_k is not None:
        decimal_input(recovery_k, "recovery enclosure temperature")
        if history[-1]["plateauStatus"] != "coexisting":
            raise ValueError("recovery requires coexistence through the entire requested schedule")
        qlo, qhi, surface = plateau_power(law, port, transition, (recovery_k, *properties), face)
        if low == high == 0:
            first = last = Fraction(0)
        elif low > 0 and qhi < 0:
            first, last = low/(-qlo), high/(-qhi)
        elif high < 0 and qlo > 0:
            first, last = -high/qhi, -low/qlo
        else:
            raise ValueError("restoring the initial inventory requires a resolved opposing heat flow")
        recovery["inventoryRecovery"] = {**surface, "durationBoundsS": pair(first, last),
            "endBoundsS": pair(elapsed+first, elapsed+last), "bathInflowBoundsW": pair(qlo, qhi),
            "energyIntoBathBoundsJ": pair(-high, -low), "finalSolidKg": str(solid),
            "finalLiquidKg": str(liquid)}
    observations = {}
    if track_reservoir_energy or track_entropy:
        ledger = reservoir_energies(history, recovery)
        ledger["energyIntoBathBoundsJ"] = pair(0, 0) if recovery else pair(low, high)
        observations["reservoirEnergy"] = ledger
        if track_entropy:
            observations["entropy"] = entropy_ledger(history, recovery, ledger, transition, law["imposedTemperaturesK"])
    return {**observations, **recovery, "schema": "sim_heat.offline_phase_exposure_sequence/1", "bathPort": port,
            "transitionTemperatureK": str(transition), "specificLatentHeatJPerKg": str(latent),
            "initialSolidKg": str(solid), "initialLiquidKg": str(liquid),
            "requestedStages": [{"enclosureK": t, "durationS": str(d)} for t, d in schedule],
            "stages": history, **{k: law[k] for k in ("studySha256", "modelSha256", "factsSha256",
                                      "nativeExecuted", "nativeQualified", "independentlyCertifiedReference",
                                      "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "bath-port", "surface-port", "transition-k",
                  "latent-j-kg", "solid-kg", "liquid-kg", "area-m2", "emissivity", "sigma"):
        parser.add_argument("--"+field, required=True)
    parser.add_argument("--stage", action="append", nargs=2, required=True, metavar=("ENCLOSURE_K", "SECONDS"))
    parser.add_argument("--recover-at-k", help="enclosure temperature for return to the initial inventory")
    parser.add_argument("--track-reservoir-energy", action="store_true",
                        help="report heat entering the enclosures and maintained supports through the modeled stages")
    parser.add_argument("--track-entropy", action="store_true",
                        help="include reservoir energy and entropy changes for the modeled heat exchanges")
    a = parser.parse_args()
    print(json.dumps(investigate((a.study, a.root, a.facts, a.facts_sha256), a.bath_port, a.surface_port,
                                 a.transition_k, a.latent_j_kg, a.solid_kg, a.liquid_kg,
                                 (a.area_m2, a.emissivity, a.sigma), a.stage, a.recover_at_k, a.track_reservoir_energy, a.track_entropy), indent=2))
