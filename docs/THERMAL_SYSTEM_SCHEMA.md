# `sim_heat.thermal_system/1` — Declarative Thermal System Authoring Reference

This standalone specification defines the canonical JSON format (`sim_heat.thermal_system/1`) consumed by `simheat.system.ThermalSystem`, `describe_equations`, `solve_system`, and the local interactive lesson loopback server.

All physical inputs are authored **once** in SI units (no separate `facts.json` duplication). Unknown keys are strictly rejected fail-closed at every object level.

---

## 1. Numeric String & SI Unit Conventions

- **All physical quantities are SI:** temperatures in kelvin (`K`, absolute, $\ge 0$), lengths in `m`, areas in `m^2`, masses in `kg`, conductivities in `W/(m K)`, heat capacities in `J/K`, specific heats in `J/(kg K)`, latent heats in `J/kg`, heat rates in `W`, durations in `s`, Stefan-Boltzmann constant $\sigma$ in `W/(m^2 K^4)`.
- **Unsigned SI decimal strings** (all standard positive/nonnegative physical fields): JSON strings containing only digits and an optional decimal point (e.g. `"273.15"`, `"0.01"`, `"0.0000000567"`, `"0"`).
  - **Forbidden on physical fields:** JSON numbers (`273.15`), scientific notation (`"5.67e-8"`), fractions (`"1/2"`), leading `"+"` or `"-"`, or surrounding whitespace.
  - **Note on solver integer controls:** `solve.maxSweeps`, `solve.initialSteps`, and `solve.maxEvents` are JSON **integers** (not strings), whereas `solve.durationS` is an unsigned SI decimal string.
- **Signed SI decimal strings** (`heatInputW` and `alphaPerK`): JSON string with optional single leading `"-"` followed by an unsigned SI decimal (e.g. `"300"`, `"-50.5"`, `"-0.0015"`, `"0"`). No leading `"+"`, no scientific notation, no surrounding whitespace.
- **Interval parameters** (supported on rod parameters `k`, `L`, `A`, `d`): either an unsigned SI decimal string (exact point value) or `{"low": "<unsigned>", "high": "<unsigned>"}` with `0 < low <= high`.
- **Sign conventions:**
  - Conduction network supply: `Q_supply[i] = sum_j W[i][j] * T[j]` (`W`, positive **into** the conduction network).
  - Body / phase-substance / maintained reservoir energy and `heatInputW`: positive **into** that owner.
  - Exterior surface / radial shell heat loss: positive **outward** to the environment.

---

## 2. Top-Level Object (`sim_heat.thermal_system/1`)

```json
{
  "schema": "sim_heat.thermal_system/1",
  "id": "unique_non_empty_system_id",
  "nodes": ["a", "j", "b"],
  "conduction": { ... },
  "attachments": {
    "a": { ... },
    "b": { ... }
  },
  "solve": { ... }
}
```

| Key | Required | Type / Rule |
|---|---|---|
| `schema` | Yes | Exact string `"sim_heat.thermal_system/1"` |
| `id` | Yes | Non-empty string identifying the system |
| `nodes` | Optional | List of node names used as default `conduction.nodes` for top-level `"rods"` conduction |
| `conduction` | Yes | Conduction subnetwork specification (see §3) |
| `attachments` | Yes | Mapping whose keys **exactly match** the conduction law's `terminals` (see §4) |
| `solve` | Yes | Solve mode, horizon, and options (see §5) |

---

## 3. Conduction Specifications (`conduction`)

Every conduction specification reduces deterministically to a certified symmetric, zero-row-sum, passive terminal conductance matrix (`DerivedLaw`).

### 3.1 Primitive Rod Graph (`kind: "rods"`)
- **Required keys:** `rods` (mapping of `rod_name -> rod_spec`)
- **Optional keys:** `kind` (`"rods"`), `nodes` (list of all node names, including internal storage-free junctions; inherits top-level `nodes` if omitted at top level), `terminals` (list of exposed terminal node names; if omitted at top level, defaults to `sorted(attachments.keys())`), `lawId`.
- **Connectivity:** All declared `nodes` must form **one single connected component** with at least 2 terminals. Every node not in `terminals` is eliminated automatically as an ideal storage-free junction (Schur/Kron reduction for exact point rods; certified monotone barrier + Rayleigh enclosure for interval rods).
- **Allowed `rod_spec` kinds (exact keys only):**
  - `rod_area`: `{"kind": "rod_area", "a": "<node>", "b": "<node>", "k": <pos>, "L": <pos>, "A": <pos>, "generatedPowerW"?: <nonneg>, "alphaPerK"?: <signed>, "referenceTemperatureK"?: <nonneg>}` ($G_0 = k_0 A / L$)
  - `rod_circular`: `{"kind": "rod_circular", "a": "<node>", "b": "<node>", "k": <pos>, "L": <pos>, "d": <pos>, "generatedPowerW"?: <nonneg>, "alphaPerK"?: <signed>, "referenceTemperatureK"?: <nonneg>}` ($G_0 = k_0 (\pi d^2 / 4) / L$, using certified rational $\pi$ enclosure; note `d` is **diameter** in meters!)
  - Optional `generatedPowerW` (unsigned SI decimal string $\ge 0$, default `"0"`, top-level `conduction(rods)` only — refused inside `conduction(join)`): models uniform volumetric heat generation along that rod (total rod power $P_r \ge 0$ W). Automatically Norton-reduced through eliminated internal junctions onto terminal heat injections $I_{\text{Norton},i}$ for linear backends (`multiport`, `enthalpy`, `staged`, `stefan`, `radiative_transient`), or retained directly in Kirchhoff rod balances (`kirchhoff`), recovering certified internal junction temperatures and per-rod peak temperatures/positions.
  - Optional `alphaPerK` (signed SI decimal string, `1/K`, default `"0"`, top-level `conduction(rods)` only — refused inside `conduction(join)`) and `referenceTemperatureK` (unsigned SI decimal string $\ge 0$, `K`, **required** whenever `alphaPerK != 0`): models affine temperature-dependent conductivity $k_r(T) = k_{0,r}(1 + \alpha_r(T - T_{\text{ref},r}))$ via exact Kirchhoff potential $\Phi_r(T) = k_{0,r}[(T - T_{\text{ref},r}) + \frac{\alpha_r}{2}(T - T_{\text{ref},r})^2]$ in steady mode (`backend: "kirchhoff"`). Strictly certifies $k_r(T) > 0$ at all nodes and heated-rod peaks.

### 3.2 Schur-Complement Network Join (`kind: "join"`)
Joins two independent conduction subnetworks across one or more ideal thermal contacts (eliminating the joined contact nodes):
- **Required keys:** `kind` (`"join"`), `left` (conduction spec), `right` (conduction spec), `contacts` (non-empty list of `{"leftPort": "<port>", "rightPort": "<port>"}`).
- **Optional keys:** `leftPrefix` (default `"left"`), `rightPrefix` (default `"right"`), `lawId`.
- **Exposed terminal names after join:** Every unjoined terminal `p` of `left` becomes `"<leftPrefix>.<p>"`, and every unjoined terminal `q` of `right` becomes `"<rightPrefix>.<q>"`. Note: when `left` or `right` is a nested `"rods"` spec inside `"join"`, you MUST explicitly declare both `nodes` and `terminals` inside `left` and `right`!

### 3.3 Other Conduction Kinds
- `kind: "h1_study"`: `{"kind": "h1_study", "studyPath": "...", "rootPath": "..."}` (optional: `terminals`, `lawId`) — adapts an existing admitted H1 Modelica study read-only without `facts.json` (CLI/Python only; refused over HTTP loopback for filesystem safety).
- `kind: "derived_law"`: `{"kind": "derived_law", "law": <sim_heat.derived_terminal_law/1 dict>}` — embeds a prebuilt validated `DerivedLaw`.
- `kind: "derived_law_ref"`: `{"kind": "derived_law_ref", "path": "..."}` (optional: `sha256`) — loads a `DerivedLaw` JSON file from disk (CLI/Python only; refused over HTTP loopback).

---

## 4. Terminal Attachments (`attachments[<terminal>]`)

Every terminal of the reduced conduction law must have exactly one attachment. Exact allowed keys per `kind`:

### 4.1 `maintained` (Fixed Dirichlet Reservoir)
- **Required:** `kind` (`"maintained"`), `temperatureK` ($\ge 0$).

### 4.2 `sensible_body` (Finite Lumped Thermal Capacity)
- **Required:** `kind` (`"sensible_body"`), `initialTemperatureK` ($\ge 0$), **plus** either `heatCapacityJPerK` ($> 0$) **or** both `massKg` ($> 0$) and `specificHeatJPerKgK` ($> 0$) (if all three are supplied, `massKg * specificHeatJPerKgK == heatCapacityJPerK` must hold exactly).
- **Optional:** `heatInputW` (signed SI decimal string, default `"0"`, positive into body).

### 4.3 `phase_substance` (Piecewise-Linear Enthalpy Substance)
Enthalpy $H$ is measured relative to pure solid at $T_{\text{tr}}$: `solid` ($H \le 0$) ↔ `plateau` ($0 \le H \le M L$) ↔ `liquid` ($H \ge M L$).
- **Required:** `kind` (`"phase_substance"`), `transitionTemperatureK` ($> 0$), `specificLatentHeatJPerKg` ($> 0$), `initialSolidKg` ($\ge 0$), `initialLiquidKg` ($\ge 0$) with `initialSolidKg + initialLiquidKg > 0`.
- **Optional:**
  - `initialTemperatureK` ($\ge 0$, defaults to `transitionTemperatureK`). Consistency rules:
    - Subcooled ($T_0 < T_{\text{tr}}$): requires `initialSolidKg > 0` and `initialLiquidKg == "0"`.
    - Superheated ($T_0 > T_{\text{tr}}$): requires `initialLiquidKg > 0` and `initialSolidKg == "0"`.
    - Coexisting / pure-phase boundary ($T_0 == T_{\text{tr}}$): any nonnegative masses with positive total mass.
  - `solidSpecificHeatJPerKgK` ($> 0$) and `liquidSpecificHeatJPerKgK` ($> 0$): **must provide both or neither**. Required whenever post-exhaustion continuation (`staged` or `enthalpy`) or non-coexisting start ($T_0 \ne T_{\text{tr}}$) is used.
  - `heatInputW` (signed SI decimal string, default `"0"`, positive into substance).

### 4.4 `exterior_surface` (Steady Convective + Radiative Surface)
- **Required:** `kind` (`"exterior_surface"`), `areaM2` ($> 0$), `enclosureTemperatureK` ($\ge 0$), `emissivity` ($\in [0, 1]$), `sigmaWPerM2K4` ($> 0$).
- **Optional (must provide both or neither):** `airTemperatureK` ($\ge 0$), `convectionCoefficientWPerM2K` ($\ge 0$).

### 4.5 `radial_shell` (Steady Multi-Layer Spherical or Cylindrical Insulated Shell)
- **Required:** `kind` (`"radial_shell"`), `geometry`, `exterior`.
- `geometry`:
  - Sphere: `{"kind": "sphere", "innerRadiusM": <pos>, "layers": [...]}`
  - Cylinder: `{"kind": "cylinder", "innerRadiusM": <pos>, "cylinderLengthM": <pos>, "layers": [...]}`
  - Each layer in `layers` (1 to 32 entries): `{"outerRadiusM": <pos>, "conductivityWPerMK": <pos>, "alphaPerK"?: <signed>, "referenceTemperatureK"?: <nonneg>}` with strictly increasing `outerRadiusM > previous_radius` (`referenceTemperatureK` required whenever `alphaPerK != 0`).
- `exterior`:
  - **Required:** `enclosureTemperatureK`, `emissivity` ($\in [0, 1]$), `sigmaWPerM2K4` ($> 0$).
  - **Optional (both or neither):** `airTemperatureK`, `convectionCoefficientWPerM2K`.

### 4.6 `stefan_layer` (Transient Quasi-Steady Moving-Boundary Freezing / Melting Front)
Models a growing or melting solid phase-change layer in the quasi-steady conduction limit (sensible heat storage inside the growing layer neglected; exact as Stefan number $\text{Ste} = c_s |T_{\text{tr}} - T_{\text{eq}}| / L \to 0$) attached to one terminal of any validated conduction network with `maintained` reservoirs on all other terminals (plus optional rod `generatedPowerW` Norton shift).
- **Required:** `kind` (`"stefan_layer"`), `geometry`, `transitionTemperatureK` ($> 0$), `densityKgPerM3` ($> 0$), `specificLatentHeatJPerKg` ($> 0$), `layerConductivityWPerMK` ($> 0$).
- **Optional:**
  - `solidSpecificHeatJPerKgK` ($> 0$): enables certified Stefan-number validity diagnostic (`assumptions.stefanNumberBounds`).
  - `externalFilmCoefficientWPerM2K` ($> 0$): adds external convective film resistance in series with the network port resistance at the exposed face.
- `geometry` (exact keys per `kind`):
  - `planar`: `{"kind": "planar", "areaM2": <pos>, "initialThicknessM": <nonneg>, "maxThicknessM"?: <pos >= initial>}`
  - `cylinder`: `{"kind": "cylinder", "coreRadiusM": <pos>, "initialOuterRadiusM": <pos >= core>, "cylinderLengthM": <pos>, "maxOuterRadiusM"?: <pos >= initial>}`
  - `sphere`: `{"kind": "sphere", "coreRadiusM": <pos>, "initialOuterRadiusM": <pos >= core>, "maxOuterRadiusM"?: <pos >= initial>}`
- **Completion semantics:** When `maxThicknessM` / `maxOuterRadiusM` is reached (freezing) or the layer reaches zero thickness (melting), `postCompletionModeled` is `false` and `modeledDurationBoundsS` stops honestly at the certified completion time `completionTimeBoundsS`.

---

## 5. Solve Specification (`solve`) & Backend Dispatch

- **Required:** `mode` (`"steady"` or `"transient"`).
- **Optional:**
  - `durationS` (unsigned SI decimal string; **required** when `mode == "transient"`, optional in `"steady"` when computing plateau consumption over a steady duration).
  - `continuation`: `"auto"` (default), `"staged"`, or `"first_exhaustion"`. (Note: `"enthalpy"` is an internal backend name selected automatically under `"auto"` or `"staged"` for multi-body/multi-phase continuation, not a `solve.continuation` enum value.)
  - `maxSweeps`: positive integer (default `120`, steady `multiport` solver).
  - `initialSteps`: integer in `[1, 256]` (default `16`, transient grid resolution).
  - `maxEvents`: positive integer (default `32`, max phase transitions in `enthalpy` continuation).
  - `observations`: list of non-empty observation label strings.

### Automatic Certified Backend Dispatch Matrix

| Mode & Attachments | Selected Backend | Notes |
|---|---|---|
| `steady` + (`maintained`, `exterior_surface`, `radial_shell`, coexisting `phase_substance` with `heatInputW=0`, optional rod `generatedPowerW`, all `alphaPerK == 0`) | `multiport` | Exact linear solve for convection-only point systems; certified monotone Newton/interval sweeps for radiation/shells and heated rods. |
| `steady` + any nonzero `alphaPerK` on rods or `radial_shell` layers (with `maintained`, `exterior_surface`, `radial_shell`, coexisting `phase_substance`, optional rod `generatedPowerW`) | `kirchhoff` | Certified steady Kirchhoff M-function solver (`sim_heat.offline_kirchhoff_steady/1`) with exact rational barrier/monotone certification, strict $k(T) > 0$ domain proof across nodes and peaks, and `rod_probe` support. |
| `transient` + any nonzero `alphaPerK` on rods or `radial_shell` layers | `unsupported_regime` | Structured refusal (`["transient_mode", "temperature_dependent_conductivity"]`); Kirchhoff $k(T)$ is steady-only in M08. |
| `steady` + `sensible_body` (or non-coexisting `phase_substance`, or nonzero `heatInputW`, or `stefan_layer`) | `unsupported_regime` | Structured refusal (`C = 0 != t -> inf`, or moving front requires transient mode). |
| `transient` + 1 `stefan_layer` + `maintained` only (optional rod `generatedPowerW`) | `stefan` | Certified quasi-steady planar / cylindrical / spherical Stefan moving-boundary solver (exact rational `isqrt` + monotone outward bisection). |
| `transient` + `stefan_layer` + (`sensible_body`, `phase_substance`, `exterior_surface`, `radial_shell`, or multiple `stefan_layer`) | `unsupported_regime` | Structured refusal naming the exact unsupported mechanism pair. |
| `transient` + (`exterior_surface` or `radial_shell`) + (`sensible_body` or `phase_substance` with `c_s`, `c_l`; optional `maintained`, `heatInputW`, rod `generatedPowerW`) | `radiative_transient` | Certified cooperative tangent/secant Metzler comparison ODE integrator for Newton convection + Stefan-Boltzmann $T^4$ radiation with sequential `solid` ↔ `plateau` ↔ `liquid` phase continuation (`first_exhaustion` or zero-storage `maintained`-only returns `unsupported_regime`). |
| `transient` + 1 `phase_substance` (with `c_s`, `c_l`, `heatInputW=0`, optional rod `generatedPowerW`) + `maintained` only | `staged` | Exact closed-form 3-stage rational exponential/logarithm enclosure. |
| `transient` + `sensible_body` + coexisting `phase_substance` (without `c_s`/`c_l` or `continuation: "first_exhaustion"`, zero rod generation) | `multibody` | Coupled multi-body transient stopping at certified first exhaustion (`first_exhaustion` + rod generation returns `unsupported_regime`). |
| `transient` + `sensible_body` / multiple `phase_substance` (with `c_s`, `c_l`) or nonzero `heatInputW` or rod `generatedPowerW` | `enthalpy` | Certified sequential `solid` ↔ `plateau` ↔ `liquid` continuation with reversals, exact symmetry-tie proofs, energy conservation checks, and honest `mode_sequence_uncertain` stops. |
| `transient` + `maintained` only (no `sensible_body`, `phase_substance`, or `stefan_layer`) | `unsupported_regime` | Structured refusal (`["transient_mode", "maintained_only"]`); requires at least one storage/phase/front attachment. |

---

## 6. Result Envelope (`sim_heat.thermal_result/1`)

`solve_system` always returns a unified JSON envelope containing:
- `schema`: `"sim_heat.thermal_result/1"`, `systemId`, `mode`, `backend` (`"multiport"`, `"kirchhoff"`, `"staged"`, `"multibody"`, `"enthalpy"`, `"stefan"`, `"radiative_transient"`, or `null` when `unsupported_regime`).
- `status`: backend outcome (`"resolved"`, `"complete"`, `"coexisting"`, `"exhausted"`, `"growing"`, `"melting"`, `"completely_frozen"`, `"completely_melted"`, `"mode_sequence_uncertain"`, `"unsupported_regime"`, etc.).
- `terminationReason`: canonical termination code (`"converged"`, `"exact_linear"`, `"sweep_limit"`, `"resolved"`, `"refinement_budget"`, `"mode_sequence_uncertain"`, `"unsupported_regime"`).
- `achievedWidths`: achieved rational enclosure widths (`maxTemperatureWidthK`, `maxFinalTemperatureWidthK`, `finalThicknessWidthM`, `modeledDurationWidthS`, etc.).
- `equations`: deterministic output of `describe_equations` (conduction matrix or Kirchhoff rod equations, optional rod Norton injections, terminal ODE/algebraic/enthalpy/Stefan equations, conservation ledger).
- `kirchhoffSummary` (present when `backend == "kirchhoff"` with `conduction(rods)`): certified `totalGeneratedPowerW`, `nodeTemperatureBoundsK` (including internal junctions), per-rod `conductivityBoundsWPerMK`, `heatCurrentAtATowardBBoundsW`, `peakTemperatureBoundsK`, `peakPositionFractionFromABounds`, and optional `probe`.
- `rodGenerationSummary` (present whenever linear-conduction rods specify positive `generatedPowerW`): certified `totalGeneratedPowerW`, `terminalNortonInjectionsBoundsW`, `nodeTemperatureBoundsK` (including eliminated internal junctions), and per-rod parabolic `rodPeaks` (`peakTemperatureBoundsK`, `peakPositionFractionFromABounds`).
- `backendResult`: full certified backend record (exact rational endpoint strings), or `null` for `unsupported_regime`.
- Offline provenance flags (always `false`): `nativeExecuted`, `nativeQualified`, `independentlyCertifiedReference`, `runnerConsumable`.
