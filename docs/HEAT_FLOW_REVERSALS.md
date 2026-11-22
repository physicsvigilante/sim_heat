# When does a rod start carrying heat the other way?

The positive heat rate through a rod runs from its port_a to its port_b. Observe a rod in any admitted transient study by supplying its name and the study's pinned reference facts.

```sh
d=qualification/h1_n13/heldout
python -B -m tools.heat_flow_reversals --root "$d" --study "$d/study.json" --facts "$d/facts.json" --facts-sha256 57c393f2b11bf658a378b6fa6ab96425b14116b8c2fc519e4bedba1e883d1783 --rod lower
```

TwinBridge's lower rod initially conducts from the junction toward the blue body. As the bodies exchange energy with each other and the bath, this rod's signed rate becomes negative. Its analytical rate is −10 exp(−t/60) + 80 exp(−t/15) W. The root is 20 ln(8) s, inside the measured 41.5–41.6 s bracket. Reversing the rod's port orientation reverses the recorded signs and preserves the time bracket.

The calculation runs the offline reference engine. A reversal requires two sample enclosures strictly on opposite sides of zero. Intervening enclosures touching zero are inconclusive. The output gives the transition between endpoint signs and exact rational time bounds; extra crossings within an interval can go undetected. With no certified reversal, the history may have maintained one direction, touched zero, or changed direction between unresolved samples.
