"""Run live H1-N1 plan and negative-control verification on main without mutating historical pins."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "f52613c39c539b2d4543a9838e5658d526fca10e"
BASELINE_TREE = "0c44961b473d23737b0c9f3b3f2cd3db65b9f264"
SOURCE_PINS_SHA256 = "28e249bbda68fba3a511caede4dfdec8cd5254e3a02b5eda5025bba82dbb6766"
HISTORICAL_DRIFT_ONLY = "AGENTS.md"
STUDY_REL = "h1/study.py"
HISTORICAL_DRIFT_EXEMPT = ("AGENTS.md", "h1/study.py")
AUTHORIZED_STUDY_OLD_LINE = b"        relative = str(path.absolute().relative_to(root))\n"
AUTHORIZED_STUDY_NEW_LINE = b"        relative = path.absolute().relative_to(root).as_posix()\n"
EXPECTED_100X_FAILURES = ["T02.G", "T06.A", "T06.G", "T07.G", "T08.G", "T10.G", "T_Plug.C"]


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _copy_safe(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _historical_file_bytes(repo_root: Path, commit: str, rel: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{commit}:{rel}"],
        capture_output=True, check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"cannot read historical {rel} at {commit}: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def _historical_agents_bytes(repo_root: Path, commit: str) -> bytes:
    return _historical_file_bytes(repo_root, commit, HISTORICAL_DRIFT_ONLY)


def prepare_stage(
    root: Path,
    stage: Path,
    pins: dict,
    *,
    historical_agents: bytes,
    historical_study: bytes,
) -> Path:
    """Materialize the N1 stage with live plan/non-exempt files and pinned historical exempt bytes."""
    root = Path(root).resolve()
    stage = Path(stage).resolve()
    n1_dir = root / "qualification" / "h1_n1"
    # Stage the LIVE h1 package and LIVE qualification/h1_n1 directory so any
    # candidate edit to plan.json, check_plan.py, reference-facts.json, inputs,
    # or tests is exercised directly.
    shutil.copytree(root / "h1", stage / "h1")
    shutil.copytree(n1_dir, stage / "qualification" / "h1_n1")
    # Copy all other live readonlySha256 files (docs, experiments, h1_c1, tools).
    for rel in pins["readonlySha256"]:
        if rel in HISTORICAL_DRIFT_EXEMPT:
            continue
        dst = stage / rel
        if not dst.exists():
            _copy_safe(root / rel, dst)
    # Materialize ONLY the verified frozen historical exempt files at baselineCommit.
    # Overwriting stage/h1/study.py after copytree preserves N1's exact pinned execution.
    (stage / HISTORICAL_DRIFT_ONLY).write_bytes(historical_agents)
    (stage / STUDY_REL).write_bytes(historical_study)

    # Ensure qualification is importable as a package inside the staged root.
    for pkg in (stage / "qualification", stage / "qualification" / "h1_n1"):
        init = pkg / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
    return stage


def assert_plan_invariants(report: dict) -> None:
    if report.get("planStructuralChecks") != "PASS" or report.get("referenceFactsBinding") != "PASS":
        raise ValueError("N1 plan structural or reference-facts check failed")
    if report.get("nativeExecuted") is not False or report.get("nativeQualified") is not False:
        raise ValueError("N1 plan must remain non-executed and non-qualified")
    if report.get("nativeExecutionReady") is not False or report.get("referenceAccuracyCertified") is not False:
        raise ValueError("N1 plan must not claim native readiness or certified accuracy")
    if report.get("nativeCallsThisCheck") != 0 or len(report.get("executionBlockers", ())) != 8:
        raise ValueError("N1 plan execution blockers or native call budget violated")
    arith = report.get("constantArithmetic", {})
    if arith.get("arithmeticGate") != "REFUSED_UNCHANGED_CHECKING_CENTRES":
        raise ValueError("N1 constant arithmetic gate weakened")
    if arith.get("staticExports") != 14 or arith.get("physical100xFailures") != EXPECTED_100X_FAILURES:
        raise ValueError("N1 constant arithmetic physical-100x refusal inventory changed")
    if not all(row.get("witnessAdopted") is False and row.get("nativeObserved") is False
               for row in arith.get("rows", ())):
        raise ValueError("N1 constant arithmetic rows must remain unadopted and unobserved")


def verify(root: Path = ROOT, *, run_tests: bool = False,
           agents_bytes: bytes | None = None, study_bytes: bytes | None = None,
           out: Path | None = None) -> dict:
    root = Path(root).resolve()
    n1_dir = root / "qualification" / "h1_n1"
    pins_path = n1_dir / "SOURCE-PINS.json"
    if pins_path.is_symlink() or not pins_path.resolve().is_relative_to(root) or not pins_path.is_file():
        raise ValueError("missing or unsafe N1 SOURCE-PINS.json")
    pins_bytes = pins_path.read_bytes()
    if _sha256_bytes(pins_bytes) != SOURCE_PINS_SHA256:
        raise ValueError("source drift: qualification/h1_n1/SOURCE-PINS.json")
    pins = json.loads(pins_bytes.decode("utf-8"))
    if pins.get("baselineCommit") != BASELINE_COMMIT or pins.get("baselineTree") != BASELINE_TREE:
        raise ValueError("N1 SOURCE-PINS.json baseline commit or tree drifted")

    # Verify every live pinned file except the explicit historical-drift exemption tuple.
    for section in ("readonlySha256", "inputSha256"):
        for rel, expected in pins[section].items():
            if section == "readonlySha256" and rel in HISTORICAL_DRIFT_EXEMPT:
                continue
            path = root / rel
            if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
                raise ValueError(f"missing or unsafe pinned file: {rel}")
            if _sha256_bytes(path.read_bytes()) != expected:
                raise ValueError(f"source drift: {rel}")

    # Attest frozen historical AGENTS.md at baselineCommit (no live check).
    historical_agents = agents_bytes if agents_bytes is not None else _historical_agents_bytes(root, BASELINE_COMMIT)
    expected_agents = pins["readonlySha256"][HISTORICAL_DRIFT_ONLY]
    if _sha256_bytes(historical_agents) != expected_agents:
        raise ValueError(f"historical {HISTORICAL_DRIFT_ONLY} at {BASELINE_COMMIT} does not match SOURCE-PINS.json")

    # Attest frozen historical h1/study.py at baselineCommit AND enforce bounded live F-06 delta.
    historical_study = (
        study_bytes if study_bytes is not None else _historical_file_bytes(root, BASELINE_COMMIT, STUDY_REL)
    )
    expected_study = pins["readonlySha256"][STUDY_REL]
    if _sha256_bytes(historical_study) != expected_study:
        raise ValueError(f"historical {STUDY_REL} at {BASELINE_COMMIT} does not match SOURCE-PINS.json")

    if historical_study.count(AUTHORIZED_STUDY_OLD_LINE) != 1:
        raise ValueError(f"historical {STUDY_REL} does not contain unique authorized F-06 target line")
    expected_live_study = historical_study.replace(AUTHORIZED_STUDY_OLD_LINE, AUTHORIZED_STUDY_NEW_LINE, 1)
    live_study_path = root / STUDY_REL
    if live_study_path.is_symlink() or not live_study_path.resolve().is_relative_to(root) or not live_study_path.is_file():
        raise ValueError(f"missing or unsafe pinned file: {STUDY_REL}")
    live_study_sha = _sha256_bytes(live_study_path.read_bytes())
    expected_live_study_sha = _sha256_bytes(expected_live_study)
    live_study_matches_delta = live_study_sha == expected_live_study_sha
    if not live_study_matches_delta:
        raise ValueError("source drift: h1/study.py beyond the authorized F-06 delta")
    live_study_differs_from_pin = live_study_sha != expected_study

    with tempfile.TemporaryDirectory() as tmp:
        stage = prepare_stage(
            root,
            Path(tmp),
            pins,
            historical_agents=historical_agents,
            historical_study=historical_study,
        )

        # Execute the LIVE staged qualification/h1_n1/check_plan.py CLI in a clean subprocess.
        env = os.environ | {"PYTHONPATH": str(stage)}
        plan_out = stage / "plan-check.json"
        check_proc = subprocess.run(
            [sys.executable, "-B", str(stage / "qualification" / "h1_n1" / "check_plan.py"),
             "--out", str(plan_out)],
            cwd=stage, env=env, capture_output=True, text=True, check=False,
        )
        if check_proc.returncode != 0:
            detail = (check_proc.stderr or check_proc.stdout).strip()
            raise ValueError(f"staged qualification/h1_n1/check_plan.py failed: {detail}")
        report = json.loads(plan_out.read_text(encoding="utf-8"))
        assert_plan_invariants(report)

        if run_tests:
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "discover",
                 "-s", str(stage / "qualification" / "h1_n1" / "tests"), "-v"],
                cwd=stage, env=env, check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"staged qualification/h1_n1/tests failed with exit code {proc.returncode}")

    report["maintenanceVerification"] = {
        "schema": "sim_heat.h1_n1_plan_maintenance/1",
        "sourcePinsManifestSha256Verified": SOURCE_PINS_SHA256,
        # Legacy compatibility key retained alongside historicalPinnedFiles.
        "historicalPinnedFile": HISTORICAL_DRIFT_ONLY,
        "historicalPinnedFiles": list(HISTORICAL_DRIFT_EXEMPT),
        "historicalBaselineCommit": BASELINE_COMMIT,
        "historicalAgentsSha256Verified": expected_agents,
        "historicalStudySha256Verified": expected_study,
        "liveStudySha256": live_study_sha,
        "liveStudyMatchesAuthorizedDelta": live_study_matches_delta,
        "liveStudyDiffersFromPin": live_study_differs_from_pin,
        # Legacy compatibility key retained for existing callers; covers all non-exempt live pins.
        "livePlanAndNonAgentsPinsVerified": True,
        "stagedTestsExecuted": run_tests,
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    result = verify(args.root, run_tests=args.run_tests, out=args.out)
    print(json.dumps(result, indent=2))
