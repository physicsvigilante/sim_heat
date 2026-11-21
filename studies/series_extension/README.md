# Add a layer to a wall already measured

A wall with a facing and two parallel strips has measured resistance 1/2 K/W under the [original assumptions](../composite_wall/README.md). Place a 0.10 m layer with conductivity 10 W/(m·K) and area 0.020 m² between the hot reservoir and the whole warm face. Keep the outer faces at 380 and 280 K. The new ideal contact is isothermal. All conduction is steady with constant material properties.

Can the old wall be reused as a single resistance to predict the new total heat rate and contact temperature? Its terminal resistance carries enough information for those two questions. The added layer contributes 0.10/(10 × 0.020) = 1/2 K/W. The series combination is 1 K/W. Hence 100 W flows and the new contact is at 330 K. The old wall now experiences only 50 K across its terminals.

Predict the branch split separately. The facing drops 25 K. The internal interface is at 305 K and the parallel paths carry 25 W and 75 W toward the cold face. The insert sensor reads −75 W. These internal observations require information about the wall's components.

The full model explicitly retains every original rod and adds the layer through public ports. This is a new assembly. Run the comparison with:

```sh
python -B -m unittest -v tests.test_series_extension
```
