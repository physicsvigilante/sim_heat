"""Prospective audit regressions. No compiler query, build, or native launch."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from h1.model import Binding, Refusal
from h1.source_preview import build_source_preview, serialized
from h1.study import load_study, verified_snapshot, _same_typed
from tools.h1_native_batch import load_plan

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'h1/cases'


class AuditRegressions(unittest.TestCase):
    def test_workbench_direct_script_has_no_implicit_pythonpath_dependency(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(
                [sys.executable, '-I', str(ROOT/'tools/authoring_workbench.py'), '--help'],
                cwd=cwd, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--root', result.stdout)

    def test_windows_native_path_is_converted_to_portable_descriptor_path(self):
        class WindowsRelativeInput:
            def absolute(self):
                return self
            def relative_to(self, root):
                return PureWindowsPath('D1/study.json')
        result = load_study(WindowsRelativeInput(), CASES)
        self.assertEqual(result.path, (CASES/'D1/study.json').resolve())

    def test_preview_rejects_mutated_physical_fact_with_unchanged_hash(self):
        study = load_study(CASES/'D1/study.json', CASES)
        study.model.components['body'].fields['m'] = Binding(987.0, 'Mass')
        with self.assertRaises(Refusal):
            build_source_preview(study)

    def test_preview_rejects_mutated_provenance_with_unchanged_hash(self):
        study = load_study(CASES/'D1/study.json', CASES)
        study.data['provenance'][0]['note'] = 'Unauthenticated after-load replacement'
        with self.assertRaises(Refusal):
            build_source_preview(study)

    def test_preview_rejects_mutated_request_metadata(self):
        study = load_study(CASES/'D1/study.json', CASES)
        study.request_report['requests'][0]['unit'] = 'J'
        with self.assertRaises(Refusal):
            build_source_preview(study)

    def test_frozenset_member_type_drift_refuses_source_preview_identity(self):
        # Independent R2 review: True compares equal to 1 in native set
        # equality. Exact typed source re-admission must not coerce it.
        admitted = load_study(CASES/'D1/study.json', CASES)
        self.assertEqual(admitted.topology.anchored_nodes, frozenset({0, 1}))
        wrong = replace(admitted, topology=replace(
            admitted.topology, anchored_nodes=frozenset({0, True})))
        self.assertEqual(wrong.topology.anchored_nodes,
                         admitted.topology.anchored_nodes)
        self.assertFalse(_same_typed(wrong, admitted))
        with self.assertRaises(Refusal) as found:
            verified_snapshot(wrong)
        self.assertEqual(found.exception.code, 'identity')
        with self.assertRaises(Refusal):
            build_source_preview(wrong)

    def test_unordered_typed_snapshot_equality_keeps_legitimate_copies(self):
        admitted = load_study(CASES/'D1/study.json', CASES)
        copied = replace(admitted, topology=replace(
            admitted.topology, anchored_nodes=frozenset({1, 0})))
        self.assertTrue(_same_typed(copied, admitted))
        self.assertEqual(build_source_preview(copied)['status'],
                         'admitted_source_only')
        self.assertFalse(_same_typed(frozenset({0, True}),
                                     frozenset({0, 1})))
        self.assertFalse(_same_typed(frozenset({True}), frozenset({1})))
        self.assertFalse(_same_typed({0, True}, {0, 1}))
        self.assertTrue(_same_typed(frozenset({1, 0}), frozenset({0, 1})))

    def test_preview_rejects_mutated_topology(self):
        study = load_study(CASES/'D1/study.json', CASES)
        study.topology.node_of['body.port'] = 999
        with self.assertRaises(Refusal):
            build_source_preview(study)

    def test_changed_source_file_after_admission_does_not_keep_old_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(CASES/'D1', root/'D1')
            source = root/'D1/study.json'
            study = load_study(source, root)
            data = json.loads(source.read_bytes())
            data['provenance'][0]['note'] = 'New source after admission'
            source.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(Refusal):
                build_source_preview(study)

    def test_unchanged_sources_and_cross_folder_revision_remain_valid(self):
        for case in ('D1', 'S1', 'TEACH_SPLIT3', 'D2_K2'):
            with self.subTest(case=case):
                study = load_study(CASES/case/'study.json', CASES)
                result = build_source_preview(study)
                self.assertEqual(result['source']['modelSha256'], study.model_sha256)
                self.assertFalse(result['source']['nativeExecuted'])
                self.assertTrue(all(r['status']=='not_computed' for r in result['requests']))
        expected = (ROOT/'viewer/source_preview/data/TEACH_SPLIT3.json').read_bytes()
        actual = serialized(build_source_preview(load_study(CASES/'TEACH_SPLIT3/study.json', CASES)))
        self.assertEqual(actual, expected)

    def test_output_provenance_does_not_alias_loaded_source(self):
        study = load_study(CASES/'D1/study.json', CASES)
        preview = build_source_preview(study)
        preview['modelProvenance'][0]['note'] = 'changed output only'
        self.assertNotEqual(study.data['provenance'][0]['note'], 'changed output only')
        build_source_preview(study)

    def test_plan_parser_consumes_exact_bytes_whose_hash_was_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('lib.mo', 'case/study.json', 'facts.json'):
                p = root/name
                p.parent.mkdir(exist_ok=True)
                p.write_text('fixture only; not executable', encoding='utf-8')
            plan = {
                'schema':'sim_heat.native_batch/1', 'branch':'original-branch',
                'caseRoot':'case', 'library':'lib.mo', 'output':'out',
                'compilerVersion':'OpenModelica 1.27.0', 'mslVersion':'4.0.0',
                'dependencies':{}, 'cases':[{'study':'case/study.json', 'reference':'facts.json'}],
                'pins':{name:sha256((root/name).read_bytes()).hexdigest()
                        for name in ('lib.mo','case/study.json','facts.json')},
            }
            path = root/'plan.json'
            original = json.dumps(plan).encode()
            path.write_bytes(original)
            changed = deepcopy(plan)
            changed['branch'] = 'unauthenticated-replacement'
            real_read = Path.read_bytes
            reads = []
            def racing_read(candidate):
                raw = real_read(candidate)
                if candidate == path:
                    reads.append(candidate)
                    path.write_text(json.dumps(changed), encoding='utf-8')
                return raw
            with patch.object(Path, 'read_bytes', racing_read):
                admitted = load_plan(root, path, sha256(original).hexdigest())
            self.assertEqual(admitted['branch'], 'original-branch')
            self.assertEqual(len(reads), 1)


if __name__ == '__main__':
    unittest.main()
