# H3-07 — shared-run source SHA and same-page refusal hygiene

**Issue:** [#24](https://github.com/physicsvigilante/sim_heat/issues/24).  
**Review origin:** independently authored [Chat B PR #23 Review 01](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-23/reviews/review-01-chat-b.md), verdict **scoped R2 PASS**, with two **nonblocking minor** future-comparison safeguards, F-01 and F-02.  
**Base main:** `8aa18488f949c6d1b506d80e44afc2a25e71b2c7`, merged/reviewed H3-06.  
**Scope/risk:** focused **R2** because generic source-pair evidence and user-visible refusal behavior change. It is not a new physical law or a second native case.

## F-01: one GitHub Actions run, one executed workflow commit

The H3-06 v2 source-pair contract already allows one genuine GitHub run/artifact to contain two **different** native case output slots and refuses an identical `runId/artifactId/archiveEntry` tuple, as well as inconsistent artifact-ID/ZIP association. Chat B demonstrated that a fabricated same-run pair can carry **two different `compiledSourceCommit` strings** when each stored string is repinned coherently.

This increment enforces an explicit policy in both generic Python `check_source_relation` and browser JS `checkSourcePair`:

- If `baseline.runId === successor.runId`, require **the same `compiledSourceCommit`** because a GitHub Actions run has one `GITHUB_SHA`, whether or not it produced multiple artifact ZIPs.
- Keep **same-run, different original output-slot** and **same-run, different-artifact** cases legitimate when the run SHA is equal. Same-artifact input additionally requires consistent original full-ZIP hash and run ID, and the exact same native result slot remains prohibited.
- Separate genuine run IDs may legitimately refer to different source commits. Do **not** demand that all what-if studies come from separate GitHub runs as a false proxy for scientific independence.
- Check this rule against **separate rehashed SYNTHETIC-ONLY** source-pair plan/native case fixtures, not falsely reported native output. New tests show that changed successor `runId` with unchanged original commit is **refused**, even when case catalog and source manifest are consistently rehashed; a test-only same-run same-commit pair is internally admissible but still **not externally authenticated**.

The already verified D2 → D2-K2 original pair has distinct runs **43691263273** and **43693191224**, both separately verified in the original [Chat B PR #19 independent R2 review](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-19/reviews/review-01-chat-b.md). Its published source schema/manifest and all original native bytes **remain unchanged**. No new native archive or source comparison is adopted by this fix.

## F-02: no stale source-linked observations in a refused selection

The previous read-only `compare.mjs` already hid the inspector and emptied the drawn chart on refusal, so no **visible** stale reading was found in the independent review. It did not purge numeric and source-link text *inside the hidden inspector*. This increment changes the existing generic `clear()` to:

- Clear cached selected pair, original rows, selected field/index, and **all** native value/metadata chart/time/gap/source-label DOM text including both archived run links.
- Remove the plotted chart path, reset/disable physical-time slider and observation selector, and remove stale observation options.
- Leave the *pair-selection menu* enabled, so a valid, source-authenticated pair can be reselected after an error. Valid acceptance redraws the unchanged recorded original native results.
- New **actual Chromium same-page** regression: initially display the true original approved D2/K2 values and source links, select a second **TEST-ONLY menu label of the exact same approved source pair** with an intentionally wrong expected source commit, assert refusal while the inspector is hidden, and use `text_content()` to verify stale values are **physically absent from the DOM**, not merely invisible. Verify disabled controls/empty chart and successful subsequent reselect/recovery on the same page. This is **not** a seventh case, a new native run, a new displayed pair, or a source rewrite.
- Retain the previous fresh-page wrong-run and delayed asynchronous selection-race regressions.

## Preservation, limits and release

**No changes:** H1 physics/Modelica/checker/runner/temporal or numerical limits; original six `viewer/network/data/*.json` native case bundles; D2/D2-K2 H1 model/study/source catalog and v2 pair manifest; archived native evidence; network renderer `app.mjs`, `core.mjs`; frozen H1-C1 baseline. All native output remains **`diagnostic_only`**, **`nativeQualified=false`**. No OpenModelica builds, launches or version queries in this work.

This only tightens relative **source consistency** and refused **UI data hygiene**. A self-repinned bogus pair/ZIP/commit can still match internal checks; **external trusted GitHub run/executed commit/artifact ID/original complete ZIP SHA-256 attestation is mandatory** for any subsequently published native evidence. No independent scientific/native qualification, classroom trial, inverse/symbolic solving, freeform parameter sweeps or new model components are claimed.

**Release gate:** source branch, current exact SHA, deterministic full H1 / Python / JS / real Chromium desktop/mobile CI, synthetic negative tests, draft PR, **independent R2 Chat B** report and owner-standing authorization for merging only after true scoped PASS. Preserve initial failed CI history and final original artifact SHA. Post-merge CI must be checked and central review status updated.
