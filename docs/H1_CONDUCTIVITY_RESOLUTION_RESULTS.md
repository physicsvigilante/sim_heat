# H1 conductivity / numerical-resolution — observed cloud results and post-run audit

**Record date:** 2026-11-15. **Status:** seven successful bounded native diagnostics; **not** full H1 acceptance or unfamiliar-composition qualification.

## Exact evidence

- Executed commit: `52b1635932a3e4519b91f3bf093c0c21b0248d91`; branch `experiment/h1-cloud-resolution-once`; draft PR #8.
- Successful GitHub Actions run: https://github.com/physicsvigilante/sim_heat/actions/runs/43693191224
- Original artifact: https://github.com/physicsvigilante/sim_heat/actions/runs/43693191224/artifacts/14153251022, ZIP SHA-256 `dc32a0a36a27f031ce7a13da83ebdd26a3dd6ac1d14612fa597b36cb439f4843`, 3,820,474 bytes.
- Prior D1/D2 primary baselines: run https://github.com/physicsvigilante/sim_heat/actions/runs/43691263273; artifact ZIP SHA-256 `8fc38b9e2f040b48ab5cbeab34e8698b7c99c4d462a1e31e8bc33b0395185379`.
- **592 file SHA-256 values** in the four native batch attempt manifests were independently recomputed against the saved ZIP; **zero mismatches**. Seven verifier reports were inspected; all report `checks_passed` and `nativeQualified=false`.

The cloud job passed. Offline preflight ran **149/149 passing tests** in each of four sub-batches. Its actual budget was **7 builds, 7 model launches, 4 explicit compiler version queries, 0 retries**. Toolchain: OpenModelica 1.27.0, Modelica Standard Library 4.0.0, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0 on an ephemeral GitHub-hosted Ubuntu 24.04 runner. All seven cases retained their predefined numerical and conservation thresholds.

| Run | Samples | Outputs | Existing native-candidate checks | Worst error / allowance |
|---|---:|---:|---:|---:|
| D2-K2 primary, conductivity 200 W/(m K) | 1001 | 14/14 | 34/34 pass | 0.650477 |
| D1, tolerance 1e-10 | 1001 | 12/12 | 28/28 pass | 0.381549 |
| D1, 2000 output intervals | 2001 | 12/12 | 28/28 pass | 0.272454 |
| D2, tolerance 1e-10 | 1001 | 14/14 | 34/34 pass | 0.382155 |
| D2, 2000 output intervals | 2001 | 14/14 | 34/34 pass | 0.443200 |
| D2-K2, tolerance 1e-10 | 1001 | 14/14 | 34/34 pass | 0.715677 |
| D2-K2, 2000 output intervals | 2001 | 14/14 | 34/34 pass | 0.441130 |

Ratios below 1 meet the existing diagnostic criterion. A tighter tolerance or denser output grid does not guarantee monotonic improvement in numerical errors.

## Separate, post-run comparison to the original primary histories

A read-only audit opened the two saved ZIP artifacts, parsed their **recorded** normalized output CSVs and presealed reference bundles, and compared each companion with its appropriate original primary history. The duplicated terminal CSV rows were removed only after byte-parsed field equality was established. All compared outputs, physical reference bindings, and per-output allowances matched the parent cases. Tighter-companion comparison used the original 1001 samples; denser companions used `dense[::2]` at **exact** common sample times, without interpolation. For every exported quantity, the absolute difference was divided by that quantity's unchanged **primary** reference-comparison allowance (not fitted to the observed discrepancy).

| Original primary ↔ companion | Maximum common-time difference / primary allowance |
|---|---:|
| D1 ↔ tighter tolerance | 0.253941 |
| D1 ↔ denser output | 0 |
| D2 ↔ tighter tolerance | 0.444576 |
| D2 ↔ denser output | 0 |
| D2-K2 ↔ tighter tolerance | 0.442886 |
| D2-K2 ↔ denser output | 0 |

All comparisons pass the bound 1. A zero means **identical at saved common-time precision**, not that the solver took more internal steps or proves accuracy at unsampled times. **The cloud workflow itself did not generate these six cross-run comparison verdicts; they were calculated afterward from its retained outputs.** No native job was repeated to perform this audit.

## Conductivity teaching result

The existing D2 and D2-K2 physical models differ only in the allowed conductivity revision. D2 conductance is 0.2 W/K and initial oriented flow +12 W; D2-K2 conductance is 0.4 W/K and initial flow +24 W. The expected relaxation time halves, **1875 → 937.5 seconds**, without changing the conservation-determined asymptotic equilibrium of **308.15 K**.

The saved native temperature difference at 1875 s is **22.0727506157 K for D2** versus **8.1201150150 K for D2-K2**, showing faster exchange. At 9375 s, D2's two body temperatures are **308.4532158334 K and 308.0489280555 K**; D2-K2's are **308.1520444590 K and 308.1493185137 K**. These are finite-time values, not exact arrival at equilibrium. The saved D2-K2 difference at time `t` matches D2 at `2t` at all 501 available comparison points to recorded precision.

## Remaining gates and preservation

These results support **component reuse and limited investigation reuse**, not a blind unfamiliar-assembly transfer success. The common Modelica package, authored physical models, MATv4 adapter and generic checker have not been specialized for this conductivity experiment. Native observations retain **`diagnostic_only`** status and **`nativeQualified=false`**. Independent checker/reference accuracy approval, final freeze, charter's broader Track A/Track B, reserved C1 and classroom-effectiveness evidence remain open.

This report is an evidence-only documentation addition. The old prepared 26-file patch was **not** reapplied, because an alternative campaign implementation had already been published and completed successfully. No additional builds, launches, merges, tolerance changes or automatic retries were needed.
