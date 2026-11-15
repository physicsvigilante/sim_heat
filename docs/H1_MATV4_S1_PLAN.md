# H1 S1 MATv4 integration — one bounded cloud attempt

Date: 2026-11-15. Authority: user's approval of an offline-tested, generic MAT-v4 adapter followed by one controlled S1 cloud run. Parent evidence: [saved S1 export inspection](H1_S1_EXPORT_INSPECTION.md) and [prior 1.27.0 run](https://github.com/physicsvigilante/sim_heat/actions/runs/43687443730).

## Why this is a generic fix

OpenModelica 1.27.0's CSV export omits parameters and parameter aliases, leaving 8/18 mandatory S1 outputs absent even though its physical model compiled and ran. OpenModelica's MATv4 format preserves parameter values, trajectories and signed alias rows. This proposed adapter reads recorded MAT values, **never** calculates absent values from physical equations or reference predictions.

`h1/matv4.py` parses only bounded double-precision MATLAB v4 data with recognized OpenModelica metadata (`Aclass`, `name`, `description`, `dataInfo`, `data_1`, `data_2`). It accepts the documented `binNormal`/`binTrans` orientations, strict 1-based data-row indices, negative signed aliases, and parameter-invariant rows. `data_1` may also contain a non-invariant *time bounds* row; it is not mistaken for a physical parameter.

Every output is mapped by **the generic internal export registry**, never by an illustration ID or a special case for copper/steel. A provenance sidecar records the source table, row, alias sign and shared channel names. The canonical CSV exists only as a lossless-to-17-significant-digits numerical interchange for the unchanged `h1.verify` checker; raw MAT bytes and both hashes remain evidence. Aliases do not become independent physical measurements merely because they appear as separate columns. Incomplete names, invalid indices/layouts, inconsistent parameter endpoints, nonfinite data, ambiguous duplicate timestamps, insufficient precision and mismatched planned grids refuse.

No physical law, Modelica component, authored S1 input, reference value, tolerance, analysis policy, public observation or trusted checker is modified.

## Offline evidence and limitations

Prepared from current implementation candidate `h1/offline-validation` and the source branch `experiment/h1-cloud-s1-1270-once`. On existing Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0 under Linux, executed `python -B -m unittest discover -s h1/tests -q`: **118 tests passed**, including 13 new synthetic MATv4 checks and full synthetic S1 integration. Both MAT orientations, parameter and variable aliases, negative signs, time-base rows, refused corruption and unchanged numerical-checker status labels are tested.

**No actual OpenModelica MAT export has yet been read.** This code has offline/synthetic evidence only. The saved CSV run is retained; none of its missing variables has been invented or marked solved. Native evidence will be separately attributed to the newly approved attempt.

## Controlled one-shot workflow

Branch: `experiment/h1-cloud-s1-matv4-once`; workflow `.github/workflows/h1-s1-matv4-once.yml`. The workflow has only a path-scoped push trigger for its own branch, no pull-request/schedule/dispatch trigger, refuses reruns, uses read-only GitHub permissions and immutable pinned setup actions. Separate experimental PR; do not merge this single-use workflow.

- Ubuntu 24.04 GitHub-hosted ephemeral runner; OpenModelica **1.27.0**, MSL **4.0.0**; Python 3.13.5 with exact NumPy/SciPy pins.
- Reuse `tools/h1_cloud_s1.py preflight` (updated one-shot branch guard) for complete offline test rerun, original `.mo`/study/reference hashes and sealed expected results, all before native build.
- `tools/h1_mat_s1.py` allows exactly one explicit `omc --version` query, one `buildModel` with `outputFormat="mat"` and `variableFilter=".*"`, then at most one executable launch. All native stages have timeouts, no retries.
- MAT reader must furnish all 18 mandatory exports with source records. Convert to canonical CSV and call **unchanged** `h1.verify check` against the presealed reference. Always retain `nativeQualified=false` and `diagnostic_only` observations, even after a numerical diagnostic pass.
- Preserve preflight, logs, executable/init XML, exact raw MAT bytes, derived CSV, provenance sidecar, SHA-256 receipts, checker output and any error as one GitHub artifact. Package downloads occur only on the ephemeral cloud runner; this is not a network-isolated sandbox.

**Execution bounds:** one build, at most one launch, one explicit post-setup version query; stop on the first unexpected failure. A failed setup/build/MAT/schema/check attempt remains evidence and consumes this authorization. No version substitution, tolerance relaxation, physics edits, or further runs without a successor decision.

## Acceptance boundaries

The first native MAT run can qualify only its tested steady S1 compilation/export/diagnostic pathway. It cannot by itself establish reference-error bounds, independently approved checker manifest, robust transient simulation, the unknown C1 topology, classroom usefulness, or full charter-level composability. The previous CSV attempts, their failures, original source PDF and reference artifacts remain unchanged.

Primary references:
- https://github.com/OpenModelica/OpenModelica/blob/v1.27.0/doc/UsersGuide/source/technical_details.rst
- https://github.com/OpenModelica/OpenModelica/blob/v1.27.0/OMCompiler/SimulationRuntime/c/simulation/results/simulation_result_mat4.cpp
- https://github.com/OpenModelica/OpenModelica/blob/v1.27.0/OMCompiler/SimulationRuntime/c/simulation/results/simulation_result_csv.cpp
