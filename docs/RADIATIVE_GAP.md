# Heat transfer across a vacuum gap between wall faces

Two composite walls face each other across a vacuum. Their backing baths maintain 380 K on the left and 280 K on the right. Each wall has thermal resistance 1/2 K/W. The facing surfaces have equal area 0.020 m² and emissivities 0.8 and 0.5. Assume diffuse gray, opaque, isothermal plates with view factor one in both directions. Edge losses, supports across the gap, and external irradiation are neglected. Use σ = 5.67 × 10⁻⁸ W/(m² K⁴).

**Predict.** Which temperatures belong in the fourth-power radiation law? What changes if the right surface becomes perfectly reflecting?

Let Q be positive from left to right. The emitting temperatures are the surface temperatures TL = 380 − Q/2 and TR = 280 + Q/2, in kelvin when Q is expressed in watts. Each plate emits and reflects radiation. Write its total outgoing radiant power per area as JL or JR. For the left plate, JL = εL σ TL⁴ + (1 − εL) JR. The right plate obeys the same balance with L and R exchanged. The net heat rate is A(JL − JR). Eliminating the two radiosities gives

    Q = A σ (TL⁴ − TR⁴) / (1/εL + 1/εR − 1).

With one perfectly reflecting plate the net heat rate is zero and both wall faces take their open-port temperatures. The plate formula applies to this particular viewing geometry.

Run from the repository root. The same composite-wall file represents two independent copies. Releasing the cold terminal on the left leaves its warm bath in place; releasing the hot terminal on the right leaves its cold bath in place.

~~~sh
python -B -m tools.radiative_gap --left-root studies/composite_wall --left-study studies/composite_wall/study.json --left-facts studies/composite_wall/facts.json --left-facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --right-root studies/composite_wall --right-study studies/composite_wall/study.json --right-facts studies/composite_wall/facts.json --right-facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --left-port cold --right-port hot --area-m2 0.020 --left-emissivity 0.8 --right-emissivity 0.5 --sigma 0.0000000567
~~~

The worked example gives 6.881 W from left to right, with plate temperatures 376.560 K and 283.440 K.

For general conductor networks the two open-port temperatures and resistances come from the pinned conduction studies. Between zero heat flow and direct-contact heat flow both surfaces stay between the two open temperatures. Over this interval the residual Q minus the radiation rate increases strictly, so bisection encloses the unique solution. The root increases with left open temperature and decreases with right open temperature. At fixed open temperatures, increasing either resistance moves the root toward zero. Evaluating the interval corners therefore bounds signed flow for either ordering. The output propagates this interval back through both conduction laws.

This is a steady offline boundary calculation. The conductive studies and explicit gap inputs are identified separately in the output.

## Insert a floating shield

Place a thin, opaque, isothermal sheet between the walls, with no conductive support leaking heat. Its two faces may have different coatings. Both gaps have the same area, each pair has mutual view factor one, and the sheet is in steady energy balance. Append `--shield-emissivities 0.6 0.3` to the example command. The first emissivity belongs to the face looking left.

The shield reduces the heat rate from **6.881 W to 2.596 W** and reaches **356.655 K**. To derive this result, write the left gap rate as KL (TL⁴ − TS⁴) and the right gap rate as KR (TS⁴ − TR⁴), using the two facing emissivities for each coefficient. Equal rates give

    TS⁴ = (KL TL⁴ + KR TR⁴)/(KL + KR)
    Q = [KL KR/(KL + KR)] (TL⁴ − TR⁴).

The wall surfaces still change temperature under load. The familiar factor of two for one black shield assumes fixed outer surface temperatures and identical gap coefficients. With a reflecting face on one side, the corresponding gap carries zero net heat. The shield then comes to the opposite plate temperature if that gap exchanges radiation. If both gaps are blocked, the model determines zero flow but leaves the shield temperature undetermined.

## Add a conducting support outside the viewing area

A solid frame can conduct heat between the two plate nodes even across an evacuated space. Model that frame as a separate two-terminal steady network. Its two original bath conditions are released when the frame is connected. Assume perfect end contacts, insulated frame sides, and a frame lying outside the stated radiating area. A floating shield, when present, has no contact with the frame.

For the worked walls, use the balanced five-rod bridge as a frame. Its two branches conduct 1 and 1/2 W/K in parallel, giving G = 1.5 W/K. Append this option to the example command above.

    --support studies/steady_bridge/study.json studies/steady_bridge studies/steady_bridge/facts.json 4cc763729e8d71b0abfc0eb5d1c3cc4d08185225104af8640541adcfdbf10bbf

Both heat paths see the same plate temperatures. Their rates add to the heat supplied by the backing walls. In watts, Q = G (TL − TR) + K (TL⁴ − TR⁴), where K includes the area and gray-surface factors. Use the **total** Q to calculate the wall temperature drops. The resulting total is **61.130 W**, split into **58.304 W through the frame** and **2.826 W by radiation**. All three signed rates use the left-to-right direction. With one perfectly reflecting outer surface the frame still conducts 60 W.

For positive support conductance the residual still increases with Q. Increasing the support conductance increases the magnitude of the transfer at fixed open temperatures and backing resistances. Solving at both ends of the support conductance enclosure, together with the existing port corners, bounds the total. The separate path enclosures use both their constitutive laws and the sum of their rates.
