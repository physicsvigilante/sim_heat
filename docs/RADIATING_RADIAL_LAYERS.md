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
