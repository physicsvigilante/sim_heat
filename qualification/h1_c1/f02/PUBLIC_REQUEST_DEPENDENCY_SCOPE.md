# SIM_HEAT H1-C1 F02 — original nine public observations to EXPECTED export dependencies

**Status: UNREVIEWED OFFLINE SOURCE-INTERPRETATION CANDIDATE; NO NATIVE VALUES, NO OMC, NO RELEASE, NO OWNER NATIVE PERMISSION.** This historical F0 experiment stays in a draft PR, never merged to production `main`.

This work follows [PR46's independent scoped R2 PASS](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-46/reviews/review-01-chat-b.md) for 37 original expected model exports, four original *analytical reference* flow-integral histories and nine admitted original authored public requests, all with **zero observed native results**. That reviewer independently verified the original archived PR31 V2 bundle and author Modelica/model study and emphasized that the report's `validate_shape` **alone** cannot authenticate complete provenance. This new source reuses the full source-derived original bound inventory and compares exact canonical serialized reports; shape-only cannot authorize values or owner trust.

## What the source maps, and what it never computes

`offline_public_request_dependencies.py` uses the original modal study `h1/cases/H1_C1_MODAL/study.json` and unchanged `h1.model` port/component kinds to construct a **name-only dependency mapping** for all nine requests. The mapping follows the projection semantics already present in frozen `h1.verification.check_candidate`: direct `temperature` maps an authored thermal component port to its expected `.T`, `.T_a` or `.T_b` field depending on component kind/port; direct `heatFlow` maps a RodArea/RodCircular component to `.Q_flow` (the positive original `Q_flow` orientation, never a guessed port-sign flip); direct `energyChange` maps a Body to `.dU`; and `temperatureDifference` is **first authored port temperature minus second authored port temperature**, represented as two ordered terms with literal signs `+1` and `-1`. No subtraction or physical value is evaluated.

<escape>Original nine mapping (source-derived expected field names, NOT observed native values):

| Original public ID | Expected source terms | Unit / status |
|---|---|---|
| leftTemperature | +leftBuffer.T | K / not_computed |
| rightTemperature | +rightBuffer.T | K / not_computed |
| hotLeadFlow | +hotLead.Q_flow | W / not_computed |
| flatBridgeFlow | +flatBridge.Q_flow | W / not_computed |
| roundBridgeFlow | +roundBridge.Q_flow | W / not_computed |
| coldLeadFlow | +coldLead.Q_flow | W / not_computed |
| bufferTemperatureDifference | +leftBuffer.T − rightBuffer.T | K / not_computed |
| leftEnergyChange | +leftBuffer.dU | J / not_computed |
| rightEnergyChange | +rightBuffer.dU | J / not_computed |</escape>

No exporter is invoked; these are **intended frozen Modelica field names**, not evidence that OMC actually publishes them. Expected exports are validated against the complete original source-derived PR46 37-field inventory and saved PR31 original analytical reference field names/units; original first-author Modelica and evaluator modal study raw SHA identities remain unchanged. The report intentionally includes NO numerical analytical series, native MAT/CSV or public values.

The new output contains 9 entries with `id`, `operation`, original authored operand references, `expectedUnit`, `dependencyKind`, `orderedExpectedExportTerms` each with exact `exportName` and signed integer `sign`, and the frozen source rule's **non-executable textual identifier**. Every entry has `expectedOnly=true`, `nativeStatus=not_computed`, `nativeValue=null`; total 8 direct expected-model-field dependencies and 1 two-field derived difference (10 signed terms). All native observation/series counts are literal zero. Source pins, original saved checking-reference SHA/seal and **all 11 genuinely absent owner/release/backup/toolchain/executable native adapter/globally protected shared CAS/pre-native R2 gates** remain enforced through the inherited read-only PR41 HOLD and Option A checking-only consumer. Every native/owner/historical-success claim is literally false and `releaseBlocked=true`.

A purely structural `validate_shape` is **not** proof of exact source interpretation. A copied/altered report must pass `assert_exact_source_bound`, which derives a fresh original source-bound report and compares canonical raw JSON bytes. This refuses missing/renamed/reordered/duplicate dependencies, signs/units/op/operand tampering, Python bool versus integer and float scalar substitutions, injected `nativeValue`, omitted/filled release gates and original PR32 alternate scientific seal. The exact report is not an owner signature or provenance proof; a genuinely executed native trace would require separate authenticated source/host/plan release and actual native-data verification.

## Original scientific/owner hard limits

Original frozen F0 `dd8c9432abe97563414bb3ed809e61e673473812`, original first-author Modelica raw SHA-256 `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`, evaluator modal study `b43e85b6b10afd6550a43322cf98097fe9781a606ee01bc031eadbfd4783b31b`, owner-adopted ORIGINAL saved PR31 V2 raw 4,409,800-byte analytical checking-reference SHA `0db511dd8dba023d16518667de256029cf3e073463ea21e2478aeac8afd1f368`, and canonical seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9`, unchanged and checking-only.

**Frozen original F0 hotLead.G precision margin 80× vs mandatory ≥100×: FAIL.** PR32 cross-host bitwise original PR31 seal reproduction **FAIL**; alternate seal NOT adopted. Nine actual native public C1 observations still `not_computed`. This dependency map neither fixes these failures nor computes a reference or native reading, and it cannot serve as an executable adapter or model authoring.

This is an **R2 source/evidence-semantics** request: independent review must confirm actual frozen source field/port projection and orientation, source array names/units, sign of the temperature difference, 8 direct+1 derived breakdown, lack of numerical/native values and exact source binding. It must not grant a native permit, physical qualification or source merge. Real native version/build/one launch would still require an independently protected source/backup, observed host/OMC/MSL, reviewed nonregenerating executable adapter/plan, durable protected owner-controlled external atomic one-shot with no retry, and a **new separate explicit owner authorization for the exact named version/build/single-launch budget**.
