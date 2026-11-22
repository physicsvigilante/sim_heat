# SIM_HEAT

A compositional **heat-transfer teaching sandbox**, with a read-only thermal-network explorer and a deliberately restricted Modelica authoring and verification pipeline. This is not a general-purpose thermodynamics engine.

## Start exploring

Work through three [JEE-style conduction problems](docs/JEE_CONDUCTION_WALKTHROUGH.md) with predictions, hand calculations and runnable offline checks for a composite wall, a thermal bridge and two insulated bodies.

Investigate [when a composite wall stops carrying 120 W](docs/JEE_PHASE_WALL.md) as a finite hot bath freezes and ice melts. Follow the heat through each rod, then change the ice mass to reverse the order of phase depletion.

Solve [whether a bath can freeze inside a warmer enclosure](docs/JEE_SUPPORTED_RADIATING_WALL.md) by balancing radiation at a face and conduction into a cold support.

Find the contact temperature jump and radiating surface temperature in a [worked furnace-wall problem](docs/JEE_FURNACE_WALL.md).

Test [whether adding insulation can melt ice faster](docs/JEE_RADIAL_PHASE_VESSEL.md) across a radial shell's critical radius, day/night cycles, and inverse film calibration from melted mass.

From the repository root:

```bash
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/` for the [start page](index.html). Its primary link opens the existing [thermal explorer](viewer/network/index.html); the second opens the [saved conductivity comparison](viewer/network/compare.html). No OpenModelica installation is needed for archived playback. The server serves static files, not a solver.

The [capability and evidence registry](docs/CAPABILITIES.md) is the current product inventory. It separates **archived native diagnostics**, **admitted authored-source previews**, **analytical checking data**, **offline analytical thermal tools**, and **expected-only source views**, with links to the original records. The dated [November 17 audit](docs/PROJECT_AUDIT_2026_11_17.md) is preserved as history rather than silently rewritten into a new result.

The previous direct route still works: serve `viewer/network` with `python -m http.server 8000 --bind 127.0.0.1 --directory viewer/network` or open `/viewer/network/` from the repository-root server. The older bridge-only prototype remains at `/viewer/`.

## What works now

The same data-driven explorer displays six source-linked archived native diagnostic cases: D1, D2, DEV_BRIDGE, steady S1, TEACH_RING4 and D2_K2. It supports case switching, saved-time playback, temperature/flow/energy inspection, reversal markers, exact original-CSV hash checking and the saved D2 versus D2_K2 comparison. It does not launch simulations or invent readings between saved samples.

The physical library for **native H1 Modelica authoring** supports ideal lumped heat-capacity bodies, storage-free conductive rods with area or circular cross-section, and fixed-temperature boundaries. Supported combinations are source-authoring tasks, not new apparatus-specific solver or renderer implementations. The small typed grammar checks ports, topology, explicit initial/boundary conditions, provenance and public observations. See the [H1 contract](docs/H1_IMPLEMENTATION_CONTRACT.md) and [offline amendment](docs/H1_OFFLINE_AMENDMENT.md).

Separately, **offline analytical Python tools** under `tools/` compose pinned steady/transient conduction networks with radial shells, diffuse-gray radiation and concentric shields, prescribed convective films, coexisting two-phase baths, multi-stage day/night schedules, lumped body-phase transients, and scoped interval inverse calibrations. These are offline analytical calculations (`nativeExecuted=false`, `nativeQualified=false`), not native OpenModelica simulations or browser-simulated cases; see the [capability registry](docs/CAPABILITIES.md) for the full breakdown.

**Published results remain `diagnostic_only` and `nativeQualified=false`.** Actual archived solver execution is not independent measurement, universal numerical qualification or classroom validation. The [viewer guide](viewer/network/README.md) retains original run/artifact hashes, source provenance and operation limits. Arbitrary CSV files are not accepted as native evidence.

## Keep C1 separate

The frozen H1-C1 external-author experiment and its historical offline/viewer tools are separate from the working main explorer. Its nine native public readings remain uncomputed. The original reference precision was 80 times against a required minimum of 100 times; later cross-host regeneration also failed to reproduce the exact original saved V2 seal. Those failures remain unchanged. The original adopted reference is for offline checking only; no alternate seal is silently adopted.

Read the [original C1 freeze](qualification/h1_c1/FREEZE.md) as a historical stage record, not the whole project's current capability checklist. Do not merge the historical qualification stack wholesale. The corrected PR51 + PR52 audit integration does not grant any new native execution permission.

## Offline development checks

With Python 3.13.5 and the [pinned checking dependencies](requirements-h1-ci.txt):

```bash
python -B -m unittest discover -s h1/tests -v
python -B -m unittest discover -s experiments/h1_spike/checks -v
python -B -m unittest discover -s viewer/network/tests -p 'test_*.py' -v
python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test viewer/tests/*.test.mjs viewer/network/tests/*.test.mjs
python -B -m h1 h1/cases/D2/study.json --root h1/cases
python -B tools/render_product_docs.py --check
```

Admission prints a descriptor/topology report, not simulated temperatures. Ordinary reference preparation makes checking data, not native evidence; never regenerate a frozen/adopted C1 reference while replaying evidence. "Offline" means no native simulation, not air-gapped dependency installation.

With the existing pinned Playwright/Chromium checking environment, run `python -B tests/browser_product_entry.py --out /tmp/simheat-entry-smoke` for start-page navigation, and `python -B viewer/network/tests/browser_smoke.py --out /tmp/simheat-explorer-smoke` for the full existing explorer checks. These run a static local HTTP server, not OpenModelica.

## Scope and next direction

No native OpenModelica convection/radiation/phase library, browser-launched solver, fluid-flow/CFD engine, moving-boundary Stefan solver, blackbody spectral/Wien solver, general symbolic/inverse solver, moving mechanics, arbitrary temperature-dependent material law, unrestricted Modelica service, or autonomous natural-language-to-validated-simulation workflow is implemented. Teacher usability and blind unfamiliar-author transfer remain unproven.

The next milestone is one unfamiliar supported composition through authored source, admission, faithful source visualization, separately authorized native execution, saved-reference checks and inspectable results. Do not substitute more mock authorization demonstrations for completing that task. Any native attempt needs a separately approved bounded plan and relevant independent review.

## Development and review

Develop and test in this repository. Publish a draft PR with exact source and CI, then use risk-based independent review in [review_sandbox](https://github.com/physicsvigilante/review_sandbox). Batch related work. Only the owner approves production merges; preserve original inputs, failed runs and scientific evidence. See [AGENTS.md](AGENTS.md).

The original [01_heat.pdf](01_heat.pdf) is preserved. Its presence does not grant redistribution rights or introduce a project license.
