"""Offline-only negative controls for N1 plan limits; no native invocation."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('n1_plan_checks',HERE/'check_plan.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class PlanChecks(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((HERE/'plan.json').read_text())

    def refuse(self, fn):
        p=deepcopy(self.plan);fn(p)
        with self.assertRaises((ValueError,KeyError,TypeError)):
            m.validate_manifest(p)

    def test_complete_current_plan_remains_nonexecuting(self):
        r=m.check(); self.assertEqual(r['planStructuralChecks'],'PASS')
        self.assertFalse(r['nativeExecutionReady']);self.assertFalse(r['nativeExecuted'])
        self.assertEqual(r['mandatoryExports'],77);self.assertEqual(r['publicRequests'],8)

    def test_native_permission_refused(self):
        self.refuse(lambda p:p['authority'].__setitem__('nativeExecutionApproved',True))

    def test_version_query_permission_refused(self):
        self.refuse(lambda p:p['authority'].__setitem__('nativeVersionQueryApproved',True))

    def test_fake_ready_refused(self):
        self.refuse(lambda p:p.__setitem__('executionReady',True))

    def test_missing_gate_refused(self):
        self.refuse(lambda p:p['executionBlockers'].pop())

    def test_budget_expansion_refused(self):
        self.refuse(lambda p:p['limits'].__setitem__('proposedModelLaunches',4))

    def test_retries_refused(self):
        self.refuse(lambda p:p['limits'].__setitem__('maximumRetries',1))

    def test_silent_horizon_change_refused(self):
        self.refuse(lambda p:p['proposedRuns'][0].__setitem__('horizonSeconds',32000))

    def test_physical_companion_override_refused(self):
        self.refuse(lambda p:p['proposedRuns'][2]['changes'].__setitem__('T06.d',.032))

    def test_weakened_error_margin_refused(self):
        self.refuse(lambda p:p['acceptance'].__setitem__('referenceErrorFractionMaximum',1/80))

    def test_summed_companion_budget_refused(self):
        self.refuse(lambda p:p['acceptance'].__setitem__('companionDifferenceAllowance','SUM'))

    def test_fabricated_runtime_hash_refused(self):
        self.refuse(lambda p:p['host'].__setitem__('actualCompilerBinarySha256','0'*64))

    def test_hidden_launch_workflow_refused(self):
        self.refuse(lambda p:p['runner'].__setitem__('automaticNativeWorkflowIncluded',True))

    def test_original_source_drift_refused(self):
        self.refuse(lambda p:p.__setitem__('modelSha256','f'*64))

    def test_independent_topology_mismatch_refused(self):
        s=m.load_study(HERE/'inputs/T/study.json',HERE/'inputs')
        ref=m.read_reference(HERE/'reference-facts.json')
        ref['rods']['T10']['b']='R'
        with self.assertRaises(m.Refusal) as caught:m.bind_reference(s,ref)
        self.assertEqual(caught.exception.code,'reference_binding')

    def test_reference_diameter_mismatch_refused(self):
        s=m.load_study(HERE/'inputs/T/study.json',HERE/'inputs')
        ref=m.read_reference(HERE/'reference-facts.json')
        ref['rods']['T06']['d']=.032
        with self.assertRaises(m.Refusal) as caught:m.bind_reference(s,ref)
        self.assertEqual(caught.exception.code,'reference_binding')


if __name__=='__main__':unittest.main()
