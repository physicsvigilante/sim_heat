"""R2 provenance pairing: original H1 studies and source-pinned native cases.

All altered local JSON/model bytes in this test are SYNTHETIC TEST-ONLY, never
new native outputs. No OpenModelica call, no reference-filled trajectories.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from h1.model import Refusal
from viewer.network.tools.build_case import sha, stable_json
from viewer.network.tools.build_compare_index import (
    compile_pair_index, check_source_relation, native_source,
)

ROOT = Path(__file__).resolve().parents[3]
PATHS = (
    'h1/cases/D2/model.mo',
    'h1/cases/D2/study.json',
    'h1/cases/D2_K2/model.mo',
    'h1/cases/D2_K2/study.json',
    'viewer/network/data/D2.json',
    'viewer/network/data/D2_K2.json',
    'viewer/network/data/compare_sources.json',
)
INDEX = 'viewer/network/data/index.json'
PLAN = 'viewer/network/data/compare_sources.json'
OUTPUT = 'viewer/network/data/compare_index.json'


def read_json(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write_json(p, obj):
    p.write_bytes(stable_json(obj))


def scratch(root: Path):
    for rel in PATHS:
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/rel, destination)
    catalog = read_json(ROOT/INDEX)
    catalog['cases'] = [
        e for e in catalog['cases'] if e['id'] in ('H1_D2','H1_D2_K2')
    ]
    dest = root/INDEX
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, catalog)


def edit(root, rel, modifier, *, case_id=None):
    dest=root/rel
    obj=read_json(dest)
    modifier(obj)
    write_json(dest,obj)
    if case_id:
        catalog=read_json(root/INDEX)
        for entry in catalog['cases']:
            if entry['id']==case_id:
                entry['sha256']=sha(dest.read_bytes())
        write_json(root/INDEX,catalog)


def admitted(root: Path):
    return compile_pair_index(root,root/PLAN,root/INDEX)


class SourcePairProvenanceTests(unittest.TestCase):
    def test_original_studies_rebuild_exact_versioned_index_without_omc(self):
        result = admitted(ROOT)
        source = (ROOT/OUTPUT).read_bytes()
        self.assertEqual(source,stable_json(result),
                         'Published compare index must be byte-for-byte generated from admitted sources')
        self.assertEqual(result['schema'],'sim_heat.viewer.compare_index/2')
        p=result['pairs'][0]
        self.assertEqual(len(result['pairs']),1)
        self.assertEqual((p['baseline'],p['successor']),('H1_D2','H1_D2_K2'))
        self.assertEqual((p['revision']['before'],p['revision']['after']),(100.,200.))
        self.assertEqual(p['revision']['target'],'rod.k')
        self.assertEqual(p['revision']['origin'],'hypothetical')
        self.assertEqual(p['sources']['baseline']['runId'],43691263273)
        self.assertEqual(p['sources']['successor']['runId'],43693191224)
        self.assertNotEqual(p['sources']['baseline']['artifactId'],
                            p['sources']['successor']['artifactId'])

    def test_direct_revision_policy_uses_actual_h1_model_and_study(self):
        with TemporaryDirectory() as td:
            root=Path(td);scratch(root)
            result=admitted(root)
            self.assertEqual(result,admitted(ROOT))
            for tag,relative,edit_fn in [
                ('wrong-parent-sha','h1/cases/D2_K2/study.json',
                 lambda x:x['revision'].__setitem__('parentStudySha256','0'*64)),
                ('not-hypothetical','h1/cases/D2_K2/study.json',
                 lambda x:x['revision'].__setitem__('origin','source_given')),
                ('changed-analysis','h1/cases/D2_K2/study.json',
                 lambda x:x['analysis'].__setitem__('intervals',500)),
                ('changed-requests','h1/cases/D2_K2/study.json',
                 lambda x:x['requests'].clear()),
                ('changed-target','h1/cases/D2_K2/study.json',
                 lambda x:x['revision'].__setitem__('target','hot.m')),
                ('parent-reversal','viewer/network/data/compare_sources.json',
                 lambda x:x['pairs'][0].__setitem__('baselineStudy','h1/cases/D2_K2/study.json')),
                ('path-escape','viewer/network/data/compare_sources.json',
                 lambda x:x['pairs'][0].__setitem__('successorStudy','../outside.json')),
            ]:
                with self.subTest(mutation=tag),TemporaryDirectory() as tmp:
                    candidate=Path(tmp);scratch(candidate)
                    edit(candidate,relative,edit_fn)
                    with self.assertRaises(Refusal):
                        admitted(candidate)

    def test_altered_physics_or_topology_refuses_even_after_model_and_study_rehash(self):
        variants=[
            ('changed-body-mass',
             lambda s:s.replace('hot(m=1.0','hot(m=2.0')),
            ('changed-rod-length',
             lambda s:s.replace('L=0.5','L=0.6')),
            ('changed-conductor-count',
             lambda s:s.replace('  SimHeat.RodArea rod(', '  SimHeat.RodArea extra(k=200.0,L=0.5,A=0.001);\n  SimHeat.RodArea rod(')),
            ('changed-topology',
             lambda s:s.replace('connect(rod.port_b, cold.port);',
                                  'connect(rod.port_b, hot.port);')),
            ('revised-rod-k',
             lambda s:s.replace('rod(k=200.0','rod(k=300.0')),
        ]
        for label,change in variants:
            with self.subTest(mutation=label),TemporaryDirectory() as td:
                root=Path(td);scratch(root)
                model=root/'h1/cases/D2_K2/model.mo'
                original=model.read_text()
                changed=change(original)
                self.assertNotEqual(original,changed)
                model.write_text(changed,encoding='utf-8')
                edit(root,'h1/cases/D2_K2/study.json',
                     lambda x:x['model'].__setitem__('sha256',sha(model.read_bytes())))
                with self.assertRaises(Refusal):
                    admitted(root)

    def test_rehashed_catalog_and_pair_metadata_refuse_misattributed_sources(self):
        malformed=[
            ('run-id',lambda x:x['pairs'][0]['expectedNative']['baseline'].__setitem__('runId',1)),
            ('artifact-id',lambda x:x['pairs'][0]['expectedNative']['successor'].__setitem__('artifactId',1)),
            ('csv-sha',lambda x:x['pairs'][0]['expectedNative']['baseline'].__setitem__('csvSha256','f'*64)),
            ('zip-sha',lambda x:x['pairs'][0]['expectedNative']['successor'].__setitem__('artifactSha256','0'*64)),
            ('commit',lambda x:x['pairs'][0]['expectedNative']['successor'].__setitem__('compiledSourceCommit','a'*40)),
            ('wrong-sha-type',lambda x:x['pairs'][0]['expectedNative']['successor'].__setitem__('csvSha256',123)),
            ('unsupported-field',lambda x:x['pairs'][0]['expectedNative']['baseline'].__setitem__('trust','certified')),
            ('same-slot',lambda x:x['pairs'][0]['expectedNative'].__setitem__('successor',
                                   deepcopy(x['pairs'][0]['expectedNative']['baseline']))),
            ('wrong-study-path',lambda x:x['pairs'][0].__setitem__('successorStudy','h1/cases/D2/study.json')),
            ('unknown-case',lambda x:x['pairs'][0].__setitem__('successor','UNVERIFIED')),
            ('duplicate-pair',lambda x:x['pairs'].append(deepcopy(x['pairs'][0]))),
        ]
        for label,fn in malformed:
            with self.subTest(mutation=label),TemporaryDirectory() as td:
                root=Path(td);scratch(root)
                edit(root,PLAN,fn)
                with self.assertRaises(Refusal):
                    admitted(root)
        for label,change in [
            ('wrong-native-source',lambda c:c['source'].__setitem__('runId',7)),
            ('wrong-native-status',lambda c:c['source'].__setitem__('nativeQualified',True)),
            ('wrong-rod-owner',lambda c:c['graph']['edges'][0].__setitem__('from','cold')),
            ('fictitious-preview-time',lambda c:c['samples'][1].__setitem__(0,469)),
            ('wrong-native-columns',lambda c:c['columns'].append('invented.T')),
            ('wrong-native-model-sha',lambda c:c['source'].__setitem__('modelSha256','0'*64)),
            ('wrong-native-grid',lambda c:c['analysis'].__setitem__('intervals',500)),
            ('changed-initial-state',lambda c:c['samples'][0].__setitem__(2,400)),
        ]:
            with self.subTest(mutation=label),TemporaryDirectory() as td:
                root=Path(td);scratch(root)
                edit(root,'viewer/network/data/D2_K2.json',change,case_id='H1_D2_K2')
                with self.assertRaises(Refusal):
                    admitted(root)

    def test_pair_reuse_allows_separate_slots_in_one_authenticated_run_not_same_slot(self):
        plan = read_json(ROOT/PLAN)['pairs'][0]['expectedNative']
        a, b = deepcopy(plan['baseline']), deepcopy(plan['successor'])
        check_source_relation(a,b)
        b['runId']=a['runId'];b['artifactId']=a['artifactId']
        b['artifactSha256']=a['artifactSha256']
        b['compiledSourceCommit']=a['compiledSourceCommit']
        b['archiveEntry']='case_01/normalized.csv'
        check_source_relation(a,b)   # one run/artifact, different compiled slots
        b['compiledSourceCommit']='0'*40
        with self.assertRaises(Refusal) as wrong_run_sha:
            check_source_relation(a,b)
        self.assertEqual(wrong_run_sha.exception.code,'pair_provenance')
        b['compiledSourceCommit']=a['compiledSourceCommit']
        b['archiveEntry']=a['archiveEntry']
        with self.assertRaises(Refusal):
            check_source_relation(a,b)
        b['archiveEntry']='case_01/normalized.csv'
        b['artifactSha256']='f'*64
        with self.assertRaises(Refusal):
            check_source_relation(a,b)
        b['artifactId']=a['artifactId']+1
        check_source_relation(a,b)  # same run, distinct ZIP artifact OK
        b['compiledSourceCommit']='0'*40
        with self.assertRaises(Refusal):
            check_source_relation(a,b)  # same run, separate artifact still one SHA
        b['runId']=a['runId']+1
        check_source_relation(a,b)  # different workflow run may have different SHA

    def test_fully_rehashed_pair_and_case_refuse_divergent_shared_run_commit(self):
        # A fabricated source plan and native case may be internally repinned.
        # This test deliberately keeps the baseline and successor artifact IDs
        # distinct but assigns them one GitHub run and *different* run SHAs.
        # A single Actions run cannot have two distinct GITHUB_SHA values.
        with TemporaryDirectory() as td:
            root=Path(td);scratch(root)
            baseline=read_json(root/PLAN)['pairs'][0]['expectedNative']['baseline']
            run_id=baseline['runId']
            edit(root,PLAN,
                 lambda x:x['pairs'][0]['expectedNative']['successor'].__setitem__(
                     'runId',run_id))
            edit(root,'viewer/network/data/D2_K2.json',
                 lambda x:x['source'].__setitem__('runId',run_id),
                 case_id='H1_D2_K2')
            with self.assertRaises(Refusal) as error:
                admitted(root)
            self.assertEqual(error.exception.code,'pair_provenance')
            self.assertIn('conflicting executed source commits',
                          error.exception.message)

            # A consistent same-run, distinct-artifact test-only repin is
            # structurally admissible; GitHub provenance is still EXTERNAL.
            original_commit=baseline['compiledSourceCommit']
            edit(root,PLAN,
                 lambda x:x['pairs'][0]['expectedNative']['successor'].__setitem__(
                     'compiledSourceCommit',original_commit))
            edit(root,'viewer/network/data/D2_K2.json',
                 lambda x:x['source'].__setitem__(
                     'compiledSourceCommit',original_commit),
                 case_id='H1_D2_K2')
            hypothetical=admitted(root)
            self.assertEqual(hypothetical['pairs'][0]['sources']['successor']['runId'],
                             run_id)
            self.assertFalse(read_json(root/'viewer/network/data/D2_K2.json')[
                'source']['nativeQualified'])

    def test_self_pinned_fabrication_is_not_external_github_attestation(self):
        with TemporaryDirectory() as td:
            root=Path(td);scratch(root)
            changed={'runId':7,'artifactId':42,
                     'compiledSourceCommit':'b'*40,
                     'artifactSha256':'f'*64}
            edit(root,PLAN,lambda x:x['pairs'][0]['expectedNative']['successor'].update(changed))
            edit(root,'viewer/network/data/D2_K2.json',
                 lambda x:x['source'].update(changed),case_id='H1_D2_K2')
            data=admitted(root)
            self.assertEqual(data['pairs'][0]['sources']['successor']['runId'],7)
            # This is deliberate admission of *coherently fabricated* test-only
            # source metadata. A separate trusted GitHub run/ZIP audit is REQUIRED.
            self.assertNotEqual(data,admitted(ROOT))

    def test_source_authoring_stays_data_only_no_case_name_dispatch(self):
        program=(ROOT/'viewer/network/tools/build_compare_index.py').read_text()
        for forbidden in ('H1_D2_K2', 'TEACH_RING4', 'buildModel(', 'simulate(',
                          'subprocess.', 'rod(k=200'):
            self.assertNotIn(forbidden,program)


if __name__=='__main__':
    unittest.main()
