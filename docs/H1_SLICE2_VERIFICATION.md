# H1 offline slice 2: reference and candidate-result checking

Date: 2026-11-15. Base: `4a73f1c990f3fec333fa1972ac68e56fdacd0c10`.
Authority: the user approved the proposed Slice 2 within the recorded bounded
offline scope. No native run, installation, CI activation, merge, C1 selection,
or changes to `new_therm` are authorized or performed by this slice.

## What changed

The existing validator remains the production admission path. New checking code
uses separately entered SI facts and port connectivity; it does not import the
production parser, graph, wrapper equations or production-computed answers.
`verification.bind_reference` checks that the two descriptions agree, refusing
rather than repairing mismatches. The reference is never a production fallback.

- `h1/reference.py`: input checks, network balances, affine matrix exponential,
  spectral cross-check, local scales, quadrature diagnostics and artifact seals.
- `h1/verification.py`: identity binding, decoded-output comparisons, local and
  connected-network checks, and diagnostic observations.
- `h1/verify.py`: explicit `prepare` and read-only `check` commands; no native mode.
- `h1/reference_cases/`: seven separately entered, development-exposed references.
- `h1/tests/test_verification.py`: scalar analytical expectations and deliberate
  corruption tests, including heterogeneous-network error dilution.

Only the export registry in the existing `model.py` changes: rods additionally
require both external `port_a.Q_flow` and `port_b.Q_flow`. Computing these as +Q
and -Q in the decoder would make rod conservation a tautology. The future exporter
must provide the actual outputs or separately qualified, attested native aliases.
No missing value is supplied from the reference. Real exporter support is pending.
The Modelica prototype, case model/study files, earlier documents and evidence
are unchanged. `h1/README.md` is a living entry point, not a frozen acceptance.

## Independent mathematical path, not an independent author

Reference facts were entered by the implementation author from the already
reviewed experiment bindings. File hashes identify the corresponding authored
case; hashes do not supply its physical values. This is algorithm/input-path
separation, NOT a new independent human/LLM interpretation review. The seven
reference files still need review against the physical sources and contract.

Each connected network is evaluated separately. Build its symmetric conductance
Laplacian L from reference edges. Partition body nodes B, fixed boundaries F,
and storage-free junctions J. In temperature offsets from that network's minimum
initial/boundary temperature, eliminate junctions with

    theta_J = -solve(L_JJ, [L_JB L_JF]) [theta_B; theta_F].

Body balances then have `C d(theta_B)/dt = -K theta_B + f`. Solve the augmented
constant-affine system including state integrals by `scipy.linalg.expm`; do not
invert its evolution matrix, which is singular in closed/isolated systems.
A second evaluation diagonalizes `C^(-1/2) K C^(-1/2)` with `scipy.linalg.eigh`.
Known zero modes are inferred from closed connected-network physics and checked,
not created by truncating an unresolved small positive eigenvalue. Ambiguous
slow modes and poorly conditioned junctions refuse reference preparation.

The spectral evaluation and matrix exponential share the separately assembled
reference matrix and numerical libraries. Agreement is a sampled algorithmic
cross-check, not a certified error bound, independent interpretation or proof of
all possible graphs. The exposed scalar cases and a development-only loop have
additional closed-form checks. No challenge case has been chosen.

Primary API references (reference documentation, not runtime pins):
- SciPy expm: https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.expm.html
- SciPy eigh: https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.eigh.html

The consulted documentation identifies SciPy 1.18.0; actual offline tests used
preinstalled SciPy 1.17.0, NumPy 2.3.5, Python 3.13.5. No package was installed.
The test report records the actual environment; it does not qualify a native host.

## Numerical policy implementation and explicit candidate clarifications

F1's per-output allowances are constructed from reference data before reading
candidate output. Temperature excursion scales are local to a node and capped
by that connected network's temperature range. Flow/energy scales use only that
specific quantity. Every node, rod and body has local checks; connected-network
energy balance is additional and cannot replace them. Public temperature
subtraction is checked against the corresponding sealed reference difference.

The unchanged candidate trajectory rule is `a_q + 1e-6*S_q` (K/W/J absolute
allowances 1e-5, 1e-6, 1e-3). Initial body temperatures also have the existing
1e-6 K condition. C, G and circular area exports use a separate arithmetic
allowance of 64 ULPs of their independent value, not trajectory tolerances.
This arithmetic allowance needs review against real export precision.

Reference-method discrepancies must be at most 1/100 of these output allowances.
Integral cross-checks use 1/100 of `(1e-3 J + 1e-6*local_integral_scale)`.
Reference trapezoidal-grid discrepancy must be no more than
`1e-4*max(1 J, local_integral_scale)`. The 1 J floor prevents an exact-zero
integral from requiring a mathematically impossible zero rounding-error bound;
it does not borrow another component's energy scale.

The body integral check allowance is its own energy allowance plus its own
reference-grid quadrature diagnostic and propagated flow allowance over time.
The quadrature diagnostic includes the reference-integral and reference-flow
budgets above. Network checks sum only that network's relevant local allowances.
The word "allowance" is intentional: cross-check agreement is not a rigorous
bound on all reference arithmetic error. Formal numerical acceptance must resolve
this limitation and the original reference-accuracy requirement independently.
No current report awards native acceptance on this basis.

The existing grid-spacing/ULP-capped timestamp matching policy is reused. The
new CLI preserves CSV line endings before computing hashes; it does not normalize
raw evidence. Steady results retain algebraic evaluation indices, not physical
elapsed-time claims.

## Evidence and status semantics

`prepare` writes one explicitly requested fresh reference artifact; it refuses
an existing output. The artifact seal covers facts, grid, expected values, local
scales/allowances, methods, dependency versions and reference implementation hash.
A separate expected seal is required when checking candidate data. Seals prove
identity, not reviewer approval, chronological ordering or authenticity.

Candidate metadata must bind CSV bytes, model/study identities and reference
seal, and explicitly label data `synthetic` or `unattested_output`. Neither label
can become native-qualified here. Failed or incomplete candidates do not return
accepted requested quantities. Successful candidate observations remain
`diagnostic_only`, with origins distinguishing a supplied column from trusted
subtraction. All reports state `nativeQualified=false` and `nativeExecuted=false`.

The seven clean baseline CSV fixtures are generated from explicit scalar analytic
formulas, not the matrix solver being checked. Other graph/fault fixtures are
same-author development tests. They do not establish independent authoring,
unfamiliar transfer, native execution, or classroom effectiveness.

Development test logs are retained as byte-preserving `.log.gz` files; decompress
them to read the original output. Failed attempts are not overwritten.

## Review conditions and remaining gates

F1/F4 now have integrated offline reference and local checking code with error
injections, not merely scale helpers. F2/F6's deterministic policies remain in
place. F3's candidate path is more complete, but is not independently accepted.
F5 is still wholly pending: compiler/MSL pairing, Modelica compilation, real
CSV/alias qualification, controlled execution, numerical companions and native
result provenance. The runtime driver has not been added.

Before freeze: independently review this code, reference input fidelity,
conservative restrictions, arithmetic precision and error allowances. Resolve
any reference-accuracy/conditioning limits without post hoc tolerance inflation.
Only then proceed to a separately approved native plan. Keep C1 unselected until
its agreed freeze boundary. Passing synthetic checks is not physical simulation.
