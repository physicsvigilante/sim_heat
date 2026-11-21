"""End-to-end read-only loopback H1 authoring workbench acceptance and refusal."""
from contextlib import contextmanager
import hashlib
from http.client import HTTPConnection
import json
import socket
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from h1.model import Refusal
from tools.authoring_workbench import create_server, DEFAULT_ROUTE

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'h1' / 'cases'


@contextmanager
def listening(name):
    server, preview = create_server(CASES / name / 'study.json', CASES)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, preview
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def request(port, method='GET', path=DEFAULT_ROUTE, headers=None, data=None):
    connection = HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        connection.request(method, path, body=data, headers=headers or {})
        result = connection.getresponse()
        return result.status, dict(result.getheaders()), result.read()
    finally:
        connection.close()


class LocalAuthoringWorkbenchTests(unittest.TestCase):
    def test_direct_script_launch_from_an_unrelated_directory(self):
        with TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, '-I', '-B', str(ROOT / 'tools/authoring_workbench.py'), '--help'],
                cwd=directory, capture_output=True, text=True, timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--root', result.stdout)

    def test_real_h1_compositions_load_without_special_case_code(self):
        for name, expected_mode, count in (('D1', 'transient', 3),
                                           ('S1', 'steady', 4),
                                           ('TEACH_SPLIT3', 'transient', 12)):
            with self.subTest(name=name), listening(name) as (server, admitted):
                self.assertEqual(server.server_address[0], '127.0.0.1')
                status, headers, raw = request(server.server_port)
                self.assertEqual(status, 200)
                self.assertIn('application/json', headers['Content-Type'])
                self.assertEqual(json.loads(raw), admitted)
                self.assertEqual(admitted['mode'], expected_mode)
                self.assertEqual(len(admitted['components']), count)
                self.assertEqual(admitted['studyId'], json.loads((CASES/name/'study.json').read_bytes())['id'])
                self.assertEqual(admitted['source']['studySha256'], hashlib.sha256((CASES/name/'study.json').read_bytes()).hexdigest())
                self.assertEqual(admitted['source']['modelSha256'], hashlib.sha256((CASES/name/'model.mo').read_bytes()).hexdigest())
                self.assertFalse(admitted['source']['nativeExecuted'])
                self.assertFalse(admitted['source']['nativeQualified'])
                self.assertEqual(admitted['source']['publicRequestStatus'], 'not_computed')
                self.assertTrue(all(r['status']=='not_computed' for r in admitted['requests']))
                self.assertIn('no-store', headers['Cache-Control'])
                self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
                self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_only_allowlisted_assets_and_no_model_or_study_download(self):
        with listening('D1') as (server, _):
            for path in ('/viewer/source_preview/', '/viewer/source_preview/index.html',
                         '/viewer/source_preview/app.mjs', '/viewer/source_preview/core.mjs',
                         '/index.html'):
                with self.subTest(path=path):
                    status, headers, data = request(server.server_port, path=path)
                    self.assertEqual(status, 200)
                    self.assertTrue(data)
                    self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            status, headers, data = request(server.server_port, path='/')
            self.assertEqual(status, 302)
            self.assertEqual(headers['Location'], '/viewer/source_preview/')
            for path in ('/.git/config', '/h1/cases/D1/model.mo', '/h1/cases/D1/study.json',
                         '/viewer/network/data/D1.json', '/viewer/source_preview/data/bad.json',
                         '/viewer/source_preview/../app.mjs', '/viewer/source_preview/%2e%2e/app.mjs',
                         DEFAULT_ROUTE+'?candidate=1'):
                with self.subTest(forbidden=path):
                    status, _, body = request(server.server_port, path=path)
                    self.assertEqual(status, 404)
                    self.assertNotIn(b'within;', body)
            for method in ('POST','PUT','DELETE','PATCH'):
                with self.subTest(method=method):
                    status, _, body = request(server.server_port, method=method,
                                              path=DEFAULT_ROUTE, data=b'arbitrary bytes')
                    self.assertEqual(status, 405)
            status, _, _ = request(server.server_port, headers={'Host':'evil.example'})
            self.assertEqual(status, 421)
            status, headers, body = request(server.server_port, method='HEAD')
            self.assertEqual(status, 200)
            self.assertEqual(body, b'')
            self.assertGreater(int(headers['Content-Length']), 100)

    def test_duplicate_host_headers_refused_in_both_orders(self):
        # Real HTTP/1.1 bytes: a dict cannot express duplicate headers.
        with listening('D1') as (server, _):
            port = server.server_port
            valid = f'Host: 127.0.0.1:{port}'
            evil = 'Host: evil.invalid'

            def exchange(method, hosts):
                request_bytes = ('\r\n'.join([
                    f'{method} {DEFAULT_ROUTE} HTTP/1.1', *hosts,
                    'Connection: close', '', '',
                ])).encode('ascii')
                with socket.create_connection(('127.0.0.1', port), timeout=5) as sock:
                    sock.settimeout(5)
                    sock.sendall(request_bytes)
                    chunks = []
                    while True:
                        data = sock.recv(65536)
                        if not data:
                            break
                        chunks.append(data)
                result = b''.join(chunks)
                self.assertIn(b'\r\n\r\n', result)
                return result.split(b'\r\n', 1)[0], result.split(b'\r\n\r\n', 1)[1]

            # Control proves the server actually serves the admitted payload.
            status, body = exchange('GET', [valid])
            self.assertIn(b' 200 ', status)
            self.assertIn(b'"studyId"', body)
            for method, hosts in (
                ('GET', [valid, evil]),
                ('GET', [evil, valid]),
                ('GET', [valid, valid]),
                ('HEAD', [valid, evil]),
                ('GET', []),
            ):
                with self.subTest(method=method, headers=hosts):
                    status, body = exchange(method, hosts)
                    self.assertIn(b' 421 ', status)
                    self.assertNotIn(b'"studyId"', body)
                    self.assertNotIn(b'authored_source_only', body)

    def test_served_ui_describes_custom_source_not_embedded_illustration(self):
        with listening('S1') as (server, preview):
            status, _, page = request(server.server_port, path='/viewer/source_preview/')
            self.assertEqual(status, 200)
            self.assertIn(b'Your admitted H1 source loads automatically', page)
            self.assertNotIn(b'Load the included TEACH_SPLIT3 demonstration', page)
            self.assertIn(b'Local session instructions', page)
            self.assertEqual(preview['studyId'], 'H1_S1')
            status, _, help_page = request(server.server_port, path='/index.html')
            self.assertEqual(status, 200)
            self.assertIn(b'no files are uploaded or modified', help_page)
            self.assertIn(b'Do not include secrets', help_page)
            self.assertIn(b'press Ctrl+C after inspection', help_page)
            self.assertNotIn(b'within;', help_page)

    def test_rejected_stale_hash_never_opens_server_or_mutates_draft(self):
        with TemporaryDirectory() as tmp:
            cases = Path(tmp)/'cases'; case = cases/'draft'; case.mkdir(parents=True)
            original_model = (CASES/'D1/model.mo').read_bytes()
            altered = original_model.replace(b'T_initial=293.15', b'T_initial=298.15')
            original_study = (CASES/'D1/study.json').read_bytes()
            (case/'model.mo').write_bytes(altered)
            (case/'study.json').write_bytes(original_study)
            with self.assertRaises(Refusal) as exc:
                create_server(case/'study.json', cases)
            self.assertEqual(exc.exception.code, 'identity')
            self.assertEqual((case/'model.mo').read_bytes(), altered)
            self.assertEqual((case/'study.json').read_bytes(), original_study)
            self.assertEqual(sorted(p.name for p in case.iterdir()), ['model.mo','study.json'])

    def test_refused_observation_and_unsafe_case_path_fail_closed(self):
        with TemporaryDirectory() as tmp:
            cases = Path(tmp)/'cases'; case = cases/'draft'; case.mkdir(parents=True)
            (case/'model.mo').write_bytes((CASES/'D1/model.mo').read_bytes())
            study = json.loads((CASES/'D1/study.json').read_bytes())
            study['requests'][0]['target'] = 'nonexistent.port'
            (case/'study.json').write_text(json.dumps(study))
            with self.assertRaises(Refusal) as exc:
                create_server(case/'study.json', cases)
            self.assertEqual(exc.exception.code, 'request')
            with self.assertRaises(Refusal) as exc:
                create_server(CASES/'D1/study.json', cases)
            self.assertEqual(exc.exception.code, 'path')

    def test_refuse_port_out_of_range_before_listening(self):
        for bad in (-1,65536,True,'8000'):
            with self.subTest(bad=bad), self.assertRaises(Refusal):
                create_server(CASES/'D1/study.json', CASES, bad)


if __name__ == '__main__':
    unittest.main()
