# H2-03S · Reusable steady and transient thermal-network explorer

This is a **data-driven** static viewer for supported, previously admitted H1 thermal compositions. It now supports **two separate source-backed contracts**: untouched transient `sim_heat.viewer.native_case/1` and steady `sim_heat.viewer.steady_case/1`. The same renderer (`app.mjs`) and observation contract (`core.mjs`) handle different networks **without editing any application code**. New structures are represented by new case-bundle data, not special-purpose UI logic.

## Try it

From the root of `sim_heat`:

```sh
python -m http.server 8000
```

Open <http://localhost:8000/viewer/network/>. It includes the three original **historical transient diagnostics** — D1 (one finite body and reservoir), D2 (two finite bodies), DEV_BRIDGE (two boundaries and five rods) — and **S1**, the PDF Illustration 123 steady copper/steel series conductor. The original bridge-only prototype remains at `/viewer/`.

Choose a case and select a body, rod, junction or boundary. **Transient cases** allow scrubbing authentic saved times; **steady cases** show one native algebraic state with no time slider, playback or time-history charts. Both show available temperatures in K, signed rod/boundary power in W and, for finite bodies only, relative energy change in J. Node locations are **logical topology**, not apparatus geometry. Chart lines are a drawing convention, **not computed intermediate physics**. The case list and all graph structure/observed fields are data: `data/index.json` plus one `data/<case>.json` file per arrangement. A viewer change is **not** required to add a new supported arrangement **within one of these two versioned physical modes**.

Positive rod flow follows the authored `port_a → port_b` orientation. Positive boundary power is **supplied to the network**, negative boundary power is **absorbed from the network**. Stored-energy changes in J are only summed with other body J terms, never with W. No new energy-balance verdict is computed in the viewer.

## Data, original source and integrity

All previews were generated from **actual saved native CSVs** whose corresponding original archived ZIP, model/study bytes and `checks_passed` diagnostic records were SHA-matched. The source authorship and native check statuses remain explicit. D1/D2: [run 43691263273](https://github.com/physicsvigilante/sim_heat/actions/runs/43691263273), ZIP SHA-256 `8fc38b9e2f040b48ab5cbeab34e8698b7c99c4d462a1e31e8bc33b0395185379`. DEV_BRIDGE: [run 43699424883](https://github.com/physicsvigilante/sim_heat/actions/runs/43699424883), ZIP SHA-256 `f16975a25eea79f61f7819fb9e704ab04a33630044a51a0d062b8399c1c9ce38`.

The case manifests explicitly retain SHA-256 identities of original compiled Modelica and study descriptors, native CSV, raw MAT and ZIP artifact, historical run/commit, source of each observed channel, the sampled output grid and topology ports. All values are copied from the original native CSV; the adapter does not compute missing temperatures or Fourier fluxes. No claim of independent sensor measurement is made. Original traces are **diagnostic_only**, `nativeQualified=false`, not full H1 or classroom qualification.

The browser validates the manifest schema, channel units/roles, signed edges, graph referential integrity, sample grid, statuses and every bundle's exact SHA-256 against the tracked catalog. **This is integrity relative to versioned source data, not independent native-execution authentication.** For the original transient cases, choose the original `case_XX/normalized.csv` from the corresponding archived artifact and import it into the browser. For S1, the original canonical native CSV has **two algebraic evaluations** (backend indices 0 and 1) and one duplicate terminal row; they are **not seconds**, and importing the exact file only verifies the displayed steady state. The browser accepts it only after full **exact-byte** SHA-256 verification, duplicate-row and grid checks and equality against all displayed preview points. Files stay on the user's computer; no upload takes place. Historical GitHub artifacts may expire.

### Adding a supported case — data-only

With a trusted archived native run and unchanged, admitted H1 study, run the offline adapter. Example:

```sh
python -B viewer/network/tools/build_case.py \
  --study h1/cases/D1/study.json \
  --archive /path/to/pinned-native-run.zip \
  --archive-sha <recorded-full-zip-sha256> \
  --case-slot 1 --artifact-id <recorded-artifact-id> \
  --title 'An example body and reservoir' \
  --out viewer/network/data/ANOTHER_CASE.json
```

It requires the **same** Modelica/study bytes used in the real native launch, a passing historical native diagnostic record, every required exported quantity, exact canonical time grid, raw MAT/CSV SHA fingerprints, model/study pin consistency and correct provenance. It uses the existing `h1.study`, `h1.model.topology`, `h1.decoder` code without modifying them. It draws an ownerless junction using the already recorded native rod-end temperature and does not fabricate a new node state. Commit the new data file and add one entry to `data/index.json` with its SHA-256; the same JavaScript displays it. Do not silently repin historical execution plans. If no trustworthy native result exists, **refuse the view**—do not synthesize one from the reference.

## H2-03S — source-selected steady S1 with fresh successful native evidence

S1 is **Illustration 123** from the read-only `01_heat.pdf` (PDF page 2 / printed page 2.89). The original `h1/cases/S1/model.mo` and `study.json` specify 75-cm copper and 125-cm steel rods, common 2-cm diameter and fixed 100°C and 0°C boundaries. The source conductivities are written in kcal-based units; the already authored H1 model explicitly adopts **4184 J/kcal**. The printed source's heat-rate unit label is inconsistent with its kcal arithmetic and is not used as an SI numerical oracle.

A **new** authorized [S1 native successor run 43820600508](https://github.com/physicsvigilante/sim_heat/actions/runs/43820600508) completed successfully with one OpenModelica 1.27.0 build and launch using MSL 4.0.0. [Artifact 14204656273](https://github.com/physicsvigilante/sim_heat/actions/runs/43820600508/artifacts/14204656273), full ZIP SHA-256 `82b4a87b66e0022d582da931253649b3829f6633119a57081c02dc253dc5dbd9`, contained matching 89/89 original manifest file hashes. Original raw MAT SHA-256 `1d5ae021cf87eda8c14418b638e5cc3c353877358b52585deb7a0f7d375a0672`, original canonical CSV SHA-256 `1133504ba47df0d4b7fcaec46f090662027ff7feff6999401aad50dbd7d629d1`. The same generic checker passed **56/56 diagnostic comparisons** without changing physical inputs, numerical tolerances or source files. Earlier failed S1 runs remain failed history.

The new bundle `data/S1.json` copies **only the actual final algebraic evaluation**: junction temperature approximately **366.456288 K** and signed rod heat flow **+1.079282 W**, hot-supply positive, cold-absorption negative. Every value and the native source provenance are recorded; no result is computed by JavaScript. The junction is storage-free and its temperature is a recorded rod-end channel, **not** a fabricated junction sensor. No absolute rod shape, pose or extra dimensional geometry is inferred from this topological schematic.

The new read-only adapter `tools/build_steady_case.py` operates from a ZIP SHA-pinned, **successful** original native diagnostic attempt and the byte-identical admitted H1 study/model. It checks the original per-file SHA manifest, required MAT/CSV identity, saved evaluation semantics, native exit codes and diagnostic receipt. The output has no fake time array or storage values; a missing/unqualified native run refuses. To reproduce the S1 bundle from original archive:

```sh
python -B viewer/network/tools/build_steady_case.py \
  --study h1/cases/S1/study.json \
  --archive /path/to/h2-s1-steady-successor-evidence.zip \
  --archive-sha 82b4a87b66e0022d582da931253649b3829f6633119a57081c02dc253dc5dbd9 \
  --case-slot 1 --artifact-id 14204656273 \
  --title 'S1 · Copper and steel in series (steady)' \
  --out /tmp/S1-replayed.json
```

The resulting byte hash must equal the tracked `data/S1.json` SHA-256 **`eacab37b499a47c094cbd642acfee269a1bea7c82d16b15b9217a8c13ef1e4e7`**. This reproduces the saved **native data selection**, not a second solver run. The test-only `tests/fixtures/S1-native-normalized.csv` retains the exact original normalized CSV bytes so browser and Node tests can exercise authentic SHA checks without expiring artifact downloads.

Both mode contracts remain `diagnostic_only`, `nativeQualified=false`. This feature is not a native scientific qualification, independently certified reference error, unrestricted-model service, or classroom evaluation.

## Checks, scope and review

- `node --test viewer/network/tests/*.test.mjs`: all three original transient bundles plus the strict steady S1 case, hashes, graph uniqueness, signed direction, units, energy ownership, negative/refusal and synthetic parser tests.
- `python -B -m unittest discover -s viewer/network/tests -v`: adapter topology, unseen-junction and sample-selection tests.
- `python -B viewer/network/tests/browser_smoke.py --out /tmp/h2-02-images`: **real Chromium** desktop/mobile, four-case switch, keyboard/playback, reversal jump and SHA rejection.
- Project CI additionally runs 151 existing H1 and four analytical offline tests, with zero OpenModelica builds or launches. The original viewer/engine remains unchanged.

H2-03S is **R2 for a new steady-evidence presentation contract**, while H2-02 remains immutable historical scope and receives one separate-chat review through `review_sandbox`, after CI is green at exact commit SHA. Owner approval is still required for a merge. Physical solver ownership, reference error budgets, native qualification, unfamiliar-author C1 and classroom effectiveness remain out of scope. See [scope](../../../docs/H2_02_GENERIC_VIEWER_SCOPE.md).
