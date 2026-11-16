**C1 AUTHOR STAGE 1 — TASK.md, first submission**

The following is the **original, first-submission `TASK.md`**. It is fixed by this issue comment before any `model.mo` or `study.json` is authored.

---

# TASK.md — Two-buffer parallel thermal bridge with opposing initial and boundary gradients

## 1. Teaching scenario and purpose

Two small, internally uniform, thermally insulated solid buffers, `leftBuffer` and `rightBuffer`, exchange heat through **two separate conducting rods connected in parallel**. The left buffer is also coupled to an ideal hot-temperature bath through a third rod; the right buffer is coupled to an ideal cold-temperature bath through a fourth rod.

Initially the **right** buffer is warmer than the **left** buffer, even though the left end of the apparatus is attached to the hotter bath. The class will explore how the two buffer temperatures evolve, how the heat-transfer directions through both parallel bridges change, and how the rods divide the inter-buffer heat current.

This is an original illustrative teaching problem, not a transcription of a textbook problem. **Transient** analysis is required. Do not prescribe any solved temperatures, heat flows, capacities, conductances, time constants, or switching times as authoring inputs.

## 2. Complete physical data

All quantities below are chosen illustrative values and are given directly in SI units. Temperatures are absolute Kelvin values. Heat is transported only by the four specified rods.

### Thermal bodies (uniform-temperature finite stores)

| Name | Mass `m` (kg) | Specific heat `c` (J/(kg·K)) | Initial temperature `T_initial` (K) |
| --- | ---: | ---: | ---: |
| `leftBuffer` | 0.25 | 500 | 293.15 |
| `rightBuffer` | 0.30 | 600 | 333.15 |

### Ideal fixed-temperature baths

| Name | Fixed temperature `T` (K) |
| --- | ---: |
| `hotBath` | 363.15 |
| `coldBath` | 283.15 |

### Four massless, constant-property conducting rods

| Name | Physical form | Conductivity `k` (W/(m·K)) | Length `L` (m) | Cross-sectional input | Port-a end | Port-b end |
| --- | --- | ---: | ---: | --- | --- | --- |
| `hotLead` | `RodArea` | 150 | 0.10 | Area `A = 0.00030 m²` | `hotBath` | `leftBuffer` |
| `flatBridge` | `RodArea` | 200 | 0.10 | Area `A = 0.00050 m²` | `leftBuffer` | `rightBuffer` |
| `roundBridge` | `RodCircular` | 50 | 0.050 | **Diameter** `d = 0.020 m` | `leftBuffer` | `rightBuffer` |
| `coldLead` | `RodArea` | 100 | 0.10 | Area `A = 0.00040 m²` | `rightBuffer` | `coldBath` |

The specified diameter is not a radius; the circular area is to be derived from the diameter by the supported physical component. The two bridge rods are distinct conducting paths; no added contact resistance or junction heat capacity is intended.

## 3. Exact thermal topology and rod orientation

Four ideal thermal nodes, with **no other connections**:

- **H (hot terminal):** `hotBath.port` ↔ `hotLead.port_a`.
- **L (left buffer):** `hotLead.port_b`, `leftBuffer.port`, `flatBridge.port_a`, and `roundBridge.port_a` share one ideal node.
- **R (right buffer):** `flatBridge.port_b`, `roundBridge.port_b`, `rightBuffer.port`, and `coldLead.port_a` share one ideal node.
- **C (cold terminal):** `coldLead.port_b` ↔ `coldBath.port`.

Schematic (parallel paths are separate physical rods):

```text
hotBath -- hotLead -- [leftBuffer] -- flatBridge  -- [rightBuffer] -- coldLead -- coldBath
                              \-- roundBridge --/
```

The bracketed buffers represent finite, initialized thermal bodies at nodes L and R; the middle two rods each independently connect L to R. Both ends of each rod are connected explicitly. No ideal node contains more than one body or boundary; no body is directly clamped to a bath. There are no unconnected conductors or boundaries.

## 4. Physics and assumptions

1. Each buffer is perfectly mixed/isothermal internally, has the constant mass and specific heat given above, and stores sensible thermal energy. Both buffers begin at their explicitly specified initial temperatures.
2. Each rod conducts according to the supported constant-property, storage-free thermal conduction idealization. Its two ends may have different temperatures. There is no heat storage in the rods.
3. The baths hold their specified temperatures throughout the transient regardless of exchanged heat.
4. All four rods and their ideal port junctions are the **only** paths for energy exchange. Every remaining buffer surface is insulated. There is no convection, radiation, phase change, mass transfer, mechanical work, internal heat generation, or ambient leakage.
5. Contacts, port connections, and branching at a buffer port are ideal, with no additional temperature drop or junction capacitance. Geometry and material properties stay constant; the numerical values are illustrative, not claimed measurements of specific materials.
6. No external controller, switch, dynamic change in conductivity, or forcing beyond the two fixed-temperature baths is imposed. No extra equation or derived physical parameter is to be supplied by the task author.

## 5. Requested observations

Observe the continuous **transient** response, including the initial condition, the approach to long-term behavior, and any inter-buffer temperature equality and consequent heat-flow sign change. A **provisional** classroom plotting window is 0–1800 s; the evaluator may choose the C1 modal horizon and output resolution before execution without changing the physical task. The request is for observable curves, not computed answers supplied in advance.

Base observation set, expressed only in supported public quantities:

1. Temperature (K) at `leftBuffer.port` versus time.
2. Temperature (K) at `rightBuffer.port` versus time.
3. Heat flow (W) in `hotLead`, positive from `hotBath` toward `leftBuffer`.
4. Heat flow (W) in `flatBridge`, positive from `leftBuffer` toward `rightBuffer`.
5. Heat flow (W) in `roundBridge`, positive from `leftBuffer` toward `rightBuffer`.
6. Heat flow (W) in `coldLead`, positive from `rightBuffer` toward `coldBath`.
7. Temperature difference (K), `T(leftBuffer.port) - T(rightBuffer.port)`.
8. Energy change (J) of `leftBuffer` relative to its own initial state.
9. Energy change (J) of `rightBuffer` relative to its own initial state.

The crossing/reversal question is to be explored from the requested temperature-difference and signed-flow curves; **do not add** a non-public event-detection, interpolation, ratio, or integral request. No pre-solved trajectory or numerical answer key is part of this task.

## 6. Teaching questions

**Core question:** The right buffer starts hotter than the left buffer, while the left buffer is attached to the hotter bath and the right buffer to the colder bath. What happens to the direction of conduction through *each* of the two parallel inter-buffer rods as the system evolves? Explain using the temperature-difference and signed-heat-flow plots, rather than assuming that heat always moves left-to-right.

**Comparison question:** Why do two rods between the same buffer nodes have the same endpoint temperature difference but need not carry the same heat flow? Compare their flow magnitudes and signs over time, and connect the observations to their different geometries and thermal conductivities.

**Energy-accounting question:** How do the two bodies' energy changes relate qualitatively to heat entering and leaving them through the specified connections? What would students look for as the system approaches its long-term regime?

## 7. Structural-transfer rationale and scope

The distinctive graph is **two finite-capacity body nodes, two separate fixed-temperature terminal nodes, two distinct parallel rods between the same two body nodes, and one terminal lead at each body**. The parallel rods form a two-edge loop, while the two baths supply an end-to-end driving gradient. This is not merely a renamed or numerically altered isolated two-body link; it is not the exposed symmetric three-body triangle, discussed three-body branch, massless-middle-junction path, or boundary-only three-spoke junction.

The transfer claim is limited to being structurally different from the **exclusion/exposure list in the frozen `START_HERE.md`**, not a claim to have audited all prior implementations or examples. This task relies only on the publicly stated support for bodies, baths, area/circular rods, shared ideal nodes, parallel links, and transient observation.

## 8. Provenance and freeze

All masses, specific heats, initial and fixed temperatures, conductivities, lengths, areas, diameters, apparatus descriptions, and connection choices above are **illustrative choices authored for this C1 teaching problem**; no textbook source is claimed. The lumped, insulated, fixed-property, storage-free-rod physical regime is an **adopted assumption**, stated explicitly above. SI units are used throughout. The task is frozen at this first issue-comment submission; a later refusal must not lead to silent physical-task replacement.

---

### Stage-1 authorship, prior-exposure and assistance disclosure

- **Author/selector:** ChatGPT, self-identified as GPT-6. The **same LLM selected and wrote** this task. There was no separate independent selector, and this is not a claim of authenticated model identity or independent/blind task selection.
- **Prior exposure:** The conversation context available to me contains summaries of earlier SIM_HEAT H1 discussions, including a request to review H1 readiness and PR #1/#2. Consequently I **cannot claim to be entirely unexposed to SIM_HEAT's earlier design/review activity**. I did not open or reread those conversations for this attempt, do not assert that I previously performed an implementation role, and have not treated that context as a solved case. I am acting as an author rather than an implementation developer or reviewer here.
- **Documents read in this attempt:** Only `qualification/h1_c1/START_HERE.md` and `qualification/h1_c1/AUTHOR_CONTRACT.md` at frozen commit `ea954eee9b416498874419b9c8e5503f94821be8`. No implementation, tests, solved examples, other repository files, or issue discussions were inspected.
- **Tools/assistance:** Connected GitHub file-reading and issue-comment posting tools only. No additional LLM, evaluator, validator, code reviewer, OpenModelica execution, calculation tool, hashing service, or simulation was used. All physical choices and text are generated by this author.
- **Stage boundary:** This is **Stage 1 only**. No `model.mo` or `study.json` has been authored or submitted, and no engine changes or execution are requested. Stop after recording this task.
