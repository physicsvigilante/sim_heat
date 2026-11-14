# H0 technical review notes and proposed dispositions

**Record:** H0-REVIEW-NOTES-20261115-01  
**Reviewed revision:** `19c9583aebcab2827e25f8b79682d75bb1200594`  
**Author:** ChatGPT, in the same project conversation that authored H0.  
**Status:** Author technical review and independent-review handoff. NOT an independent approval, an H1 implementation contract, or native qualification.

The user approved continuing the review after H0 publication. This record adds findings and proposed dispositions without replacing the four original documents or changing the PDF. The approval is not treated as permission to merge, implement H1, install tools, activate CI, or run OpenModelica.

## 1. Evidence examined and limits

Reread [README](../README.md), [H0 foundation](H0_FOUNDATION.md), [source coverage](SOURCE_COVERAGE.md), and [H1 plan](H1_PLAN.md). Their locally inspected bytes match the GitHub blob identities below. Re-rendered and visually inspected PDF pages 2, 9, and 10 (printed 2.89, 2.96, and 2.97). This is a focused review of the initial cases, not a new audit of all 23 pages.

| Original file | Git blob SHA-1 |
| --- | --- |
| `README.md` | `86a7b3e910165fcd2aca456cb0611e46ecd3aaf1` |
| `docs/H0_FOUNDATION.md` | `0305fe4054cc4849388cf2d8b905d4689ac870d2` |
| `docs/SOURCE_COVERAGE.md` | `47346f8f16ed91eb2ad6dee8de57baa4ad323d83` |
| `docs/H1_PLAN.md` | `c7b60163fc0255a14ed50e91f86611a1fc9573dd` |
| `01_heat.pdf` | `18755813329b21f5e2ac432b2a5aebfe6dc21a60` |

Also inspected the Modelica Standard Library 4.0.0 documentation, its actual `HeatCapacitor.mo` source, and Modelica Language Specification 3.6 initialization rules [M1-M5]. These are reference versions, not selected runtime versions. No `new_therm` code was changed or requalified. No project test suite, native compilation, simulation, installation, or browser capture ran. The numerical check below is standalone reference arithmetic, not a simulation.

PR #1 had no submitted reviews when this review began. No separate reviewing agent or reviewer has been obtained. A second pass by this author does not satisfy the independent-review gate in H1_PLAN section 10. This record must not be used to claim that gate passed.

## 2. Overall assessment

**Recommendation:** retain the three-concept foundation and the existing bounded experiment. No rewrite, extra physics backend, general graph compiler, or full viewer is justified by these findings.

The approved H0 direction is a design foundation, not a complete implementation specification. The findings below distinguish corrections to factual assumptions from proposed qualification boundaries and still-unsettled H1 details. None is a failure of implemented SIM_HEAT software: there is no implementation at the reviewed revision.

## 3. Findings and proposed dispositions

### R1 - Initialization must follow the actual library source, not the documentation narrative

**Evidence.** The referenced 4.0.0 HeatCapacitor documentation describes a 25 degC default and a `steadyStateStart` parameter [M1]. The actual component at the `v4.0.0` tag declares `T(start=293.15, displayUnit="degC")`; its declarations contain no `steadyStateStart` parameter and no corresponding conditional initial equation [M2]. The documentation embedded in that same source repeats the conflicting narrative. This is a directly inspected documentation/code mismatch, not evidence about every library version.

The earlier conversation's assertion that this component offers that steady-state option was therefore too broad. The core equations still express uniform constant-capacity storage. The correction concerns initialization/API assumptions, not the decision to use the standard thermal library.

**Proposed disposition.** Inspect and pin the exact library files selected for H1. Give each admitted independent body state exactly one explicit physical initial condition. A reviewed wrapper can use `T(start=T_initial, fixed=true)` or an equivalent explicit initial equation, but must not add both redundantly. Modelica distinguishes required initial values from guesses through `fixed`; a start value alone does not establish the intended constraint [M3]. Do not rely on a compiler choosing missing initialization equations or on an undocumented parameter. H1's steady conductor-only case needs no fictitious heat-capacity component or long settling transient.

**Closure evidence:** reviewed wrapper initialization, refusal of missing initial temperatures, and native evidence that the authored initial state is satisfied. Source inspection is done; implementation and native evidence remain pending.

### R2 - Define connection-node admission and solvability separately from apparatus names

**Proposed first boundary.** Treat connected ideal thermal ports as one node. Permit at most one finite body OR one maintained-temperature boundary at such a node; permit storage-free junctions with neither. Link nodes through finite positive conductances. Preserve the port sign convention and do not treat `HeatPort_a` and `HeatPort_b` as causal input/output types: the documented distinction between those port classes is their icon [M4].

For steady conductor-only networks, require each connected component to reach a fixed-temperature boundary. For transient networks, require an explicit initial temperature for every body, and require each connected algebraic-junction subnetwork to reach a body node or fixed boundary. An isolated initialized body remains admissible and has constant temperature under the adopted model. Do not add an artificial reservoir.

Directly connected multiple bodies, a body directly clamped by a boundary, or multiple boundaries on one ideal node are outside this conservative first admission class. Compatible examples can be physically meaningful; reject them as outside the admitted topology, not automatically as physically impossible. Detect contradictory values as contradictions when established. Do not silently merge bodies or discard initial conditions. A conductor whose two ends collapse to the same node should initially receive an explicit unsupported-connection diagnostic rather than silent deletion.

**Analytical rationale, not qualification:** for positive conductances, the steady unknown-node balance matrix is a weighted graph Laplacian with prescribed-temperature nodes removed. Its quadratic form is a sum of positive conductance-weighted squared differences, including links to prescribed nodes. If every unknown component reaches a prescribed node, its nullspace is trivial. In the transient case, algebraic junctions can similarly be determined from current body/boundary temperatures; positive body capacities then define a linear evolution from supplied initial states. This gives a structural uniqueness argument for the proposed idealization, but not a conditioning guarantee or native proof for every graph.

**Closure evidence:** exact admission rules, finite resource limits, positive parameter checks, valid zero-flow cases, and refusal examples. Branches, loops, and repeated elements must be handled according to those rules, not problem numbers; evidence claims remain bounded by what is actually tested.

### R3 - Keep one physical authority while allowing source-given aggregate properties

The H0 wording against requiring precomputed C or G should not be interpreted as forbidding a source from giving heat capacity or conductance directly. The standard component documentation explicitly accommodates measured aggregate values [M1, M5].

**Proposed disposition.** For the three initial cases, retain the planned mass/specific-heat and rod-material/geometry inputs. Compute capacity, area, and conductance within reviewed components. Do not add new parameterization forms merely for future coverage. When a later source supplies C or G directly, either admit a separately defined and tested direct-input form or clearly report the current interface limitation. Never invent mass, dimensions, or a material property to satisfy a wrapper.

Keep physical values and physical initial conditions in the authored Modelica model or one selected model parameter binding. Experiment metadata supplies run controls and references that binding; it does not repeat editable temperatures or material values. Requests and provenance reference stable physical identities.

**Closure evidence:** the H1 contract specifies a single authoritative location for each input and rules for redundant alternative inputs; a scenario revision preserves its baseline and labels hypothetical values.

### R4 - Make the restricted authoring and observation surfaces explicit before code

H0_FOUNDATION section 4 is an intention, not an implemented parser or security boundary.

**Proposed disposition.** Specify an allowlist for component declarations, scalar parameter bindings and supported conversions, port connections, observation references, and inert provenance annotations. Reject arbitrary case equations, algorithms, external functions, imports, redeclarations, file access, and compiler-affecting annotations outside that contract. A restriction on authored syntax does not replace process/resource containment. Do not build a universal parser or a second editable physics schema to solve this.

Validate the complete observation name, owner, operands, units, and admitted operation before execution. Keep native dependencies distinct from public requests. In particular, H1-D1's energy check needs boundary heat-flow history even when the teacher asks only for body temperature. That internal requirement must not force a dummy public request. Define whether a reported quantity is native or a verified mathematical derivative of native results. The viewer computes neither temperature evolution nor a private energy model.

**Closure evidence:** concrete permitted/rejected examples, exact public quantity definitions, invalid-object and invalid-operation refusals, and a model inspected under different passive requests without adding physical constraints. This finding does not authorize a new implementation.

### R5 - Preserve source discrepancies and finish the numerical contract before execution

**Source checks completed.** Page 2 confirms the conductivities for Illustration 123 are in kilocalorie-based units while the worked heat-flow result is labeled J/s. Using the printed parameters and circular area, standalone arithmetic from the series balance gives:

- junction temperature `46000/493 = 93.30628803245436 degC`;
- heat rate `(253/3081250)*pi = 0.0002579547071345128 kcal/s`.

The heat rate in watts is that last value multiplied by an explicitly adopted `J_per_kcal`. No calorie convention is selected by this review. The result checks the registered unit discrepancy; it does not silently replace the source answer or qualify H1-S1.

Pages 9-10 confirm that Illustration 135's final printed exponential uses `m1*s2`, while the preceding balances use `m1*s1`. The H1 reference follows those balances; retain the printed discrepancy. Illustration 134 explicitly neglects rod capacity. For 135, uniform body temperature, negligible rod storage, and absence of other external exchanges remain adopted/solution-supported assumptions, not all literal statement givens.

**Analytical reference assessment.** The H1-D1 exponential satisfies `C*dT/dt = G*(Tr-T)` with its stated initial temperature. The H1-D2 difference law satisfies `d(DeltaT)/dt = -G*(1/C1+1/C2)*DeltaT`; combining it with energy conservation determines the two temperatures. These are checks of mathematical relationships under the adopted assumptions, not an independent implementation, a symbolic-solver capability, or native evidence.

**Proposed disposition.** Before implementation acceptance, finalize input domains, source conventions, labeled numerical bindings, comparison schedules, units, and absolute/relative tolerances. Before native execution, bind these to the actual solver and output settings. Energy-integral checks need their own quadrature error allowance. Record finite-time samples separately from asymptotic equilibrium. Do not choose tolerances after observing a discrepancy.

The post-freeze challenge still requires separate selection and reference preparation with exposure disclosed. None of the proposed topology examples here is a newly blind challenge.

### R6 - Separate review, implementation, and runtime gates without adding bureaucracy

**Proposed disposition.** Resolve R1-R5 in one concise H1 implementation contract rather than proliferating apparatus profiles or repeating the architecture study. Preserve this record and the original documents; adopted changes should be prospective and explicit.

A named independent reviewer must still assess the source interpretations, initialization, node restrictions, authoring contract, reference calculations, and challenge discipline. A later user decision can accept or amend that review disposition; the current author must not manufacture an independent PASS.

Host/toolchain selection remains a native-execution prerequisite. Select and inspect one OpenModelica and Modelica Standard Library installation, along with the required reader/runtime and containment. The reference documentation's version is not a runtime pin, and NEW_THERM's acceptance does not transfer. No host has been qualified by this record.

## 4. Independent-review handoff

Review the four original documents at `19c9583aebcab2827e25f8b79682d75bb1200594` and this additive note. State reviewer identity/context and any prior exposure. Reopen the PDF pages and the cited library source rather than relying only on this author's summary. Assess whether R1-R6 are supported, whether their proposed dispositions are sufficient and proportional, and which items block an H1 contract, implementation, or native execution. Return a verdict with concrete findings, evidence locators, and unresolved items. Do not modify the PDF, implement code, install software, run native jobs, merge, or select the post-freeze challenge during this review.

A separate fresh-context review is different from this author's self-check; it still must disclose its actual scope and limitations. No review has been requested from an invented GitHub identity, and no completed independent review is claimed.

## 5. Current stop point

Author technical findings and proposed dispositions are recorded. Original H0 direction remains user-approved; independent review remains pending. H1 is not implemented or natively qualified. The documentation branch remains the publication target; `main` must not be changed by this step.

## References

Primary teaching source: [01_heat.pdf](../01_heat.pdf), original blob recorded above, focused pages 2, 9, and 10. Statements about those pages are source observations; proposed restrictions, closure reasoning, and reference arithmetic are this author's analysis.

[M1] Modelica Standard Library 4.0.0 HeatCapacitor documentation: https://doc.modelica.org/Modelica%204.0.0/Resources/helpWSM/Modelica/Modelica.Thermal.HeatTransfer.Components.HeatCapacitor.html

[M2] Actual HeatCapacitor source at the v4.0.0 tag: https://github.com/modelica/ModelicaStandardLibrary/blob/v4.0.0/Modelica/Thermal/HeatTransfer/Components/HeatCapacitor.mo

[M3] Modelica Language Specification 3.6, section 8.6 initialization: https://specification.modelica.org/maint/3.6/equations.html#initialization

[M4] Modelica Standard Library 4.0.0 thermal interfaces: https://doc.modelica.org/Modelica%204.0.0/Resources/helpDymola/Modelica_Thermal_HeatTransfer_Interfaces.html

[M5] Modelica Standard Library 4.0.0 ThermalConductor documentation: https://doc.modelica.org/Modelica%204.0.0/Resources/helpWSM/Modelica/Modelica.Thermal.HeatTransfer.Components.ThermalConductor.html
