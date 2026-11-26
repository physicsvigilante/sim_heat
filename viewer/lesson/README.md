# SIM_HEAT M05 · Interactive Calorimetry & Critical-Radius Vessel Lesson

Thin local browser lesson backed directly by the certified Python `simheat.system` engine over `127.0.0.1` loopback.

## Launch

```bash
python -B -m simheat.lesson_server --port 8765
```

Then open the printed `http://127.0.0.1:8765/viewer/lesson/` URL.

## Architectural Boundaries
- **Zero physics in JavaScript:** `viewer/lesson/core.mjs` and `viewer/lesson/app.mjs` never solve thermal equations. Every equation derivation (`POST /api/describe`) and interval solve (`POST /api/solve`) runs in Python `simheat.system`.
- **Preserved refusals:** `unsupported_regime`, `mode_sequence_uncertain`, and input/passivity validation errors (HTTP `400`) are surfaced verbatim.
- **Security:** Loopback `127.0.0.1` only, exact `Host` check (`421`), same-origin `POST` check (`403`), strict CSP, bounded 256 KiB JSON bodies (`413`), and disk-reading conduction kinds (`h1_study`, `derived_law_ref`) disabled over HTTP.
- **Offline provenance:** All responses keep `nativeExecuted=false`, `nativeQualified=false`, `independentlyCertifiedReference=false`, and `runnerConsumable=false`. No OpenModelica process is invoked.
