# SIM_HEAT F02 — offline stale-snapshot CAS **counterexample model**

**Status: UNREVIEWED OFFLINE PROTOTYPE. There is NO trusted external store, owner-authenticated release, actual native budget, native executor, OpenModelica version query/build/launch or physical qualification.** This is an explicitly non-authoritative source study.

This work follows the [independently scoped-PASS PR #42 hypothetical state machine](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-42/reviews/review-01-chat-b.md). Its reviewer identified a specific risk: even a **single stale immutable initial snapshot** can be used to fork two internally consistent histories. Pure Python immutability/history replay cannot substitute for a protected, linearizable, globally shared compare-and-swap (CAS). PR39 local SQLite, PR40 volatile fake CAS, and PR41 11-missing-gates HOLD remain fully preserved.

## New bounded differential experiments

`offline_stale_snapshot_cas_model.py` implements the following ONLY in Python RAM with no network/remote service:

- **One in-memory versioned fake, several stale readers:** many threads all receive the exact same initial fake `ObservedToyState(epoch, version=0, already_claimed=false)`. A lock-protected `fake_claim_if_unchanged` checks the fake epoch, version and consumed flag together. Exactly **one toy claim** succeeds for that **single fake object**, later stale reads refuse. This illustrates the *logical need for linearization*, not an actual cross-host atomic store.
- **Naive stale check-then-use counterexample:** two independent actors treat the same unprotected pre-claim snapshot as approval; both advance **fictionally** because the read and write are not atomic. The report explicitly states that **no CAS was used**.
- **Two distinct fake stores:** both have the same campaign label, but each grants a first toy claim. This proves a host/job split-brain weakness. Source SHA and an identical campaign string alone cannot identify one shared global authority.
- **Reset/recreation:** clearing an in-memory fake state allows a second first claim, even though replaying the previous epoch is refused. An epoch change is not durable owner-controlled non-resettable custody.
- **Lost acknowledgment after a fake commit:** the fake stores the toy consumed bit, but the caller's uncertain acknowledgment is not a native-effect observation or permission to retry. A second CAS with the stale snapshot refuses within that one object. There is no real crash/network/service tested.
- **Default-deny real native interface:** `require_real_native_permission` **always raises `CASRefusal`**. Its no-native CLI has only five fake/audit/demonstration verbs, rejecting `omc`, `execute`, `build`, `launch`, `native`, `approve`, `reserve-native` and `retry`. `audited_fake_run` first calls the reviewed PR41 read-only release HOLD, which must report **all eleven release gates still missing**.

Every emitted fake receipt states `releaseBlocked=true`, `ownerAuthenticated=false`, `ownerNativeLaunchApproved=false`, `durableOneShotReservationAllocated=false`, `crossHostAtomicityEstablished=false`, `realExternalCASConnected=false`, `nativeAllowed=false`, `nativeExecuted=false`, and all actual OMC version-query/build/launch/retry budgets as **literal integer zero**. All historical scientific success labels remain false. The fake's random epoch is only an untrusted local in-memory version marker, **not** an owner credential or release token.

The code's `VolatileVersionedCASFake` deliberately offers no authenticated principal, write protection, independent storage, cross-process connectivity, durable transaction receipts, real network failure semantics, owner-approved native budget, or retry/partial-output recovery. The single-object simulation cannot establish real linearizability, serializable owner custody or version/build/launch at-most-once across concurrent hosts.

## Frozen source and scientific evidence

The first original author Modelica SHA-256 `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`, evaluator modal study SHA-256 `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b`, frozen F0 source commit `dd8c9432abe97563414bb3ed809e61e673473812`, old native runner/checker and original unlaunched plan remain unchanged.

The user-approved **offline checking only** reference is one **exact original PR31 V2 saved** analytical bundle: raw SHA-256 `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368`, canonical seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9`. The original F0 static `hotLead.G` checking precision is only **80× vs mandatory ≥100×: FAIL**. PR32 host bitwise reproduction of original V2 seal also **FAIL**; its alternate seal is not adopted. The original nine native observations remain **not_computed**, and no native command is invoked in this PR.

## Future real owner-native gates (NONE satisfied here)

A genuine cross-host one-shot controller still needs: independently authenticated protected original source/reference release and durable backup; current signed/verified origin; an independently reviewed non-regenerating *executable* adapter and exact plan; observed target host/OMC/MSL/compiler/runtime hashes; a protected **owner-controlled shared external atomic transactional CAS**, strong unique campaign identity, monotonic/consumed durable ledger and no-delete/no-reset recovery; crash, timeout, acknowledgment-loss and partial-native-evidence failure policy; independent pre-native R2; **separate explicit owner authorization for named OMC version-query/build/one launch/no retry budgets**; and independent post-native numerical/MAT output review. All eleven PR41 release gates remain missing. The source is still an F0 experiment on a draft PR and must **never merge to production main**.

**Independent review scope:** assess the correctness of the fake differential demonstrations, verify stale snapshot and split-brain/refusal tests and all nonnative flags, exact-head offline CI preservation, and explicitly rule out real owner/native CAS authorization. This source cannot qualify a real physical run or prove production one-shot safety.
