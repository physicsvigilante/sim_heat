# SIM_HEAT H1-C1 — public authoring contract

Contract ID: H1-C1-AUTHOR-1. Date: 2026-11-15.
Candidate: `dd8c9432abe97563414bb3ed809e61e673473812`.
This is an author-facing extraction of the existing implemented interface, not a
new physical capability. No implementation code or solved example accompanies it.

## Purpose and limits

Author a physical thermal system, not its solved temperatures or heat flows.
The supported idealization is constant-property, storage-free conduction between
uniform-temperature bodies and fixed-temperature boundaries. Bodies exchange no
matter and do no mechanical work. There is no convection, radiation, phase change,
spatial diffusion, gas coupling, symbolic/inverse solving or general structural
revision interface in this test. A successful validation is not a simulated result.

For C1 choose a transient arrangement with at least two finite bodies and a
materially different connected structure from the already developed examples.
Changing names or numbers alone does not establish structural transfer. Do not
silently replace a rejected arrangement with an easier one.

## Physical file: model.mo

Use optional `within;`, one `model YourName`, component/parameter declarations,
an optional `equation` section containing only `connect(a.port, b.port);`, and
matching `end YourName;`. Use comments (`//` or `/* ... */`), not documentation
strings, for explanations. Identifiers start with an ASCII letter, then letters,
digits or underscores; use unique non-keyword names. `Modelica`, `SimHeat`, `time`,
`Real`, `Integer`, `Boolean`, and `String` are reserved along with Modelica keywords.

| Constructor | Every required named input, SI | External ports |
|---|---|---|
| `SimHeat.Body` | `m` kg, `c` J/(kg K), `T_initial` K | `port` |
| `SimHeat.RodArea` | `k` W/(m K), `L` m, `A` m2 | `port_a`, `port_b` |
| `SimHeat.RodCircular` | `k` W/(m K), `L` m, `d` m | `port_a`, `port_b` |
| `SimHeat.FixedTemperature` | `T` K | `port` |

Declaration grammar: `SimHeat.Body name(m=..., c=..., T_initial=...);`, and
analogously for each constructor. Bind all and only its named inputs once. The
engine derives heat capacity, area and conductance; do not author those derived
values as extra inputs. Rods have no energy storage. A circular rod takes diameter,
not radius. A material name supplies no physical property by itself.

Bindings accept finite decimal/scientific numeric literals (including signed
literals), previously bound compatible scalar parameters, or these conversions
with literal arguments only:

- `SimHeat.Units.from_degC(x)` -> temperature;
- `SimHeat.Units.from_cm(x)` -> length;
- `SimHeat.Units.from_cm2(x)` -> area;
- `SimHeat.Units.conductivityFromKcal(x, J_per_kcal)` -> conductivity, with an
  explicitly justified positive conversion factor.

Optional scalar declarations have the form
`parameter Modelica.Units.SI.Type name = binding;`. Allowed `Type` names are
`Mass`, `SpecificHeatCapacity`, `Temperature`, `ThermalConductivity`, `Length`,
and `Area`. Declare parameters before use. Bare literals take the expected SI
unit. Arbitrary arithmetic, nested calls, strings, imports, arrays, inheritance,
user equations/functions, algorithms, initial equations, loops and annotations
are excluded. No private component-member access is accepted.

Every mass, specific heat, conductivity, length, area, diameter and absolute
Kelvin temperature must be positive and finite. Derived capacities/conductances
must remain finite and positive. Negative Celsius is legal when Kelvin is positive.
Each body needs an explicit physical initial temperature; no state modifiers.

## Connections and ownership

A `connect` joins ideal thermal ports at one temperature with conserved net flow.
Opposite rod ends are distinct nodes unless other explicit connections collapse
them (a rod self-loop is refused). Multiple `connect` statements can form a
storage-free junction; no extra junction constructor or invented capacity is used.
Each ideal node may contain at most one body OR one temperature boundary, or
neither. Directly joining two bodies, clamping a body directly to a boundary, or
joining two boundaries is outside this conservative authoring scope even when
values agree. That exclusion does not assert physical impossibility.

Connect both ends of every rod explicitly. An initialized isolated body is legal;
an unconnected boundary is not. Self-connected ports and duplicate unordered
connection pairs are refused. Branches, loops and parallel links are assessed by
these rules, not apparatus names. Every conductor network must reach a body or
boundary. Closed initialized body networks need no artificial reservoir.

The general `steady` mode admits no bodies and needs a temperature boundary in
every network. C1 uses `transient`. Limits: 8 bodies, 8 boundaries, 32 rods,
64 ideal nodes, 128 connections, 256 scalar parameters; model <=64 KiB.
Numerical conditioning and representability may restrict otherwise valid inputs.
Admission does not establish native reliability for every permitted graph.

## Investigation file: study.json

Use UTF-8 JSON with exactly these keys: `schema`, `id`, `model`, `mode`,
`requests`, `analysis`, `provenance`. `revision` is the only optional top-level key.
No duplicate/unknown keys, comments, NaN/Infinity or physical-value overrides.

- `schema`: `sim_heat.study/1`.
- `id`: an ASCII letter followed by letters/digits/underscores (metadata only).
- `model`: exactly `path` (normally `model.mo`) and `sha256` (64 lowercase hex
  digits for the exact UTF-8 model bytes). Do not guess the hash. A mechanical
  hashing service may supply it; disclose that assistance and preserve raw files.
- `mode`: `transient` for this task.
- `analysis`: exactly `startTime`, `stopTime`, `intervals`, `solver`, `tolerance`.
  `startTime=0`; finite `stopTime` in [1e-6,1e7] seconds; even integer `intervals`
  in [1000,10000] for the C1 primary; `solver="dassl"`; `tolerance=1e-8`.
  Use evaluator-provided settings when available. Otherwise label your settings
  provisional in the submission notes: the evaluator must set C1's modal horizon
  and resolution before native execution, without changing physical facts or
  claiming an unchanged study identity. No eigenvalues or solved temperatures are
  required physical authoring inputs.
- `requests`: up to 32 request objects, each with unique `id` and one form below.
- `provenance`: up to 2048 records, each exactly `target`, `kind`, `locator`, `note`;
  all values nonempty strings. Link every physical slot, such as `bodyName.m`,
  directly or through its bound scalar parameter. An instance-wide note alone
  does not cover all its slots. Include `target="@model"` with kind
  `adopted_assumption` or `solution_assumption` for the physical regime.
  Allowed kinds: `source_given`, `source_diagram`, `solution_assumption`,
  `adopted_assumption`, `unit_convention`, `illustrative`.
  A newly invented teaching scenario uses `illustrative`, not textbook givens.

Public requests (exact fields; names below are grammar placeholders):

```json
{"id":"t","op":"temperature","target":"instance.port"}
{"id":"q","op":"heatFlow","target":"rodInstance"}
{"id":"dt","op":"temperatureDifference","a":"instance.port_a","b":"another.port"}
{"id":"u","op":"energyChange","target":"bodyInstance"}
```

Temperature targets must be actual external ports. Flow targets must be rods;
energy targets must be bodies. Rod flow is positive from `port_a` to `port_b`;
energy change is relative to that body's own initial state. Difference is T(a)-T(b).
Units are K, W and J. Zero/negative flow and zero differences are valid. Requests
are observations, never constraints. Do not request hidden diagnostics to enable
checks. One invalid request refuses the investigation, with statuses retained.
Public integrals, ratios and arbitrary-time interpolation are not supported.

Model paths stay within their case directory and the allowed case-data root;
parent paths remain within the case-data root. Symlinks/path escapes are refused.
Study size <=256 KiB. Files contain no shell/compiler commands.

## Distinct follow-up investigations

Changing passive requests keeps `model.mo` byte-identical. Preserve each study
identity; do not assume old run results automatically answer new requests.
A supported physical revision changes exactly one existing rod's conductivity,
not other physical values, types, identities or connections. The optional
`revision` object has exactly `parentStudyPath`, `parentStudySha256`,
`parentModelSha256`, `target` (the existing `rodName.k`), `reason` and
`origin="hypothetical"`. Parent chain limit: 16. Hash the actual parent bytes.
A shared-parameter edit affecting another physical slot is not an allowed
one-property revision. This interface does not support general structural edits.

For the first attempt submit only the base physical model and study; preserve
alternatives as proposals until the baseline has been captured. Do not assert
results of any unexecuted observation, revision or simulation.
