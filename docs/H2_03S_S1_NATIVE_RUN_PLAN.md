# H2-03S — approved one-shot S1 native evidence acquisition

**Owner decision:** On 2026-11-16 the owner approved the recommended **new, carefully bounded OpenModelica S1 run** after the earlier source/feasibility preparation. This is authorization for **one diagnostic attempt only**, not automatic retries, another model, a merge, or native qualification.

## Source, data and unchanged calculation contract

- Source repository: `physicsvigilante/sim_heat`; experimental branch: `experiment/h2-s1-steady-native-once`. Separate viewer-development branch: `h2/s1-steady-source-viewer`. Do **not** merge the one-shot trigger to `main`.
- Case: `h1/cases/S1/model.mo`, model SHA-256 `3228323714b2f886279aa90c46c1c49c9143e2d8b9c6de032389c750b6848f1c`; study `h1/cases/S1/study.json`, SHA-256 `83bb6badc19e55008455083cde64adc2d53ba32c1d5f009d5b1b3594bd5f2405`.
- Independent reference input (same-author checked, **not** blind authoritative truth): `h1/reference_cases/S1.json`, SHA-256 `47b1d9035230cb252a992a3fdcdbdf6fbefd350f901aacaaae9dae37b561635a`. Physical source and unit issues recorded in `docs/SOURCE_COVERAGE.md`.
- Original shared library `experiments/h1_spike/SimHeat.mo` SHA-256 `e57955b6c32cb34321a6b1908306c4ea9a63ae259b95a5fd48c7e8d3b4da10ea`. No physics/library change.
- Reuse unchanged generic runner `tools/h1_native_batch.py` SHA-256 `f2e43274f2eb08f58dcff34b327bac7c36bdba7c367efe6994cdb4fb335b61e1`; pinned-current MATv4 adapter `h1/matv4.py` SHA-256 `bb0a5194e1235af132a729d5287ecd1756eaad09585269eff18bc046589d1b8e`.
- Signed interpretation: rod power positive hot→cold; hot boundary supplies positive W, cold boundary absorbs negative W. No stored energy/time-history claims.

## Actual bounded run plan

- **Execution plan:** `tools/h2_s1_native_plan.json` with SHA-256 **`e824b0718d969483de1dc52b6562bf94c219eaadc7dc057659cd557f7c3c5283`**, read and enforced by the generic runner. It includes 22 exact SHA-256 pins covering physical inputs, references, current numerical/decoder/checker modules, runner and selected tests.
- Only one case, S1; only one reference preparation (sealed **before** build), one explicit `omc --version`, at most **one `buildModel`**, at most **one model executable launch**. There are no tolerance variations, companions, or second cases in this approval.
- Native `buildModel`: `startTime=0`, `stopTime=1`, `numberOfIntervals=1`, `tolerance=1e-8`, `method="dassl"`, `outputFormat="mat"`, `variableFilter=".*"`. The 0→1 span is an **algebraic evaluation coordinate** for S1, **not** elapsed thermal time.
- Ephemeral GitHub-hosted `ubuntu-24.04`, pinned `actions/checkout@11bd7190...`, `actions/setup-python@a26af69b...`, `OpenModelica/setup-openmodelica@419f3114...`, `actions/upload-artifact@ea165f8d...`; OpenModelica **1.27.0**, MSL **4.0.0**, Python **3.13.5**, NumPy **2.3.5**, SciPy **1.17.0**.
- Time budget: workflow ≤30 min, model build ≤600 s, model launch ≤120 s, explicit version ≤30 s. No OMC command until offline test suite passes, exact source pins match and reference is sealed. Native commands receive restricted environment without GitHub credentials; checkout does not retain credentials, and workflow token is read-only. Network-isolated execution is **not** claimed.
- The workflow triggers only from a **push modifying its own file on this exact experimental branch**. `github.run_attempt==1` and runner `check_host` forbid reruns/incorrect branch/event. Failed attempts are consumed and retained, never retried automatically.
- Save original attempt manifest and counts, original native MAT, setup, compiler/MSL hashes, source snapshots, generated C/executable/logs, normalized CSV, alias/parameter provenance, independent reference seal, verification and failure trace where present. Always upload artifacts even on failure.
- The runner returns `diagnostic_checks_passed_not_native_qualified` at most; all public requests remain `diagnostic_only` and `nativeQualified=false`. No original failed S1 workflow is relabeled successful.

## Stop and next gates

If preparation, setup, build, runtime or checking fails, **stop this attempt** and record the actual failure. Do not change native results, retry, add reference-derived values, relax numerical limits or fabricate receipt. Only if this native attempt truly completes its bounded checks may a **new separately reviewed steady-viewer adapter** use its authentic archived ZIP bytes. An H2-03S R2 draft PR, exact-head CI and independent Chat B review remain required before any viewer merge.
