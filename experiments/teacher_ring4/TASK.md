# TEACH_RING4 — teacher-authored conduction-ring investigation

**Task selection/capture:** 2026-11-16, before producing model.mo or study.json. This is a developer-authored teacher-style **illustrative extension** of the constant-property, lumped-body conduction mechanism from Illustration 135 (source PDF pages 9–10), **not** a literal textbook problem, given, diagram or answer. Not the reserved independent H1-C1 author transfer.

## Fixed natural-language problem

Four internally uniform bodies A, B, C and D have distinct masses, specific heats and initial temperatures. Conducting, storage-free rods form a **closed ring A–B–C–D–A**, plus a **diagonal A–C rod**. A sixth rod connects a maintained-temperature hot reservoir to A. Bodies are otherwise thermally insulated; no matter/work exchange, convection, radiation, rod storage, contact resistance or external geometric pose. Constant parameters. Inspect native time histories for body temperatures (K), each body’s relative stored-energy change (J), and all six signed rod currents (W; port_a → port_b). Ask which, if any, currents reverse and why. No author-computed intermediate physics is supplied.

### Authoritative physical inputs

| Component | mass kg | specific heat J/(kg K) | initial T K |
| --- | ---: | ---: | ---: |
| A | 1.0 | 500.0 | 303.15 |
| B | 1.5 | 600.0 | 323.15 |
| C | 1.2 | 600.0 | 288.15 |
| D | 2.0 | 550.0 | 313.15 |

Maintained hot reservoir **353.15 K**.

| Rod ID | Authored orientation | k W/(m K) | L m | area m² |
| --- | --- | ---: | ---: | ---: |
| bathToA | reservoir → A | 120.0 | 0.40 | 0.001 |
| ringAB | A → B | 80.0 | 0.50 | 0.001 |
| ringBC | B → C | 100.0 | 0.50 | 0.001 |
| ringCD | C → D | 90.0 | 0.45 | 0.001 |
| ringDA | D → A | 70.0 | 0.50 | 0.001 |
| diagonalAC | A → C | 120.0 | 0.50 | 0.001 |

**Physical topology is authoritative; diagram layout is not geometry.** The letter A in a rod’s area column denotes cross-sectional area and not body A.

## Study and teaching questions

Observe body A/B/C/D port temperatures, all six rod `heatFlow` quantities, body A/B/C/D `energyChange`, and `temperatureDifference` between A and B (K). User chooses native recorded times, not interpolated states. Show whether a fifth supported topology can be loaded via case data alone in the same generic viewer.

Provisional transient analysis (to be pinned before execution): **0–24000 physical seconds, 2000 intervals, DASSL, tolerance 1e-8**. An independently prepared reference checks native evidence but does not supply model inputs.

## What this does and does not test

This is a **four-body, one-boundary loop with an A–C chord**, structurally distinct from D1/D2 and the 2-body/two-boundary DEV_BRIDGE. Only existing `SimHeat.Body`, `SimHeat.RodArea`, and `SimHeat.FixedTemperature` plus ordinary `connect` clauses are authorized. No engine/viewer special case, symbolic or inverse solver, physical shape inference, qualification upgrade, invented material properties, or native status fabrication. It is **development-exposed, not blind/independent C1**. Keep H1-C1-F0 untouched.

## Stop policy

Preserve this task and the first authored model/study even if refused. Do not silently tune physical inputs or analysis tolerances to obtain favorable results. One native build and one launch maximum under a separately pinned, no-retry plan; no unattended native CI on main. Native evidence remains `diagnostic_only`, `nativeQualified=false`. Independent R2 review and separate owner approval required before production merge.
