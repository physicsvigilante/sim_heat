# H1 authored-source preview — bounded composition inspection

**Status:** prospective source-only exploration, not an OpenModelica run, physical result, teacher study, or historical C1 qualification. This milestone adds one *developer-authored illustrative* composition and a generic preview for **any supported admitted H1 study**. It is neither a blind held-out author trial nor a native author-to-result transfer.

## Use the working offline admission and source preview

From the repository root (Python 3.13.5, installed H1 checking dependencies):

```sh
python -B -m h1 h1/cases/TEACH_SPLIT3/study.json --root h1/cases
python -B -m h1.source_preview h1/cases/TEACH_SPLIT3/study.json \
  --root h1/cases --out /tmp/TEACH_SPLIT3-source.json
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/viewer/source_preview/`. The included source-only JSON loads by default. The file picker can open a locally generated preview for another H1 study. Preview files remain in the local browser and are never uploaded. Importing a JSON document checks its **source-only display schema**, not its origin or the accuracy of authored source statements. Do not treat the browser as an authoring validator; run the actual H1 CLI against trusted source files first.

The preview uses the **unchanged H1** `load_study`, parser, connection topology, provenance and public-request admission. No separate apparatus-specific parser, physical law or numerical evaluator is introduced. It shows source-bound component values in SI, logical nodes, rod endpoints, supplied attribution and requested units/statuses. Where H1 accepts parameter-sourced values, the preview preserves the original parameter provenance target and identifies the effective field it supports. Multiple original records (such as a source given and a unit convention for one input) remain distinct. Whole-component provenance remains attached to that component, not fabricated as scalar attribution; `@model` regime assumptions are separately visible. The picker namespaces source components and generated graph nodes so a legally authored component `node_0` cannot be mistaken for the logical graph node `node_0`. Imported display data with impossible steady/transient mode labels or unknown provenance kinds is refused, but these checks do not authenticate an arbitrary imported JSON source. It does **not** derive heat flow, node temperatures, energy histories, equilibrium, predictions, or unsampled values. Only authored `T` or `T_initial` source **inputs** appear; these are not output temperatures. Lines mean connectivity, not rod lengths or directions of heat transport.

The H1 CLI reports `not_computed` for every admitted public request. A valid admitted study **still requires independently reviewed native execution** and separate reference checking before any simulated result can be presented. Source hashes check identity relative to named bytes; they do not authenticate a teacher's source interpretation, a GitHub run or a solver host.

## The new composition

The fixed [Split-3 illustrative task](../experiments/teacher_split3/TASK.md) specifies three thermal bodies, two fixed boundaries and seven rods (both area-defined and circular), including a copper–aluminum shortcut and an **ownerless ideal junction** in the steel–cold branch. The study requests source interfaces for four observations: body temperature, rod heat flow, body energy and cross-node temperature difference. This is deliberately beyond a one-component demonstration, but is **developer chosen and known before this test**, not an independent teacher-generated blind problem. Its inputs are illustrative and not values supplied by the heat textbook.

Validated example identity at first authoring: model SHA-256 `549ee4fe6b082f12f51b45c0b3e9da9c963f439c670f5f0411162e329278da4e`, study SHA-256 `d4bb3edd13bf6fe841153a3fcd2c0ac960fa31fa94763d5e14db6d5e99737907`. Graph has six logical nodes (three Body, two boundary and one ideal junction), seven connected rods, one connected network and four admitted `not_computed` requests. These are checked source/topology facts, **not** simulated values or physical geometry. Save future candidate identities separately; never silently repin a historical native plan.

## Admission/refusal and safety boundaries

The preview writer refuses an invalid or unadmitted H1 study before output, stale model SHA, incompatible public request, missing provenance or unsupported physical source. It refuses overwriting source files under the authored case root, and writes an output atomically only after admission succeeds. The browser refuses malformed/non-source-only imports and clears stale graph, request and selection state, especially if `nativeQualified`, `nativeExecuted`, source-fidelity status or request status is promoted.

The browser's input graph is intentionally schematic. Nodes are arranged with a deterministic diagram layout that asserts **no apparatus geometry**. All element labels and source attribution are rendered with text nodes, not injected as markup. No dynamic Modelica compilation, numerical solution, newly sealed reference, native-runner call, original archived data modification or source-identity attestation is performed.

## Evidence and next gate

The tests run both **Python source admission** and **JavaScript source schema** against the authored case and separately against existing steady/transient H1 fixtures, including negative mutations and invalid preview imports. Hosted Chromium tests load real HTTP, click/keyboard-inspect components, refuse an inappropriately qualified imported document while clearing stale state, and accept a second unrelated source-only H1 payload with the same viewer code. CI also runs inherited offline tests and replays the six original *native diagnostic* bundles byte-for-byte, without executing their binaries. These distinct evidence classes must not be conflated.

This milestone stops **before** any new native command or authorization. The next meaningful gate requires a reviewed, non-regenerating native plan with trusted host/OMC/MSL/source/reference identity and a bounded attempt budget **followed by explicit owner permission**. No C1 frozen reference or failing historical C1 result may be rewritten by this exercise.

## Teaching source-only what-if comparison (offline, no predictions)

The local read-only authoring workbench can now independently admit **two**
existing H1 studies before opening its loopback socket. For example:

```sh
python -B tools/authoring_workbench.py h1/cases/D2/study.json --root h1/cases \
  --compare h1/cases/D2_K2/study.json
```

Open the printed local inspector URL and look under **06 · teacher what-if**.
The existing D2 and D2_K2 studies form a legitimate conductivity revision:
`rod.k` is an **authored** 100 → 200 W/(m K) change, and the second
source/model hashes are distinct. Teachers can inspect either composition's
physical source connections, inputs, units, provenance and requests in the
same viewer without modifying the core solver. There is deliberately **no
computed heat flow, temperature trajectory, final answer or automatic
OpenModelica execution**. Compare statements describe source documents, not
measured or simulated changes. The original revision studies are not edited.

Alternatively, choose a second preview JSON in the page; this is only
client-side shape checking, and the browser does **not** verify the uploaded
preview against original model/study bytes or independently authenticate
textbook provenance. A second source submitted through `--compare` is instead
fully re-admitted by Python under the same trusted root before binding the
loopback socket. Both routes preserve `nativeExecuted=false`,
`nativeQualified=false` and every public request `not_computed`. The browser
refuses impossible same-hash but changed-model/study metadata, stale/forged
native evidence and inconsistent H1 graph descriptors, while using physical
port groups rather than generated node numbers when comparing connectivity.
A refused replacement clears the stale scenario from the visible viewer.
The server still offers only exact allowlisted GET routes, rejects writes
and foreign Host headers, and never serves raw source files.

This is one step toward an explorable JEE teaching workflow **within the
existing conduction component domain**, not a conductivity-solving or
OpenModelica qualification milestone. An independent bounded review of this
new presentation/evidence semantics is required before accepting it; a
separately authorized native comparison remains a future step.

### Corrected comparison behavior after independent review #01

The comparison is intentionally about **authored source changes** and never
computes resulting heat flows or temperature trajectories. Every scenario
selection invalidates unfinished earlier file reads; when a viewed scenario is
successfully replaced, its graph, selection details, public requests and source
identity change together. A refused replacement clears the old scenario and
returns the visible inspector to the baseline instead of displaying obsolete
facts. A new baseline also cancels pending scenario reads, and a pending
startup scenario fetch cannot overwrite a subsequent user-selected scenario.

The browser comparison additionally checks that **one declared study SHA-256
cannot refer to two different model SHA-256 identities**, even if their
visible component values happen to be equal. It still does *not* authenticate
model/study bytes, source attribution or an owner's signature: importing a
source-only JSON file is deliberately display-schema validation only. When a
component is added, removed or changes its supported law/type, the comparison
shows the affected authored SI input inventory and original input/component
provenance as well as the kind/presence change. No unsupported new physical
law is inferred from a source-only display.
