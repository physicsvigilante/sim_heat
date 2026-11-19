import {admitPreview,layoutNodes,selectionValue} from './core.mjs';
import {compareSourcePreviews} from './compare_core.mjs';
const $=id=>document.getElementById(id);
const SVG='http://www.w3.org/2000/svg';
let preview=null;
let baseline=null;
let scenario=null;
let loadVersion=0;
const element=$('element-select');
function svg(tag,attrs={},txt){const e=document.createElementNS(SVG,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(txt!==undefined)e.textContent=String(txt);return e;}
function empty(){preview=null;$('graph').replaceChildren();$('requests').replaceChildren();$('identity').replaceChildren();$('model-assumptions').replaceChildren();$('details').replaceChildren();element.replaceChildren(new Option('Source not loaded',''));element.disabled=true;$('graph-title').textContent='Authored connection graph';$('state').textContent='No admitted source loaded';}
function error(message){baseline=null;scenario=null;clearComparison();empty();$('error').textContent='Refused source preview: '+message;$('error').classList.remove('hidden')}
function fields(el,pairs){el.replaceChildren();for(const [k,v] of pairs){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=String(v);el.append(dt,dd)}}
function choose(value){
  if(!preview)return;
  const componentId=value.startsWith('component:')?value.slice('component:'.length):null;
  const nodeId=value.startsWith('node:')?value.slice('node:'.length):null;
  const comp=componentId===null?null:preview.components.find(c=>c.id===componentId);
  const node=nodeId===null?null:preview.nodes.find(n=>n.id===nodeId);
  const rod=comp?preview.rods.find(r=>r.id===comp.id):null;
  let pairs=[];
  if(comp){
    pairs=[['Component',comp.id],['Source kind',comp.kind],
      ...comp.inputs.map(f=>[f.name+' (source SI)',f.sourceValue+' '+f.siUnit]),
      ...comp.sourceProvenance.map(p=>['Input attribution: '+p.appliesTo.join(', '),
        (p.target===p.appliesTo[0]?'':'via original parameter '+p.target+' · ')+p.kind+' · '+p.locator+' · '+p.note]),
      ...comp.componentProvenance.map(p=>['Component assumption · '+p.kind,
        'Original target '+p.target+' · '+p.locator+' · '+p.note])];
    if(rod)pairs.push(['Authored endpoints',rod.portA+' ↔ '+rod.portB]);
  }else if(node){
    pairs=[['Graph node',node.id],['Source role',node.role],
      ['Owner',node.owner||'Ownerless ideal junction'],['Connected ports',node.ports.join(', ')]];
  }else pairs=[['Selection','No matching source object']];
  fields($('details'),pairs);
  $('graph').querySelectorAll('.rod').forEach(e=>e.classList.toggle('selected',
    componentId!==null&&e.dataset.rod===componentId));
}
function openChoice(kind,id){const v=selectionValue(kind,id);element.value=v;choose(v)}
function render(payload){const p=admitPreview(payload);empty();preview=p;$('error').classList.add('hidden');$('state').textContent='Admitted source only · nativeExecuted=false';$('graph-title').textContent=p.modelName+' · '+p.mode+' composition';
  const points=layoutNodes(p.nodes),svgRoot=$('graph');
  for(const r of p.rods){const a=points.get(r.from),b=points.get(r.to);const g=svg('g',{tabindex:'0',role:'button','aria-label':'Inspect authored rod '+r.id,class:'selectable'}),line=svg('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:'rod','data-rod':r.id}),hit=svg('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:'rod-hit'});g.append(line,hit);const select=()=>openChoice('component',r.id);g.addEventListener('click',select);g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select()}});svgRoot.append(g);const mx=(a.x+b.x)/2,my=(a.y+b.y)/2;svgRoot.append(svg('text',{x:mx,y:my-9,class:'line-label'},r.id));}
  for(const n of p.nodes){const {x,y}=points.get(n.id),g=svg('g',{tabindex:'0',role:'button','aria-label':'Inspect source node '+n.label,class:'selectable'});g.append(svg('circle',{cx:x,cy:y,r:35,class:'component-node '+(n.role==='boundary'?'boundary':n.role==='junction'?'junction':'body')}));g.append(svg('text',{x,y:y-3,class:'node-title'},n.label.length>14?n.label.slice(0,13)+'…':n.label));g.append(svg('text',{x,y:y+16,class:'node-role'},n.role));const select=()=>openChoice('node',n.id);g.addEventListener('click',select);g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select()}});svgRoot.append(g)}
  element.replaceChildren();for(const c of p.components)element.add(new Option(c.id+' · '+c.kind,selectionValue('component',c.id)));for(const n of p.nodes)element.add(new Option(n.label+' · logical node',selectionValue('node',n.id)));element.disabled=false;choose(element.value);
  for(const r of p.requests){const d=document.createElement('div');d.className='request';const t=document.createElement('strong');t.textContent=r.id+' · '+r.operation+' ('+r.unit+')';const s=document.createElement('span');s.textContent=r.targets.join(' → ')+' · not_computed';d.append(t,s);$('requests').append(d)}
  fields($('model-assumptions'),p.modelProvenance.map(r=>
    ['Original @model assumption · '+r.kind,r.locator+' · '+r.note]));
  fields($('identity'),[['Study ID',p.studyId],['Model name',p.modelName],['Study SHA-256',p.source.studySha256],['Model SHA-256',p.source.modelSha256],['Evidence kind',p.source.evidenceKind],['Public requests',p.source.publicRequestStatus],['Native execution','false'],['Native qualification','false'],['Source fidelity qualification','false']]);
}
function clearComparison(){
  $('comparison-changes').replaceChildren();
  $('comparison-identity').textContent='';
  $('comparison-state').textContent='No second admitted source loaded.';
  $('comparison-error').textContent='';
  $('comparison-error').classList.add('hidden');
  $('view-baseline').disabled=true;
  $('view-variant').disabled=true;
}
function showComparison(){
  $('comparison-changes').replaceChildren();
  if(!baseline||!scenario){clearComparison();return;}
  const compared=compareSourcePreviews(baseline,scenario);
  $('comparison-error').classList.add('hidden');
  $('comparison-state').textContent=compared.changes.length+' authored source difference(s) · no computed values';
  $('comparison-identity').textContent='Baseline '+compared.baseline.studyId+' ('+
    compared.baseline.studySha256+') · Scenario '+compared.variant.studyId+' ('+
    compared.variant.studySha256+')';
  $('view-baseline').disabled=false;
  $('view-variant').disabled=false;
  if(!compared.changes.length){
    const p=document.createElement('p');p.textContent='No differences found in admitted display fields.';
    $('comparison-changes').append(p);
  }
  for(const change of compared.changes){
    const item=document.createElement('div'),heading=document.createElement('strong');
    const from=document.createElement('p'),to=document.createElement('p');
    item.className='compare-item';heading.textContent=change.category+' · '+change.label;
    from.textContent='Baseline: '+change.from;to.textContent='Scenario: '+change.to;
    item.append(heading,from,to);$('comparison-changes').append(item);
  }
}
function compareError(message){
  const staleScenarioDisplayed=preview !== null && preview === scenario;
  scenario=null;clearComparison();
  // A refused replacement must not leave an older scenario's visible graph,
  // request labels and assumed inputs looking like the refused candidate.
  if(staleScenarioDisplayed && baseline)render(baseline);
  $('comparison-error').textContent='Refused source comparison: '+message;
  $('comparison-error').classList.remove('hidden');
  $('comparison-state').textContent='Scenario refused · no comparison shown';
}
function setScenario(value){
  const candidate=admitPreview(value);
  compareSourcePreviews(baseline,candidate); // refuse contradictory claimed hashes
  scenario=candidate;showComparison();
}
$('view-baseline').addEventListener('click',()=>{if(baseline)render(baseline)});
$('view-variant').addEventListener('click',()=>{if(scenario)render(scenario)});
$('variant-import').addEventListener('change',async e=>{
  const file=e.target.files?.[0];if(!file)return;
  const expected=loadVersion;
  try{
    if(file.size>524288)throw Error('file exceeds 512 KiB source-only display limit');
    const raw=await file.text();
    if(expected===loadVersion&&baseline)setScenario(JSON.parse(raw));
  }catch(err){if(expected===loadVersion)compareError(err.message)}
  finally{e.target.value=''}
});
element.addEventListener('change',()=>choose(element.value));
$('import').addEventListener('change',async e=>{
  const f=e.target.files?.[0];if(!f)return;
  const current=++loadVersion;
  scenario=null;clearComparison();baseline=null;empty();$('error').classList.add('hidden');$('state').textContent='Checking selected source-only file…';
  try{
    if(f.size>524288)throw Error('file exceeds the 512 KiB preview limit');
    const raw=await f.text();
    if(current===loadVersion){const value=admitPreview(JSON.parse(raw));baseline=value;render(value);}
  }catch(err){if(current===loadVersion)error(err.message)}
  finally{e.target.value=''}
});
const initial=++loadVersion;
try{
  const response=await fetch('./data/TEACH_SPLIT3.json',{cache:'no-store'});
  if(!response.ok)throw Error('default demonstration unavailable');
  const payload=await response.json();
  if(initial===loadVersion){
    baseline=admitPreview(payload);render(baseline);
    // Only a local H1 workbench with --compare serves this additional route.
    // Static preview hosting returns 404; that is not a comparison error.
    const response2=await fetch('./data/VARIANT.json',{cache:'no-store'});
    if(response2.ok){
      const candidate=await response2.json();
      if(initial===loadVersion)setScenario(candidate);
    }else if(response2.status!==404)throw Error('scenario source route unavailable');
  }
}catch(err){if(initial===loadVersion){if(baseline)compareError(err.message);else error(err.message)}}
