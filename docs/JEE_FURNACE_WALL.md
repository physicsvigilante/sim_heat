# Where does a furnace wall lose its temperature?

The inside face of a furnace wall is held at 610 K. Its outside face radiates to a large enclosure at 300 K. Two solid panels lie in series, with a thermal contact resistance of 0.20 K/W between them. Each panel consists of a facing of conductance 4 W/K in series with a strip and insert of conductances 1 and 3 W/K in parallel. The outer face has area 0.20 m² and emissivity 1. Use σ = 5.0 × 10⁻⁸ W/(m² K⁴). Ignore convection and heat loss from the edges. Assume steady state.

1. Find the heat loss, both temperatures at the contact and the radiating surface temperature.
2. How much heat passes through the strip and through the insert in each panel?
3. Predict how repairing the contact to make its resistance zero changes the heat loss and the surface temperature.

## Solve from the hot face outward

Each panel has resistance 1/4 + 1/(1 + 3) = 0.50 K/W. Let q be positive toward the enclosure. The solids and contact together give a surface temperature of Tₛ = 610 − 1.20q, with q in watts. At steady state the rate arriving at the surface equals its net radiation.

```text
q = εσA (Tₛ⁴ − 300⁴) = 10⁻⁸ (Tₛ⁴ − 300⁴)
```

Try Tₛ = 400 K. The radiative loss is 175 W, and the conductive drop is 1.20 × 175 = 210 K. Both equations agree. This is the unique solution between 300 and 610 K because outward radiation increases with surface temperature while the heat supplied through the wall decreases.

| Position from furnace to enclosure | Temperature |
| --- | ---: |
| Inner face | 610 K |
| First panel, just before contact | 522.5 K |
| Second panel, just after contact | 487.5 K |
| Radiating face | 400 K |
| Enclosure | 300 K |

The two solids each account for 87.5 K, and the contact accounts for 35 K. Each facing carries 175 W. The parallel strip carries 43.75 W and the insert carries 131.25 W toward the enclosure. The source study orients its insert from the outer face inward, so its signed reading is −131.25 W.

## Repair the contact

With zero contact resistance, Tₛ = 610 − q. Substituting this in the radiation equation gives about **200.42 W** and **409.58 K**. Improving contact increases the heat supply to the outer face, which settles at a higher temperature and radiates more power.

## Replay and vary the material

Run `python -B -m tools.furnace_wall_lesson` from the repository root. The output includes the original calculation, the repaired contact and a third case with temperature-dependent rods. Each case reports face temperatures and signed rod flows.

In the third case all rod conductivities in the first panel increase linearly by 0.001 of their reference values per kelvin above 566.25 K. Those in the second panel decrease by the same fraction per kelvin above 443.75 K. These reference temperatures are the arithmetic means of the panel face temperatures in the table. Integrating a linear conductivity over that interval therefore gives exactly the reference conductivity times the temperature difference. The same 175 W and the same four panel-face temperatures satisfy the steady balances, even though the temperature profiles inside individual rods can change.

### Can the same heat loss hide different panel drops?

Keep the 0.20 K/W contact. Give the first panel a relative conductivity slope of +0.0025/K at 285 K and the second a slope of −0.002/K at 312.5 K. The fourth replay case predicts 610 → 560 K across the first panel, 560 → 525 K across the contact, and 525 → 400 K across the second panel.

Check each solid at its mean face temperature. At 585 K the first conductivity factor is 1.75, giving 2 × 1.75 × 50 = 175 W. At 462.5 K the second factor is 0.70, giving 2 × 0.70 × 125 = 175 W. The 35 K contact drop and 400 K radiating surface still carry 175 W. Measuring only total heat loss would miss the redistribution between the panels.
