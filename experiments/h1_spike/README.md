# H1 offline component spike (UNQUALIFIED)

**Status:** Exploratory, not an accepted implementation of H1. Based on the proposed H1 contract and GitHub H0 notes. No Modelica compiler build or physical simulation has been performed. The H0 independent review and H1 acceptance gates remain pending.

This directory contains only a candidate `SimHeat` Modelica package and three example compositions corresponding to source illustrations 123, 134, and 135. The three conceptual components are a storage body, a conducting rod, and a fixed-temperature boundary. `RodArea` and `RodCircular` are two parameterizations of the same conducting element; `RodCircular` composes `RodArea`, which itself composes the MSL `ThermalConductor`. A body internally uses MSL `HeatCapacitor` with explicitly fixed initial temperature; a boundary uses MSL `FixedTemperature`.

These examples deliberately separate *source data* from chosen demonstration values. S1 uses the PDF conductivities with the **adopted** 4184 J/kcal conversion; this does not correct the original text. D1/D2 numerical values are illustrative, not from their symbolic source statements.

The examples have not been validated by an OpenModelica compiler. The exact runtime/standard-library version is not pinned and there is no tested restricted-Modelica parser, topology validator, output adapter, result reader, run controller, or observation contract. Do not run arbitrary contributed Modelica using this spike. The library has not yet been demonstrated to pass Modelica compilation or to preserve runtime heat-flow signs; these require later controlled qualification.

Offline-only test: `python3 -m unittest discover -s experiments/h1_spike/checks -v` from repository root. This test independently checks reference arithmetic only; it does not read or validate the Modelica source and must not be presented as native evidence.

Do not merge this spike to `main` or infer H1 acceptance from its presence.
