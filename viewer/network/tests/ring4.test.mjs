import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {validateIndex,validateCase,readingsAt,firstSignChange,
        unitOf,flowDescription,energyTotal} from '../core.mjs';

const root=fileURLToPath(new URL('../',import.meta.url));
const index=JSON.parse(readFileSync(root+'data/index.json','utf8'));
const entry=validateIndex(index).find(x=>x.id==='TEACH_RING4');
const bytes=readFileSync(root+'data/TEACH_RING4.json');
const raw=JSON.parse(bytes.toString('utf8'));
const source=()=>validateCase(structuredClone(raw),entry);
const mutate=fn=>{
  const x=structuredClone(raw);fn(x);
  return ()=>validateCase(x,entry);
};

test('fifth source data is exactly hashed, diagnostic-only, transient and generically owned',()=>{
  assert.equal(index.cases.length,5);
  assert.deepEqual(index.cases.slice(0,4).map(x=>x.id),
                   ['H1_D1','H1_D2','DEV_BRIDGE','H1_S1']);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),entry.sha256);
  const c=source();
  assert.equal(c.schema,'sim_heat.viewer.native_case/1');
  assert.equal(c.modelName,'TeacherRingFour');
  assert.equal(c.source.runId,43845664024);
  assert.equal(c.source.artifactId,14215520616);
  assert.equal(c.source.artifactSha256,
              '0bc1433be66df2827f8907d100ca264f6a721fe8ad40644b962500b97fa9b8b2');
  assert.equal(c.source.csvSha256,'31b3f77dca6227462505c548907f9cf7ed7b620f8b23d73ba8ea9953f52d87d7');
  assert.equal(c.source.verificationStatus,'checks_passed');
  assert.equal(c.source.publicRequestStatus,'diagnostic_only');
  assert.equal(c.source.nativeQualified,false);
  assert.equal(c.source.checksPassed,126);
  assert.deepEqual([c.graph.nodes.length,c.graph.edges.length],[5,6]);
  assert.deepEqual([c.analysis.start,c.analysis.stop,c.analysis.intervals],[0,24000,2000]);
  assert.deepEqual([c.samples.length,c.rowObjects.length,c.source.canonicalSamples],[29,29,2001]);
  assert.equal(c.rowObjects[0].time,0);
  assert.equal(c.rowObjects.at(-1).time,24000);
  assert.equal(c.graph.nodes.filter(n=>n.kind==='body').length,4);
  assert.equal(c.graph.nodes.filter(n=>n.kind==='boundary').length,1);
  for(const n of c.graph.nodes){
    assert.equal(unitOf(n.temperature),'K');
    if(n.energy)assert.equal(unitOf(n.energy),'J');
    if(n.power)assert.equal(unitOf(n.power),'W');
  }
  for(const e of c.graph.edges)assert.equal(unitOf(e.flow),'W');
  assert.ok(!JSON.stringify(c).includes('nativeQualified":true'));
});

test('recorded native signs reverse on four rods, not reservoir or diagonal',()=>{
  const c=source();
  const expected={
    ringDA:[336,348],ringAB:[756,768],
    ringCD:[1956,1968],ringBC:[3984,3996]
  };
  for(const e of c.graph.edges){
    const change=firstSignChange(c.rowObjects,e);
    if(e.id in expected){
      assert.ok(change, e.id+' had no recorded sign change');
      assert.deepEqual([change.from,change.to],expected[e.id]);
      const prior=c.rowObjects.find(x=>x.time===change.from);
      const next=c.rowObjects.find(x=>x.time===change.to);
      assert.ok(prior[e.flow]*next[e.flow]<0,'missing native sign reversal');
      assert.equal(flowDescription(next[e.flow],e),
                   next[e.flow]>0?e.from+' → '+e.to:e.to+' → '+e.from);
    }else{
      assert.equal(change,null,'incorrect reversal on '+e.id);
    }
  }
  const t0=readingsAt(c,0),last=readingsAt(c,c.rowObjects.length-1);
  assert.equal(t0['bathToA.Q_flow'],15);
  assert.equal(t0['ringAB.Q_flow'],-3.2);
  assert.equal(t0['ringBC.Q_flow'],7);
  assert.equal(t0['ringCD.Q_flow'],-5);
  assert.ok(last['bathToA.Q_flow']>0);
  assert.equal(t0['bath.T'],353.15);
  const stored=last['A.dU']+last['B.dU']+last['C.dU']+last['D.dU'];
  assert.equal(energyTotal(last,c.graph.nodes),stored);
});

test('wrong owner/port/orientation, fake native status and fabricated time refuse',()=>{
  const invalid=[
    x=>{x.graph.edges.find(e=>e.id==='diagonalAC').to='D';},
    x=>{x.graph.edges.find(e=>e.id==='ringAB').from='B';},
    x=>{x.graph.nodes.find(n=>n.id==='C').temperature='A.T';},
    x=>{x.graph.nodes.find(n=>n.id==='B').energy='A.dU';},
    x=>{x.graph.nodes.find(n=>n.id==='bath').power='A.dU';},
    x=>{x.graph.nodes.find(n=>n.id==='A').ports=['A.port'];},
    x=>{x.graph.nodes.find(n=>n.id==='A').ports.push('phantom.port_a');},
    x=>{x.graph.nodes.push({id:'fake',kind:'junction',ports:['fake.port_a'],temperature:'fake.T_a'});},
    x=>{x.source.nativeQualified=true;},
    x=>{x.source.publicRequestStatus='qualified';},
    x=>{x.source.csvSha256='invalid';},
    x=>{x.samples[1][0]+=1;},
    x=>{x.samples[1][5]=null;},
    x=>{x.samples[0].pop();},
    x=>{x.samples.splice(2,1);},
    x=>{x.analysis.intervals=1999;},
  ];
  for(const fn of invalid)assert.throws(mutate(fn));
});

test('same physical renderer/adapter are free of Ring4 case-name dispatch',()=>{
  const app=readFileSync(root+'app.mjs','utf8');
  const core=readFileSync(root+'core.mjs','utf8');
  const adapter=readFileSync(root+'tools/build_case.py','utf8');
  for(const name of ['TeacherRingFour','TEACH_RING4','bathToA.Q_flow','ringDA.Q_flow']){
    assert.ok(!app.includes(name),'case name in renderer: '+name);
    assert.ok(!core.includes(name),'case name in contract: '+name);
    assert.ok(!adapter.includes(name),'case name in adapter: '+name);
  }
  assert.ok(!app.includes('buildModel('));
});
