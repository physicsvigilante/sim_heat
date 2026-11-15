# SIM_HEAT

A compositional **heat-transfer teaching sandbox**. An author describes supported physical components, their connections and initial/boundary conditions; OpenModelica evaluates the native model; a separate reference and verification pipeline checks and labels the resulting observations.

## H1 integration candidate

The initial implementation supports ideal lumped heat-capacity bodies, storage-free conductive rods (area or circular cross-section), and fixed-temperature boundaries. It admits a deliberately small, typed Modelica composition grammar, one study descriptor with source provenance and public observation requests, and signed/conservation-aware checking. It **does not** accept unrestricted Modelica programs, invent missing physical inputs, or replace the numerical solver with an LLM answer.

This repository now contains the *candidate source and offline tests*. The historical H0/H1 draft documents under [docs/](docs/) describe stages at the time they were written; earlier "not implemented" notices there are historical, not an accurate statement about this integration candidate. **Source presence and passing diagnostics do not mean final H1 qualification.** The checker deliberately labels results `diagnostic_only` and `nativeQualified=false`.

The entire implementation has previously been exercised using OpenModelica **1.27.0** and Modelica Standard Library **4.0.0** on explicitly bounded cloud runs. Real native evidence and failures remain linked to the original GitHub Actions runs and experimental PRs, not copied into Git history:
- [Steady S1 MATv4 exploration](https://github.com/physicsvigilante/sim_heat/pull/6) — original workflow failure and saved-output diagnostic recovery.
- [D1/D2 native transients](https://github.com/physicsvigilante/sim_heat/actions/runs/43691263273).
- [Conductivity/resolution campaign](https://github.com/physicsvigilante/sim_heat/actions/runs/43693191224).
- [Developer-authored thermal bridge](https://github.com/physicsvigilante/sim_heat/actions/runs/43699424883) — new topology, 98 diagnostic checks passed; **not** an independent author test.
- [H1-C1 technical freeze](qualification/h1_c1/FREEZE.md) — reserved external-author challenge not yet selected or executed.

## Offline usage

From the repository root, with Python 3.13.5, NumPy 2.3.5 and SciPy 1.17.0:

```bash
python -B -m unittest discover -s h1/tests -v
python -B -m unittest discover -s experiments/h1_spike/checks -v
python -B -m h1 h1/cases/D2/study.json --root h1/cases
python -B -m h1 h1/cases/DEV_BRIDGE/study.json --root h1/cases
```

Admission prints a status report, **not calculated temperatures or simulated results**. No local compiler installation or native execution is triggered by these commands.

The checking-only reference can be prepared without a native run:

```bash
python -B -m h1.verify prepare \
  --study h1/cases/DEV_BRIDGE/study.json --root h1/cases \
  --reference experiments/dev_bridge/reference/DEV_BRIDGE.json \
  --out /tmp/h1-bridge-reference.bundle.json
```

That preparation is not independent validation or a native result. See [H1 implementation contract](docs/H1_IMPLEMENTATION_CONTRACT.md), [H1 code notes](h1/README.md), and [H2-00 source-integration record](docs/H2_00_INTEGRATION_SCOPE.md) for the exact allowed domain and pending gates.

## Runtime and CI boundaries

[`h2-h1-offline-ci.yml`](.github/workflows/h2-h1-offline-ci.yml) runs the current offline suite, arithmetic checks and a bridge study/reference smoke on pushes to its integration branch and to `main`. It cannot build or launch OpenModelica. **No historical one-shot native workflow is installed here as an active production trigger.** The reusable native batch helper is restricted to explicit pinned, host-checked execution plans and is **not** run by standard CI.

The project is not yet an interactive viewer, general symbolic or inverse solver, or unrestricted physics authoring environment. Classroom usefulness and an independent-author transfer case remain untested. Read-only original source [01_heat.pdf](01_heat.pdf) is preserved; its inclusion does not grant redistribution rights or introduce a project license.

## Development and independent review

Developer Chat A creates a tested draft PR in `sim_heat`. Risk-based separate-chat reviews use [review_sandbox](https://github.com/physicsvigilante/review_sandbox), with an immutable source SHA and one report authored directly by reviewer Chat B. **Only the owner approves a production merge.** Details: [AGENTS.md](AGENTS.md) and [H2-00 issue](https://github.com/physicsvigilante/sim_heat/issues/11).