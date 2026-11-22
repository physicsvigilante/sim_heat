# When the outer coating exchanges radiation

A backing network supplies the inner surface of a hollow, layered conductor. Its outer surface faces a large isothermal enclosure with view factor one. Assume radial steady conduction, diffuse gray emission, a transparent vacuum, zero heat generation, and ideal isothermal contact between layers. For a cylinder both ends are insulated and only the lateral surface radiates.

For outer radius b the emitting area A is 4πb² for the sphere and 2πbL for the pipe of length L. Let R sum the backing and radial layer resistances. The open temperature Topen is determined by the remaining maintained baths. Solve for the outer temperature Ts by balancing the same signed outward rate through the backing, each layer and the exposed surface:

    Q = (Topen − Ts)/R = ε σ A (Ts⁴ − Tenv⁴).

Use kelvin in the fourth powers. Calculate the temperature at any interface by subtracting the drop Q times the resistance accumulated from the open port. Local flux divides Q by the area at that interface.

The worked examples use 380 K behind a 0.5 K/W backing network. Radii are 0.10, 0.20 and 0.40 m and conductivities are 2 and 1 W/(m K). The exterior emissivity is 0.8 with σ = 5.67 × 10⁻⁸ W/(m² K⁴).

| Geometry | Enclosure (K) | Outer surface (K) | Outward heat (W) |
|---|---|---|---|
| sphere | 280 | 291.563 | 98.495 |
| cylinder | 450 | 447.538 | -101.487 |

The hotter enclosure in the pipe example supplies heat inward. The observer calculates exposed area from the specified geometry and encloses both area and radial resistance. An emissivity of zero makes the entire shell equilibrate at its open-port temperature.

~~~sh
python -B -m tools.radiating_radial_layers --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --port cold --inner-radius-m 0.1 --layer 0.2 2 --layer 0.4 1 --emissivity 0.8 --sigma 0.0000000567 --enclosure-k 280
python -B -m tools.radiating_radial_layers --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --port cold --inner-radius-m 0.1 --layer 0.2 2 --layer 0.4 1 --emissivity 0.8 --sigma 0.0000000567 --cylinder-length-m 1 --enclosure-k 450
~~~

## Can adding insulation increase the heat loss?

Increase only the outer radius of the last layer. Its material and emissivity stay fixed, along with the inner layers, backing network, enclosure temperature and pipe length. Added material increases conduction resistance and also adds radiating area. The local heat-rate derivative tells which effect wins for a small thickness change.

Write A for the outside area, r for the outside radius, k for the last layer's conductivity, and R for the total resistance from the open port to the outside surface. Let h = 4 ε σ Ts³ be the slope of emitted flux with respect to the surface temperature at the operating point. For a sphere take m = 2, and for a cylinder take m = 1. Then A′/A = m/r and R′ = 1/(kA). Differentiating the coupled energy balance gives

    dQ/dr = Q (m/r − h/k) / (1 + h A R).

The same factor times |Q| gives the slope of heat-rate magnitude for inward and outward flow. In this model a stationary nonzero transfer satisfies r = m k/h, where h itself depends on the solved surface temperature. The slope describes this operating point. A finite thickness change requires solving the revised geometry.

For the same 380 K backing, 280 K enclosure, and a single spherical layer of conductivity 2 W/(m K) starting at 0.10 m, the local behavior changes with thickness.

| Outer radius (m) | Outward heat (W) | Magnitude slope (W/m) | Effect of a small increase |
|---|---|---|---|
| 0.12 | 64.094 | 474.171 | increasing |
| 1.4 | 113.688 | -0.765 | decreasing |

~~~sh
python -B -m tools.radiating_radial_layers --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --port cold --inner-radius-m 0.1 --layer 0.12 2 --emissivity 0.8 --sigma 0.0000000567 --enclosure-k 280 --radius-sensitivity
~~~

### Bracket the radius of maximum heat loss

Starting with the last example's 0.12 m outer radius, replace `--radius-sensitivity` with `--bracket-to-radius-m 1.4`. The two proposed radii must have resolved opposite slopes for heat-rate magnitude. For these materials and bath temperatures, the calculation encloses an interior maximum near **0.979483 m**. This is the outside radius. Subtract the 0.10 m inner radius to get the insulation thickness.

The output retains both endpoint studies, their signed derivative bounds and the original search interval. Continuity and the opposite slopes guarantee an interior extremum. Bisection keeps endpoints whose signs are resolved. It stops at the input resolution, after 64 iterations, or when the midpoint's slope enclosure cannot resolve its sign. Read the returned bracket width for the achieved precision. A bracket with same-sign endpoints is refused; such endpoint data alone cannot locate a turn. The result applies within the bracket and does not establish uniqueness across all radii.

## An outer surface in air

Pass both `--air-k` and `--h-w-per-m2-k` to add a uniform convective film around the outer shell. Air and enclosure temperatures may differ. Positive heat flow to the air or enclosure means that medium receives heat. Warm air can supply heat while a surface radiates to a colder enclosure. The sum of the two external rates equals the outward conduction rate at steady state.

For pure convection, the critical outer radius is k/h for a long cylinder and 2k/h for a sphere. When radiation also acts, the local surface slope becomes h + 4εσT³. Use the calculated outer temperature in kelvin to evaluate that slope; changing the insulation thickness changes the temperature as well as the exposed area.

A thermometer on the outer shell can also be used to estimate the film coefficient. The radial_film_calibration CLI accepts the same port, shell geometry and enclosure properties with `--surface-k LOW HIGH` and `--air-k`. The wall rate is (T_open − T_surface)/R_total. Subtract radiation from that rate and divide the remainder by A(T_surface − T_air). If the surface band includes the air temperature, the reading cannot resolve the film coefficient. Warm air and a cold enclosure can give a negative air heat rate with a positive film coefficient.

## Distinguishing convection from radiation

A single surface reading supplies one heat balance. To infer both h and emissivity, change the air or enclosure temperature and repeat the experiment with the same shell, maintained baths and surface properties. In a controlled example both runs have a 360 K outer surface. A 360 K air supply and 300 K enclosure isolate radiation in the first run. A 350 K air supply and 360 K enclosure isolate convection in the second. The wall supplies the same outward heat rate in both trials.

The two_environment_calibration CLI accepts two `--trial LOW_K HIGH_K AIR_K ENCLOSURE_K` groups. Each group can have both exchanges active. The two heat balances must distinguish the coefficients across the measurement bands; repeated identical trials provide no second independent equation.

## Choosing from available insulation sizes

For a 1 m long cylinder with inner radius 0.1 m, coating conductivity 1 W/(m K) and an outside film coefficient of 5 W/(m² K), the convection-only critical radius is 0.2 m. With a 380 K open port, 0.5 K/W port resistance and 280 K air, compare outer radii 0.12, 0.20 and 0.50 m against a 127 W heat-transfer budget. The smallest and largest sizes meet the budget while the middle size exceeds it.

The shell_size_selection command evaluates every supplied `--radius-m` with the same inner layers and outer coating material. It reports the smallest available size established to meet the budget. A smaller unresolved candidate leaves the minimum undecided. The budget applies to the magnitude of the rate, so the same comparison works for inward heat leaks.

## How long does the ice last?

The radial_phase_bath experiment holds a coexisting solid and liquid at the transition temperature while heat passes through the steady conductor and shell. For a two-terminal vessel, the bath receives exactly the negative of the outward shell rate. With other maintained reservoirs attached, their heat flows enter the balance too. A perfectly insulated outer shell can still permit melting if a separate warm reservoir connects to the phase bath.

While ice remains, a positive heat rate Q melts Q/L kilograms per second for latent heat L. A negative rate freezes liquid. The experiment clips the converted mass at the first exhausted phase and reports the corresponding time interval. It assumes quasi-steady conduction with negligible heat storage in the vessel and shell, constant boundary conditions, and a well-mixed phase bath.

### Sizing radial insulation for a target hold time

The `phase_shell_sizing` command evaluates each stocked `--radius-m` against a positive `--hold-duration-s`. A radius is established to meet the hold time when both phases remain coexisting across the entire target duration (including certified exact-zero equilibrium, or an unresolved near-zero flux whose worst-case conversion in either direction cannot exhaust either phase). Because heat rate can peak at the critical radius, a medium thickness may exhaust before the target duration while thinner and thicker options both survive. As with heat-budget sizing, an unresolved smaller candidate prevents claiming a larger radius as the smallest established choice.

### Sequential exterior stages (day/night exposure)

The `radial_phase_exposure` command tracks a finite two-phase inventory inside a fixed radial vessel across successive `--stage NAME AIR_K H_W_PER_M2_K ENCLOSURE_K DURATION_S` exposures. Cumulative latent energy and solid/liquid mass intervals carry forward from stage to stage while both phases coexist; if either phase exhausts or exhaustion becomes uncertain mid-stage, the schedule halts at that stage without fabricating post-exhaustion stages.

The `radial_exposure_sizing` command applies the same stocked-radius selection discipline across a multi-stage schedule, reporting which `--radius-m` choices survive every stage without exhausting either phase (`survives_schedule`) and which exhaust or become unresolved mid-schedule. Because critical-radius peaks can exhaust a medium radius during an earlier stage before a later opposing stage can refreeze it, every candidate radius is evaluated independently and any smaller unresolved radius prevents claiming a larger radius as the smallest surviving option.

### Calibrating the outer air film from melted or frozen mass

Without an outer surface thermometer, the `phase_film_calibration` command infers bounds on the external convection coefficient from a timed solid-to-liquid mass change `--melted-kg LOW_KG HIGH_KG` (positive for melting, negative for freezing). The measured conversion must remain strictly below the initial solid and liquid inventories so coexistence holds throughout the exposure. The bath heat rate $Q = L\,\Delta m / \Delta t$ pins the inner and outer shell temperatures through the steady conductor network and shell resistance, subtracts radiation $\varepsilon \sigma A (T_s^4 - T_{\text{enc}}^4)$, and divides by $A(T_s - T_{\text{air}})$. Measurements that imply exhaustion, negative Kelvin shell temperatures, a surface band straddling $T_{\text{air}}$, thermally decoupled ports, or negative convection coefficients are refused.

### Inferring an unknown shell layer conductivity from melted or frozen mass

When the exterior convection and radiation parameters are known but one radial shell layer has an unknown thermal conductivity, the `phase_shell_conductivity` command marks that layer with `--layer R_OUT_M ?` and infers certified bounds on its conductivity from `--melted-kg LOW_KG HIGH_KG`. From the steady network heat rate $Q_{\text{shell}}$, it inverts the strictly increasing exterior flux balance $h(T_s - T_{\text{air}}) + \varepsilon \sigma (T_s^4 - T_{\text{enc}}^4) = Q_{\text{shell}}/A$ to bracket the outer surface temperature $T_s$, subtracts the backing-port and known-layer resistances from $(T_{\text{inner}} - T_s)/Q_{\text{shell}}$, and divides the unknown layer's exact radial geometry factor by the remaining resistance. Measurements that imply exhaustion, an adiabatic exterior, zero or sign-straddling shell heat rate, negative Kelvin shell temperatures, thermally decoupled ports, or a non-positive implied layer resistance are refused.

### Concentric spherical and cylindrical radiation shields (vacuum Dewar)

The `radial_radiation_shields` command surrounds the outer surface of a spherical or cylindrical conducting shell with zero or more thin concentric diffuse-gray shields `--shield R_M INNER_EPS OUTER_EPS` inside a concentric diffuse-gray enclosure (`--enclosure-radius-m`, `--enclosure-emissivity`). Across each concentric vacuum gap between radii $r_j < r_{j+1}$ with view factor $F_{j,j+1} = 1$, the exact radiative resistance is $R_{\text{rad},j} = \frac{1}{\varepsilon_{j,\text{out}} A_j} + \frac{1/\varepsilon_{j+1,\text{in}} - 1}{A_{j+1}}$. Because $A_j$ grows with radius ($4\pi r_j^2$ for spheres, $2\pi L r_j$ for cylinders), placing a concentric shield closer to the inner shell provides higher radiative resistance and lower heat leak than placing the same shield near the outer enclosure. For cylinders, $F_{j,j+1} = 1$ models the ideal axially end-loss-free lateral-cylinder geometry (long or perfectly insulated/reflecting ends) and is not a finite open-ended cylinder view-factor prediction. Passing `--phase-port` and the phase-bath parameters composes the shielded vacuum shell directly with a coexisting solid/liquid Dewar bath (`sim_heat.offline_radial_shielded_phase_bath/1`).
