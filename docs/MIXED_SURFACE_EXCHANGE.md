# A wall exposed to warm air and a cold enclosure

A surface can gain heat from air while losing heat by radiation. The surface temperature sets both rates. For a uniform film coefficient h on surface area A, take the outward rate to the air as hA(T_surface − T_air). The outward radiation rate to a large black enclosure is εσA(T_surface⁴ − T_enclosure⁴). At steady state their sum equals the signed heat entering the surface from the wall.

The worked case has a conducting wall backed at 380 K with resistance 0.5 K/W. Its 0.2 m² black surface faces a 300 K enclosure and contacts air at 450 K. Take h = 21.5 W/(m² K) and σ = 5 × 10⁻⁸ W/(m² K⁴). At 400 K the air supplies 215 W and the enclosure receives 175 W. The remaining 40 W flows into the wall. Both the conduction direction and its magnitude follow from the balance.

Run the radiating_surface CLI with the ordinary pinned study arguments and add `--air-k 450 --h-w-per-m2-k 21.5`. The heat transfer coefficient is a prescribed parameter of Newton's heat-transfer law. The output reports all three signed rates independently of the air and enclosure temperatures being equal or different.

## A finite body cooling in air

The body-time CLI accepts `--air-film AIR_K AREA_M2 H_W_PER_M2_K`. A lumped body can exchange heat with a conducting network, air over a prescribed exposed area, and a radiative enclosure. Radiation can pass through an independent sequence of storage-free shields. The air-film area and the radiating area are specified separately. With `--track-energy`, the result reports signed energy into the body along each path.

For a 100 J/K body, connect a 2 W/K wall to 380 K and a 2 W/K air film to 400 K. Suppress radiation. The effective equilibrium temperature is 390 K and the time constant is 25 s. Starting at 430 K gives T(t) = 390 + 40 exp(−t/25) in kelvin. Reaching 395 K takes 25 ln(8) s. The body loses 3,500 J. The air initially removes heat, then supplies heat after the body falls below 400 K. Integrating 2(400 − T) over this time gives 20 × 25 ln(8) − 1,750 J supplied by air; the rest of the loss goes through the wall.

## Timed exposure to changing air baths

To find temperature after a specified time, body_exposure_temperature accepts the same air-film and shield arguments as the passage-time solver. To carry a temperature interval through several laboratory stages, body_exposure_sequence accepts repeated `--air-stage ENCLOSURE_K AIR_K AREA_M2 H_W_PER_M2_K SECONDS` and `--stage ENCLOSURE_K SECONDS` arguments in chronological order. An ordinary stage switches off the air film. An optional set of radiation shields is common to all stages.

In the archived experiment a 100 J/K body initially at 360 K stays on a 2 W/K rod connected to 380 K. It first sees 500 K air at hA = 4 W/K for 20 s, spends 10 s exchanging heat only with the rod, then sees 280 K air at hA = 2 W/K for 15 s. Its temperature rises above the rod bath during the first stage. For each stage, the closed-form check uses the conductance-weighted bath temperature and exponential decay of the incoming temperature difference.
