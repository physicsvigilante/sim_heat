# H1-C1-F0 — Option A owner/trust-root and reference-consumption proposal

**Status: PROPOSAL ONLY; NO OWNER APPROVAL, CERTIFICATION, NATIVE EXECUTION OR SOURCE MERGE.**

This document is a bounded design for the **next explicit governance decision** following SIM_HEAT [PR #33 targeted independent Chat B review-02](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-33/reviews/review-02-chat-b.md) (**scoped PASS for storage integrity only**). It does **not** modify original physical files, amend the original frozen H1 reference accuracy criterion, reclassify failed historical evidence, authorize native `omc`, or create a trusted reference tag.

## Scope and exact objects proposed for owner designation

| Identity | Exact reviewed value |
|---|---|
| **Frozen original H1-C1-F0 source** | `dd8c9432abe97563414bb3ed809e61e673473812` |
| **Archived-storage candidate, PR #33 reviewed source** | `bf51e7721bca73720aa9b5f5f2de90defee821ec` |
| Reviewed source Git **tree** | `a4c1e1cdd247cb07990db672ad4c092e93933d83` |
| Exact original archived PR #31 reference **raw JSON SHA-256** | `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368` |
| Raw JSON length | **4,409,800 bytes** |
| Original checked V2 **canonical reference seal** | `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9` |
| Proposed exact Git **XZ storage bytes** | **503,552 bytes**, SHA-256 `fc5a7df5928c3fb8aef2ba4af516dfbd32b42c0450ebef1051ad4fd7efebd17f` |
| Whole exact manifest **SHA-256** | `50467b138ed64cdb908f2c763bc777e6babf0bb04a0711568acc559112e66f84` |
| Independent V2 numerical review | PR #31, exact source `d857c8e807612026ecdf624277b4ace3977fefe3`, 37 × 4,001 values plus four 4,001-point integral histories |
| First Modelica model SHA | `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435` |
| Evaluator-only modal-study SHA | `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b` |
| Separately entered physical-spec fingerprint | `3afcfddb28ddbf9f9266548504bb43fc2f5420e90d10cb4acbf87334c6e3ab4c` |

**Science:** The original frozen F0 checking bundle, with `hotLead.G=0.44999999999999996 W/K`, failed the strict **100×** reference-accuracy margin (only **80×**). Its seal `d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b` and failed status remain unchanged. The **separately reviewed PR #31 V2** checked reference uses exact-decimal 0.45 W/K and passed **all 148,037 scalar comparisons and 16,004 integral comparisons** against independent high-precision physical calculations and unchanged reference-error budgets. The later two-host re-preparation produced a different canonical seal `c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07` on both hosts: **bitwise regeneration of the reviewed reference FAILS** and is not claimed. Numerically acceptable alternatives are NOT silently substituted as the same identity.

## Proposed owner decision (not yet received)

**Option A — recommended, narrow:** authorize **one exact already-reviewed immutable checking-reference ARTIFACT** (the stored raw JSON and its compressed Git object above) as the *candidate canonical source for future scientific checking*, with explicit **no claim of portable bitwise regeneration**. The approval would be **for fixture identity and future consumer design only, not a native run or a production merge**. It should retain the original first attempt, older failed F0 reference, bitwise regeneration FAIL and prior CI failures as historically distinct evidence.

To implement the trust root **after** an explicit owner decision:

1. Record an owner-attributable GitHub decision referring to **exact** PR #33 reviewed commit/tree, raw SHA/seal, manifest SHA and compressed SHA/size. Record that it accepts the immutable-fixture consumption model and explicitly rejects a universal regeneration claim. An issue/PR discussion with immutable source commit pointers is appropriate. The reviewer report itself is NOT owner authorization.
2. Create a **durable, preferably protected and signed or otherwise independently verifiable tag/reference** pointing at the *reviewed source commit* with a retention policy and a separate backup/mirror of the source+raw archived object. **Do not assume an ordinary branch cannot be deleted or rewritten**; no such tag or backup is created by this proposal.
3. Pin an approved **read-only** reference consumer to the owner-designated source tag/commit and exact raw/manifest/XZ identities. Require approval attestation and reject any mismatch, missing retained Git object, forbidden source drift, expired/ambiguous authority or alternate reference seal. Do **not** call `h1.reference.prepare` as a fallback. The present `--inspect-only` auditor returns data for checking, never owner authorization.
4. Keep original frozen `h1/` and original Modelica library unchanged. A new *separate* approved reference-bound C1 native runner/plan would need to load the exact archived bundle instead of using frozen `tools/h1_native_batch.py::prepare`, which currently **regenerates** the reference from spec and would not reproduce the reviewed V2 seal. This is a future separately reviewed **R2 evidence/runtime-adapter** scope, NOT a silent F0 runner patch.
5. **Native F-02 stays separately gated** even after a fixture-policy decision: exact execution commit/workflow/plan SHA, host OMC 1.27.0/MSL 4.0.0/Python 3.13.5/NumPy 2.3.5/SciPy 1.17.0, durable across-run *single-launch* reservation/ledger (not only `GITHUB_RUN_ATTEMPT=1`), one permitted version query/build/launch, archived original results and failure/refusal records, and post-native independent review. Companions need separately authorized attempts. No launch is implied by this proposed Option A decision.

**Alternative B:** demand bitwise-portable *reference generation*, which would require a newly specified deterministic arithmetic/rounding/serialization pipeline, new source and sealed scientific identity and independent cross-host R2. This is more work and unnecessary if an immutable, independently verified **checking artifact**, rather than reproducible regeneration, meets the owner's teaching/simulation goals. Historical PR #32's negative data remains preserved under either option.

## Offline read-only binding test — no approval bypass

`option_a_binding_preflight.py` is deliberately only an **audit-only** program. It verifies all **23** SHA-pinned historical F0 inputs from the original **unlaunched** plan; original model/first study/modal study and separately authored spec hashes; the archived fixture's compressed/raw/manifest/canonical seal identities through the independently reviewed PR #33 reader; and the unchanged frozen H1 `_verify_bundle` check against the original authored model and assisted modal study. It proves the existing **checking contract** can *read and structurally bind* the saved mathematical reference without recalculation, and that all 37 internal exports, nine public requests and four integral histories remain present.

**It never materializes a native prepared reference, creates a native plan, invokes the old runner, performs numerical simulation, supplies an owner-approval signal or grants native use.** The audit output reports `ownerApprovedOptionA=false`, `nativeQualified=false`, `nativeExecuted=false`, `authorizedForNative=false`, and `nativePlanCreated=false`. No `execute`, `approve` or `materialize` action is accepted. Tampered source/reference evidence must refuse. Its standalone success is a *dry-run source-to-checked-fixture binding*, not a permission token.

**Next:** Exact-head offline CI and R2 review of the bounded binding/audit scope, then owner chooses whether to approve Option A and the exact trust/retention contract. Until explicit approval, no canonical reference consumer and no native F-02 trial can be activated. All historical PR #28–33 branches remain draft/unmerged into production main.
