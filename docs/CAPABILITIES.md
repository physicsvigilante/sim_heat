# SIM_HEAT capability and evidence registry

Current product inventory, 2026-11-18. Start at the [local start page](../index.html), then use the [thermal explorer](../viewer/network/index.html). This document consolidates navigation and existing claims; it is not a new physical qualification or a replacement for original records. The November 17 audit is a historical snapshot.

## Evidence categories

| Category | Available use | Meaning and limit |
|---|---|---|
| Archived native diagnostics | Six published cases and one saved comparison | Actual archived OpenModelica output; `diagnostic_only`, `nativeQualified=false`. Not independent measurement or general numerical qualification. |
| Admitted authored-source previews | [Generic source-only inspector](../viewer/source_preview/index.html), including TEACH_SPLIT3 | Authored SI values, provenance and logical connectivity only; all public requests `not_computed`. No computed output, imported-file authentication or new native run. |
| Analytical checking data | Separate H1 checking pipeline | Calculated references used to check supported models; not native output and never a replacement for missing native readings. |
| Offline analytical thermal tools | Python CLI and library modules under `tools/` | Interval-enclosed steady, radial, radiative, convective, phase-change, transient and scoped-inverse calculations over pinned conduction networks; `nativeExecuted=false`, `nativeQualified=false`, `independentlyCertifiedReference=false`, `runnerConsumable=false`. Not native OpenModelica runs or browser simulations. |
| Expected-only source views | Separate historical C1 branches, not the main explorer | Source fields, dependencies and topology; nine C1 native public readings remain uncomputed. No physical pose or apparatus geometry is established. |

The archived-results browser shows saved native diagnostics only; the separate authored-source inspector displays **uncomputed H1 source** and never promotes it to a native result. Hash agreement is integrity relative to supplied/versioned evidence, not authentication of an arbitrary newly repacked archive. A new run needs separately trusted source/artifact custody and explicit bounded native authorization. No such authorization is granted here.

## Current capabilities

| Capability | Available now | Boundary / source |
|---|---|---|
| Thermal composition | Lumped bodies, storage-free conducting rods, fixed-temperature boundaries and thermal-port connections | Restricted linear lumped domain. [Historical H1 foundation contract](H1_IMPLEMENTATION_CONTRACT.md). |
| Structured authoring | Restricted Modelica plus study metadata, provenance and requested observations | Admission checks source and supported quantities; it does not simulate or authorize a run. [Current authoring guide](AUTHORING.md); [dated offline amendment](H1_OFFLINE_AMENDMENT.md). |
| Source-only composition inspection | Generic [authored-source inspector](../viewer/source_preview/index.html) and [offline generator](../h1/source_preview.py) for admitted H1 studies | Displays SI inputs, graph connections, component and model-level assumptions, source identities and `not_computed` requests. No new computed readings, apparatus geometry, imported-file authentication or native qualification. |
| Archived result inspection | Select cases and quantities; inspect saved temperatures, signed flows and energy changes | Logical graph, not apparatus geometry; no invented intermediate samples. [Viewer guide](../viewer/network/README.md). |
| Steady presentation | S1's saved algebraic state | Backend evaluation indices are not seconds or a transient history. |
| Conductivity comparison | Saved D2 versus D2_K2 | [Comparison](../viewer/network/compare.html) selects recorded histories, not live parameter simulation. |
| Original CSV verification | Exact original normalized CSV hash and consistency checks | Arbitrary CSV is not admitted as native evidence. Files stay in the browser. |
| Archive reproduction | Read-only replay through the existing adapters | [Replay tool](../viewer/network/tools/replay_published_archives.py); requires original trusted ZIPs and never executes their binaries. |
| Teacher workflow | Existing archived-case comparison and separate source-only composition inspection | Unfamiliar author-to-native-result transfer and real classroom usability are not established. |

## Published case inventory

IDs below are the existing catalog identities, not a new case schema. The [versioned catalog](../viewer/network/data/index.json) remains the source of truth for filenames and SHA-256 values. Every row is an **archived native diagnostic**, not a newly executed result.

| Catalog ID | Case | Mode / teaching use | Published bundle |
|---|---|---|---|
| `H1_D1` | D1 | Transient: one body and hot reservoir | [D1](../viewer/network/data/D1.json) |
| `H1_D2` | D2 | Transient: two isolated bodies exchanging heat | [D2](../viewer/network/data/D2.json) |
| `DEV_BRIDGE` | DEV_BRIDGE | Transient: two reservoirs and five rods | [Bridge](../viewer/network/data/DEV_BRIDGE.json) |
| `H1_S1` | S1 | Steady: copper and steel in series | [S1](../viewer/network/data/S1.json) |
| `TEACH_RING4` | TEACH_RING4 | Transient: illustrative four-body ring and shortcut | [Ring4](../viewer/network/data/TEACH_RING4.json) |
| `H1_D2_K2` | D2_K2 | Transient: hypothetical conductivity revision of D2 | [D2_K2](../viewer/network/data/D2_K2.json) |

Ring4 is a developer-authored illustration, not a held-out textbook-author trial. D2_K2's input change is hypothetical, while its displayed output comes from its recorded native run. Neither changes the evidence category.

## Separate C1 history

The [original C1 freeze](../qualification/h1_c1/FREEZE.md) and [dated audit](PROJECT_AUDIT_2026_11_17.md) describe a separate qualification experiment. The original reference-precision margin was 80 times against a required minimum of 100 times; the later exact cross-host saved-reference seal reproduction also failed. Both remain failures. The alternate seal is not silently adopted, the historical branch stack is not integrated, and the nine native C1 public readings are still uncomputed.

PR51's original review requested changes; PR52 resolved the specific integer-metadata defect in a successor. Owner-approved integration landed on main at `4162c3d47016150076b226ebe2585073a785547a`, with tree `2ad10a1679d528f88030494f0349171502ef8e0f` identical to the reviewed PR52 tree. See the [PR52 independent report](https://github.com/physicsvigilante/review_sandbox/blob/40b11729ab4c890540d3a6d24a31fa374b711d8c/projects/sim_heat/pr-52/reviews/review-01-chat-b.md). This resolves a source correction, not C1 native qualification. Exact CI evidence and subsequent integration records live in the central review repository, rather than a permanently copied test-count badge here.

## Offline analytical thermal tools

Beyond the restricted native H1 Modelica grammar and the archived browser explorer, the repository provides composable offline Python analytical modules under `tools/`. Each module operates on pinned steady/transient conduction networks using rational interval enclosures, refuses unidentifiable or out-of-domain inputs, and stamps `nativeExecuted=false`, `nativeQualified=false`, `independentlyCertifiedReference=false`, and `runnerConsumable=false`. Direct programmatic entry points enforce these flags through [offline_provenance.py](../tools/offline_provenance.py) (which validates 64-hex digest shape and refuses forged non-`False` flags; source-byte authenticity is established by pinned facts/study loading via [terminal_response.py](../tools/terminal_response.py)).

| Offline analytical family | Representative modules | Scope and status |
|---|---|---|
| Steady networks and calorimetry | [terminal_response.py](../tools/terminal_response.py), [network_calorimetry.py](../tools/network_calorimetry.py), [two_heater_calorimetry.py](../tools/two_heater_calorimetry.py) | Multi-terminal conductance matrices, heat-flow budgets and multi-bath calorimetry; offline analytical, `nativeQualified=false`. |
| Radial shells and critical radius | [spherical_conduction.py](../tools/spherical_conduction.py), [radiating_radial_layers.py](../tools/radiating_radial_layers.py), [shell_size_selection.py](../tools/shell_size_selection.py) | Spherical and cylindrical multilayer conduction, outer diffuse-gray radiation, prescribed convective films and stocked-radius selection; offline analytical, `nativeQualified=false`. |
| Planar and concentric radiation shields | [radiative_gap.py](../tools/radiative_gap.py), [shield_count_design.py](../tools/shield_count_design.py), [radial_radiation_shields.py](../tools/radial_radiation_shields.py) | Diffuse-gray vacuum gaps, planar shield stacks, and concentric spherical or end-loss-free cylindrical shields (including Dewar phase baths); offline analytical, `nativeQualified=false`. |
| Latent phase baths and staged exposure | [latent_heat_bath.py](../tools/latent_heat_bath.py), [radial_phase_bath.py](../tools/radial_phase_bath.py), [phase_shell_sizing.py](../tools/phase_shell_sizing.py), [radial_phase_exposure.py](../tools/radial_phase_exposure.py), [radial_exposure_sizing.py](../tools/radial_exposure_sizing.py) | Coexisting solid/liquid plateaus, stop-on-exhaustion clocks, day/night sequential stages and stocked-radius survival sizing; offline analytical, `nativeQualified=false`. |
| Lumped bodies and body-phase transients | [body_relaxation.py](../tools/body_relaxation.py), [isolated_pair_exchange.py](../tools/isolated_pair_exchange.py), [body_phase_bath_exchange.py](../tools/body_phase_bath_exchange.py) | Exponential relaxation, isolated two-body exchange and finite-capacity bodies coupled to finite two-phase baths (including multi-reservoir sign reversal); offline analytical, `nativeQualified=false`. |
| Scoped inverse calibration | [radial_film_calibration.py](../tools/radial_film_calibration.py), [two_environment_calibration.py](../tools/two_environment_calibration.py), [phase_film_calibration.py](../tools/phase_film_calibration.py), [phase_shell_conductivity.py](../tools/phase_shell_conductivity.py) | Bounded inference of outer film coefficient, emissivity or one unknown shell-layer conductivity from thermometer or timed melt/freeze bands; offline analytical, `nativeQualified=false`. |

## Not implemented or not established

The restricted native H1 Modelica grammar and browser explorer have no native convection, radiation or phase-change component library and no browser-launched solver. Across the entire repository, there is no general symbolic/inverse solver, fluid-flow/CFD engine, moving-boundary Stefan ice-growth solver, blackbody spectral/Wien solver, moving mechanics, arbitrary temperature-dependent material law, or autonomous natural-language-to-validated-simulation workflow. Classroom effectiveness has not been established.

## Next bounded product milestone

Complete one unfamiliar composition of already supported components through **authored model → admission → faithful source view → separately authorized native execution → saved-reference checks → inspectable results**. The restricted source-view step now exists for admitted H1 models, but the full native author-to-result chain does not. Evaluate whether a teacher can follow that path and understand a refusal without developer intervention. This remains planned work, not a claim of completion.

Before any fresh native operation, define and review the concrete execution path, source/reference custody, host/toolchain identity and bounded attempt policy, then obtain explicit owner authorization. Do not add another mock authorization layer unless it closes a real operational requirement. Existing archived playback remains useful while that separate work is unfinished.
