# Local authoring workbench for a supported thermal composition

**Scope:** a single-command, read-only inspection session for a separately authored H1 Modelica model and study descriptor. This is a **source-only preview**, not a solver, OpenModelica wrapper, upload service, numerical reference, source-authenticity attestation, or full natural-language-to-model engine. It is appropriate for an unfamiliar **combination of existing supported components**. A new physical law is still a library/review change, not an apparatus switch.

## One command after authoring the two files

From a trusted checkout of SIM_HEAT with its normal offline Python checking dependencies, and with `model.mo` and `study.json` already authored in a scratch case directory:

```sh
python -B -m tools.authoring_workbench /path/to/scratch/cases/newcase/study.json \
  --root /path/to/scratch/cases
```

The command validates the exact source through the existing `h1.study.load_study` / public-request admission and constructs the existing generic source-only preview. If admission is successful, it prints a JSON message containing `admitted: true`, `nativeExecuted: false`, source hashes and a temporary `http://127.0.0.1:<port>/viewer/source_preview/` URL. Open that URL in your browser; your **own admitted study** is shown immediately, without a manual JSON export or file import. Press Ctrl+C to stop the local session. Port `0` (the default) selects a free loopback port; `--port 8008` requests a fixed one. No installer, native compiler, server deployment or external network service is started by this command.

**Local privacy boundary:** Loopback means other processes on the same computer can still request the admitted in-memory source/provenance if they learn the session port. There is no authentication between local processes. Do not include secrets or sensitive personal information in authored models or provenance notes; avoid shared or untrusted computers, and press Ctrl+C to stop the session when finished. This workbench is not designed for public-server deployment.

The session runs **only on IPv4 loopback**. It exposes a fixed read-only set of the existing inspector's HTML/JavaScript assets and one **in-memory** source-only JSON response; it does **not** serve your raw `model.mo`, `study.json`, `.git` files, other repository sources or original native archives. It does not accept HTTP uploads, writes or commands. The existing inspector's internal default URL happens to be named `data/TEACH_SPLIT3.json`; in this isolated session that exact URL is a virtual alias for **your admitted study's payload**, which retains its own true `studyId`, source digests and `not_computed` requests. The default example is not secretly substituted for your model.

If the model SHA is stale, a quantity/port is unsupported, a public request is invalid or provenance is incomplete, the command **refuses before opening a listening socket**, prints an offline JSON diagnostic to stderr, returns exit code 2, and leaves the original files unchanged. Fix the scratch source with its real attribution and run the command again. No refused/old model is left as a valid default view in the same session. Browser imports are display-schema checked but **are not authenticated as trusted source**; for new drafts, restart this command against the authoritative study rather than importing arbitrary JSON.

## Reusable authoring request for an LLM

Provide the LLM with the physical question and any image, table or source locators **as data**. Ask it to produce only a *new scratch candidate* that satisfies this contract; the program, not the LLM, determines admissibility:

> Describe a new supported SIM_HEAT conduction composition using **only** `SimHeat.Body(m,c,T_initial)`, `SimHeat.RodArea(k,L,A)`, `SimHeat.RodCircular(k,L,d)` and `SimHeat.FixedTemperature(T)` connected through the declared thermal ports. Return the complete restricted Modelica `model.mo` and separate `sim_heat.study/1` `study.json`. Use a fresh study/model ID, explicit units, meaningful component names, all required positive scalar inputs, and fully connected rod endpoints. Do not invent equations, physical geometry or an unsupported component. Preserve exact source givens and locators; mark any values chosen for demonstration as `illustrative`, and record a truthful `@model` assumption about constant properties, uniform finite bodies and storage-free rods. List desired observations using only `temperature`, `temperatureDifference`, `heatFlow` and `energyChange`, and do **not** supply output readings. For a transient study include at least one Body and a valid H1 analysis grid; for a steady study use maintained boundaries/rods, no bodies, and an empty analysis object. State any ambiguity, missing dimensions or physics outside the supported domain rather than fabricating a value. Keep the two original authored files intact after admission. No native execution.

The H1 study schema requires `model.path` (normally `model.mo`) and the **SHA-256 of the exact model bytes**. Once the LLM has finished writing a fresh scratch model, compute its hash with a normal local hashing command and enter it in **that scratch descriptor only**. Do not repin archived models, frozen study submissions, original native evidence or historical C1 references. LLM statements about source fidelity are proposals, not verified facts; a human should inspect the actual text, units, connection topology and assumptions before trusting any model.

See the [current H1 authoring guide](AUTHORING.md) for a tested scratch-only admission/refusal walkthrough, supported units and requests. See [the existing admitted-source preview contract](ADMITTED_SOURCE_PREVIEW.md) for provenance, logical port semantics and result-status limits. The local workbench reuses **exactly the same H1 validator and source-view builder** as those commands, not an independently invented approximation or textbook solver.

## Teacher acceptance checklist

A teacher or independent reviewer should be able to (1) author a previously unlisted combination of supported components **without modifying the H1 engine or source viewer**, (2) inspect the component identities, typed source inputs, original attribution and `@model` assumptions, (3) read the logical connections without mistaking the schematic for geometry or heat-flow direction, (4) see every requested physical result as **`not_computed`**, and (5) observe useful refusal for a stale hash, invalid request or missing provenance. This is a reproducible offline acceptance exercise, **not evidence that a blind LLM or classroom has succeeded**.

It does not simulate temperatures, powers, equilibrium, heat flow, latent heat, radiation, fluid flow or mechanics. The six published historical native diagnostics remain `diagnostic_only/nativeQualified=false`. New native work requires a separately reviewed, bounded plan and **explicit owner authorization**; the workbench offers no native action or fallback. Historical C1 failures and frozen evidence are unchanged.
