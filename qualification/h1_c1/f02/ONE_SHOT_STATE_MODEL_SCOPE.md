# SIM_HEAT H1-C1-F02 — HYPOTHETICAL one-shot protocol state-machine model

**Status: UNTRUSTED, OFFLINE, NONEXECUTING RESEARCH MODEL. NO REAL OWNER APPROVAL, TRUSTED EXTERNAL STORAGE, CAS RESERVATION, OMC VERSION QUERY/BUILD/LAUNCH, OR NATIVE PHYSICAL OBSERVATION.**

This follows the independent [PR #41 scoped PASS](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-41/reviews/review-01-chat-b.md) for a **read-only HOLD** audit with all 11 genuine native/release prerequisites missing. PR39's local SQLite and PR40's in-process fake CAS both demonstrate why cross-run/cross-host durability, protected owner authority and no-retry guarantees cannot be inferred from local state, GitHub `concurrency`, `GITHUB_RUN_ATTEMPT`, or a source Git blob. They are **not** real native controls.

## Precisely bounded new contribution

`offline_one_shot_state_model.py` is a **pure Python immutable state-transition MODEL** for a fictional three-operation process: a *hypothetical* version-query slot, build slot, and model-launch slot. These names are **labels only**. No version query, model compilation or simulation is performed or made possible. Real permitted budgets remain **zero** in every state and JSON receipt. The fake state is not a permit, not a persisted ledger, not owner-signed, not globally shared, and not consumable by a real/native runner.

Its only allowed transitions are:

- `claim-version` from `AWAIT_HYPOTHETICAL_VERSION`, `claim-build` from the corresponding build await state, and `claim-launch` from the corresponding launch await state. Each changes **only local Python tuple values**, *first* consuming a single fictional slot.
- `simulate-ok` advances to the next fictional stage **only after** its slot was consumed. It never proves an effect occurred. `simulate-failure` after consumption makes that fictional state terminal.
- `crash` or `outage` makes a fictional history terminal immediately (whether or not a hypothetical claim had yet been recorded). Terminal states refuse all events, including retries and rebuilds. The project does not infer successful native action from uncertain crash/timeout status.
- Every fictional state carries `owner_native_permission=false`, `external_durable_store_verified=false`, and **`actual_omc_budget=(0,0,0)`**. Full action-history/phase/counter replay and strict scalar types detect forged local histories or increasing a slot count beyond one.
- `exhaustive_model_check(max_depth=9)` uses a bounded breadth-first search of possible event sequences, including every refused event, to verify **at-most-once only within a single shared, immutable toy-state history**, after calling reviewed PR41's scientific-source and 11-missing-gate HOLD audit.
- `demonstrate_crash_hold` and `demonstrate_outage_hold` verify that a claimed toy slot stays consumed and uncertain outcomes do not allow a retry.
- `demonstrate_split_brain` explicitly creates **two fresh independent toy states** and successfully claims the same fictional slot in **both**. This is the essential counterexample: **no shared protected atomic persistence and therefore NO real cross-host one-shot guarantee**.

There is no real external provider, authenticated owner token, protected trust root, runtime adapter, executable native plan, compiler subprocess, filesystem reservation, network call, OpenModelica dependency, MAT output, or reference regeneration in the new code. No actual OMC or Modelica executable will be installed or invoked. The CLI choices are `check-hypothetical-only`, `demonstrate-crash-hold-only`, `demonstrate-outage-hold-only`, and `demonstrate-split-brain-only`; no `native`, `execute`, `approve`, `launch`, `reserve-native` or `build`.

Every success-shaped receipt explicitly says `releaseBlocked=true`, `ownerNativeAuthorized=false`, `realAtomicExternalReservationPresent=false`, `actualOmcVersionQueryBudget=0`, `actualModelBuildBudget=0`, `actualModelLaunchBudget=0`, `actualRetryBudget=0`, `nativeExecuted=false`, `nativeAllowed=false`, and retains both original scientific FAIL flags.

## Evidence boundaries and unsolved real authority

The state machine establishes only **a property of its own assumptions**, which include a *single* immutable Python history. It is not a temporal-logic proof over an actual multi-host infrastructure, tamper-evident event log, concurrent real external CAS implementation, owner signature, or a validated native one-shot launch. It explicitly **fails** to provide global uniqueness when state is reset, forked or stored in separate places.

An actual pre-native authorization flow must have all 11 PR41 missing release gates satisfied independently: an owner-authenticated exact protected source/reference release and durable backup, live source/root trust, separately reviewed non-regenerating executable native runner and exact plan, observed authentic OMC/MSL/compiler/host hashes, protected owner-controlled globally shared transactional CAS with crash/partial-output preservation and no retry, independent pre-native R2 and **distinct explicit owner approval for each specifically named version-query/build/single-launch budget**. The presence of a new protocol model does **not** satisfy any of those gates.

## Frozen physics, archived reference, old FAILs

The original frozen F0 source commit `dd8c9432abe97563414bb3ed809e61e673473812`, first author's Modelica SHA-256 `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`, evaluator's modal study SHA-256 `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b`, frozen H1 physical source/checker/runner, and the original PR31 saved checking bundle raw SHA `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368` / seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9` are preserved.

**Historical original F0 reference accuracy: FAIL, only 80× versus required ≥100×.** PR32 cross-host bitwise reproduction of the original PR31 saved seal: **FAIL**, regenerated alternate seal is NOT adopted. Original nine actual C1 native public readings remain **not_computed**, because no native execution occurred.

## Independent review boundary

New source/CI requires exact-head checks, full prior frozen offline regression, and independent R2 because eventual state/one-shot semantics are execution-critical. A scoped PASS would establish only that **the fictional model and its counterexamples are accurately represented**. It would NOT approve a real external store, native release, executable adapter, owner permission, actual compiler action, a source merge or a physical numerical result. Historical experimental PRs stay draft/unmerged.
