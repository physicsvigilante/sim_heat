# Where does heat generated inside a wall go?

The source-pinned composite wall has a facing of conductance 4 W/K between the hot bath and a junction. Two rods of 1 and 3 W/K run in parallel between that junction and the cold bath. With baths at 380 K and 280 K, the unheated wall carries 200 W from hot to cold.

Suppose the facing generates 320 W uniformly along its length. For a uniform rod with constant cross section and conductivity, steady one-dimensional conduction assigns half its generation to each endpoint in the nodal energy balance. Of the 160 W assigned to the junction, 80 W reaches each bath because each side has conductance 4 W/K. The hot bath receives 240 W of generated heat. Its net supply changes from +200 W to **−40 W**: the hotter bath now absorbs heat.

Generate another 80 W uniformly in the 3 W/K insert. That adds 20 W at the hot bath and 60 W at the cold bath, giving net bath supplies of −60 W and −340 W. Together they remove all 400 W of generated power. The split between the baths depends on the location of the generating rod, even though the bath temperatures stay fixed.

The offline rod_generation tool accepts repeated `--generate ROD TOTAL_W` pairs. Each wattage is the total generated along that rod. Positive net bath supply means heat enters the network from that bath. The calculation uses the source network's steady temperature response to a unit temperature change at each bath. Reciprocity makes the same response the fraction of a local heat input reaching that bath. The reported observables are terminal rates; generation also produces a temperature profile within each rod.

## Finding the hottest point

With `--profiles`, the same experiment reconstructs loaded junction temperatures and the hottest point along each rod. If x is distance from terminal a divided by rod length, its temperature is

    T(x) = (1 − x) T_a + x T_b + [P / (2G)] x (1 − x).

Here P is the uniform total heat generation and G = kA/L. The quadratic term makes it possible for a point inside the rod to be hotter than either end. When P is zero, the profile is linear. A flat rod can attain its maximum everywhere.

In the example above, heat only the facing at 320 W. Half the generated power reaches the junction as an equivalent input. The junction rises by 160/(4 + 4) = 20 K, to 350 K. Along the facing, T(x) = 380 + 10x − 40x² kelvin. The maximum is **380.625 K at one eighth of the length from the hot bath**. The archived CI example instead heats the link in a conducting bridge, so both endpoints of the heated rod move.

## Releasing the surface to air and radiation

Keep the facing's uniform generation at 320 W and the inner bath at 380 K. Replace the outer bath with 0.2 m² of black surface facing a 300 K enclosure, in 450 K air with h = 13.5 W/(m² K). At 400 K the surface radiates 175 W and receives 135 W from the air. Its 40 W net loss is supplied by the conducting wall. The inner bath absorbs the remaining 280 W of internal generation.

The powered_wall_surface CLI combines the source-pinned terminal response, the distribution of generated power, and the surface balance. With the optional profiles flag it propagates the released surface temperature into every junction and rod. In this example the inner junction is at 410 K. The facing reaches **410.625 K seven eighths of the way from the 380 K bath to that junction**. Using the original cold-bath temperature in the profile calculation would put the maximum at the wrong end of the rod.

## Measuring an unknown heater through the wall

Keep the same surface conditions and measure 400 K. The surface loses 40 W net to air and radiation, while a passive surface held at that temperature would send another 40 W into the wall. At fixed surface temperature the buried sources must therefore contribute 80 W toward that surface.

Only one quarter of heat generated in the facing goes to this port. With no other heater, its power is 80/(1/4) = 320 W. If the insert is independently known to generate 80 W, it already contributes 60 W toward the port. The inferred facing power drops to **80 W**. The infer_rod_power CLI can take a lower and upper thermometer reading and bounds the resulting power. It refuses an inference when the measured port has no resolved sensitivity to the chosen rod.
