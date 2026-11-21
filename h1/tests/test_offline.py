"""Author-written offline tests; no compiler or native results.

Reference numbers/topologies below are explicitly stated separately from the
production parser. Matching them checks interpretation data, not native physics.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from h1.model import (Refusal, parse_model, topology, junction_condition, requests,
                      internal_exports)
from h1.policy import (analysis_grid, time_allowance, match_grid, local_allowance,
                       local_balance_allowance)
from h1.study import load_study, report, strict_json, sha256
from h1.decoder import decode_csv

CASES = Path(__file__).resolve().parents[1] / 'cases'
ISO = 'model One SimHeat.Body b(m=1,c=500,T_initial=300); end One;'
D2 = (CASES / 'D2/model.mo').read_text()
S1 = (CASES / 'S1/model.mo').read_text()
ANALYSIS = {'startTime': 0, 'stopTime': 100, 'intervals': 1000, 'solver': 'dassl', 'tolerance': 1e-8}


class Base(unittest.TestCase):
    def refuses(self, fn, *args, code=None):
        with self.assertRaises(Refusal) as cm:
            fn(*args)
        if code:
            self.assertEqual(cm.exception.code, code)


class ParserTests(Base):
    def test_valid_isolated_body(self):
        m = parse_model(ISO)
        self.assertEqual(m.components['b'].value('T_initial'), 300)
        self.assertEqual(topology(m, 'transient').nodes, (('b.port',),))

    def test_comments_and_signed_conversion(self):
        text = ISO.replace('300', 'SimHeat.Units.from_degC(-20)').replace('model One', '/* note */ model One // comment\n')
        self.assertAlmostEqual(parse_model(text).components['b'].value('T_initial'), 253.15)

    def test_typed_parameter_chain(self):
        text = ISO.replace('model One', 'model One parameter Modelica.Units.SI.Mass a=1; parameter Modelica.Units.SI.Mass x=a;').replace('m=1,', 'm=x,')
        m = parse_model(text)
        self.assertEqual(m.components['b'].fields['m'].dependencies, ('x', 'a'))

    def test_all_conversions(self):
        m = parse_model(S1)
        self.assertAlmostEqual(m.components['copper'].value('k'), 384.928)
        self.assertAlmostEqual(m.components['steel'].value('k'), 46.024)
        self.assertAlmostEqual(m.components['copper'].value('d'), .02)
        m = parse_model(D2.replace('A=0.001', 'A=SimHeat.Units.from_cm2(10)'))
        self.assertAlmostEqual(m.components['rod'].value('A'), .001)

    def test_unsupported_lexical_and_language_forms(self):
        bad = [ISO + ' model Extra end Extra;', ISO.replace('m=1', 'm=1+0'),
               ISO.replace('m=1', 'm=true'), ISO.replace('m=1', 'm="1"'),
               ISO.replace('b(', "'b'("), ISO.replace('b(', '_b('),
               ISO.replace('b(', 'β('), ISO.replace('m=1', 'm=1/**/.0'),
               ISO.replace('model One', 'within X; model One'),
               ISO.replace('end One;', 'algorithm x:=1; end One;'),
               ISO.replace('end One;', 'equation b.T=300; end One;'),
               ISO.replace('end One;', 'annotation(experiment(StopTime=1)); end One;'),
               ISO.replace('end One;', 'initial equation b.T=300; end One;'),
               ISO.replace('end One;', 'import X; end One;'),
               ISO.replace('m=1', 'm=sin(1)'), ISO.replace('m=1', 'm=SimHeat.Units.from_cm(1)'),
               ISO.replace('300', 'SimHeat.Units.from_degC(SimHeat.Units.from_cm(1))'),
               ISO.replace('m=1', 'm=x'), ISO.replace('b(', 'time('),
               ISO.replace('m=1', 'm=1e309'), ISO.replace('m=1', 'm=1e-999'),
               ISO.replace('m=1', 'm=NaN'), ISO + '/* unterminated']
        for text in bad:
            with self.subTest(text=text):
                self.refuses(parse_model, text)

    def test_parameters_and_identity_refusals(self):
        for text in [ISO.replace('m=1,',''), ISO.replace('m=1,','m=1,m=2,'),
                     ISO.replace('c=500,','extra=1,c=500,'), ISO.replace('300)', '300,)'),
                     ISO.replace('end One;', 'end Other;'), ISO.replace('m=1', 'm=0'),
                     ISO.replace('c=500', 'c=-1'), ISO.replace('300','0'),
                     ISO.replace('end One;', 'SimHeat.Body b(m=1,c=1,T_initial=1); end One;')]:
            with self.subTest(text=text): self.refuses(parse_model, text)

    def test_declared_type_mismatch(self):
        text = ISO.replace('model One', 'model One parameter Modelica.Units.SI.Length x=1;').replace('m=1,','m=x,')
        self.refuses(parse_model, text, code='units')

    def test_resource_limits(self):
        self.refuses(parse_model, ' ' * 65537, code='resource_limit')
        text = 'model Many ' + ' '.join(f'SimHeat.Body b{i}(m=1,c=1,T_initial=300);' for i in range(9)) + ' end Many;'
        self.refuses(parse_model, text, code='resource_limit')


class TopologyTests(Base):
    def test_source_arrangements_and_orientation(self):
        graph = topology(parse_model(D2), 'transient')
        self.assertEqual(graph.nodes, (('cold.port','rod.port_b'), ('hot.port','rod.port_a')))
        self.assertEqual(graph.edges, (('rod', 1, 0, .2),))
        graph = topology(parse_model(S1), 'steady')
        self.assertEqual(len(graph.nodes), 3)
        self.assertAlmostEqual(junction_condition(graph), 1)

    def test_invalid_connections(self):
        mutants = [D2.replace('hot.port, rod.port_a','missing.port, rod.port_a'),
                   D2.replace('hot.port, rod.port_a','hot.port, rod.internal'),
                   D2.replace('  connect(rod.port_b, cold.port);',''),
                   D2.replace('connect(hot.port, rod.port_a);','connect(hot.port, hot.port);'),
                   D2.replace('end H1_D2;', 'connect(rod.port_a, hot.port); end H1_D2;')]
        for text in mutants:
            with self.subTest(text=text): self.refuses(topology, parse_model(text), 'transient')

    def test_ideal_owner_conflict_is_not_generic_physics_failure(self):
        text = D2.replace('end H1_D2;', 'connect(hot.port,cold.port); end H1_D2;')
        self.refuses(topology, parse_model(text), 'transient', code='inconsistent_constraints')
        self.refuses(topology, parse_model(text.replace('353.15','293.15')), 'transient', code='unsupported_topology')

    def test_rod_self_loop(self):
        text = 'model Loop SimHeat.Body b(m=1,c=1,T_initial=300); SimHeat.RodArea r(k=1,L=1,A=1); equation connect(r.port_a,b.port); connect(r.port_b,b.port); end Loop;'
        self.refuses(topology, parse_model(text), 'transient', code='unsupported_topology')

    def test_floating_subnetwork(self):
        text = ISO.replace('end One;', 'SimHeat.RodArea a(k=1,L=1,A=1); SimHeat.RodArea c(k=1,L=1,A=1); equation connect(a.port_a,c.port_a); connect(a.port_b,c.port_b); end One;')
        self.refuses(topology, parse_model(text), 'transient', code='underdetermined')

    def test_disconnected_closed_bodies_need_no_boundary(self):
        text = ISO.replace('end One;', 'SimHeat.Body c(m=2,c=50,T_initial=200); end One;')
        self.assertEqual(len(topology(parse_model(text), 'transient').networks), 2)

    def test_branch_loop_and_parallel_are_rule_based(self):
        # Synthetic exposed validator fixture: triangle plus a parallel edge.
        text = 'model Network ' + ' '.join(f'SimHeat.Body b{i}(m=1,c=1,T_initial=300);' for i in range(3))
        text += ' '.join(f'SimHeat.RodArea r{i}(k=1,L=1,A=1);' for i in range(4)) + ' equation '
        for i,(a,b) in enumerate([(0,1),(1,2),(2,0),(0,1)]):
            text += f'connect(r{i}.port_a,b{a}.port); connect(r{i}.port_b,b{b}.port);'
        graph = topology(parse_model(text + ' end Network;'), 'transient')
        self.assertEqual((len(graph.nodes),len(graph.edges),len(graph.networks)), (3,4,1))

    def test_conditioning_refuses_nearly_floating_junction_pair(self):
        text = 'model Weak SimHeat.FixedTemperature b(T=300); SimHeat.RodArea a(k=1e-12,L=1,A=1); SimHeat.RodArea c(k=1,L=1,A=1); SimHeat.RodArea d(k=1,L=1,A=1); equation connect(b.port,a.port_a); connect(a.port_b,c.port_a); connect(c.port_a,d.port_a); connect(c.port_b,d.port_b); end Weak;'
        self.refuses(junction_condition, topology(parse_model(text),'steady'), code='numerical_domain')

    def test_mode_boundary(self):
        self.refuses(topology, parse_model(D2), 'steady', code='mode')
        self.refuses(topology, parse_model(S1), 'transient', code='mode')
        text = ISO.replace('end One;', 'SimHeat.FixedTemperature r(T=300); end One;')
        self.refuses(topology, parse_model(text), 'transient', code='connection')

    def test_derived_overflow(self):
        self.refuses(topology, parse_model(ISO.replace('m=1','m=1e308')), 'transient', code='numerical_domain')


class ObservationTests(Base):
    def test_requests_do_not_mutate_model_or_dependencies(self):
        m = parse_model(D2); before = repr(m); exports = internal_exports(m)
        for req in [[], [{'id':'flow','op':'heatFlow','target':'rod'}],
                    [{'id':'t','op':'temperature','target':'hot.port'}],
                    [{'id':'dt','op':'temperatureDifference','a':'hot.port','b':'cold.port'}],
                    [{'id':'e','op':'energyChange','target':'hot'}]]:
            self.assertTrue(requests(m,req)['admitted'])
            self.assertEqual(internal_exports(m),exports)
            self.assertEqual(repr(m),before)
        self.assertIn('cold.Q_in',exports)

    def test_all_requested_statuses_retained(self):
        report = requests(parse_model(D2), [
            {'id':'ok','op':'temperature','target':'hot.port'},
            {'id':'bad','op':'temperature','target':'not_a_body.port'},
            {'id':'ratio','op':'ratio','a':'hot.port','b':'cold.port'}])
        self.assertFalse(report['admitted'])
        self.assertEqual([r['status'] for r in report['requests']], ['not_computed','refused','refused'])

    def test_invalid_request_shapes_types_duplicates(self):
        invalid = [None, [], {'id':True,'op':'temperature','target':'hot.port'},
                   {'id':'x','op':'energyChange','target':'rod'},
                   {'id':'x','op':'temperature','target':{}},
                   {'id':'x','op':'temperature','target':'hot.port','extra':1}]
        for r in invalid:
            with self.subTest(r=r): self.assertFalse(requests(parse_model(D2),[r])['admitted'])
        r={'id':'x','op':'heatFlow','target':'rod'}
        self.assertFalse(requests(parse_model(D2),[r,r])['admitted'])


class StudyTests(Base):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'cases'
        shutil.copytree(CASES,self.root)
    def tearDown(self): self.temp.cleanup()
    def load(self,name='D2'): return load_study(self.root/name/'study.json',self.root)
    def change(self,fn,name='D2'):
        p=self.root/name/'study.json';d=json.loads(p.read_text());fn(d);p.write_text(json.dumps(d))
    def edit_model(self,old,new,name='D2_K2'):
        p=self.root/name/'model.mo';p.write_text(p.read_text().replace(old,new))
        self.change(lambda d:d['model'].update(sha256=sha256(p.read_bytes())),name)

    def test_all_exposed_cases_validate_without_native_commands(self):
        with patch('subprocess.Popen',side_effect=AssertionError('native launch forbidden')):
            for name in ['S1','D1','D2','D2_K2','EQ','REV','ISO']:
                with self.subTest(name=name):
                    result=report(self.load(name))
                    self.assertTrue(result['admitted']);self.assertFalse(result['nativeExecuted'])

    def test_read_only(self):
        before={str(p):sha256(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.load('D2_K2')
        after={str(p):sha256(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_duplicate_nested_json_key(self):
        self.refuses(strict_json,'{"model":{"path":"a","path":"b"}}',code='descriptor')
        self.refuses(strict_json,'{"x":NaN}',code='descriptor')

    def test_hash_mismatch(self):
        self.change(lambda d:d['model'].update(sha256='0'*64))
        self.refuses(self.load,code='identity')

    def test_no_physical_overrides_in_descriptor(self):
        self.change(lambda d:d.update(temperature=500))
        self.refuses(self.load,code='descriptor')

    def test_missing_parameter_provenance(self):
        self.change(lambda d:d.update(provenance=d['provenance'][1:]))
        self.refuses(self.load,code='provenance')

    def test_unknown_provenance_target(self):
        self.change(lambda d:d['provenance'][0].update(target='ghost.mass'))
        self.refuses(self.load,code='provenance')

    def test_path_escape(self):
        self.change(lambda d:d['model'].update(path='../D1/model.mo'))
        self.refuses(self.load,code='path')
        self.refuses(load_study,self.root.parent/'not-in-root.json',self.root,code='path')

    def test_symlink_refused(self):
        p = self.root/'D2/link.mo'
        try:
            p.symlink_to(self.root/'D2/model.mo')
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows account lacks symbolic-link creation privilege')
            raise
        self.change(lambda d:d['model'].update(path='link.mo'))
        self.refuses(self.load,code='path')

    def test_parent_pin_and_no_extra_change(self):
        self.change(lambda d:d['revision'].update(parentStudySha256='0'*64),'D2_K2')
        self.refuses(self.load,'D2_K2',code='revision')

    def test_second_physical_change_refused(self):
        self.edit_model('m=1.0','m=1.1')
        self.refuses(self.load,'D2_K2',code='revision')

    def test_noop_revision_refused(self):
        self.edit_model('k=200.0','k=100.0')
        self.refuses(self.load,'D2_K2',code='revision')

    def test_parent_cycle_refused(self):
        self.change(lambda d:d['revision'].update(parentStudyPath='study.json'),'D2_K2')
        self.refuses(self.load,'D2_K2',code='revision')

    def test_all_request_failures_visible_in_study(self):
        self.change(lambda d:d['requests'].append({'id':'missing','op':'temperature','target':'ghost.port'}))
        result=report(self.load())
        self.assertFalse(result['admitted']);self.assertEqual(len(result['requests']),3)

    def test_shared_parameter_revision_changes_other_rod_is_refused(self):
        # Both rods depend on kshared; changing it is not a one-rod revision.
        model = """model Shared
parameter Modelica.Units.SI.ThermalConductivity kshared=100;
SimHeat.Body a(m=1,c=500,T_initial=350);
SimHeat.Body b(m=1,c=500,T_initial=300);
SimHeat.RodArea r(k=kshared,L=1,A=.01);
SimHeat.RodArea s(k=kshared,L=1,A=.01);
equation connect(a.port,r.port_a); connect(b.port,r.port_b);
connect(a.port,s.port_a); connect(b.port,s.port_b); end Shared;"""
        from dataclasses import replace
        from h1.study import compare_revision
        parent=self.load()
        pm=parse_model(model);cm=parse_model(model.replace('kshared=100','kshared=200'))
        parent=replace(parent,model=pm,topology=topology(pm,'transient'))
        child=replace(parent,model=cm,topology=topology(cm,'transient'))
        self.refuses(compare_revision,parent,child,'r.k',code='revision')

    def test_parameter_provenance_inheritance(self):
        name='ISO';p=self.root/name/'model.mo'
        p.write_text(p.read_text().replace('model H1_ISO','model H1_ISO parameter Modelica.Units.SI.Mass measured=1;').replace('m=1.0,','m=measured,'))
        def change(d):
            d['model']['sha256']=sha256(p.read_bytes())
            d['provenance'][0]['target']='measured'
        self.change(change,name)
        self.assertTrue(self.load(name).request_report['admitted'])


class PolicyTests(Base):
    def test_f1_large_network_cannot_dilute_small_flow(self):
        error=1e-3; expected_scale=.01
        old_global_allowance=1e-6 + 1e-6*(60*1e8)
        self.assertLess(error,old_global_allowance)
        self.assertGreater(error,local_allowance('W',expected_scale))
        self.assertAlmostEqual(local_allowance('W',expected_scale),1.01e-6,places=20)

    def test_f1_large_capacity_cannot_dilute_small_body_energy(self):
        self.assertGreater(.1,local_allowance('J',1))
        self.assertLess(.1,1e-3+1e-6*(60*(1e12+1)))
        self.assertAlmostEqual(local_balance_allowance((('W',12),('W',12))),26e-6)

    def test_zero_scale_remains_finite_and_typed(self):
        self.assertEqual(local_allowance('W',0),1e-6)
        for unit,scale in [('Pa',1),('W',-1),('J',float('nan')),('K',True)]:
            self.refuses(local_allowance,unit,scale)
        self.refuses(local_balance_allowance,(('W',1),('J',1)))

    def test_f2_short_grid_has_disjoint_match_windows(self):
        grid=analysis_grid('transient',dict(ANALYSIS,stopTime=1e-6,intervals=20000))
        h=grid[1]-grid[0]
        self.assertGreater(1e-9,h)
        self.assertLessEqual(time_allowance(grid),h/10)
        match_grid(grid,grid)
        wrong=list(grid);wrong[1]+=h*.2
        self.refuses(match_grid,grid,tuple(wrong),code='time_grid')

    def test_f2_ambiguous_representable_grid_refused(self):
        grid=(1e12,math.nextafter(1e12,math.inf))
        self.refuses(time_allowance,grid,code='time_resolution')

    def test_f6_analysis_domain(self):
        for fields in [{'stopTime':1e-9},{'stopTime':1e8},{'stopTime':float('inf')},
                       {'intervals':999},{'intervals':1001},{'intervals':20002},{'intervals':True},
                       {'tolerance':1e-4},{'solver':'euler'},{'startTime':True},{'startTime':1}]:
            with self.subTest(fields=fields): self.refuses(analysis_grid,'transient',dict(ANALYSIS,**fields))
        self.assertEqual(analysis_grid('steady',{}),())
        self.refuses(analysis_grid,'steady',ANALYSIS)
        self.assertEqual(len(analysis_grid('transient',ANALYSIS)),1001)


class DecoderTests(Base):
    def test_synthetic_only_result(self):
        result=decode_csv('time,b.T,b.dU\n0,300,0\n1,301,500\n',('b.T','b.dU'),(0.,1.))
        self.assertEqual(result['columns']['b.dU'],(0.,500.))
        self.assertFalse(result['numericallyAccepted'])

    def test_duplicates_canonicalized_not_fabricated(self):
        text='time,b.T\n0,300\n0,300\n1,301\n'
        self.assertEqual(decode_csv(text,('b.T',),(0.,1.))['duplicateRowsCollapsed'],1)
        self.refuses(decode_csv,text.replace('0,300\n0,300','0,300\n0,301'),('b.T',),(0.,1.),code='ambiguous_output')

    def test_bad_export_shapes_and_values(self):
        for text in ['time,b.T,b.T\n0,300,300\n1,301,301\n','time,x\n0,300\n1,301\n',
                     'time,b.T\n0,nan\n1,301\n','time,b.T\n0,300\n',
                     'time,b.T\n1,300\n0,301\n','time,b.T\n0,300\n1\n',
                     'time,b.T\n0,word\n1,301\n']:
            with self.subTest(text=text): self.refuses(decode_csv,text,('b.T',),(0.,1.))


class IndependentFixtureTests(Base):
    def test_d1_independently_stated_givens_and_signs(self):
        s=load_study(CASES/'D1/study.json',CASES)
        expected={'body':{'m':1.,'c':500.,'T_initial':293.15},
                  'reservoir':{'T':353.15},'rod':{'k':100.,'L':.5,'A':.001}}
        self.assertEqual({n:{k:b.value for k,b in c.fields.items()} for n,c in s.model.components.items()},expected)
        self.assertEqual(set(map(frozenset,s.topology.nodes)),{frozenset(('body.port','rod.port_b')),frozenset(('reservoir.port','rod.port_a'))})
        # Independent analytical fixture; not a prediction from parsed production values.
        q=.2*(353.15-293.15)
        rod_a,rod_b,body_in,reservoir_port=q,-q,q,-q
        self.assertAlmostEqual(q,12)
        self.assertAlmostEqual(body_in+rod_b,0)
        self.assertAlmostEqual(reservoir_port+rod_a,0)
        self.assertAlmostEqual(-reservoir_port,12)
        self.assertAlmostEqual(500*(353.15-293.15)*(1-math.exp(-1)),30000*(1-math.exp(-1)))

    def test_d2_independently_stated_givens_topology_and_balance(self):
        s=load_study(CASES/'D2/study.json',CASES)
        expected={'hot':{'m':1.,'c':500.,'T_initial':353.15},
                  'cold':{'m':2.,'c':750.,'T_initial':293.15},'rod':{'k':100.,'L':.5,'A':.001}}
        self.assertEqual({n:{k:b.value for k,b in c.fields.items()} for n,c in s.model.components.items()},expected)
        self.assertEqual(set(map(frozenset,s.topology.nodes)),{frozenset(('hot.port','rod.port_a')),frozenset(('cold.port','rod.port_b'))})
        self.assertAlmostEqual(.2*60,12)
        self.assertEqual((-12.,12.),(-.2*60,.2*60))
        for t in (0,1875,9375):
            dt=60*math.exp(-t/1875);hot=308.15+.75*dt;cold=308.15-.25*dt
            self.assertAlmostEqual(500*(hot-353.15)+1500*(cold-293.15),0,places=8)
            self.assertAlmostEqual(-.2*dt + .2*dt,0)

    def test_s1_independent_reference_and_junction(self):
        s=load_study(CASES/'S1/study.json',CASES)
        self.assertEqual(s.model.components['copper'].value('L'),.75)
        self.assertEqual(s.model.components['steel'].value('L'),1.25)
        self.assertEqual(s.model.components['hot'].value('T'),373.15)
        self.assertEqual(s.model.components['cold'].value('T'),273.15)
        a=math.pi*.02**2/4;g1=.092*4184*a/.75;g2=.011*4184*a/1.25
        q=100/(1/g1+1/g2);junction=100-q/g1
        self.assertAlmostEqual(q,1.0792824946508015)
        self.assertAlmostEqual(junction,46000/493)
        self.assertAlmostEqual(g1*(100-junction)-g2*junction,0)

    def test_boundary_fixture_expectations(self):
        for name,expected_delta,expected_flow in [('EQ',0,0),('REV',-60,-12)]:
            m=load_study(CASES/name/'study.json',CASES).model
            self.assertAlmostEqual(m.components['hot'].value('T_initial')-m.components['cold'].value('T_initial'),expected_delta)
            self.assertAlmostEqual(.2*expected_delta,expected_flow)
        iso=load_study(CASES/'ISO/study.json',CASES)
        self.assertEqual(iso.model.connections,())
        self.assertEqual(iso.model.components['body'].value('T_initial'),293.15)


if __name__ == '__main__': unittest.main()
