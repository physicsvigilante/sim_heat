# What if only the insert conducts better?

Use the [composite wall](README.md) and replace the insert material. Its conductivity rises from 30 to 70 W/(m·K). Keep the geometry, both reservoir temperatures and all contacts fixed. Predict what happens to the heat rate through the *unchanged* parallel strip.

| Quantity | Original wall | Higher-conductivity insert |
| --- | ---: | ---: |
| Interface temperature (K) | 330 | 940/3 |
| Total heat rate toward the cold face (W) | 200 | 800/3 |
| Strip heat rate toward the cold face (W) | 50 | 100/3 |
| Insert heat rate in its sensor direction (W) | −150 | −700/3 |

The parallel conductance rises from 4 to 8 W/K. The facing still contributes 1/4 K/W in series, so the total resistance falls to 3/8 K/W. The 100 K reservoir difference now drives 800/3 W. The facing drops 200/3 K, leaving only 100/3 K across the parallel layer. The unchanged strip therefore carries **less** heat even though the wall as a whole carries more.

Reproduce both runs from the repository root with the normal offline CLI.

```sh
dir=studies/composite_wall
python -B -m qualification.h1_n13.conduction --root "$dir" --study "$dir/study.json" --facts "$dir/facts.json" --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b
python -B -m qualification.h1_n13.conduction --root "$dir" --study "$dir/higher_k.json" --facts "$dir/higher_k_facts.json" --facts-sha256 7b266f98ac5952ddc385e1555b6238fa775ef453c2eac4c899ff2e4a283b9e79
```

The successor descriptor pins the parent model and study. Both runs use the same observation requests, ideal interface and signed port convention. This investigation produces offline reference candidates.
