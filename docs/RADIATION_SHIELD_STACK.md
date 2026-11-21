# Radiation through a stack of shields

Consider two large black parallel plates at fixed temperatures, separated by vacuum. Insert two thin, opaque black shields. Each shield has a single steady temperature, the same on both faces. Adjacent surfaces see only each other and have the same area. With no heat leak, each of the three gaps carries the same heat rate. Summing the three Stefan–Boltzmann equations gives

    Q = A σ (T_left^4 − T_right^4) / 3.

For N black shields between fixed-temperature black plates the denominator is N + 1. The shield temperatures are evenly spaced in the fourth power of absolute temperature. For gray faces, the reciprocal of each gap coefficient is its resistance to a difference of fourth powers. Sum these reciprocals across the stack.

The offline gap experiment attaches the two plates to conducting networks. Their temperatures depend on the heat rate, so the fixed-temperature factor applies to the actual plate temperatures. Applying it directly to the remote bath temperatures would miss the drops in the conductors. Each repeated CLI option `--shield LEFT RIGHT` adds one shield, with face emissivities named in physical order. An optional conducting support joins the two end plates and bypasses every shield.

A perfectly reflecting face breaks radiative exchange across its gap. Shields still connected to an end plate equilibrate to that plate. A group cut off from both ends can equilibrate internally at an undetermined common temperature. The steady model reports that temperature as undetermined.

## Designing for a heat-leak limit

Suppose two black plates face across 0.02 m² of vacuum and each is connected to its bath by a 0.5 K/W wall. The baths are at 380 K and 280 K. How many identical black shields limit the steady leak to 7 W?

At the design current, the plates would be at 376.5 K and 283.5 K. Using σ = 5.67 × 10⁻⁸ W/(m² K⁴), evaluate the radiation between these plate temperatures and divide by the number of gaps. One shield leaves two gaps and exceeds the limit. Two shields give three gaps and meet it. The forward solver checks both adjacent counts with the conducting walls coupled.

For gray surfaces, write the dimensionless bare resistance as 1/ε_left + 1/ε_right − 1. Each identical shield adds 1/ε_front + 1/ε_back − 1. At the target current, subtract the heat conducted through any direct support from the available heat-leak allowance before sizing the shields. The integer calculation includes equality at the target. A perfectly reflecting face can remove the radiation term entirely.

The offline shield_count_design tool returns the minimum count when the port bounds resolve it. If the bounds span more than one count, guaranteedSufficientCount is the conservative upper count. A null upper bound means the available information gives no finite guarantee. A no_finite_count status means every admissible parameter value fails for every finite count.
