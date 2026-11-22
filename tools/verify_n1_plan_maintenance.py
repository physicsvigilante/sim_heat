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
EXPECTED_100X_FAILURES = ["T02.G", "T06.A", "T06.G", "T07.G", "T08.G", "T10.G", "T_Plug.C"]


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _copy_safe(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _historical_agents_bytes(repo_root: Path, commit: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{commit}:{HISTORICAL_DRIFT_ONLY}"],
        capture_output=True, check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"cannot read historical {HISTORICAL_DRIFT_ONLY} at {commit}: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


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
           agents_bytes: bytes | None = None, out: Path | None = None) -> dict:
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

    # Verify every live pinned file except the intentionally updated historical AGENTS.md.
    for section in ("readonlySha256", "inputSha256"):
        for rel, expected in pins[section].items():
            if section == "readonlySha256" and rel == HISTORICAL_DRIFT_ONLY:
                continue
            path = root / rel
            if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
                raise ValueError(f"missing or unsafe pinned file: {rel}")
            if _sha256_bytes(path.read_bytes()) != expected:
                raise ValueError(f"source drift: {rel}")

    # Attest the frozen historical AGENTS.md at the pinned baseline commit without rewriting pins.
    historical_agents = agents_bytes if agents_bytes is not None else _historical_agents_bytes(root, BASELINE_COMMIT)
    expected_agents = pins["readonlySha256"][HISTORICAL_DRIFT_ONLY]
    if _sha256_bytes(historical_agents) != expected_agents:
        raise ValueError(f"historical {HISTORICAL_DRIFT_ONLY} at {BASELINE_COMMIT} does not match SOURCE-PINS.json")

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        # Stage the LIVE h1 package and LIVE qualification/h1_n1 directory so any
        # candidate edit to plan.json, check_plan.py, reference-facts.json, inputs,
        # or tests is exercised directly.
        shutil.copytree(root / "h1", stage / "h1")
        shutil.copytree(n1_dir, stage / "qualification" / "h1_n1")
        # Copy all other live readonlySha256 files (docs, experiments, h1_c1, tools).
        for rel in pins["readonlySha256"]:
            if rel == HISTORICAL_DRIFT_ONLY:
                continue
            dst = stage / rel
            if not dst.exists():
                _copy_safe(root / rel, dst)
        # Materialize ONLY the verified frozen historical AGENTS.md at baselineCommit.
        (stage / HISTORICAL_DRIFT_ONLY).write_bytes(historical_agents)

        # Ensure qualification is importable as a package inside the staged root.
        for pkg in (stage / "qualification", stage / "qualification" / "h1_n1"):
            init = pkg / "__init__.py"
            if not init.exists():
                init.write_text("", encoding="utf-8")

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
        "historicalPinnedFile": HISTORICAL_DRIFT_ONLY,
        "historicalBaselineCommit": BASELINE_COMMIT,
        "historicalAgentsSha256Verified": expected_agents,
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
