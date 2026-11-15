# H2-01 — bounded explorable thermal-network viewer

**2026-11-15. Classification R1 with focused independent review because signed physical results/evidence are displayed.** Source baseline: `main` after owner-approved H2-00 merge `ecebc38dd3f6eaffd297bd3df97a0883e591c6ac`.

## Physical and teaching task

Display the existing developer-authored two-body/two-fixed-reservoir/five-rod bridge, without modifying physical equations or running a new solver. Teacher can select only recorded samples on a time slider, play them, inspect body temperatures in **K**, heat flow in **W** (positive rod port_a → port_b), stored-energy changes in **J** and maintained-boundary instantaneous heat supply in **W**. The native saved signs bracket cross-link reversal between **1720 and 1730 s**. Connections are a **logical topology**, not inferred geometry or dimensions. Chart lines connect recorded marks graphically but do not create calculated intermediate states.

## Provenance, authority, and refusals

- Original native workflow: https://github.com/physicsvigilante/sim_heat/actions/runs/43699424883 ; executed commit `b3779603563db4b26aeef8c2dd552965698deb4f`; artifact 14155084346, original ZIP SHA-256 `f16975a25eea79f61f7819fb9e704ab04a33630044a51a0d062b8399c1c9ce38`; raw MAT SHA-256 `e1da06d7223dd271317881b2d737b73c40ec643a8d533568bf7ef3bfbb5443a9`.
- One historical model build/launch, 42/42 required exports, 98/98 diagnostics pass. The original `nativeQualified=false` and `diagnostic_only` status is explicitly preserved; source evidence is **native solver output, not independently authenticated physical measurement**. The historically misleading MATv4 v1 sidecar field is not reused.
- The bundled 23-sample JSON preview contains copied values at every 1000 s plus 1720/1730 s, with source run and original CSV hash. Browser computes a Git blob digest against an embedded pin before display. Every displayed value comes from an actually saved sample. Preview selection is not an independent reference oracle.
- The teacher may import *only* the exact native `case_01/normalized.csv` whose SHA-256 is `4b1a822680c03742e3031f5be653b48e7dd736613be355796862de483c0e39fe`. The parser validates 2002 original data rows, mandatory channels, 2001 increasing canonical times at 10 s intervals and the identical duplicate terminal row. No missing-value fabrication, interpolation, arbitrary CSV interpretation or server upload.
- Body ΔU sums are display arithmetic only, not independent energy-balance certification; reservoir W and body J are never added.
- Existing Modelica library, parser/study, reference, verification, numerical tolerance, MAT adapter, native runner, archived historical evidence and H1-C1 freeze are untouched.

## Gate before independent review

Finish Node data/negative tests and real headless Chromium desktop/mobile smoke, including keyboard slider, signed arrows and stale-file SHA rejection. Capture CI logs, screenshot, dependency versions and exact commit SHA. Run current H1 offline and analytical tests; **no OpenModelica installation/native build**. Once the final draft PR has green CI, publish a central `review_sandbox/projects/sim_heat/pr-<number>/` packet and short user-ready reviewer prompt. Chat B independently checks pinned UI, evidence interpretation and failure states, and writes a new report there. Owner separately approves any merge; verify exact post-merge CI and central record.

## Explicit exclusions

No arbitrary thermal-network visualization framework yet, model authoring or editing UI, new physical simulation, additional law, external geometry/pose, inverse/symbolic solver, automatic energy integration, independent native qualification, broad charter transfer, blind C1, teacher effectiveness or classroom deployment. R1 only applies while data and evidence semantics remain unchanged; escalate to R2 for numerical, physics, provenance or qualification changes.