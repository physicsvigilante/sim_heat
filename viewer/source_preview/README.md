# Generic H1 admitted-source explorer

This directory displays only **already admitted authored source**. It is not the existing six-case [historical native diagnostic explorer](../network/index.html); it deliberately displays zero computed native readings.

The example `data/TEACH_SPLIT3.json` is deterministically built from `h1/cases/TEACH_SPLIT3/study.json` using `python -B -m h1.source_preview ...`, reusing H1's original parser, port topology and public-request admission. The generic SVG draws logical nodes and rod connections, not geometry. Selecting a rod displays its authored SI inputs and provenance. The browser validates the source-only schema, enforces `not_computed`, refuses apparent native qualification and clears stale state on any rejected import.

To inspect a different supported composition, run the [offline CLI described here](../../docs/ADMITTED_SOURCE_PREVIEW.md) on its source files and load the resulting JSON through the local file picker. No source values are authenticated by a browser import. H1 admission does not establish textbook fidelity or native approval.
