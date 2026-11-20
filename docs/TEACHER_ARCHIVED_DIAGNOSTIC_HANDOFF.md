# Teacher T1-V2 — admitted source input → original recorded diagnostic

**Status:** candidate on a draft PR, not independently reviewed, not deployed.
**Risk:** R2 source/evidence presentation. This milestone does **not** modify a
physical equation, solver, native runner, old published MAT/CSV/JSON, original
source model/study, or previously accepted H1/N1–N8 contracts.

## Classroom experience

Use the preexisting original H1 cases with the *existing* local source-only
workbench:

```sh
python -B tools/authoring_workbench.py h1/cases/D2/study.json \
  --root h1/cases --compare h1/cases/D2_K2/study.json
```

The source inspector shows the independently H1-admitted **authored** `rod.k`
change from 100 to 200 W/(m K). This is still **not a computed result**.
If and only if these original, separately admitted model **and** study SHA-256
identities match a previously published source-linked diagnostic pair, the
workbench additionally offers an **"Open original saved temperature and
heat-flow histories"** link.

That link opens the existing, unchanged `viewer/network/compare.mjs` display,
operating on **the original two published native-case JSON files**. The
teacher can switch the observed quantity, use the synchronized slider at
saved actual time samples, see signed rod heat flow, body temperatures and
relative energy changes, and return to the original admitted source graph.
In the original saved D2/D2_K2 data, at 0 seconds the rod's saved signed
flows are +12 W and +24 W; at 468.75 seconds the saved cold-body temperatures
are approximately 296.468 K and 299.052 K. Those values are read from the
original archived native diagnostic JSON. They are **not** new predictions,
extrapolations, fresh OpenModelica runs, or independently certified references.

For any other source composition, reversed pair, absent data or internally
inconsistent published evidence, the workbench remains **source-only** and
explicitly reports **no matching published diagnostic**. No analytical
reference or stale native bundle substitutes for missing observations.

## Trust and authorability contract

1. The workbench admits **both original local Modelica+study files** under the
   caller's trusted H1 root and snapshots their source-only previews **before
   binding** its read-only loopback HTTP server.
2. The new bridge reuses the existing generic
   `viewer.network.tools.build_compare_index.compile_pair_index`: it validates
   the fixed original `compare_sources.json` manifest against source-model/
   study identities, the direct single-rod `k` revision, topology, analysis,
   requests, native-case schema, original SHA-256 indexed case bytes,
   and source-provenance tuple. The rebuilt compare index must exactly equal
   the committed index. The browser's existing `compareNativeCases` independently
   applies its own strict pair/case/row/checks at display time.
3. The bridge matches both **model and study SHA-256** for both original
   locally admitted cases to the one published pair, with the correct baseline/
   successor direction. It does not accept browser-imported preview JSON as a
   source for choosing or changing the recorded results.
4. The HTTP server allowlists ONLY the already published pair's two normalized
   diagnostic JSON case files, the necessary archived comparison JavaScript
   modules, one narrowed catalog/index and its compare HTML. No raw Modelica,
   MAT, CSV archive, other case JSON, browser-posted code, arbitrary path,
   external service, compiler operation or native-execution endpoint is served.
   Host, query/traversal, method, CSP and no-store restrictions are unchanged.
5. The source page's link is explicitly labeled **"original server-admitted
   pair only"**, even if the teacher later imports another source-only JSON
   in the browser. The link never follows or accredits that imported file and is hidden as
soon as a browser baseline/scenario import is selected (refresh to return
to the original server-admitted pair).
   Browser-imported JSON remains display-*schema* checked and is not
   authenticated against original source bytes or textbook provenance.
6. The old native-case JSON remains `diagnostic_only`, `nativeQualified=false`.
   Internal digests and metadata matches do **not** independently authenticate
   the GitHub host, Modelica source interpretation, new physical accuracy,
   full original H1-C1 grid, or any owner's signature. Historical source
   references and artifacts are preserved byte-for-byte.

**Composability criterion:** no special-case `if D2` branch is introduced.
The bridge matches a documented generic original H1 conductivity revision to a
previously source-linked published comparison. A new arrangement of supported
components is still an authoring task; it does **not** automatically gain
recorded native data unless separately authorized and independently checked.
An actual newly authored dynamic simulation remains a future, separately
qualified native-runner milestone.

## Acceptance and refusals

Unit tests require exact pair selection only for the original D2→D2_K2,
and explicit source-only outcomes for D1/S1, reverse/other pairs, altered
model/study SHA, and a tampered original pair-source manifest. The original
GET catalog lists exactly two case sources, and their served bytes must hash
to the original public SHA-256. A real browser test must visit the new link,
show +12/+24 W at the initial recorded time, sample the next **recorded**
instant, and display source-linked body temperatures and provenance while
refusing unallowlisted source/archive files, foreign Host and writes. Existing
original-source-only/negative tests and six archived diagnostic replay cases
must remain green. Failing any identity/archival gate hides the link without
preventing otherwise valid source-only admission.

This is a user-visible evidence-semantics change: it needs exact-head offline
and browser CI plus **independent R2 review** before acceptance. There is no
standing approval to execute OpenModelica or merge source PRs.
