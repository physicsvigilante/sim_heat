"""Analysis-companion preparation tests; no compiler or native model invocation."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from h1 import reference
from h1.model import Refusal
from h1.study import load_study
from h1.verification import bind_reference
from tools.h1_native_batch import sha, load_plan, build_script
from tools.h1_resolution_campaign import companion, generate, validate_config

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT/'tools/h1_resolution_campaign.json'


class ResolutionCampaignTests(unittest.TestCase):
    def source(self,k):
        s=json.loads((ROOT/'h1/cases'/k/'study.json').read_text())
        r=reference.read_reference(ROOT/'h1/reference_cases'/f'{k}.json')
        return s,r

    def scratch(self):
        t=tempfile.TemporaryDirectory();root=Path(t.name)
        c=json.loads(CONFIG.read_text());b=json.loads((ROOT/c['basePlan']).read_text())
        for path in set(b['pins']) | set(c['extraPins']) | {c['basePlan'],'tools/h1_resolution_campaign.json'}:
            p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/path).read_bytes())
        # The historical pinned plans stay byte-identical and must fail closed
        # against new code. Tests use an explicitly repinned, TEMPORARY
        # successor plan, never a rewritten historical execution artifact.
        for path in ('h1/matv4.py','h1/tests/test_matv4.py','h1/study.py',
                     'h1/tests/test_resolution_campaign.py'):
            pin=sha(root/path)
            if path in b['pins']:
                b['pins'][path]=pin
            else:
                self.assertIn(path,c['extraPins'])
                c['extraPins'][path]=pin
        (root/c['basePlan']).write_text(json.dumps(b,sort_keys=True,indent=2)+'\n')
        c['basePlanSha256']=sha(root/c['basePlan'])
        (root/'tools/h1_resolution_campaign.json').write_text(json.dumps(c,sort_keys=True,indent=2)+'\n')
        return t,root,c,b

    def test_historical_plan_rejects_successor_adapter(self):
        archival=ROOT/'tools/h1_d1d2_plan.json'
        original=json.loads(archival.read_text())
        self.assertNotEqual(original['pins']['h1/matv4.py'],sha(ROOT/'h1/matv4.py'))
        self.assertNotEqual(original['pins']['h1/tests/test_matv4.py'],sha(ROOT/'h1/tests/test_matv4.py'))
        with self.assertRaises(Refusal) as caught:
            load_plan(ROOT,archival,sha(archival))
        self.assertEqual(caught.exception.code,'identity')

    def test_historical_plan_remains_bound_to_original_json_parser(self):
        archival=ROOT/'tools/h1_d1d2_plan.json'
        original=json.loads(archival.read_text())
        self.assertNotEqual(original['pins']['h1/study.py'],sha(ROOT/'h1/study.py'))
        with self.assertRaises(Refusal):
            load_plan(ROOT,archival,sha(archival))

    def test_only_analysis_and_metadata_change(self):
        for k in ('D1','D2','D2_K2'):
            for kind in ('tight','dense'):
                s,r=self.source(k);old_s,old_r=deepcopy(s),deepcopy(r)
                child,spec=companion(s,r,kind)
                self.assertEqual(s,old_s);self.assertEqual(r,old_r)
                for key in set(s)-{'id','analysis'}: self.assertEqual(s[key],child[key])
                for key in set(r)-{'id','analysis','studySha256','provenance'}: self.assertEqual(r[key],spec[key])
                self.assertEqual(child['analysis']['stopTime'],s['analysis']['stopTime'])

    def test_tight_keeps_grid(self):
        s,r=self.source('D1');child,spec=companion(s,r,'tight')
        self.assertEqual(child['analysis']['tolerance'],1e-10)
        self.assertEqual(child['analysis']['intervals'],1000)
        self.assertEqual(reference.grid_for(r).tolist(),reference.grid_for(spec).tolist())

    def test_dense_keeps_tolerance_and_common_times(self):
        for k in ('D1','D2','D2_K2'):
            s,r=self.source(k);child,spec=companion(s,r,'dense')
            self.assertEqual(child['analysis']['tolerance'],1e-8)
            self.assertEqual(child['analysis']['intervals'],2000)
            self.assertEqual(reference.grid_for(r).tolist(),reference.grid_for(spec)[::2].tolist())

    def test_unknown_change_refused(self):
        s,r=self.source('D1')
        with self.assertRaises(Refusal): companion(s,r,'physics')

    def test_primary_settings_drift_refused(self):
        s,r=self.source('D2');s['analysis']['tolerance']=1e-7
        with self.assertRaises(Refusal): companion(s,r,'tight')

    def test_seven_runs_four_scratch_successor_bounded_plans(self):
        t,root,c,b=self.scratch()
        with t:
            validate_config(root,root/'tools/h1_resolution_campaign.json',sha(root/'tools/h1_resolution_campaign.json'))
            state=generate(root,c,b,sha(root/'tools/h1_resolution_campaign.json'))
            self.assertEqual([len(x['members']) for x in state['batches']],[1,2,2,2])
            self.assertEqual(sum(len(x['members']) for x in state['batches']),7)
            for record in state['batches']:
                p=load_plan(root,root/record['plan'],record['sha256'])
                self.assertLessEqual(len(p['cases']),2)

    def test_parent_revision_still_valid(self):
        t,root,c,b=self.scratch()
        with t:
            generate(root,c,b,sha(root/'tools/h1_resolution_campaign.json'))
            for kind in ('tight','dense'):
                s=load_study(root/c['output']/f'inputs/cases/D2_K2/study_resolution_{kind}.json',root/c['output']/'inputs/cases')
                self.assertEqual(s.data['revision'],self.source('D2_K2')[0]['revision'])
                self.assertEqual(s.model.components['rod'].value('k'),200)

    def test_generation_preserves_every_scratch_successor_pin(self):
        t,root,c,b=self.scratch()
        with t:
            generate(root,c,b,sha(root/'tools/h1_resolution_campaign.json'))
            for path,pin in {**b['pins'],**c['extraPins']}.items(): self.assertEqual(sha(root/path),pin)

    def test_original_reference_inventory_unchanged(self):
        t,root,c,b=self.scratch()
        with t:
            before=sorted(p.name for p in (root/'h1/reference_cases').glob('*.json'))
            generate(root,c,b,sha(root/'tools/h1_resolution_campaign.json'))
            after=sorted(p.name for p in (root/'h1/reference_cases').glob('*.json'))
            self.assertEqual(before,after)

    def test_generation_cannot_overwrite(self):
        t,root,c,b=self.scratch()
        with t:
            generate(root,c,b,sha(root/'tools/h1_resolution_campaign.json'))
            with self.assertRaises(FileExistsError): generate(root,c,b,sha(root/'tools/h1_resolution_campaign.json'))

    def test_reference_bindings_and_frozen_allowances(self):
        t,root,c,b=self.scratch()
        with t:
            generate(root,c,b,sha(root/'tools/h1_resolution_campaign.json'))
            for k in ('D1','D2','D2_K2'):
                primary=reference.prepare(self.source(k)[1])
                for kind in ('tight','dense'):
                    s=load_study(root/c['output']/f'inputs/cases/{k}/study_resolution_{kind}.json',root/c['output']/'inputs/cases')
                    r=reference.read_reference(root/c['output']/f'inputs/reference/{k}_resolution_{kind}.json')
                    bind_reference(s,r);bundle=reference.prepare(r)
                    self.assertEqual(bundle['allowances'],primary['allowances'])
                    self.assertEqual(bundle['spec']['bodies'],primary['spec']['bodies'])
                    self.assertEqual(bundle['spec']['rods'],primary['spec']['rods'])

    def test_configuration_source_drift_refused(self):
        t,root,c,b=self.scratch()
        with t:
            (root/'h1/cases/D2_K2/model.mo').write_text('invalid')
            with self.assertRaises(Refusal):validate_config(root,root/'tools/h1_resolution_campaign.json',sha(root/'tools/h1_resolution_campaign.json'))

    def test_companions_use_same_model_name(self):
        t,root,c,b=self.scratch()
        with t:
            generate(root,c,b,sha(root/'tools/h1_resolution_campaign.json'))
            for k in ('D1','D2','D2_K2'):
                base=load_study(root/f'h1/cases/{k}/study.json',root/'h1/cases')
                for kind in ('tight','dense'):
                    s=load_study(root/c['output']/f'inputs/cases/{k}/study_resolution_{kind}.json',root/c['output']/'inputs/cases')
                    self.assertEqual(s.model.name,base.model.name)
                    text=build_script(s,root/'library.mo',root/f'h1/cases/{k}/model.mo')
                    self.assertEqual(text.count('buildModel('),1)
                    self.assertNotIn('simulate(',text)


if __name__=='__main__': unittest.main()
