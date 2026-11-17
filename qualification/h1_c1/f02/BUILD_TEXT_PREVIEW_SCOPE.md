# H1-C1 F-02 — non-regenerating Modelica build-text preview (offline)

**Status: PROPOSED / NON-EXECUTING. No new native-plan approval, compiler query/build/launch, Modelica execution, native qualification, or production merge.**

This milestone follows the independent [PR #37 review-02](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-37/reviews/review-02-chat-b.md), which scoped PASSED exact-byte offline staging/readback. The project owner's prior Option A approval permits **read-only offline scientific reference checking only**.

## What this work adds

The source-adapter `offline_build_script_preview.py` consumes the existing, separately checked six-file offline input stage (original Modelica model, evaluator modal study, frozen thermal library, exact independently verified PR31 V2 checking reference, stage state, stage manifest). It requires the stage's authentic original SHA-256s and disabled-plan/source checks before use. The only Modelica-specific operation is a **pure Python string generation** call to the preexisting unchanged frozen `tools.h1_native_batch.build_script(study, library, model)`. The entire frozen H1 runner, physics, checker, native plan and original author files remain unchanged.

It saves a **TXT preview** named `unexecuted-build-script.mos.txt` (not `build.mos`) plus an independent nonnative hash manifest under a **fresh one-use** `c1_f02_build_preview_evidence/<stage-label>/` directory. The script text contains the intended MSL 4.0.0 load/version checks, staged library/model paths, DASSL, 4,000 intervals, MAT and complete export-filter settings, **but no tool executes it**. The preview is **not** an approved native plan, does not prepare an executable model, and cannot be invoked as `sim_heat.native_batch/1`. A user or future runtime must not treat the text or PASS receipt as launch authorization.

The CLI allows only `preview-text-only` and `verify-preview-only`. No `omc`, `reference.prepare`, `h1_native_batch.prepare`, `h1_native_batch.execute`, `subprocess.Popen`, native-plan generation, executable/model run or one-shot reservation is used by this path. Text generation does **not** itself prove the compiled model will expose the required 37 columns; that still requires an independently reviewed, owner-approved native attempt.

A regenerated preview is **compared to the saved text** during readback, with exact source/model/study/library/reference inputs reverified; the new manifest's complete expected value is independently recomputed and all native/host/owner/one-shot claims remain false. Both staged input and preview directory must be non-symlinked, single-use locations. This is **temporary, offline local staging**; it is not protected concurrent storage or a durable cross-run one-shot lock.

## Frozen scientific identities and failed historical evidence

- Original author Modelica SHA-256 `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`; evaluator-assisted modal study `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b`; frozen library `e57955b6c32cb34321a6b1908306c4ea9a63ae259b95a5fd48c7e8d3b4da10ea`.
- **Exact approved PR31 V2** raw JSON SHA-256 `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368`, canonical seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9`; never regenerated or substituted.
- Original frozen F0 reference's hotLead.G physical error margin **80× vs ≥100× required — FAILED**; PR32 cross-host regeneration of the original archived PR31 seal **FAILED**. Neither is waived, repaired, rewritten or relabeled.
- Owner approved only Option A **offline reference checking**. The source anchor remains unprotected and locally cached; no authenticated live release root or backup is created here.
- The nine requested original physical observations remain **not_computed** because no actual OpenModelica simulation has taken place.

## Deliberate future gates

A **real** native adapter must separately have (1) an independently owner-authenticated, protected/retained release trust root and backup; (2) exact reviewed source/ref, stage/model/study/reference and executable native plan hashes; (3) actual toolchain OMC/MSL/compiler/host identity attestation, including the effective Modelica experiment and 37 exports; (4) an atomic, durable cross-run single-attempt reservation with no retries and failure/partial evidence preservation; (5) fresh independent pre-native R2; and (6) **new explicit owner authorization for the specific version-query/build/launch budget**. Independent post-native MAT/numerical review follows any permitted attempt. Neither this preview nor offline CI grants any of those controls.

**Only this offline text-preview source/manifest/negative-regression design is a candidate for R2 review.** Historical source branches/PRs remain draft/unmerged.
