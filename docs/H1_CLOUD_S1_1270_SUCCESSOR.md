# S1 cloud successor — OpenModelica 1.27.0 Linux

Date: 2026-11-15. User expressly authorized a corrected cloud attempt following [failed 1.27.1 run](https://github.com/physicsvigilante/sim_heat/actions/runs/43685828314). This is one additional attempt; **no further retries**.

The first attempt stopped during toolchain selection because the pinned OpenModelica setup action v1.2.0 lists **1.27.1 for Windows but not Linux**. No OMC build, simulation, or version query happened; the entire attempt is preserved in PR #4.

## Narrow successor

- Branch: `experiment/h1-cloud-s1-1270-once`, descendant of the first experiment's exact commit.
- Workflow: `.github/workflows/h1-s1-1270-once.yml`. Only a push of that workflow path on this branch triggers it. Reruns refuse via run-attempt gate. The old workflow only triggers on its old branch.
- Selected OpenModelica: **1.27.0 on Linux**, supported by the pinned action's `src/versions.json` (Linux `aptname=1.27.0-1`). Selected Modelica Standard Library: **4.0.0**.
- Correct the old workflow's library input: the action expects the bare line `Modelica 4.0.0`, not a string with literal single quotes.
- Preserve the original candidate S1 `.mo`, `study.json`, shared `SimHeat.mo`, reference data, physics input SHA-256 pins, solver settings and 18 mandatory exports. Only the branch guard, version and setup syntax change.
- Run exactly one offline preflight, then install on ephemeral runner, one recorded OMC version query, one build and at most one executable launch, each subject to a timeout. Do not retry or substitute another OMC version on failure.
- Retain all generated evidence; a missing/aliased native export or insufficient numerical precision remains a failure, not permission to synthesize data or change tolerances.

**Caveat:** A version present in setup-action inventory is not proof that its Linux APT repository supports this runner's Ubuntu distribution. The action must check repository support and may fail. Cloud setup uses network access to install dependencies; it is not a network-isolated sandbox.

This is an infrastructure/native-smoke experiment, **not** final H1 acceptance, independent R1/R2 recheck, H1 offline freeze, native numerical qualification, a generic unlimited runner, or evidence of charter-level unfamiliar composability. Keep all PRs including this one unmerged; merging is not necessary for the one-shot run.
