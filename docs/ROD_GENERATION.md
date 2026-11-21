# Where does heat generated inside a wall go?

The source-pinned composite wall has a facing of conductance 4 W/K between the hot bath and a junction. Two rods of 1 and 3 W/K run in parallel between that junction and the cold bath. With baths at 380 K and 280 K, the unheated wall carries 200 W from hot to cold.

Suppose the facing generates 320 W uniformly along its length. For a uniform rod with constant cross section and conductivity, steady one-dimensional conduction assigns half its generation to each endpoint in the nodal energy balance. Of the 160 W assigned to the junction, 80 W reaches each bath because each side has conductance 4 W/K. The hot bath receives 240 W of generated heat. Its net supply changes from +200 W to **−40 W**: the hotter bath now absorbs heat.

Generate another 80 W uniformly in the 3 W/K insert. That adds 20 W at the hot bath and 60 W at the cold bath, giving net bath supplies of −60 W and −340 W. Together they remove all 400 W of generated power. The split between the baths depends on the location of the generating rod, even though the bath temperatures stay fixed.

The offline rod_generation tool accepts repeated `--generate ROD TOTAL_W` pairs. Each wattage is the total generated along that rod. Positive net bath supply means heat enters the network from that bath. The calculation uses the source network's steady temperature response to a unit temperature change at each bath. Reciprocity makes the same response the fraction of a local heat input reaching that bath. The reported observables are terminal rates; generation also produces a temperature profile within each rod.
