"""H1-N2 read-only common-time diagnostics for the fixed original T1-T task.

Neither a native comparator nor a new checking reference. Both candidate CSVs
must separately PASS the unmodified H1 verifier against their own sealed bundles.
No compiler, installer, native runner, Modelica, reference writer, or permission
logic is imported or invoked. Synthetic success never means native qualification.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path

from h1.decoder import decode_csv
from h1.model import Refusal, require
from h1.policy import local_allowance
from h1.study import Study, load_study
from h1.verification import check_candidate

HERE = Path(__file__).resolve().parents[1]
ORIGINAL_MODEL_SHA = "2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae"
ORIGINAL_STUDY_SHA = "12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a"
ORIGINAL_FACTS_SHA = "39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf"
ORIGINAL_ID = "H1T1TFirstAttemptV1"
PUBLIC_IDS = frozenset({
    "t_ridge_temp", "t_collar_temp", "t_plug_temp",
    "t_ridge_energy", "t_plug_energy", "t_collar_to_plug",
    "t_upper_lower_link", "t_upper_minus_cool",
})
STATIC_LEGACY_REFUSALS = (
    "T02.G", "T06.A", "T06.G", "T07.G", "T08.G", "T10.G", "T_Plug.C"
)


def _need(condition, explanation):
    require(bool(condition), "n2_comparison", explanation)


def _positive_finite(number):
    return type(number) in (float, int) and math.isfinite(number) and number > 0


def _typed_equal(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(_typed_equal(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(_typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def _original_inputs():
    """Reload exact original public facts; no derived or solver-provided values."""
    facts_path = HERE / "h1_n1/reference-facts.json"
    model_path = HERE / "h1_n1/inputs/T/model.mo"
    study_path = HERE / "h1_n1/inputs/T/study.json"
    for path, digest in ((facts_path, ORIGINAL_FACTS_SHA),
                         (model_path, ORIGINAL_MODEL_SHA),
                         (study_path, ORIGINAL_STUDY_SHA)):
        _need(sha256(path.read_bytes()).hexdigest() == digest,
              "original source/facts byte identity mismatch")
    return json.loads(facts_path.read_bytes()), json.loads(study_path.read_bytes())


def _reload_study(given):
    _need(type(given) is Study, "validated H1 Study required")
    loaded = load_study(given.path, given.path.parent)
    _need(loaded.sha256 == given.sha256 and
          loaded.model_sha256 == given.model_sha256 and
          _typed_equal(loaded.data, given.data),
          "study changed after offline admission")
    return loaded


def _companion_contract(first, second, a, b, variant):
    _need(type(variant) is str and variant in ("tight", "dense"),
          "undeclared companion")
    original_spec, original_study = _original_inputs()
    _need(first.sha256 == ORIGINAL_STUDY_SHA and
          first.model_sha256 == second.model_sha256 == ORIGINAL_MODEL_SHA and
          _typed_equal(first.data, original_study),
          "primary is not the original source study")
    expected_analysis = dict(original_study["analysis"])
    if variant == "tight":
        expected_analysis["tolerance"] = 1e-10
    else:
        expected_analysis["intervals"] = 4800
    expected_study = deepcopy(original_study)
    expected_study["id"] = ORIGINAL_ID + "_N1_" + variant.upper()
    expected_study["analysis"] = expected_analysis
    _need(_typed_equal(second.data, expected_study),
          "companion changed non-analysis authored fields")
    expected_spec = deepcopy(original_spec)
    _need(_typed_equal(a["spec"], expected_spec),
          "primary reference facts are not the pinned original")
    expected_spec["id"] = expected_study["id"]
    expected_spec["studySha256"] = second.sha256
    expected_spec["analysis"] = expected_analysis
    _need(_typed_equal(b["spec"], expected_spec),
          "companion changed original physical/reference facts")
    _need(first.request_report["admitted"] and second.request_report["admitted"],
          "study request admission refused")
    _need(len(first.data["requests"]) == 8 and
          {r["id"] for r in first.data["requests"]} == PUBLIC_IDS,
          "original eight requests not preserved")
    _need(set(a["columns"]) == set(b["columns"]) and
          set(a["columns"]) == set(a["allowances"]) == set(b["allowances"]) and
          a["units"] == b["units"] and len(a["columns"]) == 77,
          "mandatory export/units/allowance inventory changed")
    _need(set(a["flowIntegrals"]) == set(b["flowIntegrals"]) and
          len(a["flowIntegrals"]) == 5, "flow-integral inventory changed")
    for bundle, intervals in ((a, 2400), (b, expected_analysis["intervals"])):
        times = bundle["grid"]
        _need(type(times) is list and len(times) == intervals+1 and
              all(type(t) in (float, int) and math.isfinite(t) and
                  t == (2400*i/intervals) for i, t in enumerate(times)),
              "exact declared planned grid is required")
        _need(all(_positive_finite(x) for x in bundle["allowances"].values()),
              "invalid per-output allowance")
    _need(a["grid"] == b["grid"] if variant == "tight"
          else b["grid"][::2] == a["grid"],
          "primary and companion lack exact common planned times")


def _port_target(target):
    _need(type(target) is str and target.count(".") == 1,
          "bad public port target")
    owner, port = target.split(".")
    _need(port in ("port", "port_a", "port_b"),
          "unsupported port kind")
    return owner + {"port": ".T", "port_a": ".T_a", "port_b": ".T_b"}[port]


def _request_operands(request):
    op = request["op"]
    if op == "temperature":
        return (_port_target(request["target"]),)
    if op in ("heatFlow", "energyChange"):
        return (request["target"] + (".Q_flow" if op == "heatFlow" else ".dU"),)
    if op == "temperatureDifference":
        return (_port_target(request["a"]), _port_target(request["b"]))
    _need(False, "unsupported original request operation")


def _checks(primary_columns, companion_columns, a, requests):
    primary_grid = a["grid"]
    keys = sorted(a["columns"])
    _need(set(primary_columns) == set(companion_columns) == set(keys),
          "comparison candidate inventory differs")
    _need(len(primary_grid) == 2401, "primary grid drift")
    checks = []

    def assess(name, left, right, allowance, unit):
        _need(_positive_finite(allowance) and
              len(left) == len(right) == len(primary_grid),
              "invalid original allowance or comparison length: " + name)
        _need(all(type(x) in (float, int) and math.isfinite(x)
                  for x in left + right), "nonfinite candidate value")
        diffs = [abs(x-y) for x,y in zip(left, right)]
        _need(all(math.isfinite(x) for x in diffs),
              "overflowing difference refused")
        worst = max(range(len(diffs)), key=diffs.__getitem__)
        maximum = diffs[worst]
        ratio = maximum / allowance
        _need(math.isfinite(ratio), "overflowing primary-only ratio")
        checks.append({"quantity": name, "unit": unit,
                       "worstTime": primary_grid[worst],
                       "maximumDifference": maximum,
                       "primaryAllowance": allowance,
                       "maximumRatio": ratio,
                       "passed": maximum <= allowance})

    for name in keys:
        assess(name, list(primary_columns[name]), list(companion_columns[name]),
               a["allowances"][name], a["units"][name])
    for request in requests:
        terms = _request_operands(request)
        _need(all(t in a["columns"] for t in terms),
              "public request references missing operand")
        if len(terms) == 1:
            left = list(primary_columns[terms[0]])
            right = list(companion_columns[terms[0]])
            eps = a["allowances"][terms[0]]
            unit = a["units"][terms[0]]
        else:
            x, y = terms
            left = [p-q for p,q in zip(primary_columns[x], primary_columns[y])]
            right = [p-q for p,q in zip(companion_columns[x], companion_columns[y])]
            reference_difference = [p-q for p,q in zip(a["columns"][x], a["columns"][y])]
            _need(all(math.isfinite(z) for z in reference_difference),
                  "nonfinite original difference")
            eps = local_allowance("K", max(abs(z) for z in reference_difference))
            unit = "K"
        assess("request:" + request["id"], left, right, eps, unit)
    _need(len(checks) == 85 and
          {c["quantity"] for c in checks[77:]} ==
          {"request:" + k for k in PUBLIC_IDS},
          "77 exports and 8 observations mandatory")
    return checks


def compare_candidates(primary_study, primary_reference, primary_csv,
                       primary_receipt, primary_seal, companion_study,
                       companion_reference, companion_csv, companion_receipt,
                       companion_seal, *, variant):
    """Compare independently verified, untrusted CSVs; NEVER authorize native use.

    The checker consumes the original primary seal/allowances as supplied
    prospectively. Authenticity and pre-output sealing chronology remain
    external evidence obligations, not something this function can certify.
    """
    _need(type(primary_csv) is str and type(companion_csv) is str and
          type(primary_seal) is str and type(companion_seal) is str,
          "read-only candidate bytes and seal identifiers required")
    # Snapshot the inputs before both independent verifications and comparison.
    first = _reload_study(deepcopy(primary_study))
    second = _reload_study(deepcopy(companion_study))
    a, b = deepcopy(primary_reference), deepcopy(companion_reference)
    ar, br = deepcopy(primary_receipt), deepcopy(companion_receipt)
    _companion_contract(first, second, a, b, variant)
    verified_a = check_candidate(first, a, primary_csv, ar, primary_seal)
    verified_b = check_candidate(second, b, companion_csv, br, companion_seal)
    _need(verified_a["status"] == verified_b["status"] == "checks_passed" and
          verified_a["nativeQualified"] is False and verified_b["nativeQualified"] is False and
          verified_a["nativeExecuted"] is False and verified_b["nativeExecuted"] is False,
          "independent per-run H1 verification did not pass")
    # The inherited decoder enforces sealed time windows, actual sample data
    # and no interpolation. Compare values ONLY at the primary planned times.
    first_decoded = decode_csv(primary_csv, tuple(a["columns"]),
                               tuple(first.grid),
                               maximum_shift=a["temporalPolicy"]["maximumShift"])
    second_decoded = decode_csv(companion_csv, tuple(b["columns"]),
                                tuple(second.grid),
                                maximum_shift=b["temporalPolicy"]["maximumShift"])
    _need(first_decoded["status"] == second_decoded["status"] == "decoded_only",
          "candidate decoding refused")
    indexes = {t: i for i, t in enumerate(b["grid"])}
    _need(len(indexes) == len(b["grid"]) and
          all(t in indexes for t in a["grid"]),
          "interpolation/changed nominal timestamps refused")
    pairs = [indexes[t] for t in a["grid"]]
    ac = {k: list(v) for k,v in first_decoded["columns"].items() if k != "time"}
    bc = {k: [v[j] for j in pairs] for k,v in second_decoded["columns"].items()
          if k != "time"}
    checks = _checks(ac, bc, a, first.data["requests"])
    _need(verified_a["modelSha256"] == verified_b["modelSha256"] == ORIGINAL_MODEL_SHA and
          verified_a["referenceSeal"] == primary_seal and
          verified_b["referenceSeal"] == companion_seal,
          "unbound source or reference seal")
    return {
        "schema": "sim_heat.h1_n2.primary_companion_check/1",
        "stage": "offline_comparison_only",
        "status": "checks_passed" if all(c["passed"] for c in checks) else "checks_failed",
        "evidenceKind": "synthetic_or_unattested_candidate_only",
        "nativeQualified": False, "nativeExecuted": False, "runtimeReady": False,
        "independentlyCertifiedReference": False,
        "referenceAccuracyCertified": False,
        "originalCheckingCentresAdopted": False,
        "staticCheckingPhysical100xRefusalsRetained": list(STATIC_LEGACY_REFUSALS),
        "nativeExecutionBlockersRetained": 8,
        "method": "unmodified per-run H1 verification then exact common planned timestamps",
        "comparisonPolicy": "primary presealed per-output allowances ONLY; never companion/sum/max",
        "variant": variant,
        "modelSha256": ORIGINAL_MODEL_SHA,
        "primaryStudySha256": first.sha256, "companionStudySha256": second.sha256,
        "primaryReferenceSeal": primary_seal, "companionReferenceSeal": companion_seal,
        "primaryCsvSha256": sha256(primary_csv.encode()).hexdigest(),
        "companionCsvSha256": sha256(companion_csv.encode()).hexdigest(),
        "commonSamples": len(a["grid"]),
        "perRunChecks": {"primary": verified_a["status"], "companion": verified_b["status"]},
        "exportsCompared": 77, "publicObservationsCompared": 8,
        "checks": checks,
        "limit": "not native execution attestation, not certified runner reference, not release permission",
    }
