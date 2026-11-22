"""Join two steady rod networks with distinct linear conductivity laws through one thermal contact."""
import argparse
from fractions import Fraction
import json

from tools.radiating_surface import decimal_input
from tools.terminal_response import investigate as terminal_response


class Material:
    def __init__(self, reference, slope, cold, hot):
        self.reference = decimal_input(reference, "reference temperature")
        negative = isinstance(slope, str) and slope.startswith("-")
        magnitude = decimal_input(slope[1:] if negative else slope, "relative conductivity slope")
        self.slope = -magnitude if negative else magnitude
        self.origin = cold
        self.factor = 1 + self.slope * (cold - self.reference)
        if self.reference <= 0 or min(self.factor, self.factor + self.slope * (hot-cold)) <= 0:
            raise ValueError("positive reference temperature and conductivity required across retained temperatures")

    def potential(self, temperature):
        rise = temperature - self.origin
        return rise * (self.factor + self.slope * rise / 2)


def response(row, potentials):
    low = high = Fraction(0)
    for port, coefficient in row.items():
        products = [a*b for a in map(Fraction, coefficient) for b in potentials[port]]
        low += min(products)
        high += max(products)
    return low, high


def investigate(left, right, contact_resistance_k_per_w="0"):
    """Each side supplies (source inputs, released port, reference kelvin, relative slope/K)."""
    resistance = decimal_input(contact_resistance_k_per_w, "contact resistance")
    sides = []
    baths = []
    for inputs, port, reference, slope in (left, right):
        law = terminal_response(*inputs, include_rods=True)
        if port not in law["terminals"]:
            raise ValueError("unknown contact terminal")
        retained = {p: Fraction(t) for p, t in law["imposedTemperaturesK"].items() if p != port}
        baths.extend(retained.values())
        sides.append((law, port, reference, slope, retained))
    cold, hot = min(baths), max(baths)
    prepared = []
    for law, port, reference, slope, retained in sides:
        material = Material(reference, slope, cold, hot)
        fixed = {p: (material.potential(t),)*2 for p, t in retained.items()}
        row = law["supplyResponseBoundsWPerK"][port]
        pivot = tuple(map(Fraction, row[port]))
        if pivot[0] <= 0:
            raise ValueError("unresolved contact conductance")
        constant = response(row, {**fixed, port: (0, 0)})
        prepared.append((law, port, material, fixed, pivot, constant))

    def port_supply(side, temperature, index):
        _, _, material, _, pivot, offset = prepared[side]
        return pivot[index]*material.potential(temperature) + offset[index]

    def right_temperature(left_temperature, left_supply):
        # q flows left to right, while a port supply is positive into its network.
        # Both faces lie within the bath extrema. Clipping off-root trial values
        # extends the residual monotonically without extrapolating either material.
        return min(hot, max(cold, left_temperature + resistance*left_supply))

    def bracket(index):
        # Both residual envelopes increase because the integrated conductivity is increasing.
        low, high = cold, hot
        for _ in range(96):
            mid = (low+high)/2
            supplied = port_supply(0, mid, index)
            value = supplied + port_supply(1, right_temperature(mid, supplied), index)
            if value == 0:
                return mid, mid
            if value < 0:
                low = mid
            else:
                high = mid
        return low, high

    left_face = bracket(1)[0], bracket(0)[1]
    right_face = tuple(right_temperature(t, port_supply(0, t, i)) for i, t in enumerate(left_face))
    result = {"nativeExecuted": False, "nativeQualified": False,
              "independentlyCertifiedReference": False, "runnerConsumable": False}
    if resistance:
        result.update(schema="sim_heat.offline_resistive_contact/1", contactResistanceKPerW=str(resistance),
                      leftFaceTemperatureBoundsK=list(map(str, left_face)),
                      rightFaceTemperatureBoundsK=list(map(str, right_face)))
    else:
        result.update(schema="sim_heat.offline_dissimilar_conductors/1",
                      contactTemperatureBoundsK=list(map(str, left_face)))
    currents = []
    for side, contact, (law, port, material, fixed, _, _) in zip(("left", "right"), (left_face, right_face), prepared):
        potentials = {**fixed, port: tuple(map(material.potential, contact))}
        supplies = {p: response(row, potentials) for p, row in law["supplyResponseBoundsWPerK"].items()}
        currents.append(supplies.pop(port))
        result[side] = {"contact": port, "referenceTemperatureK": str(material.reference),
                        "relativeSlopePerK": str(material.slope),
                        **{k: law[k] for k in ("studySha256", "modelSha256", "factsSha256")},
                        "terminalSupplyBoundsW": {p: list(map(str, v)) for p, v in supplies.items()},
                        "rodHeatFlowBoundsW": {p: list(map(str, response(row, potentials)))
                                               for p, row in law["rodResponseBoundsWPerK"].items()}}
    left_flow, right_flow = currents
    flow = max(-left_flow[1], right_flow[0]), min(-left_flow[0], right_flow[1])
    if flow[0] > flow[1]:
        raise ValueError("contact heat rates inconsistent")
    result["leftToRightHeatRateBoundsW"] = list(map(str, flow))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256", "port", "reference-k", "slope-per-k")
    for side in ("left", "right"):
        for field in fields:
            parser.add_argument("--"+side+"-"+field, required=True)
    parser.add_argument("--contact-resistance-k-per-w", default="0")
    args = vars(parser.parse_args())

    def bundle(side):
        values = [args[side+"_"+field.replace("-", "_")] for field in fields]
        return (values[:4], *values[4:])

    print(json.dumps(investigate(bundle("left"), bundle("right"), args["contact_resistance_k_per_w"]), indent=2))
