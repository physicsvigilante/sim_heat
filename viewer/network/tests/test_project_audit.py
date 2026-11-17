"""Project-audit regressions; synthetic/repacked ZIPs are NEVER native evidence.

Only ordinary D1/S1 offline checking fixtures are prepared. No C1 archived
reference is regenerated, no compiler/native runner is imported or executed.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import csv
import io
import json
import unittest
import zipfile

from h1.model import Refusal, parse_model, topology, internal_exports
from h1.study import strict_json, load_study
from h1.verification import candidate_receipt, check_candidate
from h1 import reference
from h1.tests.test_verification import analytic, csv_text
from viewer.network.tools.build_case import compile_case, owner_graph, sha, stable_json
from viewer.network.tests.test_steady_adapter import (
    make_test_only_members, zip_test_only,
)

from viewer.network.tests import test_steady_adapter as steady_fixture

ROOT=Path(__file__).resolve().parents[3]


class StrictJSONAuditTests(unittest.TestCase):
    def test_legal_exponent_overflow_is_refused_at_any_depth(self):
        for token in ('1e999','-1e999','1E+9999'):
            for raw in ('{"x":'+token+'}', '{"nested":[{"x":'+token+'}]}'):
                with self.subTest(raw=raw), self.assertRaises(Refusal):
                    strict_json(raw)

    def test_finite_numbers_keep_original_representation(self):
        value=strict_json('{"n":1,"x":1e308,"y":1e-308,"denied":false,"v":null}')
        self.assertIs(type(value['n']),int)
        self.assertIs(type(value['x']),float)
        self.assertIs(value['denied'],False)
        self.assertIsNone(value['v'])

    def test_duplicate_nonstandard_and_non_object_still_refuse(self):
        for raw in ('{"x":1,"x":2}','{"a":{"x":1,"x":2}}',
                    '{"x":NaN}','{"x":Infinity}','[]','null'):
            with self.subTest(raw=raw),self.assertRaises(Refusal):strict_json(raw)

    def test_large_integer_and_deep_nesting_are_typed_refusals(self):
        for raw in ('{"n":'+'1'*10000+'}', '{"x":'+'['*20000+'0'+']'*20000+'}'):
            with self.assertRaises(Refusal):strict_json(raw)


class JunctionIdentityAuditTests(unittest.TestCase):
    def graph(self,owner='junction_2',rod='r1'):
        source=f'''model Collision
          SimHeat.FixedTemperature hotBath(T=350);
          SimHeat.Body {owner}(m=1,c=500,T_initial=300);
          SimHeat.RodArea {rod}(k=100,L=.5,A=.001);
          SimHeat.RodArea r2(k=100,L=.5,A=.001);
        equation
          connect(hotBath.port,{rod}.port_a);
          connect({rod}.port_b,r2.port_a);
          connect(r2.port_b,{owner}.port);
        end Collision;'''
        m=parse_model(source)
        return m,owner_graph(SimpleNamespace(model=m,topology=topology(m,'transient')))

    def test_authored_body_id_cannot_collide_with_generated_junction(self):
        model,(nodes,edges)=self.graph()
        self.assertEqual(len({n['id'] for n in nodes}),3)
        junction=next(n for n in nodes if n['kind']=='junction')
        self.assertNotIn(junction['id'],model.components)
        self.assertEqual(junction['id'],'junction_2_1')
        self.assertTrue(all(e['from']!=e['to'] for e in edges))

    def test_generated_id_avoids_all_source_component_names(self):
        model,(nodes,edges)=self.graph(owner='junction_2_1',rod='junction_2')
        self.assertEqual(len({n['id'] for n in nodes}),3)
        self.assertTrue(all(n['id'] not in model.components
                            for n in nodes if n['kind']=='junction'))
        self.assertTrue(all(e['from']!=e['to'] for e in edges))

    def test_existing_catalog_topologies_are_byte_unchanged(self):
        for name in ('D1','D2','DEV_BRIDGE','S1','TEACH_RING4','D2_K2'):
            study=load_study(ROOT/'h1/cases'/name/'study.json',ROOT/'h1/cases')
            nodes,edges=owner_graph(study)
            saved=json.loads((ROOT/'viewer/network/data'/f'{name}.json').read_bytes())
            self.assertEqual(saved['graph'],{'nodes':nodes,'edges':edges},name)


def transient_test_fixture():
    """SYNTHETIC D1: explicit analytic CSV and existing checking-only baseline."""
    s=load_study(ROOT/'h1/cases/D1/study.json',ROOT/'h1/cases')
    b=reference.prepare(reference.read_reference(ROOT/'h1/reference_cases/D1.json'))
    csv_raw=csv_text(s.grid,analytic('D1',s.grid))
    rows=csv_raw.splitlines();csv_raw+='\n'.join(rows[-1:])+'\n'
    data=csv_raw.encode()
    rc=candidate_receipt(s,b,csv_raw,'unattested_output')
    verdict=check_candidate(s,b,csv_raw,rc,b['seal'])
    assert verdict['status']=='checks_passed'
    files={
        'case_01/model.mo':(s.path.parent/'model.mo').read_bytes(),
        'case_01/study.json':s.path.read_bytes(),
        'case_01/SimHeat.mo':(ROOT/'experiments/h1_spike/SimHeat.mo').read_bytes(),
        'case_01/normalized.csv':data,
        'case_01/model_res.mat':b'SYNTHETIC NOT NATIVE\n',
        'case_01/reference.bundle.json':stable_json(b),
        'case_01/receipt.json':stable_json(rc),
        'case_01/verification.json':stable_json(verdict),
        'case_01/build.returncode':b'0\n',
        'case_01/simulation.returncode':b'0\n',
        'compiler_version.returncode':b'0\n',
        'offline_tests.returncode':b'0\n',
    }
    mat=sha(files['case_01/model_res.mat'])
    files['case_01/mat_provenance.json']=stable_json({
        'rawMatSha256':mat,'canonicalCsvSha256':sha(data),'samples':len(s.grid),
        'duplicateRowsCollapsed':1,'nativeQualified':False})
    attempt={'schema':'sim_heat.native_batch_attempt/1',
        'status':'diagnostic_checks_passed_not_native_qualified','nativeQualified':False,
        'counts':{'versionQueries':1,'buildModelCalls':1,'modelLaunches':1},
        'github':{'GITHUB_RUN_ID':'123','GITHUB_SHA':'f'*40,'GITHUB_RUN_ATTEMPT':'1'},
        'cases':[{'directory':'case_01','study':'h1/cases/D1/study.json','model':s.model.name,
            'status':'checks_passed','checkCount':len(verdict['checks']),
            'maxRatio':max(c['maximumRatio'] for c in verdict['checks']),
            'canonicalSamples':len(s.grid),'rawMatSha256':mat,
            'referenceSeal':b['seal'],'referenceFileSha256':sha(files['case_01/reference.bundle.json'])}]}
    return files,attempt


class ArchiveEvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transient=transient_test_fixture()
        cls.steady=make_test_only_members()

    def compile(self,files,attempt,*,steady=False,missing=()):
        with TemporaryDirectory() as td:
            path=Path(td)/'SYNTHETIC-NOT-NATIVE.zip'
            digest=zip_test_only(path,files,attempt,missing_manifest=missing)
            if steady:return steady_fixture.SteadyAdapterTests().compile(path,digest)
            return compile_case(ROOT,'h1/cases/D1/study.json',path,digest,1,999,'TEST ONLY',
                                expected_run_id=123,expected_commit_sha='f'*40)

    def mutant(self,fixture,name,change):
        files,attempt=deepcopy(fixture)
        obj=json.loads(files[name]);change(obj);files[name]=stable_json(obj)
        return files,attempt

    def test_consistent_synthetic_transient_replay_is_diagnostic_not_qualified(self):
        result=self.compile(*deepcopy(self.transient))
        self.assertFalse(result['source']['nativeQualified'])
        self.assertEqual(result['source']['verificationStatus'],'checks_passed')

    def test_transient_all_checks_false_beneath_success_label_refuses(self):
        fs,a=self.mutant(self.transient,'case_01/verification.json',
                         lambda v:[c.__setitem__('passed',False) for c in v['checks']])
        with self.assertRaises(Refusal):self.compile(fs,a)

    def test_transient_forged_public_request_value_refuses_after_repin(self):
        fs,a=self.mutant(self.transient,'case_01/verification.json',
                         lambda v:v['requests'][0].__setitem__('values',99999))
        with self.assertRaises(Refusal):self.compile(fs,a)

    def test_numeric_boolean_replacements_in_saved_verdict_refuse(self):
        for steady,fixture in ((False,self.transient),(True,self.steady)):
            for replacement in (0,0.0):
                fs,a=self.mutant(fixture,'case_01/verification.json',
                    lambda v:v.__setitem__('nativeExecuted',replacement))
                with self.subTest(steady=steady,value=replacement),self.assertRaises(Refusal):
                    self.compile(fs,a,steady=steady)
            fs,a=self.mutant(fixture,'case_01/verification.json',
                lambda v:[c.__setitem__('passed',1) for c in v['checks']])
            with self.assertRaises(Refusal):self.compile(fs,a,steady=steady)

    def test_command_counters_require_integers_not_bools_or_floats(self):
        for steady,fixture in ((False,self.transient),(True,self.steady)):
            for key in ('versionQueries','buildModelCalls','modelLaunches'):
                for val in (True,1.0):
                    fs,a=deepcopy(fixture);a['counts'][key]=val
                    with self.subTest(steady=steady,key=key,value=repr(val)),self.assertRaises(Refusal):
                        self.compile(fs,a,steady=steady)

    def test_full_manifest_cannot_omit_present_selected_source_or_reference(self):
        for name in ('case_01/model.mo','case_01/verification.json',
                     'case_01/reference.bundle.json','case_01/mat_provenance.json'):
            with self.subTest(name=name),self.assertRaises(Refusal):
                self.compile(*deepcopy(self.transient),missing=(name,))

    def test_archived_reference_seal_and_bytes_must_agree(self):
        fs,a=deepcopy(self.transient);a['cases'][0]['referenceFileSha256']='0'*64
        with self.assertRaises(Refusal):self.compile(fs,a)
        fs,a=self.mutant(self.transient,'case_01/reference.bundle.json',
                        lambda v:v.__setitem__('seal','0'*64))
        a['cases'][0]['referenceFileSha256']=sha(fs['case_01/reference.bundle.json'])
        with self.assertRaises(Refusal):self.compile(fs,a)

    def test_transient_record_cannot_change_external_run_identity(self):
        for key,value in (('GITHUB_RUN_ID','124'),('GITHUB_SHA','0'*40)):
            fs,a=deepcopy(self.transient);a['github'][key]=value
            with self.subTest(key=key),self.assertRaises(Refusal):self.compile(fs,a)

    def test_manifest_mat_csv_provenance_must_agree(self):
        fs,a=self.mutant(self.transient,'case_01/mat_provenance.json',
                        lambda v:v.__setitem__('samples',1001.0))
        with self.assertRaises(Refusal):self.compile(fs,a)

    def test_failed_original_preflight_cannot_be_hidden_by_success_label(self):
        fs,a=deepcopy(self.transient);fs['offline_tests.returncode']=b'1\n'
        with self.assertRaises(Refusal):self.compile(fs,a)

    def test_consistent_record_does_not_regenerate_reference_or_run_compiler(self):
        from unittest.mock import patch
        from tools import h1_native_batch
        with patch.object(reference,'prepare',side_effect=AssertionError('no generation')), \
             patch.object(h1_native_batch,'invoke',side_effect=AssertionError('no OMC')):
            self.compile(*deepcopy(self.transient))



class CampaignTypeAuditTests(unittest.TestCase):
    """Synthetic campaign wrapper checks type semantics, not native origin."""
    @classmethod
    def setUpClass(cls):cls.fixture=transient_test_fixture()

    def compile_mutant(self,change=None):
        from viewer.network.tools.build_campaign_case import compile_campaign_case
        fs,a=deepcopy(self.fixture)
        recorded='test_campaign/inputs/cases/D1/study.json'
        a['cases'][0]['study']=recorded
        plan={'branch':'experiment/synthetic-test','cases':[{'study':recorded}]}
        plan_raw=stable_json(plan);a['planSha256']=sha(plan_raw)
        if change:change(fs,a)
        a['artifactSha256']={n:sha(raw) for n,raw in fs.items()}
        campaign={'schema':'sim_heat.resolution_attempt/1',
            'status':'diagnostic_checks_passed_not_native_qualified','nativeQualified':False,
            'batches':[{'output':'test_campaign/batch_1','plan':'test_campaign/plan_1.json',
                        'sha256':sha(plan_raw)}]}
        with TemporaryDirectory() as td:
            p=Path(td)/'SYNTHETIC-CAMPAIGN.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('campaign.json',stable_json(campaign))
                z.writestr('plan_1.json',plan_raw)
                z.writestr('inputs/cases/D1/study.json',fs['case_01/study.json'])
                z.writestr('batch_1/attempt.json',stable_json(a))
                for name,data in fs.items():z.writestr('batch_1/'+name,data)
            return compile_campaign_case(ROOT,'h1/cases/D1/study.json',p,sha(p.read_bytes()),
                1,1,999,'SYNTHETIC ONLY',expected_run_id=123,expected_commit_sha='f'*40,
                expected_branch='experiment/synthetic-test')

    def test_synthetic_consistent_campaign_control(self):
        self.assertFalse(self.compile_mutant()['source']['nativeQualified'])

    def test_campaign_numeric_false_verdict_refuses(self):
        def change(fs,a):
            v=json.loads(fs['case_01/verification.json']);v['nativeExecuted']=0
            fs['case_01/verification.json']=stable_json(v)
        with self.assertRaises(Refusal):self.compile_mutant(change)

    def test_campaign_boolean_command_count_refuses(self):
        with self.assertRaises(Refusal):
            self.compile_mutant(lambda fs,a:a['counts'].__setitem__('versionQueries',True))

if __name__=='__main__':unittest.main()
