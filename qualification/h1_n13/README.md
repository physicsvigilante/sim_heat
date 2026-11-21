# Offline conduction reference candidate

This milestone belongs to SIM_HEAT. It covers Fourier conduction through storage-free rods, isothermal bodies with constant heat capacity and maintained-temperature boundaries. A JEE-style investigation can ask for a junction temperature, compare two temperatures, determine the sign of a rod's heat flow, or track a body's energy change as it warms. The author supplies each physical fact and unit, with a separate facts file for checking.

## Use

Run from the repository root with the H1 CI Python dependencies. Pass an H1 study, its allowed root, independently specified H1 reference facts and their SHA-256. For a revision, the allowed root must include its parent. The inherited loader at the reviewed base has known Windows path limitations. Development fixtures without parent references use their own case directory.

```sh
python -B -m qualification.h1_n13.conduction --study h1/cases/D1/study.json --root h1/cases/D1 --facts h1/reference_cases/D1.json --facts-sha256 FACTS_SHA256
python -B -m unittest -v qualification.h1_n13.test_conduction
```

The JSON result records source identities, SI units, every exported field and authored request, and each body's and boundary's signed heat integral in J over a transient. Steady solutions have one value per series, an empty time grid and no time integrals. Transient values correspond to exact rational instants `stopTime*i/intervals`; the displayed seconds are binary64 representations. Study admission keeps its own public request statuses. The candidate schema has no native runner authority.

## Calculation and checks

N4 validates the pinned fact bytes and bounds circular areas with rational bounds on pi. N5 assembles node ownership, oriented rods and conductance intervals. The offline loader checks the admitted study, source hashes and physical port partitions. Replaying its admitted numeric bindings with exact decimal arithmetic checks every physical slot and the study analysis against the separately supplied facts.

For each owned node, solve the N7 interval Dirichlet problem with 2 K on that node and 1 K on the other owners. Subtracting 1 K gives its dimensionless influence at every junction, by linearity and constant-temperature invariance. This eliminates junctions for any accepted topology. The transient state contains one normalized temperature and its time integral for each body and an affine constant. The time and temperature normalizations are taken from the source. Signed rod flow is positive from port a to port b; body inflow is positive into storage and boundary supply is positive into the network.

N11 supplies outward fixed-point intervals, matrix products and the Taylor machinery. The successor builds a matrix of the required dimension and applies the exponential at the source time step using degree-24 interval Horner evaluation, a proven norm tail bound and power-of-two scaling and squaring. It checks junction power balance, each body's stored energy against its integrated inflow and the energy balance of each connected network. Steady networks use the junction solution directly.

Every emitted binary64 centre is compared against both endpoints of its outward enclosure. The conservative per-sample limits are 1e-8 K, 1e-8 W, 1e-5 J and 0.64 ulp for positive static constants. The result records the maximum error bound divided by the applicable limit for each series. Unsupported bounds, excessive enclosure widths and unsupported physics refuse. The inherited H1/N4 graph and study limits, N7 junction limits, and the bounded exponential scaling domain apply. A successful run establishes an offline source-mathematics candidate for that case. Independent checking and native qualification have separate evidence requirements.

Radiation requires a new component law with explicit emissivity, area, absolute temperatures and exchange assumptions. Its fourth-power temperature dependence is outside this linear solver. No radiation, convection, spatial diffusion, phase change or OpenModelica execution is part of this milestone.
