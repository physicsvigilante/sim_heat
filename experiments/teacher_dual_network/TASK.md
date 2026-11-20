# Teacher dual-network conduction experiment — fixed before authoring

**Capture:** 2026-11-20. This is a **developer-authored, explicitly illustrative and exposed** teaching challenge, not a held-out first attempt by an independent LLM, not a literal textbook problem or a certified source-fidelity result. It must never be counted as the unassisted H1-C1 trial.

## Classroom question

Two thermally **disconnected** experiments share one inspector canvas, not a physical connection:

- A reservoir-driven **parallel-path** conduction network. One path travels from maintained hot bath to a finite-temperature plate, then through **two distinct rods in series** to a maintained cold bath. The rods meet at an **ownerless, storage-free ideal junction**. An independent bypass rod connects the hot and cold baths in parallel with that entire path.
- A separate **insulated calorimetry pair**: two finite uniform-temperature bodies connected only to each other through one conducting rod. The isolated pair is not connected to either bath or the plate.

A teacher should be able to identify which system can exchange energy with maintained baths, which pair has conserved **total stored energy**, and how a rod's signed flow convention differs from an assumed graphical arrow. Do not claim the viewer supplies predicted trajectories or heat-flow directions; all public physical requests remain `not_computed` unless separately authorized native results are later obtained.

All physical numbers in this table are deliberately chosen **illustrative SI exercise inputs**, not measured/textbook givens or inferred materials. Do not silently adjust them to pass admission or a numerical check.

| ID | Existing H1 component | Explicit physical inputs (SI) |
| --- | --- | --- |
| bathHot | FixedTemperature | T = 353.15 K |
| bathCold | FixedTemperature | T = 288.15 K |
| plate | Body | m = 0.65 kg; c = 500 J/(kg K); T_initial = 308.15 K |
| left | Body | m = 0.20 kg; c = 900 J/(kg K); T_initial = 336.15 K |
| right | Body | m = 0.35 kg; c = 420 J/(kg K); T_initial = 296.15 K |
| hotFeed | RodCircular | k = 210 W/(m K); L = 0.30 m; d = 0.010 m |
| seriesOne | RodArea | k = 60 W/(m K); L = 0.50 m; A = 0.00030 m² |
| seriesTwo | RodCircular | k = 120 W/(m K); L = 0.25 m; d = 0.006 m |
| bypass | RodArea | k = 65 W/(m K); L = 0.50 m; A = 0.00015 m² |
| pairLink | RodCircular | k = 160 W/(m K); L = 0.28 m; d = 0.008 m |

Authored **port orientation**, not known power direction:

1. `bathHot.port → hotFeed.port_a → hotFeed.port_b → plate.port`;
2. `plate.port → seriesOne.port_a → seriesOne.port_b → (ideal junction) → seriesTwo.port_a → seriesTwo.port_b → bathCold.port`;
3. `bathHot.port → bypass.port_a → bypass.port_b → bathCold.port`;
4. `left.port → pairLink.port_a → pairLink.port_b → right.port`, fully separate from paths 1–3.

Use the exact four H1 constructors, ordinary `connect` statements, and no new physical law, custom Modelica source expressions or apparatus-specific renderer. For the transient study, declare 0 to 6000 s, 1200 intervals, `dassl`, tolerance `1e-8`. Request `temperature` at plate and both isolated bodies, `heatFlow` through bypass and pairLink, `energyChange` of plate and left, and an ordered `temperatureDifference` from left to right.

## Evidence to collect

Preserve a prospective `model.mo` and `study.json` as first submitted developer-authored data. Compute its model digest mechanically, check H1 admission and generic source preview without modifying any H1 code. Verify two disconnected network components, six ideal thermal nodes, one ownerless junction, five oriented rods, truthful illustrative provenance and all eight requested observations `not_computed`. Browser-check actual read-only loopback UI and refuse stale hash/bad request/replaced source. No imported JSON may inherit a historical native result. 

This test is **about composition and teachable source inspection only**. Offline analytical checks may assist a future controlled qualification; they are not OpenModelica results. The original six archived diagnostics stay untouched and `diagnostic_only/nativeQualified=false`. A new native run needs a separately reviewed bounded plan and explicit owner authorization; original seven static reference failures, eight native blockers and unsealed private scorer remain.
