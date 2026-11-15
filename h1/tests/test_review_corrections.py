"""R1/R2/R6 regressions: exposed analytical/synthetic tests, never native evidence."""
import copy
from dataclasses import replace
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from h1 import reference as ref, temporal
from h1.decoder import decode_csv
from h1.model import Refusal
from h1.policy import match_grid, time_allowance
from h1.study import load_study
from h1.verification import candidate_receipt, check_candidate
from h1.verify import main
from test_verification import ROOT, CASES, analytic, csv_text


def fast_columns(grid):
    """Separately written D1 formulas at the ACTUAL candidate times."""
    t = np.asarray(grid, dtype=float)
    e = np.exp(-t/5e-8)
    temp, q = 353.15-60*e, 12*e
    constant = lambda v: np.full(len(t), v)
    return {'body.T': temp, 'body.C': constant(1e-8), 'body.Q_in': q,
            'body.dU': 6e-7*(1-e), 'reservoir.T': constant(353.15),
            'reservoir.Q_to_network': q, 'rod.T_a': constant(353.15),
            'rod.T_b': temp, 'rod.G': constant(.2), 'rod.Q_flow': q,
            'rod.port_a.Q_flow': q, 'rod.port_b.Q_flow': -q}


class TemporalCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.scratch.cleanup)
        root = Path(cls.scratch.name)
        source = (CASES/'D1/model.mo').read_text().replace('m=1.0,c=500.0', 'm=1e-8,c=1.0')
        cls.model_bytes = source.encode()
        (root/'model.mo').write_bytes(cls.model_bytes)
        data = json.loads((CASES/'D1/study.json').read_text())
        data['id'] = 'R1_Fast'
        data['model']['sha256'] = hashlib.sha256(cls.model_bytes).hexdigest()
        data['analysis']['stopTime'] = 1e-6
        data['requests'].append({'id':'difference','op':'temperatureDifference',
                                 'a':'reservoir.port','b':'body.port'})
        raw = json.dumps(data, indent=2).encode()
        (root/'study.json').write_bytes(raw)
        cls.study = load_study(root/'study.json', root)
        s = ref.read_reference(ROOT/'reference_cases/D1.json')
        s.update(id=data['id'], modelSha256=data['model']['sha256'],
                 studySha256=hashlib.sha256(raw).hexdigest(), analysis=data['analysis'])
        s['bodies']['body'].update(m=1e-8, c=1.)
        s['provenance'] = 'R1 analytical counterexample, development-exposed synthetic regression.'
        cls.spec = s
        cls.bundle = ref.prepare(s)

    def check_at(self, times, bundle=None):
        b = bundle or self.bundle
        text = csv_text(times, fast_columns(times))
        return check_candidate(self.study, b, text, candidate_receipt(self.study,b,text), b['seal'])

    def test_counterexample_old_matching_accepts_harmful_shift(self):
        g = self.bundle['grid']; old = time_allowance(tuple(g))
        shifted = list(g); shifted[1] += .5*old
        match_grid(tuple(g), tuple(shifted))
        error = abs(fast_columns(shifted)['body.T'][1]-fast_columns(g)['body.T'][1])
        self.assertGreater(error/self.bundle['allowances']['body.T'], 800)
        with self.assertRaisesRegex(Refusal, 'time_sensitivity'):
            self.check_at(shifted)

    def test_correct_trajectory_at_tightened_shift_passes_all_checks(self):
        g = self.bundle['grid']; epsilon = self.bundle['temporalPolicy']['maximumShift']
        shifted = [t + epsilon/2 for t in g[:-1]]+[g[-1]]
        r = self.check_at(shifted)
        self.assertEqual(r['status'], 'checks_passed')
        self.assertTrue(all(c['passed'] for c in r['checks']))
        self.assertGreater(r['temporalAssociation']['maximumObservedShift'], 0)
        self.assertTrue(any(c['check']=='body_integral:body' for c in r['checks']))
        self.assertTrue(any(c['check']=='observation:difference' for c in r['checks']))
        self.assertFalse(r['nativeQualified']); self.assertFalse(r['nativeExecuted'])

    def test_initial_check_is_in_the_predeclared_budget(self):
        p=self.bundle['temporalPolicy']; dt=Fraction(p['maximumShift'])
        self.assertEqual(p['limitingConstraint'], 'initial:body')
        self.assertLessEqual(dt*Fraction(p['derivativeBounds']['body.T']), Fraction(1e-6)/100)

    def test_every_output_has_a_window_wide_rate_budget(self):
        p=self.bundle['temporalPolicy'];dt=Fraction(p['maximumShift'])
        self.assertEqual(set(p['derivativeBounds']),set(self.bundle['columns']))
        for key,rate in p['derivativeBounds'].items():
            self.assertLessEqual(dt*Fraction(rate),Fraction(self.bundle['allowances'][key])/100)
        self.assertGreater(p['derivativeBounds']['body.Q_in'],0)
        self.assertGreater(p['derivativeBounds']['body.dU'],0)
        self.assertEqual(p['derivativeBounds']['rod.G'],0)

    def test_difference_budget_covers_any_port_pair(self):
        p=self.bundle['temporalPolicy'];fastest=max(p['nodeTemperatureRateBounds'].values())
        self.assertLessEqual(2*Fraction(fastest)*Fraction(p['maximumShift']), Fraction(1e-5)/100)

    def test_sensitivity_below_timestamp_resolution_refuses(self):
        s=copy.deepcopy(self.spec);s['bodies']['body']['m']=1e-24
        with self.assertRaisesRegex(temporal.TemporalError, 'timestamp resolution'):
            temporal.make_policy(s,self.bundle['grid'],self.bundle['allowances'])

    def test_endpoint_extrapolation_refuses(self):
        for index,sign in ((0,-1),(-1,1)):
            shifted=list(self.bundle['grid']);shifted[index]+=sign*self.bundle['temporalPolicy']['maximumShift']/2
            with self.assertRaisesRegex(Refusal,'reference time domain'):
                self.check_at(shifted)

    def test_legacy_bundle_not_silently_upgraded(self):
        b=copy.deepcopy(self.bundle);b['schema']='sim_heat.reference_bundle/1';b.pop('temporalPolicy')
        b.pop('seal');b['seal']=ref.fingerprint(b)
        with self.assertRaisesRegex(Refusal,'reference_identity'):
            self.check_at(b['grid'],b)

    def test_temporal_policy_cannot_be_relaxed_by_resealing(self):
        b=copy.deepcopy(self.bundle);b['temporalPolicy']['maximumShift']*=100
        b.pop('seal');b['seal']=ref.fingerprint(b)
        with self.assertRaisesRegex(Refusal,'time_sensitivity'):
            self.check_at(b['grid'],b)

    def test_exact_matching_boundaries_and_one_ulp_beyond(self):
        grid=(0.,1.,2.); eps=2.**-30
        for sign in (-1,1):
            edge=1.+sign*eps
            match_grid(grid,(0.,edge,2.),maximum_shift=eps)
            beyond=math.nextafter(edge, -math.inf if sign<0 else math.inf)
            with self.assertRaisesRegex(Refusal,'time_sensitivity'):
                match_grid(grid,(0.,beyond,2.),maximum_shift=eps)

    def test_rates_are_not_estimated_from_reference_samples(self):
        # Far-end body's derivative starts at zero but becomes positive later.
        s=copy.deepcopy(self.spec);s['nodes']=['a','b','c'];s['boundaries']={}
        s['bodies']={n:dict(node=n,m=1.,c=1.,T_initial=t) for n,t in [('a',350.),('b',300.),('c',300.)]}
        s['rods']={n:dict(kind='RodArea',a=a,b=b,k=1.,L=1.,A=1.)
                   for n,a,b in [('ab','a','b'),('bc','b','c')]}
        with patch('h1.reference.calculate',side_effect=AssertionError('no sampled rates')):
            outputs, nodes=temporal.derivative_bounds(s)
        actual_at_half=25*math.exp(-.5)-25*math.exp(-1.5)
        self.assertGreater(actual_at_half,0);self.assertGreaterEqual(outputs['c.T'],actual_at_half)
        self.assertEqual(nodes['c'],50.)

    def test_junction_rate_inherits_conservative_anchor_bound(self):
        s=copy.deepcopy(self.spec);s['nodes'].append('junction')
        original=s['rods'].pop('rod');a,b=original['a'],original['b']
        s['rods']={'r1':dict(kind='RodArea',a=a,b='junction',k=.4,L=1.,A=1.),
                   'r2':dict(kind='RodArea',a='junction',b=b,k=.4,L=1.,A=1.)}
        outputs,nodes=temporal.derivative_bounds(s)
        self.assertEqual(nodes['junction'],nodes[b])
        self.assertGreater(outputs['r1.Q_flow'],0)

    def test_body_integral_timing_effect_fits_existing_allowance(self):
        b=self.bundle;p=b['temporalPolicy'];dt=Fraction(p['maximumShift'])
        for t in (Fraction(0),Fraction(b['grid'][-1])):
            effect=dt*(Fraction(p['derivativeBounds']['body.dU'])+t*Fraction(p['derivativeBounds']['body.Q_in']))
            budget=(Fraction(b['allowances']['body.dU'])+t*Fraction(b['allowances']['body.Q_in']))/100
            self.assertLessEqual(effect,budget)

    def test_circular_rate_upper_bound_and_isothermal_network(self):
        s=copy.deepcopy(self.spec)
        rod=s['rods']['rod'];rod.update(kind='RodCircular',d=.02);rod.pop('A')
        outputs,_=temporal.derivative_bounds(s)
        actual_rate=60*(100*math.pi*.02**2/4/.5)/1e-8
        self.assertGreaterEqual(outputs['body.T'],actual_rate)
        s['bodies']['body']['T_initial']=s['boundaries']['reservoir']['T']
        outputs,nodes=temporal.derivative_bounds(s)
        self.assertTrue(all(x==0 for x in outputs.values()))
        self.assertTrue(all(x==0 for x in nodes.values()))

    def test_directed_conversion_is_conservative(self):
        for value in (Fraction(1,10),Fraction(1,3),Fraction(1,2**1075)):
            self.assertGreaterEqual(Fraction(temporal._directed(value,True)),value)
            self.assertLessEqual(Fraction(temporal._directed(value,False)),value)
        with self.assertRaisesRegex(temporal.TemporalError,'overflow'):
            temporal._directed(Fraction(10)**400,True)


class EvidenceCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study=load_study(CASES/'ISO/study.json',CASES)
        cls.bundle=ref.prepare(ref.read_reference(ROOT/'reference_cases/ISO.json'))

    def test_s1_note_correction_does_not_change_physical_facts(self):
        s=ref.read_reference(ROOT/'reference_cases/S1.json')
        self.assertNotIn('all other numbers are illustrative',s['provenance'])
        self.assertIn('Illustration 123 supplies',s['provenance'])
        self.assertEqual(s['rods']['copper']['L'],.75)
        self.assertEqual(s['rods']['steel']['L'],1.25)
        self.assertEqual(s['rods']['copper']['d'],.02)
        self.assertEqual(s['rods']['copper']['k'],384.928)
        self.assertEqual(s['rods']['steel']['k'],46.024)
        self.assertEqual(s['boundaries']['hot']['T'],373.15)
        self.assertEqual(s['boundaries']['cold']['T'],273.15)

    def test_extra_columns_are_reported_and_not_used_as_evidence(self):
        raw='time,body.T,extra\r\n0,300,not-a-number\r\n1,300,NaN\r\n'
        d=decode_csv(raw,('body.T',),(0.,1.))
        self.assertEqual(d['ignoredExtraColumns'],['extra'])
        self.assertEqual(set(d['columns']),{'time','body.T'})
        self.assertFalse(d['numericallyAccepted'])

    def test_duplicate_required_values_may_ignore_changed_extra_column(self):
        raw='time,T,note\n0,300,first\n0,300,second\n1,300,third\n'
        d=decode_csv(raw,('T',),(0.,1.))
        self.assertEqual(d['duplicateRowsCollapsed'],1)
        self.assertEqual(d['ignoredExtraColumns'],['note'])

    def test_cli_preserves_crlf_hash_and_input_bytes(self):
        s,b=self.study,self.bundle
        raw=csv_text(b['grid'],analytic('ISO',b['grid']))
        self.assertIn('\r\n',raw)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);data=p/'data.csv';bundle=p/'bundle.json';receipt=p/'receipt.json'
            data.write_bytes(raw.encode());bundle.write_text(json.dumps(b));receipt.write_text(json.dumps(candidate_receipt(s,b,raw)))
            args=['check','--study',str(s.path),'--root',str(CASES),'--bundle',str(bundle),
                  '--csv',str(data),'--receipt',str(receipt),'--seal',b['seal']]
            before=[q.read_bytes() for q in (data,bundle,receipt)]
            with patch('sys.stdout',new=io.StringIO()) as stream, patch('subprocess.Popen',side_effect=AssertionError('no native')):
                self.assertEqual(main(args),0)
            self.assertEqual(json.loads(stream.getvalue())['status'],'checks_passed')
            self.assertEqual(before,[q.read_bytes() for q in (data,bundle,receipt)])
            data.write_bytes(raw.replace('\r\n','\n').encode())
            with patch('sys.stdout',new=io.StringIO()) as stream:
                self.assertEqual(main(args),2)
            self.assertIn('candidate_identity',json.loads(stream.getvalue())['reason'])


if __name__ == '__main__':
    unittest.main()
