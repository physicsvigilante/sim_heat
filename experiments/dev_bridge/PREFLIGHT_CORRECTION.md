# Bridge preflight correction: bind the reference to its actual preparation

Date: 2026-11-15. This prospectively supplements NATIVE_PLAN.md under the user's instruction to **correct errors and continue**. It does not erase the first failed workflow or authorize more than one actual model build and launch.

## First CI attempt, preserved

Run `43698836525`, commit `c8184490ef8a3798bd8873831670ac906b6fc64d`, passed the complete **149-test** repository suite and prepared the model/reference successfully. The new accuracy-evidence script then refused because it demanded the cloud reference's full checksum equal a locally generated reference's checksum. OpenModelica setup was skipped: **0 version queries, 0 builds, 0 model launches**. Artifact `14155995483`, ZIP SHA-256 `fe442e3e726abea5d5c61077d9fc029a1b1f1b1958e69dc6ae1072cef1f4f2f0`, retains the failure.

The local seal was `d644302bebfa877e1739a70850a0b8f3bb878ef7bed93158b431ec2189f73ce2`; the cloud preparation produced `846fcbd4a47dbd30eec6c66e28eaa33ecf05e75bb390c1726af66ba3dc5af15b`. Both have exactly the same physical specification, grid, units, temporal policy, reference implementation hashes and declared NumPy/SciPy versions. The computed reference histories nevertheless differ slightly: at most 1.42e-12 K, 5.51e-13 W and 1.05e-9 J. Parameter values agree exactly. Derived allowance differences are at most 8.48e-22 (relative difference below 1.92e-16), from the unchanged algorithm, not a manually widened policy.

The mistake was assuming cross-host bitwise identity for numerically calculated artifacts. The lower-level source of the rounding differences has not been isolated; no claim of identical BLAS/CPU/OS environments is made.

## Narrow correction and offline tests

Only the **new checking-evidence script** changes. It now checks the bundle's internal seal and binds it to the unused preparation's recorded reference seal and file hash, physical source pins, and reference implementation identities. The preparation must say `prepared`, contain exactly this case, and have all three native counters zero. It independently checks all 42 quantities and four flow integrals at the same 1/100 allowances as before. No reference column is edited, replaced or filled from the checking formula.

Rechecking the saved cloud preparation with the corrected script passes both full-grid 80-digit interpretations and the selected 100-digit repeat. The worst accuracy-budget ratio remains 0.9375. Seven focused local binding checks pass: valid saved preparation accepted; already-launched, non-prepared, wrong-seal, wrong-file-hash, wrong-physical-pin and modified-payload cases refused.

The frozen Modelica library, physical task, model, study, reference specification, parser, numerical policies, MAT reader, generic reference solver, verifier and native runner are unchanged. C1 remains unselected. The code change belongs to pre-execution evidence handling, not production physics or result acceptance.

## Corrective continuation, not a repeated simulation

The latest user request authorizes correcting errors and continuing. We interpret it narrowly as allowing **one corrective CI preparation and the still-unspent one-build/one-launch diagnostic**, with the first failure retained. This is explicitly a second CI attempt, not a claim of first-attempt success and not an automatic retry loop. If this corrective attempt fails, stop without another workflow or native retry.

Use `native_plan_bound_reference.json`, SHA-256 `27f7ac1ec97b2b832ed3b00cf1e6afceacf345e27f3bddf2be42bd143ceb2217`. Compared with the initial plan, only the new accuracy script's hash changes. Its new SHA-256 is `b17d66ef97bdbc726c573fa70672061f3e0fe52210dd3d4656f15552421e870b`. The original plan and workflow remain historical files; a distinct branch/path-restricted workflow wraps the same frozen prepare/execute commands.

Before the accuracy check, preserve a copy of `attempt.json` as `prepared_attempt.json`. Bind the report to that copy so the pre-native state remains auditable after the runner updates its live state. A successful check is still required before OMC installation/build. Preserve both source and cloud evidence; do not compare a native output before its host-specific reference is sealed and independently calculated accuracy is assessed.

No merge, new physics, native parameter change, tolerance relaxation, or general qualification is authorized by this correction. Across both CI attempts the native ceiling remains **one build and one model launch total**.
