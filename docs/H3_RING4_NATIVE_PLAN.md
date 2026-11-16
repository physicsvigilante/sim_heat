# H3-RING4 — one-shot native execution policy and evidence contract

**Owner instruction:** approval to pursue the next full teacher-described composition → native simulation → generic viewer demonstration, 2026-11-16. This document limits the native portion to **ONE** fixed, new development-exposed case and one native attempt. It is not authorization for retries, physical law changes, arbitrary Modelica execution, C1 blind transfer or merging a draft source PR.

## Explicit tested problem and frozen authoring

Original captured task `experiments/teacher_ring4/TASK.md` was committed **before** model authoring. This is an **illustrative extension** of the conduction mechanisms around Illustration 135, *not* a literal source-problem solution. This case must remain outside independently reserved H1-C1-F0. First-model SHA-256 `3a4771b5e6254a72a2d96e8a432b5151db8af51c1ef1d49b9553bb0e9c56e5a8`, study SHA-256 `812e27fb83643d8ddf052181610f3d1353efbdef4e482a9374f263dd92b7f1fd`, separately entered checking reference SHA-256 `f5a7b10337cd62ff79ce77896b63135b71a2b2e39ee355ace46acf4ede55217b`.

The model has 4 thermal bodies (individually initialized), one maintained hot boundary and 6 storage-free rods: the A–B–C–D–A ring, A–C diagonal and bath→A. Every numeric input and signed connection is in frozen Task and original Modelica. Existing H1 public grammar admitted the complete model (5 physical nodes, 15 passive observation requests); all requests remain `not_computed` before native execution. No numerical answer has been fed to the model.

## One-shot generic runner and exact pins

- Execution branch: `experiment/h3-ring4-native-once`, created from `h3/teacher-ring4-composition` after task/model/study/reference/notes first-submission commits. **Do not merge this branch-only trigger to `main`.**
- Execution plan: `tools/h3_ring4_native_plan.json`, exact SHA-256 **`6e3aeb26854cb187e6108b14439aef874271f705c96092c16cb047a978965595`**, containing **23** per-file SHA-256 pins: model, study, reference, unchanged Modelica library, H1 implementation/tests and unchanged `tools/h1_native_batch.py`. A mismatched plan or source file **refuses before native installation**.
- Existing runner `tools/h1_native_batch.py` **unchanged**, schema `sim_heat.native_batch/1`. No custom executable/model selection, no apparatus-specific solver path, no reference-filled missing observations. Runner performs complete H1 offline tests, independently seals checking reference before native commands, checks compiled identities, MAT parameter/alias precision and the unchanged verification policy.
- Ephemeral GitHub `ubuntu-24.04`, pinned `actions/checkout`, `setup-python`, `OpenModelica/setup-openmodelica` and `upload-artifact` SHAs previously qualified for D1/D2 and S1; OMC **1.27.0**, Modelica Standard Library **4.0.0**, Python **3.13.5**, NumPy **2.3.5**, SciPy **1.17.0**.
- **Maximum one explicit OMC version query, one `buildModel` call, one model executable launch**, fixed **0–24000 physical seconds**, 2000 intervals, DASSL, **1e-8** tolerance, `outputFormat="mat"`, `variableFilter=".*"`. Build ≤600s, launch ≤120s, version ≤30s; workflow ≤30 minutes. Stop at first failed stage, no retry/fallback/version substitution/tolerance relaxation. No native execution on `main` or standard PR checks.
- No persistent checkout credentials; read-only GitHub permissions, restricted native process environment. This is not claimed to be a network-isolated untrusted-code runner.
- Preserve the original run manifest, actual process counts, source snapshots, independent presealed reference, compiler/MSL source identifiers, build/source/executable logs/hashes, raw MAT, normalized CSV, verification/report and failures/cleanup inside the original Actions artifact even if unsuccessful.

## Checking-only independent physical evidence

An independently written **checking-only** SciPy DOP853 ODE constructed from task inputs (not production Modelica code) agrees with original generic H1 reference at 7 declared times with maximum temperature discrepancy about **4.8e-10 K**. Stored in `experiments/teacher_ring4/independent_ode_check.py`. The predeclared H1 reference predicts heat-flow reversals on `ringAB`, `ringBC`, `ringCD`, `ringDA`. Those are checking predictions only, not demonstrated native results, not exact unsampled crossing times.

## Stop/release decisions

A successful one-shot run can yield a **`diagnostic_checks_passed_not_native_qualified`** archived native artifact with `nativeQualified=false` and `diagnostic_only` requests. Only then may a data-only viewer adapter generate a new case from actual bytes, with independent original ZIP/source/CSV hashing. Existing source and viewer must require **zero code changes**; case JSON + catalog are the only allowed viewer additions.

If the model is refused or native checking fails, retain the original failed attempt and stop. Do not silently alter the task/model/checking policy or claim a solved case. A substantive correction or successor native run requires a new identity and explicit bounded decision. A successful source candidate still requires full current-head CI, a **draft PR**, one independent-in-context R2 Chat B review and separate owner **merge approval**. Avoid claimed H1 native qualification, generic unknown-model transfer, independent material measurement, exact radiative behavior, inverse/symbolic solving or classroom effectiveness.
