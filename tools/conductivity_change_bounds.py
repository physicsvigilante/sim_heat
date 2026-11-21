"""Bound the effective resistance after changing one rod's conductivity."""
import argparse
from fractions import Fraction
import json
import re

from tools.resistance_sensitivity import investigate


def predict(study, root, facts, facts_sha256, rod, multiplier):
    if not isinstance(multiplier, str) or not re.fullmatch(
            r"[0-9]{1,32}(?:/[1-9][0-9]{0,31}|\.[0-9]{1,32})?", multiplier):
        raise ValueError("expected a positive decimal or rational conductivity multiplier")
    factor = Fraction(multiplier)
    if factor <= 0:
        raise ValueError("conductivity multiplier must be positive")

    base = investigate(study, root, facts, facts_sha256)
    if rod not in base["rods"]:
        raise ValueError("unknown rod in baseline")
    low, high = map(Fraction, base["rods"][rod]["relativeSensitivityBounds"])
    # Each rod dissipates a nonnegative fraction of the total thermal-network
    # quadratic form. Intersect its numerical enclosure with this physical range.
    low, high = max(0, low), min(1, high)
    if low > high:
        raise ValueError("inconsistent baseline sensitivity")
    max_trial_resistance = max(1 + s * (1/factor - 1) for s in (low, high))
    max_trial_conductance = max(1 + s * (factor - 1) for s in (low, high))
    rlow, rhigh = map(Fraction, base["effectiveResistanceBoundsKPerW"])
    return {"schema": "sim_heat.offline_conductivity_change_bounds/1",
            "rod": rod, "hypotheticalConductivityMultiplier": str(factor),
            "baselineResistanceBoundsKPerW": base["effectiveResistanceBoundsKPerW"],
            "predictedResistanceBoundsKPerW": [str(rlow/max_trial_conductance),
                                                str(rhigh*max_trial_resistance)],
            **{key: base[key] for key in ("terminals", "modelSha256", "studySha256",
                                          "factsSha256", "nativeExecuted", "nativeQualified",
                                          "independentlyCertifiedReference", "runnerConsumable")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("study", "root", "facts", "facts-sha256", "rod", "conductivity-multiplier"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(predict(args.study, args.root, args.facts, args.facts_sha256,
                             args.rod, args.conductivity_multiplier), indent=2))
