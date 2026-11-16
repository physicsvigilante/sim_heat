#!/usr/bin/env python3
"""Capture *actual* V2 numerical runtime/BLAS and wheel provenance, offline only.

Only selected public runner metadata is collected: no secrets or full environment.
All values are evidence, not an OpenModelica or native verification.
"""
import contextlib
import hashlib
import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import sys

import mpmath
import numpy
import scipy
import scipy.linalg  # Load the numerical backend before threadpool inspection.
import threadpoolctl


def digest(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def selected_os_release():
    path = Path("/etc/os-release")
    if not path.is_file():
        return None
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k in ("ID", "VERSION_ID", "PRETTY_NAME", "VERSION_CODENAME"):
            entries[k] = v.strip('"')
    return entries


def cpu_summary():
    first = {}
    path = Path("/proc/cpuinfo")
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                break
            if ":" not in line:
                continue
            k, v = (x.strip() for x in line.split(":", 1))
            if k in ("vendor_id", "model name", "cpu family", "model",
                     "stepping", "flags", "Features", "microcode"):
                first[k] = v
    return first


def package(name):
    dist = metadata.distribution(name)
    wheel = dist.read_text("WHEEL")
    record = dist.read_text("RECORD")
    if not wheel or not record:
        raise RuntimeError("Missing installed wheel provenance: " + name)
    tags = re.findall(r"(?m)^Tag: (.*)$", wheel)
    if not tags:
        raise RuntimeError("No wheel tag present: " + name)
    return {
        "name": name,
        "version": dist.version,
        "wheelTags": tags,
        "wheelMetadataSha256": digest(wheel),
        "installedRecordSha256": digest(record),
        "installationRoot": str(dist.locate_file("")),
    }


def run():
    if not __debug__:
        raise RuntimeError("Optimized Python invalidates checking assertions")
    capture = io.StringIO()
    numpy_config = io.StringIO()
    scipy_config = io.StringIO()
    with contextlib.redirect_stdout(capture):
        numpy.show_runtime()  # Prints: does NOT return usable provenance.
    with contextlib.redirect_stdout(numpy_config):
        numpy.show_config()
    with contextlib.redirect_stdout(scipy_config):
        scipy.show_config()
    info = threadpoolctl.threadpool_info()  # Actual loaded libraries.
    if not info or not any(x.get("user_api") == "blas" for x in info):
        raise RuntimeError("Actual BLAS/threadpool libraries unavailable")
    runner = {k: os.environ.get(k, "") for k in (
        "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion", "RUNNER_ENVIRONMENT")}
    data = {
        "schema": "sim_heat.c1_v2_runtime_provenance/1",
        "stage": "offline_checking_only_no_native",
        "runner": runner,
        "python": platform.python_version(),
        "pythonImplementation": platform.python_implementation(),
        "pythonCompiler": platform.python_compiler(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "system": platform.system(),
        "release": platform.release(),
        "osRelease": selected_os_release(),
        "cpu": cpu_summary(),
        "processor": platform.processor(),
        "logicalCpus": os.cpu_count(),
        "numpyVersion": numpy.__version__,
        "scipyVersion": scipy.__version__,
        "mpmathVersion": mpmath.__version__,
        "threadpoolctlVersion": threadpoolctl.__version__,
        "actualLoadedThreadpoolLibraries": info,
        "numpyShowRuntimeStdout": capture.getvalue(),
        "numpyBuildConfigStdout": numpy_config.getvalue(),
        "scipyBuildConfigStdout": scipy_config.getvalue(),
        "installedWheels": [package(p) for p in
                             ("numpy", "scipy", "mpmath", "threadpoolctl")],
        "limitations": [
            "wheel tags/installed RECORD digests plus a separate wheel archive SHA manifest are retained",
            "this report is runtime attestation only, not independent reference certification",
            "runner metadata is a hosted image claim, not authenticated physical host identity",
            "all analysis remains offline; no OpenModelica invoked",
        ],
    }
    return data


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ...capture_v2_runtime output.json")
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        f.write(json.dumps(run(), sort_keys=True, indent=2, allow_nan=False) + "\n")
    print("Recorded actual loaded BLAS/threadpool, build config, CPU, OS image, and wheel tags")
