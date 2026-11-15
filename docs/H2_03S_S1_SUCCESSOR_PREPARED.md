# H2-03S — S1 successor prepared, not launched

**Status: pending new explicit owner approval. No new OpenModelica attempt.**

## Why a successor exists

The first owner-authorized [one-shot run #43757179599](https://github.com/physicsvigilante/sim_heat/actions/runs/43757179599), source SHA `067227fb1d4f901c323562c683eecca566671be5`, **failed during exact-plan input validation** before offline tests, reference sealing or native installation. Cause: a manually mistyped SHA-256 pin for `h1/__main__.py` in the new execution manifest. It was not caused by a changed source file or physics. Zero OMC version queries, zero builds, zero launches. There was no ZIP artifact because the attempt directory had not yet been created. Original job logs and [failure report](https://github.com/physicsvigilante/sim_heat/blob/experiment/h2-s1-steady-native-once/docs/H2_03S_S1_FAILED_ATTEMPT_01.md) are unchanged.

The source SHA-256 for `h1/__main__.py` is **`8d34210829a49f7a34bd495a5a481f4e14b443bb9aa82794ef3332142c79e4b8`**, as independently computed from its exact GitHub content and as recorded in the earlier successful D1/D2 native plan. The erroneous original pin was `8d34210829a49f7a34bd495a4c82000d45a1a428badbb715665186d2537e`.

## Corrected candidate

- New distinct branch: `experiment/h2-s1-steady-native-successor-once`.
- Corrected plan: `tools/h2_s1_native_plan_v2.json`, SHA-256 `9ebeab496f3b7ea22ec5de59acc6983a6062d26be1546cf0ac3b9c9a698f0d7b`.
- All **22 input pins** from the original plan were independently recomputed from GitHub source; **21 matched**. Only `h1/__main__.py` differed, and that one was corrected. Other pins retain their source values.
- Source S1 model, study, independent reference, physics library, numerical/checking implementation, compiler/MSL selections, per-case analysis and tolerances are **unchanged**.
- New output directory `h2_s1_native_successor_attempt` and new branch prevent overwriting old attempt evidence. The old one-shot workflow exists only on the original experiment branch.
- **No successor trigger/workflow has been created**; this commit is preparatory, not a native test. No new CI/preflight or model build has been counted as successful.

## Proposed successor budget — requires separate authorization

At most one compiler version query, one OpenModelica 1.27.0 model build, and one model launch using MSL 4.0.0, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0 on a fresh ephemeral Ubuntu GitHub runner. The unchanged generic batch runner must enforce the plan SHA, exact source pins, presealed S1 reference, stage/status guards, process limits, stop-on-first-failure and no retry. The workflow must be branch/path gated on a new uniquely named file, exclude manual or scheduled dispatch, archive genuine failure/success data and never be merged to `main`.

**Next decision:** Request the owner's explicit approval for this new one-shot successor. Upon approval only, create the unique trigger and check results. Do not claim native qualification or a fourth viewer case until a truly successful, traceable native artifact exists.
