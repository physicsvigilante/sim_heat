// Source-linked comparison of two previously validated native transient cases.
// This file does not calculate a new thermal trajectory or interpolate time.
const SHA=/^[0-9a-f]{64}$/;
const ID=/^[A-Za-z][A-Za-z0-9_]*$/;
export const PAIR_SCHEMA='sim_heat.viewer.compare_index/2';
const COMMIT=/^[0-9a-f]{40}$/;
const EVIDENCE_FIELDS=['runId','artifactId','artifactSha256','compiledSourceCommit',
  'archiveEntry','csvSha256','rawMatSha256'];
function need(value,message){if(!value)throw Error(message);}
function keys(value,names,label){need(value && typeof value==='object' && !Array.isArray(value) &&
  Object.keys(value).sort().join('|')===[...names].sort().join('|'),label+' fields invalid');}
function positive(x){return typeof x==='number'&&Number.isFinite(x)&&x>0;}
function positiveID(x){return Number.isSafeInteger(x)&&x>0;}
function checkEvidence(value){
  keys(value,EVIDENCE_FIELDS,'native pair evidence');
  need(positiveID(value.runId)&&positiveID(value.artifactId)&&
       [value.artifactSha256,value.csvSha256,value.rawMatSha256].every(x=>SHA.test(x))&&
       COMMIT.test(value.compiledSourceCommit)&&
       /^case_[0-9]{2}\/normalized\.csv$/.test(value.archiveEntry),
       'Invalid or missing source native provenance');
}
function checkSourcePair(sources){
  keys(sources,['baseline','successor'],'source pair');
  checkEvidence(sources.baseline);checkEvidence(sources.successor);
  const a=sources.baseline,b=sources.successor;
  if(a.artifactId===b.artifactId)
    need(a.runId===b.runId && a.artifactSha256===b.artifactSha256,
         'Same original artifact has conflicting GitHub run/ZIP identities');
  // One genuine native run can legitimately contain two different model slots.
  need(a.runId!==b.runId||a.artifactId!==b.artifactId||
       a.archiveEntry!==b.archiveEntry,
       'Both sides point to exactly one archived native result slot');
}
function checkCaseSource(caseData,pin){
  const s=caseData.source;
  need(EVIDENCE_FIELDS.every(k=>s?.[k]===pin[k]),
       'Original native run/artifact/CSV identity changed');
}

export function validateCompareIndex(value){
  keys(value,['schema','pairs'],'comparison index');
  need(value.schema===PAIR_SCHEMA&&Array.isArray(value.pairs)&&
       value.pairs.length>=1&&value.pairs.length<=20,'Unsupported comparison index');
  const ids=new Set();
  for(const pair of value.pairs){
    keys(pair,['id','title','baseline','successor','revision','sources'],'pair');
    need(ID.test(pair.id)&&!ids.has(pair.id)&&
      typeof pair.title==='string'&&pair.title.length>0&&pair.title.length<=120&&
      ID.test(pair.baseline)&&ID.test(pair.successor)&&pair.baseline!==pair.successor,
      'Invalid comparison pair identity');
    ids.add(pair.id);
    checkSourcePair(pair.sources);
    const r=pair.revision;
    keys(r,['target','before','after','unit','origin','reason',
            'parentStudySha256','childStudySha256','parentModelSha256','childModelSha256'],'revision');
    need(/^[A-Za-z][A-Za-z0-9_]*\.k$/.test(r.target)&&
      positive(r.before)&&positive(r.after)&&r.before!==r.after&&
      r.unit==='W/(m·K)'&&r.origin==='hypothetical'&&
      typeof r.reason==='string'&&r.reason.trim().length>0&&r.reason.length<=500&&
      [r.parentStudySha256,r.childStudySha256,r.parentModelSha256,r.childModelSha256].every(x=>SHA.test(x)),
      'Invalid conductivity revision');
  }
  return value.pairs;
}

export function compareNativeCases(pair, baseline, successor){
  checkSourcePair(pair.sources);
  need(baseline.id===pair.baseline&&successor.id===pair.successor&&
       baseline.schema==='sim_heat.viewer.native_case/1'&&
       successor.schema==='sim_heat.viewer.native_case/1',
       'Comparison requires the selected native transient cases');
  const r=pair.revision;
  checkCaseSource(baseline,pair.sources.baseline);
  checkCaseSource(successor,pair.sources.successor);
  need(baseline.source.nativeQualified===false&&successor.source.nativeQualified===false&&
       baseline.source.publicRequestStatus==='diagnostic_only'&&
       successor.source.publicRequestStatus==='diagnostic_only',
       'Comparison cannot promote native qualification');
  need(baseline.source.studySha256===r.parentStudySha256&&
       successor.source.studySha256===r.childStudySha256&&
       baseline.source.modelSha256===r.parentModelSha256&&
       successor.source.modelSha256===r.childModelSha256,
       'Comparison physical study/source identity changed');
  need(JSON.stringify(baseline.graph)===JSON.stringify(successor.graph),
       'Comparison topology and physical owners changed');
  need(JSON.stringify(baseline.columns)===JSON.stringify(successor.columns)&&
       JSON.stringify(baseline.analysis)===JSON.stringify(successor.analysis),
       'Comparison unit/analysis/observation grid changed');
  const rod=r.target.slice(0,-2);
  need(baseline.graph.edges.some(e=>e.id===rod&&e.flow===rod+'.Q_flow'),
       'Revised conductivity target is not a source-linked rod');
  need(baseline.rowObjects.length===successor.rowObjects.length&&
       baseline.rowObjects.length>=2,'Comparison preview sample counts disagree');
  const rows=[];
  for(let i=0;i<baseline.rowObjects.length;i++){
    const a=baseline.rowObjects[i],b=successor.rowObjects[i];
    need(a.time===b.time,'Unsynchronized saved source time; interpolation forbidden');
    rows.push({time:a.time,baseline:a,successor:b});
  }
  for(const node of baseline.graph.nodes.filter(n=>n.kind==='body'||n.kind==='boundary')){
    const atZero=rows[0];
    need(atZero.baseline[node.temperature]===atZero.successor[node.temperature],
         'Initial or maintained temperature differs between comparisons');
    if(node.kind==='body')
      need(Math.abs(atZero.baseline[node.energy])<=1e-8&&
           Math.abs(atZero.successor[node.energy])<=1e-8,
           'Initial relative stored energy differs');
  }
  return {rows,fields:baseline.columns.filter(x=>x!=='time'),graph:baseline.graph,
          defaultField:rod+'.Q_flow',revision:r};
}

// Optional purely displayed subtraction of actual recorded native temperature
// observations. This is not a new H1 solver output or an interpolated state.
export function recordedBodyTemperatureGap(pairing,index){
  const bodies=pairing.graph.nodes.filter(n=>n.kind==='body');
  if(bodies.length!==2)return null;
  const row=pairing.rows[index];
  need(!!row,'Unavailable recorded comparison instant');
  const [a,b]=bodies;
  return {baseline:Math.abs(row.baseline[a.temperature]-row.baseline[b.temperature]),
          successor:Math.abs(row.successor[a.temperature]-row.successor[b.temperature]),
          bodies:[a.id,b.id],unit:'K',time:row.time};
}
