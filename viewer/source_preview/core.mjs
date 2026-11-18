/** Only admitted H1 source metadata. These guards DO NOT authenticate an uploaded file. */
const has = (o,k) => Object.prototype.hasOwnProperty.call(o,k);
const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const keys = (o,names) => object(o) && Object.keys(o).length === names.length && names.every(n=>has(o,n));
const name = s => typeof s === 'string' && /^[A-Za-z][A-Za-z0-9_]*$/.test(s);
const hex = s => typeof s === 'string' && /^[0-9a-f]{64}$/.test(s);
const nonempty = s => typeof s === 'string' && s.trim().length > 0;
const unit = new Map([
  ['Mass','kg'],['SpecificHeatCapacity','J/(kg K)'],['Temperature','K'],
  ['ThermalConductivity','W/(m K)'],['Length','m'],['Area','m2'],
]);
const slots={Body:{m:'Mass',c:'SpecificHeatCapacity',T_initial:'Temperature'},
  FixedTemperature:{T:'Temperature'},
  RodArea:{k:'ThermalConductivity',L:'Length',A:'Area'},
  RodCircular:{k:'ThermalConductivity',L:'Length',d:'Length'}};
const ops={temperature:'K',temperatureDifference:'K',heatFlow:'W',energyChange:'J'};
const provenanceKinds=new Set(['source_given','source_diagram','solution_assumption',
  'adopted_assumption','unit_convention','illustrative']);
// A legal authored component may be named 'node_0'. Selection must never
// depend on component and generated node IDs sharing one string namespace.
export function selectionValue(kind,id){
  if(!['component','node'].includes(kind)||!name(id))refuse('invalid selection');
  return kind+':'+id;
}
function refuse(reason){throw Error('SOURCE PREVIEW REFUSED: '+reason)}
export function admitPreview(value){
  if(!keys(value,['schema','status','studyId','modelName','mode','source','components','nodes','rods','requests','modelProvenance','disclaimers']) ||
     value.schema !== 'sim_heat.viewer.admitted_source/1' || value.status !== 'admitted_source_only' ||
     !name(value.studyId) || !name(value.modelName) || !['transient','steady'].includes(value.mode)) refuse('invalid envelope');
  const s=value.source;
  if(!keys(s,['studySha256','modelSha256','evidenceKind','nativeExecuted','nativeQualified','sourceFidelityQualified','publicRequestStatus']) ||
     !hex(s.studySha256) || !hex(s.modelSha256) || s.evidenceKind!=='authored_source_only' ||
     s.nativeExecuted!==false || s.nativeQualified!==false || s.sourceFidelityQualified!==false ||
     s.publicRequestStatus!=='not_computed') refuse('source cannot claim physical results or qualification');
  if(!Array.isArray(value.components)||!Array.isArray(value.nodes)||!Array.isArray(value.rods)||!Array.isArray(value.requests)||
     !Array.isArray(value.modelProvenance)||!Array.isArray(value.disclaimers) ||
     value.components.length<1 || value.components.length>48 || value.nodes.length>64 || value.rods.length>32 || value.requests.length>32 ||
     value.disclaimers.length<4 || value.disclaimers.some(x=>!nonempty(x))) refuse('invalid resource lists');
  const components = new Map();
  const portSet = new Set();
  for(const c of value.components){
    if(!keys(c,['id','kind','inputs','sourceProvenance','componentProvenance'])||
       !name(c.id)||!has(slots,c.kind)||components.has(c.id)||
       !Array.isArray(c.inputs)||!Array.isArray(c.sourceProvenance)||
       !Array.isArray(c.componentProvenance)) refuse('invalid component');
    components.set(c.id,c);
    if(c.kind==='Body'||c.kind==='FixedTemperature')portSet.add(c.id+'.port');
    else {portSet.add(c.id+'.port_a');portSet.add(c.id+'.port_b')}
    const expected=slots[c.kind];
    if(c.inputs.length!==Object.keys(expected).length)refuse('incomplete component source facts');
    const inputNames=new Set();
    for(const v of c.inputs){
      if(!keys(v,['name','quantityType','siUnit','sourceValue']) || !has(expected,v.name) || inputNames.has(v.name) ||
         expected[v.name]!==v.quantityType || unit.get(v.quantityType)!==v.siUnit ||
         typeof v.sourceValue !== 'number' || !Number.isFinite(v.sourceValue) || !(v.sourceValue>0)) refuse('invalid authored input');
      inputNames.add(v.name);
    }
    const pnames=new Set();
    for(const p of c.sourceProvenance){
      if(!keys(p,['target','kind','locator','note','appliesTo'])||!name(p.target.split('.')[0])||
         !provenanceKinds.has(p.kind)||!nonempty(p.locator)||!nonempty(p.note)||
         !Array.isArray(p.appliesTo)||p.appliesTo.length<1||p.appliesTo.length>c.inputs.length||
         new Set(p.appliesTo).size!==p.appliesTo.length)refuse('invalid source attribution');
      for(const effective of p.appliesTo){
        if(!c.inputs.some(v=>effective===c.id+'.'+v.name) ||
           !(p.target===effective || name(p.target)))refuse('invalid attributed input');
        // Multiple *different* original records may justify the same field,
        // e.g. both source_given and unit_convention for S1.copper.k.
        pnames.add(effective);
      }
    }
    if(pnames.size!==c.inputs.length)refuse('missing source provenance');
    for(const p of c.componentProvenance){
      // Never reinterpret a whole-component modeling assumption as a
      // source-given scalar input or silently discard its original target.
      if(!keys(p,['target','kind','locator','note'])||p.target!==c.id||
         !provenanceKinds.has(p.kind)||!nonempty(p.locator)||!nonempty(p.note))
        refuse('invalid component assumption');
    }
  }
  if(value.modelProvenance.length<1||value.modelProvenance.some(p=>
      !keys(p,['target','kind','locator','note'])||p.target!=='@model'||
      !provenanceKinds.has(p.kind)||!nonempty(p.locator)||!nonempty(p.note))||
      !value.modelProvenance.some(p=>['adopted_assumption','solution_assumption'].includes(p.kind))) refuse('missing model provenance');
  const nodes=new Map(),owners=new Set(),allPorts=new Set();
  for(const node of value.nodes){
    if(!keys(node,['id','ports','owner','role','label'])||!/^node_\d+$/.test(node.id)||nodes.has(node.id)||
       !Array.isArray(node.ports)||!node.ports.length||!['junction','body','boundary'].includes(node.role)||!nonempty(node.label))refuse('invalid graph node');
    if(node.owner===null){if(node.role!=='junction')refuse('junction role mismatch')}
    else{
      if(!components.has(node.owner)||owners.has(node.owner)||node.label!==node.owner)refuse('invalid graph owner');
      const expectedRole=components.get(node.owner).kind==='Body'?'body':'boundary';
      if(node.role!==expectedRole||!node.ports.includes(node.owner+'.port'))refuse('invalid owner node role');
      owners.add(node.owner);
    }
    for(const p of node.ports){if(!portSet.has(p)||allPorts.has(p))refuse('unknown or duplicate port');allPorts.add(p)}
    nodes.set(node.id,node);
  }
  if(allPorts.size!==portSet.size)refuse('incomplete graph ports');
  const rods=new Set();
  for(const r of value.rods){
    if(!keys(r,['id','from','to','portA','portB']) || !components.has(r.id)||!components.get(r.id).kind.startsWith('Rod')||
       rods.has(r.id)||!nodes.has(r.from)||!nodes.has(r.to)||r.from===r.to||
       r.portA!==r.id+'.port_a'||r.portB!==r.id+'.port_b'||
       !nodes.get(r.from).ports.includes(r.portA)||!nodes.get(r.to).ports.includes(r.portB))refuse('invalid rod topology');
    rods.add(r.id);
  }
  if(rods.size!==[...components.values()].filter(c=>c.kind.startsWith('Rod')).length)refuse('missing rods');
  const bodies=[...components.values()].filter(c=>c.kind==='Body').length;
  const boundaries=[...components.values()].filter(c=>c.kind==='FixedTemperature').length;
  if(value.nodes.filter(n=>n.role==='body').length!==bodies||
     value.nodes.filter(n=>n.role==='boundary').length!==boundaries)refuse('missing body/boundary node');
  // Mirror the H1 steady/transient component-mode envelope. This checks only
  // caller-supplied metadata consistency, not physical correctness or source custody.
  if(value.mode==='steady' ? bodies!==0||rods.size===0||boundaries===0 : bodies===0)
    refuse('incompatible H1 source mode');
  const ids=new Set();
  for(const r of value.requests){
    if(!keys(r,['id','operation','targets','unit','status']) || !name(r.id)||ids.has(r.id)||!has(ops,r.operation)||
       r.unit!==ops[r.operation]||r.status!=='not_computed'||!Array.isArray(r.targets)||
       r.targets.length!==(r.operation==='temperatureDifference'?2:1))refuse('invalid request status');
    ids.add(r.id);
    const ok=r.operation==='temperature'||r.operation==='temperatureDifference' ? r.targets.every(p=>portSet.has(p)) :
      r.operation==='heatFlow' ? r.targets.length===1 && rods.has(r.targets[0]) :
      r.targets.length===1 && components.get(r.targets[0])?.kind==='Body';
    if(!ok)refuse('request target does not exist');
  }
  // This is structural consistency of caller-supplied source-only data, not signature verification.
  return value;
}
export function layoutNodes(nodes){
  const size=nodes.length;
  return new Map(nodes.map((n,i)=>[n.id,{x:340+220*Math.cos(-Math.PI/2+2*Math.PI*i/size),
    y:230+148*Math.sin(-Math.PI/2+2*Math.PI*i/size)}]));
}
