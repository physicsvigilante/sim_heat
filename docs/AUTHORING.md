# Author a supported thermal model

Current, source-backed guide for the read-only H1 admission path. This guide covers drafting and checking input, not running OpenModelica. It does not complete an unfamiliar author-to-native transfer, establish source fidelity, or qualify numerical results. See the [capability registry](CAPABILITIES.md) for the distinction between admission, analytical checking data and archived native diagnostics.

The [historical H1 foundation contract](H1_IMPLEMENTATION_CONTRACT.md) retains its original proposed-contract header. It is a design/history record, not a current implementation-status page or execution authorization. The [offline amendment](H1_OFFLINE_AMENDMENT.md) is also a dated record. Current behavior described here is checked against [the CLI](../h1/__main__.py), [study admission](../h1/study.py), [model and observation admission](../h1/model.py) and [analysis policy](../h1/policy.py).

## Start with an isolated draft

Use a checkout of the repository and the project's Python 3.13.5 checking environment. The [pinned checking dependencies](../requirements-h1-ci.txt) support offline checks; they are not an OpenModelica installation. Run commands from the repository root. No native tool is required for the walkthrough below. Do not edit original examples, archived studies, frozen references or historical execution plans to make a draft pass.

A draft has two UTF-8 files: a restricted Modelica file describing components and connections, and a study JSON file describing identity, mode, analysis, provenance and requested observations. The model is authoritative; the descriptor does not override physical parameters. The descriptor's model SHA-256 must match the exact model bytes, including line endings.

For an existing unmodified example, run:

```sh
python -B -m h1 h1/cases/D1/study.json --root h1/cases
```

A successful admission has exit code 0, `stage: offline_validation`, `admitted: true` and `nativeExecuted: false`. Every admitted public request remains `not_computed`; its unit is a declared interface, not a measured or simulated value. Topology and internal-export names are source-derived descriptions. The scaled junction condition is an admission preflight, not a temperature solution.

## Walk through an edit and two refusals

Save the following Python block as a temporary script outside the tracked source and run it from the repository root with `python -B /path/to/your-script.py`. It makes an isolated temporary copy of [D1's model](../h1/cases/D1/model.mo) and [study](../h1/cases/D1/study.json), changes the body initial temperature to an explicitly illustrative 298.15 K, and demonstrates a stale-hash refusal before refreshing only that new draft's model digest. It then demonstrates an unknown observation target. The temporary directory is removed on completion, including failures. No original file is overwritten.

This is an editing/admission exercise using an existing composition, not a new physical law, native experiment, held-out authoring test or computed answer. The code block itself is executed by the documentation regression tests; expected outcomes must agree with the real CLI.

```python
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

root = Path.cwd()
original = root / "h1/cases/D1"

with TemporaryDirectory(prefix="simheat-authoring-") as temporary:
    draft = Path(temporary).resolve(strict=True)
    model_path = draft / "model.mo"
    study_path = draft / "study.json"
    model_path.write_bytes((original / "model.mo").read_bytes())
    study_path.write_bytes((original / "study.json").read_bytes())

    def admit():
        run = subprocess.run(
            [sys.executable, "-B", "-m", "h1", str(study_path),
             "--root", str(draft)],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        result = json.loads(run.stdout)
        assert result["stage"] == "offline_validation"
        assert result["nativeExecuted"] is False
        return run.returncode, result

    code, result = admit()
    assert code == 0 and result["admitted"] is True, result

    text = model_path.read_text(encoding="utf-8")
    assert "T_initial=293.15" in text
    text = text.replace("H1_D1", "TeacherDraft")
    text = text.replace("T_initial=293.15", "T_initial=298.15")
    model_path.write_text(text, encoding="utf-8")
    code, result = admit()
    assert code == 2 and result["code"] == "identity"
    print("PASS: edited model with stale digest refused")

    study = json.loads(study_path.read_text(encoding="utf-8"))
    study["id"] = "TeacherDraft"
    study["model"]["sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    for record in study["provenance"]:
        if record["target"] == "body.T_initial":
            record.update(kind="illustrative", locator="authoring walkthrough",
                          note="Chosen 298.15 K for this scratch draft, not a textbook given.")
    study_path.write_text(json.dumps(study, indent=2) + "\n", encoding="utf-8")
    code, result = admit()
    assert code == 0 and result["admitted"] is True, result
    assert all(item["status"] == "not_computed" for item in result["requests"])
    print("PASS: attributed scratch edit admitted; all readings not_computed")

    study["requests"][0]["target"] = "missing.port"
    study_path.write_text(json.dumps(study, indent=2) + "\n", encoding="utf-8")
    code, result = admit()
    assert code == 2 and result["admitted"] is False
    assert result["requests"][0]["code"] == "unknown_observation_target"
    print("PASS: unknown observation refused; no native execution")
```

Only a newly authored disposable draft is repinned here. Updating a draft digest neither authenticates its source nor repairs a frozen submission, archived native record, parent revision, or native execution plan. Reusing D1's archived results after changing its model would be invalid.

## Inspect the admitted composition before any native run

The independently reviewed [generic H1 source-only inspector](../viewer/source_preview/index.html) is distinct from the six-case archived-results explorer. It can display source facts and topology for unfamiliar **supported combinations** without editing its core viewer code. In the current source repository, the [TEACH_SPLIT3 task](../experiments/teacher_split3/TASK.md) demonstrates three bodies, two maintained boundaries, seven conducting rods and an ideal junction. This developer-authored illustrative task is **not** a held-out teacher trial or a native result.

After a successful offline admission, produce a read-only source payload using the current [source-preview CLI](../h1/source_preview.py):

```sh
python -B -m h1.source_preview h1/cases/TEACH_SPLIT3/study.json --root h1/cases --out /tmp/teach-split3-source.json
```

Then serve the repository root using `python -m http.server 8000 --bind 127.0.0.1`, open `http://127.0.0.1:8000/viewer/source_preview/`, and select the generated JSON with the local file picker. The default example already displays the published source-only TEACH_SPLIT3 payload. The generator refuses nonadmitted studies and refuses writing over authored case files. Imported JSON is checked for display consistency, **not** authenticated against Modelica/source custody. Source-input initial temperatures are not predicted trajectories. Every physical request remains `not_computed`; no solver is invoked, no heat powers or final temperatures are supplied, and graph layout is not apparatus geometry. Read the [source-preview scope](../docs/ADMITTED_SOURCE_PREVIEW.md) for limits.

## Describe supported components and connections

The supported constructors and mandatory physical fields are:

| Constructor | Required fields | Thermal ports |
|---|---|---|
| `SimHeat.Body` | `m`, `c`, `T_initial` | `port` |
| `SimHeat.RodArea` | `k`, `L`, `A` | `port_a`, `port_b` |
| `SimHeat.RodCircular` | `k`, `L`, `d` | `port_a`, `port_b` |
| `SimHeat.FixedTemperature` | `T` | `port` |

Use the SI quantities represented by these slots: kg, J/(kg K), K, W/(m K), m and square metres as applicable. Values must be finite and positive after conversion. The admitted language supports typed scalar parameters, supported conversion functions and `connect` statements; it is not unrestricted Modelica and does not accept arbitrary equations, algorithms or expressions. Read [the current parser](../h1/model.py) before extending a draft beyond the demonstrated syntax.

Rods must have both endpoints connected. A single ideal node cannot contain multiple body/boundary owners; connect such owners through rods rather than directly identifying their ports. A transient study requires a body. A steady study requires rods and boundaries, contains no bodies, and has an empty analysis object. Existing [S1](../h1/cases/S1/study.json) demonstrates the steady descriptor. Component, topology and numerical-conditioning limits are enforced by admission; a syntactically valid connection is not necessarily a supported system.

## Request observations without supplying answers

The current public request schema is:

| Operation | Fields besides a unique `id` and `op` | Valid target |
|---|---|---|
| `temperature` | `target` | Existing thermal port, for example `body.port` |
| `temperatureDifference` | `a`, `b` | Two existing thermal ports, in the authored order |
| `heatFlow` | `target` | Rod component name, for example `rod` |
| `energyChange` | `target` | Body component name, for example `body` |

Do not supply expected numerical answers in the requests. One refused request refuses the investigation; the report can retain per-request reasons rather than a single top-level error. An invented operation or a physically incompatible target is refused, even when other requests are valid. Internal export names are not additional public request operations.

## Record assumptions and analysis settings

Every effective physical slot needs an attributable provenance record, directly or through a parameter dependency. Each record has `target`, `kind`, `locator` and `note`. Use truthful source locations; illustrative choices must be labeled `illustrative`. The `@model` regime record requires an `adopted_assumption` or `solution_assumption`. The parser checks these links and allowed kinds, not whether the text faithfully interprets a textbook or diagram.

Transient analysis currently requires `startTime` zero, finite `stopTime` from 0.000001 to 10000000 seconds, an even integer `intervals` from 1000 to 20000, `solver` equal to `dassl`, and `tolerance` equal to 1e-8 or 1e-10. These are descriptor-admission bounds, not permission to run those settings or evidence of accuracy. The separate frozen C1 budget and qualification conditions are not expanded by this guide. Preserve historical/reference tolerances rather than loosening them to pass a check.

A declared hypothetical conductivity revision has additional parent-source hashes and structural checks. Do not create such a relationship merely by changing an ID or copying archived provenance. Follow the existing [D2_K2 descriptor](../h1/cases/D2_K2/study.json) and [revision implementation](../h1/study.py); the walkthrough above creates a standalone scratch draft, not a qualified revision pair.

## Understand a refusal

| Report location or code | What to inspect |
|---|---|
| `identity` | The draft's model bytes and its recorded SHA-256; never repin an old native plan to bypass this. |
| `descriptor`, `path` | Required JSON fields, finite numbers, duplicate keys, UTF-8 and allowed paths; keep the model inside the study directory. |
| `syntax`, `parameters`, `units` | Supported constructors, mandatory fields, scalar bindings and compatible quantities. |
| `connection`, `unsupported_topology`, `underdetermined` | Named ports, required endpoints, owners and floating conductor networks. |
| Per-request `unknown_observation_target` or `unsupported_observation` | The operation and full referenced port/component, not just its first word. |
| `provenance`, `analysis`, `numerical_domain` | Attributions, regime assumptions, admissible settings and numerical preflight. |

Read the actual `reason` and any `requests` entries. Do not relabel a refusal as a solver failure: no solver has been run by this command.

## Stop before new native execution

An admitted draft does not yet have simulated values or an archive suitable for the existing result explorer. The complete unfamiliar-model source-view/native-result path is unfinished. Keep source drafts separate from archived-native displays; never substitute analytical references or made-up values for missing native output.

Before a new native attempt, a separately reviewed bounded plan must cover source/reference custody, the actual host/toolchain, permitted operations and attempt budget, followed by explicit owner authorization. This guide does not install or invoke OpenModelica, generate or adopt a checking reference, alter historical C1 failures, or grant native permission. Existing six-case playback remains available through the [thermal explorer](../viewer/network/index.html).
