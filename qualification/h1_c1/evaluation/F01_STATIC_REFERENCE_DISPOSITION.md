# H1-C1 F-01 — strict static-reference rounding disposition (CHECKING ONLY)

**Status: REPRODUCED DEFECT IN REFERENCE-ACCURACY EVIDENCE — HOLD, NO NATIVE EXECUTION.**
This is the Chat A response to independent [PR #28 review finding F-01](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-28/reviews/review-01-chat-b.md), **not** a native qualification, waiver, correction of an original author's answer, or revision of F0 physics/reference policy.

## Frozen inputs/identities

- Historic F0 source baseline: `dd8c9432abe97563414bb3ed809e61e673473812`.
- PR #28 reviewed head: `baabeb3ed176f4d9fa83d6be09a58b4f21fa8319`.
- Original first authored Modelica SHA-256: `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`; first study: `b235d4242728c44dd994e09db3ffd92d197398dde3fe6c8f006a801981997fdc`.
- Separate evaluator-modal study: `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b`.
- Checking-only specification: `1b4b497d7427deae9e83fd712fbe9119e0c8e6599212d7762c828eca10b594c9`; original checking bundle seal: `d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b`.
- Unlaunched original native plan SHA-256: `f46b2621b38427ffc098d16d91695a134b7dc4d7f913021be625ee74b8a9319a`.
- **No original submitted source, frozen reference checker, library, policy, preexisting bundle/seal or plan has been modified.** This branch adds only checking-only diagnostic material and an offline CI workflow.

## Exact arithmetic and floating-point diagnosis

The authored given values for `hotLead` are `k=150` W/(m·K), `A=0.00030` m² and `L=0.10` m, so mathematical `G=k*A/L=9/20=0.45` W/K (exact decimal rational).

The frozen F0 reference implementation uses binary64 arithmetic on JSON-parsed values and, for the stored parameter channel `hotLead.G`, emits `0.44999999999999996` W/K, one binary64 step below the correctly rounded real 0.45. The frozen static exported-parameter allowance is `64*ulp(stored)=3.552713678800501e-15` W/K. The strict 100× reference budget is the allowance divided by 100: `3.552713678800501e-17` W/K.

| Binary64 exported static value | Exact-rational absolute error (W/K) | Margin to native allowance | Strict reference accuracy ≥100×? |
|---|---:|---:|---|
| **Frozen sealed reference** `0.44999999999999996` | `4.440892098500626e-17` | **80×** | **FAIL** |
| Hypothetical correctly rounded `float(Decimal("0.45"))` | `1.1102230246251565e-17` | 320× | PASS **for that value only**, not for frozen seal |
| Adversarial upper neighbor `0.45000000000000007` | `6.661338147750939e-17` | 53⅓× | FAIL |

The unchanged frozen checker’s two algorithms both emit the same `hotLead.G`, so their zero difference is not an independent error bound against exact physical decimal givens. The reviewer independently checked the remaining dynamic and static channels and found no similar breach; this audit deliberately limits itself to this reproducible F-01 issue.

## Executable regression and intended interpretation

The first corrected CI attempt uncovered a further reproducibility limit: a host-local run of the unchanged floating-point F0 reference preparer emitted a **different seal** from the originally archived checking-only bundle. This is a reproducibility finding, **not authorization** to replace or reinterpret the archived reference. The independent Chat B review had already directly inspected and rehashed the actual original artifact; this audit only claims to repeat the static `hotLead.G` numerical behavior on its own host, not reconstruct every archived bundle byte.

`audit_f01_static_rounding.py`:
1. checks all 23 original native-plan SHA-pinned input files and original/assisted study identities, without executing that plan;
2. performs a **new host-local checking-only preparation** from unchanged F0 source and input, verifies the 4,001-point grid, 37 outputs and `nativeQualified=false`, and records its **new seal separately** from the immutable archived F0 reference seal; a host-local re-preparation is **not** assumed byte-identical to the original sealed ZIP;
3. evaluates `hotLead.G` with exact decimal-rational arithmetic (not float subtraction alone), reproduces the **80× failure**, checks the 320×/53⅓× neighbor controls, and demands the original algorithms' zero discrepancy;
4. emits machine-readable `status=reproduced_strict_100x_failure` and `gate=HOLD_NO_NATIVE_EXECUTION`.

**A green audit means the negative discrepancy was faithfully reproduced; it does NOT mean the frozen static reference passed qualification.** The existing reference, comparator allowances, seal and fixed original input files are unchanged. It does not create an alternative sealed reference or approve a one-off exception.

## Options requiring separate focused disposition

The safest forward choice is to retain the original sealed reference as **failed strict static accuracy** and, if scientifically justified, construct a separately versioned checking-only reference with a correctly rounded static export, explicit numerical provenance, and a **new** bundle/seal/plan identity. Such an alternate checking-reference production path requires separate scoped numerical/evidence review and cannot alter original frozen F0 production semantics. Alternatively, an explicit owner-approved policy exception could be documented *without* falsely claiming 100× compliance, but this would narrow the scientific claim and may leave native qualification blocked by the frozen contract. No such change or exception is implemented here.

The **F-02 native launch gate** remains separate and unsatisfied: approved exact workflow/source commit and plan identity, cross-run single-shot controls, pinned host/OMC/MSL/Python/packages, no retry, captured native output and later independent review are mandatory. Zero OpenModelica calls have been made for this C1 task.

## Requested focused review

Have Chat B check the exact new branch-only three-added-file diff, its current-commit offline CI and F-01 report. Required verdict is whether this **strict failure evidence** is accurate and whether the proposed distinct future reference is permissible without secretly modifying original evidence. Do **not** read this as approval to launch native or merge historical PR #28 or #29.
