# When does the wall stop carrying 120 W?

Two insulated vessels exchange heat only through a composite wall. The hot vessel contains a substance freezing at 333.15 K. The cold vessel contains ice and water at 273.15 K. Both start with solid and liquid present. Assume uniform bath temperatures, constant properties, ideal contacts and a wall with negligible heat capacity.

| Given | Hot vessel | Cold vessel |
|---|---:|---:|
| Initial solid | 0.10 kg | 0.50 kg |
| Initial liquid | 0.45 kg | 0.10 kg |
| Specific latent heat | 200 kJ/kg | 334 kJ/kg |
| Specific heat after the available phase is exhausted | Solid, 2,000 J/(kg K) | Liquid, 4,200 J/(kg K) |

The facing has conductance 4 W/K. Beyond it, a strip (1 W/K) and an insert (3 W/K) run in parallel to the cold vessel. The insert's positive direction points from the cold vessel toward the facing. [Wall geometry](../studies/composite_wall/model.mo)

**Predict before calculating.** Which vessel first runs out of a phase? How much ice has melted at 1,000 s? At that instant, what would a heat-flow sensor on the insert read?

### First phase change

The parallel pair has conductance 4 W/K. Adding its resistance in series with the facing gives an overall conductance of 2 W/K. While both vessels contain both phases, the temperature difference stays at 60 K and the wall carries **120 W**.

The hot liquid can release 0.45 × 200 = 90 kJ by freezing. Melting all the ice would require 0.50 × 334 = 167 kJ. The hot liquid therefore freezes completely first, at **750 s**. At that moment 90/334 ≈ 0.2695 kg of ice has melted.

### From 750 to 1,000 seconds

The cold vessel still contains ice. The entire 0.55 kg of hot solid now cools with a heat capacity of 1,100 J/K. Write ΔT for its temperature above 273.15 K. Energy conservation gives 1,100 dΔT/dt = −2 ΔT. Over the next 250 s the difference falls to 60 exp(−250/550) ≈ 38.084 K.

The hot solid loses a further 1,100 × (60 − 38.084) ≈ 24.107 kJ. The total transfer is **114.107 kJ**, enough to melt **0.34164 kg of ice**. Including the original water, the cold vessel now contains 0.44164 kg of liquid. Since the total energy is below 167 kJ, holding the cold vessel at its melting point throughout this calculation was consistent.

At 1,000 s the facing carries 76.168 W toward the cold vessel. The parallel pieces divide that rate in the ratio 1 to 3, so the strip reads +19.042 W and the reversed insert reads **−57.126 W**. The same split applies to cumulative heat because the conductances are constant. The insert has carried 85.581 kJ toward the cold vessel over the full interval.

### Run the investigation

Run the offline command from the repository root with the project's [pinned checking dependencies](../requirements-h1-ci.txt).

~~~sh
python -B -m tools.coupled_phase_baths --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --left-bath hot 333.15 200000 0.1 0.45 --right-bath cold 273.15 334000 0.5 0.1 --duration-s 1000 --equilibrium-cp 2000 4200 --track-rod-flows
~~~

Read `firstExhaustingPorts` and `firstExhaustionTimeBoundsS` for the first event. Under `stateAtDuration`, read the bath temperatures and phase masses at 1,000 s, then compare the rods' `heatFlowBoundsW` and `transferredHeatBoundsJ`. Each pair gives lower and upper endpoints as exact rational strings. The top-level `baths` ledger ends at the first depletion.

### Change one given

Reduce the initial ice mass to **0.20 kg**, keeping the initial water mass at 0.10 kg. Predict which phase runs out first and whether the hot vessel will still be at 333.15 K at 1,000 s.

~~~sh
python -B -m tools.coupled_phase_baths --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --left-bath hot 333.15 200000 0.1 0.45 --right-bath cold 273.15 334000 0.2 0.1 --duration-s 1000 --equilibrium-cp 2000 4200 --track-rod-flows
~~~

Melting the ice now takes 66.8 kJ, so the ice vanishes after **556.67 s**. The resulting 0.30 kg of water starts warming while the hot liquid continues to freeze. Once all the hot liquid freezes, both temperatures change. At 1,000 s the calculation gives **321.718 K** in the hot vessel and **301.543 K** in the cold one. Check the common energy transfer from each side. The donor releases 90 kJ plus sensible cooling, and the receiver absorbs 66.8 kJ plus sensible warming. Each gives about **102.575 kJ**.
