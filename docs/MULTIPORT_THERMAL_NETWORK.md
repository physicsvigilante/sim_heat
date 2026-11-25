# Multi-Port Composable Steady Thermal Network (`tools/multiport_thermal_network.py`)

## Purpose

Earlier offline analytical tools (`radiating_surface.py`, `radiating_radial_layers.py`, `radial_phase_bath.py`) reduced a steady conduction network to a single Thévenin port, limiting nonlinear exterior exchange to **one** terminal at a time.

`tools/multiport_thermal_network.py` (schema `sim_heat.offline_multiport_network/1`) generalizes steady-state composition to **any number of simultaneous coupled port attachments** on any pinned connected passive conduction network (`LINK`, `STAR`, `TRIANGLE`, `FULL`, etc.):

| Port `kind` | Physical Role | Boundary Law |
|---|---|---|
| `maintained` | Fixed Dirichlet reservoir | $T_i = T_{\text{fixed}, i}$ |
| `phase_bath` | Coexisting or pure-phase bath at $T_{\text{tr}, i}$ | $T_i = T_{\text{tr}, i}$ during coexistence; admits pure solid or pure liquid (total mass $> 0$), reporting `exhaustedAtStart=true` if certified flow leaves coexistence at $t = 0$, and tracks latent energy, remaining solid/liquid mass, `exhaustedPhase`, and earliest exhaustion across all phase baths |
| `radiating_surface` | Direct exterior surface | $Q_{\text{out}, i}(T_i) = A_i [h_i(T_i - T_{\text{air}, i}) + \varepsilon_i \sigma_i (T_i^4 - T_{\text{env}, i}^4)]$ |
| `radial_shell` | Spherical or cylindrical multilayer shell | Couples port $i$ (inner face $T_i$) through certified radial shell conductance $G_{\text{shell}, i} = 1 / R_{\text{shell}, i}$ to outer face $T_{s, i}$ with exterior radiation and/or convection |

## Mathematical Soundness

1. **Validated passive network**: Prebuilt laws are checked via `tools.offline_investigation.validate_pinned_law` (64-hex SHA-256 digests, all four offline flags `false`, exact joint rational feasibility of a connected reciprocal passive zero-sum conductance matrix).
2. **Monotone M-function enclosure & exact linear path**: When every conductance and area interval has zero width and every exterior has $\varepsilon = 0$, the exact rational linear system is solved directly (`terminationReason = "exact_linear"`). Otherwise, exact rational monotone sub-/super-solution sweeps use a coupled $2\times 2$ box-monotone block update (with clamped $\pm 10^{-30}$ outward-rounding slack) for each `radial_shell` pair alongside scalar monotone updates for `radiating_surface` nodes. `solverMetadata` reports `terminationReason` (`"converged"`, `"sweep_limit"`, or `"exact_linear"`), `maxTemperatureWidthK`, `maxHeatRateWidthW`, and `residualCertified`.
3. **Independent post-condition certification**: The final enclosure is independently verified against the pointwise parameter-box residuals ($f_k^{\max}(u_k^{\text{lo}}; u_{-k}^{\text{lo}}) \le 0$ and $f_k^{\min}(u_k^{\text{hi}}; u_{-k}^{\text{hi}}) \ge 0$), per-port heat-rate intersection consistency, and global steady energy conservation ($0 \in \sum_i Q_{\text{out}, i}$). If a phase-bath inflow straddles zero at `terminationReason = "sweep_limit"`, the solver refuses with a resolution-limit message naming the sweep limit and achieved widths.
4. **Multi-phase-bath stopping**: When multiple `phase_bath` ports coexist on the same network, the system plateau stops at the **earliest** phase exhaustion time across all baths (`postExhaustionModeled = false`); no bath is evaluated beyond another bath's exhaustion. If any pure-phase bath has certified flow leaving coexistence at $t = 0$, the system stops immediately at $[0, 0]$ with `exhaustedAtStart = true`.

## Scope & Evidence Boundary

- This is an **offline analytical rational-interval calculation** (`nativeExecuted=false`, `nativeQualified=false`, `independentlyCertifiedReference=false`, `runnerConsumable=false`), not a native OpenModelica simulation.
- At least one port must anchor steady temperatures (`maintained`, `phase_bath`, or an exterior port with $\varepsilon > 0$ or $h > 0$).
- Cylindrical radial shells assume 1D radial conduction (axial end-effects neglected).
