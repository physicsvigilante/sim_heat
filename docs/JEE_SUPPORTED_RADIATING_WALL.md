# Can a bath freeze inside a warmer enclosure?

A substance melts at 300 K. It starts with 0.20 kg solid and 0.30 kg liquid, and its specific latent heat is 200 kJ/kg. One conducting rod joins the bath to a junction. A second joins the junction to a support held at 280 K. A third joins the junction to a gray face exposed to a large isothermal enclosure.

| Rod from the junction to | Conductance |
|---|---:|
| Bath | 3 W/K |
| Cold support | 5 W/K |
| Exposed face | 2 W/K |

The face has area 1 m² and emissivity 0.8. Use σ = 5.67 × 10⁻⁸ W/(m² K⁴). Assume ideal thermal contacts, negligible heat storage in the rods and face, and insulated rod sides. The bath stays at 300 K while the phases coexist. [Network model](../studies/three_terminal/star/model.mo)

**Predict.** The enclosure warms from 310 K to 420 K. At what enclosure temperature does the bath switch from freezing to melting? At the switch, can the face still absorb radiation?

## Find the switch without solving a quartic

At the switch the bath exchanges zero heat. Both ends of its 3 W/K rod must therefore be at 300 K. The support still draws 5 × (300 − 280) = **100 W**. All 100 W must arrive through the 2 W/K rod, so its face is at 300 + 100/2 = **350 K**.

For net radiation into the face, set εσA(Tₑ⁴ − 350⁴) = 100 W. The required enclosure temperature is **362.202 K**. Below that threshold the support draws some heat from the bath and liquid freezes. Above it the bath receives heat and solid melts. At the threshold, radiation and conduction carry 100 W to the support while the phase masses stay constant.

Run the following command from the repository root. Compare the face and enclosure readings under `surfaceTemperatureBoundsK` and `balanceEnclosureTemperatureBoundsK`. Each pair encloses the answer in kelvin. [Pinned checking dependencies](../requirements-h1-ci.txt)

~~~sh
python -B -m tools.phase_balance_temperature --study studies/three_terminal/star/study.json --root studies/three_terminal/star --facts studies/three_terminal/star/facts.json --facts-sha256 16c414cf443e389560056bb782ac3dea0ac75c40cf2ba103fa0de25bef18def0 --bath-port middle --surface-port warm --transition-k 300 --area-m2 1 --emissivity 0.8 --sigma 0.0000000567
~~~

## Change the enclosure twice

Expose the face to 420 K for 1,000 s, then switch it to a 310 K enclosure. Predict how long the second exposure must last to restore 0.30 kg of liquid.

| Enclosure | Radiation into face | Heat into support | Net heat into bath |
|---|---:|---:|---:|
| 420 K | 188.362 W | 155.226 W | +33.136 W |
| 310 K | 27.615 W | 54.760 W | −27.144 W |

Each row follows from balancing the three rods at the junction and the net radiation at the exposed face. The first exposure melts 33.136 kJ / (200 kJ/kg) ≈ **0.1657 kg**. The second must remove the same energy, so it lasts about 33,136 J / 27.144 W = **1,220.73 s**. The liquid mass peaks at 0.4657 kg, within the initial total mass of 0.50 kg.

~~~sh
python -B -m tools.phase_exposure_sequence --study studies/three_terminal/star/study.json --root studies/three_terminal/star --facts studies/three_terminal/star/facts.json --facts-sha256 16c414cf443e389560056bb782ac3dea0ac75c40cf2ba103fa0de25bef18def0 --bath-port middle --surface-port warm --transition-k 300 --latent-j-kg 200000 --solid-kg 0.2 --liquid-kg 0.3 --area-m2 1 --emissivity 0.8 --sigma 0.0000000567 --stage 420 1000 --recover-at-k 310 --track-entropy
~~~

Read the first stage’s liquid mass and the recovery duration under `inventoryRecovery`. For an energy check, add the heat reaching the support over both intervals. The support receives **222.073 kJ** even though the bath ends with zero net energy change.

**Extension.** For each ideal reservoir use ΔS = Q/T, with Q positive into that reservoir. Divide the support heat by 280 K. Divide each enclosure’s heat by its own temperature before summing. The support gains about 793.117 J/K, the two enclosures together lose about 557.226 J/K and the restored bath has zero entropy change. The unrounded terms give **235.892 J/K generated** during the modeled heat transfers. Preparing the enclosures and switching between them lie outside the calculation.
