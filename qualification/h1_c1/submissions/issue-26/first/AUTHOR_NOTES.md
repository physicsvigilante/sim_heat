# AUTHOR_NOTES.md — H1-C1 Stage 2 first physical submission

## Identity, frozen task and inputs

- Author: ChatGPT (self-identified GPT-6), continuing the Stage 1 ChatGPT-authored independent-author role. This is a declared role, not authenticated proof that the same underlying session/model instance persisted. The same LLM role selected the task and authored the model and study; no independent selector is claimed.
- Frozen original task: issue #26, Stage 1 author comment `6919450031` (`TASK.md — Two-buffer parallel thermal bridge with opposing initial and boundary gradients`). Its physical values, topology, assumptions and nine base observations are unchanged in this submission.
- Permitted author-facing references: `qualification/h1_c1/START_HERE.md` and `qualification/h1_c1/AUTHOR_CONTRACT.md`, both at published commit `ea954eee9b416498874419b9c8e5503f94821be8`, plus the original frozen Stage 1 `TASK.md`. The issue description and comment headers were used only to locate the frozen materials, not as physical modeling references. The evaluator's Stage 1 comment content was not read.

## Earlier exposure and roles

- Stage 1 already disclosed exposure in conversational summaries to prior SIM_HEAT H1 readiness/design/review activity, including PR #1/#2. That exposure persists, so this attempt is not claimed to be blind to the project or independent of all earlier review context. No implementation, tests, solved examples, or other project source were inspected for Stage 2.
- The task author and physical-model author are the same ChatGPT authoring role, not a separate selector. No external agent, implementation developer, reviewer, or evaluator wrote, corrected or suggested the model or the study in this Stage 2 attempt.

## Construction, assumptions and interpretive choices

- `model.mo` declares exactly two `SimHeat.Body` stores, two `SimHeat.FixedTemperature` boundaries, three `SimHeat.RodArea` conductors and one `SimHeat.RodCircular` conductor; eight explicit `connect` statements realize the task's H, L, R and C nodes. No independent junction store, contact resistance, added loss or temperature source was introduced.
- The `roundBridge.d=0.020` binding is a **diameter in metres**; no area or conductance is precomputed or supplied. All model numbers are original illustrative task givens in SI units, not intermediate solved values.
- Signed rod flows in the requested study are interpreted from `port_a` to `port_b`: hot bath to left buffer, left to right for both bridges, and right buffer to cold bath. `temperatureDifference` is left minus right. Each body's `energyChange` is relative to its own initial state.
- The adopted physical regime is constant-property, internally uniform stores and storage-free rods, ideal connections, insulated exterior and perfectly fixed bath temperatures. This is a modeling assumption, not a conclusion verified by the engine.
- No calculated answer key, crossing time, monotonicity or numerical flow prediction is asserted. A temperature equality or bridge-flow reversal is an observation question, not a preset event or constraint.

## Study settings, exact bytes and tool disclosure

- Base observation requests: the nine items in the frozen `TASK.md` section 5, represented using only the public temperature, heat-flow, temperature-difference and energy-change operations.
- **Provisional** analysis only: `startTime=0`, `stopTime=1800` s, `intervals=3600`, `solver=dassl`, `tolerance=1e-8`. The 1800 s window comes from the task's provisional classroom window. The evaluator must set the C1 modal horizon and output resolution before native execution; a change to these settings changes `study.json` identity, not frozen physical facts.
- Exact `model.mo` bytes: UTF-8 without BOM; LF (`\n`) line endings; one final LF; no leading empty line. SHA-256 of those exact bytes: `9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435`. `study.json` and `AUTHOR_NOTES.md` are likewise UTF-8 without BOM, LF line endings and a final LF. Each file is presented literally in its own fenced code block in this issue comment; code fences and file headings are not part of file bytes.
- Tools/assistance: connected GitHub tools to read the permitted task and two public documents and post this Stage 2 comment; Python standard library text/JSON serialization and `hashlib.sha256` for mechanical file construction/hash computation. These tools did not supply or critique physical content. No external assistant, evaluator, project validator, Modelica compiler, OpenModelica run, simulation, CI execution, or feedback-based correction was used.
- Chronology: Stage 1 `TASK.md` was frozen in issue comment `6919450031` before Stage 2. This is the first `model.mo` and `study.json` drafted for that frozen task. No attempted engine validation, refusal, correction cycle, or revised physical task occurred. The Stage 2 submission is an unexecuted first attempt, not a pass claim.

## Proposed alternative observation set — not submitted or executed

For the **same unmodified model.mo**, a focused boundary-and-storage comparison could request:

1. `temperature` at `hotBath.port`.
2. `temperature` at `coldBath.port`.
3. `heatFlow` at `hotLead`.
4. `heatFlow` at `coldLead`.
5. `energyChange` at `leftBuffer`.
6. `energyChange` at `rightBuffer`.

A teacher could compare whether the ideal bath temperatures stay fixed while their leads exchange signed heat and both finite stores change energy. This would require a distinct study identity and execution; it is **only a proposal**, with no computed outcomes or altered current requests.

## Hypothetical one-rod conductivity revision — not submitted or executed

In a future, separate physical revision **only**, change `roundBridge.k` from `50` to `100` W/(m K). Keep its diameter and length, all other component values, model names, topology and connections unchanged. A teacher could compare the two bridge-flow traces, the buffers' transient temperature histories and any sign reversal against the unchanged baseline, distinguishing the changed branch's conductance from the common endpoint temperature difference. This is not a second model or study, not a claim that any particular crossing occurs, and not evidence that a general structural-editing feature exists. No parent hashes or revision record are invented before actual separate files exist.

## Uncertainties and stop boundary

The files have **not** been validated or run. Numerical admissibility, solver behavior, simulation horizon suitability, equality/reversal occurrence and classroom effectiveness remain for the independent evaluator. No engine feedback was consulted and no implementation files were changed. Stop after this first Stage 2 issue-comment submission.
