# H1-N1-R1 — Independent-source interval reference candidate (offline ONLY)

**Status: unreviewed mathematical checking implementation. NOT native-ready.** This file and `certified_reference.py` extend the separately reviewed H1-N1-P0 **design** at source PR #60; they are not part of Modelica, the runner, the historical H1-C1 failure, or the H1-T1 author's original inputs. A passing self-check is not an independent numerical qualification, owner native permission, runtime/host attestation, signed MAT result, or successful precommitted author-scoring key. Keep PR60 and PR59 draft/unmerged.

## What has been implemented

A source-pinned, checking-only numerical calculation for the **original** supported T1-T transient problem: three finite bodies (`R,B,P`), ownerless junctions (`J_Upper,J_Lower`), two thermostatted boundaries (`W,K`) and ten rods. Physical facts are read **only** from the separately transcribed `reference-facts.json`, pinned by the original byte SHA-256 `39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf`. The original author model and study SHA-256 digests are checked again, and neither native results nor the production `h1.reference` graph are used to construct the mathematical reference.

The code independently constructs all rod conductances `G=k*A/L`, a circular rod area `A=πd²/4` (diameter, not radius), body capacities `C=mc`, the weighted thermal Laplacian and a two-junction Schur reduction. Source decimal literals are parsed as **exact rational numbers**; mathematical π comes from an alternating-series Machin rational enclosure (45 terms). A two-pivot interval check refuses any unproved nonzero Schur denominator. The original thermal inputs, finite `0–2400s` horizon and all public observation operands are unchanged.

Temperature scaling is `u=(T−289 K)/(78 K)` and time is `τ=t/(2400s)`. The seven-state homogeneous/affine system `[u_R,u_B,u_P, ∫u_R dτ,∫u_B dτ,∫u_P dτ,1]` has a **time-independent 7×7 dimensionless** matrix. Integrated states provide reference flow integrals directly from the mathematical solution, rather than integrating a native output trace. All original sign conventions are retained: `rod.Q_flow=G*(T_a−T_b)` positive a→b; component port flows into the component; boundary `Q_to_network` positive into the network; body `dU=C*(T−T_initial)`. No equilibrium claim is made.

## Why the enclosure is rigorous under its explicitly stated arithmetic model

This is NOT merely `scipy.linalg.expm`/eigenfunction agreement. The new implementation uses **only exact integers and rational arithmetic for the certified interval path** (except for final reference-centre rounding to binary64, whose exact rational discrepancy is then measured). Every `I(lo,hi)` represents `[lo/Q,hi/Q]` with `Q=10^64`. Addition/subtraction are exact on endpoints; multiplication uses all four endpoint products and integer floor/ceiling; division refuses denominators crossing zero and uses outward integer reciprocal bounds, including negative intervals. No floating-point matrix solve is used in this interval path.

For the primary grid `Δτ=1/2400` and dense grid `Δτ=1/4800`, compute `X=B Δτ` with outward interval arithmetic. Let `ρ` bound its infinity matrix norm from all outward endpoints. Refuse unless `0<ρ≤1/2`. Evaluate the first **18 Taylor terms beyond the identity** by outward interval matrix products and exact division by term index. For the omitted terms, the exact-rational bound

\[
\| e^X-\sum_{k=0}^{18}X^k/k!\|_\infty \le
\frac{\rho^{19}}{19!}\frac{1}{1-\rho/20}
\]

follows from the submultiplicative infinity norm and geometric bound on successive term ratios. Add its outward-rounded radius to **each** matrix-entry enclosure. The last affine coordinate is analytically exactly `1`; no approximated constant is accumulated. Apply the resulting full matrix-step enclosure successively through **every** 2,401- or 4,801-point grid sample. This propagates all source-input, π, matrix, Taylor-tail, intermediate-rounding and time-step uncertainties without native data. The reported proof includes the exact rational norm and tail bound, fixed scale, series order and whole-grid maxima.

Each physical internal export, derived public request and integrated flow is evaluated from these propagated intervals. A proposed binary64 centre is chosen solely from the interval midpoint. Its **exact** rational distance to both outward endpoints is bounded on **every sample**. The code refuses unless the maximum error is no more than **1/100 of a conservatively lower-bounded original acceptance allowance**: `1e-5K+1e-6K` for any port temperature, `1e-6W` for any flow, `1e-3J` for any energy/integral, and the unchanged **64 ULP** allowance for static C/G/A. These K/W/J lower bounds are deliberately **stricter** than the per-quantity own-scale acceptance policy; they never widen the old comparison tolerance. Static candidate centres therefore meet the physical **0.64-ULP** error budget, including the seven constants that the **original unchanged float64 checking centres fail**. Unlike the earlier non-adopted witness examples, these full-trace candidate values are generated by an explicit versioned checking-only implementation and accompanied by interval error bounds—still **not adopted into the old reference bundle or native runner**.

The code also checks at **every grid time**: ownerless-junction heat-flow conservation, each body `dU − ∫Q_in dt` and the complete network `Σ dU − Σ∫Q_boundary_to_network dt`, each as an interval containing zero with retained maximum absolute upper bound. An exact-rational trapezoid of the *rounded reference flow centres* is compared to independently enclosed flow integrals. This uses a uniform **0.0001 J ceiling**, which is never weaker than the current checker’s `1e-4 * max(1, energy_scale)` criterion. Results are recorded for all **77 mandatory internal exports, eight public observations and five integrated flows**, not a selected passing subset.

### Evidence and status boundaries

- The `sim_heat.h1_n1.interval_reference_candidate/1` output is **not** the existing `sim_heat.reference_bundle/2` schema; the native runner cannot consume it as a substitute. `mathematicalIntervalSelfCheckPassed=true` is a checker's SELF assessment only, **`independentlyCertifiedReference=false`, `runtimeReady=false`, `nativeExecuted=false`, `nativeQualified=false`, `sourceFidelityQualified=false`**, with the original H1-T1 precommitted evaluator key still unverified.
- The prior **seven** physical 100× refusals of the *unchanged* float64 checking centres (`T02.G,T06.A,T06.G,T07.G,T08.G,T10.G,T_Plug.C`) are preserved explicitly. No original `h1.reference` values, H1-C1 reference/seal or native datum is edited. New candidate physical centres have NOT been used in a runner or certified by a separate independent review.
- The **four** unequal primary/dense native-comparison allowances remain an independent blocker. A future checking-only comparator must use frozen **PRIMARY** allowances at exact shared timestamps, after validating each run against its **own** independently sealed reference. No sum/max tolerance or interpolation. This implementation does **not** claim that comparator ready.
- Actual OMC binary/MSL/image/host identity, independently replayed new N1 reference seals, exact launch and approval manifest, durable one-shot 3/3/3/zero-retry budget, resource/network containment and owner native authorization are **all absent**. Native operation count is zero; no automatic trigger, OpenModelica version query, installation, build, launch or frozen-reference regeneration.

## Execution and review

Run **only** after installing Python checking dependencies (`numpy==2.3.5`, `scipy==1.17.0`, `mpmath==1.3.0`) for the *existing plan checker*, not OpenModelica. From the source tree:

```bash
python -B -m unittest qualification.h1_n1.tests.test_certified_reference -v
python -B -m qualification.h1_n1.certified_reference --intervals 2400 --out /tmp/n1-primary-NEW
python -B -m qualification.h1_n1.certified_reference --intervals 4800 --out /tmp/n1-dense-NEW
```

The two output folders **must be new and outside the source repository**. The checker refuses overwrite of any existing output path, including old C1/reference archives. Full checking traces and per-quantity maxima are **temporary evaluation artifacts**, not production native data. `PLAN_ONLY_NOT_EXECUTABLE` remains in force; `check_plan.py` should still report the old seven static checking-centre refusals and eight execution blockers. One focused R2 independent review should challenge this new actual interval implementation, exact source/arithmetic proofs, all-grid bounds, signatures/hashes and refusal controls, but **not** redo the already reviewed design or source-authoring trial unless a new inconsistency is found.
