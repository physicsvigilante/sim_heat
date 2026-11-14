# SIM_HEAT H1 — Bounded thermal-network implementation contract

**Version:** 0.1, draft for review  
**Record date:** 2026-11-15  
**Author:** ChatGPT, same conversation as H0; not an independent reviewer  
**Inspected repository revision:** `430089749a482861eea8c092cb8d44233c1cd99a` on `docs/h0-foundation`  
**Intended repository location:** `docs/H1_IMPLEMENTATION_CONTRACT.md`  
**Status:** Local proposed contract. Not published, adopted, implemented, independently approved, or natively qualified.

The user's latest approval authorizes drafting this contract. It does not complete H0 independent review or authorize production changes, installations, native execution, CI activation, publication, or merge. Proposed requirements below become binding only through a subsequent explicit adoption decision. Original documents and source evidence remain unchanged.

## 1. Basis, decisions, and the claim to test

This draft develops the approved H0 direction [P1], the H1 experiment proposal [P2], source coverage [P3], and technical findings R1–R6 [P4]. It applies the supplied **Composability and Teaching Charter, version 1.0** [C1] as a proposed project interpretation, not as an assertion that the charter or its amendments have already been adopted.

**Implementation-cost hypothesis:** after establishing this bounded capability, another admitted thermal network should require physical composition, investigation metadata, provenance, and independently prepared reference data—not a new production solver, topology-specific validator, extractor, or controller.

The target capability is constant-property, storage-free conduction between uniform-temperature bodies and maintained-temperature boundaries. Steady conduction and physical-time dynamics use the same heat-flow meanings. The trusted production path uses OpenModelica; a separate mathematical reference checks it. The LLM supplies physical facts and connections, not solved intermediate answers.

Three claims are distinguished:

| Claim | H1 obligation |
|---|---|
| Component reuse | The same body, conductor, and boundary laws serve all cases. |
| Fresh-assembly reuse | Different development arrangements and one post-freeze composition use the same production interfaces without arrangement-specific repairs. |
| Limited investigation reuse | The same model supports different passive requests and a validated conductivity revision with its baseline preserved. |

**Not claimed:** general structural editing, arbitrary thermal graphs being natively qualified, arbitrary Modelica, unrestricted parameter ranges being numerically reliable, symbolic answers, inverse solving, spatial diffusion, convection, radiation, phase change, gas/piston coupling, or demonstrated classroom effectiveness. A new source needing a directly given heat capacity or conductance is not accommodated by inventing geometry; direct-input forms remain an explicit H1 interface limitation.

### Charter application decisions proposed for this milestone

1. Documented public Modelica syntax is permissible authoring knowledge. Private variables, compiler workarounds, and implementation inspection must not be required in an assessed public-interface attempt. Backend-neutral authoring is not claimed.
2. H1 creates the first supported contract. The charter's existing-capability diagnostic is not represented as already performed. Restrictions and negative cases are still tested; a complete Track B diagnostic is not an extra prerequisite for this foundation experiment.
3. Retain [P2]'s **post-freeze selection** of H1-C1. This differs from [C1] section 9's preselected reserved-case protocol and needs an explicit project-specific disposition when adopting this contract. No concealed/preselected-case claim is made. The assessor and implementer record exposure and assistance.
4. A single bounded separate review may assess H0 findings together with this contract. That consolidates work, not evidence identities: it does not retrospectively turn the author's self-check into independent review.

## 2. Physical interfaces and ownership

Implement a small `SimHeat` Modelica package. The following names and parameter meanings are the proposed public API. They are specifications, not existing classes.

| Constructor | Required parameters, SI unless a sanctioned conversion is used | Ports | Required exported meanings |
|---|---|---|---|
| `SimHeat.Body` | `m` kg, `c` J/(kg.K), `T_initial` K | `port` | `T` K; `Q_in` W; `dU` J; derived capacity `C` J/K |
| `SimHeat.RodArea` | `k` W/(m.K), `L` m, `A` m² | `port_a`, `port_b` | `T_a`, `T_b` K; `Q_flow` W; derived `G` W/K |
| `SimHeat.RodCircular` | `k` W/(m.K), `L` m, `d` m | `port_a`, `port_b` | Same as `RodArea`, plus derived cross-sectional area |
| `SimHeat.FixedTemperature` | `T` K | `port` | Maintained `T`; `Q_to_network` W |

The two rod forms are parameterizations of one physical concept. They must share the same conductor implementation. A circular rod computes `A = pi*d*d/4` internally; no authored redundant area is accepted. No material property is inferred from a label such as “copper.”

Use thin wrappers over the Modelica Standard Library `HeatCapacitor`, `ThermalConductor`, and `FixedTemperature` candidates [M1, M3, M4]. Modelica Standard Library **v4.0.0 is the inspected reference API**, not a claim about an installed runtime. The exact dependency release and source identity must be recorded before library code is accepted; a different release requires a source/API compatibility check, not a silent substitution. No copying of all of `new_therm` or extraction of a cross-project framework is part of H1.

### Normative physical meanings

- The body has `C = m*c`, one uniform temperature, and no mechanical work or matter exchange. It owns stored-energy change once: `dU = C*(T-T_initial)`. This is not an absolute internal-energy reference.
- The rod has `G = k*A/L`, no storage, no contact resistance, and no lateral exchange. Its oriented flow is `Q_flow = G*(T_a-T_b)`, positive from `a` to `b`. A negative or zero value is valid.
- At each external component port, `Q_flow` is positive into that component. Thus body `Q_in = port.Q_flow`, and boundary supply `Q_to_network = -port.Q_flow`.
- Connected ideal ports have equal temperature and zero sum of incident heat flows. Their junction adds no mass, energy storage, or invented geometry.
- Rod endpoints are separated by finite conductance. They do not become one ideal temperature node merely because both belong to a rod.
- Temperature is absolute Kelvin internally. Temperature differences use K; Celsius is an explicit conversion/display choice. Energy is J and heat-transfer rate is W.
- Constant properties are adopted idealizations, not assertions of physical validity for every real material over every temperature.

### Initialization — disposition of R1

Each body's underlying independent state receives exactly one imposed initial temperature, for example through the internal capacitor modifier `T(start=T_initial, fixed=true)`. Do not also add an equivalent independent initial equation. Do not depend on start-value defaults, a guessed `steadyStateStart` parameter, or tool-supplied initialization constraints. Do not impose an initial derivative of zero.

The actual v4.0.0 `HeatCapacitor` declares `T(start=293.15)` and `C*der(T)=port.Q_flow`; the narrative describing another default and `steadyStateStart` is not the authoritative API [M1]. Modelica distinguishes required initial values from guesses using `fixed` [M2]. The steady conductor-only mode has no body state and must not add a fictitious capacity or settling transient.

## 3. Single physical authority and restricted authoring

A case consists of one authoritative `model.mo` and one compact `study.json`. The latter groups investigation, analysis, provenance, and revision references; the teacher is not required to maintain a separate file for every conceptual layer.

**Physical facts and physical initial conditions occur in `model.mo`.** `study.json` must not supply executable replacements for mass, conductivity, geometry, boundary temperature, or initial temperature. Source quotations may repeat a source fact as evidence, but are never solver inputs. Independently prepared verification data is explicitly a checking reference, not a second production model.

### Permitted Modelica surface

A tokenized, fully consumed allowlisted grammar admits:

1. An optional empty `within;`, one `model Name ... end Name;`, and comments.
2. Optional top-level scalar `parameter` declarations using only `Modelica.Units.SI.Mass`, `SpecificHeatCapacity`, `Temperature`, `ThermalConductivity`, `Length`, and `Area`. Every parameter has a binding. Declarations precede use, and identifiers are unique across parameters and instances.
3. Instances of the four constructors in section 2, with every required named parameter bound exactly once and no extra modifiers.
4. An optional `equation` section containing only literal `connect(instance.port, instance.port);` statements. No computed port paths.
5. A parameter value is a finite decimal/scientific numeric literal, a preceding compatible scalar parameter identifier, or one sanctioned conversion applied to literal arguments. The declared target type determines a bare literal's SI unit. Comments and provenance preserve source units.

Sanctioned project-owned conversion functions are `SimHeat.Units.from_degC(x)`, `from_cm(x)`, `from_cm2(x)`, and `conductivityFromKcal(x, J_per_kcal)`. Their returned types are respectively temperature, length, area, and thermal conductivity. Factors are `x+273.15`, `x/100`, `x/10000`, and `x*J_per_kcal`; the last accepts the explicit positive energy conversion factor and does not guess which calorie is intended. No arbitrary unit strings, calls, nesting, or arithmetic expressions are accepted in H1 case bindings. Derived capacity, geometry, and conductance stay inside the reviewed library. Conversion tests must independently check results and type mismatches.

No user imports, inheritance, redeclarations, arrays, loops, conditionals, algorithms, initial equations, arbitrary ordinary equations, functions, external calls, state modifiers, file access, or compiler-affecting annotations are allowed. Direct access to internal library members is rejected. Public identifiers use an ASCII letter followed by letters/digits/underscores; Modelica keywords and project-reserved identifiers are refused. Quoted identifiers and trailing unparsed tokens are rejected.

This is a small parser for a documented subset—not a general Modelica parser, universal graph compiler, or security guarantee. A blacklist or a successful compiler parse does not establish compliance. The validated original composition is copied byte-for-byte to the controlled execution directory; any generated observation/export adapter is disposable and traceable to it, never another editable physical model.

### Study descriptor

`study.json` uses the following exact top-level keys. Required keys are `schema`, `id`, `model`, `mode`, `requests`, `analysis`, and `provenance`; `revision` is optional. Unknown or duplicate keys are refused at every level.

| Key | Allowed value/fields |
|---|---|
| `schema` | Literal `sim_heat.study/1` |
| `id` | Nonempty ASCII identifier; identity/evidence only, never physics dispatch |
| `model` | Exactly `path` (relative `.mo` path) and `sha256` (64 lowercase hexadecimal characters) |
| `mode` | `steady` or `transient` |
| `requests` | Array, possibly empty; each object has `id`, `op`, and either `target` or both `a`,`b` as required by section 5; no additional fields |
| `analysis` | For `steady`, exactly `{}`. For `transient`, exactly `startTime`, `stopTime`, `intervals`, `solver`, `tolerance`; `startTime=0`, positive finite `stopTime`, positive integer `intervals`, `solver="dassl"`, and settings admitted by section 9 and the run plan |
| `provenance` | Array of records with exactly `target`, `kind`, `locator`, `note`; `target` is an existing instance/parameter/physical slot or `@model`; `kind` is `source_given`, `source_diagram`, `solution_assumption`, `adopted_assumption`, `unit_convention`, or `illustrative`; `locator` and `note` are strings |
| `revision` | Exactly `parentStudyPath`, `parentStudySha256`, `parentModelSha256`, `target`, `reason`, `origin`; `target` is the rod's `instance.k` slot and `origin="hypothetical"` |

Every effective physical parameter and adopted physical assumption must have a provenance link, directly or through its declared parameter reference. Multiple provenance records can explain one binding, such as a source conductivity and an adopted conversion convention. Labels never repair missing numerical inputs.

No authored executable commands are accepted. Paths must resolve within the separately approved case-data root, and the model within its case directory. Parent references are read-only paths under that root and are hash-checked; output paths are generated by the runner. Reject nonfinite values, booleans where numbers are required, path escapes, cycles in parent references, and inconsistent model identities. Verification references and host execution policies are separately pinned evidence, not extra executable fields in this study descriptor.

Stable physical identities are Modelica instance names. A junction is identified by its sorted member-port references, not by a case-specific apparatus name. Runtime variable paths are maintained in the adapter, not supplied by the LLM.

## 4. Admission, topology, and resource boundaries — disposition of R2

All physical input quantities must be finite; `m,c,k,L,A,d` and resulting `C,G` must be strictly positive. Authored absolute temperatures must be positive. Derived overflow or underflow to zero is a numerical-domain refusal, not silently clamped. Negative Celsius values remain admissible when the converted Kelvin value is positive.

Use connections to form ideal-node equivalence classes. At a node permit **at most one body or one fixed-temperature boundary**, or neither. Conductors connect distinct nodes. Parallel conductors, branches, loops, and disconnected assemblies are governed by these same rules, not enumerated apparatus layouts.

- Every rod endpoint must appear in an explicit connection. An unintended open rod end is not silently treated as insulation. This is an H1 authoring restriction, not a claim that an insulated rod end is impossible.
- An isolated initialized body is allowed. An unconnected boundary, self-connected port, duplicated connection statement, or rod with both ends collapsed onto one node is refused with a specific scope/authoring diagnostic.
- Directly joined multiple bodies, a body directly clamped to a boundary, and multiple ideal boundaries at one node are outside this conservative scope. Where conflicting boundary/initial values establish a contradiction, report that as well. Compatible excluded examples are not labeled physically impossible.
- `steady` requires at least one rod and one boundary, and admits no bodies. Each connected conductor network must reach a fixed-temperature node. A floating steady network is underdetermined in absolute temperature; no numerical anchor may be invented.
- `transient` requires at least one body and every body initial temperature. Each connected algebraic-junction subnetwork must reach a body or boundary node through finite conductances. A closed body network requires no reservoir.

Proposed implementation limits: at most 8 bodies, 8 boundaries, 32 rods, 64 ideal nodes, 128 connections, and 32 observation requests; one model file no larger than 64 KiB. These are bounded engineering choices, not physical laws or evidence of qualification at every limit.

The positive-conductance grounded junction matrix is nonsingular under the stated reachability rule; the corresponding quadratic form supplies the structural uniqueness argument. Algebraic-junction elimination in transient mode leaves linear evolution with positive capacities. That argument does **not** establish conditioning, floating-point accuracy, or native success for every admitted network.

Before native execution, numerical preflight must reject a nonfinite or poorly conditioned junction solve. Proposed cutoff: 2-norm condition number above `1e8` after symmetric diagonal scaling of the grounded junction matrix. Empty algebraic blocks bypass this check; a true zero diagonal is diagnosed, not regularized. This is a numerical qualification policy. Its calculation must not be reused as the sole independent physical oracle.

## 5. Public observations and internal dependencies — disposition of R4

Requests have unique IDs. Supported operations are exactly:

| Operation | Operand | Meaning and origin |
|---|---|---|
| `temperature` | Any valid external port reference, e.g. `body.port` or `rod.port_a` | Native port/node temperature, K |
| `heatFlow` | Rod instance ID | Native oriented `a`-to-`b` flow, W |
| `temperatureDifference` | Two valid external port references, `a` and `b` | Trusted subtraction `T(a)-T(b)` at the same output time, K; derived from native results |
| `energyChange` | Body instance ID | Native wrapper output relative to its authored initial state, J |

Requests return steady scalars or transient histories according to mode. Arbitrary-time interpolation, ratios, derivatives, integrals as public requests, symbolic expressions, and inverse operations are deferred. No raw backend path or arbitrary mathematical expression is accepted.

Resolve the complete operation, target type, operands, identities, and units before compilation. A temperature difference is passive, not a new equality equation. Zero flow and zero temperature difference are valid and require no denominator test.

The fixed internal export/check set includes every body temperature, heat input, and energy change; rod endpoint temperatures and oriented flows; and boundary temperatures and supplied heat-flow histories. Dependency expansion does not require dummy public requests. Public selection does not turn off conservation or admissibility checks. A changed request set may be applied to an existing complete verified bundle only after validating the model/bundle identity and dependencies and creating a separately identified verified derivative. Otherwise a new run is needed. The view does not fill missing outputs.

For H1, one invalid/unsupported request refuses that investigation before execution. The report lists every request's status, including valid requests left `not_computed`; it does not call a valid physical model impossible. Native failure or incomplete mandatory data prevents a completed-study acceptance; diagnostic partial traces remain available but unaccepted. No silent omission or zero substitution.

## 6. Scenario revision and presentation

H1 supports validation of one deliberately narrow revision operation: **changing an existing rod's conductivity** through a successor composition. A graphical editor or general automatic rewriting service is not required.

The descriptor identifies the exact parent model/study hashes, the stable rod ID, and `k` as the intended changed physical field, with a reason and hypothetical-origin label. Replacement physics lives only in the successor `.mo` file. A semantic comparison must establish unchanged instance IDs, types, topology, and all other effective physical inputs. A shared-parameter edit affecting another rod is not accepted as a one-rod revision. Derived `G` must be recomputed, not copied. The parent is never overwritten.

Revalidate the successor and obtain fresh native evidence. Compiled-model reuse is not promised. Observations on unchanged identities remain explicitly linked; structural addition/removal/renaming, multi-property revisions, sweeps, and in-run input changes are not H1 revision capabilities.

The minimum output is a machine-readable result and a plain inspection report showing source/assumption origins, temperature and flow values, and verification status. Optional static plots may consume these results, but a new viewer framework is not an acceptance dependency. Any schematic must say that unspecified shape/pose is schematic. A storage-free rod must not display a simulated diffusion front. Educational usefulness is assessed through the conductivity-change task; actual classroom effectiveness remains not tested.

## 7. Source cases, proposed bindings, and distinctions from givens

The source locators are [S1]. R5's source discrepancies remain recorded, not repaired in the PDF. The following numerical choices are **new proposed experiment bindings** requiring adoption of this contract; they are not previous decisions or executed results.

### H1-S1 — Illustration 123, PDF page 2

Preserve the given copper/steel series arrangement: `L1=0.75 m`, `L2=1.25 m`, common `d=0.02 m`; conductivities `0.092` and `0.011 kcal/(m.s.K)`; boundary temperatures `100 degC` and `0 degC`. Use `RodCircular` so area is not supplied as an LLM-calculated intermediate.

**Proposed convention:** thermochemical `J_per_kcal=4184`, identified as an adopted convention because the statement does not specify the calorie definition. NIST lists this conversion [U1]. Use explicit unit-conversion functions in the composition. The printed heat-flow label in J/s is inconsistent with its kilocalorie arithmetic; do not compare the native watt result directly to that mislabeled number.

Independent reference: `R_i=L_i/(k_i*A_i)`, `Qdot=(Th-Tc)/(R1+R2)`, `Tj=Th-Qdot*R1`. Under the proposed convention and circular area, reference arithmetic gives approximately `Tj=93.30628803245436 degC` and `Qdot=1.0792824946508015 W`. These are draft checking values, never authored physical inputs or native evidence.

### H1-D1 — Illustration 134, PDF page 9

The source supplies the symbolic arrangement, constant reservoir temperature, and negligible rod capacity, not these numbers. Proposed illustrative inputs: body `m=1 kg`, `c=500 J/(kg.K)`, `T_initial=293.15 K`; boundary `T=353.15 K`; rod `k=100 W/(m.K)`, `L=0.5 m`, `A=0.001 m²`. Adopt uniform body temperature and no other thermal exchange.

Reference consequences: `C=500 J/K`, `G=0.2 W/K`, `tau=C/G=2500 s`. Set the analysis horizon to `12500 s`. Independently check

`T(t)=Tr+(Ti-Tr)*exp(-t/tau)` and `Q_into_body=G*(Tr-T)`.

The integrated boundary supply equals the body's energy gain. The infinite-time limit is not a finite-time measurement.

### H1-D2 — Illustration 135, PDF pages 9–10

Use illustrative body 1 `m=1 kg`, `c=500 J/(kg.K)`, `T_initial=353.15 K`; body 2 `m=2 kg`, `c=750 J/(kg.K)`, `T_initial=293.15 K`. Use the same area-form rod parameters as D1, oriented from body 1 to body 2. Adopt uniform bodies, negligible rod storage, and no external heat exchange. The source explicitly neglects radiation but does not literally supply all these idealizations. Retain the final-exponential subscript discrepancy; derive checks from the two energy balances.

Reference consequences: `C1=500 J/K`, `C2=1500 J/K`, `G=0.2 W/K`, `tau=1875 s`, and energy-determined `T_eq=308.15 K`. Set the horizon to `9375 s`.

`DeltaT(t)=60*exp(-t/1875)`;  
`T1=T_eq+C2/(C1+C2)*DeltaT`;  
`T2=T_eq-C1/(C1+C2)*DeltaT`;  
`Qdot=G*DeltaT`;  
`C1*(T1-T1_initial)+C2*(T2-T2_initial)=0`.

The unequal capacities deliberately avoid relying only on a symmetric example. The original symbolic source request remains uncompleted by a numerical instance.

### Additional configurations

| ID | Change and purpose | Horizon |
|---|---|---|
| H1-D2-K2 | Hypothetical successor of D2: rod `k=200`, everything else unchanged. Reference `tau=937.5 s`, same `T_eq`. | Same `9375 s` for direct comparison |
| H1-EQ | D2 parameters but both initial temperatures `308.15 K`; valid zero exchange. | `9375 s` |
| H1-REV | D2 with body 1 at `293.15 K`, body 2 at `353.15 K`, capacities unchanged; negative oriented initial flow and independently recalculated equilibrium. | `9375 s` |
| H1-ISO | One body with `m=1`, `c=500`, `T_initial=293.15 K`, no thermal connection; constant temperature and zero energy change. | `12500 s` |
| H1-C1 | One separately selected post-freeze **transient** composition with at least two bodies and a materially different connection structure; actual inputs not selected here. | Set by pre-native reference analysis under section 9 |

These give eight physical configurations including S1, D1, and D2. EQ and REV are explicit new illustrative cases, not source revisions or additional blindly selected challenges. Development branch/loop parser/reference fixtures are permissible offline tests but not automatically native-qualified configurations.

## 8. Independent checks and references

The reference implementation must not import production physical wrappers, their derived answers, the production parser's assembled graph, or saved native results to construct its expected physics. A separately prepared, reviewed reference description supplies equivalent givens and topology. Shared generic numerical libraries are allowed and disclosed. Agreement between two paths does not replace an independent check of source interpretation.

Use the closed-form checks above for S1, D1, D2 and their numerical variants. Independently verify unit conversions, individual body temperatures and flows, initial conditions, energy changes, junction balances, and boundary supplies—not just a final temperature difference.

Build one reusable reference method for small admitted networks before freezing H1-C1. Assemble a conductance matrix from independently stated connectivity. Solve the grounded steady junction system. For transients, eliminate storage-free junctions and form `dT/dt = M*T+b`. Evaluate the affine system using an augmented matrix exponential, not `inverse(M)`, so isolated/closed networks with conserved modes are handled. SciPy supplies a matrix-exponential routine [N1]; its selected runtime version is separately recorded. This is a checking path, not a fallback production solver or a public symbolic capability.

Check the reference method against the analytic development cases and independently recomputed selected points, including a higher-precision or separately implemented spectral calculation for C1. Bound/check reference error at least 100 times below the native-comparison allowance at assessed points. Failure to establish that reference accuracy blocks a numerical acceptance claim; it is not permission to loosen native tolerances. Independent source/topology interpretation and independent numerical method are separate recorded dimensions.

## 9. Numerical policy proposed before execution

These are predeclared candidate qualification settings, not achieved accuracy.

**Steady evaluation:** the driver may evaluate the algebraic model over a backend interval `0..1` with one output interval, requiring consistent scalar outputs across those rows. This interval is an execution artifact only; no elapsed-time or settling claim is attached. It is not an input exposed as physical time in `steady` studies.

**Primary transient policy:** DASSL, tolerance `1e-8`, 1000 uniform output intervals including both endpoints. Use no extra maximum-step restriction in the primary run. D1 and D2-family horizons are fixed above. OpenModelica documents DASSL, tolerance/output controls, and solver-interpolated output grids [N2]. The host plan must verify the actual version's commands and effective settings; it may not silently substitute another solver.

For C1, independently choose a horizon spanning five slowest decaying modal time constants, preserving any conserved mode. Choose an even interval count `N >= 1000` such that `h*lambda_max <= 0.01`, where `h=t_end/N` and `lambda_max` is the fastest positive decay rate. Limit the primary `N` to 10000 so its dense companion has at most 20000 intervals. A model requiring more resolution receives an explicit numerical-policy limitation; do not alter its physics or secretly select an easier successor. C1's reference, horizon, scales, and settings are sealed before any native attempt. Known conserved modes are identified from connected-component physics and checked against the reference matrix; an unresolved small decay rate must not be silently treated as zero. Unresolved spectral separation is a numerical-policy limitation. The zero-decay-only isolated-body case uses its fixed horizon, not an infinite time constant.

### Comparison rule

For each assessed output, require `abs(native-reference) <= a_q + 1e-6*S_q`. Define scales from the independently checked physical binding **before observing native output**:

- `D = max(1 K, maximum initial/boundary temperature minus minimum initial/boundary temperature)`;
- temperature/difference scale `S_T=D`, absolute allowance `a_T=1e-5 K`;
- flow scale `S_Q=max(1 W, D*sum(G_e))`, `a_Q=1e-6 W`;
- energy scale `S_U=max(1 J, D*sum(C_i))`, `a_U=1e-3 J`.

Use the same fixed scales for the study and its conservation checks. Initial body temperatures additionally satisfy `abs(T(0)-T_initial) <= 1e-6 K`. Reference constants and parameter conversions have separately tested arithmetic checks; the numerical trajectory allowance must not conceal the wrong calorie convention or geometry.

Compare all primary output points, and dense-run values at common times. Retain the worst error, its quantity/time, and threshold. Check all mandatory quantities for finiteness and the initial/boundary temperature envelope with the numerical allowance. A valid near-zero flow uses the absolute term; no relative division by zero. Results are sampled numerical evidence, not a proof of continuous-time error.

### Energy quadrature and resolution

Check isolated-network total stored-energy change against zero at every output point. At storage-free junctions, check signed incident-flow sums; also check each rod's two-port conservation and connection temperature agreement.

For a network with boundaries, independently integrate the sum of raw `Q_to_network` histories by the composite trapezoidal rule. Before the native run, compute the reference-grid quadrature discrepancy `B_quad(t)` against an independently evaluated boundary-energy integral, including the reference's error allowance. Require `max(B_quad) <= 1e-4*S_U`; otherwise refine the declared policy before execution or refuse the planned analysis.

The whole-network boundary energy-balance allowance is `a_U + 1e-6*S_U + B_quad(t) + t*N_boundary*(a_Q + 1e-6*S_Q)`, with `B_quad` evaluated for the summed boundary supply and `N_boundary` the number of maintained-temperature boundaries. This propagates the stated sample-flow allowance; it is not a tolerance fitted to a native discrepancy. Compare native body energy directly to the independent energy reference as well, so this integral check is not the sole test.

D1, D2, D2-K2, and C1 each receive two planned companions: (a) tolerance `1e-10` at the same output grid, and (b) twice the output intervals at `1e-8`. Compare common-time quantities against the same acceptance allowances; assess quadrature improvement separately from solver tolerance. Small roundoff-level changes need not decrease monotonically. Persistent discrepancies block acceptance; no undocumented retry or tolerance relaxation.

### Proposed capability-run ceiling

Eight primary configurations plus eight numerical companions give **16 planned model launches**. Up to **16 fresh builds** are sufficient without claiming binary reuse. A host plan may use fewer builds only after validating identical-model reuse and explicitly recording the bound settings. Exact commands, ordering, and counts are fixed in that plan. Toolchain probes and any setup qualification have their own explicit plan; they are not hidden extra capability attempts. This draft authorizes zero builds or launches. Stop at the first unexpected failure; preserve it and obtain a successor decision rather than automatically spending remaining slots on retries.

## 10. Minimum execution and result contract

Implement a thin Python orchestration path with a read-only validation default. Parsing, validation, result inspection, and reference preparation must not invoke `omc`. Native execution requires an explicit mode and the separately approved exact plan.

Prefer raw CSV for the initial result reader, subject to a real-export qualification on the chosen OpenModelica release. A controlled exporter/adapter must establish all mandatory native output identities and signs. Preserve raw CSV, initialization/setup files, build and launch logs, diagnostics, and source/dependency hashes. A required eliminated or missing variable is a result-schema failure until the adapter supports an attested alias/constant representation; it must never be filled from the analytic oracle. CSV precision must be shown adequate for section 9, not assumed. MAT support is not required merely because `new_therm` uses it.

The result bundle identifies model/study/parent hashes; library and compiler versions and source identities; execution settings and effective output grid; requested outputs with units, owners, origin and status; the fixed internal export set; interpretation/provenance references; raw artifact hashes; and check outcomes. A native value and trusted subtraction have different origins. Independent reference results are stored as checks, never relabeled native observations.

Timestamps must cover the planned interval in increasing order after documented canonicalization. Preserve raw duplicate rows. Collapse only identical-time duplicate rows with identical required values; otherwise refuse ambiguous data. Grid association permits only a predeclared time-roundoff allowance of `1e-9*max(1 s,t_end)` and must be one-to-one. No extrapolation, missing-row fabrication, or implicit interpolation in acceptance checks. Label the compiler's uniform output as solver-interpolated sampling where applicable, not internal integration steps.

Before native execution, bind one host/OS, exact OMC and MSL installation identities, Python/numerical dependencies, a fresh work directory, literal allowlisted commands without shell interpolation, time/process/memory/output limits, cleanup, and network/package-download policy. Run without privileged access or unrelated credentials and restrict writes to the attempt directory as the host mechanism permits. State containment limitations explicitly. A language allowlist is not an operating-system sandbox. Installs, settings changes, CI activation, and access to the user's PC are not implied.

## 11. Offline and native test obligations

Offline implementation tests cover the complete grammar and its refusals, unit conversions and type compatibility, stable IDs, topology construction/reachability, source/provenance bindings, observations and dependencies, revision preservation, result decoding on synthetic fixtures, incomplete/failed result handling, and reference self-checks. Synthetic result files must be labeled synthetic and must not count as compiler-export qualification.

Include refusal fixtures for missing/extra parameters; duplicate/unknown identities; nonpositive or nonfinite inputs; unsupported syntax and path escapes; missing connections; direct unsupported storage/boundary combinations; contradictory temperatures; floating steady networks; missing initial states; rod self-loops; limits exceeded; invalid requests; mismatched parent/model hashes; stale data; and truncated or missing native outputs. Distinguish authoring errors, physical inconsistency, underdetermination, unsupported scope, numerical limitation, and execution failure.

Generic offline branch/loop fixtures establish validator/reference behavior only. Every claimed native mechanism must be linked to an actually executed case. After implementation, record observed authoring burden and marginal production changes separately from test and model-data additions.

The same-model request trial uses D2 for at least: temperature only; two temperatures; temperature difference; energy change. Keep physical model facts fixed. Test valid zero quantities with EQ. Invalid targets and a ratio request must be refused explicitly without invalidating the physical system itself. Use the complete verified internal export set for qualified re-observation, or allocate a fresh approved run if that set is insufficient.

## 12. Post-freeze transfer and public-interface authoring

Before selecting C1, freeze the library, conversions, public grammar and documentation, validator, observation registry, revision checker, runner interface, decoder, generic reference checker, and applicable report path. Record hashes and the candidate revision. Supply an assessed author only the public contract and task—not implementation source or a near-identical solved example. Preserve the first submission before feedback and retain repairs separately.

A separate author/reviewer selects C1 and prepares/checks reference facts with their exposure disclosed. The already discussed three-body branching example is exposed; it may be a development fixture, not untouched evidence. Do not select the actual C1 topology in this draft. At least one actual LLM authoring attempt must be retained; a developer-crafted fixture alone does not establish LLM usability. Same-author attempts are useful development evidence but never independent authoring evidence.

C1 may add composition, investigation/provenance, and reference **data** through frozen interfaces. Changing production parser, laws, topology handling, exporter, observer, generic checker, or report logic invalidates the frozen no-repair claim. Preserve the failed attempt. A repaired successor requires a new identity and an honestly revised transfer assessment.

C1 is one bounded unfamiliar composition, not the charter's full default two-arrangement Track A diagnostic and not proof of arbitrary graph support. A useful narrower implementation can be reported before transfer passes, but must not be labeled accepted reusable H1 generalization. Do not invent a separate reviewer or pretend another pass by the same author changes independence.

## 13. Deliverables, acceptance, and stopping conditions

Keep the implementation compact: a physical package; a small validator/observation/runner library; case compositions and descriptors; independent checks; tests; and retained run/result records. Logical responsibilities may share modules. No plugin platform, universal intermediate representation, new web framework, or wholesale runner copy is required. Exact module names may be chosen during implementation without another architectural gate if these interfaces and responsibilities remain intact.

**Offline candidate acceptance** requires independently reviewed component/initialization code and public contract, passing offline tests, source/assumption mappings, a frozen reference strategy, and a recorded implementation-cost baseline. It does not qualify a native trajectory.

**Native numerical acceptance** requires the planned source-inspired and boundary cases, initialization, exports, histories, units/signs, energy checks, and numerical companions to satisfy their predeclared policies on the named host. Failed paths remain evidence. No physics acceptance follows solely from compilation or a successful exit.

**Reusable H1 acceptance** additionally requires C1 without production repair, the same-model observation trial, and D2-K2 with verified parent preservation and fresh execution. Report the actual support/coverage of each item rather than accepting the whole admissible domain by extrapolation.

The conductivity teaching task must show faster exchange with the same analytically energy-determined asymptotic equilibrium for D2-K2. Compare like times and units. Do not claim identical finite-time temperatures or a finite-time arrival at exact equilibrium. Mark classroom effectiveness not tested unless actual user evidence is collected.

Report the five charter dimensions separately: source interpretation, physical/numerical correctness, simulation coverage, educational usefulness, and textbook-answer completeness. Also report component/fresh-assembly/investigation claims, production changes, author exposure, first attempts and repairs, independence, and untested structural revision. Hashes prove identity, not correctness.

Stop or narrow the claim if an arrangement needs a production special case, an unverified intermediate from the LLM, invented source data, private viewer physics, hidden changed tolerances, unsupported runtime workarounds, or missing reference accuracy. A justified refusal is not a project failure; falsely labeling it a successful simulation is.

## 14. Review findings and remaining gates

| H0 finding | Proposed resolution here | Evidence still required |
|---|---|---|
| R1 Initialization/API | One explicitly fixed initial body state; inspected API rather than narrative | Exact selected source, code review, native initial-state checks |
| R2 Nodes/closure | Connection-based rules and conservative exclusions; separate conditioning policy | Validator/negative tests and bounded native networks |
| R3 Physical authority | One `.mo` authority, trusted conversions, no invented aggregate decomposition | Authoring and parent-preservation checks |
| R4 Syntax/observations | Allowlisted complete grammar; typed operations; fixed internal dependency set | Parser/refusal tests and real-export qualification |
| R5 Numerical contract | Explicit convention/bindings, reference method, scales, grids, energy and refinement checks | Independent reference review and native evidence |
| R6 Proportionate gates | One bounded contract and consolidated separate review; no retrospective PASS | Independent verdict/dispositions, then implementation decision and later native plan |

A reviewer must resolve whether the proposed restrictions, native budget, verification allowances, CSV choice, and charter-specific challenge disposition are adequate and proportional. They are recommendations for adoption, not secretly completed review items.

**Next permitted deliverable:** a separate read-only review of H0 plus this draft, with findings/dispositions. After that, an explicit user decision may authorize implementation and offline tests under the adopted contract. The native plan, dependency installation, publication, and merge retain their separate boundaries. Do not request a fresh architectural review for ordinary work already within an approved implementation scope.

## 15. References and provenance

[P1] H0 foundation at the inspected revision: https://github.com/physicsvigilante/sim_heat/blob/430089749a482861eea8c092cb8d44233c1cd99a/docs/H0_FOUNDATION.md

[P2] H1 experiment proposal at that revision: https://github.com/physicsvigilante/sim_heat/blob/430089749a482861eea8c092cb8d44233c1cd99a/docs/H1_PLAN.md

[P3] Source coverage: https://github.com/physicsvigilante/sim_heat/blob/430089749a482861eea8c092cb8d44233c1cd99a/docs/SOURCE_COVERAGE.md

[P4] Author technical review, not independent approval: https://github.com/physicsvigilante/sim_heat/blob/430089749a482861eea8c092cb8d44233c1cd99a/docs/H0_REVIEW_NOTES.md

[C1] User-supplied `01_composibility_charter.md`, **Composability and Teaching Charter — Version 1.0**; SHA-256 `4fa10c92f8109526c7f704cdbbf688a65b9fcad359fe79a55b461ffbdbfb78b5`. Relevant sections: 2–9, 11–15. Not represented as a repository-adopted file. Proposed project interpretations are identified in section 1.

[S1] User-supplied `01_heat.pdf`, pages 2, 9, and 10 (printed 2.89, 2.96, 2.97); Git blob `18755813329b21f5e2ac432b2a5aebfe6dc21a60`; SHA-256 `8768a84a865b7f5a20e551b639be76263a0d882f317ec3d5c0b42ae72f491d1f`. The pages were locally rendered and visually checked for this draft. Public web retrieval of this PDF did not succeed; the matching uploaded original was used. No OCR or source alteration.

[M1] Actual MSL v4.0.0 HeatCapacitor source, inspected declarations/equations: https://github.com/modelica/ModelicaStandardLibrary/blob/v4.0.0/Modelica/Thermal/HeatTransfer/Components/HeatCapacitor.mo

[M2] Modelica Language Specification 3.6, initialization: https://specification.modelica.org/maint/3.6/equations.html#initialization

[M3] Actual MSL v4.0.0 ThermalConductor source, inspected declarations/equations: https://github.com/modelica/ModelicaStandardLibrary/blob/v4.0.0/Modelica/Thermal/HeatTransfer/Components/ThermalConductor.mo

[M4] Actual MSL v4.0.0 FixedTemperature source, inspected declarations/equations: https://github.com/modelica/ModelicaStandardLibrary/blob/v4.0.0/Modelica/Thermal/HeatTransfer/Sources/FixedTemperature.mo

[U1] NIST SP 811, Appendix B.9, thermochemical kilocalorie conversion: https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b9

[N1] SciPy matrix-exponential API, reference only, not a runtime pin: https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.expm.html

[N2] OpenModelica simulation flags and output-grid descriptions, retrieved 2026-11-15; page identified itself as v1.28.0-dev-292-g226ede3e89, **not a selected compiler version**: https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/simulationflags.html

**Evidence of work on this draft:** read existing documents and the current PR metadata; checked actual library declarations and primary documentation; rendered the three source pages; independently checked the displayed reference arithmetic; prepared this Markdown contract. No project implementation, test suite, compiler invocation, simulation, installation, independent review, or GitHub write was performed.
