# Source coverage and interpretation record

**Date:** 2026-11-14  
**Status:** Preliminary H0 study map; not a completed audit, implementation claim, or numerical qualification.

## 1. Source identity and preservation

| Field | Value |
| --- | --- |
| Repository | `physicsvigilante/sim_heat` |
| Inspected baseline | `49a2cc42462b47026e86313bfeff39a9b17081cd` |
| Source path | `01_heat.pdf` |
| Git blob SHA-1 | `18755813329b21f5e2ac432b2a5aebfe6dc21a60` |
| SHA-256 of uploaded source bytes | `8768a84a865b7f5a20e551b639be76263a0d882f317ec3d5c0b42ae72f491d1f` |
| Byte count | `1034396` |
| PDF pages | 23 |
| Printed page range | 2.88-2.110 |

The uploaded PDF's Git blob identity matches the repository source. Preserve those bytes. These notes describe interpretations and issues separately; they do not edit the source or imply redistribution permission.

Locators below use 1-based PDF page numbers. The chapter and its illustrations have been development-exposed through this conversation. An unimplemented example from this PDF is not automatically an unfamiliar-source test.

## 2. Preliminary physical-regime map

The subject descriptions are source-derived; the scheduling column records our design choice. All capabilities remain unimplemented in `sim_heat` at this baseline.

| Source locators | PDF pages | Physical subject | Initial treatment |
| --- | --- | --- | --- |
| Heat conduction and Illustrations 122, 123, 127, 128, 133, 136 | 1-2, 5-6, 8-10 | Steady heat transfer in rods, layers, and connected junctions | Start with 123; other cases remain exposed study material |
| Illustrations 134, 135 | 9-10 | A body heated through a rod; two finite bodies exchanging heat | Core transient development cases, with labeled numerical bindings |
| Illustrations 129, 130, 132, 137 | 6-8, 10-11 | Cylindrical/spherical geometry, temperature-dependent conductivity, and a varying-area conductor | Later reusable physical extensions |
| Convection discussion | 11 | Natural and forced convection; lumped cooling relationship | Later; supplied coefficients do not imply resolved fluid motion |
| Illustrations 139-147 and cooling discussion | 16-21 | Radiation, radiation-conduction combinations, and cooling laws | Later with explicit mechanism, geometry, and approximation assumptions |
| Illustrations 125, 131 and ice-growth discussion | 2-3, 7-8 | Boiling energy load and latent-heat-driven ice growth | Later; distinguish a latent load from a moving interface |
| Illustrations 124, 126 | 2-3 | Gas cooling in a rigid vessel; conduction through a loaded piston | Future thermodynamic coupling; not H1 |
| Illustration 138 and absorption discussion | 13-15 | Radiation absorption and spectral fractions | Separate later investigations |
| Illustrations 148-151 and spectrum discussion | 21-23 | Solar radiation, spectral peaks, and Wien's law | Separate later investigations; not all are time simulations |
| Test Your Concepts X and XI | 11-12, 23 | Additional conduction and radiation exercises | Exposed source pool; not exhaustively assessed in H0 |

This grouping does not assert that every member uses the same approximation or that each source statement is internally consistent. Review a case's literal statement and diagram before admitting it.

## 3. Initial development cases

### H1-S1: Illustration 123

**Locator:** PDF page 2, printed page 2.89.

The source gives a copper rod of length 75 cm and a steel rod of length 125 cm, both with circular cross-section of diameter 2 cm, joined end to end. Their outer ends are held at 100 degC and 0 degC. Their lateral surfaces are insulated. The given conductivities are `9.2e-2` and `1.1e-2 kcal/(m.s.degC)`. The requests concern junction temperature and heat transferred per unit time.

Model interpretation: two uniform storage-free conductors with an ideal junction and two fixed-temperature boundaries, investigated in steady state. Record ideal contact and constant-property assumptions. The source gives diameter; derive area through the trusted geometry conversion rather than a manually precomputed given.

The calorie-to-joule convention is a required explicit decision before an SI numerical reference. Do not silently replace the source conductivities with external tabulated values. See SRC-123-UNITS below.

### H1-D1: Illustration 134

**Locator:** PDF page 9, printed page 2.96.

The source describes a maintained-temperature water tank at `T0`, a smaller body with mass `m`, specific heat `c`, and starting temperature `T1 < T0`, connected by a rod with length `L`, area `A`, and conductivity `k`. It explicitly assumes negligible rod heat capacity and asks for body temperature as a function of time.

Model interpretation: one maintained-temperature boundary, one finite uniform-temperature body, and one storage-free rod. Record the ideal connection and absence of other modeled heat exchanges. Complete numerical values are not supplied; a native run needs a separately identified demonstration binding. Numerical evidence does not fulfill the symbolic source request.

### H1-D2: Illustration 135

**Locator:** PDF pages 9-10, printed pages 2.96-2.97.

The source gives two bodies with masses `m1`, `m2`, specific heats `s1`, `s2`, and initial absolute temperatures `(T1)0 > (T2)0`, joined through a rod of length `l`, area `A`, and conductivity `k`. It explicitly neglects radiative heat loss and asks for temperature difference after time `t`.

The worked solution uses uniform body temperatures, constant capacities, a storage-free conducting rod, and no external heat-exchange term. Record these as adopted/solution-supported modeling assumptions, not all as literal statement givens. A selected numerical binding must be labeled illustrative. See SRC-135-SUBSCRIPT below.

## 4. Source-issue register

These are issues identified during H0, not an exhaustive errata list. Preserve the printed source and independently derive verification references.

| ID | Locator and observation | Required treatment |
| --- | --- | --- |
| SRC-123-UNITS | Illustration 123, PDF page 2: the worked substitution uses conductivities in kilocalorie-based units but labels the resulting heat flow in `J/s` without a displayed conversion. | Retain the literal answer as source evidence; flag the inconsistency; choose and record a calorie convention; independently verify units and flow. Do not treat the mislabeled printed number as the SI oracle. |
| SRC-135-SUBSCRIPT | Illustration 135, PDF page 10: the final printed exponential contains `m1*s2` in a denominator, whereas the preceding balances and derivation use `m1*s1`. | Keep the literal printing; derive the reference from the two energy balances and the conductor law; disclose the interpretation in the numerical example. |

Interpretation and computation must remain independently assessable. A solver can correctly execute the wrong interpretation. Numerical agreement with a worked answer cannot by itself settle a source conflict.

## 5. Information and exposure categories

For each eventual case retain a source locator, literal givens/requests, diagram connectivity, and separate records for worked-solution assumptions, adopted assumptions, unit conventions, selected demonstration parameters, derived quantities, and unresolved information.

Label any chosen numeric values for Illustrations 134 and 135 as **demonstration bindings**, not source givens or recovered data. An unknown shape or dimension remains unknown; schematic layout cannot become a physical input.

The previously discussed three-body branching example is development-exposed. A post-freeze challenge may still test no-repair authoring, but its author's access to the chapter, code, examples, and expected results must be disclosed. Do not claim blind testing without evidence.

## 6. Evaluation and limits

Maintain separate assessments of interpretation fidelity, physical/numerical correctness, simulation coverage, educational usefulness, and textbook-answer completeness. Also identify execution origin, verification status, assumptions, exposure, and whether authoring required production changes.

No source case has been simulated, passed, or qualified by this document. Detailed study continues alongside admitted physical extensions rather than requiring every exercise to be solved before H1.
