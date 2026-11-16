# H1-C1-F0 — independent-author transfer readiness (no candidate selected)

**Record date:** 2026-11-16. **Stage:** `awaiting-independent-task-first-submission`. The source project has completed development demonstrations (including Ring4 and conductivity what-if), but the **held-out H1-C1 transfer test remains unattempted**. This is a process/attribution record, **not** a physical model, new input reference, changed admission rule or C1 pass.

## Canonical original freeze and public packet

| Pinned identity | Value |
| --- | --- |
| Original fixed pre-C1 implementation source | `dd8c9432abe97563414bb3ed809e61e673473812` |
| Original fixed source Git tree | `551904dc91ce5d70cc6dfc72b2115e8ae497fa22` |
| Frozen H1 subtree Git tree | `92a10d90aebfed5a3c0f655297e1f727b4c52c6b` |
| Author packet publication commit | `ea954eee9b416498874419b9c8e5503f94821be8` (historical draft PR #9; original packet also on later main) |
| [Original `AUTHOR_CONTRACT.md`](AUTHOR_CONTRACT.md) SHA-256 | `bcb4bb3b6360b5e97440bf0c91f0de6ca447711a5ec630ccb58c2d24aa38bae6` |
| [Original `START_HERE.md`](START_HERE.md) SHA-256 | `fa5d2397327ba399216563c261fb2a8c006c46e0233377957989f9c914e0a25c` |
| Freeze identity | [`FREEZE.json`](FREEZE.json), schema `sim_heat.transfer_freeze/1`, ID `H1-C1-F0` |
| Externally authored C1 task | **NOT YET SELECTED** |
| Original model/study author submission | **NOT YET RECEIVED** |
| Offline C1 admission, independent reference, native execution | **NOT YET ATTEMPTED** |

The two author documents on current main have **exactly the same Git blob identities** as the frozen publication `ea954eee9b416498874419b9c8e5503f94821be8`. The public author must read **only** those two pinned documents; not the code, examples, solved cases, checker, this evaluator-only record or prior chat transcripts. Original public-contract/START_HERE text is not rewritten for this intake.

## Explicit SHA drift audit — do not silently assess C1 on live main

GitHub exact tree comparisons made on 2026-11-16 between **original F0 source commit** `dd8c9432abe97563414bb3ed809e61e673473812` and then-current merged `main` commit **`3287fafc8f1f3cb84b84a4db1c28f032f460e6ca`** showed **13/14** `FREEZE.json.executionAndCheckingFilesSha256` pinned source files have **byte-identical Git blobs** in the two commits. **One differs**:

- `h1/matv4.py`, original Git blob **`f2d2a440419b752fa65a3e5795400b26881eb1bf`**, current-main blob **`21aac158ed7055a570680a8de74de4219711a621`**. The source change adds explicit “MAT channel uniqueness is not independent measurement” clarification, changes the output report field `channelIsIndependentMeasurement` to `hasUniqueMATChannel` and report schema `sim_heat.matv4_adapter/1` to `sim_heat.matv4_adapter/2` (plus comments). This is evidence-metadata semantics; it **must not** be silently described as the original F0 frozen adapter.
- Original F0 code still exists at its **immutable SHA**. If a C1 attempt is claimed as *post-F0 no-production-repair transfer*, the evaluator must run it against the original exact F0 source/checking hashes or explicitly mark the experiment as a **new different baseline**. A test using modern `main` may be useful developmental evidence but **cannot** be falsely relabeled an unchanged H1-C1-F0 result.
- The public author contract says only what the author may submit. It does not authorize inserting an adapter-v2 compatibility patch into the original F0 runner. If original F0 refuses later actual native output, retain the refusal and assess a separately named successor instead of backporting or silently substituting `main`.

The difference is a **metadata/report-schema change**, not a detected change to the rod/body physical laws; it still matters to historical evidence qualification.

## Fresh authoring role and known exposure — evaluator only

A true first-capture attempt requires an LLM author **other than the implementation author**, in a separate conversation with no prior implementation/review/solution access for this test. It must disclose project exposure and assistance honestly; a different chat alone does not prove different model weights, independent expert certification or task-selector independence.

The frozen `START_HERE.md` already lists examples that must not simply be renamed. **Additional post-F0 developer-exposed demonstrations now exist:** DEV_BRIDGE (two boundaries, two finite bodies and five rods with a massless junction), S1 (steady series copper/steel), Ring4 (four finite bodies in a cycle, A–C diagonal and a fixed-temperature reservoir), and H3 D2/D2-K2 conductivity comparison. The evaluator **must compare the externally selected task topology against these exposed examples before claiming structural novelty**. This is disclosure/context for the evaluator, *not* an instruction for the implementation author to choose a new topology. A task that overlaps materially is not silently swapped after capture.

## Staged independent-author intake: no manual report copying required

[Source issue #26](https://github.com/physicsvigilante/sim_heat/issues/26) is an empty, neutral task/model intake channel. Its issue **title and body do not specify or suggest a C1 physical arrangement**.

1. **Stage 1 — task-only.** The separate author opens ONLY [frozen START_HERE](https://github.com/physicsvigilante/sim_heat/blob/ea954eee9b416498874419b9c8e5503f94821be8/qualification/h1_c1/START_HERE.md) and [frozen AUTHOR_CONTRACT](https://github.com/physicsvigilante/sim_heat/blob/ea954eee9b416498874419b9c8e5503f94821be8/qualification/h1_c1/AUTHOR_CONTRACT.md), selects the task independently, and posts the **full unedited first `TASK.md` as one GitHub issue #26 comment** with role/exposure disclosure. **They stop before drafting a model/study.** A top-level GitHub issue comment does not push source code.
2. **Evaluator captures and freezes Stage 1.** Retrieve the exact GitHub issue-comment ID/body/created timestamp, preserve the original content verbatim as a separately attributable raw record in a case-specific evidence directory/branch, and record a SHA-256. Do **not** rewrite, solve, simplify or give approval based on analytical outcomes at this stage. Only after preserving the original task may the evaluator invite Stage 2.
3. **Stage 2 — first physical authoring.** The **same** independent author, still using only the two public documents and their frozen task, posts raw `model.mo`, `study.json`, `AUTHOR_NOTES.md` as a **second separate GitHub issue comment** and stops. Any unresolved model SHA is openly identified and mechanically completed by the evaluator only with an assistance record. All first authoring bytes and uncertainties must be preserved before validation.
4. **Evaluator after first-capture.** Inspect physics interpretation, task-model fidelity and exposure against known examples; then use frozen offline C1 parser to assess request admission; independently prepare reference, primary horizon and error bounds, source-hash-pinned one-shot native plan **only if** bounds/provenance/permissions permit. Native candidate outputs remain `diagnostic_only`/`nativeQualified=false` unless a separately justified qualification gate explicitly changes that. Do not fabricate a student/classroom outcome or rescue first attempt with an easier substituted task.
5. **Independent R2 review** applies to any new actual native evidence/admission semantics; a source PR requires exact SHA and CI plus central review packet. Original task and model-first attempts remain immutable even if rejected.

If the author cannot post to GitHub directly, the author should return their entire task **first and stop**; a separate evaluator can capture it manually before Stage 2. Do not represent a user-reserialized task as a byte-identical independent original without documenting normalization/assistance.

**This process record does not consume a native run, select a C1 task, certify reference error or amend F0.** No new model or study should be added to source as “first submission” until an independently authored task is captured.
