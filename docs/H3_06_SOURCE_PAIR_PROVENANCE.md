# H3-06 — Generic native comparison source-pair provenance, v2

**Issue:** [#22](https://github.com/physicsvigilante/sim_heat/issues/22)  
**Base:** `main` at `69350dab2a6faf0c10d0c0aa1d2333051f40e0e9`, after independently reviewed H3-04 and test-only H3-05.  
**Risk:** **R2** — new strict versioned comparison evidence-presentation contract, not new physics or solver capabilities. A source PR requires pinned exact-head CI, independent Chat B review and post-merge verification.

## Task and boundary

The teacher-facing what-if comparison must not become a growing list of privately hard-coded apparatuses or a self-attesting source of measurements. A source-pair needs *two separately already-admitted native cases*, with an H1-admitted parent/successor physical revision, truthful native identity on each side, compatible graph owners and saved times, and refusal if any source of evidence changes.

This milestone **does not** add a seventh physical arrangement, a new Modelica component, a second published source-pair, arbitrary parameter editing, new native OpenModelica builds, external host attestation, symbolic/inverse solving or independent H1-C1 transfer. The original six `viewer/network/data/<case>.json` source-linked bundles and `h1/` code/tests remain byte-identical.

## New offline publication gate

- `viewer/network/data/compare_sources.json` is a **strict source manifest** with an explicit baseline and successor case ID, repository-relative H1 study paths and exact *externally checked* native source identities (run, artifact, executed commit, full original ZIP SHA-256, MAT/CSV SHA-256, case archive entry). The repository's manifest is a source-relative trust assertion, **not** a cryptographic attestation by GitHub.
- `viewer/network/tools/build_compare_index.py` is a deterministic **read-only, generic** compiler. It uses the unchanged `h1.study.load_study` on the real original parent and successor Modelica/study descriptors. H1 checks the complete parent hashes, the direct `revision`, `origin="hypothetical"`, one changed effective existing rod `k`, unchanged component identities/types/topology and physical bindings.
- The compiler additionally requires the same study mode, actual physical-time grid, unchanged public requests/analysis, an original parent *without its own revision*, and original native source-case bytes matching the six-case catalog SHA-256. It checks each case's Modelica name and H1 source hashes, derivation of graph nodes and oriented rods through the same generic `owner_graph`, exact native channel set, strictly ordered preview times from the **true H1 grid**, start and end instants, valid original K/W/J channels, genuine `diagnostic_only` and `nativeQualified=false`. The two cases must share recorded preview times, graph owners/ports, observation column order and initial/maintained body temperatures. It computes no simulation values.
- The output `viewer/network/data/compare_index.json` uses **`sim_heat.viewer.compare_index/2`**, with `sources.baseline` and `sources.successor` pinned to the exact original native metadata. `revision.before` and `revision.after` are derived from the actual H1 Modelica effective `k`, and parent/child model/study hashes and reason come from the admitted H1 revision. It does not accept arbitrary self-entered numbers in the public comparison index.
- To deterministically reproduce from checked-in source:

```sh
python -B viewer/network/tools/build_compare_index.py \
  --out /tmp/compare-index-replayed.json
cmp viewer/network/data/compare_index.json /tmp/compare-index-replayed.json
```

These commands run **no native Modelica simulation**. The source branch CI executes them before all tests and archives the replay file and exact source SHA.

## Native evidence identity and lawful same-run comparison

There is **no blanket requirement for two different GitHub runs**: an already verified single native run/artifact can contain two distinct case output slots, and same-run different-artifact records can exist. For two sides citing the *same original artifact ID*, the externally supplied run and original whole ZIP SHA-256 must agree, while the selected `archiveEntry` must differ. Two sides may **never** resolve to the exact same `(runId, artifactId, archiveEntry)` result slot. A reused artifact ID with conflicting run/ZIP identity is refused. Distinct native run IDs alone do **not** establish independent measurements or trustworthy origins.

The browser's `compare_core.mjs` now validates the v2 source tuple and **matches each original native case's run, artifact, original ZIP digest, executed commit, MAT digest, CSV digest and saved archive-entry path to the pair manifest**, *before* displaying recorded numbers. It additionally retains the original strict case validator, source-model/study SHA checks, graph/port/quantity ownership checks, public diagnostic-only status, corresponding physical saved timestamps and initial relative energies. The generic `compare.mjs` has no per-apparatus names and no Modelica evaluation. Existing generation/epoch stale-fetch guards remain in place.

This is **source-relative integrity**: an attacker repinning an invented original ZIP, original case JSON, source manifest and caller-supplied run IDs *coherently* can satisfy internal comparison checks. Only separately established GitHub Actions run/executed commit/artifact ID/original full-ZIP digest provenance and a trusted admission process can qualify *which original native source* is authorized for publication. The viewer does not contact GitHub or label a result as a certified native measurement. Public evidence remains `diagnostic_only` and `nativeQualified=false`. The new read-only source manifest cannot be treated as host attestation.

## Existing approved example (not a new native run)

`H1_D2` → `H1_D2_K2` is the **single** currently published pair. The admitted child H1 revision doubles existing `rod.k` from **100 to 200 W/(m·K)**, keeps two insulated bodies and every other effective input fixed, and leaves the same **asymptotic** 308.15 K equilibrium; it shows faster heat exchange at saved times, not exact equilibrium at finite time.

The original D2 run **43691263273**, artifact **14152886226**, ZIP SHA `8fc38b9e2f040b48ab5cbeab34e8698b7c99c4d462a1e31e8bc33b0395185379`; the original D2-K2 run **43693191224**, artifact **14153251022**, ZIP SHA `dc32a0a36a27f031ce7a13da83ebdd26a3dd6ac1d14612fa597b36cb439f4843`. Both historical GitHub runs were independently verified in [PR #19's independent Chat B review](https://github.com/physicsvigilante/review_sandbox/blob/main/projects/sim_heat/pr-19/reviews/review-01-chat-b.md). No archived MAT/CSV bytes were changed for v2.

## Tests and refusal controls

- New Python source-pair unit tests compare the produced v2 index **byte-for-byte** with the committed source, construct scratch copies of authentic admitted H1 studies/case JSONs, and mutate reference-to-parent links, unsupported/extra physical changes, altered topology, wrong `rod.k`, child study analysis/requests, misowned rod/energy native channels, fake native-qualified status, rehashed catalog case bytes and false source/ZIP IDs.
- Test-only **self-consistent fabricated source metadata** can be admitted when both the pinned manifest and stored case JSON are rehashed together, intentionally demonstrating the **external** host-authentication limit rather than claiming to defeat forged evidence with internal hashes.
- Synthetic unit tests cover separately archived result slots in **the same run**, conflicting artifact ID/run/ZIP identity and both sides pointing to exactly one output slot. They are structural policy tests, **not** new native results.
- New JS tests demand v2 fields and refuse false run/artifact/ZIP/commit/MAT/CSV/archiveEntry pins; old saved time, source ownership and historical cases remain validated.
- Real desktop/mobile Chromium checks still exercise the approved pair, original case switch/import/refusal scenarios and a wrong native source pin; the **synthetic two-selection test** reuses the *same original approved D2→D2-K2 source pair* under a second test-only menu label, holds one old source fetch, then verifies the old response cannot overwrite the newest selected observations. It is not published as a new teacher case.

## Release and future expansion

Source changes affect only `viewer/network` source-pair metadata/compiler/validation/tests, one branch-only CI workflow and this scope. The `h1/` runtime and numerics, Modelica law, existing baseline native evidence, old standalone network renderer and all six published native case bundles are **unchanged**. The single teacher pair remains a constrained **read-only display**, not a general LLM-to-OMC simulation service.

Before publishing any *new* pair, repeat the external native-source verification and ensure its H1 direct revision is admitted. A new material law, unsupported physical revision or native output trust class requires an explicitly reviewed reusable extension; do not fabricate inputs or results.

**Required release gate:** Full final-HEAD H1 tests, analytics, Python/Node source-pair negatives, real Chromium desktop/mobile regression and stored original-source CI fingerprints; then **draft PR and independent Chat B R2** under `review_sandbox/projects/sim_heat/pr-N/`. Owner standing authorization covers a review-passed merge and post-merge CI, but **never** authoring Chat B's independent verdict. Keep historical failed CI and the original PR #19 report unchanged.
