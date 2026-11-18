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


class ConstantArithmeticChecks(unittest.TestCase):
    """Static design/refusal controls, not a trajectory certificate or OMC test."""
    def setUp(self):
        self.plan=json.loads((HERE/'plan.json').read_text())
        self.rows={r['export']:r for r in self.plan['constantArithmeticLedger']['entries']}

    def audit(self,p=None):
        return m.arithmetic_diagnostics(p or self.plan,HERE/'reference-facts.json')

    def mutate_refused(self, fn):
        p=deepcopy(self.plan);fn(p['constantArithmeticLedger'])
        with self.assertRaises((ValueError,KeyError,TypeError)):
            self.audit(p)

    def test_exact_rounding_even_ties_and_carry(self):
        F=m.Fraction; h=m.power_two(-53)
        self.assertEqual(m.round_binary64(F(1)+h),F(1))
        self.assertEqual(m.round_binary64(F(1)+3*h),F(1)+4*h)
        self.assertEqual(m.round_binary64(F(2)-h),F(2))

    def test_subnormal_ties_and_invalid_overflow(self):
        F=m.Fraction;q=m.power_two(-1074)
        self.assertEqual(m.round_binary64(q/2),F(0))
        self.assertEqual(m.round_binary64(3*q/2),2*q)
        with self.assertRaises(ValueError):m.round_binary64(F(-1))
        with self.assertRaises(ValueError):m.round_binary64(m.power_two(1024))

    def test_independent_pi_bracket_selects_exact_one_binary_value(self):
        lo,hi=m.pi_enclosure(40)
        self.assertLess(hi-lo,m.power_two(-160))
        self.assertEqual(m.round_binary64(lo),m.round_binary64(hi))
        self.assertEqual(float(m.round_binary64(lo)).hex(),'0x1.921fb54442d18p+1')

    def test_T10_review_counterexample_keeps_physical_refusal(self):
        F=m.Fraction
        physical,checking,source=m.constant_targets(self.rows['T10.G'],m.pi_enclosure())
        self.assertEqual(physical,(F(247,8000),)*2)
        self.assertEqual(float(checking).hex(),'0x1.f9db22d0e5602p-6')
        epsilon=64*m.binary64_ulp(checking)
        ok,delta=m.physical_certificate(checking,physical,epsilon)
        self.assertFalse(ok);self.assertEqual(delta/(epsilon/100),F(131,40))
        parsed=F.from_float(95.)*F.from_float(.00013)/F.from_float(.4)
        self.assertGreater(abs(checking-parsed),epsilon/100)
        self.assertEqual(checking,source)  # does NOT cure the physical discrepancy

    def test_T06_area_and_G_orders_are_distinct_not_native_results(self):
        for name in ('T06.A','T06.G'):
            with self.subTest(name=name):
                physical,checking,hypothesis=m.constant_targets(self.rows[name],m.pi_enclosure())
                self.assertEqual(abs(checking-hypothesis),m.binary64_ulp(checking))
                self.assertFalse(m.physical_certificate(checking,physical,64*m.binary64_ulp(checking))[0])
        self.assertFalse(self.plan['constantArithmeticLedger']['sourceOrderIsNativeObservation'])

    def test_seven_known_refusals_all_fourteen_static_exports(self):
        report=self.audit()
        self.assertEqual(report['staticExports'],14)
        self.assertEqual(report['physical100xFailures'],
            ['T02.G','T06.A','T06.G','T07.G','T08.G','T10.G','T_Plug.C'])
        self.assertEqual(report['arithmeticGate'],'REFUSED_UNCHANGED_CHECKING_CENTRES')
        self.assertFalse(report['nativeObserved']);self.assertFalse(report['referenceBundleWritten'])

    def test_unchanged_real_reference_operations_match_pinned_bits(self):
        # Cross-check ONLY after independent targets are constructed; never use
        # production-derived graph/results to define an oracle enclosure.
        import h1.reference as actual
        facts=json.loads((HERE/'reference-facts.json').read_text())
        independent={r['export']:r for r in self.audit()['rows']}
        for name,row in independent.items():
            cid,field=name.split('.')
            if field=='C':
                b=facts['bodies'][cid];value=b['m']*b['c']
            elif field=='A':value=actual.area(facts['rods'][cid])
            else:value=actual.conductance(facts['rods'][cid])
            self.assertEqual(value.hex(),row['checkingHex'],name)

    def test_nearest_physical_witness_is_feasible_but_never_adopted(self):
        report=self.audit()
        self.assertTrue(all(r['witnessPhysical100x'] for r in report['rows']))
        self.assertTrue(all(r['witnessAdopted'] is False for r in report['rows']))
        self.assertFalse(m.check()['referenceAccuracyCertified'])
        self.assertIn('STATIC_CHECKING_CENTRES_FAIL_PHYSICAL_100X_BOUND',m.check()['executionBlockers'])

    def test_rounding_consistency_does_not_replace_physical_gate(self):
        self.assertTrue(all(r['roundingConsistency'].startswith('EXACT_MATCH') for r in self.audit()['rows']))
        self.assertTrue(self.audit()['physical100xFailures'])
        self.mutate_refused(lambda x:x.__setitem__('representationPassMayReplacePhysical100x',True))

    def test_exact_budget_boundary_and_80x_refusal(self):
        F=m.Fraction
        self.assertTrue(m.physical_certificate(F(1,100),(F(0),F(0)),F(1))[0])
        self.assertFalse(m.physical_certificate(F(1,100)+F(1,10**20),(F(0),F(0)),F(1))[0])
        self.assertFalse(m.physical_certificate(F(1,80),(F(0),F(0)),F(1))[0])
        with self.assertRaises(ValueError):m.physical_certificate(F(0),(F(1),F(0)),F(1))

    def test_missing_or_duplicate_static_export_refused(self):
        self.mutate_refused(lambda x:x['entries'].pop())
        self.mutate_refused(lambda x:x['entries'].__setitem__(1,deepcopy(x['entries'][0])))

    def test_changed_input_or_circular_diameter_refused(self):
        self.mutate_refused(lambda x:next(e for e in x['entries'] if e['export']=='T06.A')['exactInputs'].__setitem__('d','0.032'))

    def test_operation_order_cannot_be_refit(self):
        self.mutate_refused(lambda x:next(e for e in x['entries'] if e['export']=='T06.A').__setitem__('checkingOperationTree','ADAPT_TO_NATIVE'))
        self.mutate_refused(lambda x:x.__setitem__('postOutputTargetSelectionAllowed',True))

    def test_pi_and_native_attestation_cannot_be_invented(self):
        self.mutate_refused(lambda x:x['pi'].__setitem__('binary64Hex','0x1.921fb54442d19p+1'))
        self.mutate_refused(lambda x:x['pi'].__setitem__('compilerMslValueAttested',True))
        self.mutate_refused(lambda x:x.__setitem__('sourceOrderIsNativeObservation',True))

    def test_constant_exemption_or_looser_bound_refused(self):
        self.mutate_refused(lambda x:x.__setitem__('constantExemptionsAllowed',True))
        self.mutate_refused(lambda x:x.__setitem__('referenceErrorDivisor',80))
        self.mutate_refused(lambda x:x.__setitem__('nativeComparisonUlpMultiplier',128))
        self.mutate_refused(lambda x:x.__setitem__('mandatory100xTarget','BINARY_OPERATION_AGREEMENT_ONLY'))

    def test_witness_cannot_silently_replace_checking_bits_or_references(self):
        self.mutate_refused(lambda x:x['correctlyRoundedPhysicalWitness'].__setitem__('adoptedAsCheckingValue',True))
        self.mutate_refused(lambda x:x['correctlyRoundedPhysicalWitness'].__setitem__('mayRewriteCurrentOrHistoricalReferences',True))
        self.mutate_refused(lambda x:next(e for e in x['entries'] if e['export']=='T10.G').__setitem__('unchangedCheckingHex','0x1.f9db22d0e5604p-6'))

    def test_invalid_pi_enclosure_and_reference_budget_refused(self):
        with self.assertRaises(ValueError):m.pi_enclosure(0)
        with self.assertRaises(ValueError):m.physical_certificate(m.Fraction(0),(m.Fraction(0),m.Fraction(1)),m.Fraction(0))

    def test_reassociation_not_granted_by_plan(self):
        self.mutate_refused(lambda x:x.__setitem__('fusedOrReassociatedOperationsAllowedWithoutNewReview',True))


if __name__=='__main__':unittest.main()
