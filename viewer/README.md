# H2-01 · Read-only Thermal Bridge Explorer

The viewer displays a **previously executed** OpenModelica thermal network. It is **not a physics solver or independent measurement**. Source: [run 43699424883](https://github.com/physicsvigilante/sim_heat/actions/runs/43699424883), artifact 14155084346. One build/one native launch, 42/42 exports and 98/98 diagnostic checks. Native observations remain `diagnostic_only`, `nativeQualified=false`, not a fully qualified result or blind C1 test.

## Use

From the repo root run `python -m http.server 8000`, then open http://localhost:8000/viewer/. No backend or native compiler is used by this viewer. It needs HTTPS or localhost browser crypto for data identity checks.

The bundled preview contains **23 unmodified native-output values per selected channel** at 0, 1000, 1720, 1730, and every additional 1000 seconds through 20000. A slider and playback select saved times only; curves visually connect samples without creating new physical values. The network graph shows logical links, not geometry. Arrows reflect the signed native rod flow. Body energy change is **J**, fixed-reservoir power is **W**; the sum of body energy changes is display arithmetic only.

To inspect all **2001** original canonical times, download the archived artifact, extract `case_01/normalized.csv`, and import it through the viewer. The browser verifies **exact SHA-256** `4b1a822680c03742e3031f5be653b48e7dd736613be355796862de483c0e39fe` before accepting. It validates all selected columns and the 2002 original records, including one identical duplicate terminal row; no repairs or interpolated data. The file is not uploaded to a service. GitHub artifacts have finite retention; the selected preview remains in source Git.

The original artifact ZIP SHA-256 is `f16975a25eea79f61f7819fb9e704ab04a33630044a51a0d062b8399c1c9ce38`; raw MAT SHA-256 is `e1da06d7223dd271317881b2d737b73c40ec643a8d533568bf7ef3bfbb5443a9`. The old MATv4 v1 provenance label incorrectly implied independence of some unique channels; this viewer does not reuse it.

## Checks and risk

Run `node --test viewer/tests/trace.test.mjs`, then `python -B viewer/tests/browser_smoke.py --screenshot /tmp/simheat-viewer.png` with Playwright/Chromium available. Standard CI also runs 151 H1 offline tests, four arithmetic fixtures, and browser interaction evidence. It installs pinned dependencies on a network-capable runner but **does not run OpenModelica**. See [H2-01 scope](../docs/H2_01_VIEWER_SCOPE.md).

Risk **R1 focused independent review**, because existing native evidence, signs, and units are presented to teachers. If source physics, numerical values/semantics, provenance or acceptance rules change, escalate to R2. The new PR and review packet must be pinned to exact SHAs. No merge without owner approval. Classroom validity, general topology editing, symbolic/inverse solving and arbitrary-model native qualification remain open.