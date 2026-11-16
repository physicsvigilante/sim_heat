# H1-C1 F-01 — prospective V2 checking-only reference (not native)

**Status:** New independently identified *candidate* analytical checking reference. **Not** a retrospective correction of the first author, historic frozen F0 checker, original F0 checking bundle, original checking-input file, or native plan. No OpenModelica work is performed. The native gate remains **HOLD** until this V2 reference and a separate one-shot host plan pass review.

## Motivation and exact input

The [PR #28 independent review](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-28/reviews/review-01-chat-b.md) identified an actual strict 100× reference-error failure in original exported `hotLead.G`: exact decimal task `150 * 0.00030 / 0.10 = 9/20 = 0.45 W/K`; original binary64 `0.44999999999999996` and original native allowance `64*ulp=3.552713678800501e-15 W/K` give a margin of **80×**, not ≥100×. [PR #30 independent negative-audit review](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-30/reviews/review-01-chat-b.md) confirmed that the original failed reference is preserved and no exception is granted.

The first author `model.mo`, `study.json`, `AUTHOR_NOTES.md`, Stage 1 task comment, all original frozen F0 production/checker files and the separately assisted `H1_C1_MODAL` analysis remain byte-identical. Original checking-input SHA-256 `1b4b497d7427deae9e83fd712fbe9119e0c8e6599212d7762c828eca10b594c9`, old reference seal `d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b`, original **unlaunched** native plan SHA-256 `f46b2621b38427ffc098d16d91695a134b7dc4d7f913021be625ee74b8a9319a`.

## New versioned method and new seal

`prepare_reference_v2.py` uses the unchanged frozen F0 generic reference preparer to generate **new** checking-only trajectory data from the previously sealed independent physical facts. It then derives `hotLead.G=9/20 W/K` from exact authored **decimal rational** quantities, rounding **once** to the nearest representable IEEE binary64 float `0.45`. No authored physical input, original reference file, existing F0 tolerance, temperature, rod flow, energy equation, numerical time grid or historical seal is edited.

This is explicitly identified in the new bundle's `method.staticExportRoundingV2` metadata. The distinct new bundle receives its own canonical SHA-256 seal under the unchanged `reference.fingerprint` method. It retains `origin=analytical_reference_only` and `nativeQualified=false`; its original reference and parent seal references remain visible. No old plan may consume its new seal.

## Independent mathematical validation

The standalone V2 program separately transcribes the task's SI givens and graph into an **85-decimal-digit two-state system**. It uses independently constructed affine spectral projectors, body-state integrals and signed thermal-flow equations, rather than reusing a saved native result or F0's affine-augmented matrix exponential. It independently compares **all 37 export channels at 4,001 timestamps (148,037 values)** against this mathematical solution using the unmodified original frozen **100× native allowance** for *each scalar and instant*. Exact rational/decimal static inputs (including `hotLead.G`) are checked; circular geometry uses high-precision π. All four integrated body/bath flow histories are also compared against the independent analytic integrals with 100× energy allowances.

The report stores maximum errors by channel, worst normalized reference/native allowance, exact model/study/reference/plan hashes, and strict status. Any failing scalar/instant or integral causes the candidate to REFUSE, not to auto-widen a tolerance or rewrite a source model.

For reproducibility the script creates **two separately prepared V2 bundle files** in one clean run, preserves both seals even on mismatch, and emits digest differences if they do not match. Environment versions and platform are recorded. This is only a same-host check; it does **not** certify cross-run or cross-host/BLAS determinism. The prior seal mismatch on a failed developer CI run had no retained alternate digest and remains an unresolved provenance question. A future independently reviewed clean-host rerun and field comparison are mandatory before treating this newly prepared reference as certified.

## Preserved gates

1. This reference is checking-only, not a native result, a completed C1 transfer or a correction of historical errors.
2. The new V2 bundle is separately hashed/sealed in the CI artifact and never written into an existing historic reference filename or old branch.
3. The original F0 reference preflight failure and previous failed CI runs remain intact and accurately classified.
4. No OpenModelica version query, build or launch is permitted by this work. A future **new plan SHA and exact commit/host/one-shot approved native workflow** remains required, along with tolerance/grid companions and post-native independent review.
5. This separate source PR needs a focused R2 review based on exact-head green offline CI and independent rechecking of 100× error, reference identity and reproducibility limits. A successful CI result is **candidate mathematical evidence, not automatic release**.
