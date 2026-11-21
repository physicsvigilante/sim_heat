# Cooling through a star of three rods

Replace the middle reservoir of the [three-terminal star](../three_terminal/README.md) with a 0.5 kg body of specific heat 420 J/(kg·K), initially at 350 K. The two other reservoirs remain at 380 K and 280 K. The warm, body and cool legs have conductances of 2, 3 and 5 W/K, respectively, from the original dimensions and conductivities. Assume constant properties, a uniform body temperature, ideal contacts and storage-free rods.

When the body has zero net heat inflow, the body leg carries zero heat, so the body shares the junction temperature (2×380 + 5×280)/7 = 2160/7 K. Heat can still flow from the warm reservoir to the cool one. To find the rate at which the body approaches equilibrium, hold both bath temperatures fixed and perturb the body. Its effective resistance is 1/3 + 1/(2+5) = 10/21 K/W. The body has heat capacity 210 J/K and time constant 100 s. Its initial heat inflow is −87 W.

For this network T(t) = 2160/7 + (350 − 2160/7) exp(−t/100) K and the body energy change is 8700[exp(−t/100) − 1] J, with t in seconds. The experiment checks the complete 500-second history at half-second intervals.

The general observer derives an effective conductance and equilibrium from the admitted rod network. Its domain is one connected transient network with exactly one finite body and one or more maintained reservoirs. Run it from the repository root:

```sh
d=studies/loaded_star
python -B -m tools.body_relaxation --root "$d" --study "$d/study.json" --facts "$d/facts.json" --facts-sha256 1fccce839e69c67230819498fb1da973ac614264378ada75ae7d0b13b7816ff8
```
