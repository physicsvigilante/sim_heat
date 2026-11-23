# Multi-Port Composable Steady Thermal Network (`tools/multiport_thermal_network.py`)

## Purpose

Earlier offline analytical tools (`radiating_surface.py`, `radiating_radial_layers.py`, `radial_phase_bath.py`) reduced a steady conduction network to a single Thévenin port, limiting nonlinear exterior exchange to **one** terminal at a time.

`tools/multiport_thermal_network.py` (schema `sim_heat.offline_multiport_network/1`) generalizes steady-state composition to **any number of simultaneous coupled port attachments** on any pinned connected passive conduction network (`LINK`, `STAR`, `TRIANGLE`, `FULL`, etc.):

| Port `kind` | Physical Role | Boundary Law |
|---|---|---|
| `maintained` | Fixed Dirichlet reservoir | $T_i = T_{\text{fixed}, i}$ |
| `phase_bath` | Coexisting two-phase bath | $T_i = T_{\text{tr}, i}$ during coexistence; tracks latent energy, remaining solid/liquid mass, and earliest exhaustion across all phase baths |
| `radiating_surface` | Direct exterior surface | $Q_{\text{out}, i}(T_i) = A_i [h_i(T_i - T_{\text{air}, i}) + \varepsilon_i \sigma_i (T_i^4 - T_{\text{env}, i}^4)]$ |
| `radial_shell` | Spherical or cylindrical multilayer shell | Couples port $i$ (inner face $T_i$) through certified radial shell conductance $G_{\text{shell}, i} = 1 / R_{\text{shell}, i}$ to outer face $T_{s, i}$ with exterior radiation and/or convection |

## Mathematical Soundness

1. **Validated passive network**: Prebuilt laws are checked via `tools.offline_investigation.validate_pinned_law` (64-hex SHA-256 digests, all four offline flags `false`, exact joint rational feasibility of a connected reciprocal passive zero-sum conductance matrix).
2. **Monotone M-function enclosure**: Extending the unknown vector with each radial shell's outer face temperature preserves the off-diagonally antitone, strictly diagonally isotone M-function structure. Exact rational monotone sub-/super-solution Gauss–Seidel sweeps with outward rounding compute certified enclosures $[u^{\text{lo}}, u^{\text{hi}}]$.
3. **Independent post-condition certification**: The final enclosure is independently verified against the pointwise parameter-box residuals ($f_k^{\max}(u_k^{\text{lo}}; u_{-k}^{\text{lo}}) \le 0$ and $f_k^{\min}(u_k^{\text{hi}}; u_{-k}^{\text{hi}}) \ge 0$), per-port heat-rate intersection consistency, and global steady energy conservation ($0 \in \sum_i Q_{\text{out}, i}$).
4. **Multi-phase-bath stopping**: When multiple `phase_bath` ports coexist on the same network, the system plateau stops at the **earliest** phase exhaustion time across all baths (`postExhaustionModeled = false`); no bath is evaluated beyond another bath's exhaustion.

## Scope & Evidence Boundary

- This is an **offline analytical rational-interval calculation** (`nativeExecuted=false`, `nativeQualified=false`, `independentlyCertifiedReference=false`, `runnerConsumable=false`), not a native OpenModelica simulation.
- At least one port must anchor steady temperatures (`maintained`, `phase_bath`, or an exterior port with $\varepsilon > 0$ or $h > 0$).
- Cylindrical radial shells assume 1D radial conduction (axial end-effects neglected).
