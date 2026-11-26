"""M05 loopback lesson server, security/refusal preservation, critical-radius physics, and JS guard tests."""
from __future__ import annotations

from fractions import Fraction as F
import http.client
import json
from pathlib import Path
import re
import threading
import unittest

from simheat.lesson_server import MAX_POST_BYTES, build_presets, create_server
from tools.offline_provenance import OFFLINE_FLAG_KEYS

ROOT = Path(__file__).resolve().parents[1]


class M05LessonLoopbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(0)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def _request(self, method: str, path: str, *, body: bytes | None = None, headers: dict[str, str] | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            hdrs = {"Host": f"127.0.0.1:{self.port}"}
            if headers:
                hdrs.update(headers)
            conn.request(method, path, body=body, headers=hdrs)
            resp = conn.getresponse()
            raw = resp.read()
            return resp.status, dict(resp.getheaders()), raw
        finally:
            conn.close()

    def _post_json(self, path: str, payload: dict, *, extra_headers: dict[str, str] | None = None):
        raw = json.dumps(payload).encode("utf-8")
        hdrs = {
            "Content-Type": "application/json",
            "Content-Length": str(len(raw)),
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        if extra_headers:
            hdrs.update(extra_headers)
        status, resp_hdrs, resp_body = self._request("POST", path, body=raw, headers=hdrs)
        return status, resp_hdrs, json.loads(resp_body.decode("utf-8"))

    def test_static_assets_headers_and_presets_route(self):
        # Root redirects to /viewer/lesson/ with full security headers (M05-R05)
        st, hdrs, _ = self._request("GET", "/")
        self.assertEqual(st, 302)
        self.assertEqual(hdrs.get("Location"), "/viewer/lesson/")
        self.assertEqual(hdrs.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("default-src 'none'", hdrs.get("Content-Security-Policy", ""))

        # Static HTML & ESM assets served with strict CSP & nosniff
        for route, mime_prefix in (
            ("/viewer/lesson/", "text/html"),
            ("/viewer/lesson/app.mjs", "text/javascript"),
            ("/viewer/lesson/core.mjs", "text/javascript"),
        ):
            st, hdrs, raw = self._request("GET", route)
            self.assertEqual(st, 200, route)
            self.assertTrue(hdrs["Content-Type"].startswith(mime_prefix))
            self.assertEqual(hdrs["X-Content-Type-Options"], "nosniff")
            self.assertIn("default-src 'none'", hdrs["Content-Security-Policy"])
            self.assertGreater(len(raw), 100)

        # GET /api/presets returns all 4 presets with honest False flags
        st, _, raw = self._request("GET", "/api/presets")
        self.assertEqual(st, 200)
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual(data["schema"], "sim_heat.lesson_presets/1")
        for flag in OFFLINE_FLAG_KEYS:
            self.assertIs(data[flag], False)
        self.assertEqual(len(data["presets"]), 4)

    def test_all_curated_presets_describe_and_solve_over_loopback(self):
        presets = {p["key"]: p for p in build_presets()}

        # 1. Calorimeter joined preset -> enthalpy complete with 2 events (solid -> plateau -> liquid)
        st_d, _, desc = self._post_json("/api/describe", presets["calorimeter_joined"]["system"])
        self.assertEqual(st_d, 200)
        self.assertTrue(desc["ok"])
        self.assertEqual(desc["equations"]["selectedBackend"], "enthalpy")
        st_s, _, sol = self._post_json("/api/solve", presets["calorimeter_joined"]["system"])
        self.assertEqual(st_s, 200)
        self.assertTrue(sol["ok"])
        res = sol["result"]
        self.assertEqual(res["backend"], "enthalpy")
        self.assertEqual(res["status"], "complete")
        self.assertEqual(len(res["backendResult"]["events"]), 2)
        for flag in OFFLINE_FLAG_KEYS:
            self.assertIs(sol[flag], False)
            self.assertIs(res[flag], False)

        # 2. Critical-radius spherical vessel: verify heat loss peaks at r_cr = 2k/h = 0.08 m!
        #    Q(r=0.045) < Q(r=0.08) and Q(r=0.20) < Q(r=0.08) strictly via certified Python solves!
        q_by_r = {}
        for r_str in ("0.045", "0.08", "0.20"):
            sys_doc = json.loads(json.dumps(presets["critical_radius_vessel"]["system"]))
            sys_doc["attachments"]["vessel_in"]["geometry"]["layers"][0]["outerRadiusM"] = r_str
            st_v, _, sv = self._post_json("/api/solve", sys_doc)
            self.assertEqual(st_v, 200)
            self.assertEqual(sv["result"]["backend"], "multiport")
            self.assertEqual(sv["result"]["terminationReason"], "converged")
            q_lo, q_hi = map(F, sv["result"]["backendResult"]["ports"]["vessel_in"]["outwardHeatRateBoundsW"])
            q_by_r[r_str] = (q_lo, q_hi)
        self.assertGreater(q_by_r["0.08"][0], q_by_r["0.045"][1])
        self.assertGreater(q_by_r["0.08"][0], q_by_r["0.20"][1])

        # 3. Reversing hysteresis preset -> 4 certified transitions
        st_h, _, sh = self._post_json("/api/solve", presets["reversing_hysteresis"]["system"])
        self.assertEqual(st_h, 200)
        self.assertEqual(sh["result"]["status"], "complete")
        self.assertEqual(len(sh["result"]["backendResult"]["events"]), 4)

        # 4. Preserved refusal preset -> structured unsupported_regime over HTTP 200 envelope
        st_u, _, su = self._post_json("/api/solve", presets["refusal_and_uncertainty"]["system"])
        self.assertEqual(st_u, 200)
        self.assertEqual(su["result"]["status"], "unsupported_regime")
        self.assertEqual(su["result"]["unsupportedMechanismPair"], ["radial_shell", "sensible_body"])
        self.assertIsNone(su["result"]["backendResult"])

    def test_preserved_mode_sequence_uncertain_and_security_refusals(self):
        # 1. Interval conductance tie -> mode_sequence_uncertain preserved verbatim over HTTP
        tie_sys = {
            "schema": "sim_heat.thermal_system/1",
            "id": "http_uncertain_tie",
            "nodes": ["heater", "b1", "b2"],
            "conduction": {
                "kind": "rods",
                "terminals": ["heater", "b1", "b2"],
                "rods": {
                    "e1": {"kind": "rod_area", "a": "heater", "b": "b1", "k": {"low": "0.999", "high": "1.001"}, "L": "1", "A": "1"},
                    "e2": {"kind": "rod_area", "a": "heater", "b": "b2", "k": {"low": "0.999", "high": "1.001"}, "L": "1", "A": "1"},
                    "e3": {"kind": "rod_area", "a": "b1", "b": "b2", "k": "0.5", "L": "1", "A": "1"},
                },
            },
            "attachments": {
                "heater": {"kind": "sensible_body", "heatCapacityJPerK": "1000", "initialTemperatureK": "373.15", "heatInputW": "300"},
                "b1": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0",
                },
                "b2": {
                    "kind": "phase_substance",
                    "transitionTemperatureK": "273.15",
                    "specificLatentHeatJPerKg": "334000",
                    "solidSpecificHeatJPerKgK": "2100",
                    "liquidSpecificHeatJPerKgK": "4200",
                    "initialSolidKg": "0.1",
                    "initialLiquidKg": "0",
                },
            },
            "solve": {"mode": "transient", "durationS": "450"},
        }
        st, _, body = self._post_json("/api/solve", tie_sys)
        self.assertEqual(st, 200)
        self.assertEqual(body["result"]["status"], "mode_sequence_uncertain")
        self.assertEqual(body["result"]["terminationReason"], "mode_sequence_uncertain")

        # 2. Invalid Host header -> 421
        st, _, _ = self._request("GET", "/api/presets", headers={"Host": "evil.example:80"})
        self.assertEqual(st, 421)

        # 3. Cross-origin POST -> 403
        st, _, err_body = self._post_json(
            "/api/describe",
            build_presets()[0]["system"],
            extra_headers={"Origin": "https://attacker.example"},
        )
        self.assertEqual(st, 403)
        self.assertFalse(err_body["ok"])
        self.assertIs(err_body["nativeExecuted"], False)

        # 4. Cross-site Sec-Fetch-Site -> 403
        st, _, _ = self._post_json(
            "/api/describe",
            build_presets()[0]["system"],
            extra_headers={"Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(st, 403)

        # 5. Filesystem-reading conduction kinds (h1_study & derived_law_ref) refused over HTTP -> 400
        for bad_cond in (
            {"kind": "h1_study", "studyPath": "studies/composite_wall/study.json", "rootPath": "studies/composite_wall"},
            {"kind": "derived_law_ref", "path": "some_law.json"},
            {
                "kind": "join",
                "left": {"kind": "derived_law_ref", "path": "secret.json"},
                "right": {"kind": "derived_law_ref", "path": "secret2.json"},
                "contacts": [{"leftPort": "a", "rightPort": "b"}],
            },
        ):
            st, _, err = self._post_json(
                "/api/solve",
                {
                    "schema": "sim_heat.thermal_system/1",
                    "id": "fs_probe",
                    "conduction": bad_cond,
                    "attachments": {"a": {"kind": "maintained", "temperatureK": "300"}},
                    "solve": {"mode": "steady"},
                },
            )
            self.assertEqual(st, 400)
            self.assertIn("disabled over the HTTP loopback API", err["error"])

        # 6. Oversized payload (Content-Length > MAX_POST_BYTES) -> 413 without buffering huge body
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            conn.putrequest("POST", "/api/describe", skip_host=True)
            conn.putheader("Host", f"127.0.0.1:{self.port}")
            conn.putheader("Origin", f"http://127.0.0.1:{self.port}")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(MAX_POST_BYTES + 1))
            conn.endheaders()
            resp = conn.getresponse()
            err_413 = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(resp.status, 413)
            self.assertFalse(err_413["ok"])
            self.assertIs(err_413["nativeExecuted"], False)
        finally:
            conn.close()

        # 7. Non-JSON Content-Type -> 415, PUT -> 405, unknown keys -> 400
        st, _, _ = self._request(
            "POST",
            "/api/describe",
            body=b"{}",
            headers={"Content-Type": "text/plain", "Content-Length": "2"},
        )
        self.assertEqual(st, 415)
        st, _, _ = self._request("PUT", "/api/solve", body=b"{}")
        self.assertEqual(st, 405)
        st, _, err_uk = self._post_json(
            "/api/solve",
            {**build_presets()[0]["system"], "unexpectedField": "bad"},
        )
        self.assertEqual(st, 400)
        self.assertFalse(err_uk["ok"])

        # 8. M05-R02 regressions: deep join nesting (> 32) and malformed non-iterable fields return clean 400 JSON (no crash!)
        deep = {"kind": "rods", "nodes": ["a", "b"], "terminals": ["a", "b"], "rods": {}}
        for _ in range(40):
            deep = {"kind": "join", "left": deep, "right": {"kind": "rods", "nodes": ["a", "b"], "terminals": ["a", "b"], "rods": {}}, "contacts": [{"leftPort": "b", "rightPort": "a"}]}
        st, _, err_deep = self._post_json(
            "/api/describe",
            {"schema": "sim_heat.thermal_system/1", "id": "deep", "conduction": deep, "attachments": {}, "solve": {"mode": "steady"}},
        )
        self.assertEqual(st, 400)
        self.assertIn("nesting exceeds", err_deep["error"])
        self.assertIs(err_deep["nativeExecuted"], False)

        # Malformed TypeError-inducing solve.observations=123 -> clean HTTP 400 JSON (no server crash!)
        bad_obs = json.loads(json.dumps(build_presets()[1]["system"]))
        bad_obs["solve"]["observations"] = 123
        st, _, err_obs = self._post_json("/api/describe", bad_obs)
        self.assertEqual(st, 400)
        self.assertFalse(err_obs["ok"])
        self.assertIs(err_obs["nativeExecuted"], False)

        # 9. M05-R03 regressions: oversized maxSweeps/maxEvents refused (400), Transfer-Encoding refused (400), OPTIONS/TRACE return 405 with CSP!
        huge_sweeps = json.loads(json.dumps(build_presets()[1]["system"]))
        huge_sweeps["solve"]["maxSweeps"] = 10**9
        st, _, err_sw = self._post_json("/api/solve", huge_sweeps)
        self.assertEqual(st, 400)
        self.assertIn("exceeds HTTP loopback limit", err_sw["error"])

        huge_events = json.loads(json.dumps(build_presets()[0]["system"]))
        huge_events["solve"]["maxEvents"] = 10**9
        st, _, err_ev = self._post_json("/api/solve", huge_events)
        self.assertEqual(st, 400)
        self.assertIn("exceeds HTTP loopback limit", err_ev["error"])

        st, hdrs_opt, _ = self._request("OPTIONS", "/api/solve")
        self.assertEqual(st, 405)
        self.assertIn("default-src 'none'", hdrs_opt.get("Content-Security-Policy", ""))
        st, _, _ = self._request("OPTIONS", "/api/solve", headers={"Host": "evil.example:80"})
        self.assertEqual(st, 421)

        st, _, err_te = self._request(
            "POST",
            "/api/describe",
            body=b"2\r\n{}\r\n0\r\n\r\n",
            headers={
                "Content-Type": "application/json",
                "Transfer-Encoding": "chunked",
                "Origin": f"http://127.0.0.1:{self.port}",
            },
        )
        self.assertEqual(st, 400)
        self.assertFalse(json.loads(err_te.decode("utf-8"))["ok"])

    def test_zero_physics_static_guard_on_lesson_javascript(self):
        lesson_dir = ROOT / "viewer" / "lesson"
        forbidden = (r"\bMath\.exp\b", r"\bMath\.log\b", r"\bMath\.pow\b", r"\bMath\.sqrt\b", r"step_matrix")
        for fname in ("core.mjs", "app.mjs"):
            src = (lesson_dir / fname).read_text(encoding="utf-8")
            for pat in forbidden:
                self.assertIsNone(re.search(pat, src), f"{fname} must not contain physics math {pat}")


if __name__ == "__main__":
    unittest.main()
