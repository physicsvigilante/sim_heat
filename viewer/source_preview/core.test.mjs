import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {admitPreview,layoutNodes} from './core.mjs';
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
