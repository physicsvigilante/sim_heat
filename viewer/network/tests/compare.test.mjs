import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {validateIndex,validateCase,unitOf} from '../core.mjs';
import {validateCompareIndex,compareNativeCases,recordedBodyTemperatureGap,PAIR_SCHEMA} from '../compare_core.mjs';

const dir=fileURLToPath(new URL('../',import.meta.url));
const index=JSON.parse(readFileSync(dir+'data/index.json','utf8'));
const pairIndex=JSON.parse(readFileSync(dir+'data/compare_index.json','utf8'));
const pairing=()=>validateCompareIndex(structuredClone(pairIndex))[0];
const meta=id=>validateIndex(structuredClone(index)).find(x=>x.id===id);
const load=id=>validateCase(JSON.parse(readFileSync(dir+meta(id).file,'utf8')),meta(id));
const paired=()=>compareNativeCases(pairing(),load('H1_D2'),load('H1_D2_K2'));
const sha=x=>createHash('sha256').update(x).digest('hex');

test('sixth native case and the original five have immutable source-linked catalog entries',()=>{
  const cases=validateIndex(index);
  assert.equal(cases.length,6);
  assert.deepEqual(cases.slice(0,5).map(x=>x.id),
    ['H1_D1','H1_D2','DEV_BRIDGE','H1_S1','TEACH_RING4']);
  for(const id of ['H1_D2','H1_D2_K2']){
    const entry=meta(id);
    assert.equal(sha(readFileSync(dir+entry.file)),entry.sha256);
  }
  const original=load('H1_D2'),modified=load('H1_D2_K2');
  assert.equal(modified.modelName,'H1_D2_K2');
  assert.equal(modified.source.runId,43693191224);
  assert.equal(modified.source.artifactId,14153251022);
  assert.equal(modified.source.artifactSha256,
    'dc32a0a36a27f031ce7a13da83ebdd26a3dd6ac1d14612fa597b36cb439f4843');
  assert.equal(modified.source.csvSha256,
    'f3fd607a4f8701f1736942db6547be7f477e6fcc0973ca4730835b64efc8c7e0');
  assert.equal(modified.source.canonicalSamples,1001);
  assert.equal(modified.source.checksPassed,34);
  assert.equal(modified.source.nativeQualified,false);
  assert.equal(original.source.nativeQualified,false);
  assert.equal(modified.source.publicRequestStatus,'diagnostic_only');
  assert.equal(modified.graph.nodes.length,2);
  assert.equal(modified.graph.edges.length,1);
  assert.deepEqual(modified.columns,original.columns);
});

test('teacher comparison uses only matching recorded instants and unchanged topology',()=>{
  const c=paired();
  assert.equal(pairIndex.schema,PAIR_SCHEMA);
  const p=pairing(),base=load('H1_D2'),rev=load('H1_D2_K2');
  for(const [side,source] of [['baseline',base.source],['successor',rev.source]])
    for(const [field,value] of Object.entries(p.sources[side]))
      assert.equal(source[field],value,'source pinned '+side+'.'+field);
  assert.notEqual(p.sources.baseline.artifactId,p.sources.successor.artifactId);
  assert.equal(c.rows.length,21);
  assert.equal(c.defaultField,'rod.Q_flow');
  assert.deepEqual(c.fields,['cold.T','hot.T','cold.dU','hot.dU','rod.Q_flow']);
  assert.deepEqual([c.revision.before,c.revision.after],[100,200]);
  assert.equal(c.revision.origin,'hypothetical');
  assert.equal(c.rows[0].time,0);
  assert.equal(c.rows.at(-1).time,9375);
  assert.equal(c.rows[0].baseline['rod.Q_flow'],12);
  assert.equal(c.rows[0].successor['rod.Q_flow'],24);
  assert.equal(unitOf(c.defaultField),'W');
  assert.equal(recordedBodyTemperatureGap(c,0).baseline,60);
  assert.equal(recordedBodyTemperatureGap(c,0).successor,60);
  const atFirstSaved=recordedBodyTemperatureGap(c,1);
  assert.equal(atFirstSaved.time,468.75);
  assert.ok(atFirstSaved.successor<atFirstSaved.baseline);
  for(const row of c.rows){
    assert.ok(row.baseline.time===row.successor.time);
    const baselineGap=Math.abs(row.baseline['hot.T']-row.baseline['cold.T']);
    const revisedGap=Math.abs(row.successor['hot.T']-row.successor['cold.T']);
    assert.ok(revisedGap<=baselineGap+1e-9);
    for(const r of [row.baseline,row.successor]){
      assert.ok(Math.abs(r['hot.dU']+r['cold.dU'])<1e-6);
    }
    assert.ok(Math.abs(row.successor['rod.Q_flow']-0.4*(row.successor['hot.T']-row.successor['cold.T']))<1e-9);
  }
  assert.ok(recordedBodyTemperatureGap(c,c.rows.length-1).successor>0);
  assert.ok(recordedBodyTemperatureGap(c,c.rows.length-1).baseline>0);
});

test('reject fake conductivity revisions and unsupported comparison metadata',()=>{
  const mutations=[
    x=>{x.schema='sim_heat.viewer.bad/1';},
    x=>{x.pairs[0].revision.before=-1;},
    x=>{x.pairs[0].revision.after=100;},
    x=>{x.pairs[0].revision.target='body.m';},
    x=>{x.pairs[0].revision.origin='source_given';},
    x=>{x.pairs[0].revision.unit='K';},
    x=>{x.pairs[0].revision.childModelSha256='invalid';},
    x=>{x.pairs[0].baseline=x.pairs[0].successor;},
    x=>{x.pairs.push(structuredClone(x.pairs[0]));},
    x=>{x.pairs[0].unsafe=true;},
    x=>{delete x.pairs[0].sources;},
    x=>{x.pairs[0].sources.extra='synthetic';},
    x=>{x.pairs[0].sources.baseline.runId=0;},
    x=>{x.pairs[0].sources.baseline.runId='43691263273';},
    x=>{x.pairs[0].sources.successor.artifactSha256='0'.repeat(63);},
    x=>{x.pairs[0].sources.successor.compiledSourceCommit='not-a-commit';},
    x=>{x.pairs[0].sources.successor.archiveEntry='../fake.csv';},
    x=>{x.pairs[0].sources.baseline.qualified=true;},
    x=>{x.pairs[0].sources.successor={
      ...x.pairs[0].sources.baseline
    };},
    x=>{x.pairs[0].sources.successor.artifactId=x.pairs[0].sources.baseline.artifactId;},

  ];
  for(const mutate of mutations){
    const data=structuredClone(pairIndex);mutate(data);
    assert.throws(()=>validateCompareIndex(data));
  }
});

test('refuse mismatched source hashes, ownership, identity or time without interpolation',()=>{
  const pair=pairing(),original=load('H1_D2'),child=load('H1_D2_K2');
  const mutate=[
    (p,a,b)=>{p.revision.parentStudySha256='0'.repeat(64);},
    (p,a,b)=>{p.revision.childModelSha256='1'.repeat(64);},
    (p,a,b)=>{b.graph.edges[0].to='hot';},
    (p,a,b)=>{b.graph.nodes[0].energy='hot.dU';},
    (p,a,b)=>{b.columns.push('fictitious.T');},
    (p,a,b)=>{b.analysis.intervals=2000;},
    (p,a,b)=>{b.source.nativeQualified=true;},
    (p,a,b)=>{b.source.publicRequestStatus='qualified';},
    (p,a,b)=>{b.id='other';},
    (p,a,b)=>{b.rowObjects[1].time=478.125;},
    (p,a,b)=>{b.rowObjects.pop();},
    (p,a,b)=>{b.rowObjects[0]['hot.T']=308.15;},
    (p,a,b)=>{b.rowObjects[0]['hot.dU']=1;},
    (p,a,b)=>{p.sources.successor.runId=12;},
    (p,a,b)=>{p.sources.baseline.artifactId=12;},
    (p,a,b)=>{p.sources.baseline.csvSha256='f'.repeat(64);},
    (p,a,b)=>{p.sources.successor.archiveEntry='case_02/normalized.csv';},
    (p,a,b)=>{p.sources.successor.compiledSourceCommit='0'.repeat(40);},
    (p,a,b)=>{p.sources.successor.artifactSha256='0'.repeat(64);},
    (p,a,b)=>{b.source.artifactSha256='f'.repeat(64);},
    (p,a,b)=>{a.source.runId=12345;},
    (p,a,b)=>{b.source.rawMatSha256='1'.repeat(64);},

  ];
  for(const change of mutate){
    const p=structuredClone(pair),a=structuredClone(original),b=structuredClone(child);
    change(p,a,b);
    assert.throws(()=>compareNativeCases(p,a,b));
  }
});

test('same GitHub run means exactly one executed workflow commit across output slots',()=>{
  // SYNTHETIC TEST-ONLY repinning of the already verified D2/D2-K2 pair.
  // Different case files from one authenticated run may occupy distinct slots,
  // but a GitHub Actions run has one workflow GITHUB_SHA.
  const p=pairing();
  const a=p.sources.baseline,b=p.sources.successor;
  b.runId=a.runId;
  b.compiledSourceCommit=a.compiledSourceCommit;
  const base=load('H1_D2'),child=load('H1_D2_K2');
  child.source.runId=a.runId;
  child.source.compiledSourceCommit=a.compiledSourceCommit;
  assert.equal(validateCompareIndex({schema:PAIR_SCHEMA,pairs:[p]}).length,1);
  assert.equal(compareNativeCases(p,base,child).rows.length,21);
  // Different ZIP artifacts can exist in the same GitHub Actions run.
  assert.notEqual(a.artifactId,b.artifactId);
  const bad=structuredClone(p);
  bad.sources.successor.compiledSourceCommit='0'.repeat(40);
  assert.throws(()=>validateCompareIndex({schema:PAIR_SCHEMA,pairs:[bad]}),
                /conflicting executed source commits/);
  assert.throws(()=>compareNativeCases(bad,base,child),
                /conflicting executed source commits/);
  // The same original ZIP can contain different case_XX output slots.
  b.artifactId=a.artifactId;
  b.artifactSha256=a.artifactSha256;
  b.archiveEntry='case_01/normalized.csv';
  child.source.artifactId=a.artifactId;
  child.source.artifactSha256=a.artifactSha256;
  child.source.archiveEntry=b.archiveEntry;
  assert.equal(compareNativeCases(p,base,child).rows.length,21);
  b.compiledSourceCommit='0'.repeat(40);
  assert.throws(()=>validateCompareIndex({schema:PAIR_SCHEMA,pairs:[p]}),
                /conflicting executed source commits/);
});

test('comparison stays source-data-driven, no solver or individual apparatus code paths',()=>{
  const app=readFileSync(dir+'compare.mjs','utf8'),core=readFileSync(dir+'compare_core.mjs','utf8');
  for(const token of ['H1_D2','H1_D2_K2','SimHeat.RodArea','buildModel(', 'simulate(', 'TeacherRingFour']){
    assert.ok(!app.includes(token),'apparatus/solver name in comparison UI: '+token);
    assert.ok(!core.includes(token),'apparatus/solver name in validation: '+token);
  }
  assert.ok(app.includes('Promise.all'));
  assert.ok(app.includes("hashHex(bytes)"));
  assert.ok(app.includes('localEpoch!==epoch'));
});
