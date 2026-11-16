# H2-03S — Illustration 123: steady conduction in the generic viewer

**Scope status:** authorized source/feasibility preparation; **not** a simulated fourth viewer case or native qualification. Baseline `main` `c977773578b04a571dfefebe615350b9ed1dcf3e`. Preserve the H2-02 transient cases and their evidence unchanged. A prior planning note used H2-03 for a future teacher-controlled simulation; **H2-03S** is a distinct, narrower steady-state extension.

## Source-selected physical system

Source: read-only `01_heat.pdf`, **Illustration 123**, PDF page 2 / printed page 2.89; [source coverage](SOURCE_COVERAGE.md). Exact authored source: `h1/cases/S1/model.mo` and `study.json`, named `H1_S1`; the model already exists and **must not be reauthored to improve agreement**.

Two laterally insulated, storage-free, circular rods joined end to end, with ideal contact and constant conductivities:
- Copper: length 0.75 m; diameter 0.02 m; conductivity **0.092 kcal/(m·s·K)**.
- Steel: length 1.25 m; diameter 0.02 m; conductivity **0.011 kcal/(m·s·K)**.
- Hot end fixed at 100 °C; cold end at 0 °C.
- The existing model explicitly adopts **4184 J/kcal**, since the source does not select a calorie definition. This is a *documented convention*, not a literal source given.
- Requested observations: copper–steel junction temperature and signed rate of heat transfer, with positive orientation hot → cold. The source's printed flow calculation has a unit-label inconsistency; its mislabeled J/s number is not an SI verification oracle.

The model is **steady**. `0..1` in old runtime CSV/MAT records are algebraic evaluation indices, **not seconds, a transient, a warmup, or physical time**. No body owns energy storage.

## Existing physics and native history: precise limitations

- The existing H1-S1 study/model and generic H1 physics/observation parser already encode this case. Do not add S1-only solver or viewer dispatch.
- 2026-11-15 [S1 MATv4 workflow 43689753800](https://github.com/physicsvigilante/sim_heat/actions/runs/43689753800) **FAILED** at output-schema admission even though a native build/launch occurred. Original archived ZIP `14151084575`, ZIP SHA-256 `1db4e13999232c8f51b4d40c52ac6ecccb2a861f03309ce57c7ef02c62e6880e`, raw MAT SHA-256 `1d5ae021cf87eda8c14418b638e5cc3c353877358b52585deb7a0f7d375a0672`. Do not relabel the failed workflow as passing.
- Later [saved-MAT post-hoc analysis](H1_MATV4_S1_POSTHOC.md) using a corrected **generic** MATv4 reader obtained **18/18 native channels** and **56/56 diagnostic-only comparisons**. This was offline re-analysis of archived MAT, **not** a new successful native workflow, a measurement by independent sensors, or H1 qualification. Historical statuses stay `diagnostic_only`, `nativeQualified=false`.
- The existing H2-02 `viewer/network/tools/build_case.py` requires an archived **successful** `diagnostic_checks_passed_not_native_qualified` attempt with `case_XX/normalized.csv`, `checks_passed` and a **transient canonical grid**. The previous S1 artifact **does not meet that gate**. Do not weaken the gate or fabricate a successful attempt/receipt to force it through.
- H2-02 `sim_heat.viewer.native_case/1` / `core.mjs` / `app.mjs` require ≥2 chronological sample rows and show time controls and history charts. Do **not** encode S1 as an invented transient with repeated steady values.

## Proposed smallest defensible extension

1. **Preflight** source statement/diagram against the exact PDF, current H1-S1 source hashes, historical MAT/manifest and post-hoc verification. Keep source facts, adopted model assumptions, converted conductivity and independently calculated references distinct. If the source PDF cannot be visually checked in an environment, record that uncompleted check.
2. **Evidence decision first:** obtain a true SHA-pinned native candidate and checking receipt, or define and independently review a *separate, explicitly lower-trust historical post-hoc diagnostic class* with the original failed workflow status visible. The latter must not masquerade as `checks_passed` in the original runner. Refuse to publish an S1 case until the selected provenance path can be enforced and independently audited. Any new native build/launch needs a separately bounded plan/authorization; no automatic OMC job.
3. **Generic mode, not apparatus switch:** design a versioned **steady** observation bundle distinct from untouched transient `native_case/1`. Strictly bind every temperature/power field to the actual native output channel and the physical node/rod owner. For ownerless junctions only use a recorded rod-end temperature. Reject missing output, inaccurate source hashes, wrong port orientation, absent/ambiguous algebraic result, and any claimed native qualification not supported by its provenance.
4. **Presentation:** the same reusable network renderer must show hot/cold boundaries, a massless intermediate junction, two oriented conductors, temperature K (optionally converted to °C for display), signed rod W and boundary-supply W. In **steady** mode remove/disable time slider, playback, reversal and temperature-history plots; show steady quantities and a truthful `steady algebraic solution; no physical time history` notice. Do not interpolate, add thermal storage, invent junction shape, or infer rod geometry from schematic lengths.
5. **Import/compatibility:** if full original steady MAT/CSV is offered, authenticate the exact saved native bytes, decode parameter aliases and evaluation endpoints with the established generic adapter, and present an algebraic state rather than an invented time series. Preserve import epochs, refusal clearing and ownership hardening from Review 02. Keep the three original transient case bundles byte-identical and green.

Independent reference calculation (never fed into the native bundle): `A=pi*(0.02)^2/4`, `kCu=0.092*4184`, `kSteel=0.011*4184`, `R_i=L_i/(k_i*A)`; `Q=(373.15-273.15)/(Rcu+Rsteel)` ≈ **1.0792824946508015 W**, `Tjunction=373.15-Q*Rcu` ≈ **366.45628803245436 K**. Check both rod orientation signs, hot-supply +W, cold-absorption −W and junction flow balance. These are **analytical reference predictions**, not a new native result or substitute for archived channels.

## Acceptance, reviews and stop points

- Complete the physical source audit, select an honest native-evidence/provenance policy, and record any necessary one-shot native budget **before** running OpenModelica. No solver/library/numerical-tolerance/source-PDF edits.
- Unit tests: strict steady schema positives with **clearly synthetic test-only values**, malformed source/mode, port ownership, fake junction, inconsistent native checkpoint, forged timestamp/time history, and preserved v1 transient schema and complete original digests. Never ship a synthetic S1 as native data.
- Browser tests: real desktop/mobile Chromium switching between steady and each existing transient network; no stale values after refusal/case switch/late import; no false steady time controls; keyboard selection and unit signs. Preserve failed attempts.
- Prepare a fully implemented source branch, pass exact-commit CI, open **draft PR**, publish a central `review_sandbox/projects/sim_heat/pr-<number>/` packet and short ready-to-paste Chat B prompt. Classify as **R2** because evidence and physical-observation meanings change. Request bounded independent review before owner merge.
- **Current work boundary:** source/evidence triage and offline readiness tests only. No new OMC build/launch, no claimed fourth native viewer case, no merge. If S1 native provenance is insufficient, report that gap and stop that pathway rather than filling it with analytic values.

Teacher-facing objective: inspect why a two-material series conductor has a non-midpoint junction temperature and a common steady transfer rate. This is a **textbook-to-viewer integration** demonstration, **not** an unfamiliar-author C1 transfer claim.
