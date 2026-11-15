// Generic H2-02 visual observation contract. Never computes physical trajectories.
export const INDEX_SCHEMA = 'sim_heat.viewer.case_index/1';
export const CASE_SCHEMA = 'sim_heat.viewer.native_case/1';
const SHA = /^[0-9a-f]{64}$/;
const ID = /^[A-Za-z][A-Za-z0-9_]*$/;
const MAX_SAMPLES = 40001;
function need(v, reason) { if (!v) throw new Error(reason); }
function keys(obj, expected, label) {
  need(obj && typeof obj==='object' && !Array.isArray(obj) &&
       Object.keys(obj).sort().join('|')===expected.sort().join('|'),label+' schema mismatch');
}
function positiveInteger(v) {return Number.isSafeInteger(v) && v>0;}
export function validateIndex(data) {
  keys(data,['schema','cases'],'index');
  need(data.schema===INDEX_SCHEMA,'Unsupported index version');
  need(Array.isArray(data.cases)&&data.cases.length>0&&data.cases.length<=32,'Bad case catalog');
  const ids=new Set(), files=new Set();
  for (const item of data.cases) {
    keys(item,['id','title','file','sha256'],'catalog entry');
    need(ID.test(item.id)&&typeof item.title==='string'&&item.title.length>0&&item.title.length<=100,
         'Invalid case name');
    need(/^data\/[A-Za-z0-9_]+\.json$/.test(item.file)&&SHA.test(item.sha256),'Invalid data path or digest');
    need(!ids.has(item.id)&&!files.has(item.file),'Duplicate case');
    ids.add(item.id);files.add(item.file);
  }
  return data.cases;
}
export function validateCase(input, catalogEntry) {
  keys(input,['schema','id','title','modelName','source','analysis','graph','columns','samples'],'case');
  need(input.schema===CASE_SCHEMA && input.id===catalogEntry.id && input.title===catalogEntry.title,
       'Case identity mismatch');
  need(ID.test(input.id)&&ID.test(input.modelName),'Invalid model identifier');
  const s=input.source;
  keys(s,['runId','artifactId','artifactSha256','modelSha256','studySha256','compiledSourceCommit',
          'csvSha256','rawMatSha256','archiveEntry','evidenceKind','nativeQualified',
          'verificationStatus','publicRequestStatus','checksPassed','canonicalSamples','duplicateRowsCollapsed'],'source');
  need(positiveInteger(s.runId)&&positiveInteger(s.artifactId)&&positiveInteger(s.checksPassed),
       'Missing native source IDs');
  need([s.artifactSha256,s.modelSha256,s.studySha256,s.csvSha256,s.rawMatSha256].every(x=>SHA.test(x)) &&
       /^[0-9a-f]{40}$/.test(s.compiledSourceCommit), 'Invalid source hashes');
  need(/^case_\d{2}\/normalized\.csv$/.test(s.archiveEntry),'Invalid native archive path');
  need(s.evidenceKind==='historical_native_diagnostic' && s.nativeQualified===false &&
       s.verificationStatus==='checks_passed' && s.publicRequestStatus==='diagnostic_only',
       'Missing/incorrect diagnostic-only status');
  need(positiveInteger(s.canonicalSamples)&&s.canonicalSamples<=MAX_SAMPLES &&
       s.duplicateRowsCollapsed===1, 'Unsupported native sample format');
  keys(input.analysis,['start','stop','intervals'],'analysis');
  const a=input.analysis;
  need(Number.isFinite(a.start)&&Number.isFinite(a.stop)&&a.start<a.stop&&
       positiveInteger(a.intervals)&&a.intervals+1===s.canonicalSamples,'Bad analysis grid');
  keys(input.graph,['nodes','edges'],'graph');
  const nodes=input.graph.nodes, edges=input.graph.edges;
  need(Array.isArray(nodes)&&nodes.length>0&&nodes.length<=64&&
       Array.isArray(edges)&&edges.length<=32,'Unsupported graph size');
  need(Array.isArray(input.columns)&&input.columns.length>=2&&input.columns.length<=64 &&
       input.columns[0]==='time'&&new Set(input.columns).size===input.columns.length,
       'Duplicate or missing native channel');
  const columns=new Set(input.columns), names=new Set(), required=new Set(['time']);
  // Port ownership is structural evidence, not an arbitrary free-form label.
  // Each declared Modelica connector belongs to one and only one ideal node.
  const portOwner=new Map(), ownerFields=new Set();
  function observe(name,suffix,kind) {
    need(typeof name==='string' && name.endsWith(suffix) && columns.has(name),
         `Missing ${kind} native observation`);
    required.add(name);
  }
  for (const node of nodes) {
    const base=['id','kind','temperature','ports'];
    if(node?.kind==='body')base.push('energy');
    if(node?.kind==='boundary')base.push('power');
    keys(node,base,'node');
    need(ID.test(node.id)&&!names.has(node.id)&&['body','boundary','junction'].includes(node.kind),
         'Duplicate/invalid node');
    names.add(node.id);
    need(Array.isArray(node.ports)&&node.ports.length>0,'Node missing connection ports');
    for (const port of node.ports) {
      need(typeof port==='string' &&
           (/^[A-Za-z][A-Za-z0-9_]*\.port$/.test(port) ||
            /^[A-Za-z][A-Za-z0-9_]*\.port_[ab]$/.test(port)),
           'Malformed native connector port');
      need(!portOwner.has(port),'Duplicate native connector owner');
      portOwner.set(port,node.id);
    }
    const namedPorts=node.ports.filter(p=>p.endsWith('.port'));
    need(node.kind==='junction' ? namedPorts.length===0 :
         namedPorts.length===1 && namedPorts[0]===node.id+'.port',
         'Physical node port owner mismatch');
    if(node.kind==='junction') {
      const sensor=node.temperature.match(/^([A-Za-z][A-Za-z0-9_]*)\.T_([ab])$/);
      need(sensor && node.ports.includes(sensor[1]+'.port_'+sensor[2]),
           'Junction temperature must come from a connected native rod end');
      observe(node.temperature, '.T_'+sensor[2], 'junction temperature');
    } else {
      need(node.temperature===node.id+'.T','Temperature channel belongs to wrong node');
      observe(node.temperature,'.T','temperature');
    }
    if(node.kind==='body') {
      need(node.energy===node.id+'.dU','Body energy belongs to wrong node');
      observe(node.energy,'.dU','energy');
    }
    if(node.kind==='boundary') {
      need(node.power===node.id+'.Q_to_network','Boundary power belongs to wrong node');
      observe(node.power,'.Q_to_network','boundary power');
    }
    for(const name of [node.temperature,node.energy,node.power].filter(Boolean)) {
      need(!ownerFields.has(name),'Native quantity assigned to multiple owners');
      ownerFields.add(name);
    }
  }
  const edgeIds=new Set();
  for(const edge of edges) {
    keys(edge,['id','from','to','flow'],'edge');
    need(ID.test(edge.id)&&!edgeIds.has(edge.id)&& names.has(edge.from)&&names.has(edge.to)&&
         edge.from!==edge.to, 'Bad rod connection');
    need(!names.has(edge.id),'Rod cannot be a physical node owner');
    edgeIds.add(edge.id);
    need(edge.flow===edge.id+'.Q_flow','Rod flow orientation mismatch');
    need(portOwner.get(edge.id+'.port_a')===edge.from &&
         portOwner.get(edge.id+'.port_b')===edge.to,
         'Rod port_a/port_b connections disagree with signed flow direction');
    observe(edge.flow,'.Q_flow','rod flow');
  }
  for(const port of portOwner.keys())if(port.endsWith('.port_a')||port.endsWith('.port_b')) {
    need(edgeIds.has(port.slice(0,port.lastIndexOf('.'))),
         'Graph contains undeclared native rod endpoint');
  }
  need(required.size===columns.size && [...columns].every(c=>required.has(c)),
       'Unattributed/unsupported sample channel');
  need(Array.isArray(input.samples)&&input.samples.length>=2&&
       input.samples.length<=s.canonicalSamples,'Invalid saved sample selection');
  let previous=-Infinity;
  const step=(a.stop-a.start)/a.intervals;
  for(const row of input.samples) {
    need(Array.isArray(row)&&row.length===input.columns.length&&
         row.every(x=>typeof x==='number'&&Number.isFinite(x)),'Invalid or missing native value');
    const t=row[0], index=Math.round((t-a.start)/step);
    need(index>=0&&index<=a.intervals&&Math.abs(t-(a.start+index*step))<=1e-8*step &&
         t>previous,'Interpolated, duplicate or out-of-order time');
    previous=t;
  }
  need(input.samples[0][0]===a.start && input.samples.at(-1)[0]===a.stop,
       'Missing native time endpoints');
  return {
    ...input,columns:[...input.columns],
    rowObjects:input.samples.map(row=>Object.fromEntries(row.map((v,i)=>[input.columns[i],v])))
  };
}
export function readingsAt(caseData, index) {
  need(Number.isSafeInteger(index)&&index>=0&&index<caseData.rowObjects.length,'Unknown saved sample');
  return caseData.rowObjects[index];
}
export function unitOf(field) {
  if(field.endsWith('.T')||field.endsWith('.T_a')||field.endsWith('.T_b'))return 'K';
  if(field.endsWith('.dU'))return 'J';
  if(field.endsWith('.Q_flow')||field.endsWith('.Q_to_network'))return 'W';
  throw new Error('Unsupported unit');
}
export function signDescription(power) {
  return power>0?'Supplied to network':power<0?'Absorbed from network':'Zero at this sample';
}
export function flowDescription(q, edge) {
  return q>0 ? `${edge.from} → ${edge.to}` : q<0 ? `${edge.to} → ${edge.from}` : 'Zero at this sample';
}
export function firstSignChange(rows, edge) {
  // Zero contact alone is not reversal: require opposite nonzero signs in
  // actually recorded samples, even when zero samples intervene.
  let previous=null;
  for(let i=0;i<rows.length;i++) {
    const sign=Math.sign(rows[i][edge.flow]);
    if(!sign)continue;
    if(previous && previous.sign!==sign)
      return {from:rows[previous.index].time,to:rows[i].time,index:i};
    previous={index:i,sign};
  }
  return null;
}
export function energyTotal(row, nodes) {
  // Display addition of J values only; not a new conservation verdict.
  return nodes.filter(n=>n.kind==='body').reduce((total,n)=>total+row[n.energy],0);
}
export async function hashHex(bytes) {
  if(typeof crypto==='undefined'||!crypto.subtle)throw new Error('HTTPS or localhost required for integrity checks');
  const buffer=await crypto.subtle.digest('SHA-256',bytes);
  return [...new Uint8Array(buffer)].map(x=>x.toString(16).padStart(2,'0')).join('');
}
export async function parseNativeCsv(bytes,caseData) {
  const s=caseData.source;
  need(bytes.byteLength<=20*1024*1024,'Original CSV oversized');
  need(await hashHex(bytes)===s.csvSha256,'Original native CSV SHA-256 mismatch');
  let text;
  try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{throw Error('Non-UTF8 CSV');}
  const lines=text.trimEnd().split(/\r?\n/);
  need(lines.length===s.canonicalSamples+s.duplicateRowsCollapsed+1,'Original CSV sample count mismatch');
  const header=lines[0].split(',');
  need(header.length===new Set(header).size && caseData.columns.every(n=>header.includes(n)),
       'Original CSV channel missing/duplicate');
  const positions=caseData.columns.map(n=>header.indexOf(n));
  const nativeRows=lines.slice(1).map(line=>line.split(','));
  need(nativeRows.every(r=>r.length===header.length),'Truncated native CSV row');
  const last=nativeRows.at(-1),prev=nativeRows.at(-2);
  need(last.every((x,i)=>x===prev[i]),'Nonidentical repeated terminal native row');
  nativeRows.pop();
  const step=(caseData.analysis.stop-caseData.analysis.start)/caseData.analysis.intervals;
  const result=nativeRows.map((row,i)=>{
    const point={};
    for(let j=0;j<positions.length;j++){
      const token=row[positions[j]];
      need(token!=='' && token.trim()===token && Number.isFinite(Number(token)),
           'Missing/nonfinite original number');
      point[caseData.columns[j]]=Number(token);
    }
    need(Math.abs(point.time-(caseData.analysis.start+i*step))<=1e-8*step,
         'Original grid mismatch');
    return point;
  });
  const byTime=new Map(result.map(row=>[row.time,row]));
  for(const point of caseData.rowObjects){
    const real=byTime.get(point.time);
    need(real,'Preview timestamp missing in original native trace');
    for(const name of caseData.columns)need(real[name]===point[name],
         'Preview/native numeric mismatch at '+name);
  }
  return result;
}
