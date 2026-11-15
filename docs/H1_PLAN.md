# H1 - Bounded thermal-network feasibility experiment

**Status:** Proposed experiment under the user-approved H0 direction. Independent review, implementation authorization, and native-execution authorization remain pending.  
**Record date:** 2026-11-14.

This is not an executable run plan and does not approve a host, installation, build budget, numerical settings, or code changes. It turns the H0 recommendation into reviewable experiment requirements without claiming results.

## 1. Question and success claim

Can an LLM author, inspect, and revise different arrangements of three reviewed thermal concepts using the same production component library, assembly/validation path, execution interface, and result extraction?

A positive result would demonstrate composability within the tested scope. It would not establish general thermal networks, arbitrary Modelica authoring, arbitrary graph solvability, a symbolic service, or automatic coupling to `new_therm`.

## 2. Scope

Admit positive constant thermal capacities, positive constant conducting links, maintained-temperature boundaries, and explicit transient initial conditions. Rods have no storage or lateral exchange. Bodies are internally uniform. Use restricted Modelica composition and evaluate the standard components identified in [H0_FOUNDATION.md](H0_FOUNDATION.md).

Steady conduction and actual-time lumped dynamics are different modes. Require temperature references for the initial steady conductor-only networks; do not add artificial reservoirs to closed transient body networks. Admit only topology and initialization classes covered by the reviewed rules.

Out of scope: convection, radiation, phase-change dynamics, gas/piston mechanics, spatially resolved diffusion, changing boundary inputs during a run, general inverse/symbolic solving, a universal graph/compiler framework, arbitrary authored code, and a full interactive viewer. Numerical demonstration instances of symbolic sources are allowed only with explicit labels.

## 3. Development cases and challenge

| Case | Source / selection | What it tests |
| --- | --- | --- |
| H1-S1 | Illustration 123; PDF page 2 | Two rods in series; junction temperature; oriented heat flows; steady junction balance and unit conversion |
| H1-D1 | Illustration 134; PDF page 9 | One finite body and one reservoir; initial condition; temperature/flow histories and body energy gain |
| H1-D2 | Illustration 135; PDF pages 9-10 | Two isolated bodies; both histories; temperature difference; total-energy conservation |
| H1-C1 | Select after production baseline fixation | A distinct admitted arrangement using the same components, with no production-code repair |

These are scenario requirements, not a count or authorization of native commands. A later execution plan must allocate builds, launches, accuracy checks, revisions, limits, and failure handling explicitly.

Resolve the source issues in [SOURCE_COVERAGE.md](SOURCE_COVERAGE.md) through documented interpretations, not by editing the PDF. Do not select final numeric bindings for symbolic cases without recording their illustrative origin and physical domain.

## 4. Challenge discipline

Freeze the physical library, admitted authoring syntax, validator, runner interface, extractor, public observation definitions, and applicable generic checkers before selecting H1-C1. Record the frozen revision and file identities.

The actual challenge must be selected by a separate author or reviewer, with disclosed access to code, source examples, and results. The already discussed three-body branching network is exposed; it cannot be presented as blind evidence.

Permitted challenge additions are case composition, requests, provenance, and independently prepared reference data under the frozen interfaces. A need to change shared physics, validation, execution, extraction, checker logic, or presentation code invalidates the original no-repair claim. Preserve the failed attempt; a repaired successor needs a new identity and qualification decision.

Do not prescribe the actual topology or numerical values in advance in this document.

## 5. Independent references

The following are analytical checks for the adopted idealizations, not implementation formulas or executed results. Derive and review them independently of production code. The source contains related derivations at the locators above; source discrepancies remain separately recorded.

### H1-S1

For rod resistances `R1 = L1/(k1*A1)` and `R2 = L2/(k2*A2)`:

`Qdot = (Th - Tc)/(R1 + R2)`  
`Tjunction = Th - Qdot*R1`.

Check each rod's signed flow and the junction balance. State units and the calorie convention explicitly. The author supplies material and geometry facts, not these solved values.

### H1-D1

With `C = m*c`, `G = k*A/L`, maintained reservoir temperature `Tr`, and physical initial body temperature `Ti`:

`T(t) = Tr + (Ti - Tr)*exp(-G*t/C)`  
`Qdot_reservoir_to_body(t) = G*(Tr - T(t))`  
`DeltaU(t) = C*(T(t) - Ti)`.

Compare the whole selected time history, including `t=0`. Independently integrate boundary heat flow with the declared sign convention and compare it with the body's stored-energy change. Account for the integration method's own resolution.

### H1-D2

With `C1 = m1*s1`, `C2 = m2*s2`, and `G = k*A/L`:

`DeltaT(t) = (T1_initial - T2_initial)*exp(-G*(1/C1 + 1/C2)*t)`  
`T_equilibrium = (C1*T1_initial + C2*T2_initial)/(C1 + C2)`  
`C1*(T1(t) - T1_initial) + C2*(T2(t) - T2_initial) = 0`.

Independently reconstruct/check both temperatures and oriented rod flow, not just their difference or a late-time endpoint. Finite-time results must not be falsely labeled the exact asymptotic equilibrium.

### H1-C1

Construct an independent reference from the network's energy balances using a method selected before execution. It must not import the production library or merely reuse its calculated answer. Record the reference's method, assumptions, numerical error assessment, and review.

## 6. Numerical evidence and edge cases

Before execution, fix physical time spans, comparison times, solver settings, output sampling, units, and absolute/relative tolerances. Near-zero quantities need an absolute tolerance. Assess solver accuracy separately from output spacing. Budget any tighter-tolerance or sampling checks in the approved run plan rather than performing undeclared retries.

Test equal initial body temperatures (zero exchange), reversed ordering (reversed signed flow), and an isolated finite body (constant temperature under this model). Check initial-state satisfaction and finite, physically admissible outputs. Record whether each test has static, analytical, or native evidence; do not label an unexecuted path native-tested.

Proposed refusal cases include invalid physical parameters, incomplete initial conditions, malformed or incompatible connections, floating steady networks, unknown object identities, and unsupported observations. Specify the exact admission class and failure outcomes before implementation. A successful parse or equation count does not by itself prove uniqueness.

A complete native result bundle must identify the authored model, library/compiler versions, experiment, origin of physical data, requested quantities and their statuses, raw outputs, diagnostics, and verification outcomes. Preserve failed runs and limitations.

## 7. Teacher investigation

Using the isolated two-body model, change rod conductivity while keeping both bodies and their initial conditions unchanged. Preserve the baseline and label the revision hypothetical. Independently check the prediction of a changed equilibration rate with unchanged energy-determined equilibrium temperature.

A network schematic, temperature/flow plots, and energy-balance summary are sufficient for the first presentation concept. A storage-free rod cannot display a simulated diffusion front. Do not claim educational usefulness from attractive graphics alone; record the teacher task and what was actually demonstrated. A full viewer is not required to begin numerical qualification and is not authorized here.

## 8. Acceptance and rejection

Accept only the scope evidenced by all of the following:

- Development cases pass reviewed independent checks on initial, intermediate, and later results, signs, and energy balance under predeclared tolerances.
- Physical inputs, source assumptions, unit conversions, and demonstration bindings remain traceable; the LLM supplies no unverified intermediate answers.
- H1-C1 uses the frozen production interfaces and requires no production repair, with exposure disclosed.
- Requests are validated completely, and unsupported or failed outcomes are not hidden by an overall success label.
- A separately identified scenario revision supports the chosen teacher investigation without changing physical laws or inventing geometry.

Reject or narrow the claim when cases need apparatus-specific dispatch, manual intermediate physics from the LLM, invented data, private viewer calculations, post hoc tolerance changes, or production changes after challenge fixation. Compiler success alone is not acceptance. Unexpected runtime cost or excessive authoring burden is evidence to reconsider implementation choices, not something to hide behind a pass.

Report interpretation fidelity, physical/numerical correctness, simulation coverage, educational usefulness, and textbook-answer completeness separately.

## 9. Remaining prerequisites

Before implementation, resolve and review:

1. Exact component/wrapper API, supported geometry inputs, stable identities, restricted authoring syntax, and where experiment/observation metadata lives without duplicating physical authority.
2. Admitted topology and initialization rules, including how ideal junctions, direct storage connections, and contradictory initial constraints are treated.
3. Numerical bindings and domain, the Illustration 123 unit convention, and explicit source interpretations.
4. Independent reference methods, complete requested observations, comparison schedules, and tolerances.
5. Minimum execution/reader design and what, if anything, can be reused from the inspected `new_therm` implementation.

Before native execution, additionally fix the host, OpenModelica and Modelica Standard Library versions, dependencies, commands, solver settings, duration, outputs, resource and build/run limits, containment, and failure/cleanup policy. The H0 session did not establish a qualified native runtime. An executable absent from one session's PATH does not establish the state of the user's PC.

## 10. Review and stop point

A separate reviewer must examine the proposed interpretation, physical laws, reference calculations, model/observation distinction, challenge protocol, and execution obligations. Review findings and their dispositions must be retained; an author self-check is not independent review.

Stop at documentation. Record the H0 review outcome before requesting a separate H1 implementation decision. Native execution has its own approved plan. No automatic continuation, source edits, `new_therm` refactor, installation, CI activation, or main-branch merge follows from this proposal.
