# How long does ice keep a wall face at the melting point?

An isothermal mixture of 0.500 kg of ice and 0.100 kg of water touches the cold face of the composite wall. Its melting point at the specified constant pressure is 273.15 K. Take the specific latent heat as 334,000 J/kg. The opposite face is maintained at 380 K. The wall has negligible heat capacity and resistance 0.5 K/W. All heat from the wall goes into the mixture, which is initially at phase equilibrium.

**Predict.** How much ice remains after ten minutes? How long can the mixture keep the wall face at the melting point?

During coexistence the wall supplies (380 − 273.15)/0.5 = **213.7 W**. After 600 s it has delivered 128,220 J, melting about 0.384 kg and leaving about **0.116 kg of ice**. The plateau ends after 0.500 × 334,000 / 213.7 ≈ **781.47 s**. A 1,000 s request therefore reports only the first 781.47 s and the inventory at exhaustion. Computing the subsequent liquid temperature would require its heat capacity and a different boundary law.

~~~sh
python -B -m tools.latent_heat_bath --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --port cold --transition-k 273.15 --latent-heat-j-per-kg 334000 --solid-kg 0.5 --liquid-kg 0.1 --duration-s 600
~~~

The offline observer replaces the selected maintained terminal with the hypothetical phase bath. All other maintained temperatures and the conductor network come from the pinned study. Positive heat into the bath melts solid. Negative heat freezes liquid until it runs out. At exactly zero inflow the phases coexist indefinitely in this model. Both initial phase masses and the latent heat must be positive. A rate interval spanning both signs produces a refusal. A requested time inside the exhaustion-time interval is reported as uncertain, with conservative bounds on the inventory and modeled duration.

This is a lumped, perfectly mixed, constant-pressure phase-equilibrium example. Wall properties, geometry and contact resistance stay fixed, and there is no heat loss to any other system. It assumes the wall is already in its steady conduction regime. The model ends at depletion of the first phase.

## When will the meltwater reach 20 °C?

Once the last ice melts, all 0.600 kg of liquid can warm. Use constant liquid specific heat 4,200 J/(kg K) and a target of 293.15 K. The wall rate falls as the temperature difference falls. The water needs **50,400 J** after melting, in addition to **167,000 J** for the original ice. A separate target-time observer follows both stages under the same maintained-bath temperatures.

Let To be the backing network's open-port temperature and R its resistance seen from the phase bath. With final mass M and specific heat c the single-phase temperature obeys Mc dT/dt = (To − T)/R. Integrating from the transition temperature Tm to target T gives the additional time RMc ln[(To − Tm)/(To − T)]. For the worked example the phase transition takes **781.47 s**, the liquid then warms for **261.13 s**, and the target is reached at **1042.60 s** from the start.

~~~sh
python -B -m tools.phase_bath_target --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --port cold --transition-k 273.15 --latent-heat-j-per-kg 334000 --solid-kg 0.5 --liquid-kg 0.1 --final-specific-heat-j-per-kg-k 4200 --target-k 293.15
~~~

The same calculation covers a liquid that finishes freezing and then cools, using the solid's specific heat. Targets must be beyond the transition in the direction of heat transfer and strictly before the open-port equilibrium. The hypothetical bath remains lumped and perfectly mixed, with constant properties and no further phase transitions on the chosen path.

## Which of two phase baths is exhausted first?

Replace both maintained terminal temperatures with initially coexisting solid and liquid phases. An illustrative phase-change material at 333.15 K contains 0.10 kg of solid and 0.45 kg of liquid. Its latent heat is 200,000 J/kg. The cold end has 0.50 kg of ice and 0.10 kg of liquid water at 273.15 K, with latent heat 334,000 J/kg. Assume constant pressure, insulated surroundings, ideal thermal contact, and a storage-free connecting network.

The composite wall conducts (333.15 − 273.15)/0.5 = **120 W** toward the ice. The warmer material can supply 90,000 J by freezing. The ice can absorb 167,000 J before it fully melts. The common plateau therefore lasts **750 s**, when the donor has fully solidified and about **0.231 kg of ice** remains. Equal masses need not change phase on the two sides because the specific latent heats differ. The joules lost by one bath equal the joules gained by the other.

~~~sh
python -B -m tools.coupled_phase_baths --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --left-bath hot 333.15 200000 0.1 0.45 --right-bath cold 273.15 334000 0.5 0.1 --duration-s 1000
~~~

The output gives the first exhaustion time even for shorter observation windows. Inventories advance only to the earlier of the requested duration and that event. Equal energy budgets exhaust both participating phases simultaneously; equal transition temperatures leave both mixtures unchanged. Only two-terminal steady networks are admitted in this experiment.

### What remains at thermal equilibrium?

For the closed pair above, append `--equilibrium-cp 2000 4200` to calculate the limiting state. These are the warmer material's specific heat as a solid and the colder material's specific heat as a liquid, in J/(kg K). Assume no other transitions across the temperature interval, constant specific heats and negligible heat capacity in the connecting rods. The optional equilibrium result is independent of the requested observation time. It does not supply a time of arrival.

After the donor freezes, cooling its 0.55 kg of solid from 333.15 K to 273.15 K can release another 66,000 J. Together with its latent heat it can supply **156,000 J**. Melting every bit of ice would require 167,000 J, so the final temperature stays at **273.15 K** and about **0.033 kg of ice** remains. The connecting network sets the initial 120 W and the timing of the first event. The energy balance fixes the limiting temperature and inventories.

If the receiver can melt and then reach the donor's transition temperature while the donor is still two-phase, the final state instead stays at the donor temperature. Otherwise both participating phases are exhausted and the common temperature lies between the two transition temperatures. For that case, with total final heat capacities Ch and Cc, equate the donor's freezing energy plus Ch(Th − T) to the receiver's melting energy plus Cc(T − Tc). The output records latent and sensible energy separately for each bath.

### When have the two reservoirs exchanged 120 kJ?

Append `--equilibrium-cp 2000 4200 --transfer-target-j 120000` to the two-bath command. The target is the total energy transferred from the initially warmer bath to the initially colder bath. This passage calculation has its own endpoint, independent of the duration requested for the first plateau.

For the first 90 kJ the two temperatures stay fixed, giving 750 s at 120 W. The donor then cools as a solid, while the receiver still contains ice. The next 30 kJ takes longer per joule. The calculation gives a total time of **1083.37 s**. Both endpoint temperatures and the duration of each stage appear under `transferPassage`.

If E is the energy transferred so far, conservation fixes each temperature: the hot material starts to cool after freezing its initial liquid, and the cold material starts to warm after melting its initial solid. Between these two event energies the temperature difference D(E) is affine. For an interval ΔE with terminal conductance G, the elapsed time is ΔE/(G D) for constant D. When D falls from D1 to D2 the time is ΔE ln(D1/D2)/[G(D1 − D2)]. The equilibrium transfer is approached asymptotically. Positive targets at or beyond that energy have no finite passage.

## A finite heat-capacity body coupled to a two-phase bath

Instead of a second maintained reservoir or a second phase bath, attach a lumped isothermal body of heat capacity $C$ at initial temperature $T_0$ to one port of the steady network (`--body-port`) while holding a coexisting two-phase mixture at `--phase-port`. While both phases coexist, the body relaxes exponentially with time constant $\tau = C R_{\text{port}}$ toward its open-port equilibrium $T_{\text{eq}}$:

$$T_b(t) = T_{\text{eq}} + (T_0 - T_{\text{eq}})e^{-t/\tau}.$$

For a two-terminal network ($T_{\text{eq}} = T_{\text{tr}}$), the cumulative latent energy entering the bath is $E_p(t) = C(T_0 - T_{\text{tr}})(1 - e^{-t/\tau})$. If $|C(T_0 - T_{\text{tr}})|$ does not exceed the participating phase's latent budget, the bath never exhausts and the body approaches $T_{\text{tr}}$ asymptotically; otherwise the phase exhausts at exact finite time $t_{\text{exh}} = \tau \ln\!\left(\frac{C(T_0 - T_{\text{tr}})}{C(T_0 - T_{\text{tr}}) - E_{\text{lim}}}\right)$ with the body still at $T_0 - E_{\text{lim}}/C$. In multi-reservoir networks, a third maintained bath adds a steady bias $Q_\infty$ so the phase-bath inflow $Q_{\text{in},p}(t) = Q_\infty + Q_{\text{tr}}e^{-t/\tau}$ can even reverse sign once during the exposure (melting first and then refreezing, or vice versa). The `body_phase_bath_exchange` command brackets $T_b(t)$, cumulative latent energy, remaining inventories, any reversal time $t^*$, and the first exhaustion event without fabricating post-exhaustion trajectories.

~~~sh
python -B -m tools.body_phase_bath_exchange --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --phase-port hot --body-port cold --transition-k 273.15 --latent-heat-j-per-kg 334000 --solid-kg 0.02 --liquid-kg 0.03 --capacity-j-per-k 200 --initial-k 373.15 --duration-s 100
~~~
