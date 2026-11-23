# Multi-Stage Sensible ↔ Phase-Change Chaining (`tools/staged_phase_body_network.py`)

## Purpose

Earlier phase-bath tools (`latent_heat_bath.py`, `radial_phase_bath.py`, `body_phase_bath_exchange.py`, `multiport_thermal_network.py`) stop at first phase exhaustion (`postExhaustionModeled = false`).

`tools/staged_phase_body_network.py` (schema `sim_heat.offline_staged_phase_body/1`) chains up to **three consecutive physical stages** for a finite mass of a phase-changing substance at one port of any pinned connected passive steady conduction network (with all other terminals maintained at fixed Dirichlet temperatures):

1. **Pre-transition sensible stage**: lumped solid heating ($T_0 < T_{\text{tr}}$) or lumped liquid cooling ($T_0 > T_{\text{tr}}$) until $T_{\text{tr}}$ is reached at $t_1$.
2. **Isothermal phase-change plateau**: clamped at $T_{\text{tr}}$ while solid and liquid coexist until exhaustion at $t_2$.
3. **Post-exhaustion sensible stage**: the exhausted bath continues as a lumped liquid body ($C_l = M c_l$) after melting or a lumped solid body ($C_s = M c_s$) after freezing through $[t_2, t_{\text{end}}]$ (`postExhaustionModeled = true`).

## Mathematical Soundness

- **Validated passive network**: Prebuilt laws are validated via `tools.offline_investigation.validate_pinned_law` (64-hex SHA-256 digests, all four offline flags `false`, exact joint rational connected passive feasibility).
- **Thermodynamic initial-state validation**: Subcooled initial states ($T_0 < T_{\text{tr}}$) require positive solid mass and zero liquid mass; superheated initial states ($T_0 > T_{\text{tr}}$) require positive liquid mass and zero solid mass; coexisting states ($T_0 = T_{\text{tr}}$) accept any nonnegative split with positive total mass.
- **Global monotonicity in $(T_{\text{eq}}, R_{\text{port}})$**: Across all three stages, heating progress is strictly increasing in $T_{\text{eq}}$ and strictly decreasing in $R_{\text{port}}$ (cooling is the exact mirror). Evaluating the piecewise-analytic rational-interval trajectory (using `radial_log` and `exp_neg_interval`) at the two monotone corners yields certified enclosures for transition times, final temperature, remaining phase masses, and enthalpy changes — even when the requested duration straddles a stage boundary (`finalStage = "stage_boundary_uncertain"`).
- **Fail-closed unresolved regimes**: If the $T_{\text{eq}}$ enclosure straddles $T_0$ or $T_{\text{tr}}$ (leaving flow direction or transition reachability unresolved), the solver refuses rather than guessing.

## Scope & Evidence Boundary

- This is an **offline analytical rational-interval calculation** (`nativeExecuted=false`, `nativeQualified=false`, `independentlyCertifiedReference=false`, `runnerConsumable=false`), not a native OpenModelica simulation.
- Assumes ideal lumped internal thermal capacity in the substance (negligible internal temperature gradients) and storage-free linear conduction in the pinned network.
