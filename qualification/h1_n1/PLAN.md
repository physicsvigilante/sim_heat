# H1-N1: one unfamiliar thermal composition — pre-native design only

**Status: PLAN ONLY; NOT EXECUTION READY. No native execution is authorized by this document or its CI.** The owner approved preparing the next milestone after PR59's independent H1-T1-UNSEALED review. This is not approval to install/query/build/launch OpenModelica, run a model, merge this PR, regenerate frozen references or deploy anything.

## 1. Question and fixed source

Can the already accepted, independently authored **T1-T two-feed three-block lattice** produce traceable numerical diagnostics through the existing generic Modelica library and read-only result checks, without arrangement-specific production code or editing the author's physical model?

Use original SIM_HEAT baseline `f52613c39c539b2d4543a9838e5658d526fca10e`, tree `0c44961b473d23737b0c9f3b3f2cd3db65b9f264`. Retrieve the original derived T files from evidence-only PR59 commit `7234a53a5022441a912eb09240138e9c6c5945d8`, path `experiments/h1_t1_unsealed/T/`. Model SHA-256 is `2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae`; original study SHA-256 is `12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a`. They were extracted from original author comment 6982616288 with exactly one terminal LF. Do not call them independently uploaded files.

The T1 source-fidelity verdict was **UNSEALED retrospective public-task evaluation**: the selector's private key was lost. Preserve that permanent limitation. N1 is a new numerical-validation question, not repair of T1 or frozen H1-C1-F0. PR59 stays evidence-only and unmerged.

The source has 3 bodies, 2 fixed-temperature boundaries, 10 rods and 2 ownerless junctions, with eight requested observations. `reference-facts.json` independently expresses facts from the locked public task, not a graph exported by the H1 parser. It is same-author transcription pending independent review, not an independent accuracy certificate or recovered secret key. The checker must refuse mismatched values, units, owner nodes, rod orientation and source hashes.

## 2. One physical model; bounded numerical variants

| Variant | Physical model | Time interval | Output intervals | Solver tolerance |
|---|---|---|---:|---:|
| Primary | Original exact bytes | 0–2400 s | 2400 | 1e-8 |
| Tight | Identical model bytes | 0–2400 s | 2400 | 1e-10 |
| Dense | Identical model bytes | 0–2400 s | 4800 | 1e-8 |

All use the authored `dassl` choice. Primary study is byte-identical. Companion study IDs and hashes must be new, with only ID and allowed analysis fields changed; preserve original provenance, mode and requested quantities. Companions are evaluator-created numerical successors, **not additional author first attempts**. Do not extend the horizon to obtain settling or substitute easier source values.

Proposed future maximum budget is **3 buildModel calls, 3 model launches, 2 standalone compiler-version invocations, 0 automatic retries and 0 installation commands**. Two batches (primary+tight, then dense) fit the existing two-case runner limit. Budgets are maxima, not guarantees: stop on the first failed identity, build, export or numerical gate and do not execute remaining variants. Timeouts: build 600 s, launch 120 s, version invocation 30 s; terminate the process group, retain logs and no hidden retry. The MSL identity checks inside an authorized build are included in that build, not extra compiler-process invocations. A separate environment-installation task would require separate authority.

This is one physical experiment with numerical controls, not proof of all thermal graphs. A single successful primary run without companions is at most a diagnostic, not completed convergence validation.

## 3. Discovered blockers — green plan CI must not hide them

**B1: reference accuracy is not certified.** Existing `h1/reference.py` compares float64 matrix-exponential and symmetric spectral calculations. Its own error claim explicitly says sampled cross-check, not a certified bound. Agreement is useful screening, not independent error evidence at least 100 times tighter than native acceptance. The frozen C1 reference failure must not recur under a new name.

**B2: existing companion comparator refuses this grid pair.** New same-author N1 screening finds four *different* sampled allowances on the 2400- and 4800-interval grids: `T02.Q_flow`, `T02.port_a.Q_flow`, `T02.port_b.Q_flow`, `T_Warm.Q_to_network`. `tools/h1_compare_companions.py` requires exact allowance equality, so it refuses the pair even when fed its own analytical checking columns. This is an expected recorded refusal in plan CI, **not a native result, production regression or permission to change the tolerance**. It may reflect a finer grid sampling an interior extremum; a tiny difference is still a real contract difference.

Required resolution before native authorization: implement and independently review a **comparison-only N1 adapter** which applies the already frozen primary per-output allowance at exact common timestamps, without demanding equal separately sealed companion allowances. Individual primary/tight/dense checks retain their own unchanged sealed allowances. Never mutate a companion bundle, union/max/sum allowances, relax tolerances, interpolate or fit thresholds to native outputs. This adapter is **not implemented by this plan**.

**B3: the historical resolution-campaign orchestrator is not reusable unchanged.** It assumes three 1000-interval base cases, 2000-interval dense variants and a seven-run budget. T1-T originally uses 2400 intervals. Do not change the original study to fit that controller or accidentally execute its historical campaign. The low-level batch runner may be reused behind a separately reviewed bounded controller.

**B4: runtime and approval enforcement are not bound.** Historical OpenModelica 1.27.0 / MSL 4.0.0 / Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0 / ubuntu-24.04 is a **target**, not a claim those native binaries exist here or on the next worker. No OMC probe has been made. Actual immutable image digest, compiler binary hash, full MSL manifest and OS/compiler/linker identity must be pinned before execution. A runner label alone is insufficient. The old runner requires `push`; a future manual-dispatch workflow must not spoof environment fields to satisfy it. Any required controller change is R2 and must be reviewed as actual code, not covered automatically by approval of this design.

These blockers are expected plan outcomes. `planChecksPassed=true` and `executionReady=false` must coexist until every execution gate is genuinely closed.

## 4. Independent checking reference — proposed construction and proof obligations

Before looking at ANY native outputs, a separate-context reviewer must confirm the reference's source facts and complete port incidence directly from public selector comment 6981681502. No solution is imported from the author, production graph or existing native traces. Three distinct concepts must stay separate: independent source expression; independent numerical method; a rigorously justified numerical error bound. A second ChatGPT context is not independent human expertise or independent model weights.

Proposed oracle implementation, **not yet built or certified**:

1. Assemble a passive conductance Laplacian directly from the separately entered fact table, with `G=k*A/L`, circular `A=pi*d*d/4`, positive capacities `m*c`, signed rod endpoints and fixed boundary temperatures. Explicitly eliminate the two ownerless algebraic junctions with checked nonzero denominators. Do not import H1 parser/reference internals into this oracle.
2. For three body temperature offsets obtain `C*dtheta/dt=-K*theta+f`, with constant boundaries. Normalize temperatures and time before matrix norm/error calculations. An affine augmented matrix state also carries the temperature integrals needed for flow/energy checks. State dimensional scaling and sign conventions explicitly; dimensionful row sums are not an acceptable norm proof.
3. Use directed/outward rounded interval arithmetic (or an independently justified exact-rational enclosure implementation), positive-capacity and junction-inverse enclosures, and a certified enclosure of pi. A rational alternating-series/Machin bound is an acceptable proposed pi route. Input conversion from published decimal values to the actual captured binary64 values and parameter arithmetic must have an explicit error allowance; do not silently switch which physical constants are being checked.
4. Enclose the augmented matrix exponential using a finite Taylor/polynomial approximation with a norm-based rigorous remainder, e.g. for `q=||h*M||` and `q/(m+2)<1`, tail no larger than `q^(m+1)/(m+1)! / (1-q/(m+2))`. Propagate approximation, input and roundoff intervals across the complete grid, including accumulated-integral errors and cancellation. Doubling precision and comparing two approximate answers is **not** itself an enclosure proof. Pin precision, subdivision, polynomial order and resource caps before approval; if width or runtime cannot meet the required bound, refuse rather than auto-tuning after native output.
5. Enclose all **77 mandatory exported quantities**, all eight public observations (including the difference directly), and analytic flow integrals used for local/network energy checks at all required timestamps. Parameter exports (`C`, `G`, circular area) are included. For each stored reference value r and independent enclosure [l,u], require `max(abs(r-l),abs(u-r)) <= epsilon/100`. Epsilon is that quantity's already frozen local acceptance allowance; public temperature differences and initial temperatures use their actual stricter thresholds. Include serialization/binary64 conversion error in this bound. No sparse selected-point certificate may stand in for all sampled quantities; no continuous-time accuracy claim beyond what is proved.
6. Freeze reference data, allowance tables, temporal policy and certificate **before first native build**. Repeat reference construction on the exact runtime image and require byte-identical saved bundles and certificates. If a different host regenerates different seals, retain the mismatch and stop; do not replace prior saved evidence or reuse the failed C1 seal. Only new N1 artifacts may be created, in a fresh namespace.

Current `reference-facts.json` and temporary `reference.prepare()` screening are **analytical checking data**, not an independent oracle, accepted reference bundle, or source of native measurements. This PR saves diagnostics, not a full reference bundle. Reference implementation, certified bound, runtime reproduction and independent review are open gates.

## 5. Runtime authority and execution checklist

A future execution request must pin the actual source HEAD/tree, input SHA-256s, reference/certificate hashes, compiler/image/MSL/OS identities, run order, maximum invocation counts, timeouts, artifact retention and a unique one-shot approval identity. The owner must approve THAT exact manifest after independent R2 review of the executable preparation/controller. Current approval covers preparing this plan only.

Before any native operation: recheck source and all task/input hashes; admit the unchanged primary and explicit numerical successors; verify 77 exports and request types; check reference certificates and same-host byte reproduction; complete negative tests and record the entire planned comparison policy. No compiler version command may run merely to discover a convenient toolchain before authorization. No native workflow is installed or triggered in this PR.

The future controller must enforce total limits across batches, persist consumed approval before the first attempt, reject rerun/new-job replay of the same approval, and reject changed events/hosts/branches. Use minimal token permissions, no source-controlled arbitrary shell, no repository credentials in compiler/model environments, no filesystem path escape, and no network/export side channel. Preparation and execution output directories must be new and immutable after capture. An unsafe/incomplete approval controller is a blocker; the old runner's version counters and `GITHUB_RUN_ATTEMPT` check alone do not prove cross-workflow one-shot authority.

## 6. Numerical/export acceptance after a future authorized run

Preserve original raw stdout/stderr, return code, build/init XML, raw MAT-v4, variable metadata and signed-alias mapping. Hash every stage. Check actual model, initialization, solver, interval, tolerance and MSL identities. Require native-recorded **77 quantities plus time**, 2401/2401/4801 planned samples, complete endpoints, finite values and matching time policy. Do not fill a missing export from reference data or reconstruct a missing native rod flow from temperature formulas. Existing MAT size/precision/shape limits are not widened automatically.

Run unchanged per-output/local allowances and conservation checks: equal connected-node temperatures; rod law and signed port balance; each body's initial temperature, capacity and owned energy; body flow integral; net boundary supply versus total stored-energy change. Preserve source signs, exact timestamp association and the no-interpolation rule. Check all grid samples, not merely requested observations. Check primary versus tight and dense on exact common timestamps with the previously sealed PRIMARY allowance, no sum/max/fit. Report all failures and only declare the bounded numerical-control checks passed when every required check actually passes.

Success still does **not** make `nativeQualified=true`. Existing verifier returns `diagnostic_only`, `nativeQualified=false` and does not attest execution. An independent execution receipt may truthfully record a native launch without editing that verifier's fields or rewriting source-only T1 evidence. Keep raw-native provenance, diagnostic numerical verification, reference independence and overall scientific qualification separate. Missing results remain `not_computed`; never backfill them from an oracle.

## 7. Preservation, evidence and review economy

Historical six archived diagnostics, original H1-T1 source-only previews, missing private-key disclosure, first failed browser test, and C1 precision/seal failures are immutable. PR59 stays evidence-only and unmerged. Neither this plan nor a future N1 success can repair or relabel that history. No radiation implementation or unsupported T1-X execution is included.

Current deliverables are a plan, machine-readable **non-executable** manifest, independently expressed but same-author source facts, offline design checks and OFFLINE-only CI. These are one coherent design-review unit. Request **one focused R2 plan review**, not a review of each file. A plan pass approves only the proposed scope; the future executable oracle/controller and actual runtime evidence need their own pinned execution-readiness review when they exist. Batch those genuine new R2 implementation changes into one review; do not use this distinction to add repetitive reviews for editorial corrections.

Stopping point: **no native execution until the open gates are closed and separately owner-authorized**. This plan deliberately exposes existing comparator/runtime/reference gaps rather than spending runs on a candidate already known not to satisfy the evidence contract.
