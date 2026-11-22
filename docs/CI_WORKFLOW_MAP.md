# CI Workflow Map (Offline Only — Zero Automatic OpenModelica)

Every GitHub Actions workflow under `.github/workflows/` runs **offline** (zero automatic OpenModelica native execution). Workflows are grouped below by the contract surface they verify.

## 1. Primary `main` Integration Gate

| Workflow | Trigger | Required / Scope |
|---|---|---|
| `main-offline-acceptance-ci.yml` (`main-offline-acceptance`) | `push` to `main`, `pull_request` to `main` | Full offline acceptance gate: top-level `tests/`, `h1/tests`, `experiments/h1_spike/checks`, `viewer/network/tests`, Node viewer tests, `render_product_docs.py --check`, N1–N13 offline suites, and representative CLI smoke replays. Records checked-out tree and commit identity. |

### Branch-Protection Enforcement (Repository Admin Closeout)

Configuring GitHub branch protection is a repository-administration action owned by the repository owner (`physicsvigilante`). To enforce `main-offline-acceptance` as a required merge check on `main`:

1. In GitHub **Settings → Branches → Branch protection rules** for `main`, enable **Require status checks to pass before merging** and select **`main-offline-acceptance`**.
2. Keep both `pull_request` (merge-ref) and `push` (final `main`) triggers active in `.github/workflows/main-offline-acceptance-ci.yml`.
3. Verify enforcement with a deliberately failing negative-control PR (confirming GitHub blocks merge until `main-offline-acceptance` passes).

## 2. Source Admission & Local Authoring Workbench

| Workflow | Trigger | What It Covers |
|---|---|---|
| `authoring-workbench-ci.yml` | `push`, `pull_request` | Restricted H1 Modelica authoring workbench (offline source-only admission and preview). |
| `source-preview-ci.yml` | `push`, `pull_request` | Novel composition source-only preview (`not_computed` observations). |
| `workbench-launch-ci.yml` | `pull_request` | Offline workbench launch and route checks. |
| `preview-provenance-ci.yml` | `pull_request` | Offline preview provenance and regression suites. |
| `frozen-thermal-inputs-ci.yml` | `pull_request` | Frozen thermal input integrity across checkouts. |

## 3. Offline Thermal Physics & Analytical Compositions

| Workflow | Trigger | What It Covers |
|---|---|---|
| `calorimeter-prediction-ci.yml` | `pull_request` | Offline thermal engine (`tools/*`, including `offline_investigation.py`) and viewer regressions. |
| `h1-general-conduction-ci.yml` | `pull_request` | General linear H1 conduction offline replay. |
| `composite-wall-ci.yml` | `pull_request` | Composite wall offline conduction checks. |
| `series-extension-ci.yml` | `pull_request` | Series extension of a two-terminal wall. |
| `terminal-resistance-ci.yml` | `pull_request` | Two-terminal thermal resistance checks. |
| `wall-revision-ci.yml` | `pull_request` | Composite wall conductivity revision checks. |

## 4. Qualification Maintenance & Offline Reference Checks (N1–N13)

| Workflow | Trigger | What It Covers |
|---|---|---|
| `qualification-offline-ci.yml` | `pull_request` | Aggregate offline maintenance check across N1–N13 (zero OMC). |
| `h1-n1-plan-ci.yml`, `h1-n1-reference-ci.yml` | `push`, `pull_request` | N1 pre-native plan check and offline interval reference candidate (never native). |
| `h1-n2-offline-comparator-ci.yml` | `push`, `pull_request` | N2 checking-only primary/companion diagnostics. |
| `h1-n3-design-ci.yml` | `push`, `pull_request` | N3 offline migration design checks. |
| `h1-n4-static-reference-ci.yml` | `push`, `pull_request` | N4 generic static physical reference. |
| `h1-n5-thermal-graph-ci.yml` | `push`, `pull_request` | N5 composable thermal graph balance. |
| `h1-n6-exact-junctions-ci.yml` | `push`, `pull_request` | N6 exact area-rod junction equilibrium. |
| `h1-n7-interval-junction-ci.yml` | `push`, `pull_request` | N7 rigorous circular junction enclosures. |
| `h1-n8-corner-crosscheck-ci.yml` | `push`, `pull_request` | N8 independent rational corner crosscheck. |
| `h1-n9-static-trace-ci.yml` | `push`, `pull_request` | N9 original N1–N4 static full-grid crosscheck. |
| `h1-n10-dynamic-ci.yml` | `push`, `pull_request` | N10 independent high-precision dynamic replay. |
| `h1-n11-rational-proof-ci.yml` | `push`, `pull_request` | N11 independent outward rational dynamic proof candidate. |
| `h1-n12-triple-stage-ci.yml` | `push`, `pull_request` | N12 source-only three-case reference staging. |

## 5. Product Behavior, Archived Explorer & Audit Provenance

| Workflow | Trigger | What It Covers |
|---|---|---|
| `product-entry-ci.yml` | `push`, `pull_request` | Product documents (`README.md`, `CAPABILITIES.md`/`.html` parity), start-page navigation, and current-base regressions. |
| `project-audit-core.yml` | `push`, `pull_request` | Core audit corrections, offline regressions, and original archive integrity. |
| `pr51-f01-typed-provenance.yml` | `push`, `pull_request` | Typed steady/campaign provenance over original archives. |
| `h2-h1-offline-ci.yml` | `push` | H2/H1 integration offline verification on `main`. |
| `h2-generic-viewer-ci.yml`, `h2-s1-steady-viewer-ci.yml`, `h2-viewer-ci.yml` | `push` | Archived thermal explorer, native-data hash provenance, and browser smoke checks. |
| `h3-campaign-repin-ci.yml`, `h3-ring4-offline-ci.yml`, `h3-shared-run-ci.yml`, `h3-source-pair-ci.yml`, `h3-teacher-whatif-ci.yml` | `push` | Teacher what-if, Ring4 offline authoring/reference, shared-run SHA refusal, source-pair provenance, and campaign receipt refusal regressions. |

## Scope Boundary

- Frozen `qualification/h1_c1/` records and `qualification/h1_n1/` source pins remain immutable; none of these workflows regenerate frozen seals or grant native execution authority.
- All offline analytical tools (including the typed adapter `tools/offline_investigation.py`, schema `sim_heat.offline_investigation/1`) keep `nativeExecuted=false`, `nativeQualified=false`, `independentlyCertifiedReference=false`, and `runnerConsumable=false`.
