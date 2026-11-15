# H1 implementation-review corrections: R1, R2 and focused R6 tests

Date: 2026-11-15. Reviewed base: `250779ec1e8ff5c6aa81d79b440e410436b65573`.
Authority: the user approved the bounded correction-and-recheck step after the
external implementation review. This author may implement, test offline and
publish to `h1/offline-validation`; no native execution, installation, merge,
C1 selection, or final acceptance/freeze is authorized by this step.

## Review record and evidence boundaries

The exact supplied report is [preserved as lossless gzip here](reviews/20261115_IMPLEMENTATION_REVIEW.md.gz),
SHA-256 `2f446181cb4ccd9a4f19647386d1caa86ba1cc39bc2492390193c7577d1455ab`.
Decompression yields the unchanged uploaded bytes. It reports an independent 86-test reproduction, PDF inspection, and 80-digit
comparisons for seven exposed cases. Its reviewer disclosed earlier architecture
involvement. This is a user-supplied external LLM report, not an authenticated
GitHub review submission. Its high-precision scripts and raw comparison artifacts
were not supplied: reported ratios are retained as reported, not reclassified as
reproduced or as closure of R3. This corrective pass is by the implementation
author, not a fresh independent review.

## R1: sensitivity-aware timestamp admission

Keep every original value/conservation tolerance. Tighten timestamp matching
before candidate data is read, using at most **1/100 of each existing allowance**
for the effect of a permitted time displacement. The tighter window is stored
in a newly sealed reference artifact, recomputed/checked on consumption, and
applied by the decoder before any candidate comparison. A window smaller than
eight ULPs at the largest grid timestamp refuses the analysis instead of changing
its physics or loosening accuracy requirements.

The rule is conservative for the existing passive, constant-property network
only. It is not a new general transient model. Let D be the initial/boundary
temperature range of one connected network. Positive conductances and capacities
with fixed boundaries imply a temperature maximum principle: at a maximum a
body cannot receive positive net heat; storage-free junctions are positive
weighted averages of their anchors. Thus all temperatures remain in that
network's envelope for t >= 0. With S_i the sum of conductances incident on body i,

    |dT_i/dt| <= D*S_i/C_i.

A junction is a time-independent convex combination of body and fixed-boundary
temperatures, so its rate magnitude is no larger than the largest body-rate
bound in that network. Fixed boundaries have zero temperature rate. For each
rod e and endpoint-rate bounds L_a,L_b,

    |dQ_e/dt| <= G_e*(L_a+L_b).

Body and boundary flow-rate bounds sum their incident rod-rate bounds. A body's
energy-change derivative is its heat input, bounded by D*S_i. C, G and area
exports have zero time derivative. These are bounds over the **entire allowed
window**, not finite-difference estimates at the output samples. Closed and
isolated systems, algebraic junctions and disconnected networks use the same
rules. Unrelated networks do not enlarge value allowances; a common time window
can conservatively be tightened by the fastest network.

`h1/temporal.py` computes these scalar bounds with exact rational arithmetic on
the supplied finite binary input values. For circular geometry it uses
`A <= d*d` (pi < 4) as an upper bound, not a replacement physical area. Rates
are rounded upward and the time limit downward when converted to binary floats.
This limits rounding in this bound calculation; it does not certify the matrix
reference, source data, Modelica arithmetic, or physical modeling error.

For each nonconstant exported quantity use `dt <= epsilon_q/(100*L_q)` and
retain the original grid-spacing/ULP ceiling. Include the stricter `1e-6 K`
initial-state check. Cover every possible requested temperature difference by
`L_difference <= 2*max(L_node)` and the existing absolute difference floor
`1e-5 K`, independent of which requests are currently selected. Steady models
have zero rate bounds; their grid remains an algebraic evaluation index.

Samples outside the closed planned time interval refuse. Values are not
interpolated or shifted. The verifier continues to use the planned grid for
reference comparisons and quadrature and reports the maximum actual timestamp
displacement. This is bounded association, not a claim to integrate on the
perturbed timestamp grid. For a body integral check the additional association
effect is bounded by

    dt*(L_dU + t*L_Qin) <= (epsilon_dU + t*epsilon_Qin)/100.

This fits within the existing body residual allowance; the unchanged quadrature
and reference budgets are additional terms. Summing those local bounds likewise
covers network checks. Initial states, differences, flows and energy histories
are therefore included, not just temperature comparisons. This does not promise
that every trajectory already at the numerical-error limit will pass; it makes
the timestamp discrepancy a small, predeclared part of that unchanged limit.

The review's fast D1 fixture has a 5e-8 s time constant. Its old geometric window
is about 1e-10 s; the corrected window is about 8.333333333333332e-18 s, limited
by the initial-temperature obligation. A shifted exact analytical trajectory
inside that window passes all candidate checks, including its requested
temperature difference and body/network integrals. The previously admitted
harmful shift now refuses as `time_sensitivity`. These are synthetic/analytical
regressions, not native simulations or the reserved challenge.

## R2: source provenance and successor identities

Only the `provenance` string in `h1/reference_cases/S1.json` changes. It now
identifies Illustration 123's lengths, diameter, conductivities and boundary
temperatures as source-given; the SI conversion and adopted 4184 J/kcal convention
are separate. No source fact is relabeled illustrative. This pass does not
re-render the PDF; it follows the supplied review and recorded source evidence.
The authored S1 model/study and every physical/reference numeric value remain
unchanged. The reference specification's fingerprint and successor seals change.

All seven reference artifacts are regenerated into fresh paths because their
schema and implementation identities change, not because their trajectories or
allowances change. `sim_heat.reference_bundle/1` is historical; the verifier
requires version 2 and never upgrades an old artifact silently. Old contracts,
source files, spike files, reference summaries and development logs are retained.

## R6 tests and remaining gates

New regressions cover the harmful and admissible sensitivity shifts, initial and
integral budgets, whole-window versus sampled rates, junction and circular-rod
bounds, representability refusal, exact matching boundaries and one ULP beyond,
legacy policy refusal, policy tampering, CRLF hash preservation, ignored extra
columns and the S1 note correction. Unknown CSV columns are reported as ignored;
they are not interpreted as quantities or evidence. Duplicate rows are judged
on time and mandatory values only, as before.

R1/R2 and the focused R6 tests are implemented and author-tested, **pending scoped
independent recheck**, not automatically closed by this document. R3 (independent
reference accuracy with retained executable evidence), R4 (approved complete
checker/runtime identity manifest), and R5 (real compiler exports and precision)
remain open at their existing native/transfer gates. The extra temporal module
hash is recorded in successor bundles; this alone is not the R4 freeze manifest.
No reference comparison allowance, solver setting, run ceiling, physical
component or observation operation is expanded. No C1 is selected.

## References for implementation semantics

The passive-network bound above is this author's derivation under the existing
H1 equations, not a quote from a source. Modelica connection rules supply
potential equality and flow conservation:
https://specification.modelica.org/maint/3.6/connectors-and-connections.html

Directed floating conversion uses Python's documented `math.nextafter` and
`math.ulp`; rational calculations use the standard-library `Fraction`:
https://docs.python.org/3/library/math.html
The actual offline runtime and test outcomes are recorded in `h1/evidence/r1r2/`.
