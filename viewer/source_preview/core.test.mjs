import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {admitPreview,layoutNodes,selectionValue} from './core.mjs';
const original=JSON.parse(fs.readFileSync(new URL('./data/TEACH_SPLIT3.json',import.meta.url)));
const copy=()=>structuredClone(original);
test('one unseen supported composition parses with no computed fields',()=>{
  const p=admitPreview(copy());assert.equal(p.nodes.length,6);assert.equal(p.rods.length,7);
  assert(p.nodes.some(n=>n.role==='junction'));assert(p.requests.every(r=>r.status==='not_computed'));
  assert.equal(p.source.nativeExecuted,false);assert.equal(p.source.nativeQualified,false);
  assert(!('results'in p)&&!('samples'in p));
});
test('position is layout only and deterministic',()=>{
  const x=layoutNodes(original.nodes),y=layoutNodes(original.nodes);
  assert.deepEqual([...x],[...y]);assert.equal(x.size,6);
});
test('reject any native qualification / computed request / fabricated result keys',()=>{
  for(const mutation of [p=>p.source.nativeQualified=true,p=>p.source.nativeExecuted=true,
    p=>p.source.publicRequestStatus='diagnostic_only',p=>p.source.evidenceKind='historical_native_diagnostic',
    p=>p.requests[0].status='computed',p=>p.results=[{T:300}],p=>p.source.verified=true]){
    const p=copy();mutation(p);assert.throws(()=>admitPreview(p),/REFUSED/);
  }
});
test('reject malformed graph, duplicate or unbound ports, false owners',()=>{
  for(const mutation of [p=>p.rods[0].from='missing',p=>p.rods[0].from=p.rods[0].to,
    p=>p.nodes[0].ports[0]='not-a-port',p=>p.nodes[1].ports.push(p.nodes[0].ports[0]),
    p=>p.nodes[0].owner='not-a-component',p=>p.rods.pop()]){
    const p=copy();mutation(p);assert.throws(()=>admitPreview(p),/REFUSED/);
  }
});
test('reject missing attribution, incompatible requests, unsupported units',()=>{
  for(const mutation of [p=>p.components[0].sourceProvenance=[],p=>p.components[0].inputs[0].siUnit='W',
    p=>p.requests[0].targets=['no.port'],p=>p.requests[1].unit='K',p=>p.components[0].inputs[0].sourceValue=0]){
    const p=copy();mutation(p);assert.throws(()=>admitPreview(p),/REFUSED/);
  }
});
test('reject wrong types and invalid flags',()=>{
  for(const mutation of [p=>p.source.nativeQualified=0,p=>p.source.sourceFidelityQualified='false',
    p=>p.nodes=[],p=>p.mode='dynamic',p=>p.components=[{}],p=>p.modelProvenance=[]]){
    const p=copy();mutation(p);assert.throws(()=>admitPreview(p),/REFUSED/);
  }
});

test('legitimate repeated source records for one input are accepted',()=>{
  const p=copy();const c=p.components.find(c=>c.id==='shortcut');
  const k=c.sourceProvenance.find(r=>r.appliesTo.includes('shortcut.k'));
  c.sourceProvenance.push({...k,kind:'unit_convention',note:'Second original attribution for same admitted input'});
  assert.doesNotThrow(()=>admitPreview(p));
});
test('effective provenance must target real fields, not arbitrary other components',()=>{
  for(const update of [
    p=>p.components[0].sourceProvenance[0].appliesTo=['other.k'],
    p=>p.components[0].sourceProvenance[0].target='bad.fake',
    p=>p.components[0].sourceProvenance[0].appliesTo=[],
  ]){const p=copy();update(p);assert.throws(()=>admitPreview(p),/REFUSED/)}
});

// Chat B PR55 F-01: H1 allows a rod named node_0 even when the generic
// graph's aluminum node is also node_0. Selection values must be typed.
test('component and graph node identities occupy distinct selection namespaces',()=>{
  assert.notEqual(selectionValue('component','node_0'),selectionValue('node','node_0'));
  assert.equal(selectionValue('component','node_0'),'component:node_0');
  assert.equal(selectionValue('node','node_0'),'node:node_0');
  assert.throws(()=>selectionValue('rod','node_0'),/REFUSED/);
});

test('component-wide original assumptions remain independent from slot attribution',()=>{
  const p=copy(),feed=p.components.find(c=>c.id==='feed');
  const original={target:'feed',kind:'adopted_assumption',locator:'review/component',
    note:'R2_COMPONENT_ASSUMPTION: lateral heat loss neglected'};
  feed.componentProvenance.push(original,structuredClone(original));
  assert.doesNotThrow(()=>admitPreview(p));
  assert.equal(feed.componentProvenance.length,2);
  assert(!feed.sourceProvenance.some(r=>r.target==='feed'));
  for(const mutation of [x=>x.components.find(c=>c.id==='feed').componentProvenance[0].target='other',
    x=>x.components.find(c=>c.id==='feed').componentProvenance[0].kind='native_qualified',
    x=>x.components.find(c=>c.id==='feed').componentProvenance[0].appliesTo=['feed.k']]){
    const v=structuredClone(p);mutation(v);assert.throws(()=>admitPreview(v),/REFUSED/);
  }
});

test('reject cross-mode metadata and unrecognized provenance kinds',()=>{
  for(const mutation of [p=>p.mode='steady',
    p=>p.components.find(c=>c.id==='feed').sourceProvenance[0].kind='native_qualified',
    p=>p.modelProvenance[0].kind='native_qualified']){
    const v=copy();mutation(v);assert.throws(()=>admitPreview(v),/REFUSED/);
  }
  const p=copy();p.modelProvenance.push({target:'@model',kind:'source_diagram',locator:'x',note:'x'});
  assert.doesNotThrow(()=>admitPreview(p)); // Original regime assumption remains
  p.modelProvenance=p.modelProvenance.filter(p=>p.kind==='source_diagram');
  assert.throws(()=>admitPreview(p),/REFUSED/); // H1 requires a regime assumption
});

// Proposed teacher what-if comparison is a read-only display of TWO claimed
// source documents. It NEVER computes temperatures, powers or time histories.
import {compareSourcePreviews} from './compare_core.mjs';
const withChangedRod = () => {
  const changed=copy();
  const rod=changed.components.find(c=>c.id==='shortcut');
  const field=rod.inputs.find(v=>v.name==='k');
  field.sourceValue=field.sourceValue*2;
  changed.source.modelSha256='a'.repeat(64);
  changed.source.studySha256='b'.repeat(64);
  changed.studyId='TEACH_SPLIT3_Variant';
  changed.modelName='TEACH_SPLIT3_Variant';
  return changed;
};
test('source-only teacher compare finds changed k but never invents heat flow or native results',()=>{
  const result=compareSourcePreviews(copy(),withChangedRod());
  assert.equal(result.schema,'sim_heat.viewer.authored_source_comparison/1');
  assert.equal(result.status,'source_facts_only_not_simulated');
  assert.equal(result.nativeExecuted,false);
  assert.equal(result.nativeQualified,false);
  assert.equal(result.publicRequestStatus,'not_computed');
  const k=result.changes.find(x=>x.category==='input'&&x.label==='shortcut.k · authored SI');
  assert(k);assert.match(k.from,/W\/\(m K\)/);assert.notEqual(k.from,k.to);
  assert(!('heatFlow' in result)&&!('temperatureHistory' in result)&&!('nativeResults' in result));
  assert(result.disclaimer.includes('no physical trajectory'));
});
test('same source creates zero changes, not an invented physical equality claim',()=>{
  const x=compareSourcePreviews(copy(),copy());
  assert.equal(x.changes.length,0);
  assert.equal(x.status,'source_facts_only_not_simulated');
});
test('changes to assumed provenance and public request labels remain visible',()=>{
  const x=copy();
  x.components.find(c=>c.id==='shortcut').sourceProvenance[0].note='Explicitly changed assumption';
  x.requests[0].id='whatif_request';
  x.source.studySha256='c'.repeat(64);
  const r=compareSourcePreviews(copy(),x);
  assert(r.changes.some(c=>c.category==='provenance'&&c.label.includes('shortcut')));
  assert(r.changes.some(c=>c.category==='request'));
  assert(r.changes.every(c=>typeof c.from==='string'&&typeof c.to==='string'));
});
test('source SHA identities cannot remain unchanged when model or study facts drift',()=>{
  const changed=copy();
  changed.components.find(c=>c.id==='shortcut').inputs.find(v=>v.name==='k').sourceValue*=2;
  assert.throws(()=>compareSourcePreviews(copy(),changed),/model SHA-256/);
  const requestChanged=copy();requestChanged.requests[0].id='renamed_request';
  assert.throws(()=>compareSourcePreviews(copy(),requestChanged),/study SHA-256/);
});
test('not-computed displays refuse forged qualified or computed source documents',()=>{
  for(const makeBad of [p=>p.source.nativeQualified=true,p=>p.source.nativeExecuted=true,
    p=>p.requests[0].status='computed',p=>p.results={temperature:314},
    p=>p.source.publicRequestStatus='certified']){
    const p=withChangedRod();makeBad(p);
    assert.throws(()=>compareSourcePreviews(copy(),p),/REFUSED/);
  }
});
test('logical topology uses source port grouping, never layout node ids or geometry',()=>{
  const v=withChangedRod();
  const reordered=structuredClone(v);
  // Renumber every logical node ID, preserving actual authored port groupings.
  const lookup=new Map(reordered.nodes.map((n,i)=>[n.id,'node_'+(90+i)]));
  for(const n of reordered.nodes)n.id=lookup.get(n.id);
  for(const rod of reordered.rods){rod.from=lookup.get(rod.from);rod.to=lookup.get(rod.to);}
  // Same model hash and same physical model, despite different layout node IDs.
  const x=compareSourcePreviews(v,reordered);
  assert.equal(x.changes.length,0);
});

// Independent PR71 R2 review-01 source-evidence regression: test-first RED.
test('same claimed study SHA cannot identify two different model SHA values',()=>{
  const variant=copy();
  variant.source.modelSha256='a'.repeat(64);
  // Even with all displayed SI values and port groups unchanged, the one
  // study source byte identity cannot point to a different physical model.
  assert.equal(variant.source.studySha256,copy().source.studySha256);
  assert.doesNotThrow(()=>admitPreview(variant));
  assert.throws(()=>compareSourcePreviews(copy(),variant),/study SHA-256/);
  const newStudy=copy();newStudy.source.studySha256='b'.repeat(64);
  const sameModel=compareSourcePreviews(copy(),newStudy);
  assert.equal(sameModel.baseline.modelSha256,sameModel.variant.modelSha256);
});

test('cross-kind component changes expose authored inputs and provenance',()=>{
  const changed=copy(),rod=changed.components.find(c=>c.id==='shortcut');
  assert.equal(rod.kind,'RodArea');
  rod.kind='RodCircular';
  const area=rod.inputs.find(x=>x.name==='A');
  assert(area);area.name='d';area.quantityType='Length';area.siUnit='m';area.sourceValue=0.02;
  for(const note of rod.sourceProvenance){
    if(note.target==='shortcut.A')note.target='shortcut.d';
    note.appliesTo=note.appliesTo.map(v=>v==='shortcut.A'?'shortcut.d':v);
    if(note.appliesTo.includes('shortcut.d'))note.note='Source diameter assumed instead of area';
  }
  rod.componentProvenance.push({target:'shortcut',kind:'illustrative',
    locator:'source-only review fixture',note:'Circular, not area, rod assumption'});
  changed.source.modelSha256='a'.repeat(64);
  changed.source.studySha256='b'.repeat(64);
  assert.doesNotThrow(()=>admitPreview(changed));
  const report=compareSourcePreviews(copy(),changed);
  assert(report.changes.some(x=>x.category==='component'&&x.label.includes('shortcut')));
  assert(report.changes.some(x=>x.category==='input'&&x.label.includes('shortcut.A')&&x.to==='not present'));
  assert(report.changes.some(x=>x.category==='input'&&x.label.includes('shortcut.d')&&x.from==='not present'));
  assert(report.changes.some(x=>x.category==='provenance'&&x.label.includes('shortcut')&&x.to.includes('Circular')));
  assert.equal(report.nativeExecuted,false);
  assert.equal(report.publicRequestStatus,'not_computed');
});

test('added and removed components report each authored input and attribution',()=>{
  const baseline=copy(),more=copy(),template=more.components.find(c=>c.kind==='Body');
  const newBody=structuredClone(template),id='extra_body';
  newBody.id=id;
  for(const source of newBody.sourceProvenance){
    source.target=source.target.replace(template.id+'.',id+'.');
    source.appliesTo=source.appliesTo.map(x=>x.replace(template.id+'.',id+'.'));
  }
  for(const source of newBody.componentProvenance)source.target=id;
  more.components.push(newBody);
  more.nodes.push({id:'node_55',owner:id,role:'body',label:id,ports:[id+'.port']});
  more.source.modelSha256='a'.repeat(64);
  more.source.studySha256='b'.repeat(64);
  assert.doesNotThrow(()=>admitPreview(more));
  const added=compareSourcePreviews(baseline,more);
  assert(added.changes.some(x=>x.category==='component'&&x.label===id));
  assert.equal(added.changes.filter(x=>x.category==='input'&&x.label.startsWith(id+'.')).length,3);
  assert(added.changes.some(x=>x.category==='provenance'&&x.label.includes(id)&&x.to.includes(id+'.m')));
  const removed=compareSourcePreviews(more,baseline);
  assert(removed.changes.some(x=>x.category==='component'&&x.label===id));
  assert.equal(removed.changes.filter(x=>x.category==='input'&&x.label.startsWith(id+'.')).length,3);
  assert(removed.changes.some(x=>x.category==='provenance'&&x.label.includes(id)&&x.from.includes(id+'.m')));
});
