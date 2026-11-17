# H1-C1 F-02 — Reference-bound native-control DESIGN PREVIEW (strictly offline)

**Status: NON-EXECUTABLE PROPOSAL. No independent R2 review yet. No OpenModelica execution or owner native-launch approval.**

## Why this narrow step exists

The owner approved **Option A only for read-only scientific checking** of the exact independently reviewed H1-C1 PR #31 V2 reference. [Central owner decision](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-34/OWNER-DECISION-01.md); [PR #35 independent scoped review](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-35/reviews/review-01-chat-b.md). The frozen historical `tools/h1_native_batch.py::prepare` **regenerates** references with `reference.prepare`; PR #32 demonstrated this can produce another bitwise seal. It cannot be reused unchanged for qualification of the reviewed saved PR #31 bundle.

The next safe goal is to prove **what an approved reference-bound native plan would have to bind**, with no native activation, no executable/native-runner code, and no misleading fabricated readings. This work is on a separate historical draft branch; do not merge it or historical PRs to production main.

## Exact frozen and adopted identities

- Original H1-C1-F0 source: `dd8c9432abe97563414bb3ed809e61e673473812`.
- Original first model: SHA-256 `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`; first study `b235d4242728c44dd994e09db3ffd92d197398dde3fe6c8f006a801981997fdc`.
- Evaluator-assisted modal study: `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b`, settings start `0`, stop `1810.609003248995` seconds, `4000` intervals, `dassl`, tolerance `1e-8`.
- Original **unlaunched** F0 plan SHA-256 `f46b2621b38427ffc098d16d91695a134b7dc4d7f913021be625ee74b8a9319a`, containing 23 SHA-pinned inputs. **This old plan is historical evidence and is NOT authorized for execution.**
- Owner-adopted checking-only PR #31 raw JSON: 4,409,800 bytes SHA-256 `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368`; canonical seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9`; archived XZ SHA-256 `fc5a7df5928c3fb8aef2ba4af516dfbd32b42c0450ebef1051ad4fd7efebd17f`; whole manifest SHA-256 `50467b138ed64cdb908f2c763bc777e6babf0bb04a0711568acc559112e66f84`. Source anchor reviewed PR #33 `bf51e7721bca73720aa9b5f5f2de90defee821ec`.
- Existing approved checking-only consumer (independent PR #35 R2): `f7c69954490c8dcd48d152906e8e2a6d5699481d` (not a trusted native launcher).

## The design-only control file and its refusal boundaries

`F02_CONTROL_PLAN_PREVIEW.json` uses **`sim_heat.h1_c1_f02_control_preview/1`**, intentionally **incompatible** with the frozen native runner's `sim_heat.native_batch/1`. Its status is `DESIGN_ONLY_UNREVIEWED_NO_NATIVE_EXECUTION`. It has **no approved native source commit or plan hash, no host image, OMC executable/MSL library observation, signed owner trust root, independent runner review, persistent one-shot reservation, or owner launch permission**. These fields must all remain `null`. Proposed toolchain versions (OpenModelica 1.27.0 / MSL 4.0.0 / Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0) are **requirements for future checking**, not observed installed tools.

The `launchPolicy` explicitly forbids: native execution, creating an executable, even querying `omc --version`, a build, model launch, automatic reference regeneration, retries, or claiming simulation evidence. Its `maxLaunchesAfterSeparateApproval=1` is only a **proposed one-shot budget**, NOT an allocated or enforceable reservation. Later design must use an owner-approved, protected/durable source of truth for across-run reservation and native execution. A per-job `GITHUB_RUN_ATTEMPT=1` is not a sufficient global one-shot gate.

`offline_control_preflight.py` verifies the **whole** design file against a code-pinned original Git blob identity and its exact semantic safeguards. It then checks the owner-adopted **offline** consumer, original 23 source pins, reference identity, exact original study grid, 37 export channels, four integral histories and nine public requests. It prints **`F02_CONTROL_DESIGN_PREFLIGHT_PASS_NONEXECUTABLE`** with every native/host/owner-authorization flag false; it **never writes** a reference/native plan, calls the old numerical generator or native runner, invokes `omc`, or produces MAT/CSV/native observations. The CLI has **only `design-preview-only`**; forbidden `execute`, `prepare`, `native`, `approve`, and `launch` actions must refuse.

## Preserved prior failed evidence and future gates

The original F0 checking reference at `hotLead.G=0.44999999999999996` had only **80×** vs required **100×** accuracy margin; it stays **FAIL** and no tolerance is loosened. PR #32's cross-host generation of another V2 seal `c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07` stays **FAIL** for bitwise regeneration of reviewed PR #31. Neither is overwritten. All nine original public observations remain `not_computed` with no native trace.

**Future separate gates, not authorized by this proposal:** an independently owner-authenticated reference-release root/protected durable ref/backup; a distinct reference-bound native adapter that consumes *exactly* the stored bytes (not old regenerate); a source/host/plan SHA and actual OpenModelica/MSL identity, across-run one-shot reservation with no retry/duplicate attempts and cleanup/failure archiving, independent pre-native R2, **new explicit owner approval for one actual native launch**, and independent review of native MAT/numerical evidence. A plan can fail or remain incomplete without silently revising H1 physics or the first author submission.

This proposal must obtain its own pinned source/CI and independent R2 before future executable adapter work. **No merge or native launch.**
