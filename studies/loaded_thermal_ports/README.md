# A composite wall between two networks of maintained baths

Start with the star and triangle in three_terminal. Release the middle bath on the star and the warm bath on the triangle. Connect these ports through composite_wall, with its cold-named terminal on the left. Only the four outer baths maintain their temperatures. The previous temperatures at the released baths no longer fix the direction of transfer.

With its port open the star supplies zero heat through the middle leg. Its port temperature is (2 × 380 + 5 × 280)/7 = 2160/7 K. Its resistance viewed from the port is 1/3 + 1/7 = 10/21 K/W. On the triangle the corresponding values are (0.6 × 330 + 1 × 280)/1.6 = 1195/4 K and 5/8 K/W. The wall contributes 1/2 K/W. Its branch details matter through its effective resistance.

For open temperatures TL and TR and the three resistances RL, RW and RR, the signed left-to-right rate is (TL - TR)/(RL + RW + RR). The loaded port temperatures are TL - Q RL and TR + Q RR. This gives about 6.13 W from the star toward the triangle. The facing rod points in the opposite direction, so its own reported flow is negative. Equal open temperatures yield zero link flow even if other rods carry heat between maintained baths.

The offline command tools.loaded_thermal_ports takes three pinned input bundles (left, link, right) and the released terminal on each outer network. It uses independent unit-temperature excitations to determine conductances. It assigns the link terminals alphabetically from left to right and reports that mapping. The nine-rod model in this directory provides a direct offline comparison. The givens are illustrative and all rods have constant properties, insulated lateral surfaces and ideal contacts.
