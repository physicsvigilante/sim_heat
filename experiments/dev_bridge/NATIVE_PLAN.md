# DEV-BRIDGE-1: reviewed case and bounded native continuation

Date: 2026-11-15. Parent case revision: `75aecc053d2ba34526339c259602f8482ea36720`. The user instructed **"correct any errors and continue"** after the proposed single-case cloud test. This record authorizes one attempt through the existing frozen runner, not a retry series, merge, or H1-C1 independent-author claim.

## Review and corrections

The exact committed TASK.md, model.mo, study.json, reference facts and previous offline report were reopened. All two body, two reservoir and five rod inputs, the four ideal connection nodes, all ten endpoint connections and six passive observations agree with the precommitted task. The graph has two independent cycles. No physical-model, connectivity, request or provenance correction was required. Original task/model/study/reference bytes are preserved.

The missing assurance was a retained, independently implemented reference-accuracy calculation and a case-bound native plan. `check_reference_accuracy.py` now evaluates an explicitly derived two-state closed-form solution and its exact exponential flow integrals using mpmath 1.3.0. It imports none of the production/reference implementation, NumPy or SciPy. It is checking-only evidence, not a replacement solver or runtime adapter. It remains **same-author** evidence, not independent-person approval.

Two different input interpretations are examined: intended decimal task values and exact binary representations of those inputs. All 42 recorded reference quantities at all 2001 planned times and four integrated-flow histories agree within one hundredth of the existing per-output allowances. The worst ratio to that 1/100 budget is 0.9375 (decimal interpretation, a conductance parameter) and 0.78125 (binary-input interpretation). These ratios are below 1, but the parameter margin is narrow; no allowance was increased. A selected-point 100-digit repeat differs from the 80-digit values by at most about 5.66e-76 in the compared outputs. These are high-precision comparisons, not certified interval bounds.

One error in the new evidence script was caught before publication: it initially required the stored float grid to equal `10*i` bit-for-bit. The actual predeclared policy uses `20000*(i/2000)`, which can differ by rounding. The check now tests that existing grid definition and evaluates at the stored binary timestamps. No planned timestamp, source setting or numerical allowance was changed. The failed initial evidence-script log is retained in the downloadable continuation evidence.

The local reconstructed 105-test historical core passes again. This is not a claim about all 149 current tests: the full current repository suite will run in the cloud preparation before any build. No current test is replaced or removed.

## Independent-algorithm predictions (not native results)

The two positive modal time constants are approximately 3435.743069 s and 1148.989755 s. The original 20000-second horizon is 5.821 slow time constants; the 10-second nominal interval gives h*lambda_fast approximately 0.0087033, below 0.01. Keep the authored 2000 intervals, DASSL and tolerance 1e-8 unchanged.

The analytical bridge-flow reversal is approximately 1726.233322 s, refining the earlier rounded "around 1730 s" prediction. Initial oriented flow is -6 W; final predicted flow is approximately +2.028651124 W. Different maintained hot/cold reservoirs imply a non-equilibrium steady state with sustained heat transfer, not common-temperature equilibration of the two bodies. The limiting body temperatures are approximately 320.554580153 K and 310.401908397 K.

Pre-run checking reference seal: `d644302bebfa877e1739a70850a0b8f3bb878ef7bed93158b431ec2189f73ce2`. A changed cloud reference or failed precision comparison stops before compilation; it is not adjusted after native results.

## Exact attempt

- Branch: `experiment/h1-developer-thermal-bridge`; workflow `.github/workflows/h1-dev-bridge-once.yml`, triggered only by a push changing that file on this branch; run-attempt must be 1.
- Plan: `experiments/dev_bridge/native_plan.json`, SHA-256 `6404fb03f5b141851f4af520da506cf8f997903cff2385181d450c2ecb3f2709`.
- Unchanged `tools/h1_native_batch.py prepare` runs the current offline suite, validates all source pins and seals the bridge reference. The independent-algorithm script then reproduces the high-precision report in the artifact before any OMC model build.
- Ephemeral Ubuntu 24.04 runner; OpenModelica 1.27.0, MSL 4.0.0, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0. mpmath 1.3.0 is an extra checking-only dependency, not a production backend. Installation/network access stays on the ephemeral runner, not the user's PC. No network-isolation claim.
- Unchanged `tools/h1_native_batch.py execute` performs at most **one build, one model launch and one explicit compiler-version query**. Setup-action probes are separately logged. Native input copies, setup/settings validation, MAT extraction, signed-alias provenance, reference comparison and conservation checks use the frozen implementation.
- Stop on the first error; no automatic retries, changed tolerances, invented exports or physical tuning. Keep raw MAT, normalized CSV, reference and accuracy reports, source/MSL manifests, commands, diagnostic reports and any failure. No additional native companions or property revisions in this attempt.

## Interpretation

A successful attempt establishes developer-authored assembly reuse for this fixed structure without arrangement-specific production changes. It does not establish blind authoring, public-interface usability for another author, general structural editing, all thermal networks, full H1 acceptance or classroom effectiveness. The checker keeps `diagnostic_only` observations and `nativeQualified=false`. The external-author C1 remains unselected. No merge or change to the freeze is needed.
