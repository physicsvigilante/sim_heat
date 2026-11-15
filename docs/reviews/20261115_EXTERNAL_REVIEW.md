# **SIM_HEAT — Independent Technical Review**

PASS WITH CONDITIONS

**Recommendation: H1 is ready to begin bounded offline implementation, but is not ready for implementation acceptance, native numerical qualification, or merging.**

I reviewed [PR #1](https://github.com/physicsvigilante/sim_heat/pull/1?utm_source=chatgpt.com) and [PR #2](https://github.com/physicsvigilante/sim_heat/pull/2?utm_source=chatgpt.com) together, including the proposed H1 contract, physical components, example compositions, analytical tests, and relevant Modelica Standard Library v4.0.0 source.

The fundamental physical design is sound. I found **no demonstrated physics-law or connector-sign defect requiring an architectural redesign**. I did identify two weaknesses in the proposed numerical acceptance policy, along with several implementation and evidence gaps that must be closed before H1 can be qualified.

## **1. What passes the review**

The three-concept foundation is appropriate for the intended first capability:

| Area                      | Assessment                                                                     |
| ------------------------- | ------------------------------------------------------------------------------ |
| Physical laws             | PASS — correct constant-capacity storage and Fourier conduction approximations |
| Component reuse           | PASS — same underlying MSL components for all three examples                   |
| Connector semantics       | PASS at source level — signs agree with MSL conventions                        |
| Initialization design     | PASS at source level — explicitly fixed body initial temperature               |
| Composition strategy      | PASS — ports and connections, not textbook-specific dispatch                   |
| Single physical authority | PASS in contract design                                                        |
| Numerical verification    | CONDITIONS — acceptance scales need correction                                 |
| Restricted authoring      | Specified, but not implemented or tested                                       |
| Native execution          | Not qualified                                                                  |

### **Physical equations and Modelica implementation**

The wrapper code in [SimHeat.mo](https://github.com/physicsvigilante/sim_heat/blob/6f8b504e15c14e698fe81f1261a64a919e464f94/experiments/h1_spike/SimHeat.mo?utm_source=chatgpt.com) follows the intended equations:

\\[ C=mc,\qquad C\frac{dT}{dt}=Q\_{\mathrm{in}} \\]

\\[ G=\frac{kA}{L},\qquad Q\_{a\to b}=G(T_a-T_b) \\]

The body's `dU = C*(T-T_initial)` correctly represents an energy change, not an absolute internal energy.

I independently checked the actual MSL v4.0.0 source for `HeatCapacitor`, `ThermalConductor`, `Element1D`, `FixedTemperature`, and the heat-port definitions. The spike's sign conventions agree with those sources:

- `RodArea.Q_flow` is positive from `port_a` to `port_b`.
- `Body.Q_in` is positive when heat enters the body.
- `FixedTemperature.Q_to_network = -source.port.Q_flow` is positive when the boundary supplies heat.
- `HeatPort_a` and `HeatPort_b` are not directional input/output types.

The explicit initialization modifier `T(start=T_initial, fixed=true)` is also appropriate. The contract correctly avoids relying on the nonexistent `steadyStateStart` parameter in the inspected v4.0.0 implementation.

These are source-level conclusions. They are **not** claims of successful Modelica compilation.

## **2. Findings requiring correction**

| ID     | Severity / gate                                    | Finding and required correction                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------ | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1** | **Required before numerical qualification**        | The contract uses global temperature, conductance, and capacity scales for numerical tolerances. In heterogeneous or disconnected networks, one very large component can make errors in another component appear acceptable. Use per-connected-network temperature scales and per-observation flow/energy scales, derived independently before viewing native results. Apply corresponding local scales to conservation checks. |
| **F2** | **Required before numerical qualification**        | The timestamp matching allowance `1e-9*max(1 s,t_end)` can exceed the sample spacing for sufficiently short transient horizons. Cap matching tolerance below a fixed fraction of the minimum grid spacing, and define supported lower time/resolution bounds or explicit refusals.                                                                                                                                              |
| **F3** | **Required for offline implementation acceptance** | PR #2 supplies component prototypes and standalone analytical tests, but no restricted authoring validator, topology admission implementation, `study.json` cases, observation resolver, revision checker, or result decoder. Implement the contract's narrow surfaces and negative fixtures before treating it as an H1 candidate.                                                                                             |
| **F4** | **Required for physics verification**              | The reported four Python tests check reference arithmetic, not the Modelica components or their connections. Add independent signed-flow, initial-condition, junction-balance, and energy-ownership fixtures. Cross-check that independently specified reference inputs and topology match the authored cases without importing production-derived answers.                                                                     |
| **F5** | **Required before native execution**               | No exact runtime MSL/compiler pairing, successful Modelica translation, actual CSV export schema, or solver-output qualification exists. Pin and inspect the selected runtime, verify public output identities and sign conventions, and establish the contained execution plan before any native claim.                                                                                                                        |
| **F6** | **Required before contract freeze**                | Some general transient admission limits remain dependent on a later run plan, particularly supported `stopTime`, `intervals`, and numerical settings. Make the accepted domain and refusal rules deterministic before freezing the validator. Explicitly record the contract's post-freeze C1-selection exception to the referenced charter protocol before claiming charter compliance.                                        |

The principal technical concern is **F1**, because the proposed global error normalization could produce a false numerical PASS on a larger composed network. It does not invalidate the three initial analytical models, but it must be corrected before those tolerances become general acceptance rules.

F2 is similarly a bounded numerical-policy issue, not a reason to change the physical architecture.

## **3. Verification requirements for the first implementation**

The current analytical bindings provide useful, concrete checks.

| Case   | Independent expected behavior                                                                           |
| ------ | ------------------------------------------------------------------------------------------------------- |
| H1-S1  | Junction approximately 93.306288°C; both rods carry approximately +1.079282 W in the authored direction |
| H1-D1  | At \\(t=0\\), rod flow, body heat input, and reservoir supply are all +12 W                             |
| H1-D2  | At \\(t=0\\), rod flow is +12 W; hot-body input is −12 W and cold-body input is +12 W                   |
| H1-EQ  | Equal initial temperatures produce zero exchange                                                        |
| H1-REV | Reversed initial temperatures produce negative oriented rod flow                                        |
| H1-ISO | An isolated initialized body retains its temperature and zero energy change                             |

These checks should be complemented by the generic node law, rod conservation, and body energy balance rather than by adding apparatus-specific code.

The proposed independent conductance-matrix and matrix-exponential reference is appropriate for checking unfamiliar networks. Keep it **strictly a verification path**, not an alternative production solver. There is no reason to introduce a universal intermediate representation or second executable physical engine.

## **4. Complexity and optional improvements**

The Modelica component layer is not unnecessarily complicated. `RodCircular` reuses `RodArea`, which reuses the standard `ThermalConductor`. That is an acceptable thin abstraction and avoids duplicating Fourier's law.

The larger H1 contract is rigorous, but several responsibilities can be implemented incrementally without changing the architecture. Build the minimal library, constrained parser, and topology tests first; then add observation handling, scenario preservation, and reference verification. The complete native evidence and post-freeze challenge machinery can follow after offline qualification.

Three optional improvements are worth considering: use neutral identifiers such as `body1` and `body2` rather than `hot` and `cold` for scenarios that reverse temperatures; eventually make body heat input and boundary heat supply available as public observations, since the wrappers already expose them; and later support directly supplied heat capacities or conductances without inventing mass or geometry. **None should block H1's initial offline implementation.**

The conservative restriction permitting at most one storage body or fixed boundary at an ideal node is also defensible for H1. It excludes some physically meaningful combinations, but does so uniformly rather than through case-specific exceptions. Broader admission can wait until supported by tests.

## **5. Review limitations and evidence status**

This was a fresh read-only review of PR #1 at `8a285d401def5c1864405a8fb3258b66dde9ffe3` and PR #2 at `6f8b504e15c14e698fe81f1261a64a919e464f94`.

I independently inspected the Modelica reference sources, but could not re-render the original binary `01_heat.pdf` through the available GitHub access. The recorded Illustration 123 unit discrepancy and Illustration 135 subscript discrepancy therefore remain based on the repository's source-coverage record rather than a fresh visual examination by this reviewer. The original source should remain unchanged.

I did not independently rerun the reported Python tests. No Modelica compilation, simulation, installation, file modification, merge, or commit was performed. Neither PR has an existing submitted GitHub review.

## **6. Final disposition**

**H0 physical foundation**

PASS

**H1 contract for bounded offline work**

PASS WITH CONDITIONS

**PR #2 as an accepted H1 implementation**

Not accepted

**Native qualification and reusable H1 claim**

Not established

**Recommended next decision:** Authorize a narrowly scoped offline implementation using the existing physical architecture, with F1–F6 recorded as mandatory closure items at their respective gates. Begin by preserving the current spike as exploratory evidence, establishing the restricted authoring/validation path, and adding physical-sign and negative-case tests.

Do not merge either PR solely on this review, and do not promote PR #2's standalone reference tests to evidence of successful simulation.

The project is moving in the intended composable direction. The necessary corrections concern **verification boundaries and implementation completeness**, not the underlying choice of OpenModelica or the three physical component abstractions.