# SIM_HEAT project audit — 19 November 2026

**Assessment:** a genuinely compositional but narrowly scoped thermal-conduction foundation, with useful archived OpenModelica diagnostics. It is not yet one integrated, independently qualified, teacher-ready general JEE thermal simulator. The highest-value next step is product/runtime consolidation, not another isolated proof layer.

This is Chat A's implementation/audit report, not an independent Chat B verdict. The corrections below are a prospective **R2 successor to main**. Nothing here authorizes a merge, installation, compiler query, native build/launch, reference promotion or rewriting a frozen experiment.

## 1. What was actually inspected and executed

Two distinct source lines were inspected:

- Product `main`: commit `f52613c39c539b2d4543a9838e5658d526fca10e`, whole tree `0c44961b473d23737b0c9f3b3f2cd3db65b9f264`.
- Latest draft PR69: commit `23172ce2cd7a18466d2bf176b83064e6cd49bac1`, tree `112d8b56e0d6b72fd2dec06628e5f2f58b4665a5`. This includes N1–N8 qualification work not deployed in main. PR69's correction review remains separate; this audit does not approve it.

The PR69 source archive was downloaded from GitHub Actions artifact 14544661914. Its ZIP SHA-256 was independently recomputed as `37ccc620c827f3dd67cc6c1eae35564b4f175d53d59ce0ad0067282cf3d4757a`; CRC checks passed and a reconstructed Git tree exactly matched the pinned tree. The main product tree was independently reconstructed and matched its separate pin. Local synthetic Git commits are not presented as original GitHub history.

Inspection covered authoring/parser/provenance, Modelica components and topology, numerical policy and verification, MAT/CSV decoding, native batch/campaign preparation, archive adapters, browser data/entry points, local workbench, documentation, workflows, examples, and the draft qualification layers. Existing automated tests and new adversarial controls were run on actual modules. This is a broad source/test audit, **not a proof that every possible bug or physical interpretation has been found**.

## 2. Reproduced defects and prospective corrections

| ID | Reproduced problem | Correction | Remaining boundary |
|---|---|---|---|
| A19-01 | The documented direct workbench command fails with `ModuleNotFoundError: h1` under isolated Python/from an unrelated working directory. Normal developer environments can hide the missing import-root setup. | Establish the repository import root before importing H1 when launched as a script. | No HTTP, privacy or native-execution behavior changed. |
| A19-02 | `load_study` converted a Windows filesystem-relative path to `str`, creating backslashes that its own portable-descriptor guard rejects. | Use `.as_posix()` at the filesystem-to-portable descriptor boundary. | Windows path behavior was tested with `PureWindowsPath`; this is not a native Windows/OpenModelica qualification. |
| A19-03 | `Study` is a frozen dataclass but its nested component/provenance/request/topology dictionaries remain mutable. A mass changed to 987 after admission appeared in a preview still claiming the original model SHA. | Retain the original case root, re-admit original file snapshots, compare all derived/source objects with exact-type semantics, and build from a detached freshly validated `Study`. | Integrity is not independent truth of the authored physics. The trusted case root is retained for sibling-directory revision chains. |
| A19-04 | Native `load_plan` hashed a file via one read, then parsed a second read. A scratch-file race substituted a different branch after hashing and before parsing. | Capture raw bytes once, bound and hash them, and parse those identical bytes. | The native runner's historical external authority, host identity and execution-budget requirements are not solved by this small fix. No compiler was invoked. |
| A19-05 | Two workflows triggered for future main PRs but required the exact all-added-file diff of their original introduction PR. Legitimate maintenance could never meet that historic scope assertion. | Retain the original exact-diff/protected-code checks on the original milestone branches. Maintenance PRs still record actual checkout/base identity and run the full regression, archive replay and browser gates. | This does not permit altering frozen evidence. Changed source still requires scoped R2 review. |

The first ten regression tests ran against unchanged main with **seven failures and one error**, demonstrating the four code defects rather than assuming them from inspection. The corrected ten tests pass; two additional workflow-maintenance regressions pass. Source byte-length bounds are checked after reading as well as before. No numerical acceptance tolerance, Modelica law, public observation quantity, saved native value or historical reference was changed.

`h1/tests/test_resolution_campaign.py` updates pins only inside its explicitly disposable temporary fixture for the newly changed loader. Original historical plans are untouched and continue to refuse changed successor code. This is essential: silently repinning old native experiments would destroy their meaning.

## 3. Executed checks and preservation

### Corrected main-based product

| Suite | Collected | Passed | Skipped |
|---|---:|---:|---:|
| H1 authoring/numerics/decoder/controller tests | 152 | 152 | 0 |
| Analytical source examples | 4 | 4 | 0 |
| Archive and viewer adapters | 63 | 62 | 1 |
| Product/source-preview/workbench plus new audit regressions | 52 | 52 | 0 |
| JavaScript viewer/preview tests | 42 | 42 | 0 |
| **Total** | **313** | **312** | **1** |

The optional adapter skip is not a failed check or a claimed pass. Documentation HTML parity also passed. The unchanged TEACH_SPLIT3 source preview still serializes to its original saved bytes. A separately executed original-archive replay covers the six published diagnostic cases.

### Frozen draft qualification snapshot

N1 plan 34, N1 interval 17, N2 16, N3 12, N4 15, N5 11, N6 13, N7 13 and N8 16: **147/147 qualification-specific tests passed** against the unchanged PR69 snapshot. These are not tests of an integrated main runtime. Combined with the product suites, 460 test methods were collected across the two explicitly distinguished source lines: 459 passed and one optional test skipped. Repeated CI/local runs are not additional distinct coverage.

The draft snapshot was not repinned or modified to make it accept the main-based changes. Its source-pin-sensitive gates must be deliberately re-baselined and reviewed before any eventual integration.

### Genuine historical OpenModelica outputs

Five original ZIPs were downloaded, independently SHA-256/CRC checked, and processed through the existing offline archive adapters. No archived executable was launched:

| Archive ID | Cases | Replay result |
|---|---|---|
| 14152886226 | D1, D2 | Both published bundles byte-identical |
| 14155084346 | DEV_BRIDGE | Byte-identical |
| 14204656273 | S1 steady | Byte-identical |
| 14215520616 | TEACH_RING4 | Byte-identical |
| 14153251022 | D2_K2 | Byte-identical |

The replay validates saved reference/checker/decoded-data coherence, not a new compiler execution. Labels stay `diagnostic_only` and `nativeQualified=false`.

### Browser and native limitations

Two actual local HTTP Chromium attempts (workbench and archived explorer) were blocked by the environment's `net::ERR_BLOCKED_BY_ADMINISTRATOR` policy. These are recorded as **blocked**, not browser passes or demonstrated application bugs. Existing hosted workflows retain real browser smoke tests; exact new-head hosted results must be checked separately.

No OpenModelica executable was available in this audit environment and no installation, version query, build or launch was attempted. The tests never authorize native execution. Current fresh native behavior remains **not tested**.

## 4. Composability: strong physical foundation, incomplete product integration

The good architectural choice is that `Body`, `RodArea`, `RodCircular`, and `FixedTemperature` wrap Modelica Standard Library thermal components and connect through thermal ports. The parser derives topology from connections rather than naming an apparatus. The generic reference and source preview are similarly graph-based. The six historical cases and unrelated qualification fixtures demonstrate meaningful reuse within that bounded domain.

A supported new network of bodies, rods, junctions and fixed reservoirs should need new authored source/study data, not a new `if apparatus == ...` solver branch. That is the right criterion. A genuinely new heat-transfer law should become a reusable component plus a compatible observation/reference extension, not a copied per-question implementation.

However, composability is currently fragmented across separate interfaces:

1. Author writes restricted Modelica plus study/provenance/request JSON.
2. The production workbench admits and displays source-only facts, not new computed values.
3. The existing explorer reads a fixed catalog of archived native diagnostic outputs.
4. Draft N4–N8 routines operate on separately expressed physical-facts JSON and mathematical snapshots.
5. The old native runner still prepares its original reference format, not the new interval candidate.

The numerical work is therefore ahead of the integrated teacher experience. A new composition may be mathematically inspectable without being runnable/visualizable through one supported product path. Calling that complete end-to-end authorability would overstate the evidence.

There is also architectural debt: duplicated schema/identifier/status guards and graph arithmetic across qualification stages, many milestone-specific workflows, and a long draft PR stack. Preserve truly independent numerical checking algorithms; consolidate ordinary shared contracts and input validation so fixes do not need repeated propagation. Never create a reference oracle by merely reusing the same faulty solver twice.

**Verdict:** composition is real for the supported linear lumped thermal graph; generic thermomechanical composition and smooth end-to-end teacher authoring are still incomplete. No blind unfamiliar LLM-authorability or classroom effectiveness result is claimed.

## 5. JEE relevance: useful conduction module, not full thermal physics

The official JEE Advanced 2026 thermal syllabus is the explicit reference used for this mapping [E1]. This is a capability map, not a prediction of question weight or a claim about a later exam year. The repository's own source map and adopted assumptions remain important: Illustrations 123, 134 and 135 are development-exposed examples, not held-out authorability tests.

| Learning objective | Current supported interpretation | Important limitation |
|---|---|---|
| One-dimensional conduction, composite rods, series/parallel paths | Strong match to constant-k storage-free rod networks | Not general distributed-temperature or temperature-dependent-k conduction |
| Junction temperatures and heat-flow directions | Good analytical/archived support; draft exact/interval snapshot methods | New snapshot results are not native trajectories |
| Heat capacity and finite-body energy exchange | Lumped constant-C bodies, energy changes, archived transient examples | Uniform body temperature is an assumption, not always physically justified |
| Symbolic statements and illustrative numbers | LLM can propose supported model with explicit numerical demonstration bindings | A numerical demonstration does not prove a symbolic formula or solve every inverse problem |
| Newton cooling / convection | No explicit supported public convection component | A conductive exponential is not automatically a modeled convection experiment |
| Radiation, emissivity and Stefan-Boltzmann exchange | Not implemented in the admitted H1 component set | MSL's existence of a radiation model does not mean SIM_HEAT supports it |
| Latent heat / phase changes / melting interfaces | Not implemented | Constant heat capacity cannot silently stand in for latent heat |
| Thermal expansion; gas processes, heat-work, engines | Outside current H1 mechanics/thermodynamics domain | Requires new reusable coupled laws, not just another thermal rod |
| Spectral radiation / Wien / blackbody spectrum | Outside current model | Total heat-flow components do not supply spectral physics |

`RodCircular` means axial conduction through a constant circular cross-section, with area derived from diameter. It does **not** mean radial conduction through a cylindrical shell. That distinction should be prominent in teaching examples.

The most valuable JEE improvements are not more numerical digits. Expose assumptions, show why an invalid model is refused, distinguish W from J and absolute K from temperature differences, explain the direction of heat flow, and let a teacher compare meaningfully changed physical systems. Keep numerical bindings separate from source givens; keep the recorded source errata in `docs/SOURCE_COVERAGE.md` rather than adjusting inputs to match a printed answer.

## 6. OpenModelica: earlier integration demonstrated; current successor not freshly qualified

The core Modelica design aligns with MSL 4.0.0: a heat capacitor stores energy, a thermal conductor transfers heat without storage, and fixed-temperature boundaries supply or remove energy [E2]. The library preserves connection-based conservation; public rod flow is oriented from a to b, and boundary heat supplied to the network has its own stated sign.

Historical execution records show the earlier bounded examples running with **OpenModelica 1.27.0 and MSL 4.0.0**. Raw MATv4 outputs, aliases/signs, normalized samples and separately checked values are present in the retrieved archives. OpenModelica documents MATv4 signed aliases and `dataInfo`; the project's dedicated decoder and tests are the appropriate way to interpret those, rather than manufacturing missing values from a reference [E3]. This audit's six byte-identical replays provide tangible continuing interoperability evidence.

It would nevertheless be inaccurate to say the current full project is now qualified on OpenModelica:

- The latest qualification methods are Python checking-only code, not a new integrated Modelica runtime path.
- The historical native runner still uses the legacy `reference.prepare` bundle contract. New source-exact interval candidates do not automatically become approved native references.
- Seven original T1 static checking centres fail the strict source-physical 100x precision requirement. That is a checking-reference/readiness issue; it does not alone demonstrate a wrong OpenModelica trajectory.
- Eight native execution blockers and external ownership/host/seal requirements remain. The runner's environmental checks and local hashes are not a new trusted external manifest or hardened one-use execution authority.
- Native setup and recorded archives were not regenerated, and no historical qualification was upgraded retroactively.

**Verdict:** compatible enough to have produced and retained useful verified diagnostic runs; not yet a freshly qualified, integrated arbitrary-author-model execution service. Retain pinned versions until a separately authorized compatibility test justifies changing them.

## 7. Recommended next work, in order

**First: one audit correction review and product consolidation.** Independently review these provenance/path/loader fixes and exact-head CI. Keep PR69's existing correction review separate. Merge only with explicit owner approval. Do not merge the entire draft chain merely because unit tests pass. Add clear product-versus-experimental status and a single reproducible health command.

**Second: one complete teaching workflow.** Pick a supported unfamiliar thermal network, have a separate author supply only the documented public inputs, preserve the first attempt, admit and preview it, and obtain one separately authorized bounded native execution with pre-approved checking reference. Let a teacher change one conductivity and interpret the new signed flows/energy curves. Measure whether this required core edits and whether the teacher understood assumptions/refusals. This is stronger evidence of usefulness than another standalone checker report.

**Third: integrate only the reusable subset.** Reconcile the separate mathematical fact descriptors, observation names/units, status semantics and runtime adapter under one versioned contract. Do not lower error budgets or change original source facts to obtain a pass. Retain a genuinely independently expressed checking path.

**Fourth: broaden the educational laws deliberately.** After the end-to-end conduction flow works, prioritize an explicit linear convection boundary/Newton-cooling model, then radiation, then calorimetry/phase change if the intended teaching scope includes them. Every extension needs source-based tests and compatible domain assumptions. Pressure-volume thermodynamics should be an explicitly scoped thermomechanical extension, not quietly folded into H1.

## 8. Reproduction and sources

From a checkout of the audit successor, using its pinned existing Python dependencies and Node:

```sh
python tools/check_project.py --out /absolute/outside-repository/new-audit-directory
```

Add `--archives /absolute/path/to/five-original-zips` for offline archived-result replay. Add `--browser` only with an already installed browser/Playwright; blocked or failed checks return failure and are recorded rather than silently skipped. The command never installs or invokes OpenModelica.

Repository evidence: `experiments/h1_spike/SimHeat.mo`; `h1/{model,study,reference,verification,matv4}.py`; `tools/h1_native_batch.py`; `viewer/network/tools/replay_published_archives.py`; `docs/{SOURCE_COVERAGE,H1_D1D2_NATIVE_RESULTS,H1_CONDUCTIVITY_RESOLUTION_RESULTS}.md`; immutable PR69 qualification tests and source identity described above.

External primary references consulted 19 November 2026:

- [E1] JEE (Advanced), official **2026 syllabus**, Physics / Thermal Physics: https://jeeadv.ac.in/documents/jee-advanced-2026-syllabus.pdf
- [E2] Modelica Standard Library **4.0.0**, thermal components and assumptions: https://doc.modelica.org/Modelica%204.0.0/Resources/helpOM/Modelica.Thermal.HeatTransfer.Components.html
- [E3] OpenModelica User's Guide, technical details / MATv4 result file format: https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/technical_details.html

This report distinguishes code inspection, locally executed tests, archived native evidence and unperformed current native/browser qualification. No exhaustive defect-free claim, merge or release authorization is made.
