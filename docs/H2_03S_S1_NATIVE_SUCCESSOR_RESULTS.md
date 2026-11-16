# H2-03S — corrected S1 native successor: one successful bounded diagnostic attempt

**Date:** 2026-11-16. **Status:** `diagnostic_checks_passed_not_native_qualified`. This is an author-directed, source-pinned native evidence inspection; **not** Chat B's independent R2 review or scientific acceptance.

## Exact provenance and preservation

- Original earlier S1 MATv4 workflow [43689753800](https://github.com/physicsvigilante/sim_heat/actions/runs/43689753800) remains **failed** at its original post-build extraction. Its later offline MAT recovery is separate and unchanged.
- First H2-03S one-shot [43757179599](https://github.com/physicsvigilante/sim_heat/actions/runs/43757179599) remains **failed** during input-hash preflight, with **zero** version queries, builds or launches. The failure was a mistyped `h1/__main__.py` pin, not changed source bytes; the original [failure report](https://github.com/physicsvigilante/sim_heat/blob/experiment/h2-s1-steady-native-once/docs/H2_03S_S1_FAILED_ATTEMPT_01.md) is preserved.
- **Corrected and newly authorized** successor workflow [43820600508](https://github.com/physicsvigilante/sim_heat/actions/runs/43820600508), attempt **1**, **completed/success**, source head **`337ef554fb40da9408485bda8f2a4024c84720f6`**, branch `experiment/h2-s1-steady-native-successor-once`. Its post-run documentation commit must not be mistaken for the actually executed SHA.
- Pinned corrected execution plan `tools/h2_s1_native_plan_v2.json`, exact SHA-256 **`9ebeab496f3b7ea22ec5de59acc6983a6062d26be1546cf0ac3b9c9a698f0d7b`**. All **22/22** pinned input-source SHA-256 values were checked against the exact branch source before the workflow was triggered. No physical-model, checking policy, Modelica library, MAT adapter or numerical-tolerance revision.
- Actual uploaded [artifact 14204656273](https://github.com/physicsvigilante/sim_heat/actions/runs/43820600508/artifacts/14204656273), `h2-s1-steady-successor-evidence`, **235,746 bytes**, downloaded and independently SHA-256 checked to **`82b4a87b66e0022d582da931253649b3829f6633119a57081c02dc253dc5dbd9`** (matches GitHub's original upload log/API digest). ZIP CRC passes for all 94 members; archived `attempt.json` lists **89/89 original file hashes**, all independently recomputed and matching.
- Artifact was inspected **read-only**; compiled executable and object files were **not executed** or installed by the inspector.

## Actual source, runtime and execution counts

- Recorded `GITHUB_SHA` `337ef554fb40da9408485bda8f2a4024c84720f6`, `GITHUB_RUN_ID` `43820600508`, `GITHUB_RUN_ATTEMPT` `1`. Original `model.mo` SHA-256 `3228323714b2f886279aa90c46c1c49c9143e2d8b9c6de032389c750b6848f1c`; study SHA-256 `83bb6badc19e55008455083cde64adc2d53ba32c1d5f009d5b1b3594bd5f2405`.
- Actual `compiler_version.stdout`: **OpenModelica 1.27.0**; installed Modelica **4.0.0**; saved `msl_manifest.json` has **2,508** Modelica source-file hashes. Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0 on Ubuntu-hosted Linux. Compiler binary SHA-256 `18f36345eee8a8b3b6d170afe5bbe125d1c8368120f00a393754e01fd50dabfc`.
- Source reader `tools/h1_native_batch.py` consumed the exact pinned plan; `offline_tests.returncode=0` and `offline_tests.stderr` reports **151/151 passed**. Reference bundle was generated and sealed before OpenModelica installation/build.
- **One** explicit compiler-version query, **one** `buildModel` invocation, **one** executable launch; all corresponding return-code files contain `0`, and logs/checking were successful. No repeat, fallback, changed limits or second case. Final outer attempt status exactly **`diagnostic_checks_passed_not_native_qualified`**; `nativeQualified=false`.
- S1 original presealed reference seal `d4b04b2bfaa38afacda550bea9433b5645af83e173d0b28632b1b5225e8e8074` matches the recovered prior S1 diagnostic seal. No reference data or tolerance was altered to fit output.

## Native outputs and checking

- Raw MAT result `case_01/model_res.mat` SHA-256 **`1d5ae021cf87eda8c14418b638e5cc3c353877358b52585deb7a0f7d375a0672`**, verified both against uploaded bytes and outer attempt manifest.
- Native-derived normalized CSV `case_01/normalized.csv` SHA-256 **`1133504ba47df0d4b7fcaec46f090662027ff7feff6999401aad50dbd7d629d1`**, verified against uploaded bytes and verification. It has 19 columns (time + 18 registered values), **2** distinct steady algebraic evaluation indices `0` and `1`, plus **1 identical repeated terminal row**; the indices are **not seconds** or actual temperature dynamics.
- Checker `case_01/verification.json`: **56/56 checks passed**, maximum error/allowance ratio **0.03125**. Required original S1 native channels were present; no invented channel or substituted analytical result. Source ports and shared MAT aliases are explicitly recorded; a distinct named output is **not** an independently measured sensor quantity.
- Recorded junction `copper.T_b = steel.T_a = 366.4562880324543 K` (93.306288 °C); recorded `copper.Q_flow` and `steel.Q_flow` approximately **+1.0792824946508013 W** from hot to cold; hot/cold boundaries **373.15 K / 273.15 K**, power supplied at hot and absorbed at cold with opposite signed W. The independently stated series-resistance prediction is junction **366.45628803245436 K** and power **+1.0792824946508015 W**. Very small differences between algebraic export indices reflect floating-point representation; do not call them physical time variation.
- The inner verification layer explicitly records `evidenceKind=unattested_output`, `nativeExecuted=false`, `nativeQualified=false`, and `publicRequestStatus=diagnostic_only`. That reflects the checker's deliberately untrusted-candidate interface. **Separate outer evidence** is the actual GitHub native process, source hashes, return codes and raw MAT/CSV files. Neither layer turns this into independently authenticated experimental measurement.
- This re-run produced raw MAT/CSV hashes matching the previously recovered saved MAT evidence, consistent with deterministic native output. The earlier workflow is still a historical **failure**, not upgraded.

## Next safe development boundary

The successful **new** attempt is now eligible as historical/native diagnostic source material for **a separately implemented and independently reviewed steady viewer adapter**. Do not feed it directly to H2-02's transient `native_case/1` schema or label the algebraic indices as elapsed time. H2-03S requires mode-specific contract/validator, strict node ownership, proper signed power and a UI that disables playback/time history in steady mode, with real desktop/mobile browser tests and stale-refusal protections.

Native execution alone does **not** qualify H1, certify reference error, prove C1 unfamiliar-model transfer or establish classroom effectiveness. No mainline merge, H2-02 source edit or reviewer finding occurred in this run; keep the single-use workflow on its experimental branch and preserve all earlier failures.
