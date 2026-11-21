# Effective thermal resistance between two reservoirs

A steady, connected, storage-free wall or rod assembly with two maintained temperatures has a through-rate Q in watts. The temperature difference between the reservoirs divided by Q is the assembly’s effective resistance in K/W. At equal temperatures the measured ratio is undefined. A third reservoir can supply heat independently and breaks this two-terminal interpretation.

Run from the repository root, for example:

```sh
d=studies/composite_wall
python -B -m tools.terminal_resistance --root "$d" --study "$d/study.json" --facts "$d/facts.json" --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b
```

The original wall gives 1/2 K/W. Replacing its insert gives 3/8 K/W. The same command accepts the two circular rods of S1, where the two individual resistances add. Component names and rod port directions can vary. The tool identifies the warm terminal by its maintained temperature. It runs the bound offline engine, intersects the two oppositely signed terminal supply intervals, and divides the exact imposed temperature difference by the resulting positive interval. JSON endpoints are exact rational strings in the units named by each field. Source identities accompany every result.
