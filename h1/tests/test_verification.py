"""Author-written checking tests. All candidate CSVs here are SYNTHETIC.

Seven baseline histories use explicit scalar analytic formulas, not the matrix
reference under test. Other exposed graph fixtures exercise algorithms and fault
injection only; none is C1 or a native physical experiment.
"""
import ast
import copy
import csv
from dataclasses import replace
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from h1 import reference as ref
from h1.model import Refusal, parse_model, topology, requests, internal_exports
from h1.study import load_study
from h1.verification import bind_reference, candidate_receipt, check_candidate
from h1.verify import main

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT/'cases'


def csv_text(grid, columns):
    out = io.StringIO(); writer = csv.writer(out); keys = sorted(columns)
    writer.writerow(['time']+keys)
    for i, t in enumerate(grid):
        writer.writerow([format(float(t), '.17g')]+[format(float(columns[k][i]), '.17g') for k in keys])
    return out.getvalue()


def analytic(name, grid):
    """Standalone explicit physical expectations, not production-computed values."""
    t = np.asarray(grid); cols = {}
    def put(owner, **fields):
        for f, value in fields.items():
            cols[owner+'.'+f] = np.broadcast_to(value, t.shape).copy()
    def rod(owner, a, b, q, g, area=None):
        put(owner, T_a=a, T_b=b, Q_flow=q, G=g)
        cols[owner+'.port_a.Q_flow'] = np.broadcast_to(q, t.shape).copy()
        cols[owner+'.port_b.Q_flow'] = np.broadcast_to(-np.asarray(q), t.shape).copy()
        if area is not None: put(owner, A=area)
    if name == 'S1':
        area = math.pi*0.01**2
        g1, g2 = 384.928*area/0.75, 46.024*area/1.25
        q = 100/(1/g1+1/g2); tj = 373.15-q/g1
        put('hot', T=373.15, Q_to_network=q); put('cold', T=273.15, Q_to_network=-q)
        rod('copper',373.15,tj,q,g1,area); rod('steel',tj,273.15,q,g2,area)
    elif name == 'D1':
        decay = np.exp(-t/2500); temp=353.15-60*decay; q=12*decay
        put('body', T=temp, Q_in=q, C=500., dU=30000*(1-decay))
        put('reservoir', T=353.15, Q_to_network=q); rod('rod',353.15,temp,q,.2)
    elif name == 'ISO':
        put('body', T=293.15, C=500., Q_in=0., dU=0.)
    else:
        ti, tj = (308.15,308.15) if name=='EQ' else (293.15,353.15) if name=='REV' else (353.15,293.15)
        g = .4 if name=='D2_K2' else .2
        tau = 937.5 if name=='D2_K2' else 1875.
        equilibrium = (500*ti+1500*tj)/2000
        delta = (ti-tj)*np.exp(-t/tau)
        a, b = equilibrium+.75*delta, equilibrium-.25*delta
        put('hot', T=a, C=500., Q_in=-g*delta, dU=500*(a-ti))
        put('cold', T=b, C=1500., Q_in=g*delta, dU=1500*(b-tj))
        rod('rod',a,b,g*delta,g)
    return cols


class VerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.studies, cls.bundles, cls.specs = {}, {}, {}
        for p in sorted((ROOT/'reference_cases').glob('*.json')):
            name=p.stem
            cls.studies[name]=load_study(CASES/name/'study.json', CASES)
            cls.specs[name]=ref.read_reference(p)
            cls.bundles[name]=ref.prepare(cls.specs[name])

    def result(self, name='D2', mutate=None, study=None, bundle=None):
        s=study or self.studies[name]; b=bundle or self.bundles[name]
        cols=analytic(name,b['grid'])
        if mutate: mutate(cols)
        text=csv_text(b['grid'],cols)
        return check_candidate(s,b,text,candidate_receipt(s,b,text),b['seal'])

    def test_all_seven_closed_form_histories_pass_without_native_claim(self):
        for name in self.studies:
            with self.subTest(name=name):
                r=self.result(name)
                self.assertEqual(r['status'],'checks_passed')
                self.assertFalse(r['nativeQualified']); self.assertFalse(r['nativeExecuted'])
                self.assertEqual(r['evidenceKind'],'synthetic')
                self.assertTrue(all(q['status']=='diagnostic_only' for q in r['requests']))

    def test_signed_initial_flow_expectations(self):
        for name, field, value in [('D1','body.Q_in',12),('D1','reservoir.Q_to_network',12),
                                   ('D2','hot.Q_in',-12),('D2','cold.Q_in',12),
                                   ('D2','rod.port_b.Q_flow',-12),('REV','rod.Q_flow',-12),
                                   ('EQ','rod.Q_flow',0),('ISO','body.Q_in',0)]:
            self.assertAlmostEqual(self.bundles[name]['columns'][field][0],value,places=11)

    def test_reference_math_does_not_import_production(self):
        imports=[n.module for n in ast.walk(ast.parse(Path(ref.__file__).read_text())) if isinstance(n,ast.ImportFrom)]
        self.assertFalse(any(x and x.startswith(('h1','model','study','policy')) for x in imports))
        with patch('h1.model.parse_model',side_effect=AssertionError('parser is not a reference')):
            ref.prepare(self.specs['ISO'])

    def test_zero_modes_and_isolated_initial_state(self):
        for name in ('EQ','ISO'):
            for k, v in self.bundles[name]['columns'].items():
                self.assertTrue(all(x==v[0] for x in v))
        r=self.result('ISO'); self.assertEqual(r['status'],'checks_passed')

    def test_reference_facts_mismatch_refuses(self):
        spec=copy.deepcopy(self.specs['D2']);spec['bodies']['hot']['m']=1.01
        with self.assertRaisesRegex(Refusal,'reference_binding'): bind_reference(self.studies['D2'],spec)

    def test_reference_connection_reversal_refuses(self):
        spec=copy.deepcopy(self.specs['D2']);spec['rods']['rod']['a']='right';spec['rods']['rod']['b']='left'
        with self.assertRaisesRegex(Refusal,'reference_binding'): bind_reference(self.studies['D2'],spec)

    def test_reference_or_study_identity_mismatch_refuses(self):
        spec=copy.deepcopy(self.specs['D2']);spec['studySha256']='0'*64
        with self.assertRaisesRegex(Refusal,'reference_identity'): bind_reference(self.studies['D2'],spec)

    def test_bad_input_domains_and_float_graph(self):
        for change in [lambda s:s['bodies']['hot'].update(c=0),
                       lambda s:s['rods']['rod'].update(k=float('inf')),
                       lambda s:s['bodies']['cold'].update(node='left'),
                       lambda s:s['nodes'].append('unused')]:
            s=copy.deepcopy(self.specs['D2']);change(s)
            with self.assertRaises(ref.ReferenceError):ref.prepare(s)

    def test_duplicate_reference_json_key(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ref.json';p.write_text('{"id":"a","id":"b"}')
            with self.assertRaisesRegex(ref.ReferenceError,'duplicate'):ref.read_reference(p)

    def test_wrong_rod_sign_detected(self):
        r=self.result(mutate=lambda c:c['rod.Q_flow'].__imul__(-1))
        failed={c['check'] for c in r['checks'] if not c['passed']}
        self.assertIn('rod_orientation_a:rod',failed); self.assertIn('reference:rod.Q_flow',failed)
        self.assertTrue(all(q['status']=='not_computed' for q in r['requests']))

    def test_wrong_second_port_not_manufactured_from_first(self):
        r=self.result(mutate=lambda c:c['rod.port_b.Q_flow'].__imul__(-1))
        self.assertTrue(any(c['check']=='rod_conservation:rod' and not c['passed'] for c in r['checks']))

    def test_missing_second_port_refused(self):
        with self.assertRaisesRegex(Refusal,'missing required output'):
            self.result(mutate=lambda c:c.pop('rod.port_b.Q_flow'))

    def test_local_energy_errors_cannot_cancel_globally(self):
        def corrupt(c): c['hot.dU']+=1; c['cold.dU']-=1
        r=self.result(mutate=corrupt)
        checks={c['check']:c['passed'] for c in r['checks']}
        self.assertTrue(checks['network_energy:0'])
        self.assertFalse(checks['energy_ownership:hot']);self.assertFalse(checks['energy_ownership:cold'])
        self.assertFalse(checks['body_integral:hot'])

    def test_boundary_supply_and_body_integral_detect_error(self):
        r=self.result('D1',mutate=lambda c:c['reservoir.Q_to_network'].__imul__(-1))
        self.assertTrue(any(c['check']=='network_energy:0' and not c['passed'] for c in r['checks']))

    def test_initial_state_has_stricter_own_check(self):
        def corrupt(c): c['hot.T'][0]+=2e-6
        r=self.result(mutate=corrupt)
        self.assertTrue(any(c['check']=='initial:hot' and not c['passed'] for c in r['checks']))

    def test_parameter_export_not_allowed_trajectory_tolerance(self):
        r=self.result(mutate=lambda c:c['rod.G'].__imul__(1.00001))
        self.assertTrue(any(c['check']=='reference:rod.G' and not c['passed'] for c in r['checks']))

    def test_reference_seal_catches_allowance_tampering(self):
        s=self.studies['D2'];b=copy.deepcopy(self.bundles['D2']);b['allowances']['rod.Q_flow']=1e99
        text=csv_text(b['grid'],analytic('D2',b['grid']))
        with self.assertRaisesRegex(Refusal,'reference_identity'):
            check_candidate(s,b,text,candidate_receipt(s,b,text),self.bundles['D2']['seal'])

    def test_candidate_hash_incomplete_and_fake_native_labels_refuse(self):
        s=self.studies['D2'];b=self.bundles['D2'];text=csv_text(b['grid'],analytic('D2',b['grid']))
        for update in [dict(csvSha256='0'*64),dict(dataComplete=False),dict(evidenceKind='native_qualified'),dict(modelSha256='0'*64)]:
            receipt=candidate_receipt(s,b,text);receipt.update(update)
            with self.assertRaises(Refusal):check_candidate(s,b,text,receipt,b['seal'])

    def test_missing_time_sample_never_filled(self):
        s=self.studies['D2'];b=self.bundles['D2'];columns=analytic('D2',b['grid'])
        text=csv_text(b['grid'][:-1],{k:v[:-1] for k,v in columns.items()})
        with self.assertRaisesRegex(Refusal,'missing or extra output samples'):
            check_candidate(s,b,text,candidate_receipt(s,b,text),b['seal'])

    def test_constant_steady_has_no_physical_time_claim(self):
        r=self.result('S1');self.assertEqual(r['timeMeaning'],'algebraic_evaluation_index')

    def test_empty_public_requests_do_not_disable_physics_checks(self):
        s=self.studies['D2']; data=copy.deepcopy(s.data);data['requests']=[]
        s=replace(s,data=data,sha256='1'*64,request_report=requests(s.model,[]))
        spec=copy.deepcopy(self.specs['D2']);spec['studySha256']=s.sha256;b=ref.prepare(spec)
        r=self.result(study=s,bundle=b,mutate=lambda c:c['cold.Q_in'].__imul__(-1))
        self.assertEqual(r['status'],'checks_failed');self.assertEqual(r['requests'],[])

    def test_cond_revision_changes_rate_not_asymptotic_energy_mean(self):
        for name,tau in [('D2',1875),('D2_K2',937.5)]:
            b=self.bundles[name];i=200;t=b['grid'][i]
            self.assertAlmostEqual(b['columns']['hot.T'][i]-b['columns']['cold.T'][i],60*math.exp(-t/tau),places=10)
            weighted=(500*b['columns']['hot.T'][i]+1500*b['columns']['cold.T'][i])/2000
            self.assertAlmostEqual(weighted,308.15,places=11)

    def test_reference_crosscheck_detects_corrupted_primary_algorithm(self):
        original = ref.expm
        def broken(matrix):
            result = original(matrix)
            result[..., 0, -1] += .01
            return result
        with patch('h1.reference.expm', side_effect=broken):
            with self.assertRaisesRegex(ref.ReferenceError, 'disagree'):
                ref.prepare(self.specs['D1'])

    def test_coarse_reference_grid_refuses_without_changing_physics(self):
        spec=copy.deepcopy(self.specs['D1']);spec['rods']['rod']['k']=1000.0
        before=copy.deepcopy(spec)
        with self.assertRaisesRegex(ref.ReferenceError,'quadrature too coarse'):ref.prepare(spec)
        self.assertEqual(spec,before)

    def test_overflowing_reference_area_refuses(self):
        spec=copy.deepcopy(self.specs['S1']);spec['rods']['copper']['d']=1e308
        with self.assertRaisesRegex(ref.ReferenceError,'area overflow'):ref.prepare(spec)

    def test_unattested_output_cannot_become_native_accepted(self):
        s=self.studies['ISO'];b=self.bundles['ISO'];text=csv_text(b['grid'],analytic('ISO',b['grid']))
        r=check_candidate(s,b,text,candidate_receipt(s,b,text,'unattested_output'),b['seal'])
        self.assertEqual(r['status'],'checks_passed');self.assertFalse(r['nativeQualified'])
        self.assertTrue(all(q['status']=='diagnostic_only' for q in r['requests']))

    def test_cli_prepare_never_overwrites_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'reference.json'
            args=['prepare','--study',str(CASES/'ISO/study.json'),'--root',str(CASES),
                  '--reference',str(ROOT/'reference_cases/ISO.json'),'--out',str(out)]
            with patch('sys.stdout',new=io.StringIO()),patch('subprocess.Popen',side_effect=AssertionError('no execution')):
                self.assertEqual(main(args),0);before=out.read_bytes();self.assertEqual(main(args),2)
            self.assertEqual(out.read_bytes(),before)

    def test_cli_check_synthetic_and_read_only(self):
        s=self.studies['ISO'];b=self.bundles['ISO'];text=csv_text(b['grid'],analytic('ISO',b['grid']))
        with tempfile.TemporaryDirectory() as d:
            paths=[Path(d)/n for n in ('bundle.json','data.csv','receipt.json')]
            for p, value in zip(paths,[json.dumps(b),text,json.dumps(candidate_receipt(s,b,text))]):
                p.write_bytes(value.encode("utf-8"))
            before=[p.read_bytes() for p in paths]
            args=['check','--study',str(s.path),'--root',str(CASES),'--bundle',str(paths[0]),'--csv',str(paths[1]),
                  '--receipt',str(paths[2]),'--seal',b['seal']]
            stream=io.StringIO()
            with patch('sys.stdout',new=stream),patch('subprocess.Popen',side_effect=AssertionError('no execution')):
                self.assertEqual(main(args),0)
            self.assertFalse(json.loads(stream.getvalue())['nativeQualified'])
            self.assertEqual(before,[p.read_bytes() for p in paths])


class ExposedNetworkTests(unittest.TestCase):
    def skeleton(self):
        return dict(schema='sim_heat.reference/1',id='Exposed',mode='steady',modelSha256='0'*64,
                    studySha256='0'*64,analysis={},provenance='Author-created, development-exposed algorithm fixture, not C1.',
                    nodes=[],bodies={},boundaries={},rods={})

    def test_generic_steady_branch_and_junction(self):
        s=self.skeleton();s['nodes']=['a','j','b','c']
        s['boundaries']={n:{'node':n,'T':v} for n,v in [('a',350.),('b',300.),('c',280.)]}
        s['rods']={'r_'+n:dict(kind='RodArea',a=n,b='j',k=1.,L=1.,A=1.) for n in ('a','b','c')}
        b=ref.prepare(s)
        for n in ('a','b','c'):self.assertAlmostEqual(b['columns']['r_'+n+'.T_b'][0],310.)
        self.assertAlmostEqual(sum(b['columns']['r_'+n+'.Q_flow'][0] for n in ('a','b','c')),0.,places=12)

    def test_generic_transient_closed_loop_against_closed_form(self):
        s=self.skeleton();s.update(mode='transient',nodes=['a','b','c'],
            analysis={'startTime':0,'stopTime':5.,'intervals':1000,'solver':'dassl','tolerance':1e-8})
        s['bodies']={n:dict(node=n,m=1.,c=1.,T_initial=t) for n,t in [('a',330.),('b',300.),('c',270.)]}
        s['rods']={}
        for name,a,b in [('ab','a','b'),('bc','b','c'),('ca','c','a')]:
            s['rods'][name]=dict(kind='RodArea',a=a,b=b,k=1.,L=1.,A=1.)
        b=ref.prepare(s)
        for n,offset in [('a',30.),('b',0.),('c',-30.)]:
            np.testing.assert_allclose(b['columns'][n+'.T'],300+offset*np.exp(-3*np.array(b['grid'])),atol=1e-10,rtol=0)

    def test_algebraic_junction_elimination_dynamic(self):
        s=ref.read_reference(ROOT/'reference_cases/D2.json');s['nodes'].append('mid')
        del s['rods']['rod']
        for name,a,b in [('first','left','mid'),('second','mid','right')]:
            s['rods'][name]=dict(kind='RodArea',a=a,b=b,k=.4,L=1.,A=1.)
        b=ref.prepare(s);t=np.array(b['grid'])
        np.testing.assert_allclose(np.array(b['columns']['hot.T'])-b['columns']['cold.T'],60*np.exp(-t/1875),rtol=0,atol=1e-10)

    def test_floating_reference_rejected(self):
        s=self.skeleton();s.update(nodes=['a','b'],rods={'r':dict(kind='RodArea',a='a',b='b',k=1.,L=1.,A=1.)})
        with self.assertRaises(ref.ReferenceError):ref.prepare(s)

    def test_small_flow_scale_not_diluted_by_huge_connected_or_disconnected_rod(self):
        for disconnected in (False,True):
            with self.subTest(disconnected=disconnected):
                s=self.skeleton();s['nodes']=['a','b']
                s['boundaries']={'warm':dict(node='a',T=310.),'cool':dict(node='b',T=300.)}
                s['rods']={'small':dict(kind='RodArea',a='a',b='b',k=.001,L=1.,A=1.),
                           'huge':dict(kind='RodArea',a='a',b='b',k=1e8,L=1.,A=1.)}
                if disconnected:
                    s['nodes']+=['c','d'];s['boundaries'].update(warm2=dict(node='c',T=310.),cool2=dict(node='d',T=300.))
                    s['rods']['huge'].update(a='c',b='d')
                b=ref.prepare(s)
                self.assertAlmostEqual(b['scales']['small.Q_flow'],.01)
                self.assertLess(b['allowances']['small.Q_flow'],1.1e-6)
                self.assertGreater(.001,b['allowances']['small.Q_flow'])
                self.assertGreater(b['allowances']['huge.Q_flow'],100)

    def test_f1_heterogeneous_flow_fault_rejected_end_to_end(self):
        s=self.skeleton();s['nodes']=['a','b']
        s['boundaries']={'warm':dict(node='a',T=310.),'cool':dict(node='b',T=300.)}
        s['rods']={'small':dict(kind='RodArea',a='a',b='b',k=.001,L=1.,A=1.),
                   'huge':dict(kind='RodArea',a='a',b='b',k=1e8,L=1.,A=1.)}
        text_model = """model Exposed
SimHeat.FixedTemperature warm(T=310); SimHeat.FixedTemperature cool(T=300);
SimHeat.RodArea small(k=.001,L=1,A=1); SimHeat.RodArea huge(k=1e8,L=1,A=1);
equation connect(small.port_a,warm.port); connect(small.port_b,cool.port);
connect(huge.port_a,warm.port); connect(huge.port_b,cool.port); end Exposed;"""
        # Test-only descriptor, not an authoring/transfer claim.
        model=parse_model(text_model)
        base=load_study(CASES/'S1/study.json',CASES)
        data=copy.deepcopy(base.data);data.update(id='Exposed',requests=[])
        mh=hashlib.sha256(text_model.encode()).hexdigest()
        study=replace(base,data=data,model=model,model_sha256=mh,sha256='2'*64,
                      topology=topology(model,'steady'),request_report=requests(model,[]))
        s.update(modelSha256=mh,studySha256=study.sha256)
        bundle=ref.prepare(s);columns={k:np.array(v) for k,v in bundle['columns'].items()}
        columns['small.Q_flow']+=.001
        raw=csv_text(bundle['grid'],columns)
        r=check_candidate(study,bundle,raw,candidate_receipt(study,bundle,raw),bundle['seal'])
        failure=next(c for c in r['checks'] if c['check']=='reference:small.Q_flow')
        self.assertFalse(failure['passed']);self.assertGreater(failure['maximumRatio'],900)

    def test_weak_positive_mode_is_not_silently_a_conserved_zero(self):
        s=ref.read_reference(ROOT/'reference_cases/D2.json')
        s['nodes'].append('bath');s['boundaries']['bath']=dict(node='bath',T=290.)
        s['rods']['weak']=dict(kind='RodArea',a='left',b='bath',k=1e-20,L=1.,A=1.)
        with self.assertRaisesRegex(ref.ReferenceError,'slow mode unresolved'):ref.prepare(s)

    def test_local_energy_scale_not_total_capacity(self):
        s=ref.read_reference(ROOT/'reference_cases/ISO.json')
        s['nodes']+=['huge'];s['bodies']['large']=dict(node='huge',m=1e10,c=1e10,T_initial=1e5)
        b=ref.prepare(s)
        self.assertEqual(b['scales']['body.dU'],0.)
        self.assertEqual(b['allowances']['body.dU'],.001)


if __name__ == '__main__':
    unittest.main()
