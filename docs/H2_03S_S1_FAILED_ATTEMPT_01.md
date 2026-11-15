# H2-03S S1 native attempt 01 — preflight refused (no OMC installation or launch)

**Actual GitHub Actions run:** https://github.com/physicsvigilante/sim_heat/actions/runs/43757179599

- Actual HEAD: `067227fb1d4f901c323562c683eecca566671be5` on `experiment/h2-s1-steady-native-once`.
- Workflow: `.github/workflows/h2-s1-steady-native-once.yml`, first attempt only, run `43757179599`.
- GitHub conclusion: **failure**, exact step `Verify 22 pinned source files and run full offline suite; seal reference BEFORE native work`.
- Exact error: `h1.model.Refusal: identity: source drift: h1/__main__.py` from `load_plan` before `prepare()` created its attempt directory. **No test suite ran, no reference was sealed, no `omc` installed or queried, no model build or launch performed**.
- Native execution budget actually used: **version queries 0, builds 0, launches 0**. The OpenModelica installation and native-execute workflow steps were skipped. Upload action emitted `No files were found`; **there is no ZIP artifact** for this refusal. The immutable original Actions job log is the evidence.
- Root cause independently inspected: the author manually entered an **incorrect pin** for `h1/__main__.py` in `tools/h2_s1_native_plan.json`. The plan recorded `8d34210829a49f7a34bd495a4c82000d45a1a428badbb715665186d2537e` while the actual source bytes independently hash to `8d34210829a49f7a34bd495a5a481f4e14b443bb9aa82794ef3332142c79e4b8`, matching historical pinned source.
- **Classification:** author-generated manifest transcription defect; no demonstrated physics/model change or source-file drift. The strict guard correctly rejected mismatched metadata. **Do not mark this run successful** or infer post-hoc tests.
- Original failed S1 MATv4 run `43689753800` and the prior post-hoc MAT diagnostic are unrelated and unchanged.

**Disposition:** This one-shot workflow **must not be rerun**. A corrected plan for a **fresh separately authorized successor** may be prepared and offline-verified, using a new branch and unique one-shot workflow identity. The owner has not approved such successor in this attempt record. Do not sneak the original one-shot launcher into the mainline viewer PR; do not claim a fourth native steady viewer case.
