"""Verify a TwinBridge replay, including per-series reported enclosure ratios.

Run with python -B -m tools.verify_twinbridge fresh-output.json.gz. The returned
summary retains the first oracle's units and original-allowance normalization.
"""
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import gzip
import json
from math import ulp
import sys

from qualification.h1_n13.heldout import oracle


# Tight source-enclosure budgets used by the frozen candidate for its ratio.
ABSOLUTE_BUDGET = {"K": Fraction(1, 10**8), "W": Fraction(1, 10**8),
                   "J": Fraction(1, 10**5)}
ANALYTICAL_GUARD = Fraction(1, 10**65)


def verify(data):
    if not __debug__:
        raise RuntimeError("TwinBridge verification requires enabled assertions")
    with localcontext() as context:
        context.prec = 80
        context.rounding = ROUND_HALF_EVEN
        summary = oracle.verify(data)
        # The frozen oracle checks units, identities, inventories and lengths.
        ratios = {(family, name): Fraction(ratio)
                  for family, maxima in data["maxErrorToBudgetBySeries"].items()
                  for name, ratio in maxima.items()}
        for index in range(1201):
            for family, quantities in oracle.expected(Decimal(index) / 10).items():
                for name, (unit, reference) in quantities.items():
                    sample = data[family][name]["values"][index]
                    if unit in ABSOLUTE_BUDGET:
                        budget = ABSOLUTE_BUDGET[unit]
                        guard = ANALYTICAL_GUARD
                    else:
                        # The solver uses the spacing of each emitted centre.
                        budget = Fraction(64, 100) * Fraction(ulp(sample))
                        guard = 0
                    bound = ratios[family, name] * budget + guard
                    if abs(Fraction(sample) - Fraction(reference)) > bound:
                        raise ValueError(f"understated error ratio for {family}.{name} at sample {index}")
    return summary


if __name__ == "__main__":
    with gzip.open(sys.argv[1], "rt", encoding="utf-8") as stream:
        print(json.dumps(verify(json.load(stream)), indent=2, sort_keys=True))
