# SIM_HEAT

A compositional **heat-transfer teaching sandbox**, with a working read-only
thermal-network explorer and an intentionally restricted Modelica authoring
and verification pipeline. This is not a general-purpose thermodynamics engine.

## What works now

The [network explorer](viewer/network/index.html) displays **six source-linked
archived native diagnostic cases**: D1, D2, the developer thermal bridge, steady
S1, the four-body teacher ring, and the D2-K2 conductivity revision. It supports
case switching, saved-time playback, temperature/flow/energy inspection, flow
reversal markers, original-CSV hash checking and a [saved what-if comparison](viewer/network/compare.html).
It selects **previously archived OpenModelica output**; it does not launch a solver
from the browser or invent values between saved samples.

The supported physical library contains ideal lumped heat-capacity bodies,
storage-free conductive rods with area or circular cross-section, and fixed-
temperature boundaries. The engine admits a small typed Modelica grammar,
port connections, explicit initial/boundary conditions, provenance and public
observation requests. It checks topology, units, source identity, signed flows,
energy accounting and numerical comparisons. New supported combinations are
source-authoring tasks, not new apparatus-specific renderer code.

**Evidence labels matter:** published cases remain `diagnostic_only` and
`nativeQualified=false`. Actual archived solver execution is not the same as
independent numerical qualification, a measured apparatus or a classroom trial.
See [the viewer guide](viewer/network/README.md) for original run/artifact hashes,
source provenance, supported operations and limits.

## Run the read-only explorer

From the repository root:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory viewer/network
```

Open `http://127.0.0.1:8000/` in a browser. This local server serves static
JavaScript/data, not OpenModelica. An imported full CSV must match its original
recorded SHA-256; an arbitrary file is not accepted as native evidence.

## Keep the three development tracks distinct

| Track | Status | What it does not establish |
|---|---|---|
| `main`: H1 engine and H2/H3 explorer | Implemented source, six original archived diagnostic cases and saved comparison | Unrestricted physics, independently certified native accuracy or arbitrary browser-run simulations |
| Frozen H1-C1 first-author experiment | Submission and offline evaluation exist on separate qualification branches; original failures retained | A successful C1 native transfer or nine computed C1 public readings |
| Unmerged C1 offline/viewer experiments | Source-bound expected fields, request dependencies, topology and nonphysical schematic | Actual C1 solver output, physical pose/geometry, owner execution permission or a durable global launch lock |

The C1 first-attempt reference error margin was **80× against a required ≥100×**;
that failure is not rewritten. Later cross-host reproduction did not reproduce
the exact original saved V2 reference seal. The owner-adopted original saved
reference is approved **for offline checking only**. Historical qualification
branches must not be merged wholesale into `main`.

Earlier H0/H1 documents and [the original C1 freeze](qualification/h1_c1/FREEZE.md)
are historical stage records, not a current feature checklist. See the
[project audit and forward plan](docs/PROJECT_AUDIT_2026_11_17.md) for the current
capability boundary and tested corrections.

## Offline development checks

With Python 3.13.5 and [pinned checking dependencies](requirements-h1-ci.txt):

```bash
python -B -m unittest discover -s h1/tests -v
python -B -m unittest discover -s experiments/h1_spike/checks -v
python -B -m unittest discover -s viewer/network/tests -p 'test_*.py' -v
node --test viewer/tests/*.test.mjs viewer/network/tests/*.test.mjs
python -B -m h1 h1/cases/D2/study.json --root h1/cases
```

Admission prints a descriptor/topology report, **not simulated temperatures**.
Reference preparation is a checking-data operation, not a substitute for a native
solver. Never regenerate a frozen/adopted C1 reference while replaying evidence.
The prospective corrective CI also exercises real Chromium and read-only replay
of the existing archived native data; it never installs or invokes OpenModelica.
“Offline” here means no physical/native simulation, not air-gapped dependency
installation.

## Limitations and next direction

No general symbolic or inverse solver, convection/radiation library, fluid flow,
phase change, moving mechanics, unrestricted Modelica service or autonomous
natural-language-to-validated-model workflow is implemented. Teacher usability
and blind unfamiliar-author transfer remain unproven. Next work should consolidate
the existing explorer and real evidence path, not add more toy authorization
layers. A new native attempt requires a separately approved, bounded plan and
appropriate independent review; this audit grants no such permission.

The original [01_heat.pdf](01_heat.pdf) is preserved; its presence does not grant
redistribution rights or introduce a project license.

## Development and review

Develop and test in this repository. Publish a draft PR with an exact SHA, then
use risk-based independent review in [review_sandbox](https://github.com/physicsvigilante/review_sandbox).
Batch related corrections into coherent milestones. **Only the owner approves
production merges.** Preserve original source submissions, failed runs and
scientific evidence. See [AGENTS.md](AGENTS.md).
