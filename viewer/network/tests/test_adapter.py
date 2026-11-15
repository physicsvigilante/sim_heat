"""Generic topology/CSV adapter smoke without a compiler or native execution."""
from pathlib import Path
import unittest
from h1.model import parse_model, topology
from h1.study import load_study
from viewer.network.tools.build_case import owner_graph, pick_indices, stable_json

ROOT=Path(__file__).resolve().parents[3]

class AdapterTests(unittest.TestCase):
    def test_current_offline_study_topologies_not_hardcoded(self):
        expected={'D1':(2,1),'D2':(2,1),'DEV_BRIDGE':(4,5)}
        for name,shape in expected.items():
            with self.subTest(name=name):
                study=load_study(ROOT/'h1/cases'/name/'study.json',ROOT/'h1/cases')
                n,e=owner_graph(study)
                self.assertEqual((len(n),len(e)),shape)
                self.assertEqual({f['id'] for f in e},set(r[0] for r in study.topology.edges))
                self.assertTrue(all(x['from'] != x['to'] for x in e))
    def test_unknown_conductor_chain_uses_native_junction_endpoint(self):
        source='''model Chain
          SimHeat.FixedTemperature source(T=350);
          SimHeat.Body store(m=1,c=500,T_initial=300);
          SimHeat.RodArea r1(k=100,L=.5,A=.001);
          SimHeat.RodArea r2(k=100,L=.5,A=.001);
          equation
          connect(source.port,r1.port_a);
          connect(r1.port_b,r2.port_a);
          connect(r2.port_b,store.port);
          end Chain;'''
        model=parse_model(source)
        class StudyStub: pass
        study=StudyStub();study.model=model;study.topology=topology(model,'transient')
        nodes,edges=owner_graph(study)
        self.assertEqual((len(nodes),len(edges)),(3,2))
        junction=next(n for n in nodes if n['kind']=='junction')
        self.assertIn(junction['temperature'],('r1.T_b','r2.T_a'))
        self.assertFalse('energy' in junction or 'power' in junction)
    def test_sampling_records_sign_change_without_interpolation(self):
        cols={'rod.Q_flow':(3,1,-1,-2,2,4)}
        output=pick_indices(cols,[{'flow':'rod.Q_flow'}],5,max_regular=1)
        self.assertEqual(output,list(range(6)))
        # sparse grid should still include both sides of a reversal
        sparse=pick_indices(cols,[{'flow':'rod.Q_flow'}],5,max_regular=2)
        self.assertIn(1,sparse);self.assertIn(2,sparse)
        self.assertIn(3,sparse);self.assertIn(4,sparse)
    def test_stable_json_refuses_nonfinite(self):
        with self.assertRaises(ValueError): stable_json({'unavailable':float('nan')})

if __name__=='__main__': unittest.main()
