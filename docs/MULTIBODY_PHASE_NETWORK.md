# Coupled Multi-Body + Phase-Bath Transient Network (`tools/multibody_phase_network.py`)

## Purpose

`tools/multibody_phase_network.py` (schema `sim_heat.offline_multibody_phase_network/1`) generalizes transient body–phase exchange (`body_phase_bath_exchange.py`) from a single lumped body to **any number of coupled finite heat-capacity bodies, coexisting two-phase baths, and maintained reservoirs** attached to the terminals of any pinned connected passive steady conduction network (`LINK`, `STAR`, `TRIANGLE`, `FULL`, etc.).

## Mathematical Formulation & Soundness

1. **Validated passive network**: Prebuilt laws are validated via `tools.offline_investigation.validate_pinned_law` (64-hex SHA-256 digests, all four offline flags `false`, exact joint rational connected passive feasibility).
2. **Augmented certified matrix exponential**: For $N \ge 1$ lumped bodies, the $(2N+1)$-dimensional state vector $(\mathbf{u}_b(t), \frac{1}{t}\int_0^t \mathbf{u}_b(\tau)\,d\tau, 1)$ is evolved using the repository's outward-rounded Horner matrix exponential (`qualification.h1_n13.conduction.step_matrix`), intersected with the maximum-principle temperature invariant $[T_{\min}, T_{\max}]$, and checked for global energy conservation ($\sum C_i \Delta T_i + \sum E_f \ni 0$).
3. **Certified intermediate-peak / reversal first-exhaustion localization**: Because multi-body systems can exhibit non-monotonic bath heat flows and intermediate energy overshoots, `_locate_first_exhaustion` uses certified maximum-principle Lipschitz bounds over subintervals (`subinterval_enclosures_with_flows`) with adaptive left-to-right subdivision and separate pruning (`max_prune_refinements`) and bisection (`max_bisect_refinements`) budgets, reported in `solverMetadata` (`terminationReason`, `pruneRefinementsUsed`, `bisectRefinementsUsed`, `modeledDurationWidthS`). Stop-state enclosures for body temperatures, phase-bath energies, and maintained-port energies take the union over remaining unsafe cells plus `state_at(cert_hi)` (when exhausted) or `state_at(duration)` (when `exhaustion_time_uncertain`).
4. **Pure-phase bath admission**: `phase_bath` ports admit pure solid or pure liquid at $T_{\text{tr}}$ (total mass $> 0$). Certified initial outflow leaving coexistence reports `exhausted` at $[0, 0]$ with `exhaustedAtStart = true` and unchanged inventory; exact equilibrium reports `coexisting`; strictly inward flux on a cell $[0, b]$ anchored at $t = 0$ (retaining the opposite-boundary check) continues normal localization; unresolved or zero initial flux with nonzero/unresolved derivative reports conservative `exhaustion_time_uncertain` modeled from $t = 0$.

## Scope & Evidence Boundary

- Offline analytical rational-interval calculation (`nativeExecuted=false`, `nativeQualified=false`, `independentlyCertifiedReference=false`, `runnerConsumable=false`), not a native OpenModelica simulation.
- Assumes ideal lumped heat capacity at `lumped_body` ports, isothermal coexistence at `phase_bath` ports until first exhaustion, and storage-free linear conduction in the pinned network.
