# Can a triangle of rods replace a star?

Three reservoirs maintain 380 K (warm), 330 K (middle) and 280 K (cool). In the star, each has a rod to a common insulated, storage-free junction. The warm, middle and cool legs have conductivities 20, 30 and 50 W/(m·K), respectively. In the triangle, connect warm–middle, warm–cool and middle–cool directly with conductivities 6, 10 and 15 W/(m·K). Every rod has length 0.1 m and area 0.01 m². These illustrative cases assume constant properties, perfect contacts and steady conduction.

At the given temperatures, the star junction settles at (2×380 + 3×330 + 5×280)/10 = 315 K. Warm and middle supply 130 W and 45 W, and cool absorbs 175 W. Use the triangle to check all three signed rates. Would the match survive a different temperature at just one reservoir?

For leg conductances gᵢ, conservation at the common junction gives Tⱼ = ΣgᵢTᵢ / Σgᵢ. Substitution into Qᵢ = gᵢ(Tᵢ − Tⱼ) yields a direct link of conductance gᵢgₖ / Σg between every pair of terminals i and k. This gives the triangle above. The equality applies to each terminal's steady supply for all admitted reservoir temperatures. Internal rod flows and the star junction temperature belong to their respective assemblies.

Run the general response tool for either study. Its rows identify reservoirs supplying heat into the network; each column gives the change in those rates per kelvin added at that column's reservoir, holding the other temperatures fixed. Each matrix entry is an interval with exact rational endpoints.

```sh
d=studies/three_terminal/star
python -B -m tools.terminal_response --root "$d" --study "$d/study.json" --facts "$d/facts.json" --facts-sha256 16c414cf443e389560056bb782ac3dea0ac75c40cf2ba103fa0de25bef18def0
```

The engine computes the response with its steady junction solution for each independent terminal temperature increment. This investigation supports connected storage-free networks with at least two maintained terminals.
