# Developer-authored investigation: two-reservoir thermal bridge

Task identity: DEV-BRIDGE-1. Selected on 2026-11-15 **after** the H1-C1-F0 freeze, as a **developer-authored diagnostic**. This is NOT the separately authored H1-C1 challenge, and its author has already seen the engine and example layouts. The H1-C1 task remains unselected.

## Physical teaching question

A thermal system has two well-mixed finite bodies, each coupled by conduction to both a maintained hot reservoir and a maintained cold reservoir. A fifth storage-free rod connects the two finite bodies. The hot and cold reservoirs are independent maintained temperatures. Investigate whether the direction of cross-link heat flow can change during the transient, how the body temperatures evolve, and how energy supplied/removed by the reservoirs balances the bodies' stored-energy changes.

This is a five-conductor thermal bridge with two finite storage nodes and two maintained-temperature nodes. It differs structurally from the exposed one-body/reservoir, isolated two-body link, three-body triangle/branch, two-body single-junction path, and boundary-only three-spoke cases. The new structure combines **two boundaries and two finite bodies in two interlinked paths**, with two conductor loops. The case is chosen as an implementation-aware probe, not blind transfer.

## Physical facts (all illustrative SI values; no textbook givens)

- Hot reservoir `heated`: maintained at 353.15 K (80 °C).
- Cold reservoir `cooled`: maintained at 283.15 K (10 °C).
- Finite body `left`: mass 1.3 kg, specific heat capacity 520 J/(kg K), initial temperature 298.15 K (25 °C).
- Finite body `right`: mass 1.8 kg, specific heat capacity 680 J/(kg K), initial temperature 328.15 K (55 °C).
- All rods are storage-free with constant stated SI properties and area 0.001 m²:
  - `supplyLeft`: hot reservoir → left body; k=80 W/(m K), L=0.4 m.
  - `supplyRight`: hot reservoir → right body; k=40 W/(m K), L=0.5 m.
  - `rejectLeft`: left body → cold reservoir; k=60 W/(m K), L=0.5 m.
  - `rejectRight`: right body → cold reservoir; k=100 W/(m K), L=0.5 m.
  - `bridge`: left body → right body; k=120 W/(m K), L=0.6 m.
- Explicit ideal-port connections create four nodes: `heated`, `left`, `right`, `cooled`. Each storage node has exactly one body; each boundary node has one maintained temperature. Every conductor has exactly two connected ends.
- No convection, radiation, work, phase change, contact resistance, external body leakage, or extra junction heat capacity is represented.

## Intended passive observations

- `left.port` and `right.port` temperatures as physical-time histories.
- `bridge` heat flow in the declared left-to-right orientation (a negative value is legitimate).
- Temperature difference `left.port - right.port`.
- Both bodies' stored-energy changes (relative to their stated initial temperatures).

The question about flow reversal is exploratory, not a pre-specified solved answer or an imposed equation. Do not alter physical parameters after inspecting numerical results just to manufacture a desired reversal.

## Planned bounds and assessment

Provisional analysis only: start 0 s, stop 20000 s, 2000 equal output intervals, DASSL tolerance 1e-8. An independent reference and numerical-domain check will determine whether the time span is appropriate before any native attempt. The task is fixed before `model.mo`, descriptor, reference or solver output; model authorship and any assistance must remain disclosed.

For this stage, admit the new model with the **unchanged frozen** parser and public request rules. If admitted, separately generate a reference specification, run offline validation and record any refusal. Do not alter the physical component library, parser, native runner, MAT decoder, checker, reference policy, tolerances, or the C1 freeze. No cloud simulation, compiler launch, installation, merge, or production repair is authorized by this task record.
