"""Replay the worked steady composite-wall reversal and its constant-material control."""
from fractions import Fraction
import json
from pathlib import Path

from tools.join_variable_conductors import investigate


def check_flow(bounds, fraction_of_magnitude, exact_magnitude, component):
    a, b = map(Fraction, bounds)
    low, high = sorted((a/fraction_of_magnitude, b/fraction_of_magnitude))
    if exact_magnitude is None:
        # The physical reverse magnitude is the unique root in [0, 200] W.
        def polynomial(m):
            return m*m - 1680*m + 168000
        contains = 0 <= low <= high <= 200 and polynomial(high) <= 0 <= polynomial(low)
    else:
        contains = low <= exact_magnitude <= high
    if not contains or not 0 <= b-a <= Fraction(1, 10**10):
        raise ValueError(f"{component} flow differs from the worked solution")


def replay():
    root = Path(__file__).resolve().parents[1] / "studies/composite_wall"
    inputs = (root / "study.json", root, root / "facts.json",
              "f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b")
    output = {}
    for material, slope in (("dissimilar", "0.00625"), ("constant", "0")):
        for drive, left, right in (("forward", "cold", "hot"), ("reverse", "hot", "cold")):
            result = investigate((inputs, left, "280", slope), (inputs, right, "280", "0"))
            a, b = (Fraction(t)-280 for t in result["contactTemperatureBoundsK"])
            if slope == "0":
                magnitude = 100
                valid = a <= 50 <= b
            elif drive == "forward":
                magnitude = 120
                valid = a <= 60 <= b
            else:
                magnitude = None
                valid = 0 <= a <= b <= 100 and a*a+640*a <= 32000 <= b*b+640*b
            if not valid or not 0 <= b-a <= Fraction(1, 10**10):
                raise ValueError(f"{material} {drive} interface differs from the worked solution")
            check_flow(result["leftToRightHeatRateBoundsW"], 1 if drive == "forward" else -1,
                       magnitude, "contact")
            for side, released in (("left", left), ("right", right)):
                parts = {"facing": 1, "strip": Fraction(1, 4), "insert": Fraction(-3, 4)}
                for rod, share in parts.items():
                    check_flow(result[side]["rodHeatFlowBoundsW"][rod], share, magnitude, side+"."+rod)
                bath = "hot" if released == "cold" else "cold"
                check_flow(result[side]["terminalSupplyBoundsW"][bath], 1 if bath == "hot" else -1,
                           magnitude, side+"."+bath)
            output[f"{material}_{drive}"] = result
    return output


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
