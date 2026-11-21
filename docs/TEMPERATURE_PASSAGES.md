# When does a body pass a target temperature?

A body can warm through a temperature and later cool through it in the same investigation. Run the offline observer on the published TwinBridge network from the repository root:

```sh
d=qualification/h1_n13/heldout
python -B -m tools.temperature_passages --study "$d/study.json" --root "$d" --facts "$d/facts.json" --facts-sha256 57c393f2b11bf658a378b6fa6ab96425b14116b8c2fc519e4bedba1e883d1783 --body blue --threshold-k 307
```

Blue warms through 307 K between 36.9 and 37.0 s and cools through it between 94.3 and 94.4 s. Heat exchange with both the other body and the bath allows this reversal.

Each bracket is supported by two sampled temperatures whose full error intervals are strictly on opposite sides of the target. Continuity guarantees at least one passage between those samples. The recorded direction describes the endpoint transition. Additional passages, tangencies and excursions between samples can go undetected. A sample touching the threshold is inconclusive for this strict test. The output reports how many sample intervals overlap the threshold; a run with no certified passage is inconclusive about crossings between sample times. Time endpoints are exact rational seconds on the imposed grid. Calculations are offline reference candidates.
