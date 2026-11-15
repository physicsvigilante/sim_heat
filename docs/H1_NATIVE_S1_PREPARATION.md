# H1 first native step — S1 preparation

Date: 2026-11-15. Candidate: `cce9eea14223f12df0d7959d1e893f3181ee779a`.
Status: desk-only preparation, **not an executable or approved native run plan**.

The user approved moving toward controlled OpenModelica qualification while
retaining the composability guide. This step records a small next experiment;
it does not install tools, invoke OMC, freeze/accept the candidate, select C1,
merge a PR, or change the charter. The existing R1/R2 correction remains
an author-tested candidate, not an independent PASS. Another broad architecture
review or review packet is not a prerequisite for this preparation. No blanket
waiver of the outstanding execution/acceptance gates is inferred.

## 1. One experiment, not another apparatus solver

Start with the existing **S1 steady series-conduction composition**:
`h1/cases/S1/model.mo` and its existing `study.json`, using the unchanged shared
`experiments/h1_spike/SimHeat.mo` library. S1 is already development-exposed.
The native gap is compiler/runtime/export integration, not a missing heat law.

Question: can the selected compiler build this admitted composition, export the
required quantities with known units/signs/precision, and supply evidence the
existing generic checker can assess?

A successful attempt would qualify only this tested steady build/export path.
It would not qualify thermal-body initialization, transient integration, general
network admission, classroom effectiveness, or unfamiliar assembly. The `0..1`
backend evaluation interval is not physical elapsed time in this steady model.

**Reuse test:** the future execution/export adapter must consume the existing
model identity and generated export registry, not branch on `H1_S1`, `copper`,
`steel`, or an illustration number. Independent test expectations may name a
fixture; production physics and assembly may not. Record any production change
and whether it belongs to generic backend integration or case-specific handling.

The later D1/D2 runs exercise storage and physical time through that same path.
Observation changes and D2-K2 test limited investigation reuse. C1 remains
unselected until the applicable production/public interfaces are actually frozen.
H1's documented post-freeze exception remains a narrower protocol, not the
charter's full Track A/Track B diagnostic or general structural editing.

## 2. Candidate inputs and predeclared expected behavior

| Input | SHA-256 at the candidate |
| --- | --- |
| Shared `SimHeat.mo` | `e57955b6c32cb34321a6b1908306c4ea9a63ae259b95a5fd48c7e8d3b4da10ea` |
| S1 `model.mo` | `3228323714b2f886279aa90c46c1c49c9143e2d8b9c6de032389c750b6848f1c` |
| S1 `study.json` | `83bb6badc19e55008455083cde64adc2d53ba32c1d5f009d5b1b3594bd5f2405` |
| `h1/reference_cases/S1.json` | `47b1d9035230cb252a992a3fdcdbdf6fbefd350f901aacaaae9dae37b561635a` |

These are inspection pins, not a complete approved checker/toolchain manifest.
Physical values remain in the authored model; the plan cannot override them.
The existing S1 model uses the explicit adopted convention 4184 J/kcal. The
reference source facts and provenance correction remain unchanged.

Independent series-resistance expectations, not results of a native attempt:
- Junction: approximately **366.45628803245436 K** (93.30628803245436 degC).
- Each rod's authored a-to-b heat flow: approximately **+1.0792824946508015 W**.
- Hot boundary supplies that amount; cold boundary's `Q_to_network` is negative.
- Each rod's a-port flow is positive and b-port flow is negative; junction flow
  sums and total boundary supply balance to zero within the predeclared policies.

Use the current per-output allowances and reference-accuracy obligations, not
rounded figures in this note, as the actual numerical acceptance criteria.
Do not relax the parameter/area/conductance precision requirement after seeing
CSV output. If the export is too coarse, record an export limitation.

The existing public requests are junction temperature and copper-rod heat flow.
The internal registry requires **18 quantities**, regardless of request selection:

- `hot.T`, `hot.Q_to_network`, `cold.T`, `cold.Q_to_network`.
- For each of `copper` and `steel`: `A`, `G`, `T_a`, `T_b`, `Q_flow`,
  `port_a.Q_flow`, and `port_b.Q_flow`.

A compiler alias or eliminated constant must not be silently supplied from the
reference, inferred from the physical law, or fabricated as the negative of
another column. Native alias/constant metadata can support a future explicit
adapter only after its semantics are checked and its identity recorded. Two
alias-related outputs are not independent measurements; preserve that limitation.
The current decoder requires its columns, so a missing one is a recorded schema
failure, not permission to bypass the checker.

## 3. First attempt shape — proposed, currently zero authorization

After host binding, scoped gate disposition, launcher/export implementation and
exact-plan approval, propose at most **one compiler version query, one build,
and one model-executable launch**, with no automatic retries. Building and
launching are separate steps; check build diagnostics and identities before
launch. Pin the selected solver/settings and effective export controls explicitly,
never by inheriting version-dependent defaults.

Treat this as the planned S1 primary attempt within the earlier proposed H1
capability ceiling, not a hidden extra setup run. If separate toolchain probes
are needed, declare their commands and budget before execution. A failed export
or build remains a consumed recorded attempt; a successor needs an explicit
bounded decision. Nothing here approves the larger 16-launch proposal.

Retain exact inputs, commands/environment, stdout/stderr, compiler diagnostics,
generated setup/alias information, executable/dependency hashes, raw CSV bytes,
verification output, and cleanup outcome in one fresh attempt directory.
Stop on source drift, unexpected external access, failed compilation, missing
outputs, precision/identity mismatch, nonfinite data, or failed numerical checks.
Do not tune an example's physics, widen tolerances, or launch an undeclared retry.

The current `h1.verify` deliberately admits only synthetic/unattested candidates
and always reports `nativeQualified=false`. Preserve that behavior. Do not flip
flags or relabel a manually created receipt to claim native acceptance. A small
reviewed execution-evidence layer must establish actual process/artifact provenance
and report execution, export, numerical checks and acceptance separately.

## 4. Runtime facts needed to turn this into an executable plan

No `omc` executable was found on PATH in this chat's Linux environment during
this preparation. That is not an inventory of the user's computer.

The inspected `new_therm/CLAUDE.md` records a candidate existing Windows host,
`gunjan-pc`, with OpenModelica under
`C:\Users\Gunjan\Tools\OpenModelica-1.27.1` and Python under
`C:\Users\Gunjan\.conda\envs\new-therm\python.exe`.
Its blob is `488cb8e22128c1fddfafd02a009cf4d061593aa2`.
These are **repository records**, not confirmation of present host availability,
an executable path, an installed MSL release, or SIM_HEAT qualification.

Prefer evaluating that existing installation over adding a second toolchain.
Do not modify `new_therm`, consume its approvals, or inherit its acceptance.
Its documented network/shell containment concerns must be considered before
any OMC invocation, including a version query; do not change firewall, shell,
update, package or environment settings as part of this preparation.

The exact plan still needs:
- Selected host and operator; absolute OMC/Python paths and installed versions;
  MSL package path/release/source hashes; build-tool and dependency identities.
- A host-specific, tested launcher/export mapping and complete checker manifest,
  including `temporal.py`, decoder, verifier, reference, policies and dependencies.
- Fresh work/output locations; explicit resource/time/process limits; permissible
  writes; network/package-download controls and cleanup with disclosed limitations.
- Sealed S1 reference and retained executable reference-accuracy evidence;
  exact invocation/settings; the remaining review/waiver disposition and approval.

No host details or executable commands are guessed here. A host-specific offline
compatibility rerun is distinct from a native run and must retain its own evidence.

## 5. Review boundaries and next action

R1/R2 are corrected and author-tested, with the scoped recheck still not recorded.
R3 reference accuracy, R4 checker/runtime identity, and R5 real exports/precision
remain at their documented gates. S1 does not exercise transient timing or body
initialization, so S1 success could not close those obligations. Planning can
proceed now; execution requires the unresolved items to be resolved or explicitly
dispositioned for the narrowed claim, without inventing independent approval.

**Next practical action:** identify the execution host and inspect its existing
runtime. Then finish one exact S1 execution plan and the smallest generic launch/
export support it needs. No new physical feature or full architecture review.

## 6. Checks performed for this preparation

Reopened the uploaded charter and current candidate contract/decision/cases.
Reconstructed the 71-file correction snapshot; tree
`de9c202acac14e054763300cf6e8d29ca06ee123` matches its recorded candidate.
Ran the existing S1 offline admission CLI in that scratch snapshot: admitted,
requests not computed, no native execution. Inspected its 18-export registry
and input hashes. No full test rerun or physical-result verification is claimed.
No OMC command, build, model launch, dependency install or CI activation occurred.

OpenModelica's primary documentation confirms that `buildModel` builds without
launching and that output format/filter are explicit settings. These reference
pages are not a selected installed compiler or proof of actual CSV/alias behavior:
- https://build.openmodelica.org/Documentation/OpenModelica.Scripting.buildModel.html
- https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/scripting_api.html

Project authorities: `H1_OFFLINE_DECISION.md`, `H1_OFFLINE_AMENDMENT.md`,
`H1_SLICE2_VERIFICATION.md`, `H1_REVIEW_CORRECTIONS.md`, and the retained reviews.
The supplied Composability and Teaching Charter v1.0 is used without rewriting it;
its project-specific H1 exception remains in the existing decision record.
