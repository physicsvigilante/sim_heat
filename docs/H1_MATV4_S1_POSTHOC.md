# H1 S1 MATv4 saved-native-output diagnostic — after reader correction

Date: 2026-11-15. **No new native run or build during this step.** This is a later, read-only decode and verification of the original raw MATv4 result from a failed workflow. It is not a retrospective claim that the original workflow finished successfully.

## Source and unchanged evidence identities

- Actual native cloud run: https://github.com/physicsvigilante/sim_heat/actions/runs/43689753800
- Executed Git commit: `547d482f1034e8af3364552c425f6fd9544dab88`; workflow result **failure** at MAT schema admission, after one build and one launch succeeded.
- Evidence artifact: https://github.com/physicsvigilante/sim_heat/actions/runs/43689753800/artifacts/14151084575
- Original artifact ZIP SHA-256: `1db4e13999232c8f51b4d40c52ac6ecccb2a861f03309ce57c7ef02c62e6880e`.
- **Unchanged raw MAT SHA-256:** `1d5ae021cf87eda8c14418b638e5cc3c353877358b52585deb7a0f7d375a0672`.
- Pre-native reference seal from that same artifact: `d4b04b2bfaa38afacda550bea9433b5645af83e173d0b28632b1b5225e8e8074`.
- Post-hoc normalized CSV SHA-256: `1133504ba47df0d4b7fcaec46f090662027ff7feff6999401aad50dbd7d629d1`.
- **Corrected MAT adapter SHA-256**: `d322b5243bbdfb5b02380583b0af6631800d2bcd3cf5126148cd814fb147ba2c`; the *earlier executed revision* was `912db581869422743537bd3f5f604dc9b61ca2d776875444ab35679927f2d9f0`. Do not conflate their evidence identities.
- Unchanged generic checker SHA-256: `338c13934ac073603304503201edf9e25ba9ad410643b83492a1f6648`.

## What was observed and corrected

OpenModelica 1.27.0 `H1_S1_res.mat` is valid MATLAB v4. Its `Aclass` is already presented as logical rows by SciPy and says `binTrans`. Its `name`, `description` and `dataInfo` arrays require transposition, **but its `data_1` and `data_2` arrays are already canonical**. The initial, synthetic-only decoder incorrectly assumed every array required the same transposition and refused with `mat_schema: unrecognized or inconsistent Aclass orientation`.

The corrected generic decoder reads the `Aclass` orientation flag separately and admits a numeric orientation **only if metadata indices, required parameter invariance, and the predeclared time grid jointly validate it without ambiguity**. It never infers missing physical values from equations or the reference. A `data_1` time-bounds row is permitted to change across endpoints; an actually required parameter row must not.

The native MAT contains **35 named variables**, **18/18 required registered values**, with 3 sampled rows (0, 1, 1); the repeated terminal row is identical and is collapsed to the two planned steady algebraic evaluation indices. Signed and shared aliases are recorded with source table, one-based row number and sign. These are not independent measurements merely because separate names refer to one underlying native channel.

## Result of subsequent offline diagnostic verification

The existing, unchanged `h1.verify` numerical checker was applied to a canonical CSV produced **only from the saved native MAT bytes**; the original reference was sealed before native execution. There were **56/56 passing checks**, maximum normalized error ratio **0.03125** against the existing tolerances, and two diagnostic-only requested observations:

| Quantity | Read from saved MAT |
| --- | ---: |
| Hot boundary `hot.T` | 373.15 K |
| Cold boundary `cold.T` | 273.15 K |
| Rod area for each rod | 0.00031415926535897931 m² |
| Copper rod conductance | 0.16123826359480156 W/K |
| Steel rod conductance | 0.011567092823105328 W/K |
| Junction temperature `copper.T_b` | 366.4562880324543 K (93.306288 °C) |
| Copper and steel oriented heat flow | +1.0792824946508013 W |
| Hot / cold boundary supply | +1.0792824946508013 / -1.0792824946508013 W |

All readings above are **MAT-recorded values or direct string/number representations of those values**, not solver replacements. No dummy observation was added. The physical `.mo` model, source provenance, reference trajectories and numerical comparison allowances are unchanged.

The updated offline suite has **119 tests passed, 0 failures/errors**, with synthetic checks for actual OMC 1.27.0 mixed matrix orientation and refusal of single-precision MAT parameter storage. The original cloud preflight ran 118 tests; **119 is the later author-run count**, not a claim about the original workflow's test results.

## Qualification boundary and next work

This diagnostic improves our evidence for **the tested steady S1 composition, generic extraction and numerical consistency**. It is not:
- proof the original failed workflow completed, or pre-run approval of the subsequently corrected adapter;
- a native qualification verdict (the checker still records `nativeQualified=false` and requested values `diagnostic_only`);
- independent implementation review, a complete certified reference-error budget or a frozen checker/runtime manifest;
- evidence for body initialization, transient trajectories, a blind unfamiliar composition or the charter's full Track A/Track B.

A separately approved successor run would be needed to validate this corrected reader **in the execution workflow itself** if that higher assurance is required. Do not automatically retry. No new physical-law, apparatus-specific branch, tolerance relaxation, workflow trigger, installation, merge, or changes to `main` occurred during this post-hoc correction.
