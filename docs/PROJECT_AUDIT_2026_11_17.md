# Project-wide audit — 17 November 2026

## Scope and evidence boundaries

This audit examines both active `main` (`c06fb5395781482bd6bbe055d10bc10cdf3bba8d`)
and the unmerged PR49 qualification/viewer lineage
(`04461dd840c3249ced06c4bf0bdeecc25babe962`), using complete source/review Git
snapshots and original archived native artifacts. It inventories workflows,
capabilities and historical decisions, inspects the active parser/topology,
archival adapters and viewer, executes regression/adversarial checks and
checks the standalone HTML in Chromium. This is not a proof that every
historical file, textbook example, platform or possible input is defect-free.

**No OpenModelica installation, version query, build or model launch occurred.**
No C1 mathematical reference was regenerated. Ordinary D1/S1 analytical data
used in synthetic unit-test fixtures is explicitly not native evidence. Native
archive replay reads the original saved reference and CSV; it does not rerun the
physical model. Historical failed records and original author submissions remain
untouched. Corrections are prospective draft successors, not production merges.

## Concrete findings and corrections

| ID | Finding reproduced | Correction | Verification |
|---|---|---|---|
| A01 | PR49 draws the flat/round bridge lanes without connections to the junction circles; original DOM tests still pass | Add schematic-only connector paths to both circle rims; move sign labels clear of arrowheads | Exact endpoint regression and actual Chromium page/selection/layout checks |
| A02 | A valid Body named `junction_2` collides with an automatically generated junction, creating duplicate IDs and a false self-loop | Reserve all authored component IDs before deterministically naming synthetic junctions | Collision/suffix/rod-name negatives; all six existing graphs unchanged |
| A03 | Main shared `strict_json` accepts legal `1e999` as infinity; oversized/nested input refusal can be inconsistent | Finite `parse_float`, bounded integer tokens and structured descriptor failures | Nested positive/negative exponent, finite controls, duplicates, large integers and recursion tests |
| A04 | Steady/campaign saved-report equality treats `0 == False` and `1 == True`; boolean command counters can masquerade as integer counts | Compare deterministic serialized reports and require exact integer counts | Synthetic repacked mutation probes for both adapters |
| A05 | Transient archive adapter accepts contradictory saved checks or fabricated public values under a success label; omitted manifest entries can be missed | Verify complete manifest, original saved reference/seals, MAT/CSV provenance and replay the complete existing checker report | Synthetic adversarial repacks plus byte-identical replay of all six genuine published bundles |
| A06 | Root README incorrectly says there is no interactive viewer and describes C1 as unselected | Replace with an evidence-scoped capability matrix and working local-viewer instructions | Cross-check against code, catalog, original source records and artifacts |

A04/A05 attacks deliberately recompute outer and member hashes in **synthetic
repacked test archives**. They expose inadequate internal consistency checks;
they do not demonstrate a way to alter an independently trusted original ZIP
without changing its SHA. Caller-supplied hashes or GitHub-looking strings are
not signatures. All newly accepted archives still require independent origin
verification. The transient CLI now requires `--expected-run-id` and
`--expected-commit-sha`, matching the existing steady/campaign boundary.

The shared JSON parser correction changes current source, so old SHA-pinned
native plans correctly refuse the successor. The resolution-campaign tests
update only explicitly disposable scratch fixture pins, including the new
parser; **no historical plan or actual native budget is repinned**. A separate
regression asserts the original plan still refuses the new parser.

## Demonstrated capabilities already present

### Composition and validation

The H1 library supports `Body`, `RodArea`, `RodCircular` and `FixedTemperature`.
Bodies have lumped constant heat capacity; rods are storage-free conductors;
fixed boundaries impose temperature. A restricted Modelica grammar plus a study
JSON supplies values, connections, initial/boundary conditions, provenance and
public requests. It admits supported unfamiliar graph combinations and rejects
unsupported constructs or missing/inconsistent data. This is not unrestricted
Modelica or a universal thermodynamics specification.

Topology uses thermal-port equivalence classes, oriented rods, boundary/body
ownership and a junction-conditioning check. Supported public operations include
temperature, rod heat flow, ordered temperature difference and Body energy change.
The numerical reference/checker is separate from the Modelica source and includes
signed-flow, energy/conservation, temporal association and resolution diagnostics.
A MATv4 reader and canonical CSV path exist; neither makes a result independently
qualified by itself.

### Actual archived execution and explorer

`viewer/network/data/index.json` publishes six original source-linked native
**diagnostic** cases: D1, D2, DEV_BRIDGE, steady S1, TEACH_RING4 and D2_K2. The
browser supports case selection, physical-time playback for transient cases,
steady algebraic display without fake time, signed flow/reversal inspection,
energy ownership, full CSV identity verification and a saved D2/D2_K2 what-if
comparison. It displays saved solver output; sliders do not run a new simulation.
The generic source-to-graph adapter is not supposed to depend on an apparatus ID.

All six original published bundle bytes were reproduced with the corrected
adapters from the original whole ZIPs. Original artifact IDs are 14152886226
(D1/D2), 14155084346 (bridge), 14204656273 (S1), 14215520616 (ring4) and
14153251022 (conductivity/resolution campaign). The audit evidence records each
ZIP hash and regenerated bundle hash. No saved values or scientific tolerances
were changed. Labels remain `diagnostic_only`, `nativeQualified=false`.

### C1-specific state

The first independent-author C1 material exists, and its first evaluation was
preserved. Its original strict checking-reference precision margin was 80×,
below the frozen ≥100× requirement. The later cross-host regeneration did not
reproduce the exact original saved PR31 V2 seal. Neither is retrospectively a
pass. The adopted original saved reference is for **offline checking only**.

The C1 successor branches can inventory 37 expected exports, four analytical
integral histories and nine authored public requests; map their exact source
field dependencies; reconstruct the original four-junction topology; and emit a
standalone nonphysical schematic with request highlighting. Those expected
fields are not actual C1 native output. All nine native C1 public values remain
uncomputed. The local SQLite/CAS/state-machine experiments demonstrate limitations
and denial behavior; they are not deployed durable owner-controlled launch locks.

## Validation results and limits

The active-main baseline had 151 H1, four arithmetic, 33 adapter and 31 Node tests
(219 collected, one optional archive test skipped). The corrective main branch
adds parser/topology/archive regressions and a historical-plan guard. Exact
final counts are in its CI/source logs, not inferred from an old PR total.

The schematic successor runs the inherited qualification suite plus one new
endpoint regression (410 offline Python methods) and actual Chromium checks on
the emitted page: all nine request selections, show-all reset, keyboard control,
desktop/mobile layout, source endpoints, no network requests and no script errors.
It uses `page.set_content`, not URL navigation; this is one Chromium build, not
cross-browser, screen-reader or real classroom certification. The audit's local
main-viewer localhost smoke was blocked by the environment's browser navigation
policy (`ERR_BLOCKED_BY_ADMINISTRATOR`), so that local attempt is **not a pass**;
the normal localhost browser suite is included in corrective hosted CI.

Earlier interrupted source-transfer failure was a GitHub workflow-write permission
failure, not verified source publication. The exact schematic tree was recovered,
inspected and retested before publication through the authorized GitHub connector.
The old transfer failure, prior PR49 failures and scientific failures remain
historical records. Independent R2 is still required for the corrective code;
this developer audit is not a second-context review.

## Plan forward — consolidate, then demonstrate useful capability

1. **One corrective review milestone:** review the active-main hardening and the
   separately based schematic correction with exact source/CI evidence. Merge
   active-main corrections only with owner approval. Do not merge the historical
   qualification chain wholesale, and do not treat passing offline tests as a
   native budget.
2. **Consolidate the product surface:** make the existing generic explorer the
   primary entry point; expose original archived diagnostic cases separately
   from expected-only C1 schematics. Use one capability/evidence registry and a
   reproducible test command, rather than more copies of shape/hold validators
   and branch-specific workflows. Stop adding toy authorization layers unless
   they close a named operational requirement.
3. **Choose one meaningful end-to-end acceptance task:** an unfamiliar supported
   author composition must be admitted, rendered correctly, executed by a
   separately reviewed non-regenerating adapter under an explicitly authorized
   bounded native plan, and checked against the already adopted original
   reference. Preserve failures and permit no silent retry. Actual execution
   needs authentic source/reference custody, host/toolchain evidence and a real
   enforceable attempt budget; mocks do not satisfy these requirements.
4. **Teacher workflow next:** clear input/provenance editing, informative refusal
   messages, source/topology inspection, original diagnostic observations and
   safe comparison of separately authorized runs. Measure an actual teacher's
   ability to understand assumptions and identify an invalid model before
   adding more physics.
5. **Physics expansion only after that baseline:** add a reusable physical law
   (for example a reviewed boundary/transfer mechanism) with independent tests,
   not a new apparatus-specific implementation. General symbolic/inverse solving,
   fluid flow, phase change, mechanics and unrestricted language-to-model
   generation are future work, not current capabilities.

Remaining organizational debt includes many stacked historical draft PRs,
expiring Actions artifacts, repeated case-specific offline wrappers and duplicated
shape-versus-exact validators. Archive/review these deliberately; do not erase
history, silently repin science or call a local hash an authenticated release.
