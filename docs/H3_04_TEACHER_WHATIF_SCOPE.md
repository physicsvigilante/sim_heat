# H3-04 — Teacher-controlled thermal what-if comparisons (scoped design)

**Date:** 2026-11-16. **Base:** merged H3 Ring4 on `main` at `ab45af5a33888850e8577f9c70b6f8d78c168cf1`.
**Status:** bounded scope/design only, not executed/merged. Standing owner authorization covers ordinary development; **independent R2 review remains mandatory** before merging changes that alter native evidence or user-visible measured meaning.

## Teacher's task

A teacher opens an existing admitted native thermal network (e.g., D2 or Ring4) and asks: **What changes if this particular rod conducts better?** They should compare temperature histories and signed heat flows without learning Modelica. We will start with **one rod conductivity revision** because it is the *only* revision explicitly supported by the public H1 contract.

### First milestone: one hypothetical k change, no new physics

1. **Import the original source model/study from a pinned repository case.** Preserve the original model/study and native evidence byte-for-byte.
2. **Author a successor model and revision study outside the original directory.** Only a specified existing `RodArea` or `RodCircular` instance's `k` changes; the public H1 `revision` contract must enforce parent study/model hashes, target `instance.k`, `origin="hypothetical"`, reason, and unchanged physical topology, all other parameters, original analysis and requests (unless a distinctly named investigation is intentionally authored).
3. **Admission-only first.** The same unchanged H1 parser / semantic revision guard must admit a valid example and refuse wrong parent hashes, nonexistent rod, shared-parameter changes affecting other conductors, multiple property changes, topology changes and unsupported/invalid new `k`. No browser or LLM-generated Modelica is allowed to bypass admission.
4. **Compute only with actual OpenModelica.** The existing bounded generic runner generates a new separately source/plan-hash-pinned native attempt, with the reference sealed *before* the single build/launch. No runtime calls from untrusted browser text; first execution is through a fixed approved experiment branch and one-shot workflow. No fallback to reference/analytical values when results are unavailable.
5. **Publish side-by-side source-linked viewer data** with unchanged generic renderer and a separate original baseline and revised-case catalog entry. The eventual UI may offer a 2-case comparison selector once both authentic artifacts have independently checked identities, matching unit/time policies and diagnostics. It must label baseline versus hypothetical revised inputs, keep source/provenance/CI links distinct, prevent stale case/csv imports and show signed W/K/J without inventing intermediate times or a 'faster' answer from analysis alone.

## Initial selected physical comparison

Reuse the already implemented D2 two finite bodies sharing a single storage-free rod. Model **D2-K2** is an existing H1 offline admitted revision fixture, not a novel physical network; its baseline is D2. Preserve the prior D2 numerical values, study requirements, original reference/evidence and old D2 preview. Compare exactly supplied saved physical timestamps and original heat-flow sign orientation. A higher `k` must lead to faster temperature difference decay with the **same energy-determined equilibrium** in the ideal insulated two-body system; no claim that either case *reaches equilibrium at a finite time*. Treat the derivative/analytic calculation as a diagnostic reference, never as data to display.

This is a **teacher usefulness** milestone rather than a new physics or independent C1 test. If D2-K2's existing authored source is already sufficiently reviewed, reuse it under exact hash; if not, prepare a new separate provenance-controlled variant. The first native attempt and allowed budgets must be explicitly pinned and recorded. Do not re-run an old one-shot job or silently broaden the native runtime policy.

## Non-goals and success criteria

- No freeform arbitrary Modelica, network editing, parameter sweeps, browser-triggered compiler installation, symbolic or inverse solving, physical rod geometry, material tables, field interpolation, or claims of full native qualification.
- One trusted baseline and one trusted hypothetical successor, both admitted by **the same** public H1 grammar and checked with original native records. No model-specific application dispatch.
- The teacher can explain **which conductivity was changed**, inspect original/hypothetical temperature and signed heat-flow traces, and understand an asymptotic comparison without false precision.
- Passing offline tests, independently pinned native artifacts, genuine real Chromium desktop/mobile checks, an R2 draft source PR, central Chat B report and source CI are prerequisites for any release.
- Historical failed jobs, frozen H1-C1 and the five existing native viewer cases remain untouched.

## Work sequencing and risk

- **Phase 0 (this scope):** inspect existing D2-K2 model/study/revision grammar and historical diagnostic availability; record source hashes, existing gaps, the minimal intended comparison, and refusal cases. No OMC.
- **Phase 1:** implement a read-only case-pair study/revision adapter plus test-only synthetic negative cases and current-source CI. A real native rerun requires a separate one-shot fixed plan and evidence; no uncontrolled retries.
- **Phase 2:** after genuine native results, add selected data bundles and simple source-linked comparison UI; exercise browser modes and refusal concurrency.
- **Phase 3:** draft PR, exact-head CI, independent-in-context R2 review, owner standing merge authorization only once review has **passed**; check post-merge CI. Notify owner only at review handoff or hard blocker.

**Standing authorization note:** The owner asked for continuous work without routine approvals. That does not waive source checks, independent R2 review, bounded native execution, owner awareness of significant new risks or truthful diagnostic-only attribution.
