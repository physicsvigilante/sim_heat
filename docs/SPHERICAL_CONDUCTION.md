# Why heat flux falls through a spherical shell

Two concentric layers surround a spherical cavity of radius 0.10 m. The first layer ends at 0.20 m and has conductivity 2 W/(m K). The second ends at 0.40 m and has conductivity 1 W/(m K). Each end surface is isothermal and connects through a thermal network of resistance 0.5 K/W to a maintained bath. Use 380 K on the inside and 280 K on the outside. Assume steady radial conduction, uniform material properties in each layer, perfect contact, and no internal heat generation.

**Predict.** Which quantity is conserved as the area grows, heat rate in watts or heat flux in watts per square metre? Where is the largest temperature gradient?

At radius r, Fourier's law gives Q = −4πr² k dT/dr. Integrating between the radii a and b gives the resistance (1/a − 1/b)/(4πk). Resistances of the layers and the backing networks add in series. For these layers each resistance is 2.5/(4π) K/W. The common outward rate is **71.537 W**. The flux Q/(4πr²) falls by a factor of four at each doubling of radius. At a material interface it is continuous, while the local temperature gradient changes inversely with conductivity. Here the largest gradient magnitude occurs at the innermost surface.

| Radius (m) | Temperature (K) | Outward heat flux (W/m²) |
|---|---|---|
| 0.10 | 344.232 | 569.270 |
| 0.20 | 330.000 | 142.317 |
| 0.40 | 315.768 | 35.579 |

The two pinned network studies act as independent inner and outer thermal connections through ideal isothermal spreaders. The specified shell geometry describes the added component. The observer bounds π using the existing rational enclosure and reports the input identities, per-layer resistances, temperatures and signed fluxes. Specify layers from inside out with one outer radius and conductivity per layer.

~~~sh
python -B -m tools.spherical_conduction --inner-root studies/composite_wall --inner-study studies/composite_wall/study.json --inner-facts studies/composite_wall/facts.json --inner-facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --outer-root studies/composite_wall --outer-study studies/composite_wall/study.json --outer-facts studies/composite_wall/facts.json --outer-facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --inner-port cold --outer-port hot --inner-radius-m 0.1 --layer 0.2 2 --layer 0.4 1
~~~

Exchanging the backing baths reverses the heat rate. Splitting a layer into two pieces of identical material preserves its resistance because the shared reciprocal-radius terms cancel. This study concerns a complete sphere in radial symmetry. The output is an offline calculation.
