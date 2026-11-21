# Radiation through a stack of shields

Consider two large black parallel plates at fixed temperatures, separated by vacuum. Insert two thin, opaque black shields. Each shield has a single steady temperature, the same on both faces. Adjacent surfaces see only each other and have the same area. With no heat leak, each of the three gaps carries the same heat rate. Summing the three Stefan–Boltzmann equations gives

    Q = A σ (T_left^4 − T_right^4) / 3.

For N black shields between fixed-temperature black plates the denominator is N + 1. The shield temperatures are evenly spaced in the fourth power of absolute temperature. For gray faces, the reciprocal of each gap coefficient is its resistance to a difference of fourth powers. Sum these reciprocals across the stack.

The offline gap experiment attaches the two plates to conducting networks. Their temperatures depend on the heat rate, so the fixed-temperature factor applies to the actual plate temperatures. Applying it directly to the remote bath temperatures would miss the drops in the conductors. Each repeated CLI option `--shield LEFT RIGHT` adds one shield, with face emissivities named in physical order. An optional conducting support joins the two end plates and bypasses every shield.

A perfectly reflecting face breaks radiative exchange across its gap. Shields still connected to an end plate equilibrate to that plate. A group cut off from both ends can equilibrate internally at an undetermined common temperature. The steady model reports that temperature as undetermined.
