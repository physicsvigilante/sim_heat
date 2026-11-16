#!/usr/bin/env python3
"""F0 C1 F-01: exact-rational audit of one sealed, checking-only static export.

No OpenModelica invocation, source edits, new reference, tolerance override,
policy exemption, or native qualification. Green execution means the NEGATIVE
evidence was reproduced and the pre-native gate remains HOLD.
"""
import hashlib
import json
import math
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from h1 import reference

ROOT = Path(__file__).resolve().parents[3]
REL = Path("qualification/h1_c1/evaluation")
PLAN = ROOT / REL / "C1_PRIMARY_NATIVE_PLAN_NOT_LAUNCHED.json"
SPEC = ROOT / REL / "C1_FIRST_CHECKING_REFERENCE.json"
EXPECTED_PLAN_SHA = "f46b2621b38427ffc098d16d91695a134b7dc4d7f913021be625ee74b8a9319a"
EXPECTED_SPEC_SHA = "1b4b497d7427deae9e83fd712fbe9119e0c8e6599212d7762c828eca10b594c9"
EXPECTED_F0_SEAL = "d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b"
EXPECTED_MODEL_SHA = "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435"
EXPECTED_FIRST_STUDY_SHA = "b235d4242728c44dd994e09db3ffd92d197398dde3fe6c8f006a801981997fdc"
EXPECTED_MODAL_STUDY_SHA = "b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b"
EXPORT = "hotLead.G"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_checks():
    assert digest(PLAN) == EXPECTED_PLAN_SHA, "unapproved native plan identity"
    assert digest(SPEC) == EXPECTED_SPEC_SHA, "unapproved physical reference identity"
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["schema"] == "sim_heat.native_batch/1"
    assert len(plan["pins"]) == 23
    for relpath, expected_sha in plan["pins"].items():
        path = ROOT / relpath
        assert path.is_file() and not path.is_symlink(), relpath
        assert digest(path) == expected_sha, "frozen input changed: " + relpath
    assert digest(ROOT / "h1/cases/H1_C1_FIRST/model.mo") == EXPECTED_MODEL_SHA
    assert digest(ROOT / "h1/cases/H1_C1_FIRST/study.json") == EXPECTED_FIRST_STUDY_SHA
    assert digest(ROOT / "h1/cases/H1_C1_MODAL/model.mo") == EXPECTED_MODEL_SHA
    assert digest(ROOT / "h1/cases/H1_C1_MODAL/study.json") == EXPECTED_MODAL_STUDY_SHA
    return plan


def exact_fraction(text):
    return Fraction(Decimal(text))


def static_accuracy(value, exact, allowance):
    error = abs(Fraction.from_float(value) - exact)
    permitted = Fraction.from_float(allowance) / 100
    return {
        "displayedFloat": repr(value),
        "exactRationalError": str(error),
        "absoluteError": float(error),
        "nativeAllowance": allowance,
        "oneHundredthNativeAllowance": float(permitted),
        "errorAsFractionOfNativeAllowance": float(error / Fraction.from_float(allowance)),
        "marginTimes": float(Fraction.from_float(allowance) / error) if error else None,
        "strict100xPass": error <= permitted,
    }


def run():
    plan = source_checks()
    spec = reference.read_reference(SPEC)
    lead = spec["rods"]["hotLead"]
    assert lead["kind"] == "RodArea" and (lead["a"], lead["b"]) == ("H", "L")
    assert lead["k"] == 150 and lead["A"] == 0.0003 and lead["L"] == 0.1
    # The original task explicitly specified 150, 0.00030 and 0.10 in SI.
    # Decimal strings refer to exact authored decimal facts, not binary
    # interpretations of the input JSON floats or a native result.
    exact = (exact_fraction("150") * exact_fraction("0.00030")
             / exact_fraction("0.10"))
    assert exact == Fraction(9, 20)
    assert exact_fraction(str(lead["k"])) * exact_fraction(str(lead["A"])) / exact_fraction(str(lead["L"])) == exact

    bundle = reference.prepare(spec)  # frozen unchanged F0 checker, checking only
    assert bundle["seal"] == EXPECTED_F0_SEAL, "reproduced bundle/seal differs"
    assert bundle["nativeQualified"] is False
    assert bundle["origin"] == "analytical_reference_only"
    assert len(bundle["grid"]) == 4001 and len(bundle["columns"]) == 37
    assert bundle["units"][EXPORT] == "W/K"
    values = bundle["columns"][EXPORT]
    assert len(values) == 4001 and all(x == values[0] for x in values)
    observed = values[0]
    allowance = bundle["allowances"][EXPORT]
    assert math.isfinite(observed) and math.isfinite(allowance) and allowance > 0
    assert allowance == 64 * math.ulp(observed), "frozen static allowance changed"

    # The original result is the immediate lower binary64 neighbor of the
    # correctly rounded exact decimal 0.45. The latter is a proposal for
    # separately governed future reference work, NOT a corrected bundle.
    correctly_rounded = float(Decimal("0.45"))
    assert observed == math.nextafter(correctly_rounded, -math.inf)
    original = static_accuracy(observed, exact, allowance)
    nearest = static_accuracy(correctly_rounded, exact, allowance)
    above = static_accuracy(math.nextafter(correctly_rounded, math.inf), exact, allowance)
    assert original["strict100xPass"] is False
    assert original["marginTimes"] == 80.0
    assert nearest["strict100xPass"] is True
    assert nearest["marginTimes"] == 320.0
    assert above["strict100xPass"] is False
    assert above["marginTimes"] < 100.0
    assert bundle["method"]["maximumDiscrepancies"][EXPORT] == 0.0, (
        "frozen methods no longer agree; different issue")
    assert plan["branch"] == "experiment/h1-c1-f0-native-primary-once"

    return {
        "schema": "sim_heat.c1_f01_static_rounding_audit/1",
        "status": "reproduced_strict_100x_failure",
        "gate": "HOLD_NO_NATIVE_EXECUTION",
        "firstSubmissionChanged": False,
        "frozenF0SourceChanged": False,
        "nativeExecuted": False,
        "referenceModified": False,
        "referenceExceptionGranted": False,
        "planSha256": EXPECTED_PLAN_SHA,
        "checkedSourcePins": len(plan["pins"]),
        "checkingReferenceSha256": EXPECTED_SPEC_SHA,
        "reproducedReferenceSeal": bundle["seal"],
        "gridPoints": len(bundle["grid"]),
        "referenceChannels": len(bundle["columns"]),
        "export": EXPORT,
        "unit": "W/K",
        "physicalExactRational": str(exact),
        "physicalExactDecimal": "0.45",
        "originalSealedFloat": original,
        "hypotheticalNearestBinary64": nearest,
        "negativeUpperNeighborControl": above,
        "frozenTwoMethodDisagreement": 0.0,
        "note": ("The sealed frozen-F0 hotLead.G export fails literal per-export "
                 "100x physical-reference accuracy (80x only). Correct rounding "
                 "would give 320x, but this audit does not regenerate a bundle, "
                 "change a sealed value, or authorize an exception or native run."),
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2, allow_nan=False))
