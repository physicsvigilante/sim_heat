# Measuring specific heat with a conducting wall

A 0.200 kg sample sits in a calorimeter of heat capacity 20 J/K. Assume the sample and calorimeter share one uniform temperature and all heat enters through a wall of conductance 2 W/K. A bath maintains the far side at 380 K. The assembly warms from 280 K to 330 K in 34.65–34.67 s. What specific heat is consistent with the observation?

The driving temperature difference halves from 100 K to 50 K. For combined heat capacity C, the heat equation is C dT/dt = 2(380 − T), so the transit time is (C/2) ln 2. A time near 34.66 s gives C near 100 J/K. Subtract the calorimeter contribution before dividing by the sample mass. The result is about **400 J/(kg K)**.

The same inference works with a more complicated heat current P(T) when the baths stay fixed and the body has constant heat capacity. The transit time is proportional to C. Compute the transit time for 1 J/K, divide the measured time by that result, then subtract the empty calorimeter capacity and divide by mass. Use the longest admissible unit transit when deriving the lowest heat capacity, and the shortest when deriving the highest.

The offline tool accepts a pinned wall or a multi-terminal rod network, including a radiating surface. Run the example from the repository root.

```shell
python -B -m tools.timed_specific_heat --study studies/composite_wall/study.json --root studies/composite_wall --facts studies/composite_wall/facts.json --facts-sha256 f4687ad77987ba5b5452d19b4c3aaa7a17ee3ab2320b8b8a3ddca73b177b4d5b --port cold --reference-k 280 --slope-per-k 0 --enclosure-k 400 --area-m2 1 --emissivity 0 --sigma 0.00000005 --initial-k 280 --target-k 330 --time-low-s 34.65 --time-high-s 34.67 --calorimeter-j-per-k 20 --sample-kg 0.2
```

The resulting interval includes both stopwatch uncertainty and the engine's transit-time bounds. An equilibrium target takes unbounded time to reach from a distinct starting temperature in this model.
