# SIM_HEAT H1-C1-F02 — local one-slot reservation SIMULATION

**Status: NONNATIVE OFFLINE EXPERIMENT — no trusted launch lock, native plan, OpenModelica or owner native-launch approval.**

This follows [PR #38 independent targeted R2 PASS](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-38/reviews/review-02-chat-b.md) for the purely offline, unexecuted Modelica build-text preview. It addresses a separate future runtime risk: a naive one-shot gate such as `GITHUB_RUN_ATTEMPT=1`, CI concurrency, or a local stage label is **not** an across-run durable owner-controlled reservation. The present prototype deliberately does **not** claim to solve that real gate.

## Exactly what this prototype tests

`offline_one_shot_ledger_simulator.py` is a **pure-Python/SQLite, local-filesystem concurrency exercise**. It uses a single hardcoded simulation campaign keyed to the previously reviewed, owner-approved **offline-only** PR31 reference and disabled-plan identities. `simulate_once(database)` transactionally executes `BEGIN IMMEDIATE` then a unique-primary-key `INSERT … ON CONFLICT DO NOTHING`. Once committed, later cooperative processes using the **same local SQLite file** refuse a second simulated slot. A process crash after the local commit does not clear that local row. `inspect_only(database)` reads a present row without creating another; `sqlite3` is the only stateful persistence tool. This code never invokes `omc`, a simulator, the native runner, Modelica build script, `reference.prepare`, or any external reservation/owner API.

The simulator returns one of `SIMULATED_LOCAL_SLOT_CONSUMED_NOT_NATIVE`, `REFUSED_ALREADY_SIMULATED_LOCALLY`, or `LOCAL_SIMULATED_SLOT_PRESENT_NOT_AUTHORITY`. It sets `nativeAllowed=false`, `nativeExecuted=false`, `realAcrossRunReservationAllocated=false`, `ownerNativeLaunchApproved=false`, `releaseTrustRootComplete=false`, `sharedAcrossHosts=false`, `compilerQueried=false` and all other native/evidence flags false. A random nonce identifies **only a local demo row**, not a signed attempt or permission token. The allowed CLI actions are only `simulate-local-only` and `inspect-local-only`. No native build/executable/plan launch command is defined.

**Deliberate negative evidence:** deleting/replacing the local SQLite database lets the demo allocate a new simulated slot. A second GitHub Actions runner/host normally has a different disk and therefore a different demo file. The SQLite lock does **NOT** protect against a malicious file owner, Git ref rewrites, shared-disk inconsistencies, race-prone symlink checks, cross-host or cross-GitHub-run duplicates, or require verified external owner release identity. The tests explicitly exhibit this failure rather than calling the prototype a real native one-shot gate. The simulator does not consume or decrement any approved native launch budget because no such budget has been granted.

## Offline checks and acceptance

The code tests successful first claim/refusal of subsequent claims in fresh SQLite connections, **ten concurrent child Python processes on the same local filesystem** (exactly one should win), post-commit child-process crash persistence, read-only inspection, malformed/scientific-identity-drift and symlink refusals, invalid database paths, deletion/reset weakness and no native/owner command API. Tests use Python multiprocessing, `sqlite3`, `tempfile` and pure library code only; no Modelica installation, version query, build or launch.

The prior full offline history is unchanged: 15 corrected text-preview tests, 24 immutable input staging tests, 16 disabled plan/type tests, 11 owner-approved offline consumer tests, 8 source binding tests, 9 archive-integrity tests, and 149 original frozen H1 tests. The new workflow must keep all source/plan/reference SHA pins and compare only **added** files against independently reviewed PR #38; no frozen files may change. It triggers on all pushes to this experimental branch rather than filtered files; it is **not** a protected required check.

## Immutable reference and historical FAILs

- Original model SHA-256 `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`; evaluator-modal study SHA `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b`. Frozen original F0 implementation `dd8c9432abe97563414bb3ed809e61e673473812` unchanged.
- Owner-adopted **OFFLINE checking only** PR31 saved reference: exact raw SHA `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368`, canonical seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9`. This simulator does **not** read, regenerate, replace or certify reference values; the recorded reference SHA is only a fixed **expected** context identifier.
- Original frozen F0 reference error margin **80×** versus strict **100×** required **FAILED**. PR #32 two-host bitwise regeneration of the original reviewed PR31 V2 seal also **FAILED**. Both remain genuine historical FAILs; the simulator reports both checks false. All nine actual C1 native public observations remain **not_computed**.

## What would be needed for a real native one-shot gate

A separate high-risk implementation must use a **trusted owner-controlled external atomic store** shared across all permitted hosts/runs, authenticated identities and protected access control, durable once-only reservation semantics that survive crashes and refuse retries, source/ref/plan/host and original approved checking-reference attestation, explicit separately approved owner launch budget, safe handling of partial/failed native evidence, and an independently reviewed runnable non-regenerating adapter and exact plan. A local SQLite simulation alone cannot satisfy those. Actual OpenModelica version/build/launch operations are **NOT approved** by Option A's checking-data decision, any green offline CI or a Chat B scoped PASS.

**Never merge historical F0 source PRs into production main. No native execution, new physical law, numerical-tolerance change or reference regeneration is part of this milestone.**
