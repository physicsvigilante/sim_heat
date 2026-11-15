"""Tests for post-run common-time comparison; values here are synthetic."""
from copy import deepcopy
from pathlib import Path
import unittest
import numpy as np
from h1 import reference
from h1.model import Refusal
from tools.h1_compare_companions import compare
from tools.h1_resolution_campaign import companion
from h1.study import strict_json

ROOT=Path(__file__).resolve().parents[2]


class CompanionComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s=strict_json((ROOT/'h1/cases/D1/study.json').read_text())
        r=reference.read_reference(ROOT/'h1/reference_cases/D1.json')
        _,d=companion(s,r,'dense')
        cls.a=reference.prepare(r);cls.b=reference.prepare(d)

    def test_equal_reference_histories_pass(self):
        r=compare(self.a['columns'],self.a,self.b['columns'],self.b)
        self.assertEqual(r['status'],'checks_passed');self.assertEqual(r['commonSamples'],1001)
        self.assertFalse(r['nativeQualified'])

    def test_error_larger_than_existing_allowance_fails(self):
        values=deepcopy(self.b['columns']);values['body.T'][200]+=2*self.a['allowances']['body.T']
        r=compare(self.a['columns'],self.a,values,self.b)
        self.assertEqual(r['status'],'checks_failed')

    def test_changed_physics_refuses(self):
        b=deepcopy(self.b);b['spec']['bodies']['body']['m']=2
        with self.assertRaises(Refusal):compare(self.a['columns'],self.a,b['columns'],b)

    def test_looser_companion_allowance_refuses(self):
        b=deepcopy(self.b);b['allowances']['body.T']*=2
        with self.assertRaises(Refusal):compare(self.a['columns'],self.a,b['columns'],b)

    def test_grid_not_interpolated(self):
        b=deepcopy(self.b);b['grid'][2]+=1e-7
        with self.assertRaises(Refusal):compare(self.a['columns'],self.a,b['columns'],b)

    def test_dense_reference_quadrature_improves_separately(self):
        r=compare(self.a['columns'],self.a,self.b['columns'],self.b)
        q=next(v for v in r['quadratureDiagnostics'] if v['flow']=='body.Q_in')
        ratio=q['primaryReferenceGridErrorJ']/q['companionReferenceGridErrorJ']
        self.assertAlmostEqual(ratio,4,delta=1e-4)


if __name__=='__main__':unittest.main()
