# H1 conductivity revision and numerical companions

Date: 2026-11-15. Base: `17b79772153b15a61bc00f8d3c5fc66695d2d1d0`. The user approved the conductivity-change investigation and planned resolution checks after the primary D1/D2 cloud results. This is a bounded diagnostic extension, not full H1 acceptance or an unfamiliar-composition claim.

## Exact work and budget

Use existing D2_K2 (rod conductivity 200 instead of 100 W/(m.K), original bodies and initial states unchanged) once at its existing primary settings. For each of D1, D2 and D2_K2, run two planned companions: DASSL tolerance 1e-10 on the same 1000-interval grid; and 2000 intervals at the primary tolerance 1e-8. Horizons remain 12500 s for D1 and 9375 s for D2/D2_K2. No physics input or comparison allowance is changed.

**Maximum: 7 builds, 7 launches, 4 explicit compiler-version queries; no retries.** The existing two-case batch runner is unchanged. Four pinned subplans hold respectively 1, 2, 2, 2 configurations. An orchestration helper prepares all seven references before any native build and invokes those plans in order, stopping the whole campaign on the first error. Setup-action package/version probes are separate from the four explicit queries and retained in setup logs. This step does not spend the unselected C1 or edge-case run slots.

The original D1/D2 primary outputs are reused from run `43691263273`, artifact `14152886226`, ZIP SHA-256 `8fc38b9e2f040b48ab5cbeab34e8698b7c99c4d462a1e31e8bc33b0395185379`. They are not rerun or rewritten.

## Reuse and input authority

The Modelica library, authored models, original studies and references, batch runner, MAT reader, numerical policy and verifier retain their bytes. All original checking/input pins are inherited from the approved D1/D2 plan; extra source pins and the seven-entry list are in `tools/h1_resolution_campaign.json`.

Numerical companion descriptors change only analysis settings and experiment identity. Reference companion descriptions change corresponding analysis/identity fields, not physical facts or connectivity. Original model bytes are copied to a fresh disposable inputs directory; the conductivity revision still validates against the exact original D2 parent hashes. The generated studies, references, plans, source copies and hash links are retained. They are not additional editable physical authorities.

## Predeclared comparisons

Every native output must first pass the unchanged per-study checker with its presealed reference, initialization, sign and conservation policies. `tools/h1_compare_companions.py` then compares each companion to its primary at exact common planned times, with the original primary per-output allowance (not a fitted tolerance and not the sum of two allowances). Different physical inputs, grids without exact common times and changed allowances refuse. No interpolation or missing-value reconstruction.

Assess sampled-flow quadrature separately: compare cumulative trapezoidal integrals to the existing reference integrals and report how denser output changes that discrepancy. Do not infer solver accuracy from plot density or require monotonic roundoff-level changes.

For the teaching investigation, compare D2_K2 and D2 temperature differences at like physical times; also compare D2_K2(t) to D2(2t) wherever the saved primary grid supplies the latter exactly. The adopted equations predict doubled initial heat flow, half the relaxation time and the same 308.15 K asymptotic equilibrium; this statement is an analytical expectation, not a finite-time equilibrium claim.

## Offline evidence and cloud boundary

The restored 130-test baseline matched all 24 checking/input pins from the original native artifact and passed locally. The expanded suite passes **149 tests, zero failures/errors**, on existing Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0. A complete prepare-only pass sealed all seven references with **zero native calls**.

An earlier prepare-only development attempt exposed a fixture-discovery conflict: companion JSON files in the original reference directory were picked up by baseline tests. The generated inputs were moved to an isolated disposable directory; neither the original tests nor physics were weakened. That failed preflight and its logs remain retained with the author evidence. No cloud attempt had been triggered.

Cloud: Ubuntu 24.04, OMC 1.27.0, MSL 4.0.0 and the same pinned Python/numerical dependencies and action commits as the successful primary batch. Branch/path-scoped one-shot workflow; rerun guard; read-only token; no credentials in native subprocesses; existing timeouts/process-group cleanup and stop-on-error semantics. Network downloads during ephemeral installation are permitted; no network-isolation claim. All raw MAT, normalized data, channel origins, MSL manifests, logs, checks and failures are uploaded.

No C1 selection, native edge-case claim, independent review, final qualification label, classroom-effectiveness claim, or merge is implicit. The checker keeps `nativeQualified=false` and diagnostic-only observations. Prior failures, the source PDF, and earlier evidence remain untouched.
