# H1-N12 — Three-case source-only reference staging, NO native runner

**OFFLINE STAGING CANDIDATE, NOT an adopted native reference.** Stacked on
independently R2-scoped-passed H1-N11 and its R1 test-only follow-up PR79.
This deliberately advances **data preparation for the native qualification
path** rather than inventing a new physical solver or an authorization mock.

## What new capability exists

The original independently authored H1-T1-T `model.mo` and first-version
`study.json` stay byte-identical and SHA-pinned. The separately published
N3 migration contract requires three distinct runs of the SAME physical
composition: original `primary` 2400 intervals / DASSL 1e-8, new
analysis-only `tight` 2400 intervals / 1e-10, and new analysis-only
`dense` 4800 intervals / 1e-8.

N12 prepares those three descriptors in an outside-repository scratch
directory, preserving every model fact, original requests and all 41 physical
provenance slots. Each is admitted by the **unchanged genuine H1 parser**
with all eight original public requests still `not_computed`. Its model
bytes are the same original SHA
`2c60e40f1ad8d85f46968f03712d23e8cd6b9c656cf6099a38a97d198d0873ae`.
Only study `id` and declared `analysis` for the two companions differ;
their source-descriptor SHA hashes are unique and recorded.

To prepare **physical target data**, the code independently **reruns N11's
actual full-grid source-rational mathematical audit** and the **unchanged
N1** source-only primary/dense generator. It requires the complete original
N1 trace bytes to match prepublished SHA256
`b13877c8d069a60928cf3b23ae007b1a10feb53151f00ffb65a57082a7fc10af`
(primary, reused as the physics target for tight) and
`9ba71a1d2fccb39be071df0647793f6fb844737e2ac9c91bb143546ab8d26b40`
(dense); the reviewed N9 static bit/unit proof and the actual N11
source-physical 648,180 candidate-centre budget check are rerun.
**Solver tolerance does not enter the ideal physical initial-value problem**:
using the primary time-grid physical target for tight is mathematically
intentional, but does not provide native DASSL 1e-10 results or native
solver accuracy evidence.

The three packages contain all **77 internal source-only reference exports**,
8 original author-requested reference series, and 5 source-only integrated
flows at every saved time, plus the ORIGINAL N1 trace SHA and the separately
regenerated N11 receipt SHA. A small stage receipt stores the three exact
new source-study identities and file digests. Replaying staging in two
separate clean scratch roots must yield **byte-identical output packages**,
including the original/derived Modelica and study snapshots.

## Strict evidence and run boundary

**Schema: `sim_heat.h1_n12.source_only_three_case_reference_stage/1`.**
This is deliberately **NOT** the old `sim_heat.reference_bundle/2` nor the
future `sim_heat.h1_n3.reference_bundle/1`. It has no `seal`,
`semanticSeal`, verified owner signature, owner-authorized expected SHA,
native allowances, local scales or temporal/quadrature policy. Those are
unimplemented requirements for a subsequently reviewed versioned reference
adapter and release workflow. Source-created SHA identities protect bytes
against accidental substitution; they **do not authenticate** the owner,
the toolchain, the reviewer, or a successful simulation.

The code refuses altered original study/model/facts bytes; mutated or
promoted N3 design, reviewed N11 numerical source closure drift; changed
original N1 trace identities, missing public/integral inventories, attempts
to attribute a new physical model to an analysis-only companion; wrong
source H1 admission, reused study digests, and altered false native
qualification flags. A malformed stage is NEVER authorized to invoke OMC.
Original first-author and frozen C1 inputs are never rewritten.

The original legacy `reference.prepare` still has **seven static
source-physical 100× failures**:
`T02.G,T06.A,T06.G,T07.G,T08.G,T10.G,T_Plug.C`.
All **eight native readiness blockers** remain, including an absent
reviewed-runner reference, exact runtime OpenModelica/MSL identities,
external pre-output owner-approved manifest, and real single-use attempt
lease. N12 solves NONE of these. It does not claim certified runtime
adoption, native results or permission to run OpenModelica.

## Reproduce offline

```sh
python -B -m unittest qualification.h1_n12.tests.test_stage_reference -v
python -B -m qualification.h1_n12.stage_reference --out /tmp/h1-n12-fresh-stage
```

The target directory must be NEW and outside the repository. It will
contain `cases/{primary,tight,dense}/model.mo` and `study.json`,
`primary.candidate.json`, `tight.candidate.json`,
`dense.candidate.json`, and `stage-receipt.json`.
No files are served to the browser, loaded as source native evidence or
adopted by a runner. CI will replay the generator twice in independent
scratch folders and check byte identity. Generated candidate files must
not be reinterpreted as protected reference approvals; only a
separately reviewed source/physical certificate, authenticated owner
manifest and prospective versioned runner can later create that trust.

Because this creates new *reference preparation evidence semantics*, this
bounded implementation needs one independent R2 review. Do not merge PR79
or N12 automatically, install/query/build/launch OpenModelica, approve
source/runner changes, deploy, or alter the original C1/diagnostic history.
