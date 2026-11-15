"""Offline-only batch and transient MAT checks; no compiler or model is invoked."""
import ast
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from h1.model import Refusal, internal_exports
from h1.study import load_study
from h1 import reference
from h1.matv4 import decode_mat_bytes
from h1.verification import check_candidate, candidate_receipt
from h1.tests.test_matv4 import make_mat
from h1.tests.test_verification import analytic
from tools.h1_native_batch import settings, build_script, check_setup, load_plan, check_host, invoke

ROOT=Path(__file__).resolve().parents[2]


class NativeBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.studies={k:load_study(ROOT/'h1/cases'/k/'study.json',ROOT/'h1/cases') for k in ('D1','D2')}
        cls.bundles={k:reference.prepare(reference.read_reference(ROOT/'h1/reference_cases'/f'{k}.json')) for k in cls.studies}

    def test_different_settings_are_read_from_studies(self):
        self.assertEqual(settings(self.studies['D1'])['stopTime'],12500)
        self.assertEqual(settings(self.studies['D2'])['stopTime'],9375)
        for s in self.studies.values():
            self.assertEqual(settings(s)['intervals'],1000)
            self.assertEqual(settings(s)['tolerance'],1e-8)

    def test_generated_script_one_build_no_simulate(self):
        for s in self.studies.values():
            script=build_script(s,ROOT/'experiments/h1_spike/SimHeat.mo',ROOT/'h1/cases/D1/model.mo')
            self.assertEqual(script.count('buildModel('),1)
            self.assertNotIn('simulate(',script)
            self.assertIn('outputFormat="mat"',script)
            self.assertIn('numberOfIntervals=1000',script)
            self.assertIn(f'buildModel({s.model.name},',script)

    def test_model_rename_does_not_need_runner_dispatch(self):
        s=self.studies['D2']; renamed=replace(s,model=replace(s.model,name='TeacherAuthored'))
        script=build_script(renamed,ROOT/'library.mo',ROOT/'model.mo')
        self.assertIn('buildModel(TeacherAuthored,',script)
        self.assertNotIn('H1_D2',script)

    def mat_candidate(self,k,mutate=None):
        s=self.studies[k];b=self.bundles[k];columns=analytic(k,b['grid'])
        if mutate: mutate(columns)
        required=internal_exports(s.model);names=['time']+list(required)
        times=list(b['grid'])+[b['grid'][-1]]
        d1=[[times[0],times[-1]]];d2=[times];info=[[0,1,0,-1]]
        for name in required:
            v=columns[name]
            if name.endswith(('.C','.G')) or np.all(v==v[0]):
                d1.append([float(v[0]),float(v[-1])]);info.append([1,len(d1),0,-1])
            else:
                d2.append(v.tolist()+[float(v[-1])]);info.append([2,len(d2),0,-1])
        raw=make_mat(names,info,d1,d2,trans=True,native_layout=True)
        decoded=decode_mat_bytes(raw,required,tuple(b['grid']),maximum_shift=b['temporalPolicy']['maximumShift'])
        csv=decoded['canonicalCsv']
        result=check_candidate(s,b,csv,candidate_receipt(s,b,csv,'synthetic'),b['seal'])
        return decoded,result

    def test_transient_mat_d1_end_to_end(self):
        decoded,r=self.mat_candidate('D1')
        self.assertEqual(len(decoded['decoded']['columns']['time']),1001)
        self.assertEqual(decoded['decoded']['duplicateRowsCollapsed'],1)
        self.assertEqual(r['status'],'checks_passed');self.assertFalse(r['nativeQualified'])

    def test_transient_mat_d2_end_to_end(self):
        decoded,r=self.mat_candidate('D2')
        self.assertEqual(len(decoded['decoded']['columns']['time']),1001)
        self.assertEqual(r['status'],'checks_passed')
        self.assertTrue(all(x['status']=='diagnostic_only' for x in r['requests']))

    def test_signed_heat_corruption_rejected(self):
        def corrupt(c): c['hot.Q_in']=-c['hot.Q_in']
        _,r=self.mat_candidate('D2',corrupt)
        self.assertEqual(r['status'],'checks_failed')
        self.assertTrue(all(x['status']=='not_computed' for x in r['requests']))

    def test_model_setup_mismatch_stops_before_launch(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model_init.xml'
            p.write_text('<fmiModelDescription modelName="H1_D1"><DefaultExperiment startTime="0" stopTime="12500" stepSize="12.5" tolerance="1e-8" solver="dassl" outputFormat="mat"/></fmiModelDescription>')
            self.assertEqual(check_setup(p,self.studies['D1'])['solver'],'dassl')
            with self.assertRaises(Refusal):check_setup(p,self.studies['D2'])

    def test_plan_drift_refuses(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'plan.json';p.write_text('{}')
            with self.assertRaises(Refusal):load_plan(Path(t),p,'0'*64)

    def test_local_execution_and_rerun_refused(self):
        plan={'branch':'test','dependencies':{'python':'3.13.5','numpy':'2.3.5','scipy':'1.17.0'}}
        with patch.dict(os.environ,{},clear=True),self.assertRaises(Refusal):check_host(plan)
        env={'GITHUB_ACTIONS':'true','GITHUB_REF':'refs/heads/test','GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'2'}
        with patch.dict(os.environ,env,clear=True),self.assertRaises(Refusal):check_host(plan)

    def test_failed_command_no_retry(self):
        with tempfile.TemporaryDirectory() as t:
            with patch('tools.h1_native_batch.subprocess.Popen') as process:
                process.return_value.wait.return_value=1
                with self.assertRaises(Refusal):invoke(['dummy'],Path(t),Path(t),'dummy',1)
                self.assertEqual(process.call_count,1)
                self.assertFalse(process.call_args.kwargs.get('shell',False))

    def test_runner_contains_no_physical_case_dispatch(self):
        source=(ROOT/'tools/h1_native_batch.py').read_text()
        for specific in ('H1_D1','H1_D2','copper','steel','12500','9375'):
            self.assertNotIn(specific,source)
        tree=ast.parse(source)
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('eval','exec') for n in ast.walk(tree)))


if __name__=='__main__':
    unittest.main()
