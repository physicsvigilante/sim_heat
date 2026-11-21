# Windows H1 study loader · offline compatibility record

**Local result, 2026-11-21.** On Windows 11 build 26200 (AMD64), the loader at `7a31937e7676bb1927def52234f0e4232e7e36b9` admitted a nested study with a parent revision. It refused authored backslashes in both the model path and parent-study path. Only the internally computed relative path uses `as_posix()`. The test exercised the public `load_study` entry point. The source change and its regression are the complete delta from the reviewed N12 parent, `6904ec8219be0ddb8ec1635a9d000ddda80307c9`. The parent's independent review covered N12 F-01. Independent review of this Windows change is pending.

## Source identity and scope

| SHA-256 identity | Value |
| --- | --- |
| Historical N1 source manifest | `28e249bbda68fba3a511caede4dfdec8cd5254e3a02b5eda5025bba82dbb6766` |
| Loader pinned by that manifest | `0205d016a50f359a6d42e17117fb2908ff5916849c51d4fd5b0d3124b92eec69` |
| Windows loader tested | `04b5bea4fe93396d74912e102f59977201c500d8672de05ed4e78ce77fa6817f` |

All 18 read-only files and three original inputs matched the historical manifest on the reviewed parent. On the Windows candidate, 17 of 18 read-only files and all three inputs matched. The loader accounts for the sole difference. The historical plan checker refused the candidate with `source drift: h1/study.py`, as its original pin requires.

The Windows loader admitted the original T study from the nested `qualification/h1_n1/inputs` root and bound it to the original reference facts. The model and descriptor matched their pinned hashes, the model exposed 77 internal exports, and all eight public requests remained `not_computed`. This record covers offline path handling and source admission. The seven historical reference failures and eight native-readiness blockers remain open. No native operation was performed.

## Reproduce the scoped checks

Use the source commit above with original Git blob line endings, Windows CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0 and mpmath 1.3.0. From the checkout root, run `python -s -B -m unittest -v h1.tests.test_study_paths`. The following Python block verifies the recorded byte identities, source admission and historical refusal. Run it from the same checkout root.

```python
import hashlib
import json
from pathlib import Path
import subprocess

from h1.model import internal_exports
from h1.reference import read_reference
from h1.study import load_study
from h1.verification import bind_reference
from qualification.h1_n1.check_plan import check

parent = "6904ec8219be0ddb8ec1635a9d000ddda80307c9"
manifest = Path("qualification/h1_n1/SOURCE-PINS.json")
sha = lambda data: hashlib.sha256(data).hexdigest()
assert sha(manifest.read_bytes()) == "28e249bbda68fba3a511caede4dfdec8cd5254e3a02b5eda5025bba82dbb6766"
pins = json.loads(manifest.read_bytes())
for group, expected_changes in (("readonlySha256", ["h1/study.py"]), ("inputSha256", [])):
    changes = []
    for name, expected in pins[group].items():
        original = subprocess.check_output(["git", "cat-file", "blob", f"{parent}:{name}"])
        assert sha(original) == expected, name
        if sha(Path(name).read_bytes()) != expected:
            changes.append(name)
    assert changes == expected_changes, changes
assert sha(Path("h1/study.py").read_bytes()) == "04b5bea4fe93396d74912e102f59977201c500d8672de05ed4e78ce77fa6817f"

q = manifest.resolve().parent
study = load_study(q / "inputs/T/study.json", q / "inputs")
bind_reference(study, read_reference(q / "reference-facts.json"))
assert study.model_sha256 == pins["inputSha256"]["qualification/h1_n1/inputs/T/model.mo"]
assert study.sha256 == pins["inputSha256"]["qualification/h1_n1/inputs/T/study.json"]
assert len(list(internal_exports(study.model))) == 77
requests = study.request_report["requests"]
assert study.request_report["admitted"] and len(requests) == 8
assert all(item["status"] == "not_computed" for item in requests)
try:
    check()
except ValueError as exc:
    assert str(exc) == "source drift: h1/study.py", str(exc)
else:
    raise AssertionError("historical checker accepted a different loader")
```

## Full Windows suite

The 14 unittest invocations in [the inherited offline workflow](../../.github/workflows/h1-n12-triple-stage-ci.yml) ran with the versions above. Of 338 tests, 334 passed, one failed and three errored. The exact-head hosted CI for the reviewed parent is a separate Linux result.

| Remaining test | Windows observation |
| --- | --- |
| N1 `test_complete_current_plan_remains_nonexecuting` and `test_nearest_physical_witness_is_feasible_but_never_adopted` | Both reached the historical loader identity guard and errored. Both count against the full-suite result. |
| H1 `test_cli_check_synthetic_and_read_only` | The fixture writes CSV text with Windows newline translation after the receipt has hashed it. In a separate diagnostic, preserving the original CSV bytes at write time made the test pass. The unchanged test failed. |
| H1 `test_symlink_refused` | Windows returned error 1314 while creating the test symlink, including under the normal account outside the sandbox. The refusal assertion was unexercised on this host. |
