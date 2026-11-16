# TEACH_RING4 — first-submission author notes and bounded claim

**Author:** Chat A / GPT-6 in the source-development conversation, same workflow as the implementation author. This is **not an independent or blind H1-C1 author** and must never be counted as such.

**First captured task:** [TASK.md](TASK.md), committed as `a87d19308899b7f320d5d3632112f5b605d8f279` **before** creating `model.mo` and `study.json`. Task describes a four-body, one-boundary conductive cycle plus one diagonal cross-link; all parameters are illustrative, and only conduction principles relate it to source Illustration 135. It is not an unimplemented literal textbook problem.

**First physical authoring submission:**
- `h1/cases/TEACH_RING4/model.mo`: SHA-256 `3a4771b5e6254a72a2d96e8a432b5151db8af51c1ef1d49b9553bb0e9c56e5a8`.
- `h1/cases/TEACH_RING4/study.json`: SHA-256 `812e27fb83643d8ddf052181610f3d1353efbdef4e482a9374f263dd92b7f1fd`.
- `h1/reference_cases/TEACH_RING4.json`: SHA-256 `f5a7b10337cd62ff79ce77896b63135b71a2b2e39ee355ace46acf4ede55217b`, checking only; independently re-entered **by same Chat A author**, not by a separate independent reviewer.
- Model/study: **4 bodies, 1 boundary, 6 rods, 5 native ideal nodes, 15 public observation requests, 32 provenance records**. No contact geometry, rod heat capacity, extra physics laws, arbitrary equations or inferred conductivities.

## Local checks, not native results

The unchanged `python -B -m h1 h1/cases/TEACH_RING4/study.json --root h1/cases` admitted the physical composition and its complete public requests, returning `nativeExecuted=false` and all requested values `not_computed`. The generic `h1.reference.prepare` independently admitted separately entered reference facts and sealed a **checking-only** reference `30c6ea011bb7c2e0a2161e57733f7ce68876e4db23b62107bdedf0d925b350ec`.

The separate checking-only `experiments/teacher_ring4/independent_ode_check.py` builds four energy-balance ODEs directly from the frozen task and compares high-precision SciPy DOP853 with the original generic H1 reference at 7 declared times over 0–24000 s: maximum difference approximately **4.8e-10 K**. This is **analytical/reference preparation**, not OpenModelica, evidence of native accuracy, or arbitrary-case generality. The generic H1 reference predicts nonzero signed-flow reversals on four of the six rods; these are **predictions**, not yet native observations. No flow-zero instant is claimed between samples.

All baseline H1 production source and both viewer contracts remain unchanged. The sandbox runtime contains Python 3.13.5, NumPy 2.3.5 and SciPy 1.17.0; compiler `omc` is not installed in this local environment. A full local H1 test discovery in a CI source snapshot may fail due the intentionally absent `tools/h1_native_batch.py`; do not claim full H1 tests passed locally. GitHub full CI must independently run the test suite on the exact execution source.

## Teaching investigations without structural-engine edits

The teacher could change passive observation selection on **the same** `model.mo` (e.g. body B/D temperatures and `ringDA` flow only). This requires a separate study identity and saved evidence; it does not change physical facts.

One hypothetical conductivity experiment changes only `ringAB.k` (80.0→160.0 W/(m K)), preserving all other parameters, topology and initial conditions. A separately identified narrow `revision` study and new native evidence would be required; this has **not** been authored or run.

## Safety, scope, next gate

Use only the public `SimHeat.Body`, `RodArea`, `FixedTemperature` constructors, conserved ideal ports and original `h1` parser, MAT adapter, reference, numerical checker and batch runner. For native evidence, pin the existing OpenModelica 1.27.0 / MSL 4.0.0 / Python 3.13.5 environment with one build and at most one launch, no retries, fixed DASSL tolerance 1e-8 and 2000 saved output intervals. Inspect any refusal and preserve the failed attempt; do **not** change source physical parameters, solver tolerances or required observations to force acceptance.

**Development claim only:** successful first-attempt H1 admission of one new fixed 4-body conductive ring on an established grammar. Full native execution, viewer ingestion, educational usability and independent R2 review are future checks. Frozen H1-C1-F0 transfer experiment remains untouched.
