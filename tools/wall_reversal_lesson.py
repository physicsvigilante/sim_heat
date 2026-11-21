"""Replay the worked steady composite-wall reversal and its constant-material control."""
from fractions import Fraction
import json
from pathlib import Path

from tools.join_variable_conductors import investigate


def replay():
    root = Path(__file__).resolve().parents[1] / "studies/composite_wall"
    inputs = (root / "study.json", root, root / "facts.json",
              "f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b")
    output = {}
    for material, slope in (("dissimilar", "0.00625"), ("constant", "0")):
        for drive, left, right in (("forward", "cold", "hot"), ("reverse", "hot", "cold")):
            result = investigate((inputs, left, "280", slope), (inputs, right, "280", "0"))
            a, b = (Fraction(t)-280 for t in result["contactTemperatureBoundsK"])
            qlo, qhi = map(Fraction, result["leftToRightHeatRateBoundsW"])
            if slope == "0":
                rise = 50
                q = 100 if drive == "forward" else -100
                valid = a <= rise <= b and qlo <= q <= qhi
            elif drive == "forward":
                valid = a <= 60 <= b and qlo <= 120 <= qhi
            else:
                # The exact reverse magnitude m satisfies m² - 1680m + 168000 = 0.
                def polynomial(m):
                    return m*m - 1680*m + 168000
                valid = (0 <= a <= b <= 100 and a*a+640*a <= 32000 <= b*b+640*b
                         and -200 <= qlo <= qhi <= 0 and polynomial(-qlo) <= 0 <= polynomial(-qhi))
            if not valid or max(b-a, qhi-qlo) > Fraction(1, 10**10):
                raise ValueError(f"{material} {drive} differs from the worked solution")
            output[f"{material}_{drive}"] = result
    return output


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
