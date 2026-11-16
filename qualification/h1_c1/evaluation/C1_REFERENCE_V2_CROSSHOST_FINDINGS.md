# H1-C1 V2 reference — observed two-host and historical-seal reproducibility limits

**Recorded outcome: BITWISE REPRODUCIBILITY REFUSED; MATHEMATICAL/NUMERICAL ACCURACY REMAINS CHECKING-ONLY. NATIVE GATE HOLD.**
This is a forensic interpretation of actual GitHub-hosted **offline** evidence, not a substitute sealed reference, native run authorization, V2 reference change, tolerance waiver or resolution of the prior frozen F0 80× failure.

## Immutable reference identities

| Record | Source/run | Exact checking-only reference seal |
|---|---|---|
| Historical failed F0 reference | Original [PR #28 preflight #43895266125](https://github.com/physicsvigilante/sim_heat/actions/runs/43895266125) | `d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b` |
| PR #31 independently reviewed V2 candidate | [Exact-head CI #43915934653](https://github.com/physicsvigilante/sim_heat/actions/runs/43915934653), source `d857c8e807612026ecdf624277b4ace3977fefe3`, [artifact #14249313720](https://github.com/physicsvigilante/sim_heat/actions/runs/43915934653/artifacts/14249313720) | `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9` |
| Two fresh V2 processes on Ubuntu 22.04 | [Reproduction CI #43921113470](https://github.com/physicsvigilante/sim_heat/actions/runs/43921113470), source `86cbe18ba87ab3daf813d3bbff2d753072385fe5`, [artifact #14254152610](https://github.com/physicsvigilante/sim_heat/actions/runs/43921113470/artifacts/14254152610) | `c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07` |
| Two fresh V2 processes on Ubuntu 24.04 | Same exact source, different hosted OS, [artifact #14254052553](https://github.com/physicsvigilante/sim_heat/actions/runs/43921113470/artifacts/14254052553) | **Same** `c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07` |

Both two-host artifacts have their own captured `runtime.json`, `wheels.sha256`, full V2 bundles, reports, logs and negative-control receipts. Each host used Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, mpmath 1.3.0, threadpoolctl 3.6.0, and the **same four downloaded wheel archive SHA-256s**. Actual loaded BLAS is OpenBLAS 0.3.30 (Haswell dispatch, four threads reported) on both hosts. The hosted CPUs/OS images differ (22.04: AMD EPYC 7763, image 20261111.360.2; 24.04: AMD EPYC 9V74, image 20261111.370.1). Those facts are directly captured as provenance, **not proof of what caused the old/new numerical difference**; the reviewed PR #31 run lacked equivalent recorded BLAS/CPU provenance.

## Saved evidence and field-level diagnosis

The **two newly prepared host bundles are byte-identical to each other** within and across processes (new V2 bundle raw SHA-256 `456b82081aa97b59f55e86830ddabfc36f14fd74991542e350a2266e0f9962f5`). Each recalculated canonical seal is internally valid. However, both differ from the independently reviewed PR #31 saved bundle (raw SHA-256 `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368`). Its prior F0-reprepared parent seal was `d76c98…`; the new hosts independently recorded `e92e1a00d9c45d4bb91f458f3750ba189f117fcdecd8b56c693e0fc57476d2cb` as their parent. **Neither is substituted for the other.**

The [immutable forensic field-diff CI #43921830450](https://github.com/physicsvigilante/sim_heat/actions/runs/43921830450) ([artifact #14255040340](https://github.com/physicsvigilante/sim_heat/actions/runs/43921830450/artifacts/14255040340), full ZIP SHA-256 `892df4986191246bf9d37dd3326bd3de28db5181ae9ede08f5ddcecb809c6f75`) independently downloaded the prior saved CI artifacts and compared their actual JSON values without rerunning or replacing a reference. It found:

- **0 differing leaves between Ubuntu 22.04 and 24.04** new V2 bundles.
- **112,049 differing JSON leaves between the reviewed PR #31 V2 and either new host**, including 26 of 37 output channels (83,077 scalar samples), four flow-integral histories (13,445 values), five output allowances and derived scales/quadrature data. Some differences are derived from earlier floating-point trajectory differences.
- The largest observed temperature change was approximately `7.67e-12 K` and the largest body-energy change approximately `9.82e-10 J`. All four static rod conductances are **unchanged** across PR #31 and the new hosts, including corrected `hotLead.G=0.45 W/K` and `coldLead.G=0.39999999999999997 W/K`.
- A separate saved-scalar comparison to the **more conservative of the two unchanged-policy native allowances** gives maximum old-vs-new drift `2.41e-7` of a native allowance, versus the reference-error ceiling `0.01`. The largest flow-integral difference is `5.03e-9 J` and remains under `8.9e-5` of its existing strict 100× integral budget. These comparisons are differences **between two checking references**, not a substitute for each reference's separately run high-precision physical verification. Both respective V2 evaluations passed their original independent 100× sampled checks.

The standalone current diagnostic `diagnose_v2_reviewed_seal_drift.py` additionally reports **all 37×4001 old-vs-new scalar differences** and all four 4001-sample integral differences normalized to the conservative unchanged strict budget; a failure in that numerical-equivalence check must record REFUSAL. It preserves the original complete field-level comparison on a failed bitwise identity check.

## What is and is not established

- **Established:** one previously reviewed V2 bundle and a second host-pair V2 bundle family are each internally sealed and mathematically checked; two new hosted environments have exactly equal outputs with complete captured wheel/BLAS/CPU provenance. Original source code and first author files remain unchanged; no native calls occurred.
- **Not established:** unconditional byte-for-byte reproduction of the *historically reviewed* V2 reference; the prior failed F0 seal assertion has no retained alternate digest; a causal attribution to BLAS/CPU; a new certified V2 reference; acceptance of a different seal for an existing plan; general platform portability or full native C1 qualification.
- **Mandatory stop:** both cross-host host jobs and the original aggregate job correctly returned **FAIL/REFUSED** because their new seals did not match the approved PR #31 candidate. The diagnostic job succeeded **only in capturing the negative evidence**, not reference certification.
- **Future independent decision:** either (A) decide through a focused independent R2/owner gate whether one exactly archived, hash-pinned, independently high-precision-verified V2 bundle may remain the sole *canonical* pre-native checking reference despite separately recorded float64 preparation variability, with no claim of bitwise generator portability; or (B) develop a **separate** deterministic numerical reference generator/lineage with its own hashes/seal, independent checks and R2. **Neither path is approved or implemented here.** Strict 100× reference error limits and the old original F-01 failed result are never waived.

**F-02 native one-shot source/host/plan gate:** still separately blocked, no OpenModelica query, build, model launch, MAT file or `nativeQualified` evidence. Do not merge historical PRs into production main.
