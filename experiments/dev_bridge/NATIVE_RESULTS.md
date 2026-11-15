# DEV-BRIDGE-1: native developer-authored assembly diagnostic

Date: 2026-11-15. **The corrected cloud workflow completed successfully. All 98 existing numerical/physical diagnostics pass.** This is a developer-authored assembly-reuse result, not the independent-author H1-C1 claim or full H1 qualification.

## Exact execution and integrity

- Successful run: https://github.com/physicsvigilante/sim_heat/actions/runs/43699424883
- Executed commit: `b3779603563db4b26aeef8c2dd552965698deb4f` on `experiment/h1-developer-thermal-bridge`, PR #10.
- Artifact: `14155084346`, `h1-dev-bridge-bound-reference-evidence`, 1,523,705 bytes.
- Original ZIP SHA-256: `f16975a25eea79f61f7819fb9e704ab04a33630044a51a0d062b8399c1c9ce38`.
- Raw MAT SHA-256: `e1da06d7223dd271317881b2d737b73c40ec643a8d533568bf7ef3bfbb5443a9`.
- Reference seal: `d644302bebfa877e1739a70850a0b8f3bb878ef7bed93158b431ec2189f73ce2`, sealed and high-precision checked before the native build.
- Downloaded artifact: **91/91 manifest file hashes match**. The retained pre-native preparation copy matches the hash in the accuracy report. All **14 frozen execution/checking source pins** match H1-C1-F0.
- Actual MSL source-manifest SHA-256: `15bcd69467c3ac4b183c04a200452eb34dcdf7989cebf888c6ec04ead38a194a`, matching the previously observed freeze record.
- Runtime: OpenModelica 1.27.0, MSL 4.0.0, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, checking-only mpmath 1.3.0, ephemeral Ubuntu 24.04 runner. Complete platform details and source manifests remain in the artifact; no complete OS-level freeze is claimed.

## Counts and preflight history

There were **two CI attempts but only one actual native build and one model launch total**. The first run `43698836525` passed 149 tests but stopped at an overly strict local-versus-cloud reference checksum comparison, before any OpenModelica setup, version query, build or launch. Its original failure remains preserved. See PREFLIGHT_CORRECTION.md for the exact diagnosis and prospective continuation scope.

The second run also passed **149/149 offline tests**, validated the independently calculated high-precision reference against its own unused preparation, then performed **one explicit version query, one build and one launch** through the unchanged shared batch runner. There was no native simulation retry, no physical tuning and no change to the solver settings or tolerance policy. Setup-action package/version probes are recorded separately in its installation logs.

## Results from actual native output

| Item | Result |
|---|---:|
| Physical interval | 0 to 20,000 s |
| Canonical time samples | 2,001 |
| Mandatory output histories/parameters | 42/42 |
| Public requested histories | 6/6 diagnostic-only |
| Existing numerical/physical checks | 98/98 pass |
| Largest error-to-allowance ratio | 0.7057009322603044, below 1 |
| Largest temperature discrepancy from reference | 8.952437269726943e-6 K |

The effective initialization XML confirms DASSL, tolerance 1e-8, 2000 intervals and MAT output. There were 2002 raw output rows; one identical repeated terminal row was collapsed by the unchanged decoder. No interpolation or missing-value reconstruction was used.

| Native quantity | Initial | At 20,000 s |
|---|---:|---:|
| Left body temperature | 298.15 K | 320.5698596902518 K |
| Right body temperature | 328.15 K | 310.4266052636757 K |
| Bridge flow, positive left to right | -6 W | +2.0286508853152214 W |
| Left stored-energy change | 0 J | +15155.825150610235 J |
| Right stored-energy change | 0 J | -21693.43515726092 J |
| Hot-reservoir heat supply | +13 W | +9.933899640855579 W |
| Cold-reservoir heat supply | -10.8 W | -9.945704215565364 W |

**Observed flow reversal:** the recorded bridge flow is -0.009653756395368874 W at 1720 s and +0.005807881808732419 W at 1730 s. The native samples therefore bracket the reversal in that interval. The separately calculated analytic crossing is about 1726.233322 s; it is not an exact crossing time measured by the native output grid.

Reference histories, imposed initial temperatures, oriented Fourier-law flows, ideal-node temperature/flow constraints, energy ownership and integrated body/network heat exchange all pass. The largest normalized check is a quadrature-aware body-integral residual, not a temperature error of 0.706 K. Endpoint temperatures are finite-time observations; with two maintained reservoirs this system approaches a non-isothermal steady state, not common-temperature isolated-body equilibrium.

## Offline audit after download

All 42 normalized output columns were compared directly against their corresponding recorded MAT data rows, signed aliases and parameter entries using the saved name/dataInfo metadata and provenance sidecar. They match exactly at parsed double precision. The normalized timestamps also match raw MAT timestamps; shared aliases are not claimed to be independent physical measurements.

The unchanged frozen numerical verifier was rerun locally on the saved native-derived CSV, receipt and presealed reference. Every report field matches the cloud verifier report exactly. No downloaded executable was run. The actual native result did not require a post-run adapter or physics repair.

## What changed and what this establishes

The original fixed task, model.mo, study.json and checking-reference physical facts retain their original hashes. No edits were made to the Modelica component library, parser/topology rules, observation/revision interface, reference solver, error/time policies, MAT/CSV readers, numerical verifier or shared native runner. Additions were case-specific checking evidence, execution-plan data, launch-only workflows and documentation. The only corrected implementation was the newly added evidence script's binding to its pre-native reference; it does not supply production answers or modify acceptance calculations.

This supports the scoped statement: **a new, developer-authored two-body/two-reservoir/five-rod arrangement executed and passed the fixed diagnostic path without arrangement-specific production changes.** It does not establish unfamiliar-author usability, independent task selection, blind C1 transfer, general structural editing, all supported numerical regimes, tighter/dense companions for this bridge, or classroom effectiveness. The generic checker retains `nativeQualified=false` and `diagnostic_only`; actual build/launch provenance is supplied separately by the execution manifest.

The external-author C1 remains unselected. No frozen evidence or failed attempt was rewritten, no merge was required, and no production-branch promotion is implied by this result.
