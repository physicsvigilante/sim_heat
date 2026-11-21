"""Source-only, novel composition and preservation checks; no native execution."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from h1.model import Refusal
from h1.source_preview import build_source_preview, serialized
from h1.study import load_study

ROOT=Path(__file__).resolve().parents[1]
CASE=ROOT/'h1/cases/TEACH_SPLIT3'
SAVED=ROOT/'viewer/source_preview/data/TEACH_SPLIT3.json'


def digest(data: bytes)->str:
    return hashlib.sha256(data).hexdigest()


class SourcePreviewTests(unittest.TestCase):
    def test_new_authored_composition_admitted_with_no_native_outputs(self):
        study=load_study(CASE/'study.json',ROOT/'h1/cases')
        preview=build_source_preview(study)
        self.assertEqual(preview['modelName'],'TEACH_SPLIT3')
        self.assertEqual((len(preview['components']),len(preview['nodes']),len(preview['rods'])),(12,6,7))
        self.assertEqual({n['role'] for n in preview['nodes']},{'body','boundary','junction'})
        self.assertEqual(sum(n['role']=='junction' for n in preview['nodes']),1)
        self.assertEqual({r['status'] for r in preview['requests']},{'not_computed'})
        self.assertEqual(preview['source']['evidenceKind'],'authored_source_only')
        for name in ('nativeExecuted','nativeQualified','sourceFidelityQualified'):
            self.assertIs(preview['source'][name],False)
        self.assertEqual(preview['source']['publicRequestStatus'],'not_computed')
        self.assertFalse(any(k in preview for k in ('temperatures','heatFlows','samples','results','nativeRun')))
        self.assertEqual(serialized(preview),SAVED.read_bytes())

    def test_new_case_evidence_is_source_inputs_not_computed_values(self):
        preview=json.loads(SAVED.read_bytes())
        self.assertEqual({c['kind'] for c in preview['components']},
                         {'FixedTemperature','Body','RodArea','RodCircular'})
        self.assertEqual(len(preview['requests']),4)
        self.assertEqual({r['unit'] for r in preview['requests']},{'K','W','J'})
        for c in preview['components']:
            self.assertTrue(c['inputs'])
            self.assertEqual({x['name'] for x in c['inputs']},
                             {p['target'].split('.')[-1] for p in c['sourceProvenance']})
        self.assertTrue(any('geometric' in s for s in preview['disclaimers']))

    def test_same_builder_also_admits_unrelated_steady_and_transient_examples(self):
        for name in ('S1','D2','D2_K2','TEACH_RING4','DEV_BRIDGE','D1'):
            with self.subTest(name=name):
                study=load_study(ROOT/f'h1/cases/{name}/study.json',ROOT/'h1/cases')
                preview=build_source_preview(study)
                self.assertEqual(preview['source']['publicRequestStatus'],'not_computed')
                self.assertTrue(preview['nodes'])
                self.assertEqual(len(preview['rods']),sum(c['kind'].startswith('Rod') for c in preview['components']))
                self.assertFalse(preview['source']['nativeQualified'])

    def test_admitted_legal_component_node_id_collision_is_not_renamed(self):
        # Recreate Chat B F-01 from genuinely admitted H1 source bytes, not a
        # forged display fixture. H1 identifiers must remain legal unchanged.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'cases'; draft=root/'COLLISION'; draft.mkdir(parents=True)
            original_model=(CASE/'model.mo').read_bytes()
            model=original_model.replace(b'shortcut',b'node_0')
            data=json.loads((CASE/'study.json').read_text().replace('shortcut','node_0'))
            data['model']['sha256']=digest(model)
            (draft/'model.mo').write_bytes(model)
            (draft/'study.json').write_text(json.dumps(data))
            loaded=load_study(draft/'study.json',root)
            self.assertTrue(loaded.request_report['admitted'])
            preview=build_source_preview(loaded)
            self.assertIn('node_0',[c['id'] for c in preview['components']])
            self.assertIn('node_0',[n['id'] for n in preview['nodes']])
            self.assertEqual(next(n['owner'] for n in preview['nodes']
                                  if n['id']=='node_0'),'aluminum')
            self.assertEqual(next(c['kind'] for c in preview['components']
                                  if c['id']=='node_0'),'RodArea')
            command=("import {admitPreview,selectionValue} from './viewer/source_preview/core.mjs';"
                     "import {readFileSync} from 'node:fs';"
                     "const p=admitPreview(JSON.parse(readFileSync(0,'utf8')));"
                     "if(selectionValue('node','node_0')===selectionValue('component','node_0'))throw Error('ambiguous selection');")
            r=subprocess.run(['node','--input-type=module','-e',command],input=serialized(preview),
                             cwd=ROOT,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr)

    def test_admitted_component_and_model_assumptions_preserved_in_original_scope(self):
        # Chat B F-02: a legal whole-component note cannot silently vanish or
        # become source_given for individual inputs; model assumptions stay raw.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'cases'; draft=root/'ASSUMPTIONS'; draft.mkdir(parents=True)
            (draft/'model.mo').write_bytes((CASE/'model.mo').read_bytes())
            data=json.loads((CASE/'study.json').read_bytes())
            comp={'target':'feed','kind':'adopted_assumption',
                  'locator':'review/component','note':'R2_COMPONENT_ASSUMPTION: lateral losses neglected'}
            model={'target':'@model','kind':'solution_assumption',
                   'locator':'review/model','note':'R2_MODEL_REGIME_MARKER: uniform bodies'}
            data['provenance'].extend([comp,dict(comp),model])
            (draft/'study.json').write_text(json.dumps(data))
            preview=build_source_preview(load_study(draft/'study.json',root))
            feed=next(c for c in preview['components'] if c['id']=='feed')
            self.assertEqual(feed['componentProvenance'],[comp,comp])
            self.assertIn(model,preview['modelProvenance'])
            self.assertNotIn(comp,feed['sourceProvenance'])
            self.assertFalse(any('feed.k' in p.get('appliesTo',[])
                                 and p['target']=='feed' for p in feed['sourceProvenance']))
            self.assertIn(b'R2_COMPONENT_ASSUMPTION',serialized(preview))
            self.assertIn(b'R2_MODEL_REGIME_MARKER',serialized(preview))
            command=("import {admitPreview} from './viewer/source_preview/core.mjs';"
                     "import {readFileSync} from 'node:fs';"
                     "admitPreview(JSON.parse(readFileSync(0,'utf8')));")
            r=subprocess.run(['node','--input-type=module','-e',command],input=serialized(preview),
                             cwd=ROOT,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr)

    def test_refused_source_request_never_becomes_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            cases=Path(temp)/'cases';target=cases/'draft';target.mkdir(parents=True)
            (target/'model.mo').write_bytes((CASE/'model.mo').read_bytes())
            doc=json.loads((CASE/'study.json').read_bytes())
            doc['requests'][0]['target']='missing.port'
            (target/'study.json').write_text(json.dumps(doc))
            study=load_study(target/'study.json',cases)
            self.assertFalse(study.request_report['admitted'])
            with self.assertRaises(Refusal) as caught:
                build_source_preview(study)
            self.assertEqual(caught.exception.code,'request')
            out=Path(temp)/'existing-preview.json';out.write_bytes(b'ORIGINAL')
            p=subprocess.run([sys.executable,'-B','-m','h1.source_preview',str(target/'study.json'),
                              '--root',str(cases),'--out',str(out)],cwd=ROOT,capture_output=True)
            self.assertEqual(p.returncode,2)
            self.assertEqual(out.read_bytes(),b'ORIGINAL')
            self.assertIn(b'"nativeExecuted": false',p.stderr)

    def test_stale_model_hash_does_not_write_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            cases=Path(temp)/'cases';target=cases/'draft';target.mkdir(parents=True)
            (target/'model.mo').write_bytes((CASE/'model.mo').read_bytes().replace(b'390.0',b'391.0'))
            (target/'study.json').write_bytes((CASE/'study.json').read_bytes())
            out=Path(temp)/'preview.json'
            p=subprocess.run([sys.executable,'-B','-m','h1.source_preview',str(target/'study.json'),
                              '--root',str(cases),'--out',str(out)],cwd=ROOT,capture_output=True)
            self.assertEqual(p.returncode,2)
            self.assertFalse(out.exists())
            self.assertIn(b'identity',p.stderr)

    def test_outside_authored_case_root_and_stdout_are_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'preview.json'
            command=[sys.executable,'-B','-m','h1.source_preview',str(CASE/'study.json'),'--root',str(ROOT/'h1/cases')]
            a=subprocess.run(command,cwd=ROOT,capture_output=True)
            self.assertEqual(a.returncode,0,a.stderr)
            b=subprocess.run(command+['--out',str(out)],cwd=ROOT,capture_output=True)
            self.assertEqual(b.returncode,0,b.stderr)
            self.assertEqual(a.stdout,out.read_bytes())
            self.assertEqual(digest(a.stdout),digest(SAVED.read_bytes()))

    def test_no_preview_output_written_inside_authored_case_root(self):
        proposed=CASE/'refused-source-output.json'
        try:
            command=[sys.executable,'-B','-m','h1.source_preview',str(CASE/'study.json'),
                     '--root',str(ROOT/'h1/cases'),'--out',str(proposed)]
            p=subprocess.run(command,cwd=ROOT,capture_output=True)
            self.assertEqual(p.returncode,2)
            self.assertFalse(proposed.exists())
        finally:
            proposed.unlink(missing_ok=True)

    def test_original_native_diagnostic_catalog_never_changed(self):
        catalog=json.loads((ROOT/'viewer/network/data/index.json').read_bytes())
        self.assertEqual(len(catalog['cases']),6)
        for item in catalog['cases']:
            with self.subTest(case=item['id']):
                raw=(ROOT/'viewer/network'/item['file']).read_bytes()
                self.assertEqual(digest(raw),item['sha256'])
                p=json.loads(raw)['source']
                self.assertIs(p['nativeQualified'],False)
                self.assertEqual(p['publicRequestStatus'],'diagnostic_only')

    def test_existing_steady_s1_duplicate_provenance_is_preserved(self):
        # S1 legitimately has source_given AND unit_convention attribution for k.
        s=load_study(ROOT/'h1/cases/S1/study.json',ROOT/'h1/cases')
        data=build_source_preview(s)
        copper=next(c for c in data['components'] if c['id']=='copper')
        records=[p for p in copper['sourceProvenance'] if p['appliesTo']==['copper.k']]
        self.assertEqual({p['kind'] for p in records},{'source_given','unit_convention'})
        # The browser validator must accept an authentic, admitted steady source.
        script=("import {admitPreview} from './viewer/source_preview/core.mjs';"
                "import {readFileSync} from 'node:fs';"
                "admitPreview(JSON.parse(readFileSync(0,'utf8')));")
        r=subprocess.run(['node','--input-type=module','-e',script],input=serialized(data),
                         cwd=ROOT,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_parameter_origin_attribution_is_not_fabricated_as_direct_source(self):
        # A valid H1 study may cite a parameter that supplies a component field.
        source=ROOT/'h1/cases/D1'
        with tempfile.TemporaryDirectory() as temp:
            cases=Path(temp)/'cases';draft=cases/'PARAM';draft.mkdir(parents=True)
            model=(source/'model.mo').read_text()
            model=model.replace('model H1_D1\n',
                'model H1_D1\n  parameter Modelica.Units.SI.Mass effectiveMass = 1.0;\n')
            model=model.replace('body(m=1.0','body(m=effectiveMass')
            (draft/'model.mo').write_bytes(model.encode('utf-8'))
            study=json.loads((source/'study.json').read_bytes())
            study['id']='H1_D1_PARAM'
            study['model']['sha256']=digest(model.encode())
            study['provenance']=[dict(p,target='effectiveMass') if p['target']=='body.m'
                                 else p for p in study['provenance']]
            (draft/'study.json').write_text(json.dumps(study))
            preview=build_source_preview(load_study(draft/'study.json',cases))
            body=next(c for c in preview['components'] if c['id']=='body')
            attr=next(p for p in body['sourceProvenance'] if p['target']=='effectiveMass')
            self.assertEqual(attr['appliesTo'],['body.m'])
            self.assertNotIn('body.m', [p['target'] for p in body['sourceProvenance']])
            script=("import {admitPreview} from './viewer/source_preview/core.mjs';"
                    "import {readFileSync} from 'node:fs';"
                    "admitPreview(JSON.parse(readFileSync(0,'utf8')));")
            r=subprocess.run(['node','--input-type=module','-e',script],input=serialized(preview),
                             cwd=ROOT,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr)

    def test_preview_builder_never_calls_native_or_reference_prepare(self):
        # An empty case-root preview task never executes an OMC process or a
        # fresh analytical reference. Fail immediately if a helper is called.
        from h1 import reference
        with patch.object(reference,'prepare',side_effect=AssertionError('reference prepare called')):
            study=load_study(CASE/'study.json',ROOT/'h1/cases')
            build_source_preview(study)


if __name__=='__main__':unittest.main()
