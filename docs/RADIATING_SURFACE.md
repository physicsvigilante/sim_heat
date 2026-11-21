# How warm is the exposed face of a wall?

A composite wall is backed by a bath at 380 K. Release its other temperature boundary and expose that face to a large isothermal enclosure at 280 K. Use a diffuse gray surface of area 0.020 m², emissivity 0.8 and view factor one. For this exercise take σ = 5.67 × 10⁻⁸ W/(m² K⁴). The intervening medium is transparent and provides no conductive or convective heat transfer. All other wall surfaces are insulated.

At steady state the heat supplied through the rods equals the **net** power delivered to the enclosure. With all temperatures in kelvin,

    (Topen − Ts)/R = ε σ A (Ts⁴ − Tenv⁴).

The existing conduction network determines its open-port temperature Topen and its resistance R seen at the exposed port. For this wall they are 380 K and 1/2 K/W. Substituting gives a face temperature of about 373.92 K and about 12.16 W to the enclosure. Replacing Ts by the backing-bath temperature in the radiation formula would omit the temperature drop through the wall.

Run from the repository root using the pinned checking environment.

~~~sh
python -B -m tools.radiating_surface --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --port cold --enclosure-k 280 --area-m2 0.020 --emissivity 0.8 --sigma 0.0000000567
~~~

The output gives rational endpoints for the surface temperature and signed power (positive toward the enclosure). The exterior parameters describe a hypothetical load and are recorded alongside the original conduction source pins. Area is the exposed radiating area. A hotter enclosure can drive heat back into the network.

The heat-balance residual increases strictly with surface temperature on the nonnegative kelvin axis. Its root lies between the open temperature and the enclosure temperature. For fixed resistance the root rises with open temperature. For fixed open temperature, increasing resistance moves the root toward the enclosure temperature. Bisection at all four corners of the input intervals therefore encloses the physical root. The calculation uses rational arithmetic and 64 halvings per corner. An emissivity of zero gives the open temperature and zero power directly.

This offline calculation covers a single uniform surface at steady state. The existing H1 Modelica sources describe the conductor network. The exterior calculation has no native qualification.

The signed power enclosure also uses the conductive balance (Topen − Ts)/R. Intersecting the two power intervals retains the common steady rate. This matters when the fourth-power law changes sharply across a narrow temperature interval. In a numerical stress test using the same wall and an enclosure at 999999999999 K, the resulting interval width is below one microwatt. The stress test checks numerical behavior only.
