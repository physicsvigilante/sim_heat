# `sim_heat` Architecture Record (v2)

> **Status:** Authoritative baseline architecture record (post-M02 / PRs #202–#203, merged at `07a10fb`).
> Changes to this record require reviewed commits, and milestone contracts/packets cite it by exact commit SHA.

- **Policy binding:** Any milestone contract that departs from a convention or invariant recorded here must explicitly declare the departure and the owner authority that approved it.
- **Accepted architectural direction:**
  - Unify at the **physical representation, state, and result layer** across specialized certified Python engines—not via a monolithic universal solver.
  - Keep **thermal physics** (conduction, sensible storage, latent phase change, convective/radiative boundaries, radial shells, calorimetry) as the primary focus.
  - Keep **OpenModelica** strictly as an optional independent cross-check requiring separate owner authorization.
  - Settle the **M03 authoring format (D2)** via the read-only three-assembly authoring comparison before freezing `CONTRACT-M03.md`.
- **Subsystems:** Ownership, agent participation, and reasoning strengths are controlled explicitly by the owner (currently Neon as primary coordinator; Opus excluded):
  - `core` — exact-rational interval kernel, `step_matrix`, graph assembly (planned neutral re-export at `simheat/core` in M03)
  - `laws` — terminal conductance laws and validated derived laws (joins, shell eliminations)
  - `steady` — `multiport` steady thermal network solver
  - `transient` — `multibody` / `staged` / enthalpy-mode transient solvers
  - `authoring` — shared system description and H1 adapter
  - `presentation` — viewer and thin interactive lessons

---

## 1. Authoritative Physical & Numerical Conventions

- **Units:** SI throughout; all temperatures are absolute kelvin (`K`).
  - Nonnegative scalar inputs (temperatures, masses, areas, heat capacities, durations, resistances) use unsigned SI decimal strings per `decimal_input` rules.
  - Inherently signed quantities (conductivity temperature slope $\alpha$, signed measured phase conversion, prebuilt off-diagonal conductances, future oriented heat sources/sinks) use signed decimals with explicit per-field semantics.
  - Certified outputs are exact rational endpoint strings representing `exact_rational_closed_enclosure`.
- **Sign conventions:** Every power or energy carries an explicit owner and sign convention—never renamed to a generic "heat flow":
  - rod `Q_flow`: positive from port `a` to port `b`;
  - terminal supply: positive into the conduction network (H1);
  - reservoir, body, or phase-bath inflow: positive into that owner;
  - exterior outflow: positive outward to the environment.
  - Any conversion between sign conventions must be explicit.
- **Network and derived laws:** A storage-free conduction subnetwork reduces to a symmetric, zero-row-sum, passive terminal conductance law (Schur/Kron reduction). Derived laws (network joins, shell eliminations) record their child identities and the reduction operation applied, and must be able to pass cleanly between existing engines without problem-specific glue code or loss of physical meaning.
- **Thermal state:** A phase-capable node carries enthalpy $H$ measured relative to pure solid at $T_{\text{tr}}$. $T(H)$ is piecewise linear: sensible solid below $0$, isothermal coexistence plateau at $T_{\text{tr}}$ over $[0, mL]$, and sensible liquid above $mL$. A sensible body is the zero-latent-heat case. A maintained reservoir is a boundary prescription with its own energy ledger—not an infinite heat capacity.
- **Steady vs. transient separation:** Steady and transient solves are distinct operations over the same physical description. $C = 0$ and $t \to \infty$ are not interchangeable and must not be conflated.

---

## 2. Soundness & M02-Established Engine Invariants

- **Certified containment invariant:** Every certified output encloses the exact solution of the stated model for every *admitted realization* in the input parameter box up to the modeled stop.
  - If an event sequence is unresolved, the solver must either enclose the outcomes of all admissible sequences or stop with an explicit status.
  - Uncertainty about an event time never makes enclosing the physical state optional.
  - Matrix exponential scaling refuses when the interval matrix's maximum absolute row sum exceeds $2^{31}$.
- **Termination semantics:** Per [`PROJECT_POLICY.md`](PROJECT_POLICY.md) §3, target canonical outcomes are `converged`, `sweep_limit`, `refinement_budget`, `mode_sequence_uncertain`, and `unsupported_regime`.
  - *As implemented in M02 (`bca7273`, PR #202):*
    - `multiport`: `solverMetadata.terminationReason` $\in$ `{converged, sweep_limit, exact_linear}`, with `maxTemperatureWidthK` and `maxHeatRateWidthW`.
    - `multibody`: `solverMetadata.terminationReason` $\in$ `{resolved, refinement_budget}`, with `pruneRefinementsUsed`, `bisectRefinementsUsed`, and `modeledDurationWidthS`.
  - M03's shared result envelope reconciles these vocabularies without breaking existing backend entry points.
- **Fast-path gating (M02 EH-01, `bca7273`):** An exact or closed-form shortcut is admitted only when **every** input it consumes is a point value. For `multiport` `exact_linear`, this requires point values across every entry of `w_net` (including edges between two fixed ports), every attachment area, $\varepsilon = 0$, and no `radial_shell`. Otherwise the certified interval method runs.
- **Event bracketing (M02 F-01, `bca7273`):** Certified first-crossing brackets start only from a proved-safe point. Certification helpers verify `before(lo)` themselves unless the caller passes a documented `lo_proved_safe=True` with the proof justified at the call site.
- **Stop-state enclosure (M02 F-03, `bca7273`):**
  - When exhaustion is certified: union over remaining unsafe cells plus `state_at(cert_hi)`.
  - When exhaustion is not certified: union over remaining unsafe cells plus `state_at(duration)`.
- **Pure-phase bath admission (M02 F-04, `bca7273`):** Pure phases are admitted in `latent_heat_bath`, `multiport_thermal_network`, and `multibody_phase_network` via direction-aware regimes (a)–(d):
  - Leaving coexistence at $t = 0$ yields `exhausted` with `exhaustedAtStart: true` over $[0, 0]$.
  - An unresolved initial departure yields the conservative `exhaustion_time_uncertain` starting from $0$.
  - Legacy `body_phase_bath_exchange` continues refusing pure phases by design (`multibody` supersedes it).
- **Pin-safe Windows admission & line endings (M02 follow-up, `b2ea46c` / `07a10fb`, PR #203):**
  - `h1/study.py` normalizes its internally derived relative path via `.as_posix()` (provably identical on POSIX; authored backslash strings remain refused).
  - `tools/verify_n1_plan_maintenance.py` attests historical `h1/study.py` at `f52613c` against pin `0205d016…`, stages exact historical bytes for N1 plan checks and 51 staged N1 tests, and enforces the exact authorized one-line live delta.
  - `.gitattributes` explicitly pins live-hashed files (13 added rules plus existing entries) to `text eol=lf`.
- **Honest offline evidence flags:** Offline results report `nativeExecuted`, `nativeQualified`, `independentlyCertifiedReference`, and `runnerConsumable` as `false` and are never silently promoted.

---

## 3. Durable Decisions, Rejected Alternatives, and Historical Dissent

- **D-1 (Accepted):** Unify at the physical description, state, and result layer; keep specialized certified backends behind it. *Rejected:* a monolithic enthalpy-hybrid universal solver (loses closed-form precision, requires nonlinear DAE integration, carries high migration risk).
- **D-2 (Accepted):** Linear sequential enthalpy-mode switching is in scope for M04. Coupled nonlinear radiating transients are deferred until a certified cooperative integrator is justified and authorized.
- **D-3 (Accepted):** Certified Python engines are the primary solver; OpenModelica is an optional independent cross-check under separate owner authorization. *Rejected:* an immediate parallel native OpenModelica demonstration.
- **D-4 (Open — to be resolved via read-only 3-assembly authoring comparison before freezing `CONTRACT-M03.md`):**
  - Evaluate candidate representations (declarative offline `ThermalSystem` with H1 adapter vs. extended SimHeat Modelica grammar with generated facts) on:
    1. physical composability;
    2. LLM authorability;
    3. extensibility;
    4. absence of duplicated physical information;
    5. ability to derive governing equations directly from the authored system.
  - Do not implement two competing systems. Whichever representation is chosen must present one clean representation at the solver boundary, honestly describe the solved system, and eliminate hand-duplicated `facts.json`.
- **Historical M01 dissent (preserved for record):** During M01 assessment, participants differed on whether F-02 was classified as a confirmed defect vs. architectural limitation plus reporting defect (D3), whether F-08 was P2 vs. P3 if raw calls become internal (D4), and whether F-04/F-05 were defects vs. architectural limitations. M02 subsequently resolved F-02 and F-04; F-05 and F-08 are scheduled for M03 consolidation.

---

## 4. Contract & Milestone Index

| Milestone | Scope | Reviewed Head | Merge Commit (`main`) | Status |
|---|---|---|---|---|
| **M02** (PR #202) | Correctness batch: F-01 (P1), F-02–F-04, F-07, F-09, F-10 | `bca7273f71477d0ba7fee6ef4143fdf99f959111` | `f37422399672479d083ddb6e1085afafe54615db` | **Merged & Verified** |
| **M02 Follow-up** (PR #203) | F-06 Windows nested-path + bounded N1 exemption + A-05b `.gitattributes` | `b2ea46c8094ef3daddc077de5c0ea8348ff46d54` | `07a10fb2824538e88297072d6c714f063b299c6a` | **Merged & Verified** |
| **M03** (planned) | Physical composability & consolidation (`ThermalSystem`, validated `DerivedLaw`, F-05/F-08, `simheat/core`, Windows CI) | — | — | **Pending D2 comparison & `CONTRACT-M03.md`** |
