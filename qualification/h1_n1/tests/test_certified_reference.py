"""Independent and adversarial offline-only tests for the N1 interval candidate."""
import json
from copy import deepcopy
from unittest.mock import patch
from decimal import Decimal
from fractions import Fraction as F
import math
from pathlib import Path
import tempfile
import unittest

import mpmath as mp
from qualification.h1_n1 import certified_reference as n
from qualification.h1_n1 import check_plan as reviewed_design

HERE = Path(__file__).resolve().parents[1]


class ArithmeticSafety(unittest.TestCase):
    def test_source_sha_is_fixed_and_unaltered(self):
        s=n.read_facts()
        self.assertEqual(s['modelSha256'],n.MODEL_SHA256)
        self.assertEqual(s['studySha256'],n.STUDY_SHA256)
        self.assertEqual(n.sha256((HERE/'reference-facts.json').read_bytes()).hexdigest(),n.FACTS_SHA256)
        self.assertEqual(n.sha256((HERE/'inputs/T/model.mo').read_bytes()).hexdigest(),n.MODEL_SHA256)
        self.assertEqual(n.sha256((HERE/'inputs/T/study.json').read_bytes()).hexdigest(),n.STUDY_SHA256)

    def test_changed_source_fact_refused_without_rescoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=(HERE/'reference-facts.json').read_text()
            p=Path(tmp)/'facts.json';p.write_text(data.replace('0.00013','0.00014',1))
            with self.assertRaisesRegex(ValueError,'byte identity mismatch'):
                n.read_facts(p)

    def test_f01_mutated_in_memory_facts_refused_before_construct(self):
        # The original GitHub source-fact file may be byte-pinned while a
        # public caller changes the mutable object returned by read_facts().
        # No trajectory computation or source identity receipt is permitted.
        edits = {
            'rod_conductivity': lambda x: x['rods']['T10'].__setitem__('k', Decimal('95.00000000000001')),
            'rod_orientation': lambda x: x['rods']['T10'].__setitem__('a', 'B'),
            'boundary_temperature': lambda x: x['boundaries']['T_Warm'].__setitem__('T', 366),
            'body_initial_temperature': lambda x: x['bodies']['T_Ridge'].__setitem__('T_initial', 338),
            'analysis_horizon': lambda x: x['analysis'].__setitem__('stopTime', 2401),
            'analysis_grid': lambda x: x['analysis'].__setitem__('intervals', 4800),
            'node_order': lambda x: x['nodes'].reverse(),
            'study_identity': lambda x: x.__setitem__('studySha256', '0'*64),
            'provenance_claim': lambda x: x.__setitem__('provenance', 'fabricated'),
            'unexpected_field': lambda x: x.__setitem__('unsafe_extra', True),
            'removed_field': lambda x: x['rods']['T06'].pop('d'),
            'typed_boolean_spoof': lambda x: x['analysis'].__setitem__('startTime', False),
            'float_instead_of_exact_decimal': lambda x: x['rods']['T10'].__setitem__('A', 0.00013),
        }
        for label, edit in edits.items():
            with self.subTest(mutation=label):
                supplied=deepcopy(n.read_facts())
                edit(supplied)
                with patch.object(n, 'construct', side_effect=AssertionError('forged object reached solver')) as build:
                    with self.assertRaisesRegex(ValueError, 'pinned source-facts object identity mismatch'):
                        n.certify(supplied, 2400)
                    build.assert_not_called()

    def test_f01_refusal_creates_no_output_directory(self):
        supplied=deepcopy(n.read_facts())
        supplied['boundaries']['T_Cool']['T']=Decimal('289.00000001')
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/'should-not-be-created'
            with patch.object(n, 'construct', side_effect=AssertionError('should not compute')) as build:
                with self.assertRaisesRegex(ValueError, 'pinned source-facts object identity mismatch'):
                    n.certify(supplied, 2400, output=dest)
                build.assert_not_called()
            self.assertFalse(dest.exists())

    def test_f01_unchanged_in_memory_facts_pass_identity_gate(self):
        supplied=deepcopy(n.read_facts())
        with patch.object(n, 'construct', side_effect=RuntimeError('trusted facts reached construct')) as build:
            with self.assertRaisesRegex(RuntimeError, 'trusted facts reached construct'):
                n.certify(supplied, 2400)
            build.assert_called_once()
            # Future modifications to a caller-owned object cannot change the
            # snapshot that actually drives the mathematical reference.
            self.assertIsNot(build.call_args.args[0], supplied)

    def test_f02_nonzero_affine_last_row_refuses_instead_of_false_enclosure(self):
        bad_matrices = [
            [[n.interval(1)]],  # old code returned [1,1] instead of exp(1/2400)
            [[n.interval(0), n.interval(0)], [n.interval(1), n.interval(0)]],
            [[n.interval(1), n.interval(0)], [n.I(-1, 1), n.interval(0)]],
        ]
        for i, bad in enumerate(bad_matrices):
            with self.subTest(counterexample=i):
                with self.assertRaisesRegex(ValueError, 'exactly zero affine last row'):
                    n.exp_step(bad, 2400)

    def test_f02_matrix_shape_and_types_refused(self):
        non_square = [
            [],
            [[n.interval(1), n.interval(0)]],
            [[n.interval(1)], [n.interval(0)]],
            [[n.interval(1), n.interval(0)], [n.interval(0)]],
            [[], []],
            n.identity(8),  # bounded source-only 7-state affine scope
        ]
        for i, bad in enumerate(non_square):
            with self.subTest(shape=i):
                with self.assertRaisesRegex(ValueError, 'square matrix'):
                    n.exp_step(bad, 2400)
        with self.assertRaisesRegex(ValueError, 'matrix entries must be bounded intervals'):
            n.exp_step([[n.interval(1), 0], [n.interval(0), n.interval(0)]], 2400)
        with self.assertRaisesRegex(ValueError, 'positive integer grid'):
            n.exp_step([[n.interval(1), n.interval(0)], [n.interval(0), n.interval(0)]], 0)

    def test_fixed_point_outward_endpoints_and_inversion(self):
        third=n.interval(F(1,3))
        self.assertTrue(third.contains(F(1,3)))
        self.assertLessEqual(third.lo*n.Q*3,n.Q*n.Q)
        self.assertTrue((third*n.interval(3)).contains(1))
        self.assertTrue((n.interval(-3)/n.interval(-2)).contains(F(3,2)))
        with self.assertRaisesRegex(ValueError,'zero'):
            n.interval(0).inv()
        with self.assertRaisesRegex(ValueError,'zero'):
            n.I(-1,1).inv()
        self.assertTrue((n.interval(-2)*n.interval(3)).contains(-6))
        self.assertTrue((n.interval(-2)*n.interval(-3)).contains(6))

    def test_matrix_exp_step_has_nonzero_tail_and_norm_guard(self):
        b=[[n.interval(1),n.interval(0)], [n.interval(0),n.interval(0)]]
        e,proof=n.exp_step(b,2400)
        with mp.workdps(90):
            target=mp.exp(mp.mpf(1)/2400)
            lo,hi=e[0][0].bounds()
            self.assertLessEqual(mp.mpf(lo.numerator)/lo.denominator,target)
            self.assertGreaterEqual(mp.mpf(hi.numerator)/hi.denominator,target)
        self.assertEqual(e[-1], [n.interval(0),n.interval(1)])
        self.assertEqual(proof['seriesTerms'],18)
        with self.assertRaisesRegex(ValueError,'norm precondition'):
            n.exp_step([[n.interval(2),n.interval(0)],[n.interval(0),n.interval(0)]],1)

    def test_pi_and_T10_are_source_based_not_old_centres(self):
        s=n.read_facts();m=n.construct(s)
        lo,hi=m['conductances']['T10'].bounds()
        target=F(247,8000)
        self.assertLessEqual(lo,target)
        self.assertGreaterEqual(hi,target)
        old=reviewed_design.arithmetic_diagnostics(json.loads((HERE/'plan.json').read_text()),HERE/'reference-facts.json')
        self.assertIn('T10.G',old['physical100xFailures'])
        self.assertEqual(len(old['physical100xFailures']),7)
        self.assertLess(m['conductances']['T10'].maxerr(m['conductances']['T10'].center()),
                        64*F.from_float(math.ulp(m['conductances']['T10'].center()))/100)

    def test_output_cannot_rewrite_repo_or_prior_files(self):
        s=n.read_facts()
        with self.assertRaisesRegex(ValueError,'outside-repository'):
            n.certify(s,2400,output=HERE/'inputs/T')
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'new outside-repository'):
                n.certify(s,2400,output=td)
        with self.assertRaisesRegex(ValueError,'unsupported scope grid'):
            n.certify(s,3000)


class FullGridCandidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Two full grids: 2,401 and 4,801 records, no compiler invocation.
        cls.tmp=tempfile.TemporaryDirectory()
        cls.base=Path(cls.tmp.name)
        cls.s=n.read_facts()
        cls.primary=n.certify(cls.s,2400,output=cls.base/'primary')
        cls.dense=n.certify(cls.s,4800,output=cls.base/'dense')
        cls.data={key:json.loads((cls.base/sub/f'N1_T1T_reference_grid{i}.json').read_text())
                  for key,sub,i in (('primary','primary',2400),('dense','dense',4800))}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_counts_full_grid_and_original_uncomputed_status(self):
        for npts,key in ((2401,'primary'),(4801,'dense')):
            r=self.data[key];h=r['report']
            self.assertEqual((h['samples'],h['allExports'],h['requests'],h['flowIntegrals']),
                             (npts,77,8,5))
            self.assertEqual(len(r['grid']),npts)
            self.assertTrue(all(len(v)==npts for v in r['columns'].values()))
            self.assertTrue(all(len(v)==npts for v in r['requests'].values()))
            self.assertTrue(all(len(v)==npts for v in r['integrals'].values()))
            self.assertEqual(sorted(r['columns']), sorted(json.loads((HERE/'plan.json').read_text())['acceptance']['mandatoryExports']))
            self.assertEqual(sorted(r['requests']), sorted(json.loads((HERE/'plan.json').read_text())['acceptance']['publicRequestIds']))
            self.assertTrue(h['mathematicalIntervalSelfCheckPassed'])
            self.assertFalse(h['independentlyCertifiedReference'])
            self.assertFalse(h['runtimeReady'])
            self.assertFalse(h['nativeExecuted'])
            self.assertFalse(h['nativeQualified'])
            self.assertFalse(h['originalCheckingCentresAdopted'])
            self.assertFalse(h['historicalReferenceRegenerated'])
            self.assertTrue(h['originalPublicRequestsNotComputed'])
            self.assertEqual(len(h['margin']),77)
            self.assertEqual(len(h['publicRequestMargins']),8)
            self.assertEqual(len(h['integralMargins']),5)

    def test_all_77_8_and_5_have_worst_case_100x_margin(self):
        for kind in ('primary','dense'):
            h=self.data[kind]['report']
            for name,row in h['margin'].items():
                with self.subTest(kind=kind,name=name):
                    self.assertLessEqual(F(row['maxErrorUpperRational']),
                                         F(row['conservativeNativeAllowanceLowerRational'])/100)
            for col in ('publicRequestMargins','integralMargins'):
                for name,row in h[col].items():
                    with self.subTest(kind=kind,component=col,name=name):
                        self.assertLessEqual(F(row['maxErrorUpperRational']),
                                             F(row['conservativeAllowanceLowerRational'])/100)
            self.assertLess(F(h['energyIntegralBalanceResidualMaxUpper']),F(1,10**20))
            self.assertLess(F(h['ownerlessJunctionBalanceResidualMaxUpper']),F(1,10**20))
            self.assertTrue(all(F(x['trapezoidDifferenceUpperRational']) <=F(1,10000)
                                for x in h['integralMargins'].values()))

    def test_initial_values_and_signed_observations(self):
        for x in self.data.values():
            d=x['columns'];req=x['requests']
            self.assertEqual(d['T_Warm.T'][0],367.0)
            self.assertEqual(d['T_Cool.T'][0],289.0)
            self.assertEqual(d['T_Ridge.T'][0],337.0)
            self.assertEqual(d['T_Collar.T'][0],303.0)
            self.assertEqual(d['T_Plug.T'][0],318.0)
            self.assertAlmostEqual(req['t_ridge_energy'][0],0,places=10)
            self.assertLess(d['T06.Q_flow'][0],0)  # T_Collar colder than T_Plug initially
            for i in (0,len(x['grid'])//2,len(x['grid'])-1):
                self.assertEqual(req['t_collar_to_plug'][i],d['T06.Q_flow'][i])
                self.assertEqual(req['t_upper_lower_link'][i],d['T10.Q_flow'][i])
                self.assertAlmostEqual(req['t_upper_minus_cool'][i],
                                       d['T03.T_a'][i]-d['T_Cool.T'][i],places=12)
            self.assertTrue(all(289 <=t<=367 for key,v in d.items() for t in v[::max(1,len(v)//30)] if key.endswith(('.T','.T_a','.T_b'))))

    def test_dense_primary_exact_common_grid_source_agreement(self):
        a=self.data['primary'];b=self.data['dense']
        self.assertEqual(a['grid'],b['grid'][::2])
        for k in a['columns']:
            upper=F(a['report']['margin'][k]['conservativeNativeAllowanceLowerRational'])/100
            diffs=[abs(x-y) for x,y in zip(a['columns'][k][::100],b['columns'][k][::200])]
            self.assertLess(max(diffs),max(float(upper),1e-11),k)
        self.assertEqual(a['report']['refModelSha256'],b['report']['refModelSha256'])

    def test_independent_mpmath_linear_physics_at_five_times(self):
        # Second, unbounded cross-check for gross assembly/geometry errors.
        # This does NOT itself establish certified accuracy.
        with mp.workdps(70):
            s=self.s
            names=['R','B','P','J_Upper','J_Lower','W','K'];idx={name:j for j,name in enumerate(names)}
            L=mp.matrix(7)
            for row in s['rods'].values():
                k=mp.mpf(str(row['k'])); length=mp.mpf(str(row['L']))
                area=mp.mpf(str(row['A'])) if row['kind']=='RodArea' else mp.pi*(mp.mpf(str(row['d']))**2)/4
                g=k*area/length
                i,j=idx[row['a']],idx[row['b']]
                L[i,i]+=g;L[j,j]+=g;L[i,j]-=g;L[j,i]-=g
            b=mp.matrix(2,5)
            for i in range(2):
                for j,oldj in enumerate((0,1,2,5,6)):b[i,j]= -L[i+3,oldj]
            ljj=mp.matrix(2)
            for i in range(2):
                for j in range(2):ljj[i,j]=L[i+3,j+3]
            x=mp.inverse(ljj)*b
            weights=mp.matrix(7,4)
            for i in range(3):weights[i,i]=1
            for i in range(2):
                for j in range(3):weights[i+3,j]=x[i,j]
                weights[i+3,3]=x[i,3]
            weights[5,3]=1
            caps=[mp.mpf(str(next(v['m'] for v in s['bodies'].values() if v['node']==n)))*mp.mpf(str(next(v['c'] for v in s['bodies'].values() if v['node']==n))) for n in ('R','B','P')]
            H=mp.matrix(7)
            for i in range(3):
                for col in range(4):
                    val=sum((L[i,n]*weights[n,col] for n in range(7)),mp.mpf(0))
                    H[i,col if col<3 else 6]=-val/caps[i]
                H[i,i+3]=0
                H[i+3,i]=1
            u0=mp.matrix([mp.mpf(48)/78,mp.mpf(14)/78,mp.mpf(29)/78,0,0,0,1])
            data=self.data['primary']['columns']
            for step in (0,1,100,1200,2400):
                y=mp.expm(H*step)*u0
                for i,name in enumerate(('T_Ridge.T','T_Collar.T','T_Plug.T')):
                    val=289+78*y[i]
                    self.assertLess(abs(float(val)-data[name][step]),1e-10,(step,name))


if __name__=='__main__':unittest.main()
