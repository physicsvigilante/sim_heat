# `sim_heat` Project Policy (v2)

> **Status:** Baseline project policy (post-M02 / PRs #202–#203, merged at `07a10fb`).
> Supplements [`AGENTS.md`](../AGENTS.md) and maps `sim_heat` onto Multiagent Framework v0.2 (`framework-v0.2`, commit `dd091fed2c1efdc398ec1c8124283e374f029e55`).

## 1. Governance, Roles, and Tiers

- **Supersession.** Once approved and merged by the owner, this policy supplements `AGENTS.md` and supersedes any conflicting workflow or review requirement in it. Every non-conflicting requirement stays in force, including: **merge only with explicit owner approval**, **no automatic OpenModelica native jobs in standard CI**, and **preserve original inputs, failed runs, and historical records**.
- **Owner control over participation and reasoning strengths.** The owner retains explicit control over final merges, agent participation, role assignments, reasoning strengths, and major project-direction changes.
  - Current standing governance: **Neon** is the primary coordinator; **Opus is excluded** from the workflow; any additional agent participation and reasoning strengths are specified separately by the owner.
- **Autonomous engineering research workflow.** Once the owner approves a milestone's broad objectives and authorizes the agent roster and reasoning strengths, the team operates autonomously through design, implementation, experimentation, testing, independent review, and corrections—behaving as an autonomous engineering research team rather than pausing for routine technical or architectural decisions.
  - Keep planning and contracts **lightweight** and allow designs to evolve through implementation and scientific investigation.
  - Consult the owner only when a decision materially changes project direction, requires additional agent authorization, involves significant irreversible consequences (such as merging to `main` or modifying frozen qualification pins), or falls outside approved scope.
- **Tier mapping and proportionality.** `AGENTS.md` risk classes **R0**, **R1**, and **R2** correspond to Framework v0.2 **Tiers 0, 1, and 2**. Apply verification requirements **proportionately** to the actual scientific and architectural risks: prioritize deep physical/mathematical understanding and meaningful verification over speed, while avoiding unnecessary administrative overhead or rigid upfront paperwork. R2 work (physics, numerical methods, result/status semantics, provenance/qualification, or authoring-grammar changes) still requires independent non-author verification and strong scientific evidence.
- **Roles.** Framework roles replace the legacy "Chat A / Chat B" labels:
  - an owner-selected **primary coordinator** (currently Neon);
  - an owner-selected **implementation owner**, kept stable across coupled milestones where practical;
  - **independent reviewers and oracle authors**, who must be non-authors working from the brief alone (cross-model where authorized by the owner).
- **Reviewer independence.** The legacy standing rule ("fresh Codex reviewer subagent") is replaced by the framework rule: a review is independent only if the reviewer did not author the work and works from the brief alone. Fresh-context self-review by the author does not count as independent.
  - **Same-model separate participants** (for example, a separate reviewer session checking an implementer session on the same model) count as independent review when explicitly labeled *same-model*. When cross-model participation is authorized by the owner for R2 physics work, pair same-model review with at least one cross-model oracle (M02 demonstrated that both lines catch distinct defects: the same-model reviewer caught EH-01, which the cross-model oracles had missed).
  - **Persistent sessions.** Implementation and review sessions may persist across a milestone; open a fresh session only when independence is actually at risk under the framework's prior-endorsement rule.
- **Shared communication & records.**
  - **Live status channel:** GitHub Issue #204 (*Live Project Status & Owner Decisions*) is the shared live communication channel between project agents, the owner, and the owner's independent ChatGPT adviser. Keep its main body updated at meaningful checkpoints, before requesting owner decisions, and when direction changes; preserve substantive decisions and discoveries in append-only comments without adding unnecessary reporting overhead.
  - **Durable packets & review hub:** External milestone packets live in `C:\Users\samee\Documents\sim_heat-milestone-packets\`; the central review hub (`review_sandbox`, `sim_heat-review-ledger`) retains review artifacts where used.

## 2. Evidence Required for Offline Physics (R2)

Independent evidence is scoped to the scientific claim being made. Every change to a certified solver or physics engine must carry:

1. **An independent oracle**, written by a non-author, from a closed form, exact rational bounds, or `mpmath` at 50 or more digits with stated margins.
2. **A conservation or ledger check:** energy balance, and entropy where relevant.
3. **An equivalence witness** against another representation of the same physics where one exists (for example `multibody` vs `body_phase`, `multiport` vs `radiating_radial_layers`, `staged` vs `multibody`).
4. **A discriminating regression** that fails before the change and passes after it.
5. **Adversarial witnesses for every fast path and admission gate.** Any shortcut (exact linear path, closed form, early exit) requires a witness specifically crafted to break its admission condition (for example, an interval edge between two fixed ports — M02 EH-01). The admission gate must check **every** input the shortcut consumes, not only inputs adjacent to unknowns.
6. **Explicit oracle provenance labels:**
   - `(a)` cross-model, non-author;
   - `(b)` same-model, separate participant;
   - `(c)` supporting regression;
   - `(d)` target value only.

   Never mislabel `(b)` as cross-model; when cross-model participation is authorized for an R2 physics change, do not rely on `(b)` alone.
7. **Self-checking certification helpers.** A certification helper either verifies its own preconditions directly or accepts an explicit, documented `*_proved_safe`-style flag whose proof is justified at the call site (M02 F-01).

Prebuilt interval laws are a supported input class; soundness tests must include widened-law sweeps, not only exact point fixtures.

## 3. Result Semantics (All Certified Solvers)

- Every certified result reports `terminationReason` (for example `converged`, `sweep_limit`, `refinement_budget`, `mode_sequence_uncertain`) and its achieved enclosure widths. A solver that hits a work limit may not silently return its unfinished box as an ordinary answer.
- Every status label must agree with the reported state inventory (M02 F-07).
- Unsupported combinations of supported mechanisms must return `unsupported_regime` naming the pair of mechanisms involved, rather than a generic `ValueError`.

## 4. Refusal Policy

- Every refusal requires either a physical/mathematical justification or a stated method limitation, documented explicitly as one of those. Unnecessary safeguards that reject physically valid canonical cases (M02 F-04) count as defects.
- Out-of-scope or physically meaningless configurations may be refused directly without building elaborate workarounds for unrealistic inputs.

## 5. Composition Discipline

- **Genuine physical composability.** Once M03 lands, derived physical laws must pass between existing engines without problem-specific glue code or loss of physical meaning.
- **No new engine or schema** unless it registers with the shared system description and unified result envelope (preventing repeats of PR #197 being bypassed by PRs #198–#200).
- **No new per-arrangement CLI** (`tools/<problem>.py`) for textbook problems. Problems are expressed as system descriptions, with lessons as thin presentation layers on top.
- **Honest authored models.** The authored source must describe the solved physical system—no component may stand in disguise for a different physical component (for example, disguising a finite body as a fixed temperature).

## 6. Qualification, Provenance, Pinned Files, and OpenModelica

- **Frozen historical qualification records.** C1, N1–N13, historical workflows, and archived native diagnostics are frozen and immutable, and are not extended.
- **Neutral kernel re-export.** Re-export the exact-rational interval kernel from a neutral package (`simheat/core`) without moving or editing frozen `qualification/**` files.
- **Pin-manifest checks before contract freeze.** Before freezing any contract, check every planned file edit against all pin manifests (including `qualification/h1_n1/SOURCE-PINS.json` and `tools/h1_d1d2_plan.json`). Modifying a pinned file requires an explicit owner decision on pin policy:
  - *Precedent (PR #203, `07a10fb`):* `h1/study.py` carries a bounded N1 historical-drift exemption in `tools/verify_n1_plan_maintenance.py` that stages exact historical pinned bytes (`0205d016…`) for N1 checks/tests while enforcing the exact authorized one-line live delta.
  - *Deferred (A-05c):* `h1/tests/test_verification.py` remains untouched because it is pinned by `tools/h1_d1d2_plan.json:44`.
- **Direct-call provenance.** Keep but do not extend the forgery/provenance layer on legacy direct-call APIs; supported entry points accept a validated law object.
- **Generated facts.** Offline authoring generates `facts.json` rather than duplicating model facts by hand. Independently prepared facts are required only when making a source-fidelity claim.
- **OpenModelica role.** OpenModelica remains an optional independent cross-check on overlapping linear cases, executed only under explicit owner authorization with a bounded plan. Standard CI never runs native jobs.

## 7. Platform

- **Windows support.** Windows is a supported development platform. Maintain a Windows CI job (planned in M03) covering H1 admission and authoring/replay paths.
- **Line endings.** Every file whose bytes are hashed or pinned must carry an explicit `.gitattributes` `text eol=lf` (or `-text`) rule. PR #203 landed 13 explicit `text eol=lf` rules covering all live-hashed N1/N2–N12/viewer files and `AGENTS.md`. Check `git ls-files --eol` before Windows evidence replay without renormalizing protected checkouts.
- **Evidence isolation on Windows.** Run local Windows evidence in fresh worktrees or byte-exact archives—never in the stale protected main checkout.

## 8. Workspace and Merge Discipline

- **Protected main checkout.** `C:\Users\samee\Documents\sim_heat` holds the shared `.git` metadata for **106** registered historical worktrees (all 5 temporary M02 worktrees were safely removed after PRs #202 and #203 merged at `07a10fb`). Treat it as read-only/protected.
- **Preservation and safe teardown.** Historical worktrees, their unstaged edits, and `SIM_HEAT_HANDOFF.md` are preserved. Worktree removal requires owner authorization and must follow Framework v0.2's canonical junction-safe unforced teardown procedure (recursive reparse-point scan, procedural stop if any links exist, non-recursive unlink first, sentinel hash check, then unforced `git worktree remove --`).
- **External packets.** Store durable milestone packets and evidence outside disposable worktrees in `C:\Users\samee\Documents\sim_heat-milestone-packets\`.
- **Merges and branch protection.** Merges to `main` always require explicit owner approval and green CI on exact heads plus post-merge `main` CI verification. Enabling branch protection and required status checks on `main` is recommended (owner-gated).
