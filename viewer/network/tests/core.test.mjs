import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash,webcrypto} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {validateIndex,validateCase,readingsAt,flowDescription,signDescription,
        firstSignChange,unitOf,energyTotal,hashHex,parseNativeCsv} from '../core.mjs';

const DIR=fileURLToPath(new URL('../',import.meta.url));
const index=JSON.parse(readFileSync(DIR+'data/index.json','utf8'));
const cases=()=>validateIndex(structuredClone(index)).filter(meta=>meta.id!=='H1_S1').map(meta=>{
  const bytes=readFileSync(DIR+meta.file);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),meta.sha256);
  return validateCase(JSON.parse(bytes.toString('utf8')),meta);
});

function edit(c,fn){const meta=index.cases.find(x=>x.id===c.id);const data=structuredClone(c);delete data.rowObjects;fn(data);return()=>validateCase(data,meta);}

test('three data-only arrangements load against one strict generic contract',()=>{
  const arr=cases();assert.equal(arr.length,3);
  assert.deepEqual(arr.map(c=>c.graph.nodes.length),[2,2,4]);
  assert.deepEqual(arr.map(c=>c.graph.edges.length),[1,1,5]);
  assert.deepEqual(arr.map(c=>c.rowObjects.length),[21,21,23]);
  for(const c of arr){
    assert.equal(c.source.nativeQualified,false);
    assert.equal(c.source.publicRequestStatus,'diagnostic_only');
    assert.equal(c.source.verificationStatus,'checks_passed');
    assert.equal(c.samples[0][0],c.analysis.start);
    assert.equal(c.samples.at(-1)[0],c.analysis.stop);
    assert.ok(c.source.checksPassed>0);
  }
});

test('native rod orientations, boundary signs, units, and energy owners are generic',()=>{
  for(const c of cases()){
    for(const edge of c.graph.edges){
      const row=readingsAt(c,0);
      assert.equal(unitOf(edge.flow),'W');
      const observed=flowDescription(row[edge.flow],edge);
      assert.ok(observed.includes('→')||observed.startsWith('Zero'));
      if(row[edge.flow]>0)assert.equal(observed,edge.from+' → '+edge.to);
      if(row[edge.flow]<0)assert.equal(observed,edge.to+' → '+edge.from);
    }
    for(const node of c.graph.nodes){
      assert.equal(unitOf(node.temperature),'K');
      if(node.energy)assert.equal(unitOf(node.energy),'J');
      if(node.power){assert.equal(unitOf(node.power),'W');
                     assert.equal(signDescription(-1),'Absorbed from network');}
    }
    const atEnd=readingsAt(c,c.rowObjects.length-1);
    const energy=c.graph.nodes.filter(n=>n.energy).reduce((x,n)=>x+atEnd[n.energy],0);
    assert.equal(energyTotal(atEnd,c.graph.nodes),energy);
  }
});

test('bridge reversal exists, other two show no fabricated flow reversal',()=>{
  const [d1,d2,bridge]=cases();
  assert.equal(firstSignChange(d1.rowObjects,d1.graph.edges[0]),null);
  assert.equal(firstSignChange(d2.rowObjects,d2.graph.edges[0]),null);
  const e=bridge.graph.edges.find(x=>x.id==='bridge');
  const reversal=firstSignChange(bridge.rowObjects,e);
  assert.deepEqual(reversal,{from:1720,to:1730,index:3});
  const early=readingsAt(bridge,2),late=readingsAt(bridge,3);
  assert.equal(early[e.flow],-0.009653756395368874);
  assert.equal(late[e.flow],0.005807881808732419);
  assert.equal(flowDescription(early[e.flow],e),'right → left');
  assert.equal(flowDescription(late[e.flow],e),'left → right');
});

test('catalog rejects wrong file path, sha, ID and duplicate data',()=>{
  const errors=[i=>{i.cases[0].file='../bad.json';},
    i=>{i.cases[0].sha256='0'.repeat(63);},
    i=>{i.cases[1].id=i.cases[0].id;},
    i=>{i.cases.push(i.cases[0]);}];
  for(const mutate of errors){const c=structuredClone(index);mutate(c);assert.throws(()=>validateIndex(c));}
});

test('case refuses fake qualification, missing node/edge/field, stale time and corrupt numeric',()=>{
  const c=cases().at(-1);
  const mutations=[
    x=>{x.source.nativeQualified=true;},
    x=>{x.source.publicRequestStatus='native_qualified';},
    x=>{x.source.csvSha256='not-a-hash';},
    x=>{x.graph.nodes[0].temperature='left.nonexistent';},
    x=>{delete x.graph.nodes[0].temperature;},
    x=>{x.graph.edges[0].from='unknown';},
    x=>{x.graph.edges[0].flow='fake.Q_flow';},
    x=>{x.columns.push('imagined.T');},
    x=>{x.samples[1][0]+=0.001;},
    x=>{x.samples.splice(1,1);x.samples[1][0]=x.samples[0][0];},
    x=>{x.samples[1][3]=null;},
    x=>{x.samples[1].pop();},
    x=>{x.samples.shift();},
    x=>{x.analysis.intervals=2001;},
  ];
  for(const change of mutations){assert.throws(edit(c,change));}
});

test('F-03: repinned catalog cannot misattribute physical owner fields or rod endpoints',()=>{
  const [d1,d2,bridge]=cases();
  const negatives=[
    [d1,x=>{x.graph.edges[0].from='body';x.graph.edges[0].to='reservoir';}],
    [d1,x=>{x.graph.nodes.find(n=>n.id==='body').ports.push('rod.port_a');}],
    [d1,x=>{x.graph.nodes.find(n=>n.id==='body').ports=['body.port'];}],
    [d1,x=>{x.graph.nodes.find(n=>n.id==='body').ports.push('phantom.port_a');}],
    [d1,x=>{x.graph.nodes.find(n=>n.id==='body').ports[0]='reservoir.port';}],
    [d2,x=>{const [a,b]=x.graph.nodes;[a.temperature,b.temperature]=[b.temperature,a.temperature];}],
    [d2,x=>{const [a,b]=x.graph.nodes;[a.energy,b.energy]=[b.energy,a.energy];}],
    [bridge,x=>{const a=x.graph.nodes.find(n=>n.id==='heated'),b=x.graph.nodes.find(n=>n.id==='cooled');[a.power,b.power]=[b.power,a.power];}],
    [bridge,x=>{x.graph.nodes[0].ports.push(x.graph.nodes[1].ports[0]);}],
    [bridge,x=>{x.graph.edges[0].to=x.graph.edges[0].from;}],
    [bridge,x=>{x.graph.nodes[0].temperature='bridge.T_a';}],
  ];
  for(const [c,change] of negatives)assert.throws(edit(c,change),'Invalid owner/rod mapping accepted');
  const c=structuredClone(d1);delete c.rowObjects;
  c.graph.nodes[0].ports=['body.port'];
  c.graph.nodes[1].ports=['reservoir.port','rod.port_a'];
  c.graph.nodes.push({id:'junction_2',kind:'junction',ports:['rod.port_b'],temperature:'rod.T_b'});
  c.graph.edges[0].to='junction_2';
  c.columns.push('rod.T_b');c.samples.forEach(row=>row.push(312));
  const meta=index.cases.find(x=>x.id===c.id);
  assert.doesNotThrow(()=>validateCase(c,meta));
  c.graph.nodes[2].temperature='rod.T_a';
  assert.throws(()=>validateCase(c,meta),/Junction temperature/);
});

test('F-04: a zero touch alone is not a recorded reversal',()=>{
  const rod={flow:'rod.Q_flow'},rows=values=>values.map((q,i)=>({time:i,'rod.Q_flow':q}));
  for(const values of [[1,0,1],[-1,0,-1],[0,0,1,1],[1,0,0,1],[0,0,0]])
    assert.equal(firstSignChange(rows(values),rod),null,values.join(','));
  assert.deepEqual(firstSignChange(rows([1,0,-1]),rod),{from:0,to:2,index:2});
  assert.deepEqual(firstSignChange(rows([-1,1]),rod),{from:0,to:1,index:1});
  assert.deepEqual(firstSignChange(rows([-1,0,0,1]),rod),{from:0,to:3,index:3});
  assert.deepEqual(firstSignChange(rows([0,-1,0,1]),rod),{from:1,to:3,index:3});
});

test('full CSV parser verifies exact original hash before interpreting data',async()=>{
  const c=cases()[0],meta=index.cases[0];
  const buf=new TextEncoder().encode('time,body.T\n0,300\n');
  await assert.rejects(()=>parseNativeCsv(buf.buffer,c),/SHA-256 mismatch/);
  const tick=(c.analysis.stop-c.analysis.start)/c.analysis.intervals;
  const selected=new Map(c.rowObjects.map(o=>[o.time,o]));
  const rows=[];
  rows.push(c.columns.join(','));
  for(let i=0;i<=c.analysis.intervals;i++){
    const t=c.analysis.start+i*tick;
    const known=selected.get(t);
    rows.push(c.columns.map(f=>String(f==='time'?t:known?.[f]??0)).join(','));
  }
  rows.push(rows.at(-1));const text=rows.join('\n')+'\n';
  const bytes=new TextEncoder().encode(text);
  const synthetic=structuredClone(c);delete synthetic.rowObjects;
  synthetic.source.csvSha256=createHash('sha256').update(bytes).digest('hex');
  const altered=validateCase(synthetic,meta);
  const full=await parseNativeCsv(bytes.buffer,altered);
  assert.equal(full.length,1001);
  assert.equal(full.at(-1).time,12500);
  assert.equal(full[80]['rod.Q_flow'],0); // synthetic missing interior values are NOT physics evidence
  assert.equal((await hashHex(bytes.buffer)),synthetic.source.csvSha256);
  const corrupted=new TextEncoder().encode(text.replace('0,293.15,','0,294.15,'));
  await assert.rejects(()=>parseNativeCsv(corrupted.buffer,altered),/SHA-256 mismatch/);
  const other=structuredClone(altered);other.source.csvSha256=createHash('sha256').update(new TextEncoder().encode(rows.slice(0,-1).join('\n')+'\n')).digest('hex');
  await assert.rejects(()=>parseNativeCsv(new TextEncoder().encode(rows.slice(0,-1).join('\n')+'\n').buffer,other),/sample count mismatch/);
});

test('renderer and adapter have no case-name dispatch or native solver invocation',()=>{
  const viewer=readFileSync(DIR+'app.mjs','utf8');const core=readFileSync(DIR+'core.mjs','utf8');
  const adapter=readFileSync(DIR+'tools/build_case.py','utf8');
  for(const name of ['H1_D1','H1_D2','DEV_BRIDGE','H1_S1','SimHeat.Rod','bridge.Q_flow']){
    assert.ok(!viewer.includes(name),name+' hardcoded in renderer');
    assert.ok(!core.includes(name),name+' hardcoded in contract');
    assert.ok(!adapter.includes(name),name+' hardcoded in adapter');
  }
  for(const symbol of ['buildModel(', 'simulate(', 'omc --version','eval(', 'new Function(']){
    assert.ok(!(viewer+core).includes(symbol),symbol+' forbidden');
  }
});
