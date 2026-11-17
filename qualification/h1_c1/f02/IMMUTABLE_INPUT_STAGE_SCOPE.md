# SIM_HEAT H1-C1 F-02 — quarantined input staging (OFFLINE ONLY)

**Status: NOT NATIVE, NO EXECUTABLE PLAN, NO COMPILER QUERY, NO LAUNCH APPROVAL.** This is a separately reviewed future-runtime input-preparation *candidate*, based on independent [PR #36 scoped PASS](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-36/reviews/review-01-chat-b.md) for a **disabled design preview**. It does not change frozen H1 physical code, first-author evidence, scientific reference, or numeric thresholds.

## Actual staged content and its limits

The new `stage_immutable_inputs.py` creates a **fresh, never-overwritten** subfolder under `c1_f02_stage_evidence/<label>/` containing exactly:

| File | Exact source/input |
|---|---|
| `model.mo` | Original first-author Modelica source, SHA-256 `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435` |
| `study.json` | Separate evaluator modal study, SHA-256 `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b` |
| `SimHeat.mo` | Original frozen thermal library, SHA-256 `e57955b6c32cb34321a6b1908306c4ea9a63ae259b95a5fd48c7e8d3b4da10ea` |
| `reference.bundle.json` | **Exact 4,409,800 original archived PR #31 scientific JSON bytes**, SHA-256 `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368` and seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9` |
| `STAGED_INPUTS_MANIFEST.json` and `STAGE_STATE.json` | New offline-only SHA inventory, forbidden native flag assertions and completion state |

No `build.mos`, commands, executable, native-runner script, `model_res.mat`, native plan accepted by `sim_heat.native_batch/1`, or owner launch token is staged. A completed staging receipt is **`OFFLINE_STAGED_EXACT_INPUTS_NOT_NATIVE`**, and all `nativeAllowed`, `nativeExecuted`, `nativePlanCreated`, `oneShotReservationAllocated` and `ownerNativeLaunchApproved` remain false. Missing, tampered, additional or symlinked output members refuse; no duplicate staging is allowed. An interrupted copy remains labeled **INCOMPLETE_NONNATIVE** and cannot be promoted to complete by a legitimate verifier.

Before copying, the adapter runs the previously reviewed disabled F-02 plan audit and owner-approved **offline scientific-data-only** consumer, verifying original 23 F0 source-plan SHA pins and original first-author/model/modal-study/reference identities. The 503,552-byte reviewed XZ reference is checked against an independent fixed SHA and decompressed with the reviewed XZ decoder memory bound, then must match **exact original JSON raw byte SHA**. It does **not** recompute temperatures/flows or call `h1.reference.prepare` (which is known to produce a different reference seal on other hosts). It preserves original `nativeQualified=false` scientific reference provenance.

The new CLI only accepts `stage-offline-only --label ...` and `verify-offline-only --label ...`. It does not execute a simulation, issue a compiler query, build a model, run a one-shot reservation, create an approved native plan, or change the original frozen code. Output labels cannot traverse paths and the stage directory must be newly created. The output is transient CI/artifact evidence, **not itself a durable protected release or trusted native-input authorization**.

## PR #36 minor F-06 hardening

The independent PR #36 reviewer found the standalone semantic validator used `== 1` for a proposed future one-shot count, so in Python `True == 1` and `1.0 == 1`. The new branch explicitly requires **`type(count) is int`** and validates the exact scalar types for modal grid values (start integer, stop float, interval integer, tolerance float, solver string). Negative tests assert refusal for boolean and floating-point substitutions. The original pinned disabled plan stays **byte-identical**; only the previously added predicate/tests change, under a new exact head and new R2.

## Necessary later gates, none implemented here

The **owner-approved Option A scope is offline scientific checking only**. The reference anchor is an ordinary, unprotected Git branch; a checkout's cached `origin` ref does not prove upstream freshness. Before an actual F-02 native attempt, separately establish an independently trusted/protected and retained owner-designated reference release and backup, a source-attested non-regenerating native **runner** and exact native plan, a durable across-run one-shot reservation with no retries, actual OMC 1.27.0/MSL 4.0.0/Python/toolchain and host identity, and a **new explicit owner authorization for one named native version/build/launch budget**. Independent pre-native R2 and post-native MAT/numerical review are both required. None can be inferred from a green offline staging CI or this proposed source.

The original F0 checking reference's **80× vs mandatory 100×** static failure and the PR #32 **bitwise regeneration FAIL** remain unchanged. Original first-authored model/study/notes, native attempts, rejection history and all nine **not_computed** observations remain preserved. Historical PRs remain draft/unmerged; do not merge them to main.

## Review scope

Review the exact new source SHA and CI, the strictly bounded byte-for-byte staging, manifest/state refusal behavior, type-hardening F-06, original source/reference pins, no simulation or native plan creation, and the difference between staged *data* versus runtime *authorization*. Any material evidence semantics changes require a new R2, not a retroactive pass.
