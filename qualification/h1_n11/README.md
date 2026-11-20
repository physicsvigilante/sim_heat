# H1-N11 — independent outward-rational T1-T dynamic verification candidate

**Offline checking candidate; NOT an independently reviewed or adopted reference.**
Parent reviewed-but-unmerged N10 PR77 `1caea6afae55b3529c9818405d2ae669ea00be5c`.
No Modelica, legacy H1 production, native runner, old archive, original author,
N1–N10 calculation or frozen reference bytes change.

## Physical and mathematical scope

N9 already found 100,828 exact-static-physics candidate-bit agreements, and
N10 separately compared 648,180 original T1-T dynamic/public/integral values
against 90-decimal-digit mpmath. Neither agreed numerical approximation
is itself a rigorous error bound. N11 goes beyond agreement by making a
second **outward interval arithmetic proof candidate** directly from the
original, independently transcribed source facts (fixed byte SHA
`39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf`),
original author Modelica and study SHAs, and original unmodified N1 trace
byte SHA identities.

The new arithmetic is a private `Box(low,high)` integer-scaled rational
enclosure with scale `10^88`. Each physical source decimal is interpreted
as a Fraction **exactly**; the independent circular-area constant uses a
43-term alternating Machin Pi interval with the mathematical first-omitted
term bound. Every interval multiplication and inverse encloses both extrema,
refusing a zero-containing denominator. No unproved `mpmath`, `SciPy` or
`float` calculations generate the physical enclosure.

Unlike N1's T1-specific, 2×2 determinant-based Schur inverse and
term-by-term Taylor series, N11 computes a signed graph Laplacian from its
own parsed original source `RodArea` and `RodCircular` ports, eliminates
the two source-ownerless junction nodes using independently coded **interval
Gaussian pivots**, and evaluates the exact state matrix through a **descending
matrix Horner expansion**. The normalized seven-state augmented ODE uses
`u=(T-289 K)/(78 K)`, `τ=t/2400s`, and states
`[u_R,u_B,u_P,∫u_R dτ,∫u_B dτ,∫u_P dτ,1]` (actual body order comes from
sorted source-owned bodies rather than N1's hard-coded R/B/P order).
No spurious capacity or thermal connection is assigned to a junction.

For each grid step, `X=B/intervals`; the source-derived **outward**
infinity norm `ρ >= ||X||∞` is refused unless `0<ρ<=1/2`.
The degree-24 Horner polynomial receives a per-entry exact rational tail:
`2 ρ^25/25!`, because `exp(ρ) <= 2` under the admitted norm bound.
This encloses the true real matrix exponential in every entry. The
mathematically exact affine last row may be set to `[0,...,0,1]` **only**
after proving every interval in the original last generator row is exactly
zero; interval rows merely containing zero must refuse. The complete
outward matrix-step enclosure is repeatedly propagated, retaining all
rounding and source-Pi uncertainty through **every** original saved time.

N11 independently reconstructs from those enclosed temperatures and their
analytical time integrals all **77 original internal exports**, **eight
first-author study requests** and **five signed body/boundary integrated
flows**, with physical a→b positive rod flow and component-positive-inlet
convention. At each time, the true zero junction flux balance, each
`dU−∫Q_in`, and global body/boundary integrated supply must lie **inside**
the outward residual enclosure; these conditions cannot be fulfilled by
substituting N1/native expected values.

A proposed original N1 `float64` centre is accepted only when its *exact
rational bit-representation* is within the outward **physical source**
interval by at most the original conservative **1/100 reference allowance**:
`1.1e-7 K`, `1e-8 W`, `1e-5 J`, and
`(64 ULP)/100` for C/G/A. No source-dependent allowance fitting or
post-output threshold increase is performed. There are exactly
`(77+8+5)*(2401+4801) = 648180` comparisons, including 100828 static
samples also already tested by N9. They are repeated channel/sample checks,
not statistically independent physical facts.

## Provenance and important nonclaims

- The N1 2401/4801-grid float64 bundles **must match exactly** their
  prepublished full-source-only trace SHA256
  `b13877c8d069a60928cf3b23ae007b1a10feb53151f00ffb65a57082a7fc10af`
  and `9ba71a1d2fccb39be071df0647793f6fb844737e2ac9c91bb143546ab8d26b40`,
  checked by the earlier N9 original-byte gate **before** N11 consumes a
  result. N4's source-exact static consistency is also required.
- This is a new independent-implementation **mathematical self-enclosure
  candidate**, not a separately reviewed independent proof yet. Even a
  successful hosted CI remains a developer-provided claim until Chat B
  independently examines premises, interval operations, Machin remainder,
  Gaussian pivots, matrix norm/tail, accumulated recurrence and every
  physical export/sign/integral/error allowance.
- `sourceMathematicalEnclosureSelfChecked` can be true if the executable
  actually passes; `independentExternalMathematicalCertification`,
  `fullDynamicPhysical100xIndependentlyCertified`,
  `referenceAccuracyCertified`, `independentlyCertifiedReference`,
  `runtimeReady`, `referenceBundleWritten`,
  `externalOwnerApprovalVerified`, `nativeExecuted` and
  `nativeQualified` **must remain false**. The N11 output is NOT a
  `sim_heat.reference_bundle/2` or future
  `sim_heat.h1_n3.reference_bundle/1`; the legacy runner cannot consume it.
- Independently externally authenticated owner source/reference manifest,
  native one-use reservation, actual fixed OMC/MSL/container identity,
  versioned runner dispatch and native artifact validation are all still
  MISSING, even if the mathematics passes. The original legacy
  `h1.reference.prepare` seven 100× physical-precision failures
  `T02.G,T06.A,T06.G,T07.G,T08.G,T10.G,T_Plug.C`, eight native
  blockers and original lost/unsealed first-author scoring key remain open.
  They cannot be relabelled as corrected by N11; no old reference is rewritten.
- The proof is for original T1-T source+two grids, not arbitrary phase change,
  thermal radiation, true 3D geometry, general JEE thermodynamics or
  automatically certified unfamiliar compositions. Component reuse is
  separate from a universality claim.

## Reproduction

With the pinned mathematical **checking-only** Python dependencies and without
OpenModelica, from the repository root:

```sh
python -B -m unittest qualification.h1_n11.tests.test_rational_dynamic_proof -v
python -B -m qualification.h1_n11.rational_dynamic_proof --out /tmp/h1-n11-fresh-candidate
```

The output folder must not exist and must be outside the source repository.
N1's original full traces are regenerated in temporary scratch directories,
rehashed and checked; the only surviving result is N11's compact JSON
receipt. No native simulation, source modification, historical C1 overwrite,
reference version migration, output/authentication promotion, merge or deploy.

One focused independent **R2 mathematical/evidence** review is mandatory before
accepting the narrow claim. Any numerical refusal or reviewer-discovered
counterexample is a preserved outcome, not a request to loosen the original
physical accuracy obligation.
