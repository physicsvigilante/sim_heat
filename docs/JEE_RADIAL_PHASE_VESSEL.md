# Can adding insulation melt ice faster?

An insulated vessel contains a well-mixed ice–water bath at 273.15 K (0.02 kg ice, 0.03 kg liquid water, specific latent heat 334 kJ/kg). Its interior connects through a 0.50 K/W composite-wall backing conductor ([wall geometry](../studies/composite_wall/model.mo)) to the inner face ($r_i = 0.10\text{ m}$) of a hollow radial shell exposed to ambient air and a large isothermal enclosure. Assume quasi-steady conduction, negligible shell heat capacity, constant material properties, diffuse gray radiation with $\sigma = 5.67 \times 10^{-8}\text{ W/(m}^2\text{ K}^4)$, and ideal contacts.

**Predict before calculating:**

1. For a spherical shell ($r_o = 0.20\text{ m}$, $k = 2\text{ W/(m K)}$, $\varepsilon = 0.8$) in 293.15 K air ($h = 10\text{ W/(m}^2\text{ K)}$) and a 300 K enclosure, how much ice remains after 120 s and when does the ice run out?
2. For a 1 m long cylindrical pipe ($k = 1\text{ W/(m K)}$, $h = 5\text{ W/(m}^2\text{ K)}$, $\varepsilon = 0$, 293.15 K air), which of the stocked outer radii `0.12 m`, `0.20 m`, and `0.50 m` keep ice present for **260 s**?
3. If the spherical vessel experiences 100 s of warm daytime conditions followed by 120 s of cold nighttime conditions, does the bath end with more or less ice than it started with?
4. Without a surface thermometer, can weighing between 0.0095 and 0.0096 kg of melted ice after 120 s bound the unknown outer air-film coefficient $h$?

---

## 1. Forward melting through a spherical shell

The backing resistance is $R_{\text{port}} = 0.50\text{ K/W}$. The spherical shell adds

$$R_{\text{shell}} = \frac{1/r_i - 1/r_o}{4\pi k} = \frac{10 - 5}{8\pi} = \frac{5}{8\pi} \approx 0.19894\text{ K/W},$$

giving total conduction resistance $R_{\text{tot}} \approx 0.69894\text{ K/W}$ and outer area $A = 4\pi(0.20)^2 = 0.16\pi \approx 0.50265\text{ m}^2$. Balancing inward conduction against convection and radiation at the outer surface $T_s$ gives

$$\frac{T_s - 273.15}{R_{\text{tot}}} = A\left[10(293.15 - T_s) + 0.8\sigma(300^4 - T_s^4)\right].$$

Solving gives outer surface temperature **291.741 K** and inner shell face temperature **286.449 K**. The ice bath receives **26.598 W** total (**7.084 W** from the 293.15 K air and **19.514 W** from the 300 K enclosure).

Over 120 s the bath absorbs 3.192 kJ, melting **0.009556 kg** of ice and leaving **0.010444 kg** solid. Melting all 0.02 kg requires $0.02 \times 334 = 6.68\text{ kJ}$, so the ice runs out at **251.145 s**.

```sh
python -B -m tools.radial_phase_bath --study studies/composite_wall/study.json --root studies/composite_wall --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --phase-port hot --surface-port cold --transition-k 273.15 --latent-heat-j-per-kg 334000 --solid-kg 0.02 --liquid-kg 0.03 --duration-s 120 --inner-radius-m 0.1 --layer 0.2 2 --enclosure-k 300 --emissivity 0.8 --sigma 0.0000000567 --air-k 293.15 --h-w-per-m2-k 10
```

---

## 2. Critical-radius paradox: sizing a cylindrical shell for 260 s

Switch to a 1 m long cylinder with coating conductivity $k = 1\text{ W/(m K)}$ and pure convection ($h = 5\text{ W/(m}^2\text{ K)}$, $\varepsilon = 0$, $T_{\text{air}} = 293.15\text{ K}$). The total thermal resistance as a function of outer radius $r_o$ is

$$R(r_o) = 0.50 + \frac{\ln(r_o / 0.10)}{2\pi(1)(1)} + \frac{1}{2\pi r_o (1)(5)}.$$

Setting $dR/dr_o = 0$ locates the cylindrical **critical radius** at $r_c = k / h = \mathbf{0.20\text{ m}}$, where thermal resistance hits its minimum and the melting rate peaks:

| Outer radius (m) | Melting rate (W) | Ice exhaustion time (s) | Status at 260 s |
|---:|---:|---:|---|
| 0.12 | 25.180 | 265.288 | `meets_hold_time` |
| 0.20 | 25.992 | 257.004 | `fails_hold_time` |
| 0.50 | 24.396 | 273.817 | `meets_hold_time` |

Adding insulation from 0.12 m to 0.20 m **melts the ice faster** because the added surface area lowers convective resistance faster than the added wall increases conductive resistance. Both `0.12 m` and `0.50 m` survive 260 s, so the smallest established stocked size is `0.12 m` (`3/25`). Raising the required hold time to **270 s** eliminates `0.12 m` as well, leaving only `0.50 m` (`1/2`).

```sh
python -B -m tools.phase_shell_sizing --study studies/composite_wall/study.json --root studies/composite_wall --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --phase-port hot --surface-port cold --transition-k 273.15 --latent-heat-j-per-kg 334000 --solid-kg 0.02 --liquid-kg 0.03 --hold-duration-s 260 --inner-radius-m 0.1 --coating-k 1 --radius-m 0.5 --radius-m 0.2 --radius-m 0.12 --enclosure-k 280 --emissivity 0 --sigma 0.0000000567 --cylinder-length-m 1 --air-k 293.15 --h-w-per-m2-k 5
```

---

## 3. Day/night melting and refreezing cycle

Return to the spherical vessel from Part 1 ($r_o = 0.20\text{ m}$, $k = 2$, $\varepsilon = 0.8$) and expose it sequentially to:

- **Day (100 s)**: 293.15 K air ($h = 10$), 310 K enclosure → **+30.827 W** into the bath, absorbing **+3.083 kJ** and dropping the ice mass to **0.010770 kg**.
- **Night (120 s)**: 253.15 K air ($h = 8$), 240 K clear-sky enclosure → **−26.426 W** (freezing), removing **3.171 kJ**.

Across the full 220 s cycle the net energy change is **−88.436 J**, so the bath finishes with **0.020265 kg** of ice—slightly *more* solid than it started with, while remaining coexisting throughout both stages.

```sh
python -B -m tools.radial_phase_exposure --study studies/composite_wall/study.json --root studies/composite_wall --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --phase-port hot --surface-port cold --transition-k 273.15 --latent-heat-j-per-kg 334000 --solid-kg 0.02 --liquid-kg 0.03 --inner-radius-m 0.1 --layer 0.2 2 --emissivity 0.8 --sigma 0.0000000567 --stage day 293.15 10 310 100 --stage night 253.15 8 240 120
```

---

## 4. Inverse calibration: bounding $h$ from melted ice alone

Now keep the Part 1 spherical vessel, air (293.15 K), and enclosure (300 K, $\varepsilon = 0.8$), but treat $h$ as **unknown**. Weighing the ice after 120 s establishes that between **0.0095 kg** and **0.0096 kg** melted.

Because $0.0096 < 0.02\text{ kg}$, coexistence held for the entire 120 s, pinning the steady bath inflow to

$$Q_{\text{phase}} = \frac{334000\,\Delta m}{120} \in [\mathbf{26.441,\; 26.720}]\text{ W}$$

(outward-rounded from $26.44166\ldots\text{ W}$ and exact $26.72\text{ W}$). Since $Q_{\text{shell}} = -Q_{\text{phase}}$, the outer surface temperature lies in $T_s = 273.15 + R_{\text{tot}} Q_{\text{phase}} \in [\mathbf{291.631,\; 291.826}]\text{ K}$—strictly below 293.15 K air. Subtracting the radiative inflow $A\varepsilon\sigma(300^4 - T_s^4)$ and dividing by $A(293.15 - T_s)$ bounds the unknown film coefficient (outward-rounded from $[8.7507\ldots, 11.1161\ldots]$) to

$$h \in [\mathbf{8.750,\; 11.117}]\text{ W/(m}^2\text{ K)},$$

cleanly enclosing the true `10 W/(m² K)` from Part 1 without needing an outer surface thermometer. Had the measurement reached 0.02 kg (all ice melted), the tool refuses to infer $h$: an exhausted bath leaves the 273.15 K plateau at an unknown earlier instant, so $\Delta m / \Delta t$ no longer equals the steady plateau rate.

```sh
python -B -m tools.phase_film_calibration --study studies/composite_wall/study.json --root studies/composite_wall --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --phase-port hot --surface-port cold --transition-k 273.15 --latent-heat-j-per-kg 334000 --solid-kg 0.02 --liquid-kg 0.03 --duration-s 120 --melted-kg 0.0095 0.0096 --inner-radius-m 0.1 --layer 0.2 2 --air-k 293.15 --enclosure-k 300 --emissivity 0.8 --sigma 0.0000000567
```

All commands above run offline (`nativeExecuted: false`, `nativeQualified: false`) against source-pinned thermal network facts.
