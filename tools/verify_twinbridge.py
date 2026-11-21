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
        # The frozen oracle has checked units, identities, inventories and lengths.
        # Convert each ratio once. All subsequent comparisons use exact rationals.
        bounds = {}
        for family, ratios in data["maxErrorToBudgetBySeries"].items():
            for name, ratio in ratios.items():
                series = data[family][name]
                unit = series["unit"]
                if unit in ABSOLUTE_BUDGET:
                    limit = ABSOLUTE_BUDGET[unit]
                    guard = ANALYTICAL_GUARD
                else:
                    # TwinBridge C and G are exact, constant integers.
                    limit = Fraction(64, 100) * Fraction(ulp(series["values"][0]))
                    guard = 0
                bounds[family, name] = Fraction(ratio) * limit + guard

        for index in range(1201):
            for family, quantities in oracle.expected(Decimal(index) / 10).items():
                for name, (_, reference) in quantities.items():
                    centre = Fraction(data[family][name]["values"][index])
                    # A discrepancy beyond the claim plus oracle uncertainty
                    # disproves the reported series maximum at this sample.
                    if abs(centre - Fraction(reference)) > bounds[family, name]:
                        raise ValueError(f"understated error ratio for {family}.{name} at sample {index}")
    return summary


if __name__ == "__main__":
    with gzip.open(sys.argv[1], "rt", encoding="utf-8") as stream:
        print(json.dumps(verify(json.load(stream)), indent=2, sort_keys=True))
