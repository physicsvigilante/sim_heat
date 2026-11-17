# H1-C1 F02 — owner-controlled external CAS contract PREVIEW (OFFLINE FAKE ONLY)

**Status: INDEPENDENT R2 NOT YET REQUESTED. NO NATIVE WORK AUTHORIZED. NO REAL EXTERNAL PROVIDER CONNECTED. NO OWNER-AUTHENTICATED RELEASE OR NATIVE BUDGET.**

This is deliberately separate from [PR #39's independently scoped-PASS local SQLite demonstration](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-39/reviews/review-01-chat-b.md). That review independently proved local cooperative uniqueness but **also proved database deletion/recreation and two isolated databases can yield multiple first claims**. A local SQLite file, fresh stage label, GitHub run attempt number or workflow concurrency is never a real cross-host/native one-shot lock.

## Exactly what the new source implements

The module `offline_external_cas_contract.py` defines a bounded *design exercise* for a future owner-controlled, shared external compare-and-set (CAS) authorization system, but it does **not** implement or connect to such a system.

Its `snapshot()` contains exactly one hardcoded experimental campaign, reviewed PR #39 source SHA, original first model and evaluator-modal-study hashes, owner-approved **OFFLINE checking only** archived PR #31 V2 raw SHA and seal, and the separately reviewed disabled-native-plan SHA. **Every native budget counter is literal zero**: compiler version queries, builds, launches and retries are all unapproved. All owner/release/host/actual shared-store assertions are literal false. `assert_snapshot()` refuses changes to the complete canonical simulation facts or wrong JSON scalar types.

`ExternalAuthorityUnavailable.reserve_native`, `validate_native_launch` and `require_native_permission()` **unconditionally raise `GateRefusal`**. There is no optional network configuration, API token, GitHub write, shell, compiler wrapper or native runner invocation. There is no code path which can mint a real native reservation or permission.

`FakeAtomicCAS` is explicitly an **untrusted, volatile, same-Python-process fake**, using `threading.Lock()` to emulate a unique `put-if-absent` on one in-memory dictionary. `simulate_contention()` demonstrates exactly one fake first claim and N–1 fake refusals among multiple threads using **one instance**, not separate processes/hosts. `simulate_split_brain()` constructs **two independent fake providers** for the SAME campaign and requires two independent fake first claims, proving absence of global one-shot protection. `simulate_reset_attack()` destroys its fake store and requires another first claim, proving loss of attempted reservations. A forged nonce string with the expected shape can be stored because the fake has no protected signature: deliberately tested, never accepted as an owner/native token.

The CLI allows only `inspect-unavailable-authority`, `simulate-contention-only`, `demonstrate-split-brain-only`, and `demonstrate-reset-only`. No `omc`, `execute`, `approve`, `reserve-native`, `build`, `launch` or `run` action exists. All receipts are labeled `UNTRUSTED` or `REFUSED`, with **`nativeAllowed=false`**, **`ownerNativeLaunchApproved=false`**, **`realAcrossRunReservationAllocated=false`**, `crossHostAtomicityProved=false`, `externalStoreConnected=false`, `compilerQueried=false`, `buildInvoked=false`, `modelLaunched=false`, and all historical F0/PR32 success flags false. Any fake count/nonce/hash is a **local exercise**, not an attestation.

## The actual separate runtime authority contract (NOT implemented)

A real owner-native one-shot gate would need ALL these conditions verified **before any budget-consuming operation**:

1. Independently authenticated owner release for **this exact frozen source/model/study, PR31 saved scientific raw JSON and canonical seal**, original failed evidence and active non-regenerating native adapter, with signed/protected immutable designation and verified durable backup/recovery policy.
2. Exact reviewed *executable* adapter and pinned plan committed/attested independently, with no fallback to the frozen `h1_native_batch.prepare` reference generator. Explicit remote source freshness, no mutable unprotected `origin` ref as sole trust root.
3. Real target host identity and **actual** OpenModelica executable/version/hash, MSL source tree/version/hash, Python/package/compiler/runtime and operating image identity; planned strings (OMC 1.27.0, MSL 4.0.0) are not observed facts.
4. Authenticated narrow-scope access to **one owner-controlled, durable, shared external atomic CAS store**, reachable by every permitted host/job and never anonymously resettable. Unique campaign key and exact owner release/host/plan/budget fingerprints, no secondary/fallback store, atomic compare-and-swap, durable consumed state and tamper-evident independent audit.
5. Separate counts and authorization for the **specific version query, build and one model launch**, with strict no retry. Define what constitutes consumption *before* each action and preserve cancellation, timeout, crash, unavailable-store and partial-native output evidence without accidentally restoring/duplicating a budget. Recovery must not silently replace a consumed campaign with a fresh token.
6. Independently reviewed source/remote auth/host/plan/atomic-store path and an explicit **new owner approval for the particular native-version/build/launch budget**. No such owner approval was given; Option A was checking-reference **offline only**.
7. After an actually permitted run, independent review of MAT/native provenance, 37 exports × 4001 timestamps, four integral histories, conservation/energy balances and all nine original public observations. None is currently native-qualified or computed.

The present in-memory fake **does not verify, reserve or authorize any of these**. There is deliberately no real provider implementation to misconfigure, no native executor and no OpenModelica dependency.

## Frozen science/history and review requirements

Original frozen F0 implementation `dd8c9432abe97563414bb3ed809e61e673473812` and the author's Modelica `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435` remain unchanged. The approved PR31 archived reference for **offline checking only** has exact raw SHA `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368` and canonical seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9`. The original first F0 static `hotLead.G` accuracy **80× against required ≥100× FAIL** and the PR32 two-host regenerated V2 bitwise identity **FAIL** remain preserved; no reference regeneration, tolerance waiver, native launch or historical source merge is part of this work.

A scoped R2 review must assess precise semantics and limitations of the **untrusted external CAS fake and default-deny interface** and actual exact-head offline CI (including split-brain, reset, forgery and CLI refusal evidence). Such a scoped PASS would NOT authorize actual external credentials/provider configuration, a real atomic shared store, signed release, native plan or OMC execution. A real trust/runtime mechanism requires a separately approved owner release and new R2.
