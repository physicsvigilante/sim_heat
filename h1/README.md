# H1 offline implementation candidate - slices 1 and 2, review corrections

This starts the user-authorized offline implementation after the external review.
It is **not accepted H1, native qualification, or a safe arbitrary-Modelica runner**.
See [decision](../docs/H1_OFFLINE_DECISION.md), [amendment](../docs/H1_OFFLINE_AMENDMENT.md)
and [external review](../docs/reviews/20261115_EXTERNAL_REVIEW.md).


## Current correction: R1/R2 (author-tested; scoped recheck pending)

See [correction record](../docs/H1_REVIEW_CORRECTIONS.md) and the preserved
[external implementation review](../docs/reviews/20261115_IMPLEMENTATION_REVIEW.md.gz).
`temporal.py` derives conservative whole-window rate bounds from independently
supplied physical facts, not sampled/candidate derivatives. Reference bundles
now use `sim_heat.reference_bundle/2` and contain a sealed sensitivity-aware
matching window. Version 1 bundles remain historical and are not silently
upgraded. Reprepare them into fresh files with the documented command below.
No trajectory or energy allowance has been increased. CSV extra columns are
explicitly reported as ignored, never used as physical evidence.

The S1 reference provenance note is corrected without changing its physical
numbers or any authored model/study. Regenerated reference identities and the
baseline/new test runs are recorded under `evidence/r1r2/`. Native execution,
checker freeze, reference-accuracy acceptance and the scoped independent recheck
remain separate pending gates. This is not a new physics capability.

## Current addition: Slice 2 (offline, not accepted)

The checking path is implemented in `reference.py`, `verification.py` and
`verify.py`; see [Slice 2 scope and limitations](../docs/H1_SLICE2_VERIFICATION.md).
It uses separately entered facts in `reference_cases/` and tests synthetic CSVs
against local physical checks. Neither references nor successful synthetic checks
are native results. The original read-only admission CLI is unchanged.

```sh
python -B -m unittest discover -s h1/tests -v
python -B -m h1.verify prepare --study h1/cases/D2/study.json --root h1/cases \
  --reference h1/reference_cases/D2.json --out /path/to/fresh-reference.json
python -B -m h1.verify check --study h1/cases/D2/study.json --root h1/cases \
  --bundle /path/to/fresh-reference.json --seal <recorded-seal> \
  --csv /path/to/candidate.csv --receipt /path/to/candidate-metadata.json
```

`prepare` explicitly writes one fresh artifact; `check` reads only. Exit codes
are 0 for candidate checks passed, 2 for refusal, 3 for numerical checks failed.
These codes never assert native acceptance. SciPy is needed for reference
preparation, not the original admission CLI. No automatic installation occurs.
Evidence and development failures for this addition are under `evidence/slice2/`.
The notes below describe the original slice; its report remains unchanged.

## Slice 1 use from repository root

```sh
python -B -m unittest discover -s h1/tests -v
python -B -m h1 h1/cases/D2/study.json --root h1/cases
python -B -m h1 h1/cases/D2_K2/study.json --root h1/cases
```

The CLI reads only, prints JSON and exits 0 for offline admission or 2 for refusal.
There is no `run` command, import-time compiler work, shell command execution or
native-result fallback. NumPy is used for scaled junction-condition preflight;
if needed but unavailable, validation refuses instead of installing it.

`model.py` tokenizes and fully consumes the allowed composition subset, validates
quantity types/parameters, builds ideal nodes and conductor connectivity, checks
closure/conditioning, resolves public requests and enumerates internal exports.
`study.py` checks strict JSON, source links, paths, hashes and the one-rod
conductivity revision. `policy.py` supplies bounded grids and local error-policy
helpers. `decoder.py` validates synthetic CSV shape and time association; decoding
alone never establishes accepted native output.

Seven exposed model/study fixtures implement S1, D1, D2, D2-K2, EQ, REV and ISO.
S1/D1/D2 model bytes match the original spike examples. New numerical variants
are illustrative cases, not new textbook givens or blind tests. No C1 selected.

The tests exercise offline behavior and separately stated reference facts/signs.
They do not execute Modelica, prove wrapper equations correct at runtime, or
complete the independent reference pipeline. All public request results remain
`not_computed`, even when the physical model passes offline admission.

## Evidence and remaining work

See `evidence/` for retained development failures, the passing run and a sample
read-only validation report. The first smoke check incorrectly rejected metadata
request ID `flow` as a Modelica keyword. It was fixed. The first full test run
had one overly exact floating-point assertion; its numerical assertion was fixed
without changing an acceptance tolerance. Neither was a post-freeze challenge.

Still pending: independent code review, exact MSL/runtime pairing, compiled wrapper
and CSV-export qualification, reusable independent reference/envelope generation,
full numerical/conservation verification, native runner/containment, numerical
companions, post-freeze authoring/transfer and educational evidence. F1-F6 retain
those stage-specific closure obligations. No changes to main or the old spike.
