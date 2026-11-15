# H1 S1 cloud successor — Linux OpenModelica 1.27.0

**Authority:** The user explicitly approved one corrected cloud attempt after reviewing the stopped first attempt. This authorizes a new one-shot setup/build/launch attempt with Linux OpenModelica 1.27.0 and MSL 4.0.0 on an ephemeral GitHub Actions runner. It does not authorize automatic retries, broader H1 runs, or merges.

## Preserved first attempt

- [Run #43685828314](https://github.com/physicsvigilante/sim_heat/actions/runs/43685828314), commit `12cd18fb3c6e42c5572189964023504733fc87e0`: failed during **toolchain version selection** because the pinned `OpenModelica/setup-openmodelica` action has no Linux 1.27.1 entry.
- Offline suite, model hashes, study admission and reference preparation passed. **Zero Modelica builds and zero model launches**. Logs and the 16-file preflight artifact remain attached to the first run.
- First workflow and scripts remain historically visible in its commit. The corresponding [PR #4](https://github.com/physicsvigilante/sim_heat/pull/4) preserves both attempts without merge.

## Bounded successor correction

The same action at immutable commit `419f31141aa79a22f7033def5626047dd3bb5069` advertises Linux `1.27.0` with APT package `1.27.0-1`, while Windows advertises `1.27.1`. Select the existing Linux 1.27.0 entry rather than overriding the installer or silently using an unpinned release.

The action's `libraries` input is a newline-delimited `Modelica 4.0.0` without shell-style quote characters. This fixes the request's formatting (MSL 4.0.0 remains unchanged). Leave the interpreter/dependency pins, original authored model/study/physical values, build limits, exports, numerical checker, and one-shot no-retry rule unchanged.

The workflow runs only when its own file changes on the experimental branch, and `tools/h1_cloud_s1.py` refuses rerun attempts. The explicit native budget remains **one compiler build and at most one model executable launch** after offline preflight, including a single explicit `omc --version` query. Package installation/probes are setup, not claimed physical-model qualification.

**Stop conditions:** Failure to download/install OpenModelica or MSL, missing build outputs, missing native CSV exports, precision/sign/energy check failure, or any unexpected failure. Preserve artifact/log evidence. No fallback to another version and no further retry without a new decision.

**Acceptance limitation:** A successful smoke would still be narrower than H1 acceptance. The checker can only return `diagnostic_only`, `nativeQualified=false`. No C1 transfer, transient qualification, classroom claim, or merge is implied.

No new project production physics, authoring grammar, or observation operations are added. The charter's general compositional-transfer obligations remain separate.
