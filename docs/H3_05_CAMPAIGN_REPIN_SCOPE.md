# H3-05 — deterministic SHA-repinned campaign-admission refusal coverage

**Issue:** [#20](https://github.com/physicsvigilante/sim_heat/issues/20), from Chat B's nonblocking recommendations in [SIM_HEAT PR #19 Review 01](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-19/reviews/review-01-chat-b.md).

**Scope:** **R1 test-only assurance**. Add a test generator and a source-branch offline/browser CI workflow. **No production code changes.** No new Modelica build, no native model launch, no runner/checker/decoder/graph/renderer edits, no new source case or trusted native-output data. H1-C1 freeze and old failed evidence stay untouched. This does **not** broaden the previously reviewed generic campaign adapter's external-trust contract.

## What the new test actually proves

`viewer/network/tests/test_campaign_repin.py` constructs a **SYNTHETIC TEST-ONLY** one-batch ZIP satisfying the general shape of a successful historical native resolution campaign. Its generated 1001-timestamp CSV comes from the existing **H1 checking reference only as a test fixture**. Its `model_res.mat` contains literal dummy bytes (not a readable MAT result). The test-only fake run/commit/artifact IDs are deliberately not production GitHub identities. No production case bundle is emitted by the tests.

It first admits this internally consistent **synthetic** positive control into the unchanged `compile_campaign_case` function, verifying that the rejection tests reach meaningful gates. Every deliberately corrupted copy reserializes and *refreshes the batch manifest SHA-256 map and the entire ZIP SHA-256* before calling the **actual production adapter**. This is substantially stronger than merely presenting stale hashes.

Adversarial subtests cover:

- Every saved numerical check `passed=false`, a fabricated public result and forged ratio.
- Altered executed model and study bytes while updating native ZIP hashes.
- Altered reference numeric payload, reference seal, receipt seal, verification seal, attempt seal and reference file digest.
- Removed, added or inconsistent native SHA manifest entries, missing MAT/reference members, duplicated entries and unsafe traversal/absolute member names (even unrelated outer entries).
- Plan SHA, campaign batch-plan SHA, source branch, native attempt run/commit, false `nativeQualified` and incorrect independently supplied expected run/commit/branch values.
- An **explicit trust-boundary demonstration**: a fully self-repinned synthetic ZIP and correspondingly fabricated *matching* caller pins may be internally admitted. This is intentionally **not** proof of external GitHub execution and remains labeled diagnostic-only. The original artifact requires independent GitHub run/artifact/commit/whole-ZIP verification.

The test code stores no original fake "native measurement" files and never substitutes these synthetic values for real archived output.

## Separately performed authentic-archive challenge

An optional integration test `test_optional_original_native_archive_and_fully_rehashed_test_only_mutants` is **skipped** when the original historical artifact is not available. It can be run with:

```sh
SIMHEAT_ORIGINAL_CAMPAIGN_ZIP=/path/to/original_h1_conductivity_resolution_artifact.zip \
  python -B -m unittest viewer.network.tests.test_campaign_repin -v
```

Before reading, it checks full original ZIP SHA-256 exactly **`dc32a0a36a27f031ce7a13da83ebdd26a3dd6ac1d14612fa597b36cb439f4843`**, corresponding to [native run 43693191224 / artifact 14153251022](https://github.com/physicsvigilante/sim_heat/actions/runs/43693191224). It first invokes the unchanged production adapter against the authentic archive with verified D2-K2 run/commit/branch and requires ordinary diagnostic-only admission. It then independently repacks **seven separate TEST-ONLY mutant copies** of the *real original ZIP's file bytes*, refreshing the selected batch manifest and the outer ZIP SHA for each; it demands `campaign_evidence` refusals for contradictory numerical-check flags, forged public values, changed model, changed reference seal, missing manifest entry, modified batch plan, and an added unlisted native file. The original ZIP is opened read-only and rehashed unchanged afterward.

**Actually executed locally by Chat A on 2026-11-16:** five test methods passed, including the optional original-GitHub-archive test and all seven repacked genuine-archive-derived challenge cases. This test is **not** a new native experiment, independent in human/model context, or an externally authenticated fork. Its source bytes came from the original previously independently verified downloaded ZIP. The separately reviewed PR #19's valid archived output remains unchanged.

CI **does not depend on the original artifact's expiry**: with the env variable absent, it runs the permanently reproducible synthetic generator and marks only the optional original-archive test **skipped**. A separate authorized reviewer or contributor can rerun the original-artifact test later if the historical ZIP is available. Do **not** describe the skipped optional test as an automated CI pass.

## Release acceptance and limits

- Source branch only, test/CI/doc changes; no changed H1 library, original `h1/`, Modelica laws, checker, `viewer/network/tools/build_campaign_case.py`, viewer JS/HTML or six published native case bundles.
- Execute full existing H1/analytical/adapter/Node/Chromium desktop and mobile suites on **exact final source HEAD**, recording the one intentionally skipped optional archive integration and all actual passes; preserve historical CI failures.
- R1 test-only change can be merged under standing owner authorization after CI, without another full R2 review. Any future change to the production archive admission semantics, runtime evidence trust, or dynamically added native comparison pairs is **R2** and still needs Chat B review.
- Run IDs, locally fabricated original ZIP mutations, real original native output and checking-only reference-generated synthetic CSV must remain clearly distinguished. Real native scientific qualification remains **`nativeQualified=false`**, public observations `diagnostic_only`, and external run/commit/ZIP attestation remains outside the adapter.
