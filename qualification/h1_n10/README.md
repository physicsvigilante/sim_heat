# H1-N10 — Independent high-precision dynamic replay candidate (OFFLINE ONLY)

**Status: prospective mathematical corroboration, NOT a certified native reference.** This new layer follows independently scoped-reviewed N9 PR76. It does not change any H1 parser/model/physics library, N1–N9 source, original T1-T first authored model or study, checking-reference bundles, native runner, archived results or frozen C1.

## Why this is the next useful step

N9 checked **100,828 static C/G/A values** against independently derived source-physical calculations, but the original T1-T **temperature, signed heat-flow, stored-energy and integrated-flow histories** had not yet been recomputed by a second mathematical implementation.

N10 performs a separate high-precision **numerical** reconstruction from the original `sim_heat.reference/1` physical facts (SHA256 `39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf`). N4's source parser validates those original physical facts; N10 does **not** use N4's computed static values, N1's Schur transform, interval propagator, public request calculation or N1 solver as its independent physical calculation. N10 assembles its own oriented graph Laplacian, identifies finite bodies, fixed temperatures and ownerless nodes, solves the actual junction equations using general `mpmath` matrix inversion, eliminates the ownerless algebraic nodes, and constructs the original constant-property affine physical-temperature ODE with separately integrated body-temperature states.

A new **90-decimal-digit mpmath matrix-exponential** step recursively calculates all original saved time points for both 2400-interval and 4800-interval grids, then reconstructs from the source physical facts **all 77 internal exports, eight original author-requested observations and five integrated body/boundary flows** using independently stated energy and sign formulas. All rods preserve positive `port_a→port_b` orientation, port flow into its own component, positive boundary supply toward the network, `dU=C*(T−T_initial)` and `G=kA/L`, circular area from **diameter** `A=πd²/4`.

The original N1 interval-reference **candidate** is freshly generated in scratch space, and N9 requires the **entire original trace SHA256** match these pre-published digests BEFORE N10 uses a single sample:

- Primary 2,401 samples: `b13877c8d069a60928cf3b23ae007b1a10feb53151f00ffb65a57082a7fc10af`.
- Dense 4,801 samples: `9ba71a1d2fccb39be071df0647793f6fb844737e2ac9c91bb143546ab8d26b40`.

N10 independently predicts the exact 2401/4801 physical grid times, checks every original 77+8+5 value against the 90-dps calculation, and compares its error to **one hundredth of a conservative existing allowance** for each unit: `(1e-5+1e-6) K /100`, `1e-6 W /100`, `1e-3 J /100`, and `64 ULP /100` for static C/G/A. These are *fixed before reading outputs* and are not enlarged to make a model pass. With 90 values per saved time, there are **648,180 scalar comparisons** across both grids. The results are cross-implementation numerical corroboration, not independent interval enclosures.

**Critical distinction:** 90-digit mpmath is a high-precision *numerical method*, not an independently verified rigorous proof of truncation, rounding and input-to-binary error. Even a close match at every saved point is NOT a full independent 100× physical-error certificate, source/owner seal or proof that OpenModelica will produce the same result. N1's previously reviewed interval reference and N4 static proof remain separate checking-only sources. N10 does NOT adopt either as runner-consumable reference. Its positive result must keep `fullDynamicPhysical100xIndependentlyCertified=false`, `referenceAccuracyCertified=false`, `independentlyCertifiedReference=false`, `referenceBundleWritten=false`, `runtimeReady=false`, `nativeExecuted=false`, `nativeQualified=false`, `externalOwnerApprovalVerified=false`.

## Refusals and proof boundaries

- A changed original first-author `model.mo`, `study.json` or source facts SHA **REFUSES**, as does an inconsistent original N1 full-trace byte hash, changed N4 static proof or altered native/certification status. The test permits no fallback to a regenerated historical checking bundle, native MAT/CSV, checking predictions of missing results, or altered original source.
- Strong negative tests: unsupported original numerical grid, corrupted output and in-repository target; one sample outside the strict allowance; signed `T06` flow and port direction; rod reversal leaves body physics unchanged but changes rod flow sign; a new insulated two-body conduction network has zero total stored-energy change and no fictitious fixed bath. The new calculation reads only source-physical data.
- The historical seven legacy `h1.reference.prepare` physical static 100× errors `T02.G,T06.A,T06.G,T07.G,T08.G,T10.G,T_Plug.C` remain **open**, as do all eight native blockers and the lost/unsealed first-author private key. No new interval proof, owner-verified manifest, real one-shot lease, actual OMC/MSL toolchain identity, full native qualification, or runner migration is delivered here.
- This is still specific evidence for the original T1-T fixed source and two original grids. Its graph assembly is reusable for supported constant-property connected/disconnected graphs, but that is not itself a generality/qualification certificate for unknown JEE systems.

## Offline reproduction

Run from the N10 branch on an **unchanged** source checkout with the pinned Python mathematical-only checker dependencies (including `mpmath==1.3.0`):

```sh
python -B -m unittest qualification.h1_n10.tests.test_dynamic_crosscheck -v
python -B -m qualification.h1_n10.dynamic_crosscheck --out /tmp/h1-n10-NEW-RECEIPT
```

The requested output must be a *new directory outside* SIM_HEAT. N1 primary and dense temporary full traces are deleted after verification; only the compact N10 report is written in the requested scratch directory. Original referenced input, H1-C1, old native diagnostic files and existing reviews are never overwritten. No OpenModelica installation/version query/build/launch, reference promotion, production merge or deployment.

Independent R2 review must challenge all 648,180 independently recomputed dynamic/integral channel comparisons (not only t=0), signed component energy/port conventions, source byte pins, invalid input handling, thermal junction elimination, high-precision method limits and the strict no-native/no-reference-certificate flag contract. If the independent calculation differs at a saved time, preserve the original failed output; do not silently tune physical assumptions or tolerance.
