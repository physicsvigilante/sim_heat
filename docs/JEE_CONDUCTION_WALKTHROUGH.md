# Three conduction problems to solve with SIM_HEAT

Try each prediction on paper, then run the command from the repository root using Python 3.13.5 with the pinned checking dependencies. The commands run the offline reference engine. The long final argument identifies the exact checking inputs. The problems assume constant material properties, insulated lateral surfaces and ideal contacts. [Checking dependencies](../requirements-h1-ci.txt)

## A composite wall with a reversed heat-flow sensor

A facing layer touches a 380 K reservoir. Behind the facing, two strips run side by side to a 280 K reservoir. Every piece is 0.10 m thick. The facing has area 0.020 m² and conductivity 20 W/(m K). The strip and insert each have area 0.010 m², with conductivities 10 and 30 W/(m K). An isothermal sheet joins the facing to both strips.

**Predict.** What temperature does the sheet reach? The insert sensor points from the cold bath toward the sheet. What will it read?

Using R = L/(kA), the facing contributes 1/4 K/W. The other pieces share both endpoint temperatures and conduct in parallel. Their conductances add to 1 + 3 = 4 W/K. The facing and the parallel section therefore have equal resistances and each drops 50 K. The sheet reaches **330 K**. The facing carries 200 W toward the cold bath, split into 50 W through the strip and 150 W through the insert. The insert sensor reads **−150 W** because of its orientation.

~~~sh
python -B -m qualification.h1_n13.conduction --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b
~~~

Read the values in the four named entries under `requests`. To check energy balance from the sheet's perspective, compare the 200 W arriving through the facing with the 50 + 150 W leaving. [Wall model](../studies/composite_wall/model.mo)

### What if conductivity increases with temperature?

Keep the same wall and bath temperatures. Take each piece's authored conductivity as its value at 280 K and multiply it by 1 + 0.01(T − 280 K), with T in kelvin and the slope in K⁻¹. The factor increases from 1 at the cold reservoir to 2 at the hot one. Each piece obeys steady Fourier conduction with a constant cross-section.

Integrate the factor from 280 K to T. Writing x = T − 280 K gives a transformed temperature u = x + 0.005x². The original wall conductance of 2 W/K now multiplies the difference in u. At 380 K, u = 150 K, so **300 W** crosses the wall. The strip carries +75 W and the reversed insert reads −225 W.

The facing and the parallel section have equal reference resistance. At their junction u = 75 K, so solving x + 0.005x² = 75 gives **338.114 K**. The junction lies above 330 K because the hot section conducts more readily. The same calculation applies to branches and loops when every rod shares the relative slope and its conductivity stays positive over the bath temperature range.

~~~sh
python -B -m tools.variable_conductivity --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --reference-k 280 --slope-per-k 0.01
~~~

## A bridge with a conducting crossbar

Two branches run from 380 K to 280 K. Along the upper branch the conductances are 2 and 2 W/K, in hot-to-cold order. Along the lower branch they are 1 and 1 W/K. A 1 W/K crossbar joins the branch midpoints, with positive flow from upper to lower.

**Predict.** Can the crossbar carry zero heat while the reservoirs exchange heat? If only the upper branch's hot-side conductance doubles, which way will heat flow through the crossbar?

Initially each branch splits its 100 K drop in half. Both midpoints sit at 330 K, and the crossbar carries **0 W**. The branches still carry 100 W and 50 W. Run the balanced case first.

~~~sh
python -B -m qualification.h1_n13.conduction --root studies/steady_bridge --study studies/steady_bridge/study.json --facts studies/steady_bridge/facts.json --facts-sha256 4cc763729e8d71b0abfc0eb5d1c3cc4d08185225104af8640541adcfdbf10bbf
~~~

For the changed bridge, let u and v be the upper and lower midpoint temperatures above 280 K. Balancing heat at each midpoint gives 4(100 − u) = 2u + (u − v) and (100 − v) + (u − v) = v. Solving gives u = 65 K and v = 55 K. Look for **345 K**, **335 K** and **+10 W** in the revised output under `upperT`, `lowerT` and `crossFlow` inside `requests`.

~~~sh
python -B -m qualification.h1_n13.conduction --root studies/steady_bridge --study studies/steady_bridge/changed_study.json --facts studies/steady_bridge/changed_facts.json --facts-sha256 9e62ef107a7499beb80406ac8b54b35e084830eb17f8d370ce96888884ba9f1f
~~~

The revised hot reservoir supplies 4(100 − 65) + (100 − 55) = 185 W. Treating the crossbar as permanently inactive would miss the redistribution. [Bridge model and revision](../studies/steady_bridge/README.md)

## Two insulated bodies joined by a rod

A body of heat capacity 500 J/K starts at 353.15 K. Another of capacity 1,500 J/K starts at 293.15 K. A storage-free rod of conductance 0.2 W/K connects them inside an insulating enclosure.

**Predict.** Which quantities depend on the rod? Would doubling its conductance change the equilibrium temperature, the total heat ultimately transferred, or the time taken to reduce the temperature difference by half?

Energy conservation gives the capacity-weighted equilibrium temperature **308.15 K**. The hotter body ultimately loses 500 × (353.15 − 308.15) = **22,500 J**. The rod sets the initial rate, 0.2 × 60 = **12 W**. The temperature difference decays exponentially with time constant [500 × 1500/(500 + 1500)]/0.2 = **1,875 s**. The half-time is 1,875 ln 2, about 1,300 s. Doubling conductance halves both times while preserving the equilibrium and limiting heat transfer.

~~~sh
python -B -m tools.isolated_pair_exchange --root h1/cases/D2 --study h1/cases/D2/study.json --facts h1/reference_cases/D2.json --facts-sha256 befcb977a08bdb4d3f15d903ebafccf910d83675f8d1a92f1988bca74a8a547a
~~~

Read `fromBody` and `toBody` before interpreting the sign. The command reports cold-to-hot transfer, so its initial rate is −12 W and its limiting transfer is −22,500 J. The equal endpoints in `differenceTimeConstantBoundsSeconds` give 1,875 s. [Two-body model](../h1/cases/D2/model.mo)
