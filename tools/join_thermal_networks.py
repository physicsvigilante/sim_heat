"""Join two validated steady terminal laws through a single ideal, storage-free contact."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import Box, ZERO
from tools.terminal_response import investigate as terminal_response


def bounds(value):
    return [str(x) for x in value.span()]


def join(left, right, left_port, right_port):
    """Eliminate the common contact by imposing zero net heat supply there."""
    external = []
    block = {}
    contact_row = {}
    contact_column = {}
    temperatures = {}
    pivot = ZERO
    for side, law, port in (("left", left, left_port), ("right", right, right_port)):
        if port not in law["terminals"]:
            raise ValueError(f"unknown {side} contact terminal")
        matrix = law["supplyResponseBoundsWPerK"]
        def coefficient(i, j):
            return Box.bounds(*map(Fraction, matrix[i][j]))
        pivot += coefficient(port, port)
        retained = [n for n in law["terminals"] if n != port]
        for i in retained:
            label = side + "." + i
            external.append(label)
            temperatures[label] = Fraction(law["imposedTemperaturesK"][i])
            contact_row[label] = coefficient(port, i)
            contact_column[label] = coefficient(i, port)
            for j in retained:
                block[label, side + "." + j] = coefficient(i, j)
    if pivot.low <= 0:
        raise ValueError("contact conductance is unresolved")
    weights = {j: -contact_row[j] / pivot for j in external}
    # Subtract a common reference to avoid large offset terms in the heat rates.
    origin = min(temperatures.values())
    offsets = {j: temperatures[j] - origin for j in external}
    contact_offset = sum((weights[j] * offsets[j] for j in external), ZERO)
    reduced = {}
    supplies = {}
    for i in external:
        row = {j: block.get((i, j), ZERO) + contact_column[i]*weights[j] for j in external}
        reduced[i] = {j: bounds(v) for j, v in row.items()}
        supplies[i] = bounds(sum((row[j]*offsets[j] for j in external), ZERO))
    return {"terminals": external, "supplyResponseBoundsWPerK": reduced,
            "imposedTemperaturesK": {n: str(t) for n, t in temperatures.items()},
            "contactTemperatureBoundsK": bounds(contact_offset + origin),
            "terminalSupplyBoundsW": supplies}


def investigate(left_inputs, right_inputs, left_port, right_port):
    left = terminal_response(*left_inputs)
    right = terminal_response(*right_inputs)
    source_fields = ("modelSha256", "studySha256", "factsSha256")
    return {"schema": "sim_heat.offline_joined_terminal_response/1",
            "sources": {side: {**{k: law[k] for k in source_fields}, "contact": port}
                        for side, law, port in (("left", left, left_port), ("right", right, right_port))},
            **join(left, right, left_port, right_port),
            "nativeExecuted": False, "nativeQualified": False,
            "independentlyCertifiedReference": False, "runnerConsumable": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = ("study", "root", "facts", "facts-sha256")
    for side in ("left", "right"):
        for name in (*inputs, "port"):
            parser.add_argument("--" + side + "-" + name, required=True)
    args = vars(parser.parse_args())
    def bundle(side):
        return tuple(args[side + "_" + n.replace("-", "_")] for n in inputs)
    print(json.dumps(investigate(bundle("left"), bundle("right"), args["left_port"], args["right_port"]),
                     indent=2))
