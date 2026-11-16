# H1-C1 F0 V2 — clean-process and distinct-host reference reproducibility

**Purpose:** address PR #31 independent Chat B finding F-03 *only*, without changing the numerical/physical reference that passed its scoped 100× sampled check. This is a **new offline evidence experiment**, not native simulation, solver authorization, production code change or retrospective alteration of historical data.

## Source and lineage

- Frozen original H1 F0 source: `dd8c9432abe97563414bb3ed809e61e673473812`.
- Preserved first-authored task/model/study, original failed F0 reference (old seal `d76c98f37a0629b56d977c960d1e75694e1121832a9d5281f68bb972d31a365b`) and original unlaunched primary native plan remain unchanged.
- PR #31 reviewed exact V2 source: `d857c8e807612026ecdf624277b4ace3977fefe3`; reviewed new V2 seal `d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9`.
- This follow-up adds only `capture_v2_runtime.py`, `compare_v2_reproduction.py`, this scope document and an **offline-only** workflow. The original `prepare_reference_v2.py`, original Modelica, study, H1 checker, policy, Mat adapter, sources, reference files and old sealed artifacts are not modified. All previous reviews remain bound to their exact SHAs.

## Frozen execution boundaries

Two independent GitHub Actions hosted jobs on **Ubuntu 22.04** and **Ubuntu 24.04** use exact Python **3.13.5**, NumPy **2.3.5**, SciPy **1.17.0**, mpmath **1.3.0** and threadpoolctl **3.6.0**. Each host downloads exact release wheels first, records SHA-256 of all installed wheel archives, and installs directly from those downloads (no untracked install-time resolver change). Each host then invokes `prepare_reference_v2` in **two distinct fresh Python processes**, with a separate clean output directory and retained full **V2 bundle, in-process repeat bundle, and report** for each. The original script also performs two in-process preparations, so clean-process comparisons are meaningful beyond PR #31's same-process test.

Before any reference comparison, record actual `threadpoolctl.threadpool_info()`, the **stdout** of `numpy.show_runtime()` (not its unusable `None` return), NumPy/SciPy build configurations, Python package versions, installed WHEEL tags and RECORD identities, OS image/version, CPU model/features and selected runner metadata. Do not record secret environment values or claim actual physical hardware authentication.

One comparator checks both full bundles and exact canonical seals on each host and, in an independent follow-up job, across the two runner-image labels. It compares **full saved JSON structures**, records different leaf counts with bounded field/index examples, raw file SHA-256, declared reference seal, 37 columns/4001 points/4 energy-integral histories, original physical spec fingerprint, sampled 100× report budgets, and V2-specific static exact-rational margin. It explicitly checks the **approved PR #31 V2 seal**. If *any* value, metadata or raw byte differs, or a host/package/BLAS identity is missing, status must be **REFUSED**, all available files/results must be uploaded, and no new seal or reference certification may be claimed. Different OS images are expected *only* in separately stored runtime-provenance files, not the sealed bundle.

In-memory negative-control checks corrupt a saved static value, a dynamic temperature, a flow integral and a tolerance allowance; the original seal must detect all four, while the independent high-precision strict-100× checker must refuse the three numeric corruptions. No mutation may reach the saved candidate reference. The Python invocations use `-B` without optimization and explicitly guard against `-O` weakening assertions. These tests are **offline integrity controls**, not native model tests.

## Failure/qualification interpretation

- Green matrix/aggregate jobs demonstrate reproducibility **on precisely the two tested hosted images and processes** and actual captured source/package/runtime identities; they are not a universal mathematical/host determinism theorem or an independent R2 signoff.
- A single differing bundle, a missing wheel hash, missing loaded BLAS evidence, violated 100× budget, absent result, or invalid seal is a recorded **refusal**, not a reason to silently patch original reference or widen native tolerances.
- The prior [CI #43911222494](https://github.com/physicsvigilante/sim_heat/actions/runs/43911222494) old-seal assertion failure with no saved alternate digest remains historical. Two new clean hosts may strengthen reproducibility but cannot reconstruct that missing prior digest or prove its root cause.
- Any new host/BLAS divergence must be inspected field-by-field and may require another distinct reference lineage/review. There is **no** authorized OpenModelica query/build/launch, no permitted native plan, no teacher-facing result and no change to the nine original `not_computed` requests.
- This milestone requires fresh exact-head CI and one **focused independent Chat B R2 review** of both host artifacts, aggregate artifact and source changes before claiming V2 reference certification. Native F-02 one-shot source/host gate stays separately blocked pending review/owner authorization.

**Status:** experimental checking-only assurance. Successful automated jobs are *necessary but not sufficient* for release.
