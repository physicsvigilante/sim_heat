# SIM_HEAT

An OpenModelica-based, compositional heat-transfer sandbox for LLM-authored physical systems and teaching exploration.

## Current status

**H0 design direction approved by the user; independent review pending. No physical capability is implemented or qualified. H1 implementation and native execution are not authorized by this documentation.**

This documentation records the H0 design presented and approved in the project conversation on 2026-11-14. User design approval is distinct from independent technical review, implementation acceptance, and execution permission.

The inspected repository baseline is commit `49a2cc42462b47026e86313bfeff39a9b17081cd`. At that revision the repository contains only `01_heat.pdf`. This document set is intended for a documentation-only development branch; its presence in a local review bundle does not imply it has been published or merged.

## Objective

An LLM should be able to describe an unfamiliar arrangement of supported thermal components, their properties, physical connections, boundaries, and initial conditions. The engine assembles, computes, and verifies the supported physics. A teacher can inspect the results and explore revised scenarios without production-code changes for each arrangement.

The LLM interprets and authors; the engine owns supported laws and mathematics; the viewer presents verified results. Textbook-answer completeness and faithful physical simulation are separate outcomes. Every explicitly requested quantity must nevertheless receive an honest result or limitation status.

## Read these documents

| Document | Purpose |
| --- | --- |
| [H0 foundation](docs/H0_FOUNDATION.md) | Approved design direction, component meanings, authoring responsibilities, and review boundaries |
| [Source coverage](docs/SOURCE_COVERAGE.md) | Preliminary physical-regime map, source locators, assumptions, issues, and development exposure |
| [H1 plan](docs/H1_PLAN.md) | Proposed bounded feasibility experiment, independent verification, and unresolved execution prerequisites |

## Initial candidate capability

The proposed foundation has three author-facing concepts: finite thermal bodies, uniform conducting rods, and fixed-temperature boundaries. It distinguishes steady conduction from lumped dynamics over physical time. Restricted Modelica composition over reviewed Modelica Standard Library components is the initial authoring candidate, with thin wrappers where they avoid manual intermediate calculations.

Illustrations 123, 134, and 135 are development examples. A separate post-freeze composition challenge is proposed, not selected or passed. No automatic symbolic solving, inverse solving, distributed heat diffusion, phase-front dynamics, convection, radiation, gas coupling, or interactive viewer is claimed.

## Relationship with NEW_THERM

`sim_heat` is initially a separate project. Keep compatible units, energy ownership, heat-flow signs, physical identities, and evidence meanings. Reuse infrastructure only after examining its actual suitability. Do not copy or refactor `new_therm`, edit its historical evidence, or transfer its qualification claims to this project.

## Working boundaries

Preserve `01_heat.pdf` byte for byte. Treat source statements, solution assumptions, adopted conventions, selected demonstration values, and computed outputs as different kinds of information. Never silently repair a source to match an answer.

No installation, native build, simulation, browser capture, CI activation, or code implementation is authorized by checkout or by these files. Before execution, approve a bounded plan that identifies the host, OpenModelica and library versions, numerical settings, comparisons, resource limits, and output locations. Preserve failed attempts and distinguish author checks from independent review.

The PDF's inclusion does not grant redistribution rights or an open-source license. No new project-wide license is selected here.
