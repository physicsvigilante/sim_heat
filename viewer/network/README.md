# H2-02 · Reusable thermal-network explorer

This is a **data-driven** static viewer for supported, previously admitted H1 thermal compositions. The same renderer (`app.mjs`) and observation contract (`core.mjs`) handle different networks **without editing any application code**. New structures are represented by new case-bundle data, not special-purpose UI logic.

## Try it

From the root of `sim_heat`:

```sh
python -m http.server 8000
```

Open <http://localhost:8000/viewer/network/>. It includes three original **historical diagnostic** experiments: D1 (one body, one maintained reservoir, one conductor); D2 (two bodies, one conductor); and DEV_BRIDGE (two maintained reservoirs, two bodies, five conductors). The original bridge-only prototype remains at `/viewer/`.

Choose a case, select a body/rod/boundary, scrub its saved times, and inspect its actual temperature K, body energy change J, signed rod heat flow W or boundary power W. Node locations are **logical topology**, not apparatus geometry. Chart lines are a drawing convention, **not computed intermediate physics**. The case list and all graph structure/observed fields are data: `data/index.json` plus one `data/<case>.json` file per arrangement. A viewer change is **not** required to add a new supported physical arrangement.

Positive rod flow follows the authored `port_a → port_b` orientation. Positive boundary power is **supplied to the network**, negative boundary power is **absorbed from the network**. Stored-energy changes in J are only summed with other body J terms, never with W. No new energy-balance verdict is computed in the viewer.

## Data, original source and integrity

All previews were generated from **actual saved native CSVs** whose corresponding original archived ZIP, model/study bytes and `checks_passed` diagnostic records were SHA-matched. The source authorship and native check statuses remain explicit. D1/D2: [run 43691263273](https://github.com/physicsvigilante/sim_heat/actions/runs/43691263273), ZIP SHA-256 `8fc38b9e2f040b48ab5cbeab34e8698b7c99c4d462a1e31e8bc33b0395185379`. DEV_BRIDGE: [run 43699424883](https://github.com/physicsvigilante/sim_heat/actions/runs/43699424883), ZIP SHA-256 `f16975a25eea79f61f7819fb9e704ab04a33630044a51a0d062b8399c1c9ce38`.

The case manifests explicitly retain SHA-256 identities of original compiled Modelica and study descriptors, native CSV, raw MAT and ZIP artifact, historical run/commit, source of each observed channel, the sampled output grid and topology ports. All values are copied from the original native CSV; the adapter does not compute missing temperatures or Fourier fluxes. No claim of independent sensor measurement is made. Original traces are **diagnostic_only**, `nativeQualified=false`, not full H1 or classroom qualification.

The browser validates the manifest schema, channel units/roles, signed edges, graph referential integrity, sample grid, statuses and every bundle's exact SHA-256 against the tracked catalog. **This is integrity relative to versioned source data, not independent native-execution authentication.** For all 1,001/2,001 original saved samples, choose the original `case_XX/normalized.csv` from the linked GitHub archived artifact and import it into the browser. The browser accepts it only after full **exact-byte** SHA-256 verification, duplicate-row and grid checks and equality against all displayed preview points. Files stay on the user's computer; no upload takes place. Historical GitHub artifacts may expire.

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

## Checks, scope and review

- `node --test viewer/network/tests/*.test.mjs`: all three case bundles, hashes, graph uniqueness, signed direction, units, energy ownership, negative/refusal and synthetic parser tests.
- `python -B -m unittest discover -s viewer/network/tests -v`: adapter topology, unseen-junction and sample-selection tests.
- `python -B viewer/network/tests/browser_smoke.py --out /tmp/h2-02-images`: **real Chromium** desktop/mobile, three-case switch, keyboard/playback, reversal jump and SHA rejection.
- Project CI additionally runs 151 existing H1 and four analytical offline tests, with zero OpenModelica builds or launches. The original viewer/engine remains unchanged.

H2-02 is **R2 for a new generic evidence-presentation contract** and receives one separate-chat review through `review_sandbox`, after CI is green at exact commit SHA. Owner approval is still required for a merge. Physical solver ownership, reference error budgets, native qualification, unfamiliar-author C1 and classroom effectiveness remain out of scope. See [scope](../../../docs/H2_02_GENERIC_VIEWER_SCOPE.md).
