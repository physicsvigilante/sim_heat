# Composite wall with a parallel heat path

A 0.10 m facing covers the full 0.020 m² wall. Behind it, two strips run side by side, each 0.10 m thick with area 0.010 m². Thermal conductivities are 20 W/(m·K) for the facing, 10 for the strip and 30 for the insert. The outer faces are maintained at 380 K and 280 K. An ideal isothermal sheet joins the layers. Assume perfect contacts, insulated sides, constant properties and steady one-dimensional conduction within each piece. These are illustrative JEE-style givens.

**Investigation.** Find the interface temperature and the heat rate through each piece. Predict the sign reported by a sensor on the insert whose positive direction points toward the warm face.

Use R = L/(kA). The facing contributes 1/4 K/W in series with two parallel resistances of 1 and 1/3 K/W. Their parallel equivalent is 1/4 K/W, so the total heat rate is 100/(1/2) = 200 W. The facing drops 50 K, giving 330 K at the interface. The remaining 50 K drives 50 W through the strip and 150 W through the insert toward the cold face. The insert's reversed ports report −150 W. The hot reservoir supplies 200 W and the cold reservoir absorbs 200 W.

From the repository root, run the generic offline engine with the checked facts pin.

```sh
python -B -m qualification.h1_n13.conduction --root studies/composite_wall --study studies/composite_wall/study.json --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b
```

The authored model, study and same-author checking facts use the existing public interfaces. The output is an offline reference candidate.
