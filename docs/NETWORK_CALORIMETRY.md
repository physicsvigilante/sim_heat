# Does increasing conductivity change the final temperature?

Two insulated bodies at 353.15 K and 293.15 K have heat capacities 500 and 1500 J/K. Their connecting rod stores no heat. At equilibrium the hotter body has lost exactly the heat gained by the cooler body, so the common temperature is (500 × 353.15 + 1500 × 293.15)/2000 = **308.15 K**. A rod of greater conductivity changes how quickly they approach that limit.

In D2 the conductance is 0.2 W/K. Subtracting the body heat equations gives a decaying temperature difference with time constant 1/[G(1/500 + 1/1500)] = 1875 s. At 9375 s the difference is 60 exp(−5) ≈ 0.4043 K. In D2_K2 the conductance doubles; the remaining difference is 60 exp(−10) ≈ 0.002724 K.

The offline observer partitions an admitted transient network by its rod connections. For each isolated component it reports the capacity-weighted equilibrium temperature, checks the sum of all body energy changes at every sampled time, and encloses the final temperature spread from the body's temperature bounds. Components touching a maintained reservoir are listed separately. Constant properties, positive conductances and a connected isolated component make a common limiting temperature meaningful.

From the repository root, replay the baseline:

```sh
python -B -m tools.network_calorimetry --root h1/cases/D2 --study h1/cases/D2/study.json --facts h1/reference_cases/D2.json --facts-sha256 befcb977a08bdb4d3f15d903ebafccf910d83675f8d1a92f1988bca74a8a547a
```

For the published revision, run on Linux using the parent case directory so its descriptor can validate both source pins:

```sh
python -B -m tools.network_calorimetry --root h1/cases --study h1/cases/D2_K2/study.json --facts h1/reference_cases/D2_K2.json --facts-sha256 d4da4597c01cb175d6b0b02c10ec055a9653a9e56e2ffc6e0d74a6335a150b6f
```

This frozen H1 loader refuses the nested revision path on Windows. The baseline runs there with its own case directory as the root.
