# H1 first transient cloud batch: D1 and D2

Date: 2026-11-15. User approved the next D1/D2 transient milestone after the S1 saved-MAT diagnostic result. Base: `e963081aee6e2774b771126fea9fd5e50322d141`. This is a bounded developmental native experiment, not full H1 acceptance, a merge decision, or an unfamiliar-composition claim.

## Physical scope and reuse

Use the unchanged `h1/cases/D1` and `h1/cases/D2` model/study files and the unchanged shared `experiments/h1_spike/SimHeat.mo`. D1 has one finite body connected to a fixed-temperature reservoir; D2 has two isolated bodies connected by a rod. Their numerical parameters are illustrative bindings, not textbook numerical givens.

`tools/h1_native_batch.py` reads the model class, settings and output registry from admitted studies. It contains no dispatch on D1, D2, illustration numbers, materials or their physical values. Both cases use the same build, execution, corrected MAT reader and checker. S1-specific launch scripts remain historical and untouched. This is a backend orchestration generalization, not new physics or an alternative numerical engine.

| Case | Physical time horizon | Output intervals | Native method/tolerance | Required values |
|---|---:|---:|---|---:|
| D1 | 0 to 12500 s | 1000 | DASSL / 1e-8 | 12 |
| D2 | 0 to 9375 s | 1000 | DASSL / 1e-8 | 14 |

Reference predictions: D1 starts at 293.15 K with +12 W heat input; its time constant is 2500 s. D2 starts at 353.15 K and 293.15 K, has an initial +12 W oriented rod flow, and conserves the two bodies' total energy; the temperature-difference time constant is 1875 s. These are checking predictions, not native observations. A finite last sample is not an exact asymptotic equilibrium.

## Exact execution boundary

Branch `experiment/h1-cloud-transients-once`. A new workflow triggers only when its own file is pushed on this branch; no pull-request, scheduled or manual trigger. GitHub rerun attempts are refused. Existing workflows have different branch filters and must not be triggered by these additions.

Pinned environment: ephemeral Ubuntu 24.04 runner, OpenModelica 1.27.0, Modelica Standard Library 4.0.0, Python 3.13.5, NumPy 2.3.5 and SciPy 1.17.0. Reuse the previously exercised immutable setup-action SHAs. The compiler and loaded MSL version are checked; a manifest of the installed MSL .mo files is retained. Package-manager setup probes are not counted as model attempts and remain in workflow logs.

Budget: **at most two builds and two launches, one per case in D1-then-D2 order**, plus one explicit compiler version query for the batch. Stop on the first unexpected build, export, setting or numerical failure; do not launch D2 after a failed D1. No automatic retries, fallback solver, version substitution or tolerance relaxation. Build timeout 600 seconds; launch timeout 120 seconds; workflow timeout 30 minutes. Child process groups are killed on timeout. GitHub token is read-only, checkout does not retain credentials, and compiler/model subprocesses receive a restricted environment without GitHub credentials. This is not claimed to be a network-isolated or hostile-code execution service.

The plan file `tools/h1_d1d2_plan.json` is pinned by SHA-256 `3ece2a2b2fb3b6910d74b006fcd425203f099136e4c93de2559474c7ea042ed2` in the workflow. It binds all Python checking/adapter modules, their tests, the shared Modelica library, model/study files, separately entered references, and the new runner. A drift refuses execution. All references are prepared and sealed before the first native build. The manifest records the exact checkout and runtime versions.

After each successful build, inspect the actual initialization XML's model identity and effective start/stop/step/tolerance/solver/output settings before launching. XML starts are never used to fill result values. Actual MAT parameters, trajectories and alias signs are decoded by the unchanged corrected reader; normalized CSV and per-column origins are separately hashed. All registered quantities and local balances are checked, not just public requests. Missing/malformed data refuses rather than invoking an analytical fallback.

The generic checker remains unchanged and returns `diagnostic_only` observations and `nativeQualified=false`. The outer execution manifest records actual subprocess counts separately from that verifier's deliberately unattested input labels. Evidence includes source copies, both presealed references, build and simulation logs, init XML, raw MAT, normalized columns, origin records, verifier reports and failures. No artifact executable is run during post-run analysis.

## Offline checks actually performed

The reconstructed unchanged baseline passed 119 tests. Adding 11 offline runner/adapter tests gives **130 tests passed, zero failures/errors**, using existing Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0. The added tests cover study-selected horizons, one-build scripts, model renaming without dispatch, 1001-sample D1/D2 synthetic MAT verification, signed-flow corruption, effective-setting mismatch, identity drift, rerun/local-host refusal and no-retry command failure. A local prepare-only invocation also sealed both references with zero native calls. The same complete suite must pass again on the cloud host before installation/build. Synthetic tests do not establish native transient correctness.

## Claim limits

A successful primary batch supplies evidence for these two exposed transient arrangements and the reused extraction/checking path. It does not complete the planned tighter-tolerance/dense-grid companions, conductivity-revision native trial, reference-accuracy qualification, independent implementation acceptance, frozen C1 transfer, structural editing or classroom effectiveness. No challenge is selected here. No existing source, physical model, MAT adapter, checker tolerance, review record, earlier failed run or main-branch content is changed. No merge is needed to run this batch.
