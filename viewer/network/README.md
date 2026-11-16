# H2-03S · Reusable steady and transient thermal-network explorer

This is a **data-driven** static viewer for supported, previously admitted H1 thermal compositions. It now supports **two separate source-backed contracts**: untouched transient `sim_heat.viewer.native_case/1` and steady `sim_heat.viewer.steady_case/1`. The same renderer (`app.mjs`) and observation contract (`core.mjs`) handle different networks **without editing any application code**. New structures are represented by new case-bundle data, not special-purpose UI logic.

## Try it

From the root of `sim_heat`:

```sh
python -m http.server 8000
```

Open <http://localhost:8000/viewer/network/>. It includes the three original **historical transient diagnostics** — D1 (one finite body and reservoir), D2 (two finite bodies), DEV_BRIDGE (two boundaries and five rods) — **S1**, the PDF Illustration 123 steady copper/steel series conductor, and **TEACH_RING4**, a developer-authored four-body conductive ring with one diagonal rod and a hot reservoir. Ring4 is an illustrative extension of the conduction mechanism, **not** an actual textbook question or a held-out C1 author trial. The original bridge-only prototype remains at `/viewer/`.

Choose a case and select a body, rod, junction or boundary. **Transient cases** allow scrubbing authentic saved times; **steady cases** show one native algebraic state with no time slider, playback or time-history charts. Both show available temperatures in K, signed rod/boundary power in W and, for finite bodies only, relative energy change in J. Node locations are **logical topology**, not apparatus geometry. Chart lines are a drawing convention, **not computed intermediate physics**. The case list and all graph structure/observed fields are data: `data/index.json` plus one `data/<case>.json` file per arrangement. A viewer change is **not** required to add a new supported arrangement **within one of these two versioned physical modes**.

Positive rod flow follows the authored `port_a → port_b` orientation. Positive boundary power is **supplied to the network**, negative boundary power is **absorbed from the network**. Stored-energy changes in J are only summed with other body J terms, never with W. No new energy-balance verdict is computed in the viewer.

## Data, original source and integrity

All previews were generated from **actual saved native CSVs** whose corresponding original archived ZIP, model/study bytes and `checks_passed` diagnostic records were SHA-matched. The source authorship and native check statuses remain explicit. D1/D2: [run 43691263273](https://github.com/physicsvigilante/sim_heat/actions/runs/43691263273), ZIP SHA-256 `8fc38b9e2f040b48ab5cbeab34e8698b7c99c4d462a1e31e8bc33b0395185379`. DEV_BRIDGE: [run 43699424883](https://github.com/physicsvigilante/sim_heat/actions/runs/43699424883), ZIP SHA-256 `f16975a25eea79f61f7819fb9e704ab04a33630044a51a0d062b8399c1c9ce38`. Ring4: [native run 43845664024](https://github.com/physicsvigilante/sim_heat/actions/runs/43845664024), original artifact 14215520616, full ZIP SHA-256 `0bc1433be66df2827f8907d100ca264f6a721fe8ad40644b962500b97fa9b8b2`.

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

The new read-only adapter `tools/build_steady_case.py` operates from a ZIP SHA-pinned, **successful** original native diagnostic attempt and the byte-identical admitted H1 study/model. After Chat B's PR #16 Review 01, it now enforces **complete archived-member/SHA-manifest coverage**, checks the original presealed reference file digest and matching seals, and **recomputes the entire saved numerical verification and public-request receipt using the unchanged generic H1 checker**. Contradictory `passed` flags, request values, reference seals, omitted mandatory files and missing archive members refuse. The output has no fake time array or storage values. This read-only verification neither executes OMC nor independently certifies reference accuracy.

**Provenance trust boundary:** The archive's internal `GITHUB_RUN_ID` and `GITHUB_SHA` are self-described metadata. Supply `--expected-run-id` and `--expected-commit-sha` from the **separately checked GitHub Actions run**, together with the externally verified original full-ZIP digest and artifact ID. The adapter checks that the archive agrees with these supplied identities; it does **not** contact GitHub or establish that an arbitrary newly repinned ZIP originated from an authenticated physical measurement. A person/process must independently check the GitHub run/artifact/commit before accepting newly supplied evidence. To reproduce S1 from its separately verified original archive:

```sh
python -B viewer/network/tools/build_steady_case.py \
  --study h1/cases/S1/study.json \
  --archive /path/to/h2-s1-steady-successor-evidence.zip \
  --archive-sha 82b4a87b66e0022d582da931253649b3829f6633119a57081c02dc253dc5dbd9 \
  --case-slot 1 --artifact-id 14204656273 \
  --expected-run-id 43820600508 \
  --expected-commit-sha 337ef554fb40da9408485bda8f2a4024c84720f6 \
  --title 'S1 · Copper and steel in series (steady)' \
  --out /tmp/S1-replayed.json
```

The resulting byte hash must equal the tracked `data/S1.json` SHA-256 **`eacab37b499a47c094cbd642acfee269a1bea7c82d16b15b9217a8c13ef1e4e7`**. This reproduces the saved **native data selection**, not a second solver run. The test-only `tests/fixtures/S1-native-normalized.csv` retains the exact original normalized CSV bytes so browser and Node tests can exercise authentic SHA checks without expiring artifact downloads.

Both mode contracts remain `diagnostic_only`, `nativeQualified=false`. This feature is not a native scientific qualification, independently certified reference error, unrestricted-model service, or classroom evaluation.

## H3 — Four-body teacher-authored ring, genuine transient native evidence

The fixed [teacher task](../../../experiments/teacher_ring4/TASK.md) was committed **before** the first `TeacherRingFour` model and study; it describes the one-reservoir + four-body A–B–C–D–A conducting ring with an A–C shortcut. All masses, heat capacities, initial states, rod conductivities, lengths and areas are **illustrative inputs**. The problem tests composability of supported components, not a literal book illustration, a held-out blind-author transfer or an arbitrary physical law.

A separate, owner-approved [OpenModelica run 43845664024](https://github.com/physicsvigilante/sim_heat/actions/runs/43845664024) compiled and executed the **unchanged** first-authored Modelica source in one version query, one build, one launch. [Original ZIP artifact 14215520616](https://github.com/physicsvigilante/sim_heat/actions/runs/43845664024/artifacts/14215520616), SHA-256 **`0bc1433be66df2827f8907d100ca264f6a721fe8ad40644b962500b97fa9b8b2`**, retains 88/88 verified original native source/member hashes. Native raw MAT SHA-256 `6ed17558911379b0be0d85f46e1a00d9ce3cac8aca0513fe3d5fd9209156af5b`, normalized CSV SHA-256 `31b3f77dca6227462505c548907f9cf7ed7b620f8b23d73ba8ea9953f52d87d7` (`1,962,266` original bytes). Exactly **126/126** H1 diagnostics and 15 public observations passed at the unchanged numerical policy; all remain **`diagnostic_only`, `nativeQualified=false`**. This does not independently certify native accuracy or measure a physical apparatus.

The [fifth original-native data bundle](data/TEACH_RING4.json) includes 5 graph nodes, 6 oriented rods, 4 finite body `ΔU` channels and a boundary W channel. **29 authentic saved samples from 2,001 physical-time samples** include both sides of four observed sign reversals: `ringDA` 336–348 s, `ringAB` 756–768 s, `ringCD` 1956–1968 s, `ringBC` 3984–3996 s. No exact unsampled zero instant is claimed and no case-name-specific renderer code was added. The UI illustrates *logical* connectivity, not literal rod positions or lengths.

A small **generic archive-read compatibility** addition to `tools/build_case.py` reads original SHA-pinned ZIPs with either a root-level `attempt.json` (legacy D1/D2/bridge) or one nested native-attempt directory (new GitHub Actions multi-folder artifact); original whole-ZIP digest and bytes are untouched and no archives are silently re-packed. The new input-layout path does **not** infer missing native data or change the H1 checker. To regenerate the new bundle against the **original full GitHub ZIP**, after downloading/verifying its run, exact SHA and source:

```sh
python -B viewer/network/tools/build_case.py \
  --study h1/cases/TEACH_RING4/study.json \
  --archive /path/to/h3-ring4-native-successor-evidence.zip \
  --archive-sha 0bc1433be66df2827f8907d100ca264f6a721fe8ad40644b962500b97fa9b8b2 \
  --case-slot 1 --artifact-id 14215520616 \
  --title 'Ring4 · four bodies, loop and shortcut' \
  --out /tmp/TEACH_RING4-replayed.json
```

The generated byte SHA-256 must equal **`b4f46b2953409980ea5d5ed1b41cafaf5a7504003da44038d9d51286bb6e8a34`**. This is an offline selection of **actual original native readings**, not a new simulation. Independently, the unchanged `parseNativeCsv` accepted all 2,001 full authentic native saved time points from the 1,962,266-byte original CSV and checked the preview after its exact hash.

The original one-shot [43843168327](https://github.com/physicsvigilante/sim_heat/actions/runs/43843168327) failed *before* native execution due a preflight synthetic-fixture inventory mistake; the original failure and related failed offline CI remain preserved. A separate author-approved successor ran exactly once after a data-only correction and new offline qualification. This fifth case does **not** advance blind H1-C1 transfer, R3 scientific error certification, symbolic inverse solving or classroom effectiveness. See the [full evidence report](../../../experiments/teacher_ring4/NATIVE_SUCCESSOR_RESULTS.md) and [R2 scope](../../../docs/H3_RING4_COMPOSITION_VIEWER_SCOPE.md).

## Checks, scope and review

- `node --test viewer/network/tests/*.test.mjs`: all three original transient bundles plus the strict steady S1 case, hashes, graph uniqueness, signed direction, units, energy ownership, negative/refusal and synthetic parser tests.
- `python -B -m unittest discover -s viewer/network/tests -v`: adapter topology, unseen-junction and sample-selection tests.
- `python -B viewer/network/tests/browser_smoke.py --out /tmp/h2-02-images`: **real Chromium** desktop/mobile, four-case switch, keyboard/playback, reversal jump and SHA rejection.
- Project CI additionally runs 151 existing H1 and four analytical offline tests, with zero OpenModelica builds or launches. The original viewer/engine remains unchanged.

H2-03S is **R2 for a new steady-evidence presentation contract**, while H2-02 remains immutable historical scope and receives one separate-chat review through `review_sandbox`, after CI is green at exact commit SHA. Owner approval is still required for a merge. Physical solver ownership, reference error budgets, native qualification, unfamiliar-author C1 and classroom effectiveness remain out of scope. See [scope](../../../docs/H2_02_GENERIC_VIEWER_SCOPE.md).
