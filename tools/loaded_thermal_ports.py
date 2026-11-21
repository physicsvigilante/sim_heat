"""Predict signed heat flow through a two-terminal link between two released bath ports."""
import argparse
from fractions import Fraction
import json

from qualification.h1_n13.conduction import ONE, ZERO, interval
from tools.join_thermal_networks import bounds
from tools.terminal_response import investigate as terminal_response


def port_equivalent(law, port):
    if port not in law["terminals"]:
        raise ValueError("unknown released terminal")
    row = law["supplyResponseBoundsWPerK"][port]
    slope = interval(row[port])
    if slope.low <= 0:
        raise ValueError("released-port conductance is unresolved")
    maintained = {n: Fraction(t) for n, t in law["imposedTemperaturesK"].items() if n != port}
    origin = min(maintained.values())
    # Solve the port's zero-supply balance with all other baths held fixed.
    forcing = sum((interval(row[n]) * (t-origin) for n, t in maintained.items()), ZERO)
    return origin - forcing/slope, ONE/slope


def investigate(left_inputs, link_inputs, right_inputs, left_port, right_port):
    left, link, right = (terminal_response(*args) for args in (left_inputs, link_inputs, right_inputs))
    if len(link["terminals"]) != 2:
        raise ValueError("coupling link requires exactly two terminals")
    a, b = link["terminals"]
    slope = interval(link["supplyResponseBoundsWPerK"][a][a])
    if slope.low <= 0:
        raise ValueError("link conductance is unresolved")
    resistance = ONE/slope
    tl, rl = port_equivalent(left, left_port)
    tr, rr = port_equivalent(right, right_port)
    flow = (tl-tr)/(rl+resistance+rr)
    sources = {side: {k: law[k] for k in ("modelSha256", "studySha256", "factsSha256")}
               for side, law in (("left", left), ("link", link), ("right", right))}
    return {"schema": "sim_heat.offline_loaded_ports/1", "sources": sources,
            "leftPort": left_port, "rightPort": right_port, "linkTerminalsLeftToRight": [a,b],
            "leftOpenTemperatureBoundsK": bounds(tl), "rightOpenTemperatureBoundsK": bounds(tr),
            "leftPortResistanceBoundsKPerW": bounds(rl), "rightPortResistanceBoundsKPerW": bounds(rr),
            "linkResistanceBoundsKPerW": bounds(resistance),
            "leftLoadedTemperatureBoundsK": bounds(tl-flow*rl),
            "rightLoadedTemperatureBoundsK": bounds(tr+flow*rr),
            "leftToRightHeatRateBoundsW": bounds(flow),
            "nativeExecuted": False, "nativeQualified": False,
            "independentlyCertifiedReference": False, "runnerConsumable": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    fields = ("study", "root", "facts", "facts-sha256")
    for side in ("left", "link", "right"):
        for name in fields:
            parser.add_argument("--" + side + "-" + name, required=True)
    for side in ("left", "right"):
        parser.add_argument("--" + side + "-port", required=True)
    args = vars(parser.parse_args())
    bundles = [tuple(args[side+"_"+field.replace("-", "_")] for field in fields)
               for side in ("left", "link", "right")]
    print(json.dumps(investigate(*bundles, args["left_port"], args["right_port"]), indent=2))
