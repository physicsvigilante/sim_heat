"""Local loopback HTTP server for the M05 interactive calorimetry & critical-radius vessel lesson.

Exposes a thin, strictly loopback (127.0.0.1) API that delegates 100% of equation derivation and
certified physics solving directly to ``simheat.system`` (zero physics in JavaScript, zero
OpenModelica execution, zero file writes, zero arbitrary filesystem reads over HTTP).
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from simheat.system import (
    THERMAL_SYSTEM_SCHEMA,
    describe_equations,
    solve_system,
)
from tools.offline_provenance import OFFLINE_FLAG_KEYS

LESSON_DIR = ROOT / "viewer" / "lesson"
MAX_POST_BYTES = 262144  # 256 KiB hard ceiling on incoming JSON payloads
MAX_HTTP_JOIN_DEPTH = 32
MAX_HTTP_SWEEPS = 1000
MAX_HTTP_EVENTS = 64
FORBIDDEN_HTTP_CONDUCTION_KINDS = frozenset({"h1_study", "derived_law_ref"})

CSP_HEADER = (
    "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
    "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)


def build_presets() -> list[dict[str, Any]]:
    """Return curated JEE interactive lesson presets (canonical sim_heat.thermal_system/1)."""
    return [
        {
            "key": "calorimeter_joined",
            "title": "Lesson 1 · Coupled Hot-Block + Subcooled Ice Calorimeter (Joined Law)",
            "category": "calorimetry",
            "summary": (
                "Hot copper block + brass calorimeter cup joined through a conduction bridge to "
                "subcooled ice. Watch certified solid -> melting plateau -> liquid continuation "
                "over a Schur-complement joined DerivedLaw."
            ),
            "controls": [
                {
                    "id": "hot_T0",
                    "label": "Hot block T_0 (K)",
                    "path": ["attachments", "left.hot_block", "initialTemperatureK"],
                    "min": 310,
                    "max": 520,
                    "step": 5,
                },
                {
                    "id": "ice_mass",
                    "label": "Ice mass (kg)",
                    "path": ["attachments", "right.ice_sample", "initialSolidKg"],
                    "min": 0.05,
                    "max": 0.4,
                    "step": 0.01,
                },
                {
                    "id": "ice_T0",
                    "label": "Ice initial T_0 (K)",
                    "path": ["attachments", "right.ice_sample", "initialTemperatureK"],
                    "min": 240,
                    "max": 273.15,
                    "step": 1,
                },
                {
                    "id": "duration",
                    "label": "Horizon duration (s)",
                    "path": ["solve", "durationS"],
                    "min": 60,
                    "max": 1200,
                    "step": 30,
                },
            ],
            "system": {
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "lesson_calorimeter_joined",
                "conduction": {
                    "kind": "join",
                    "left": {
                        "kind": "rods",
                        "nodes": ["hot_block", "calorimeter", "bridge"],
                        "terminals": ["hot_block", "calorimeter", "bridge"],
                        "rods": {
                            "block_to_cal": {"kind": "rod_area", "a": "hot_block", "b": "calorimeter", "k": "25", "L": "0.1", "A": "0.01"},
                            "cal_to_bridge": {"kind": "rod_area", "a": "calorimeter", "b": "bridge", "k": "40", "L": "0.1", "A": "0.01"},
                            "block_to_bridge": {"kind": "rod_area", "a": "hot_block", "b": "bridge", "k": "15", "L": "0.1", "A": "0.01"},
                        },
                    },
                    "right": {
                        "kind": "rods",
                        "nodes": ["bridge", "ice_sample"],
                        "terminals": ["bridge", "ice_sample"],
                        "rods": {
                            "bridge_to_ice": {"kind": "rod_area", "a": "bridge", "b": "ice_sample", "k": "30", "L": "0.1", "A": "0.02"},
                        },
                    },
                    "contacts": [{"leftPort": "bridge", "rightPort": "bridge"}],
                },
                "attachments": {
                    "left.hot_block": {
                        "kind": "sensible_body",
                        "massKg": "0.5",
                        "specificHeatJPerKgK": "400",
                        "initialTemperatureK": "420",
                    },
                    "left.calorimeter": {
                        "kind": "sensible_body",
                        "heatCapacityJPerK": "1500",
                        "initialTemperatureK": "320",
                    },
                    "right.ice_sample": {
                        "kind": "phase_substance",
                        "initialTemperatureK": "258.15",
                        "transitionTemperatureK": "273.15",
                        "specificLatentHeatJPerKg": "334000",
                        "solidSpecificHeatJPerKgK": "2100",
                        "liquidSpecificHeatJPerKgK": "4200",
                        "initialSolidKg": "0.15",
                        "initialLiquidKg": "0",
                    },
                },
                "solve": {"mode": "transient", "durationS": "600"},
            },
        },
        {
            "key": "critical_radius_vessel",
            "title": "Lesson 2 · Critical-Radius Insulated Spherical Vessel (Steady)",
            "category": "critical_radius",
            "summary": (
                "Compare insulation thickness around a heated spherical vessel (r_in = 0.04 m, "
                "k_ins = 0.4 W/(m K), h = 10 W/(m^2 K) => critical radius r_cr = 2k/h = 0.08 m). "
                "Adding insulation below r_cr INCREASES heat loss!"
            ),
            "sweepSpec": {
                "label": "Insulation outer radius r_out (m)",
                "path": ["attachments", "vessel_in", "geometry", "layers", 0, "outerRadiusM"],
                "values": ["0.045", "0.06", "0.08", "0.12", "0.20"],
                "metricPort": "vessel_in",
            },
            "controls": [
                {
                    "id": "r_out",
                    "label": "Insulation outer radius r_out (m)",
                    "path": ["attachments", "vessel_in", "geometry", "layers", 0, "outerRadiusM"],
                    "min": 0.045,
                    "max": 0.25,
                    "step": 0.005,
                },
                {
                    "id": "k_ins",
                    "label": "Insulation k (W/(m K))",
                    "path": ["attachments", "vessel_in", "geometry", "layers", 0, "conductivityWPerMK"],
                    "min": 0.05,
                    "max": 1.0,
                    "step": 0.05,
                },
                {
                    "id": "h_conv",
                    "label": "Convection h (W/(m^2 K))",
                    "path": ["attachments", "vessel_in", "exterior", "convectionCoefficientWPerM2K"],
                    "min": 2,
                    "max": 30,
                    "step": 1,
                },
                {
                    "id": "emissivity",
                    "label": "Surface emissivity",
                    "path": ["attachments", "vessel_in", "exterior", "emissivity"],
                    "min": 0,
                    "max": 1,
                    "step": 0.1,
                },
            ],
            "system": {
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "lesson_critical_radius_sphere",
                "nodes": ["core", "vessel_in"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["core", "vessel_in"],
                    "rods": {
                        "wall_contact": {"kind": "rod_area", "a": "core", "b": "vessel_in", "k": "400", "L": "0.01", "A": "0.02"},
                    },
                },
                "attachments": {
                    "core": {"kind": "maintained", "temperatureK": "400"},
                    "vessel_in": {
                        "kind": "radial_shell",
                        "geometry": {
                            "kind": "sphere",
                            "innerRadiusM": "0.04",
                            "layers": [
                                {"outerRadiusM": "0.08", "conductivityWPerMK": "0.4"},
                            ],
                        },
                        "exterior": {
                            "airTemperatureK": "300",
                            "convectionCoefficientWPerM2K": "10",
                            "enclosureTemperatureK": "300",
                            "emissivity": "0",
                            "sigmaWPerM2K4": "0.0000000567",
                        },
                    },
                },
                "solve": {"mode": "steady"},
            },
        },
        {
            "key": "reversing_hysteresis",
            "title": "Lesson 3 · 4-Event Melt -> Superheat -> Re-Enter -> Refreeze Hysteresis",
            "category": "calorimetry",
            "summary": (
                "Subcooled ice on a 3-terminal STAR network coupled to a hot body and a cold "
                "reservoir: warms to 273.15 K, melts completely, superheats, then reverses as the "
                "reservoir cools it back through refreezing into subcooled solid."
            ),
            "controls": [
                {
                    "id": "body_T0",
                    "label": "Hot body T_0 (K)",
                    "path": ["attachments", "b", "initialTemperatureK"],
                    "min": 320,
                    "max": 450,
                    "step": 10,
                },
                {
                    "id": "cold_T",
                    "label": "Cold reservoir T (K)",
                    "path": ["attachments", "r", "temperatureK"],
                    "min": 210,
                    "max": 265,
                    "step": 5,
                },
                {
                    "id": "duration",
                    "label": "Horizon duration (s)",
                    "path": ["solve", "durationS"],
                    "min": 200,
                    "max": 4000,
                    "step": 200,
                },
            ],
            "system": {
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "lesson_reversing_hysteresis_star",
                "nodes": ["b", "p", "r"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["b", "p", "r"],
                    "rods": {
                        "bp": {"kind": "rod_area", "a": "b", "b": "p", "k": "3.2", "L": "1", "A": "1"},
                        "pr": {"kind": "rod_area", "a": "p", "b": "r", "k": "0.55", "L": "1", "A": "1"},
                        "br": {"kind": "rod_area", "a": "b", "b": "r", "k": "0.45", "L": "1", "A": "1"},
                    },
                },
                "attachments": {
                    "b": {"kind": "sensible_body", "heatCapacityJPerK": "900", "initialTemperatureK": "410"},
                    "p": {
                        "kind": "phase_substance",
                        "initialTemperatureK": "260",
                        "transitionTemperatureK": "273.15",
                        "specificLatentHeatJPerKg": "334000",
                        "solidSpecificHeatJPerKgK": "2100",
                        "liquidSpecificHeatJPerKgK": "4200",
                        "initialSolidKg": "0.04",
                        "initialLiquidKg": "0",
                    },
                    "r": {"kind": "maintained", "temperatureK": "240"},
                },
                "solve": {"mode": "transient", "durationS": "3800", "initialSteps": 24},
            },
        },
        {
            "key": "refusal_and_uncertainty",
            "title": "Lesson 4 · Preserved Refusals (unsupported_regime & mode_sequence_uncertain)",
            "category": "refusals",
            "summary": (
                "Demonstrates honest physical boundaries: a transient radiating shell returns "
                "structured unsupported_regime (never fake steady math); switch mode or try the "
                "interval-conductance tie to observe certified mode_sequence_uncertain."
            ),
            "controls": [],
            "system": {
                "schema": THERMAL_SYSTEM_SCHEMA,
                "id": "lesson_unsupported_transient_radiation",
                "nodes": ["core", "shell_in"],
                "conduction": {
                    "kind": "rods",
                    "terminals": ["core", "shell_in"],
                    "rods": {
                        "wall": {"kind": "rod_area", "a": "core", "b": "shell_in", "k": "15", "L": "0.05", "A": "0.01"},
                    },
                },
                "attachments": {
                    "core": {"kind": "sensible_body", "heatCapacityJPerK": "400", "initialTemperatureK": "500"},
                    "shell_in": {
                        "kind": "radial_shell",
                        "geometry": {
                            "kind": "sphere",
                            "innerRadiusM": "0.08",
                            "layers": [{"outerRadiusM": "0.10", "conductivityWPerMK": "1.5"}],
                        },
                        "exterior": {
                            "enclosureTemperatureK": "300",
                            "emissivity": "0.8",
                            "sigmaWPerM2K4": "0.0000000567",
                        },
                    },
                },
                "solve": {"mode": "transient", "durationS": "120"},
            },
        },
    ]


def _check_http_conduction_safe(conduction: Any) -> None:
    """Iteratively check conduction tree: refuse disk-reading kinds and excessive join nesting."""
    stack: list[tuple[Any, int]] = [(conduction, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_HTTP_JOIN_DEPTH:
            raise ValueError(
                f"conduction join nesting exceeds HTTP loopback limit of {MAX_HTTP_JOIN_DEPTH}"
            )
        if not isinstance(node, dict):
            continue
        kind = node.get("kind")
        if kind in FORBIDDEN_HTTP_CONDUCTION_KINDS:
            raise ValueError(
                f"conduction kind {kind!r} reads local filesystem paths and is disabled over the HTTP loopback API"
            )
        if kind == "join":
            stack.append((node.get("left"), depth + 1))
            stack.append((node.get("right"), depth + 1))


def _validate_http_system_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object matching sim_heat.thermal_system/1")
    _check_http_conduction_safe(payload.get("conduction"))
    solve = payload.get("solve")
    if isinstance(solve, dict):
        max_sweeps = solve.get("maxSweeps")
        if max_sweeps is not None and not isinstance(max_sweeps, bool) and isinstance(max_sweeps, int):
            if max_sweeps > MAX_HTTP_SWEEPS:
                raise ValueError(
                    f"solve.maxSweeps ({max_sweeps}) exceeds HTTP loopback limit of {MAX_HTTP_SWEEPS}"
                )
        max_events = solve.get("maxEvents")
        if max_events is not None and not isinstance(max_events, bool) and isinstance(max_events, int):
            if max_events > MAX_HTTP_EVENTS:
                raise ValueError(
                    f"solve.maxEvents ({max_events}) exceeds HTTP loopback limit of {MAX_HTTP_EVENTS}"
                )
    return payload


def _snapshot_static_resources(lesson_dir: Path = LESSON_DIR) -> dict[str, tuple[bytes, str]]:
    """Snapshot all static UI assets at server startup so no path is derived from HTTP requests."""
    index_bytes = (lesson_dir / "index.html").read_bytes()
    app_bytes = (lesson_dir / "app.mjs").read_bytes()
    core_bytes = (lesson_dir / "core.mjs").read_bytes()
    presets_bytes = json.dumps(
        {
            "schema": "sim_heat.lesson_presets/1",
            "presets": build_presets(),
            **{k: False for k in OFFLINE_FLAG_KEYS},
        },
        allow_nan=False,
    ).encode("utf-8")
    return {
        "/viewer/lesson/": (index_bytes, "text/html; charset=utf-8"),
        "/viewer/lesson/index.html": (index_bytes, "text/html; charset=utf-8"),
        "/viewer/lesson/app.mjs": (app_bytes, "text/javascript; charset=utf-8"),
        "/viewer/lesson/core.mjs": (core_bytes, "text/javascript; charset=utf-8"),
        "/api/presets": (presets_bytes, "application/json; charset=utf-8"),
    }


class LessonHandler(BaseHTTPRequestHandler):
    """Strict loopback-only HTTP handler delegating directly to simheat.system."""

    def __init__(self, *args, resources: dict[str, tuple[bytes, str]], **kwargs):
        self.resources = resources
        super().__init__(*args, **kwargs)

    def version_string(self) -> str:
        return "SIM_HEAT-lesson-loopback"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass

    def _send(self, status: int, data: bytes, mime: str, *, head: bool = False, close: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", CSP_HEADER)
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if not head:
            self.wfile.write(data)
        self.wfile.flush()

    def _send_json(self, status: int, obj: dict[str, Any], *, head: bool = False, close: bool = False) -> None:
        raw = json.dumps(obj, allow_nan=False).encode("utf-8")
        self._send(status, raw, "application/json; charset=utf-8", head=head, close=close)

    def _check_host(self, *, head: bool = False) -> str | None:
        expected = f"127.0.0.1:{self.server.server_port}"
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0] != expected:
            self._send(421, b"Invalid Host\n", "text/plain; charset=utf-8", head=head)
            return None
        return expected

    def _check_same_origin_post(self, expected_host: str) -> bool:
        expected_origin = f"http://{expected_host}"
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1 or (len(origins) == 1 and origins[0] != expected_origin):
            self._send_json(
                403,
                {
                    "ok": False,
                    "error": "cross-origin POST forbidden on local loopback lesson server",
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
            )
            return False
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site is not None and fetch_site not in ("same-origin", "none"):
            self._send_json(
                403,
                {
                    "ok": False,
                    "error": f"cross-site POST forbidden (Sec-Fetch-Site={fetch_site!r})",
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
            )
            return False
        return True

    def _route_get(self, *, head: bool = False) -> None:
        if self._check_host(head=head) is None:
            return
        uri = urlsplit(self.path)
        if uri.scheme or uri.netloc or uri.query or uri.fragment or self.path != uri.path:
            self._send(404, b"Not found\n", "text/plain; charset=utf-8", head=head)
            return
        if uri.path == "/":
            self.send_response(302)
            self.send_header("Location", "/viewer/lesson/")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Content-Security-Policy", CSP_HEADER)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if uri.path == "/favicon.ico":
            self._send(204, b"", "text/plain; charset=utf-8", head=head)
            return
        resource = self.resources.get(uri.path)
        if resource is None:
            self._send(404, b"Not found\n", "text/plain; charset=utf-8", head=head)
            return
        self._send(200, *resource, head=head)

    def do_GET(self) -> None:
        self._route_get()

    def do_HEAD(self) -> None:
        self._route_get(head=True)

    def do_POST(self) -> None:
        expected_host = self._check_host()
        if expected_host is None:
            return
        if not self._check_same_origin_post(expected_host):
            return
        uri = urlsplit(self.path)
        if uri.scheme or uri.netloc or uri.query or uri.fragment or self.path != uri.path:
            self._send_json(404, {"ok": False, "error": "not found", **{k: False for k in OFFLINE_FLAG_KEYS}})
            return
        if uri.path not in ("/api/describe", "/api/solve"):
            self._send_json(404, {"ok": False, "error": "not found", **{k: False for k in OFFLINE_FLAG_KEYS}})
            return

        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            self._send_json(
                415,
                {
                    "ok": False,
                    "error": "Content-Type must be application/json",
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
            )
            return

        if self.headers.get_all("Transfer-Encoding", []):
            self._send_json(
                400,
                {
                    "ok": False,
                    "error": "Transfer-Encoding is not supported on the local loopback API; send Content-Length",
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
                close=True,
            )
            return

        cl_headers = self.headers.get_all("Content-Length", [])
        if len(cl_headers) != 1 or not cl_headers[0].strip().isdigit():
            self._send_json(
                400,
                {
                    "ok": False,
                    "error": "single positive integer Content-Length header required",
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
                close=True,
            )
            return
        length = int(cl_headers[0].strip())
        if length <= 0:
            self._send_json(
                400,
                {
                    "ok": False,
                    "error": "positive Content-Length header required",
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
                close=True,
            )
            return
        if length > MAX_POST_BYTES:
            self._send_json(
                413,
                {
                    "ok": False,
                    "error": f"payload exceeds {MAX_POST_BYTES} byte limit",
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
                close=True,
            )
            return

        body = self.rfile.read(length)
        try:
            payload = json.loads(
                body.decode("utf-8"),
                parse_constant=lambda tok: (_ for _ in ()).throw(ValueError(f"non-finite JSON token {tok!r}")),
            )
            _validate_http_system_payload(payload)
            if uri.path == "/api/describe":
                result = describe_equations(payload)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "equations": result,
                        **{k: False for k in OFFLINE_FLAG_KEYS},
                    },
                )
            else:
                result = solve_system(payload, include_equations=True)
                self._send_json(200, {"ok": True, "result": result, **{k: False for k in OFFLINE_FLAG_KEYS}})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, RecursionError) as exc:
            self._send_json(
                400,
                {
                    "ok": False,
                    "error": str(exc),
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
            )
        except Exception:
            self._send_json(
                500,
                {
                    "ok": False,
                    "error": "internal loopback server error",
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
                close=True,
            )

    def _method_not_allowed(self) -> None:
        if self._check_host() is None:
            return
        self._send(405, b"Method not allowed\n", "text/plain; charset=utf-8", close=True)

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_TRACE = do_CONNECT = _method_not_allowed


def create_server(port: int = 0, *, lesson_dir: Path = LESSON_DIR) -> ThreadingHTTPServer:
    """Create a strictly loopback-bound lesson server (port=0 selects an ephemeral port)."""
    if isinstance(port, bool) or not isinstance(port, int) or not (0 <= port <= 65535):
        raise ValueError("port must be an integer in [0, 65535]")
    resources = _snapshot_static_resources(lesson_dir)
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(LessonHandler, resources=resources))
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="Loopback port on 127.0.0.1 (0 selects available port)")
    args = parser.parse_args(argv)
    try:
        server = create_server(args.port)
    except (OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "stage": "lesson_loopback_server",
                    "started": False,
                    "error": str(exc),
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
                allow_nan=False,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        print(
            json.dumps(
                {
                    "stage": "lesson_loopback_server",
                    "started": True,
                    "url": f"http://127.0.0.1:{server.server_port}/viewer/lesson/",
                    "apiRoutes": ["/api/presets", "/api/describe", "/api/solve"],
                    **{k: False for k in OFFLINE_FLAG_KEYS},
                },
                allow_nan=False,
            ),
            flush=True,
        )
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
