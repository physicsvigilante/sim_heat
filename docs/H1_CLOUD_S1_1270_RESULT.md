# H1 cloud S1 — Linux OpenModelica 1.27.0 one-shot result

Date: 2026-11-15. **Evidence stage:** first actual native Modelica build and executable launch; **not complete output-schema or H1 numerical acceptance**.

**Authorization:** User approved a single corrected cloud S1 attempt after the prior Linux 1.27.1 setup-selector failure. This successor used OpenModelica **1.27.0** and Modelica Standard Library **4.0.0** on Ubuntu 24.04 in a temporary GitHub Actions runner.

## Reproducible evidence

- [Corrected GitHub Actions run #43687137945](https://github.com/physicsvigilante/sim_heat/actions/runs/43687137945), commit `018529b98a4d70eeaa78e5aa1aac36350d35a187`, attempt 1, completed with **workflow conclusion failure**.
- [Raw GitHub Actions artifact #14150897064](https://github.com/physicsvigilante/sim_heat/actions/runs/43687137945/artifacts/14150897064), ZIP SHA-256 `1d59cf64eca35814f92c5f1644766151230cb7a0c66cb6b8a6bc527f3f506b6d`. Contains the actual executable, generated code/setup files, raw CSV, complete build/launch logs, source/reference hashes and failure manifest.
- Previous failure [run #43685828314](https://github.com/physicsvigilante/sim_heat/actions/runs/43685828314) is preserved independently. The changes to the second attempt were limited to the selected Linux toolchain version and the documented Modelica-library input formatting.
- The original S1 model, shared SimHeat component library, study, and numerical verifier **were not altered**.

## What actually ran

1. GitHub checkout, pinned Python 3.13.5 + NumPy 2.3.5/SciPy 1.17.0, complete offline test suite, source SHA-256 checks, S1 study admission, and independent-reference sealing: **PASS**.
2. Official setup action installed OpenModelica 1.27.0 and MSL 4.0.0: **PASS**. The action itself used OMC for package installation/index access; this is not counted as a physical simulation launch.
3. Explicit `omc --version` call: **1**. The exact `build.mos` reports `loadModel(Modelica, {"4.0.0"})`, `getVersion(Modelica) = "4.0.0"`, both source `loadFile` calls true, `buildModel(H1_S1, startTime=0, stopTime=1, numberOfIntervals=1, tolerance=1e-8, method="dassl", outputFormat="csv", variableFilter=".*")` returning a real native executable: **PASS**, **1 build**.
4. The compiled executable `H1_S1` launched **once**. Its stdout reports successful initialization and simulation. The raw CSV is present: **PASS**, **1 model launch**.
5. The fixed raw CSV export contract requires **18 physical fields**, but the actual CSV has only **10** of those exact names (plus four additional native variables and time). **Schema FAIL**; no missing data synthesized, no full generic numerical checker PASS, no native qualification.

The endpoint `t=0..1` is an algebraic backend evaluation interval for this steady state, not an elapsed thermal transient.

## Missing export identities and compiler metadata

The missing mandatory fields are:

`cold.T`, `hot.T`, `copper.A`, `copper.G`, `steel.A`, `steel.G`, `copper.T_a`, `steel.T_b`.

Inspection of **native** `H1_S1_init.xml` establishes:

- `cold.T`, `hot.T`: declared parameter variables with start values 273.15 K and 373.15 K.
- `copper.A`, `copper.G`, `steel.A`, `steel.G`: native *calculatedParameter* records; area and conductance were not exported as CSV columns. Their XML records have no direct numeric `start` attribute. **Do not populate them using independently computed reference values.**
- `copper.T_a`: native alias of `hot.source.T`; `steel.T_b`: native alias of `cold.source.T`. These underlying source temperatures are parameters and were also not exported as CSV columns.

This is consistent with parameter exclusion and compiler alias elimination, not evidence of a model-law failure. A future **generic, attested** export mapping may use real compiler-generated parameter/alias evidence only after its source/precision/semantics are reviewed. Never simply fill missing columns from the oracle or assume every compiler emits the same aliases.

The exported rod-port flow values are present, but port-flow aliases from one compiled equation system do **not** amount to independent physical measurements. The checker should retain that provenance distinction.

## Direct read-only numerical diagnosis on actual native values

These observations are from `H1_S1_res.csv`, not reconstructed missing fields:

| Direct exported quantity | t=0 native value | Independently calculated S1 reference |
| --- | ---: | ---: |
| **Copper** rod flow `copper.Q_flow` | +1.079282494650801 W | +1.0792824946508015 W |
| Junction `copper.T_b` | 366.4562880324543 K | 366.4562880324543 K |
| Other rod flow `steel.Q_flow` | +1.079282494650801 W | +1.0792824946508015 W |
| Hot boundary supply `hot.Q_to_network` | +1.079282494650801 W | +1.0792824946508015 W |
| Cold boundary supply `cold.Q_to_network` | −1.079282494650801 W | −1.0792824946508015 W |

At the displayed t=0 sample, the difference in rod heat flow from the scalar resistance reference is about `4.44e-16 W`, and the temperature difference is zero at printed precision. Both rod-port flow sums, the copper/steel junction flow sum and the total boundary-supply sum are **exactly zero at the exported decimal precision**. The CSV also contains the expected t=1 row twice with identical required values; the generic decoder allows collapsing exact duplicate rows, but the complete checker was not executed because its mandatory export contract is unmet.

The scalar analytical comparison was performed read-only after the failed run, using raw CSV values and `k*A/L`; it is **diagnostic evidence only**, not a PASS of the complete reference/parameter/conservation contract.

## Result, stops, and next bounded task

**Outcome:** SUCCESS for native compilation and one executable launch, **FAIL for required export-schema completeness**, therefore **no complete native numerical acceptance**. Both authorized native budgets were consumed. No automatic retry, version substitution, second build, or additional model launch occurred.

**Next technical task:** design and offline-test a **generic exporter/metadata adapter** that distinguishes raw time-series columns, attested compiler aliases, and native parameter/constant values with preserved precision and derivation provenance. It must admit/disallow each mapped output by exact compiler metadata semantics and refuse anything not verifiable. For S1's calculated parameters the current XML provides declarations but not necessarily their numeric values, so a missing value must stay missing unless authentic compiler evidence is available.

Preserve the existing raw evidence and ask for a separately authorized bounded native test only after the adapter's offline tests and exact plan are ready. No reason to merge draft PR #1, #2, #3, or #4 merely to run the cloud workflow; all remain unmerged. A working S1 steady solver does not establish transient initialization, a general compositional transfer, or the charter's Track A/Track B goals.
