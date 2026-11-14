# H0 - Compositional heat-transfer foundation

**Record:** H0-20261114-01  
**Status:** User-approved design direction; independent review pending. Documentation only.  
**Decision source:** The user's reply `approved` to the H0 design in the project conversation on 2026-11-14.  
**Repository baseline:** `physicsvigilante/sim_heat` at `49a2cc42462b47026e86313bfeff39a9b17081cd`.

This record preserves the approved direction. It is not an independent review or a simulation acceptance record. The H1 experiment is a proposal; implementation, execution, installations, and merging to `main` are separate decisions. Publication of these documents does not activate a capability.

## 1. Product objective and authority

Build a reusable physical model, not a catalogue of textbook-specific solvers. Within an admitted physical regime, a new arrangement of supported components is an authoring task. A genuinely new law or regime can justify a reusable extension.

The authority chain is source evidence and explicit interpretation -> authored physical composition using reviewed laws -> backend execution -> verified results -> educational presentation. The authored composition determines which components and conditions apply. The physical library owns the law meanings. An independent reference calculation is verification evidence, not a second production engine.

The LLM identifies entities, connections, source facts, assumptions, and investigations. The engine performs supported parameter conversions, assembly, equation solving, observations, and checks. The viewer consumes result identities and qualified geometry; it does not derive a private cooling model.

A model is a reusable, versioned object. Preserve the source baseline when changing physical properties, initial conditions, boundaries, or supported connections. Record teacher-authored revisions separately. A new scenario is not the same as an input changing during one time trajectory.

## 2. Initial physical scope

Support two distinct investigation modes using compatible component meanings:

- **Steady conduction:** no represented part accumulates energy; solve junction temperatures and signed heat flows.
- **Lumped thermal dynamics:** internally uniform bodies store energy and change temperature over physical time.

The initial candidate components are:

| Author-facing concept | Authored facts | Responsibility and assumptions |
| --- | --- | --- |
| Finite thermal body | Mass, specific heat, explicit physical initial temperature for a transient | One uniform temperature; positive constant heat capacity; owns its stored-energy change |
| Uniform conducting rod | Conductivity, length, cross-sectional geometry, endpoints | Positive constant conductance; no thermal storage; no lateral heat loss in this initial model |
| Fixed-temperature boundary | Maintained temperature | Supplies or absorbs the necessary heat while maintaining that temperature |

An ideal connection junction has no added mass, storage, or geometry. Do not invent a material body merely to represent a connection.

Thin project-owned wrappers may calculate `C = m*c`, `G = k*A/L`, and supported geometric conversions. The author should supply physical facts rather than precomputed capacities, conductances, junction temperatures, or decay constants. Equivalent alternative parameterizations require an explicit authoring rule rather than contradictory duplicate inputs.

The candidate standard components are `Modelica.Thermal.HeatTransfer.Components.HeatCapacitor`, `ThermalConductor`, and `Modelica.Thermal.HeatTransfer.Sources.FixedTemperature`. Their documented semantics support the intended starting abstractions: uniform constant-capacity storage, storage-free heat transport, and a fixed Kelvin boundary [M1-M3]. Their existence does not qualify our wrappers or execution workflow. The documentation version below is a reference, not an approved runtime pin.

## 3. Physical meanings

Use SI internally and preserve source units and conversion conventions. Absolute temperatures use Kelvin; a Celsius input and a temperature increment are different concepts. Heat flow is power in watts, while accumulated heat and stored-energy changes are in joules.

Use the standard thermal-port convention: temperature at a port and heat-flow rate positive into its component [M4]. The project-facing oriented rod flow is defined by

`Qdot_a_to_b = G * (T_a - T_b)`.

Negative flow means the direction is from `b` to `a`; it is not a physical failure. Components sharing an ideal junction share its temperature and balance their incident heat flows. Opposite ends of a finite conductor are not forced to have equal temperatures.

A body owns its energy storage once. Report a change relative to the initial state, `DeltaU = C*(T - T_initial)`, rather than inventing an absolute energy reference. Internal heat exchanges cancel in the balance for the combined system.

For a transient, require an explicit physical initial temperature for every body. Do not turn standard-library start defaults or numerical guesses into source givens [M1]. Steady-state initialization is not a substitute for an authored transient initial state.

Initially, material properties and boundary temperatures are constant during a run. Insulation is the absence of an external heat exchange in the admitted model, not a small invented conductance. A closed transient collection of finite bodies need not have a fixed-temperature boundary. By contrast, each independent steady conductor-only network being solved needs a temperature reference to determine absolute temperatures. These closure requirements follow the proposed balance equations; detailed admission rules remain a pre-H1 review item.

## 4. Authoring, experiments, and requests

Start with **restricted Modelica composition**, not a general-purpose JSON-to-physics compiler. Admit approved components, physical parameter bindings, typed connections, explicit initialization, and registered observations. Arbitrary algorithms, external functions, imports, or case-authored replacement laws are outside the initial authoring contract.

These restrictions are a design intention, not an implemented security guarantee. Their exact enforcement and the execution containment plan must be reviewed before accepting authored models or running them.

The Modelica composition is the authoritative physical description. Source notes and display metadata reference stable instance identities instead of repeating physical values as another executable model. A future compact authoring adapter requires evidence of a concrete authoring burden; it is not part of H1 by default.

| Responsibility | Examples | Must not do |
| --- | --- | --- |
| Physical composition | Bodies, rods, materials, topology, boundary relationships | Include source-number dispatch or answer formulas |
| Experiment definition | Selected initial conditions, physical duration, solver settings, output times | Confuse physical conditions with numerical guesses or display interpolation |
| Passive observations | Temperature, flow, temperature difference, stored-energy change | Add a physical constraint merely to request a value |
| Inverse analysis | Determine an unknown parameter from measurements | Be represented as a passive display request; it is deferred |

Each physical value or condition has one authoritative location even when experiment selection activates it. An implementation must settle the exact file and annotation layout before code; this record does not create a second editable physics representation.

Initial observations should cover body/junction temperatures, oriented conductor flow, temperature differences, and stored-energy changes. Resolve referenced objects and complete observation names before native execution. Expose requested quantities that fail, are missing, or are unsupported; do not silently drop them. Necessary internal dependencies need not become extra public requests.

Symbolic and inverse solving remain deferred. An analytic verification formula is not an implemented symbolic service. A numerical binding of a symbolic source does not complete its symbolic request.

## 5. Source fidelity

Preserve the literal source, including its discrepancies. Distinguish statement givens, diagram facts, worked-solution assumptions, adopted modeling assumptions, conversion conventions, selected numerical examples, derived quantities, and missing information.

See [SOURCE_COVERAGE.md](SOURCE_COVERAGE.md) for the preliminary map and the two starting issues identified in Illustrations 123 and 135. The PDF remains unchanged. Do not use a printed solution as the only numerical oracle.

## 6. Bounded experiment and verification

The proposed H1 experiment uses Illustration 123 for steady conduction, Illustration 134 for one-body heating, and Illustration 135 for isolated two-body equilibration. The latter two need explicitly identified numerical demonstration bindings. A composition challenge is selected only after the production interfaces and checks are frozen.

Verification compares intermediate histories as well as endpoints, independent reference relationships, energy balances, signs, initial conditions, and supported limiting cases. Fix tolerances and comparison times before execution. Compare solver accuracy and output sampling separately. A successful compiler exit is not a physics verdict.

A three-body branching arrangement already discussed in chat is development-exposed. It may be a structural test but cannot be relabeled blind. Document a challenge author's exposure and preserve a failed frozen attempt if production repairs become necessary. See [H1_PLAN.md](H1_PLAN.md).

## 7. Educational exploration and presentation

The first proposed teacher investigation changes the connecting rod's conductivity in the isolated two-body model while preserving the bodies and their initial state. The model predicts a changed equilibration rate but the same energy-determined equilibrium temperature. Demonstrate this with separately identified, verified scenario runs; do not assume executable reuse or instant slider responsiveness.

An initial presentation can be a network schematic, temperature and flow histories, and an energy-balance summary. Schematics must disclose unspecified geometry. A storage-free rod does not support an animated transient diffusion front [M2]. Plot interpolation is presentation, not new simulated evidence. A full interactive viewer remains separate work.

Report five independent dimensions: interpretation fidelity; physical/numerical correctness; simulation coverage; educational usefulness; textbook-answer completeness. A requested observation is not answered merely because another part of the simulation is useful. Actual teacher-task evidence must remain distinct from predicted usefulness.

## 8. Compatibility with NEW_THERM

Keep separate repositories initially and align physical meanings, not all code structures. Evaluate small utilities for reuse; do not copy or refactor the reference project or alter its retained evidence.

The inspected reference is `physicsvigilante/new_therm` at `1f547e70cbda8532e71d5fdb8d425aad70fa5f5a`. Its `native_runner/runner.py` builds with `startTime=0`, `stopTime=1`, `numberOfIntervals=1`, and validates host-specific Windows/runtime identities [N1]. This is evidence against assuming that runner can be adopted unchanged for configurable thermal time histories. A new thermal execution path must explicitly qualify duration, sampling, numerical controls, time-series reading, and retained diagnostics.

Future gas or piston coupling requires compatible time-dependent energy and mechanical models. A shared compiler does not establish that compatibility. No current `new_therm` qualification is inherited here.

## 9. Review and stop conditions

This document set records user-approved direction, not an independent review. A reviewer should evaluate component assumptions, source fidelity, closure, authoring restrictions, observation semantics, verification independence, challenge exposure, and execution requirements. An author self-check must not be called independent review.

Before H1 implementation, settle the remaining items in [H1_PLAN.md](H1_PLAN.md), record the review disposition, and obtain separate implementation authorization. Before native execution, approve its exact plan. No implementation, installation, native run, browser capture, CI activation, or merge is authorized by this record.

## References

Primary source: `../01_heat.pdf`, repository blob `18755813329b21f5e2ac432b2a5aebfe6dc21a60`; exact identity and locators are recorded in [SOURCE_COVERAGE.md](SOURCE_COVERAGE.md).

[M1] Modelica Standard Library 4.0.0, `HeatCapacitor`: https://doc.modelica.org/Modelica%204.0.0/Resources/helpWSM/Modelica/Modelica.Thermal.HeatTransfer.Components.HeatCapacitor.html

[M2] Modelica Standard Library 4.0.0, `ThermalConductor`: https://doc.modelica.org/Modelica%204.0.0/Resources/helpWSM/Modelica/Modelica.Thermal.HeatTransfer.Components.ThermalConductor.html

[M3] Modelica Standard Library 4.0.0, `FixedTemperature`: https://doc.modelica.org/Modelica%204.0.0/Resources/helpWSM/Modelica/Modelica.Thermal.HeatTransfer.Sources.FixedTemperature.html

[M4] Modelica Standard Library 4.0.0, thermal interfaces: https://doc.modelica.org/Modelica%204.0.0/Resources/helpDymola/Modelica_Thermal_HeatTransfer_Interfaces.html

[N1] Inspected NEW_THERM runner: https://github.com/physicsvigilante/new_therm/blob/1f547e70cbda8532e71d5fdb8d425aad70fa5f5a/native_runner/runner.py
