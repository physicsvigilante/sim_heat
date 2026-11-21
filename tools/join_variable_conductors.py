"""Join two steady rod networks with distinct linear conductivity laws at one ideal contact."""
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


def investigate(left, right):
    """Each side supplies (source inputs, released port, reference kelvin, relative slope/K)."""
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

    def bracket(index):
        # Both residual envelopes increase because the integrated conductivity is increasing.
        low, high = cold, hot
        for _ in range(96):
            mid = (low+high)/2
            value = sum(pivot[index]*m.potential(mid) + offset[index]
                        for _, _, m, _, pivot, offset in prepared)
            if value == 0:
                return mid, mid
            if value < 0:
                low = mid
            else:
                high = mid
        return low, high

    contact = bracket(1)[0], bracket(0)[1]
    result = {"schema": "sim_heat.offline_dissimilar_conductors/1",
              "contactTemperatureBoundsK": list(map(str, contact)), "nativeExecuted": False,
              "nativeQualified": False, "independentlyCertifiedReference": False, "runnerConsumable": False}
    currents = []
    for side, (law, port, material, fixed, _, _) in zip(("left", "right"), prepared):
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
    args = vars(parser.parse_args())

    def bundle(side):
        values = [args[side+"_"+field.replace("-", "_")] for field in fields]
        return (values[:4], *values[4:])

    print(json.dumps(investigate(bundle("left"), bundle("right")), indent=2))
