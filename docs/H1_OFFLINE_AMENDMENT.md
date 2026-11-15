# H1 offline numerical and interface amendment 1

Date: 2026-11-15. Authority: [offline decision](H1_OFFLINE_DECISION.md).
This is a prospective candidate implementation refinement of contract v0.1.
Old records remain unchanged. It is not native execution authorization, full H1
freeze, independent code acceptance, or a claim of measured numerical accuracy.

## F1: local normalization, not whole-model scale dilution

For each scalar/history output, seal a scale from an independently prepared
reference **before seeing native output**. Never derive it from native values,
parser-solved answers, other disconnected assemblies, or total model capacity.

- Temperature: use the reference excursion from that node's initial temperature,
  floored at 1 K, capped by that connected network's initial/boundary temperature
  range, also floored at 1 K. Use a separate connected-network envelope check.
- Temperature difference: maximum absolute reference difference for those operands.
- Rod/body/boundary heat flow: that specific output's maximum absolute reference
  flow. A large other branch must not enlarge it, even in the same network.
- Body energy change: that body's maximum absolute reference energy change.

Use `epsilon_q = a_q + 1e-6*S_q`, with absolute allowances unchanged from the draft:
`a_T=1e-5 K`, `a_Q=1e-6 W`, `a_U=1e-3 J`. Exact zero has a finite absolute allowance.
These are resolution limits, not proof of relative accuracy for arbitrarily small
quantities. A small response below that resolution must not be described as a
resolved relative measurement. Reference-error requirements remain in force.

A local conservation residual receives the sum of the allowances of its own
same-unit terms only. Check every junction, rod and body; an aggregate network
check is additional evidence, not a substitute that can hide local errors.
For a body energy-integral residual, use its own energy allowance plus its
independently bounded quadrature/reference error plus `t*epsilon_Qin`.
For a connected network, sum only that network's body/incident-boundary allowances
and quadrature errors. Do not use all bodies/boundaries across disconnected parts.
Recompute these policies prospectively if the physical case changes.

This slice implements typed allowance helpers and synthetic dilution regressions.
It does NOT yet produce/seal independent reference envelopes or integrate a
complete local native verification pipeline. F1 is therefore not finally closed.

## F2 and F6: deterministic analysis envelope and time matching

Candidate transient descriptor bounds are:

- `startTime = 0` seconds; `1e-6 <= stopTime <= 1e7` seconds, finite.
- Even integer `1000 <= intervals <= 20000`; booleans are not numbers.
- `solver = "dassl"`; `tolerance` exactly `1e-8` or `1e-10`.
- The contract's primary C1 maximum remains 10000 intervals. Larger grids are
  allowed here only as a representable descriptor for a later planned dense
  companion; offline admission is not execution permission or a new run budget.
- Primary development settings remain the contract's fixed case settings.
  Native planning must identify primary versus companion and verify the settings.

These are conservative software qualification limits, not physical time limits.
The descriptor's finite time range does not establish stiffness or trajectory
accuracy for all admitted inputs. The separate C1 modal/reference requirements
and actual host limits remain applicable before native qualification.

On the planned increasing grid, let `h_min` be its minimum adjacent spacing.
Use `epsilon_time = min(1e-9*max(1 second, abs(first), abs(last)), h_min/10)`.
Refuse a grid when eight times its largest timestamp ULP exceeds that allowance.
Require one-to-one, strictly ordered sample matching, after the permitted exact
identical-time/identical-required-value duplicate collapse. No interpolation,
extrapolation, invented samples or ambiguous row matching is permitted.

Short-horizon regression: at `stopTime=1e-6` and 20000 intervals, nominal spacing
is `5e-11` seconds. The old `1e-9` allowance spans 20 intervals; the new allowance
is at most `5e-12`. This is arithmetic/policy evidence, not a native result.

## Implementation clarifications, without expanding physics

Modelica identifiers retain Modelica/project reserved-word restrictions.
Study/request IDs are metadata: the ASCII spelling `flow` is legal there and
must not be rejected just because it is a Modelica keyword. No ID selects physics.
Provenance checks require links for every effective physical slot and a model
regime record; checking a link does not establish that its note is true.

The case model remains authoritative. No descriptor parameter overrides are
allowed. A conductivity revision checks the complete effective component/type/
node structure and all physical fields, not merely the authored line containing
`k`. Shared-parameter changes affecting a second component are rejected.

Additional offline resource limits: 256 bound scalar parameters, a 256 KiB study,
2048 provenance entries, a 16-deep parent chain; model/topology limits remain
those of the contract. Paths are confined, existing UTF-8 files; symlinks are
refused. Candidate CSV input is capped at 20 MiB, 4096 columns and 40002 data rows.
Missing/aliased native outputs are not fabricated. The current decoder has only
synthetic evidence and never issues numerical acceptance.

This first implementation does not add a native runner or compiler invocation.
The old Modelica prototype has not been compiled, accepted or silently promoted.
Reference documentation for conditioning is NumPy's `linalg.cond` 2-norm API;
the offline environment used for tests is recorded separately, not chosen for
future native use. No new dependency has been installed.
