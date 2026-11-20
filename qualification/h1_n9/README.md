# H1-N9 — Original T1-T full-grid static-physics cross-check (OFFLINE ONLY)

**Candidate status:** a bounded **checking-only** consistency test between two independently implemented pieces already present in the draft numerical lineage, not a new physics solver, a fresh OpenModelica run, a production reference, or a release-ready runner. Stack: independently scoped-reviewed **PR69 N8** at `3e7a8434880cc197d54cd02377e4bd69c15d1717`. All historical source and diagnostic bytes remain unchanged.

## The specific gap it closes

The existing **N1** source-pinned T1-T reference candidate has 2,401 (primary) and 4,801 (dense) sample trajectories, 77 internal exports, eight requested values, and five integrated flows. Its interval proof is mathematical evidence under its stated source-physics model, **not independently certified as a new native-runner reference**. The existing **N4** reusable exact-source static arithmetic independently computes positive body capacities, rod conductances and circular areas using rational source decimals, rational Pi enclosure and correctly rounded RN-even float64 centres. N4 was independently reviewed as a **generic static source-only candidate**.

N9 does **not** write another solver or reimplement physical laws. It re-runs the unchanged N1 generator for the *original* pinned T1-T task at both original grids and independently reconstructs N4's fourteen scalar static physical proofs directly from the original `reference-facts.json` bytes. It requires **the float64 bit pattern of every single N1 static sample** to equal the separately derived **N4 correctly rounded physical centre**, with exactly the original SI unit. It checks all `14 × (2401 + 4801) = 100,828` static observations, not just a t=0 or selected-channel sample. This is stronger evidence of cross-implementation static consistency; **it does not independently reverify all dynamic temperatures or heat-flow trajectories**.

Both original N1 trace SHA-256 identifiers are pinned *before* inspecting a new result:

- 2401-point source-only trace: `b13877c8d069a60928cf3b23ae007b1a10feb53151f00ffb65a57082a7fc10af`
- 4801-point source-only trace: `9ba71a1d2fccb39be071df0647793f6fb844737e2ac9c91bb143546ab8d26b40`

The exact same original N1 physical facts `39f18db09fa618bc73bbe75ca40f33d41ded70a1c73865b2a0e376973d9adfbf`, author Modelica `2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae`, and study `12ad51f59d2bd6c6561d4059f68b4263e7d4e39cdf5493f353a7affee6929d2a` remain immutable. N9 refuses any drift of the original trace bytes, source or flags, absent static field, changed unit, nonfinite/boolean numeric value, forged source-qualified status or differing static float64 bit on any sample. It cannot substitute its own reference values for missing native data.

The seven **legacy** `h1.reference.prepare` physical 100× checking-centre failures remain precisely `T02.G,T06.A,T06.G,T07.G,T08.G,T10.G,T_Plug.C`. The generic N4 mathematical candidate may agree with N1 at all static outputs **without repairing those old reference bundles**. The original dynamic/integral physical certificate, versioned bundle/runner migration, independent external trust anchor/approval, real OMC/MSL/host identity and one-shot lease remain separate work.

## Reproduction, without a native compiler

```sh
python -B -m unittest qualification.h1_n9.tests.test_static_trace_crosscheck -v
python -B -m qualification.h1_n9.static_trace_crosscheck --out /tmp/h1-n9-fresh-receipt
```

The output path must be a **new path outside the repository**. Full grid data is generated under disposable scratch directories, rehashed/checked, then deleted. Only a small source-only audit receipt is written to the requested scratch location. No original source, archived diagnostic, C1, physical reference or native execution plan is overwritten.

The receipt declares `staticPhysicalAgreement=PASS_CHECKING_CANDIDATES_ONLY`, explicitly **false** for `independentFullGridPhysicalCertificate`, `independentlyCertifiedReference`, `referenceAccuracyCertified`, `runtimeReady`, `nativeExecuted` and `nativeQualified`. A green result is *not* a request-to-run OpenModelica.

## Review acceptance

Independent R2 should challenge actual N1 and N4 sources and the crosschecked bit/unit equality, original trace and model/study/facts SHA pins, deliberate later-sample one-ULP mutation, missing units, false status and failure-counter preservation. It must distinguish N1's own interval proof from this static cross-check, and require separate evidence before any full 77+8+5 dynamic reference certificate or native attempt. No new physical law or apparatus-specific dispatch is introduced.

**HARD HOLD:** all prior draft PRs remain unmerged. Seven old static physical checking failures, eight native blockers and unsealed first-author private key persist. No OpenModelica install/version query/build/launch, native reference promotion, source owner trust seal, C1 rewrite, merge or deployment.
