# A wall exposed to warm air and a cold enclosure

A surface can gain heat from air while losing heat by radiation. The surface temperature sets both rates. For a uniform film coefficient h on surface area A, take the outward rate to the air as hA(T_surface − T_air). The outward radiation rate to a large black enclosure is εσA(T_surface⁴ − T_enclosure⁴). At steady state their sum equals the signed heat entering the surface from the wall.

The worked case has a conducting wall backed at 380 K with resistance 0.5 K/W. Its 0.2 m² black surface faces a 300 K enclosure and contacts air at 450 K. Take h = 21.5 W/(m² K) and σ = 5 × 10⁻⁸ W/(m² K⁴). At 400 K the air supplies 215 W and the enclosure receives 175 W. The remaining 40 W flows into the wall. Both the conduction direction and its magnitude follow from the balance.

Run the radiating_surface CLI with the ordinary pinned study arguments and add `--air-k 450 --h-w-per-m2-k 21.5`. The heat transfer coefficient is a prescribed parameter of Newton's heat-transfer law. The output reports all three signed rates independently of the air and enclosure temperatures being equal or different.
