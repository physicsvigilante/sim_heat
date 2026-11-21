"""Release and join two distinct pairs of terminals on steady thermal networks."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import ZERO, interval
from tools.join_thermal_networks import bounds
from tools.terminal_response import investigate as terminal_response


def investigate(left_inputs, right_inputs, first_pair, second_pair):
    pairs = (first_pair, second_pair)
    if any(len(pair) != 2 for pair in pairs):
        raise ValueError("each contact requires one terminal per network")
    contacts = ("contact1", "contact2")
    matrix = {}
    temperatures = {}
    sources = {}
    for index, (side, inputs) in enumerate((("left", left_inputs), ("right", right_inputs))):
        law = terminal_response(*inputs)
        ports = [pair[index] for pair in pairs]
        if len(set(ports)) != 2 or not set(ports).issubset(law["terminals"]):
            raise ValueError(f"two distinct {side} terminals required")
        names = dict(zip(ports, contacts, strict=True))
        for port in law["terminals"]:
            if port not in names:
                names[port] = side + "." + port
                temperatures[names[port]] = Fraction(law["imposedTemperaturesK"][port])
        for i, row in law["supplyResponseBoundsWPerK"].items():
            for j, value in row.items():
                key = names[i], names[j]
                matrix[key] = matrix.get(key, ZERO) + interval(value)
        sources[side] = {key: law[key] for key in ("modelSha256", "studySha256", "factsSha256")}
        sources[side]["contacts"] = dict(zip(contacts, ports, strict=True))
    if not temperatures:
        raise ValueError("at least one maintained external terminal required")

    # The two junction supplies vanish together. Solve their 2x2 system for
    # each external unit excitation, keeping all enclosure operations outward.
    a, b = contacts
    aa, ab = matrix[a,a], matrix[a,b]
    ba, bb = matrix[b,a], matrix[b,b]
    determinant = aa*bb - ab*ba
    if determinant.low <= 0:
        raise ValueError("two-contact conductance determinant is unresolved")
    weights = {a: {}, b: {}}
    for j in temperatures:
        u, v = matrix.get((a,j), ZERO), matrix.get((b,j), ZERO)
        weights[a][j] = (ab*v - bb*u)/determinant
        weights[b][j] = (ba*u - aa*v)/determinant

    origin = min(temperatures.values())
    offsets = {n: t-origin for n, t in temperatures.items()}
    def response(row):
        return sum((coefficient*offsets[j] for j, coefficient in row.items()), ZERO)

    reduced, supplies = {}, {}
    for i in temperatures:
        row = {j: matrix.get((i,j), ZERO) + sum(
            (matrix.get((i,k), ZERO)*weights[k][j] for k in contacts), ZERO)
               for j in temperatures}
        reduced[i] = {j: bounds(value) for j, value in row.items()}
        supplies[i] = bounds(response(row))
    return {"schema": "sim_heat.offline_two_contact_response/1", "sources": sources,
            "terminals": list(temperatures), "supplyResponseBoundsWPerK": reduced,
            "imposedTemperaturesK": {k: str(v) for k, v in temperatures.items()},
            "contactTemperatureBoundsK": {k: bounds(response(weights[k])+origin) for k in contacts},
            "terminalSupplyBoundsW": supplies, "nativeExecuted": False, "nativeQualified": False,
            "independentlyCertifiedReference": False, "runnerConsumable": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256")
    for side in ("left", "right"):
        for field in fields:
            parser.add_argument("--" + side + "-" + field, required=True)
    for flag in ("first-contact", "second-contact"):
        parser.add_argument("--" + flag, nargs=2, metavar=("LEFT", "RIGHT"), required=True)
    args = vars(parser.parse_args())
    def inputs(side):
        return tuple(args[side + "_" + field.replace("-", "_")] for field in fields)
    print(json.dumps(investigate(inputs("left"), inputs("right"), args["first_contact"],
                                 args["second_contact"]), indent=2))
