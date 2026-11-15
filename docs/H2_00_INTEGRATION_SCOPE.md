# H2-00 — first clean H1 source integration candidate

Record date: 2026-11-15. Tracking: [sim_heat issue #11](https://github.com/physicsvigilante/sim_heat/issues/11). **R2 independent-review gate**, even if reused source bytes are unchanged. Not an H1 acceptance or mainline merge verdict.

## Candidate provenance and curation

- Destination base: `main` at `49a2cc42462b47026e86313bfeff39a9b17081cd`, retaining the original `01_heat.pdf` Git blob exactly.
- Imported source: experimental PR #10 at `a314671828b32b24876250a84f5c057c9d93411f`, following reviewed H1-C1-F0 source commit `dd8c9432abe97563414bb3ed809e61e673473812`.
- Bit-for-bit preserved H1 subtree: `3f695b7a68bc6e344ae2512886ca7d9fffd9a539`.
- Bit-for-bit preserved experiments subtree: `895f450964832465d7f1d84099c2ab444ddc1094`.
- Bit-for-bit preserved docs subtree at import: `f6dfed0b11a6b82c227ae2fa3e1b7d3d293c0626`. This record is additive; original drafts remain historical evidence.
- Bit-for-bit preserved C1 technical-freeze subtree: `e2f741e3ee535236f628d3559b7a95d6c7935a34`.
- Retain the unchanged generic native runner and numerical-companion helper/scripts needed by existing regression tests, with exact Git blobs:
  - `tools/h1_native_batch.py`: `6e6d97f69650e695a90c48f82fcd864618e569e9`;
  - `tools/h1_compare_companions.py`: `accf8d253aac35bc8014cc08874a23d758249b13`;
  - `tools/h1_d1d2_plan.json`: `b7af78d77fd06ba3bb935a54f8dccc806aaf5923`;
  - `tools/h1_resolution_campaign.json`: `99b5f53364e187b4f77dba9cef7f049759690034`;
  - `tools/h1_resolution_campaign.py`: `c0da552862398d87e0f38375d01255ba5c8200f8`.
- Historical, case-specific S1 one-shot launcher scripts `tools/h1_cloud_s1.py` and `tools/h1_mat_s1.py` are **not imported** into this mainline candidate; their exact original bytes and launch evidence remain on their historical experimental branches.
- All prior `.github/workflows/*once.yml` experiments are **not imported**. They are not safe general-purpose CI and must not be silently enabled on main.
- New root README/AGENTS, this additive record and an offline-only CI workflow are packaging/governance changes. No physical model, numerical allowance, parser, reference solver, MAT adapter, verifier, or reusable runner is rewritten.

## Scope and domain

The curated H1 implementation admits constant-property, lumped thermal bodies, conductive storage-free rods and maintained-temperature boundaries. Public requests return only admitted meanings (temperature, oriented rod flow, difference, relative stored-energy change). Matrices, time associations, native parameters/aliases, and signed conservation balances are checked by existing generic policies. This is not arbitrary Modelica, symbolic inversion, convection/radiation, distributed conduction, or a teacher-facing viewer.

Several historical reports under `docs/`, `h1/README.md` and `experiments/h1_spike/README.md` accurately say "no native run" at their original milestone. Those records are **not revised**; actual later native results are recorded independently and linked below. The inclusion of a candidate in main does not upgrade the current `diagnostic_only` or `nativeQualified=false` status.

## Acceptance and evidence

1. **Source identity**: source Git subtree/blob equivalence listed above, original PDF unchanged, no imported native workflow triggers. Review diff and CI source manifest.
2. **Current-source offline gate**: Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0 and optional checking-only mpmath 1.3.0. Entire `h1/tests` suite (historically 149 tests), separate original arithmetic fixtures, and a true offline admission/reference-preparation smoke for the developer bridge. No new native build/launch in integration CI.
3. **Previous pinned native evidence**: S1 saved-MAT [experiment and failure](https://github.com/physicsvigilante/sim_heat/actions/runs/43689753800), [D1/D2 successful native](https://github.com/physicsvigilante/sim_heat/actions/runs/43691263273), [D2-K2 and numerical-resolution runs](https://github.com/physicsvigilante/sim_heat/actions/runs/43693191224), and [developer bridge native checks](https://github.com/physicsvigilante/sim_heat/actions/runs/43699424883). Historical ZIP SHA-256 and file hashes are in the original run artifacts/reports. These are **not** new integration-branch native CI.
4. **Review**: Chat A self-check and passing CI on the final pinned source SHA, then one full separate-chat R2 review in `physicsvigilante/review_sandbox/projects/sim_heat/pr-<new-number>/`. The reviewer must inspect physical/evidence boundaries, negative tests, stale-identity controls, and missing production-trust gates. A separate conversation is not a distinct model or independent physics expert.
5. **Merge**: draft/unmerged until explicit owner approval; post-merge offline CI must be verified and the central review record updated. Do not merge experimental PRs #1–#10 en masse.

## Known remaining risks

The source has author-tested fixes to prior R1/R2 findings; independent signoff for all correction details, reference-error budgets and final native qualification remains open. No unrestricted user-submitted Modelica isolation or safe compiler-execution service is claimed. The C1 separate-author transfer trial remains unselected. The viewer, classroom observations, new physical laws and full charter-level transfer are outside this integration.