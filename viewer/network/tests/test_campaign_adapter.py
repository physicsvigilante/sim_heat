"""Read-only campaign-adapter and conductivity-revision checks.

The original real OpenModelica run is externally preserved and SHA-pinned.
Tiny mutated ZIPs in these negative tests are SYNTHETIC, never native evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from h1.model import Refusal
from h1.study import load_study
from viewer.network.tools.build_campaign_case import compile_campaign_case

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/'viewer/network/data'
ARCHIVE_SHA='dc32a0a36a27f031ce7a13da83ebdd26a3dd6ac1d14612fa597b36cb439f4843'
MODEL_SHA='8d57b06b2e46d7ccca44da784acc433f3297b94871e65ad590881d4fc75531e3'
STUDY_SHA='ab3741a80e94b32a8f6d050f34baf9c773763fdd3ed6df71ccdcdbe2214a0d87'


class CampaignCaseTests(unittest.TestCase):
    def source(self,name):
        return load_study(ROOT/'h1/cases'/name/'study.json',ROOT/'h1/cases')

    def test_original_parent_and_child_are_admitted_narrow_h1_revision(self):
        base=self.source('D2')
        child=self.source('D2_K2')
        self.assertTrue(base.request_report['admitted'])
        self.assertTrue(child.request_report['admitted'])
        self.assertEqual(child.model_sha256,MODEL_SHA)
        self.assertEqual(child.sha256,STUDY_SHA)
        self.assertEqual(child.data['revision']['target'],'rod.k')
        self.assertEqual(child.data['revision']['origin'],'hypothetical')
        self.assertEqual(child.data['revision']['parentStudySha256'],base.sha256)
        self.assertEqual(child.data['revision']['parentModelSha256'],base.model_sha256)
        self.assertEqual(base.model.components['rod'].value('k'),100)
        self.assertEqual(child.model.components['rod'].value('k'),200)
        self.assertEqual(base.topology.nodes,child.topology.nodes)
        self.assertEqual(base.data['analysis'],child.data['analysis'])

    def test_saved_source_linked_hypothetical_is_native_not_generated_reference(self):
        baseline=json.loads((DATA/'D2.json').read_text())
        revised_path=DATA/'D2_K2.json'
        revised=json.loads(revised_path.read_text())
        catalog=json.loads((DATA/'index.json').read_text())['cases']
        self.assertEqual([i['id'] for i in catalog],
            ['H1_D1','H1_D2','DEV_BRIDGE','H1_S1','TEACH_RING4','H1_D2_K2'])
        self.assertEqual(hashlib.sha256(revised_path.read_bytes()).hexdigest(),
                         catalog[-1]['sha256'])
        self.assertEqual(revised['source']['artifactSha256'],ARCHIVE_SHA)
        self.assertEqual(revised['source']['runId'],43693191224)
        self.assertEqual(revised['source']['artifactId'],14153251022)
        self.assertEqual(revised['source']['modelSha256'],MODEL_SHA)
        self.assertEqual(revised['source']['studySha256'],STUDY_SHA)
        self.assertEqual(revised['source']['canonicalSamples'],1001)
        self.assertEqual(revised['source']['checksPassed'],34)
        self.assertEqual(revised['source']['publicRequestStatus'],'diagnostic_only')
        self.assertFalse(revised['source']['nativeQualified'])
        self.assertEqual(len(revised['samples']),21)
        self.assertEqual(revised['columns'],baseline['columns'])
        self.assertEqual(revised['graph'],baseline['graph'])
        self.assertEqual(revised['analysis'],baseline['analysis'])
        self.assertEqual([r[0] for r in baseline['samples']],
                         [r[0] for r in revised['samples']])

    def test_exact_saved_physics_differences_have_independent_analytic_check(self):
        original=json.loads((DATA/'D2.json').read_text())
        new=json.loads((DATA/'D2_K2.json').read_text())
        eq=(500*353.15+1500*293.15)/2000
        self.assertAlmostEqual(eq,308.15,places=12)
        self.assertEqual(new['samples'][0][-1],24)
        self.assertEqual(original['samples'][0][-1],12)
        for old,newrow in zip(original['samples'],new['samples']):
            t,cold,hot,delta_cold,delta_hot,q=newrow
            self.assertEqual(t,old[0])
            self.assertAlmostEqual(delta_cold+delta_hot,0,delta=1e-6)
            self.assertAlmostEqual(q,0.4*(hot-cold),delta=1e-12)
            self.assertAlmostEqual(hot-cold,60*math.exp(-t/937.5),delta=3e-5)
            self.assertLessEqual(hot-cold,old[2]-old[1]+1e-9)
            self.assertGreater(hot-cold,0)  # no finite-time equilibrium claim

    def test_invalid_native_candidate_and_zip_members_refuse_before_publication(self):
        with TemporaryDirectory() as td:
            p=Path(td)/'SYNTHETIC-NOT-NATIVE.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('campaign.json',
                    json.dumps({'schema':'sim_heat.resolution_attempt/1',
                                'status':'stopped','nativeQualified':False,'batches':[]}))
                z.writestr('batch_1/attempt.json','{"status":"stopped"}')
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            args=(ROOT,'h1/cases/D2_K2/study.json',p,digest,1,1,14153251022,
                  'TEST-ONLY')
            external={'expected_run_id':43693191224,
                      'expected_commit_sha':'52b1635932a3e4519b91f3bf093c0c21b0248d91',
                      'expected_branch':'experiment/h1-cloud-resolution-once'}
            with self.assertRaises(Refusal) as error:
                compile_campaign_case(*args,**external)
            self.assertEqual(error.exception.code,'campaign_evidence')
            for changes in (
                {'expected_run_id':-1},
                {'expected_commit_sha':'not-sha'},
                {'expected_branch':'main'},
            ):
                options={**external,**changes}
                with self.assertRaises(Refusal):
                    compile_campaign_case(*args,**options)
            with self.assertRaises(Refusal):
                compile_campaign_case(ROOT,'h1/cases/D2_K2/study.json',
                    p,'0'*64,1,1,14153251022,'test-only',**external)
            with self.assertRaises(Refusal):
                compile_campaign_case(ROOT,'h1/cases/D2_K2/study.json',
                    p,digest,0,1,14153251022,'test-only',**external)

    def test_reject_unsafe_outside_archive_members_even_if_rehashed(self):
        with TemporaryDirectory() as td:
            p=Path(td)/'SYNTHETIC-UNSAFE.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('campaign.json','{}')
                z.writestr('batch_1/attempt.json','{}')
                z.writestr('../ignored.txt','TEST-ONLY')
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaises(Refusal) as error:
                compile_campaign_case(
                    ROOT,'h1/cases/D2_K2/study.json',p,digest,1,1,14153251022,'test',
                    expected_run_id=43693191224,
                    expected_commit_sha='52b1635932a3e4519b91f3bf093c0c21b0248d91',
                    expected_branch='experiment/h1-cloud-resolution-once')
            self.assertEqual(error.exception.code,'campaign_evidence')

    def test_production_builder_does_not_dispatch_on_apparatus_id_or_call_solver(self):
        source=(ROOT/'viewer/network/tools/build_campaign_case.py').read_text()
        for token in ('H1_D2_K2','rod.Q_flow','TEACH_RING4','subprocess.',
                      'simulate(','buildModel('):
            self.assertNotIn(token,source)


if __name__=='__main__':unittest.main()
