# SIM_HEAT H1-C1-F0 — Option A checking-reference adoption (no native)

**Policy state: OWNER APPROVED FOR OFFLINE CHECKING ONLY.**
**Technical consumer state: HISTORICAL DRAFT / AWAITING INDEPENDENT R2.**
**Native C1 status: NO VERSION QUERY, BUILD, LAUNCH OR NATIVE QUALIFICATION AUTHORIZED.**

The project owner replied **“approved”** in ChatGPT on 2026-11-17 (Asia/Kolkata), in response to Chat A's explicit request for **“Option A reference adoption only; no native execution.”** Chat A published the exact [owner-direction record](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-34/OWNER-DECISION-01.md), Git blob SHA-1 `599bfd42362c5d75224c82291b08b3f97310eb7c`. This records the conversation's owner direction; it is **not independently GitHub-signed identity attestation** or a permission to merge or execute native programs.

## What Option A adopts

One **existing, exact, already independently numerically checked** archived PR #31 V2 mathematical reference for the **H1_C1_MODAL** physical model and evaluator-assisted modal study. The original scientific reference raw bytes are **4,409,800 bytes**, SHA-256 `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368`, canonical reference seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9`. Its original stored XZ archive is **503,552 bytes**, SHA-256 `fc5a7df5928c3fb8aef2ba4af516dfbd32b42c0450ebef1051ad4fd7efebd17f`; original entire manifest SHA-256 `50467b138ed64cdb908f2c763bc777e6babf0bb04a0711568acc559112e66f84`. The PR #33 source with the reviewed archive/inspector is commit `bf51e7721bca73720aa9b5f5f2de90defee821ec`, tree `a4c1e1cdd247cb07990db672ad4c092e93933d83`.

Original frozen H1-F0 implementation `dd8c9432abe97563414bb3ed809e61e673473812`, original first model SHA `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`, evaluator modal study SHA `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b`. The first author's original model, study and notes remain unchanged; the assisted grid is separately identified. This approval does **not** adopt a newly regenerated scientific reference.

**Historical negative evidence is mandatory:** the original frozen F0 reference still has an 80× accuracy margin for one exported static conductance versus 100× required, and remains **FAIL**. PR #32's cross-host regenerated V2 has a different seal `c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07`; that bitwise-regeneration trial remains **FAIL**, not silently substituted. The scientific justification for this *archived* PR #31 reference comes from its own independent high-precision 37×4001 plus four-integral 100× review.

## Explicit adoption record and trust limitations

The versioned machine-readable `qualification/h1_c1/option_a/OWNER_ADOPTION.json` is a **separate decision record**, **not** a rewritten original PR #33 fixture manifest (the original has `approvedForNative=false`). Its exact Git blob SHA-1 `0fc2e11e6e2bf618799ec5b314e2872f14236d8c` is pinned in the new consumer source. The consumer also independently verifies the central review-hub owner-decision Git blob ID and the old exact study/reference/archive identities. A reference-anchor branch `qualification/h1-c1-f0-option-a-reviewed-reference-anchor` was created pointing to the previously reviewed exact PR #33 commit `bf51e7721bca73720aa9b5f5f2de90defee821ec`; the consumer refuses if it moves or is missing.

**Important limitation:** this is currently an *ordinary unprotected GitHub branch*, not a signed, enforced permanent release tag. GitHub branch/ref deletion or rewrite is still possible; the code-level Git/cryptographic pins would refuse mismatches only under a known, reviewed consumer revision. A protected/signed ref and independently backed-up object/manifest remain future trust/retention work before a high-assurance native launch. This owner approval should not be misrepresented as cryptographic proof of the chat participant's GitHub identity.

## Approved offline consumer, deliberately separate from native control

`offline_reference_consumer.py` is limited to `check-reference-only` on the CLI and `load_for_offline_checking(purpose="offline_checking")` as Python data access. It validates:

- exact decision record Git object and explicitly false native permission fields; exact reviewed Git anchor SHA and tree;
- original 23 pinned F0 source inputs, first-authored model/study and evaluator modal study through the existing, reviewed read-only binding preflight;
- exact original PR #33 archived XZ object, whole manifest SHA, raw scientific JSON SHA, canonical V2 seal and frozen study/model/export registry;
- non-native reference labels and a second exact canonical-seal verification before returning the public scientific data.

It **does not call `reference.prepare`**, does not call frozen `tools/h1_native_batch.py`, never generates or modifies reference values, never creates a new plan, never prepares/executes a native job or claims a simulated result. It returns an **offline checking-data receipt**, with `nativeAllowed=false`, `nativeQualified=false`, `nativeExecuted=false`, `nativePlanApproved=false`, `productionMergeAllowed=false` and **`releaseTrustRootComplete=false`**. Possessing the bundle or a PASS receipt **is not native-execution authorization**. Any future native adapter must have an independent, reviewed trust and executable launch boundary.

The new adoption workflow triggers on **every push to its experimental branch** (no `paths` filter), so dependency-only changes also trigger current-source CI; any physical/source changes instead violate its exact additive diff/pin rules and refuse. This is not equivalent to enforcing a protected required GitHub status rule.

## Separate next gates

1. Independent **R2 review of the exact source consumer and user-direction record**, including forged-owner/anchor/ref/model/reference identity cases and current-head CI. Historical source PRs stay draft/unmerged.
2. Owner-controlled protected/durable Git ref or independently verified release signature and backup/mirror for the reviewed immutable reference, tied to exact reviewed commit/tree/raw/XZ/manifest. This tooling currently cannot configure GitHub branch protection or sign a release and does not claim those controls exist.
3. Design a **separately reviewed and explicitly approved native adapter/plan** which consumes this exact saved bundle and does **not** call the frozen generator. Complete dependency triggers, one-shot durable cross-run reservation, actual compiler/MSL/host/plan source pins, no retries and post-native independent evidence review are required.
4. **New explicit owner authorization for any OpenModelica native attempt**. Approval of this checking-reference artifact is not that authorization.

**No production merge and no native simulation follows from this decision.**
