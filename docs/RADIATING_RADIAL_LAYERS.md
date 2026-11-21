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
