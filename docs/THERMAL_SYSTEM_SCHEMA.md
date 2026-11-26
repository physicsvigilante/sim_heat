# `sim_heat.thermal_system/1` — Declarative Thermal System Authoring Reference

This standalone specification defines the canonical JSON format (`sim_heat.thermal_system/1`) consumed by `simheat.system.ThermalSystem`, `describe_equations`, `solve_system`, and the local interactive lesson loopback server.

All physical inputs are authored **once** in SI units (no separate `facts.json` duplication). Unknown keys are strictly rejected fail-closed at every object level.

---

## 1. Numeric String & SI Unit Conventions

- **All physical quantities are SI:** temperatures in kelvin (`K`, absolute, $\ge 0$), lengths in `m`, areas in `m^2`, masses in `kg`, conductivities in `W/(m K)`, heat capacities in `J/K`, specific heats in `J/(kg K)`, latent heats in `J/kg`, heat rates in `W`, durations in `s`, Stefan-Boltzmann constant $\sigma$ in `W/(m^2 K^4)`.
- **Unsigned SI decimal strings** (all standard positive/nonnegative physical fields): JSON strings containing only digits and an optional decimal point (e.g. `"273.15"`, `"0.01"`, `"0.0000000567"`, `"0"`).
  - **Forbidden on physical fields:** JSON numbers (`273.15`), scientific notation (`"5.67e-8"`), fractions (`"1/2"`), leading `"+"` or `"-"`, or surrounding whitespace.
  - **Note on solver integer controls:** `solve.maxSweeps`, `solve.initialSteps`, and `solve.maxEvents` are JSON **integers** (not strings), whereas `solve.durationS` is an unsigned SI decimal string.
- **Signed SI decimal strings** (`heatInputW` only): JSON string with optional single leading `"-"` followed by an unsigned SI decimal (e.g. `"300"`, `"-50.5"`, `"0"`). No leading `"+"`, no scientific notation, no surrounding whitespace.
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
  - `rod_area`: `{"kind": "rod_area", "a": "<node>", "b": "<node>", "k": <pos>, "L": <pos>, "A": <pos>}` ($G = k A / L$)
  - `rod_circular`: `{"kind": "rod_circular", "a": "<node>", "b": "<node>", "k": <pos>, "L": <pos>, "d": <pos>}` ($G = k (\pi d^2 / 4) / L$, using certified rational $\pi$ enclosure; note `d` is **diameter** in meters!)

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
  - Each layer in `layers` (1 to 32 entries): `{"outerRadiusM": <pos>, "conductivityWPerMK": <pos>}` with strictly increasing `outerRadiusM > previous_radius`.
- `exterior`:
  - **Required:** `enclosureTemperatureK`, `emissivity` ($\in [0, 1]$), `sigmaWPerM2K4` ($> 0$).
  - **Optional (both or neither):** `airTemperatureK`, `convectionCoefficientWPerM2K`.

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
| `steady` + (`maintained`, `exterior_surface`, `radial_shell`, coexisting `phase_substance` with `heatInputW=0`) | `multiport` | Exact linear solve for convection-only point systems; certified monotone Newton/interval sweeps for radiation/shells. |
| `steady` + `sensible_body` (or non-coexisting `phase_substance`, or nonzero `heatInputW`) | `unsupported_regime` | Structured refusal (`C = 0 != t -> inf`). |
| `transient` + (`exterior_surface` or `radial_shell`) | `unsupported_regime` | Nonlinear radiating transient is explicitly out of scope (deferred). |
| `transient` + 1 `phase_substance` (with `c_s`, `c_l`, `heatInputW=0`) + `maintained` only | `staged` | Exact closed-form 3-stage rational exponential/logarithm enclosure. |
| `transient` + `sensible_body` + coexisting `phase_substance` (without `c_s`/`c_l` or `continuation: "first_exhaustion"`) | `multibody` | Coupled multi-body transient stopping at certified first exhaustion. |
| `transient` + `sensible_body` / multiple `phase_substance` (with `c_s`, `c_l`) or nonzero `heatInputW` | `enthalpy` | Certified sequential `solid` ↔ `plateau` ↔ `liquid` continuation with reversals, exact symmetry-tie proofs, energy conservation checks, and honest `mode_sequence_uncertain` stops. |

---

## 6. Result Envelope (`sim_heat.thermal_result/1`)

`solve_system` always returns a unified JSON envelope containing:
- `schema`: `"sim_heat.thermal_result/1"`, `systemId`, `mode`, `backend` (`"multiport"`, `"staged"`, `"multibody"`, `"enthalpy"`, or `null` when `unsupported_regime`).
- `status`: backend outcome (`"resolved"`, `"complete"`, `"coexisting"`, `"exhausted"`, `"mode_sequence_uncertain"`, `"unsupported_regime"`, etc.).
- `terminationReason`: canonical termination code (`"converged"`, `"exact_linear"`, `"sweep_limit"`, `"resolved"`, `"refinement_budget"`, `"mode_sequence_uncertain"`, `"unsupported_regime"`).
- `achievedWidths`: achieved rational enclosure widths (`maxTemperatureWidthK`, `maxFinalTemperatureWidthK`, `modeledDurationWidthS`, etc.).
- `equations`: deterministic output of `describe_equations` (conduction matrix, terminal ODE/algebraic/enthalpy equations, conservation ledger).
- `backendResult`: full certified backend record (exact rational endpoint strings), or `null` for `unsupported_regime`.
- Offline provenance flags (always `false`): `nativeExecuted`, `nativeQualified`, `independentlyCertifiedReference`, `runnerConsumable`.
