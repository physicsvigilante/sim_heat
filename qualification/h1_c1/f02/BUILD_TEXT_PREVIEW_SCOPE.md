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

## PR #38 independent review-01 F-01 — exact-manifest readback correction

[Independent Chat B review-01](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-38/reviews/review-01-chat-b.md) returned **CHANGES REQUESTED** at original source `a570e3c589457d21b6673701a2d126d7046e1c3c`, despite confirming original physical/reference byte identities, safe text-only formatting, 229 original offline tests, and zero native operations. It reproduced one **major** evidence-only defect: `doc == contract(label,raw)` allows `0 == False` or `4000.0 == 4000` in Python, so a changed manifest with forged numeric permissions or interval type could be incorrectly accepted at readback.

The corrected `verify()` preserves the strict duplicate-key/NaN-refusing JSON parser, then requires the **actual complete raw manifest bytes** to equal the exact original deterministic `encoded(contract(label,raw))` serialization. This refuses any changed JSON types (including numeric zero/float-zero in every permission/history field or 4000.0 intervals), field arrangement, whitespace, added fields or provenance changes even where Python parsed values compare equal. The saved build-text itself is still compared to fresh **source-derived TEXT** only; the original numerical reference is never regenerated. New on-disk negative tests independently mutate every false flag to `0` and `0.0`, change `targetIntervals` to `4000.0`, and alter whitespace while retaining semantically equivalent JSON. The expected outcome is **REFUSED**, never a native permission or qualifying evidence receipt.

The original review-01 and its exact-head successful CI remain historical records at their original source. This new correction requires a separately pinned exact-head CI and **targeted independent Chat B review-02**, not rewriting or assuming the earlier verdict. **The Modelica script remains merely nonexecuted text**. Original frozen F0 80× numerical accuracy FAIL, PR32 cross-host bitwise regenerated V2 FAIL, and all no-native/owner-launch/trust-root restrictions remain unchanged.

## Deliberate future gates

A **real** native adapter must separately have (1) an independently owner-authenticated, protected/retained release trust root and backup; (2) exact reviewed source/ref, stage/model/study/reference and executable native plan hashes; (3) actual toolchain OMC/MSL/compiler/host identity attestation, including the effective Modelica experiment and 37 exports; (4) an atomic, durable cross-run single-attempt reservation with no retries and failure/partial evidence preservation; (5) fresh independent pre-native R2; and (6) **new explicit owner authorization for the specific version-query/build/launch budget**. Independent post-native MAT/numerical review follows any permitted attempt. Neither this preview nor offline CI grants any of those controls.

**Only this offline text-preview source/manifest/negative-regression design is a candidate for R2 review.** Historical source branches/PRs remain draft/unmerged.
