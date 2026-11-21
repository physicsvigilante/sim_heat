# When does a bridge rod carry heat?

Two paths connect reservoirs at 380 K and 280 K. The upper path contains feed and drain rods, each with conductivity 20 W/(m·K). The lower inlet and outlet have conductivity 10 W/(m·K). A fifth rod of conductivity 10 W/(m·K) joins the two midpoints, oriented upper to lower. Every rod has length 0.10 m and area 0.010 m². Assume steady conduction, ideal junctions, constant properties and insulated lateral surfaces.

**Predict before solving.** Can the transverse rod carry zero heat even though each path carries heat? What changes if only the upper feed conductivity doubles?

For conductances G₁, G₂ on the upper path and G₃, G₄ on the lower path (ordered hot to cold), the bridge balances when G₁/G₂ = G₃/G₄. Each midpoint then sits at the same fraction of the imposed temperature difference. Here both fractions are 1/2. Both midpoints are at 330 K, so the link carries 0 W. The upper and lower paths carry 100 W and 50 W respectively. The terminal resistance is 100/150 = 2/3 K/W.

For the revision, let u and v be upper and lower temperature rises above 280 K. Heat balance gives 4(100−u) = 2u + (u−v) and (100−v) + (u−v) = v. Hence u = 65 K and v = 55 K. The transverse rod now carries 10 W from upper to lower. The hot reservoir supplies 140 + 45 = 185 W, giving 20/37 K/W. Dropping the link from this revised network would change the answer.

Run the two studies through the existing conduction and two-terminal resistance tools with the exact pins in the test. Run the paired comparison with `python -B -m unittest -v tests.test_steady_bridge`. These are illustrative offline calculations.
