"""Developer-exposed composition probe: genuine H1 admission, not native output.

The fixed illustrative task and initial model/study commits are preserved.
This test must not reinterpret or edit those source facts to obtain a pass.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from h1.model import Refusal
from h1.study import load_study
from h1.source_preview import build_source_preview
from tools.authoring_workbench import create_server

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'experiments' / 'teacher_dual_network'
MODEL_SHA = 'aad202adb2fa7cd4f308fd602b37ece83b26ef2c1d652db49d49c97e92cab6a4'


@contextmanager
def serve(study=CASE/'study.json', root=CASE):
    server, payload = create_server(study, root)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get(port, path='/viewer/source_preview/', method='GET', data=None):
    con = HTTPConnection('127.0.0.1', port, timeout=10)
    try:
        con.request(method, path, body=data)
        response = con.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        con.close()


class TeacherDualNetworkTests(unittest.TestCase):
    def test_first_author_source_and_two_disconnected_networks(self):
        raw = (CASE/'model.mo').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), MODEL_SHA)
        study = load_study(CASE/'study.json', CASE)
        self.assertEqual(study.model_sha256, MODEL_SHA)
        self.assertEqual(study.data['id'], 'TEACH_DUAL_NETWORK')
        self.assertEqual(study.model.name, 'DualNetworkLesson')
        self.assertEqual(len(study.model.components), 10)
        self.assertEqual(len(study.topology.nodes), 6)
        self.assertEqual(len(study.topology.edges), 5)
        self.assertEqual(len(study.topology.networks), 2)
        self.assertEqual(len(study.topology.anchored_nodes), 5)
        n = study.topology.node_of
        # Genuine disjoint networks, never an automatic link due to canvas position.
        group_of = {node: group for group in study.topology.networks for node in group}
        self.assertEqual(group_of[n['left.port']], group_of[n['right.port']])
        self.assertNotEqual(group_of[n['left.port']], group_of[n['plate.port']])
        self.assertEqual(group_of[n['bathHot.port']], group_of[n['bathCold.port']])
        self.assertEqual(group_of[n['bathHot.port']], group_of[n['plate.port']])
        junctions = [ports for i, ports in enumerate(study.topology.nodes)
                     if i not in study.topology.anchored_nodes]
        self.assertEqual(len(junctions), 1)
        self.assertEqual(set(junctions[0]), {'seriesOne.port_b', 'seriesTwo.port_a'})
        self.assertEqual({edge[0] for edge in study.topology.edges},
                         {'hotFeed', 'seriesOne', 'seriesTwo', 'bypass', 'pairLink'})
        self.assertTrue(study.request_report['admitted'])
        self.assertEqual(len(study.request_report['requests']), 8)
        self.assertEqual({q['status'] for q in study.request_report['requests']}, {'not_computed'})
        self.assertEqual([q['unit'] for q in study.request_report['requests']],
                         ['K', 'K', 'K', 'W', 'W', 'J', 'J', 'K'])

    def test_generic_source_view_preserves_truth_and_not_computed(self):
        preview = build_source_preview(load_study(CASE/'study.json', CASE))
        self.assertEqual(preview['status'], 'admitted_source_only')
        self.assertEqual(preview['source']['modelSha256'], MODEL_SHA)
        self.assertFalse(preview['source']['nativeExecuted'])
        self.assertFalse(preview['source']['nativeQualified'])
        self.assertFalse(preview['source']['sourceFidelityQualified'])
        self.assertEqual(preview['source']['publicRequestStatus'], 'not_computed')
        self.assertEqual(len(preview['components']), 10)
        self.assertEqual(len(preview['nodes']), 6)
        self.assertEqual(len(preview['rods']), 5)
        self.assertEqual(sum(x['role'] == 'junction' for x in preview['nodes']), 1)
        self.assertEqual(len(preview['requests']), 8)
        self.assertEqual({r['status'] for r in preview['requests']}, {'not_computed'})
        for component in preview['components']:
            self.assertTrue(component['inputs'])
            self.assertEqual(len(component['sourceProvenance']), len(component['inputs']))
            for record in component['sourceProvenance']:
                self.assertEqual(record['kind'], 'illustrative')
                self.assertEqual(record['locator'],
                                 'experiments/teacher_dual_network/TASK.md | Explicit physical inputs (SI)')
                self.assertEqual(len(record['appliesTo']), 1)
        self.assertEqual(len(preview['modelProvenance']), 1)
        self.assertEqual(preview['modelProvenance'][0]['kind'], 'adopted_assumption')
        self.assertNotIn('samples', preview)

    def test_local_server_is_source_only_and_does_not_serve_archived_diagnostics(self):
        with serve() as (server, payload):
            port = server.server_port
            status, headers, html = get(port)
            self.assertEqual(status, 200)
            self.assertIn(b'SIM_HEAT', html)
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            self.assertIn('no-store', headers['Cache-Control'])
            actual = json.loads(get(port, '/viewer/source_preview/data/TEACH_SPLIT3.json')[2])
            # Legacy file name is only a virtual route for *this* genuine input.
            self.assertEqual(actual['studyId'], 'TEACH_DUAL_NETWORK')
            self.assertEqual(actual, payload)
            self.assertEqual(len(actual['requests']), 8)
            for forbidden in ('/viewer/network/compare.html',
                              '/viewer/network/data/D2.json',
                              '/experiments/teacher_dual_network/model.mo',
                              '/experiments/teacher_dual_network/study.json',
                              '/h1/cases/D2/model.mo'):
                with self.subTest(forbidden=forbidden):
                    self.assertEqual(get(port, forbidden)[0], 404)
            self.assertEqual(get(port, method='POST', data=b'dummy')[0], 405)

    def test_stale_hash_wrong_request_and_missing_provenance_refuse(self):
        with TemporaryDirectory() as temp:
            draft = Path(temp)
            (draft/'model.mo').write_bytes((CASE/'model.mo').read_bytes())
            (draft/'study.json').write_bytes((CASE/'study.json').read_bytes())

            with (draft/'model.mo').open('ab') as file:
                file.write(b'// intentionally changed after study was hashed\n')
            with self.assertRaises(Refusal) as ctx:
                load_study(draft/'study.json', draft)
            self.assertEqual(ctx.exception.code, 'identity')
            (draft/'model.mo').write_bytes((CASE/'model.mo').read_bytes())

            descriptor = json.loads((draft/'study.json').read_text('utf-8'))
            descriptor['requests'][0]['target'] = 'notARealBody.port'
            (draft/'study.json').write_text(json.dumps(descriptor)+'\n', encoding='utf-8')
            not_admitted = load_study(draft/'study.json', draft)
            self.assertFalse(not_admitted.request_report['admitted'])
            self.assertEqual(not_admitted.request_report['requests'][0]['code'],
                             'unknown_observation_target')
            with self.assertRaises(Refusal):
                build_source_preview(not_admitted)
            descriptor['requests'][0]['target'] = 'plate.port'

            descriptor['provenance'] = [r for r in descriptor['provenance']
                                        if r['target'] != 'pairLink.k']
            (draft/'study.json').write_text(json.dumps(descriptor)+'\n', encoding='utf-8')
            with self.assertRaises(Refusal) as ctx:
                load_study(draft/'study.json', draft)
            self.assertEqual(ctx.exception.code, 'provenance')


if __name__ == '__main__':
    unittest.main()
