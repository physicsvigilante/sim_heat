import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {validateIndex,validateCase,validateSteadyCase,parseSteadyCsv,
        STEADY_SCHEMA,readingsAt,unitOf,flowDescription} from '../core.mjs';

const DIR=fileURLToPath(new URL('../',import.meta.url));
const data=JSON.parse(readFileSync(DIR+'data/S1.json','utf8'));
const index=JSON.parse(readFileSync(DIR+'data/index.json','utf8'));
const meta=validateIndex(index).find(x=>x.id==='H1_S1');
const fixture=readFileSync(DIR+'tests/fixtures/S1-native-normalized.csv');
const sha=b=>createHash('sha256').update(b).digest('hex');
function checked(){return validateCase(structuredClone(data),meta);}
function modify(f){const d=structuredClone(data);f(d);return()=>validateCase(d,meta);}

test('original three transient identities are preserved; fourth is truly steady',()=>{
  const original=['H1_D1','H1_D2','DEV_BRIDGE'];
  assert.deepEqual(index.cases.slice(0,3).map(c=>c.id),original);
  assert.equal(index.cases.length,6);
  assert.equal(data.schema,STEADY_SCHEMA);
  assert.equal(sha(readFileSync(DIR+'data/S1.json')),meta.sha256);
  assert.equal(sha(fixture),data.source.csvSha256);
  const s=checked();
  assert.equal(s.mode,'steady');
  assert.equal(s.source.nativeQualified,false);
  assert.equal(s.source.publicRequestStatus,'diagnostic_only');
  assert.equal(s.source.algebraicEvaluations,2);
  assert.equal(s.source.evaluationMeaning,'algebraic_evaluation_index');
  assert.equal(s.source.selectedEvaluationIndex,1);
  assert.ok(!('analysis' in s));
  assert.ok(!('samples' in s));
  assert.ok(!('rowObjects' in s));
  assert.ok(!('time' in s.readings));
  assert.equal(Object.keys(s.readings).length,7);
  assert.equal(s.graph.nodes.filter(n=>n.kind==='junction').length,1);
  assert.equal(s.graph.edges.length,2);
});

test('strict native owner/rod orientation and source status refusals also apply to steady',()=>{
  const negatives=[
    x=>{x.source.nativeQualified=true;},
    x=>{x.source.publicRequestStatus='nativeQualified';},
    x=>{x.source.evaluationMeaning='seconds';},
    x=>{x.source.algebraicEvaluations=1001;},
    x=>{x.source.selectedEvaluationIndex=0;},
    x=>{x.source.duplicateRowsCollapsed=0;},
    x=>{x.source.artifactSha256='0'.repeat(63);},
    x=>{x.source.csvSha256='not-a-sha';},
    x=>{x.source.archiveEntry='../not-native.csv';},
    x=>{x.schema='sim_heat.viewer.native_case/1';},
    x=>{x.mode='transient';},
    x=>{x.analysis={start:0,stop:1,intervals:1};},
    x=>{x.samples=[[0,273],[1,273]];},
    x=>{x.columns.unshift('time');x.values.unshift(1);},
    x=>{x.columns.push('invented.T');x.values.push(298);},
    x=>{x.values[2]=null;},
    x=>{x.graph.edges[0].from='cold';},
    x=>{x.graph.edges[1].to='hot';},
    x=>{x.graph.nodes[0].power='hot.Q_to_network';},
    x=>{x.graph.nodes[1].temperature='cold.T';},
    x=>{x.graph.nodes[2].temperature='steel.T_b';},
    x=>{x.graph.nodes[2].ports[0]='copper.port_a';},
    x=>{x.graph.nodes[1].ports.push('steel.port_b');},
    x=>{x.graph.nodes.push({id:'phantom',kind:'body',temperature:'phantom.T',energy:'phantom.dU',ports:['phantom.port']});},
  ];
  for(const f of negatives)assert.throws(modify(f));
});

test('saved S1 quantities are direct native values with Kelvin, watt and signed direction',()=>{
  const s=checked(),r=s.readings;
  assert.equal(r['copper.T_b'],366.4562880324543);
  assert.equal(r['copper.Q_flow'],1.0792824946508015);
  assert.equal(r['steel.Q_flow'],1.0792824946508015);
  assert.equal(r['hot.Q_to_network'],-r['cold.Q_to_network']);
  assert.equal(flowDescription(r['copper.Q_flow'],s.graph.edges[0]),'hot → junction_2');
  assert.equal(flowDescription(r['steel.Q_flow'],s.graph.edges[1]),'junction_2 → cold');
  assert.equal(unitOf('cold.T'),'K');
  assert.equal(unitOf('copper.Q_flow'),'W');
  assert.throws(()=>readingsAt(s,0)); // steady has no time-sample API
  // Independent reference arithmetic is a test expectation only, not runtime repair.
  const area=Math.PI*(.02*.02)/4, k1=.092*4184, k2=.011*4184;
  const q=(373.15-273.15)/(.75/(k1*area)+1.25/(k2*area));
  const junction=373.15-q*(.75/(k1*area));
  assert.ok(Math.abs(q-r['copper.Q_flow'])<1e-12);
  assert.ok(Math.abs(junction-r['copper.T_b'])<1e-12);
});

test('original S1 CSV positively authenticates and rejects corruption, truncation and wrong algebraic indices',async()=>{
  const s=checked();
  const bytes=new Uint8Array(fixture).buffer;
  const r=await parseSteadyCsv(bytes,s);
  assert.deepEqual(r,s.readings);
  const altered=new Uint8Array(fixture);
  altered[altered.length-2]^=1;
  await assert.rejects(()=>parseSteadyCsv(altered.buffer,s),/SHA-256 mismatch/);
  const missing=fixture.toString('utf8').split('\n').slice(0,3).join('\n')+'\n';
  const s2=checked();s2.source.csvSha256=sha(missing);
  await assert.rejects(()=>parseSteadyCsv(new TextEncoder().encode(missing).buffer,s2),/row count mismatch/);
  const wrong=fixture.toString('utf8').replaceAll('\n1,','\n2,');
  const s3=checked();s3.source.csvSha256=sha(wrong);
  await assert.rejects(()=>parseSteadyCsv(new TextEncoder().encode(wrong).buffer,s3),/indices must be 0 and 1/);
  const swapped=fixture.toString('utf8').replace('1.0792824946508015','1.0792824946508016');
  const s4=checked();s4.source.csvSha256=sha(swapped);
  await assert.rejects(()=>parseSteadyCsv(new TextEncoder().encode(swapped).buffer,s4),/Nonidentical repeated|differs from archived/);
});

test('steady observations and source-only adapter never dispatch on apparatus name',()=>{
  const app=readFileSync(DIR+'app.mjs','utf8');
  const core=readFileSync(DIR+'core.mjs','utf8');
  const adapter=readFileSync(DIR+'tools/build_steady_case.py','utf8');
  for(const specific of ['H1_S1','copper.T_b','steel.Q_flow','Illustration 123']){
    assert.ok(!app.includes(specific),specific);
    assert.ok(!core.includes(specific),specific);
    assert.ok(!adapter.includes(specific),specific);
  }
  assert.ok(app.includes('updateSteady()'));
  assert.ok(app.includes("sourceCase.mode==='steady'"));
  assert.ok(!app.includes('new Function('));
  assert.ok(!app.includes('simulate('));
});
