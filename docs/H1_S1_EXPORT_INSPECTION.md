# H1 S1 saved-export inspection

Date: 2026-11-15. Scope: inspect the existing artifact; no new compiler call,
model launch, installation, workflow change, production-code change or merge.
This is an author inspection and proposal, not independent acceptance.

## Exact evidence

- Run: https://github.com/physicsvigilante/sim_heat/actions/runs/43687443730
- Executed commit: `c8b63132b6d1137c0766a7171bfff3992faf0abf`.
- Artifact: `14151300250`, `h1-s1-1270-native-evidence`, 104,838 bytes.
- Downloaded ZIP SHA-256: `566a804fee3b795da82027af57bb82712c33fea4326afb65ff9b9d46fe9d7d0c`.
  This matches the digest returned by GitHub for this artifact.
- CSV SHA-256: `619d30ad45f8006da02090708c2676dfe7728d55460102e5ae9acbe480fa2492`.
- Init XML SHA-256: `b715ffa631210181da6b826506bb5bc5f41529b17a7b3ed6e5d64576b1779619`.
- Existing reference seal: `d4b04b2bfaa38afacda550bea9433b5645af83e173d0b28632b1b5225e8e8074`.

All 88 SHA-256 entries in the saved attempt manifest match the downloaded files.
The reference seal was independently recomputed from its canonical payload.
The raw CSV has three rows at indices 0, 1, 1. The last two rows are identical;
there are two distinct algebraic evaluation indices, not physical-time dynamics.
The build log reports MSL `4.0.0`; generated C source paths identify the package
folder as `Modelica 4.0.0+maint.om`. This does not establish a complete MSL source
pin. The old manifest remains `stopped_model_executed`, `nativeQualified=false`.
The artifact's original executable and generated C were read/hashed, never run.

## Root cause: CSV is not a complete parameter export

The exact OpenModelica v1.27.0 CSV runtime source [1] has no parameter-writing
loop and explicitly excludes `ALIAS_TYPE_PARAMETER` aliases from both header
and row output. Its real-valued output format is `%.16g`.

Consequently, this is not merely an unexpected naming issue. The CSV-first
integration choice cannot satisfy the complete 18-output registry for this
model. Changing `variableFilter` to `.*` does not change the writer's parameter
policy; the failed run already used that filter.

| Missing names | Saved XML evidence | Disposition |
| --- | --- | --- |
| `hot.T`, `cold.T` | `rPar`, parameter inputs; fixed starts 373.15 and 273.15 K | Start metadata is not a separate recorded post-initialization result. Do not silently promote it to a native observation. |
| `copper.A`, `copper.G`, `steel.A`, `steel.G` | `rPar`, `causality=calculatedParameter`; no `Real start` value | The values are computed during initialization and are absent from this CSV/XML value set. Do not substitute zeros or reference calculations. |
| `copper.T_a`, `steel.T_b` | Aliases to `hot.source.T` and `cold.source.T`; those targets are calculated parameters without a stored start | Alias links identify relationships, not missing runtime values. Their own `start=288.15`, `fixed=false` fields must not be used as solutions. |

The generated `H1_S1_08bnd.c` shows assignments for area, conductance and the
boundary-source parameters. These corroborate the initialization dependency;
evaluating the generated formulas in Python would produce reconstructed values,
not evidence that those values were actually exported by this completed run.
No such evaluation or reconstruction was used.

The raw CSV already contains both rod-port flow columns. The missing exports
are parameters and parameter-linked temperatures, not the second port flows.

## Partial numerical observations from the actual saved CSV

The 10 available mandatory columns were compared at the two canonical indices
against their presealed reference columns, with their unchanged allowances.
All 10 are within those allowances. The largest absolute flow discrepancy is
`6.661338147750939e-16 W`; the largest error/allowance ratio is
`3.203671538084899e-10`. The two available temperature columns match the stored
floating-point reference values at these indices.

| Quantity | Raw CSV values at indices 0 and 1 |
| --- | --- |
| `copper.T_b`, `steel.T_a` | 366.4562880324543 K at both indices |
| `copper.Q_flow`, `steel.Q_flow` | +1.079282494650801, +1.079282494650802 W |
| `hot.Q_to_network` | +1.079282494650801, +1.079282494650802 W |
| `cold.Q_to_network` | -1.079282494650801, -1.079282494650802 W |

Each rod's a-port flow is positive and b-port flow negative in the raw file.
The XML identifies the flow outputs as signed aliases of the same native
`steel.Q_flow` channel. It likewise links `copper.T_b` to `steel.T_a`.
Their sign/consistency checks are useful, but are not independent numerical
measurements simply because they occupy different CSV columns.

These are partial diagnostic comparisons, not completion of `h1.verify`,
reference-accuracy closure or whole-study acceptance. The strict verifier was
not bypassed or called with manufactured values. Its original incomplete-output
failure remains unchanged.

## Smallest reusable successor: MATv4 result adapter

Use OpenModelica's double-precision MATv4 output for a future controlled attempt.
The v1.27.0 format specification [2] and MAT writer [3] explicitly represent
parameters, trajectories and parameter/variable aliases. This is a backend
representation change, not a new physical law or apparatus-specific solver.

The adapter should use the existing output registry and the result's `name`,
`dataInfo`, `data_1` and `data_2` matrices. It must decode the recorded orientation,
1-based indices, alias signs and actual parameter values; keep an origin record
for every exported quantity; and identify shared channels rather than claiming
alias copies are independent. It must refuse missing values, invalid indices,
inconsistent parameter endpoints, unsupported layouts, nonfinite data and
ambiguous sample times. No XML-start fallback or evaluation of physics formulas.

The existing checker can then consume canonical columns, with raw MAT and any
normalized representation separately hashed. Keep current units, time policy,
comparison tolerances, native evidence labels and physical model inputs intact.
Neither implementation nor qualification of that new adapter is claimed by
this inspection. Test its decoding offline before a separately authorized native
attempt. No workflow or production source is changed here.

## Composability and current disposition

The gap belongs to backend result extraction, not component/assembly physics.
Any fix must apply to registered names in arbitrary admitted arrangements; no
`copper`, `steel`, S1 or illustration-number dispatch is justified. Do not remove
parameters from the checking obligation merely to make the old CSV pass.

No new cloud run or merge was needed for this diagnosis. Source PDFs, authored
models, shared physical library, historical evidence and acceptance tolerances
are unchanged. The present run remains a successful native build/launch with an
incomplete exported-result contract, not an accepted H1 simulation.

## Primary implementation sources inspected

[1] https://github.com/OpenModelica/OpenModelica/blob/v1.27.0/OMCompiler/SimulationRuntime/c/simulation/results/simulation_result_csv.cpp

[2] https://github.com/OpenModelica/OpenModelica/blob/v1.27.0/doc/UsersGuide/source/technical_details.rst

[3] https://github.com/OpenModelica/OpenModelica/blob/v1.27.0/OMCompiler/SimulationRuntime/c/simulation/results/simulation_result_mat4.cpp
