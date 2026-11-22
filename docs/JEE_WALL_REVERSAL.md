# Does reversing a composite wall change its heat current?

Two composite walls, A and B, meet at an ideal contact. Each has a facing of conductance 4 W/K in series with a strip and an insert of conductances 1 and 3 W/K in parallel. These are the values at 280 K. In A every rod conductivity increases by 0.625% of its 280 K value per kelvin. In B all conductivities are constant. The outer baths are at 380 and 280 K. Assume steady one-dimensional conduction along each rod, insulated sides and zero contact resistance.

**Predict first.** When A touches the hot bath, what are the interface temperature and the heat current? When B touches the hot bath, does the magnitude increase or decrease? Which parallel branch carries more heat?

## Solve by current continuity

At 280 K each wall has effective conductance
`G = [1/4 + 1/(1+3)]⁻¹ = 2 W/K`. Write temperature rises above 280 K as numerical values in kelvin. For A, integrating the linear conductivity factor from 0 to rise x gives `F(x) = x + x²/320`. For B the integral is just x. In steady flow a rod carries its reference conductance times the difference of these integrated values at its ends. All rods within A share that factor, so series and parallel reduction works in F throughout A. Match the **physical temperature** and current at the contact.

| Hot bath touches | Equation for contact rise x | Interface | Heat current from A to B |
| --- | --- | --- | --- |
| A | 2[F(100) − F(x)] = 2x | 340 K | +120 W |
| B | 2F(x) = 2(100 − x) | 326.606 K | −106.788 W |

For the first row x = 60 solves the equation. For the second row solve x² + 640x − 32000 = 0 and select the root within the baths. A conducts better over its hotter operating range in the first arrangement. The forward magnitude exceeds the reverse magnitude by about 12.37% relative to the reverse magnitude. The insert always carries three quarters of its wall's current magnitude because it spans the same two endpoints as the strip. Its recorded sign follows the insert's own endpoint order.

## Replay both arrangements

From the repository root run `python -B -m tools.wall_reversal_lesson`. The replay uses two copies of the pinned composite-wall study. For the first row it releases A's cold terminal and B's hot terminal to form the common contact. For the second it exchanges which terminal is released on each two-terminal wall. This gives the swapped bath temperatures in the conductance calculation. Rod signs in the JSON follow the source study's endpoint labels for each run. The reported A-to-B sign always uses the same material order.

As a control, set both slopes to zero in the same calculation. Either direction then has two 0.5 K/W walls in series, giving a 330 K interface and a heat-current magnitude of 100 W. The replay includes this control and preserves the engine's rational interval endpoints.
