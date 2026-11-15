# H1 one-shot S1 cloud execution — authorized scope and limitations

Date: 2026-11-15. Parent candidate: `0f30b1f9fdf20c5015c5c44a8e52459ed0b7c8e4` on `h1/offline-validation`.
**User authorization:** one GitHub-hosted S1 OpenModelica build and model launch, with temporary runner installation and retained evidence; optional merges only if needed. This does not authorize a second build, an automatic retry, or broader H1 native acceptance.

## Reproducible trigger and environment

The workflow `.github/workflows/h1-s1-once.yml` is restricted to a `push` changing **that workflow path** on branch `experiment/h1-cloud-s1-once`; the job refuses rerun attempts. It is not enabled on `main`, any pull request, a schedule, or a manual dispatch. Existing PR #3 remains unchanged; do **not** merge as a prerequisite to this experiment.

The one-shot execution stages are:
1. Checkout candidate; prepare offline Python 3.13.5 + NumPy 2.3.5 and SciPy 1.17.0 on the ephemeral runner. Reproduce the complete 105-test offline suite, verify source SHA-256 pins and offline S1 study admission. Seal the independent reference **before reading native output**. Failure stops execution before installation/build.
2. Install official OpenModelica 1.27.1 with MSL 4.0.0 using the version-pinned OpenModelica setup action. This installation may contact external package repositories. It does not modify the user's PC.
3. Make one explicit `omc --version` query. Run a single `.mos` containing one `buildModel(H1_S1, startTime=0, stopTime=1, numberOfIntervals=1, tolerance=1e-8, method="dassl", outputFormat="csv", variableFilter=".*")`; compile from the original source files, with no edits/parameter overrides. Do not launch if build fails, the executable is missing, or errors are reported.
4. Launch the resulting `H1_S1` executable once, with a two-minute process timeout and no retry. Preserve raw result bytes. If all mandatory native exports are actually present, check the result with the presealed generic `h1.verify` *diagnostic* pipeline without invented aliases, flows, or parameter values.
5. Upload the attempt directory as a GitHub Actions artifact even on failure (where available), including the compiler output, executable, init XML, raw CSV, reference artifact, hashes, logs, and the stage/failure manifest. There is no CI publishing step or push from the workflow.

**Bound:** one `buildModel` call / one launched model executable / one explicit post-install compiler version query; no automatic retry or fallbacks. OpenModelica setup may issue compiler/package-manager probes during toolchain installation, which are distinct from the recorded capability attempt. GitHub-hosted runners are ephemeral, but no OS-level network sandbox is claimed. Workflow `GITHUB_TOKEN` has read-only contents permission and checkout does not preserve credentials. Third-party actions are pinned to exact commit SHAs.

## Physical expectations and scope

S1 is a steady copper/steel series network. Reference (not native): junction 366.45628803245436 K; rod oriented flow +1.0792824946508015 W; boundary supplies cancel. The existing 18-export requirement includes both port flows and component constants. Real CSV may omit aliases/constants; that is an *export-schema failure*, not permission to make up them or to retry. A successful process exit is not native numerical acceptance. The checker only returns `diagnostic_only` and `nativeQualified=false`.

This experiment is a narrowly authorized *native smoke attempt* rather than final offline candidate freeze, completion of R3/R4/R5, or independent re-review of R1/R2. Even full S1 success does not qualify body initialization, physical-time transients, assembly transfer, or the broader composability charter. After results arrive, decide specific subsequent gates and whether any merge is warranted. If a native error occurs, record it and stop: propose a successor only with fresh explicit authorization.

## Action identity pins

- `actions/checkout`: `11bd71901bbe5b1630ceea73d27597364c9af683` (v4.2.2).
- `actions/setup-python`: `a26af69be951a213d495a4c3e4e4022e16d87065` (v5.6.0).
- `OpenModelica/setup-openmodelica`: `419f31141aa79a22f7033def5626047dd3bb5069` (v1.2.0, annotated signed tag).
- `actions/upload-artifact`: `ea165f8d65b6e75b540449e92b4886f43607fa02` (v4.6.2).

See `docs/H1_NATIVE_S1_PREPARATION.md`, `docs/H1_REVIEW_CORRECTIONS.md`, and `h1/evidence/r1r2/OFFLINE_REPORT.json`. The script is a one-shot host adapter; it does not change production thermal laws, authoring, observation logic, the validated `.mo` source, or any previous experiment report.
