# Developer-authored thermal bridge — offline result (not H1-C1)

**Date:** 2026-11-15. **Status:** new physical arrangement admitted and analytical checking reference prepared; **no native simulation, transfer qualification, or independent-author success claimed**.

## Chronology, authority and frozen production baseline

1. The implementation-aware assistant selected the physically distinct **DEV-BRIDGE-1** task, including all physical values, connectivity, and exploratory questions, and committed `experiments/dev_bridge/TASK.md` **first** at `937d66f79af288f05f633330c49c75d9517c31a2`. Task SHA-256: `3f9a1e11af69227a2ffaf3353a2a59662cbb150a63bbae3da5fa9a889361873c`. The fixed task was not rewritten or tuned against reference or native results.
2. The implementation-aware assistant then authored `h1/cases/DEV_BRIDGE/model.mo` and `study.json`, with six passive requests and physical-slot provenance. Source model SHA-256: `a18b56dbf748bff1c6609970d0812489f800a46d2154d90921f3cb14cb933b2e`; study SHA-256: `ec359796e1c1c8daa85a5d518dec658dadedd15470885ccf1f978c0ed6a2318f`.
3. A checking-only numerical reference `experiments/dev_bridge/reference/DEV_BRIDGE.json` was separately authored from the task's physical SI facts; its SHA-256 is `b316d55727671755423c1c45145b6c0db41da0149b05bef9010bdc500c85d255`. It is a **same-author** reference, not independently reviewed evidence.
4. A local scratch snapshot ran the frozen validator and reference-preparation modules, then its original **105 tests**; all 105 passed with no failures. The source SHA-256 values for the involved Modelica package, parser, study loader, reference solver, temporal policy, decoder and verifier match the exact H1-C1-F0 freeze manifest. This is **not** a claim that the expanded 149-test current branch suite was run.
5. The existing offline admission reported `admitted=true`, `nativeExecuted=false`, **four ideal nodes in one connected thermal network**, scaled grounded-junction condition `1.0`, and all six requests `not_computed`. The generic registry requires **42 outputs**, without any special-case physics.
6. The existing `h1.verify prepare` accepted the separately entered facts and bound the unchanged reference. Its seal is `d644302bebfa877e1739a70850a0b8f3bb878ef7bed93158b431ec2189f73ce2`. No native candidate has yet been compared, so this is **reference preparation**, not numerical validation of an executed model.

## Teaching comparison and predeclared interpretation

A **five-conductor, two-reservoir, two-body bridge** joins two independently maintained-temperature nodes and two finite storage nodes. Each body has its own hot and cold path; a fifth conductor provides cross-coupling. There are two independent conductor loops. The arrangement is different from the exposed simple series, reservoir/body, two-body, three-body, and single-junction examples. It is not a blind C1 challenge.

The separately prepared reference predicts the declared left-to-right bridge flow changes from **−6 W initially** to **+2.029 W at 20,000 s**, with a zero crossing around **1,730 s**. This numerical prediction was made **after** the fixed task and authored model existed and is not a measured OpenModelica output or certified reference-accuracy result. It gives a clear later physical check of passive sign changes and energy ownership. No parameter was adjusted to force this outcome.

## Limits and next bounded execution

This is evidence of **offline authorability and admissibility under a frozen general parser**, not yet successful native assembly reuse. All 42 native exports and 2001 planned time samples remain unexecuted. The existing status labels are unchanged. No source code, component library, parser, result reader, runner, numerical policy or freeze was modified. No model was copied from an exposed solution. No independent author or reviewer was invoked; the unrelated H1-C1 transfer task stays **unselected**.

Before native execution: review this developer-authored case as a new scientific scenario, confirm selected-point/reference-accuracy evidence and the numerical horizon, pin an exact one-build/one-launch cloud plan with original source/checker identities, and record the bounded authorization. Stop on mismatch; do not silently tune or repair production physics. The first actual native run, if any, must retain complete outputs and failures. This report does **not** launch that run, merge a PR, or assert a charter-level transfer PASS.
