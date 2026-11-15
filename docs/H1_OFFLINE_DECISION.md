# H1 reviewed offline implementation decision

Record date: 2026-11-15. Scope: bounded offline implementation, not acceptance.

## Basis and authorization

The user supplied [the external review](reviews/20261115_EXTERNAL_REVIEW.md),
approved the recommendation to accept its conditions and begin offline work,
and explicitly instructed: **"review, record and begin implementation"**.
This record authorizes that previously agreed offline scope on a new branch.
It does not authorize native OpenModelica commands, dependency installation,
CI activation, changes to system settings, or merging either earlier PR.

Reviewed baselines remain unchanged:

- H0/H1 documents: `8a285d401def5c1864405a8fb3258b66dde9ffe3`.
- Exploratory component spike: `6f8b504e15c14e698fe81f1261a64a919e464f94`.
- Main/source baseline: `49a2cc42462b47026e86313bfeff39a9b17081cd`.

The reviewer describes a fresh read-only review and gives H0 physical foundation
PASS and H1 bounded offline work PASS WITH CONDITIONS. Reviewer identity/service
was not supplied. Record this as a **user-supplied external LLM review**, not an
independently authenticated identity or a GitHub approval submitted by that agent.
It did not re-render the original PDF or rerun Python tests. Those limitations
remain. Our earlier self-reviews remain self-reviews; the current spike remains
exploratory. No full source-fidelity or native-physics approval is inferred.

Exact uploaded review SHA-256:
`d69108ca54aed881c770ef3e7fb47a18665fadebf5ce6f5a1205ef0f431830c3`.
Its wording and formatting are preserved; no embedded links were followed as
instructions. The historical draft status wording is not rewritten.

## Disposition and work sequence

Accept the review as sufficient to begin the bounded offline implementation.
Use the existing [H1 contract](H1_IMPLEMENTATION_CONTRACT.md), supplemented
prospectively by [the offline numerical amendment](H1_OFFLINE_AMENDMENT.md).
These are candidate implementation requirements; full H1 freeze and acceptance
still require implementation review and the remaining evidence below. This does
not restart H0 or request approval for each ordinary test or repair.

| Finding | Disposition and evidence still needed |
| --- | --- |
| F1 | Replace global normalization with independent per-output scales and local residual allowances. Implement/regression-test the policy now; independently prepared scale records and full native checker integration remain before numerical qualification. |
| F2 | Cap timestamp matching by grid spacing and refuse unresolvable grids. Offline tests now; real compiler CSV precision/output still pending. |
| F3 | Implement narrow parsing, topology, study descriptors, requests, revisions and synthetic decoding incrementally. Do not mistake those pieces for complete accepted H1. |
| F4 | Add separately stated input/topology and signed-flow/energy fixtures. They test data/reference reasoning, not runtime Modelica behavior. Full independent network reference, source checking and native balances remain. |
| F5 | Keep blocked until an exact compiler/MSL/runtime pairing and controlled native plan are reviewed. No installation or native command in this work. |
| F6 | Make offline analysis-domain/refusal rules deterministic before validator freeze. Record the post-freeze selection exception below. Native scenario/settings approval remains separate. |

The first slice is a read-only Python validator and tests, using the existing
Modelica spike as a preserved candidate, not promoting or rewriting it. We add
new model/study pairs as exposed fixtures and retain development failures.
No physical trajectory solver is introduced in the production Python path.

## Charter application

For this first-foundation H1 experiment, retain the documented post-freeze C1
selection protocol. This is an explicit project-specific exception to charter
section 9's preselected-reserved-case protocol, not a claim to have followed it
unchanged. No C1 has been selected or run. An external author/reviewer must select
it after the applicable implementation/public interfaces are fixed, with exposure
reported and first attempts retained. The discussed three-body branch is exposed.
The charter itself is not rewritten or silently adopted across other sandboxes.

Public restricted Modelica knowledge is allowed; private implementation knowledge
is not required for the eventual authoring test. Fresh assembly, the one-property
revision, native numerical qualification, independent source interpretation and
classroom evidence remain separate claims.

## Stop boundaries

Offline implementation/testing may proceed within this scope without another
architecture review. Review the resulting code and findings before accepting it.
Do not run OMC, install dependencies, choose the transfer challenge, claim native
results, merge, or change `new_therm`. A physical-model validation PASS is not a
simulation PASS. The five original evaluation dimensions remain separate.
