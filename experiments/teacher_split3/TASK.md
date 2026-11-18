# Teacher Split-3 — independent source-authoring exercise (not a textbook case)

This is an explicitly **illustrative, developer-authored** investigation within the existing restricted H1 heat-conduction domain; it is not a held-out/blind authoring trial or an independently verified physical experiment.

Construct a transient thermal network with three finite uniform-temperature bodies (`copper`, `steel`, `aluminum`), two maintained-temperature boundaries (`sourceHot`, `sourceCold`) and seven storage-free conducting rods. Include a direct copper–aluminum shortcut and a separate steel-to-cold two-rod branch meeting at an ownerless ideal junction. Use both area-defined and circular-geometry rods. All physical numbers below are illustrative exercise inputs, not textbook givens or measured values.

| Component | Model type | Authored inputs (SI) |
|---|---|---|
| sourceHot | FixedTemperature | T = 354.15 K |
| sourceCold | FixedTemperature | T = 287.15 K |
| copper | Body | m=0.4 kg, c=385 J/(kg K), T_initial=299.15 K |
| steel | Body | m=0.9 kg, c=490 J/(kg K), T_initial=311.15 K |
| aluminum | Body | m=0.7 kg, c=900 J/(kg K), T_initial=291.15 K |
| feed | RodCircular | k=390 W/(m K), L=0.21 m, d=0.012 m |
| rodCS | RodArea | k=44, L=0.36, A=0.00016 m2 |
| rodSA | RodCircular | k=56, L=0.29, d=0.008 m |
| drain | RodArea | k=200, L=0.18, A=0.00015 m2 |
| shortcut | RodArea | k=160, L=0.42, A=0.00011 m2 |
| jLeft | RodArea | k=80, L=0.12, A=0.00014 m2 |
| jRight | RodCircular | k=25, L=0.2, d=0.009 m |

Connections: sourceHot → feed → copper → rodCS → steel → rodSA → aluminum → drain → sourceCold; copper → shortcut → aluminum; steel → jLeft → (ownerless ideal junction) → jRight → sourceCold. The arrows here mean authored port orientation, **not** computed power direction or motion.

Request only the source-expectations for `steel.port` temperature, `shortcut` heatFlow, `aluminum` energyChange, and the `copper.port`–`sourceCold.port` temperatureDifference. Explore a 0..1000 second declared transient grid of 1000 equal intervals under the existing admitted H1 settings. Do not execute a solver or infer predicted temperatures, powers, equilibrium, branch directions or computed sample histories from this task.

Acceptance for this bounded exercise: H1 admits the source without modifying its general parser/topology; the preview transparently shows only authored facts, connection topology, request units and **not_computed** statuses. A bad target, altered hash, missing attribution, or unsupported input must refuse. No original archived bundles or frozen C1 source may change. Real native results require a separately reviewed and explicitly owner-authorized execution plan.
