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
