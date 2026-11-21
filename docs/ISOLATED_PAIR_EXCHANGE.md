# How quickly do two insulated bodies exchange heat?

Two bodies with uniform temperatures and heat capacities C1 and C2 are joined by a network of storage-free rods. The surrounding enclosure is insulating. Energy conservation fixes the common equilibrium temperature at (C1 T1 + C2 T2)/(C1 + C2), using initial temperatures. The rod arrangement sets the rate of approach.

A unit temperature difference applied between the body nodes gives the effective network conductance G in W/K. If D is the instantaneous temperature of the first body minus that of the second, the first body loses heat at rate G D and the second gains it at the same rate. Subtracting their energy balances gives dD/dt = -G (1/C1 + 1/C2) D. With reduced heat capacity C* = C1 C2/(C1 + C2), the difference decays exponentially with time constant C*/G. The limiting signed heat passed from first to second is C* D(0).

Run the offline observer from the repository root:

    python -B -m tools.isolated_pair_exchange --study h1/cases/D2/study.json --root h1/cases/D2 --facts h1/reference_cases/D2.json --facts-sha256 befcb977a08bdb4d3f15d903ebafccf910d83675f8d1a92f1988bca74a8a547a

The output names both bodies in alphabetical order. In D2 the first is cold. The initial transfer from cold to hot is -12 W, the limiting transfer is -22,500 J, and the difference falls to 1/e of its initial value after 1,875 s. At equal initial temperatures the transfer stays zero, while the time constant still describes how the same network would respond to a temperature difference. The observer requires exactly one connected transient network, two bodies, and no maintained baths.
