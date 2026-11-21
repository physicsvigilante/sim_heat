# Which rod controls the total resistance?

In the composite wall, increase one rod's thermal resistance by a small percentage while holding every other rod fixed. Which change has the largest effect on the wall? The answer depends on how much heat flows through that rod and how much resistance it contributes.

For a connected two-terminal network, let Q be the total steady heat rate and qᵢ the oriented heat rate through rod i. Its **absolute sensitivity** is ∂R/∂rᵢ = (qᵢ/Q)². Its **relative sensitivity** is (rᵢ/R)(qᵢ/Q)². Both numbers are dimensionless. Multiplying the relative sensitivity by a small fractional change in rᵢ gives the first-order fractional change in the total resistance R. A finite material change can redistribute the flows and requires a fresh solution.

To derive the rule, normalize all rod flows to unit terminal throughput. Writing fᵢ = qᵢ/Q, the rod law and junction conservation give R = Σ rᵢ fᵢ². On differentiating, the redistribution term is proportional to Σ (rᵢ fᵢ) dfᵢ. Each rᵢ fᵢ is the rod's temperature drop in the normalized solution. Grouping these drops by endpoint gives a sum of node temperatures times changes in net node flow, all zero at fixed throughput. Only Σ fᵢ² drᵢ remains. The relative sensitivities therefore sum to one.

| Composite-wall rod | Absolute sensitivity | Relative sensitivity |
| --- | ---: | ---: |
| Facing | 1 | 1/2 |
| Strip | 1/16 | 1/8 |
| Insert | 9/16 | 3/8 |

A 1% resistance increase in the facing produces about a 0.5% increase in the wall resistance. In a balanced bridge the crossbar carries zero flow and its sensitivity vanishes. Unbalancing one arm restores crossbar flow and a positive sensitivity.

The tool uses a unit terminal temperature difference in the existing linear conduction engine to obtain the flow fractions, even when the imposed study temperatures are equal. It reports rational lower and upper bounds for each rod. Run from the repository root:

```sh
d=studies/composite_wall
python -B -m tools.resistance_sensitivity --root "$d" --study "$d/study.json" --facts "$d/facts.json" --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b
```
