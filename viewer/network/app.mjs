// Generic graph + reading renderer. No model/case-specific names or physics.
import {validateIndex,validateCase,readingsAt,unitOf,signDescription,flowDescription,
        firstSignChange,energyTotal,hashHex,parseNativeCsv} from './core.mjs';
const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
let catalog=[],current=null,rows=[],selected=0,chosen=null,timer=null,markTemperature=()=>{},markObservation=()=>{};
let caseEpoch=0,importEpoch=0; // invalidates asynchronous case loads and native imports
const fmt=(n,d=2)=>Number(n).toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d});
const signed=(n,d=2)=>(n>0?'+':'')+fmt(n,d);
function make(tag,attrs={},txt){const el=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))el.setAttribute(k,String(v));if(txt!==undefined)el.textContent=txt;return el;}
function clearEvidence(){
  stop();current=null;rows=[];selected=0;chosen=null;
  markTemperature=()=>{};markObservation=()=>{};
  for(const id of ['time-slider','play','reset','reversal','observation','native-import'])$(id).disabled=true;
  $('time-slider').min='0';$('time-slider').max='0';$('time-slider').value='0';
  for(const id of ['network','temperature-chart','observation-chart',
    'temp-legend','energy-readouts','observation'])$(id).replaceChildren();
  for(const id of ['graph-count','time-label','time-start','time-stop','field-unit',
    'current-value','current-direction','model-id','native-run','check-count','csv-sha'])$(id).textContent='—';
  for(const id of ['reversal-note','field-title','selection-description','import-description',
    'import-status'])$(id).textContent='No verified evidence available';
  $('sample-note').textContent='No evidence displayed';
  $('native-run').removeAttribute('href');
  $('import-status').className='help';$('native-import').value='';
}
function err(message){clearEvidence();$('error').textContent='Evidence refused: '+message;$('error').classList.add('active');}
function ok(){ $('error').textContent='';$('error').classList.remove('active'); }
function stop(){if(timer){clearInterval(timer);timer=null;}$('play').textContent='▶ Play';}
async function getJSON(url,expected){const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error('Missing data '+url);const bytes=await response.arrayBuffer();if(expected && await hashHex(bytes)!==expected)throw new Error('Case digest differs from source catalog');return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}
function availableFields(bundle){const result=[];for(const n of bundle.graph.nodes){result.push({field:n.temperature,label:n.id+' · temperature',owner:n.id,kind:'temperature'});if(n.energy)result.push({field:n.energy,label:n.id+' · stored energy ΔU',owner:n.id,kind:'energy'});if(n.power)result.push({field:n.power,label:n.id+' · signed boundary power',owner:n.id,kind:'power'});}for(const e of bundle.graph.edges)result.push({field:e.flow,label:e.id+' · signed rod flow',owner:e.id,kind:'flow',edge:e});return result;}
function pos(i,total){if(total===2)return {x:i===0?210:580,y:180};const ang=(2*Math.PI*i/total)-Math.PI/2;return{x:390+Math.cos(ang)*251,y:182+Math.sin(ang)*124};}
function describeFlow(e,q){return `${signed(q,Math.abs(q)<.03?4:2)} W · ${flowDescription(q,e)}`;}
function network(bundle,row){const svg=$('network');svg.replaceChildren();const nodes=bundle.graph.nodes;const positions=Object.fromEntries(nodes.map((n,i)=>[n.id,pos(i,nodes.length)]));
for(const edge of bundle.graph.edges){const a=positions[edge.from],b=positions[edge.to],q=row[edge.flow];const selectedEdge=chosen?.edge?.id===edge.id;const dx=b.x-a.x,dy=b.y-a.y,dist=Math.hypot(dx,dy)||1,ux=dx/dist,uy=dy/dist;const begin={x:a.x+ux*59,y:a.y+uy*59},end={x:b.x-ux*59,y:b.y-uy*59};const line=make('line',{x1:begin.x,y1:begin.y,x2:end.x,y2:end.y,class:'edge'+(selectedEdge?' select':'')});svg.append(line);const button=make('line',{x1:begin.x,y1:begin.y,x2:end.x,y2:end.y,stroke:'transparent','stroke-width':22,role:'button',tabindex:0,'aria-label':`Select rod ${edge.id}: ${describeFlow(edge,q)}`,class:'edge-button'});const activate=()=>{$('observation').value=edge.flow;chooseField(edge.flow)};button.addEventListener('click',activate);button.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();activate();}});svg.append(button);
const mx=(begin.x+end.x)/2,my=(begin.y+end.y)/2;if(q!==0){const angle=Math.atan2(dy,dx)+(q<0?Math.PI:0);const p=make('path',{d:'M 11 0 L -9 -6 L -9 6 Z',transform:`translate(${mx} ${my}) rotate(${angle*180/Math.PI})`,class:'arrow'+(q<0?' negative':'')});svg.append(p);}svg.append(make('text',{x:mx,y:my-13,class:'edge-amount'},`${edge.id}: ${signed(q,Math.abs(q)<.02?4:2)} W`));}
for(const n of nodes){const p=positions[n.id],g=make('g',{class:'node-button',role:'button',tabindex:0,'aria-label':'Select '+n.kind+' '+n.id});const shape=make('circle',{cx:p.x,cy:p.y,r:47,class:'node-shape '+n.kind});if(n.kind==='boundary'){shape.setAttribute('r','48');}g.append(shape);g.append(make('text',{x:p.x,y:p.y-6,class:'node-label'},n.id.length>12?n.id.slice(0,11)+'…':n.id));g.append(make('text',{x:p.x,y:p.y+14,class:'node-kind'},fmt(row[n.temperature],2)+' K'));const activate=()=>{$('observation').value=n.temperature;chooseField(n.temperature)};g.addEventListener('click',activate);g.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();activate();}});svg.append(g);}
$('graph-count').textContent=nodes.length+' nodes · '+bundle.graph.edges.length+' rods';}
function chart(id,series,values,height,zero=false){const target=$(id);target.replaceChildren();if(!series.length||!values.length)return()=>{};const box=id==='temperature-chart'?{w:790,h:262}:{w:490,h:205},left=54,right=box.w-17,top=17,bottom=box.h-30;let min=Math.min(...values.flatMap(r=>series.map(s=>r[s.field]))),max=Math.max(...values.flatMap(r=>series.map(s=>r[s.field])));if(zero){min=Math.min(min,0);max=Math.max(max,0);}if(min===max){min-=1;max+=1;}const pad=(max-min)*.1;min-=pad;max+=pad;const first=values[0].time,last=values.at(-1).time,x=t=>left+(t-first)/(last-first)*(right-left),y=v=>bottom-(v-min)/(max-min)*(bottom-top);
for(let i=0;i<=4;i++){const yy=top+(bottom-top)*i/4;target.append(make('line',{x1:left,x2:right,y1:yy,y2:yy,stroke:'#e2e9e4'}));target.append(make('text',{x:left-8,y:yy+4,'text-anchor':'end','font-size':11,fill:'#80928e'},fmt(max-i*(max-min)/4,1)));target.append(make('text',{x:left+(right-left)*i/4,y:box.h-7,'text-anchor':'middle','font-size':10,fill:'#819694'},fmt(first+(last-first)*i/4,0)));}if(zero&&min<0&&max>0)target.append(make('line',{x1:left,x2:right,y1:y(0),y2:y(0),stroke:'#ba7770','stroke-dasharray':'4 4'}));
for(const s of series){const path=values.map((r,i)=>(i?'L':'M')+x(r.time).toFixed(3)+' '+y(r[s.field]).toFixed(3)).join(' ');target.append(make('path',{d:path,stroke:s.color,fill:'none','stroke-width':2.4,'stroke-linejoin':'round'}));}const cursor=make('line',{x1:left,x2:left,y1:top,y2:bottom,stroke:'#477a7e','stroke-dasharray':'4 4'});target.append(cursor);const dots=series.map(s=>{const circ=make('circle',{r:4,fill:s.color,cx:left,cy:top});target.append(circ);return circ;});return i=>{const row=values[i];if(!row)return;const xx=x(row.time);cursor.setAttribute('x1',xx);cursor.setAttribute('x2',xx);series.forEach((s,j)=>{dots[j].setAttribute('cx',xx);dots[j].setAttribute('cy',y(row[s.field]));});};}
function chooseField(field){if(!current)return;const all=availableFields(current);const item=all.find(f=>f.field===field);if(!item)throw new Error('Unsupported selected observation');chosen=item;$('observation').value=field;$('field-unit').textContent=unitOf(field);$('field-title').textContent=item.label;$('selection-description').textContent=item.kind==='flow'?'Rod power is signed from port_a to port_b; the arrow reverses for negative values.':item.kind==='power'?'Signed boundary power: + supplied to network; − absorbed from network.':item.kind==='energy'?'Cumulative stored-energy change from the stated initial body temperature.':'Native temperature, not inferred from the illustrative network geometry.';markObservation=chart('observation-chart',[{field:item.field,color:item.kind==='temperature'?'#3e9890':'#b67b5e'}],rows,205,item.kind==='flow'||item.kind==='power');draw();}
function draw(){if(!current||!rows.length)return;const row=readingsAt({...current,rowObjects:rows},selected);$('time-slider').value=String(selected);$('time-label').textContent=fmt(row.time,6)+' s';network(current,row);const q=row[chosen.field],u=unitOf(chosen.field);$('current-value').textContent=signed(q,Math.abs(q)<.03?4:2)+' '+u;$('current-direction').textContent=chosen.edge?flowDescription(q,chosen.edge):chosen.kind==='power'?signDescription(q):'';const out=$('energy-readouts');out.replaceChildren();for(const n of current.graph.nodes){let field=n.energy||n.power;if(!field)continue;const tile=document.createElement('div');tile.className='record-field';const name=document.createElement('small');name.textContent=n.id+(n.energy?' · ΔU':' · power');const value=document.createElement('strong');value.textContent=signed(row[field])+' '+unitOf(field);tile.append(name,value);if(n.power){const text=document.createElement('em');text.textContent=signDescription(row[field]);tile.append(text);}out.append(tile);}const bodies=current.graph.nodes.filter(n=>n.kind==='body');if(bodies.length){const tile=document.createElement('div');tile.className='record-field span';const small=document.createElement('small');small.textContent='Combined body ΔU (J only)';const strong=document.createElement('strong');strong.textContent=signed(energyTotal(row,current.graph.nodes))+' J';tile.append(small,strong);out.append(tile);}markTemperature(selected);markObservation(selected);}
function setSample(i){selected=Math.max(0,Math.min(rows.length-1,i));draw();}
function updateRows(full,mode){stop();rows=full;selected=0;$('time-slider').max=String(rows.length-1);$('time-slider').disabled=false;for(const id of ['play','reset','observation','native-import'])$(id).disabled=false;$('sample-note').textContent=rows.length+' saved points displayed of '+current.source.canonicalSamples+' canonical native samples · '+mode;$('time-start').textContent=fmt(current.analysis.start,0)+' s';$('time-stop').textContent=fmt(current.analysis.stop,0)+' s';const flags=current.graph.edges.map(edge=>({edge,cross:firstSignChange(rows,edge)})).filter(r=>r.cross);$('reversal').disabled=!flags.length;$('reversal-note').textContent=flags.length?flags.map(r=>`${r.edge.id}: sign change bracket ${fmt(r.cross.from,1)} to ${fmt(r.cross.to,1)} s`).join(' · '):'No signed rod reversal among the displayed saved samples.';
const palette=['#c87857','#368e85','#678ab4','#9b7da3','#7c967a','#bd9d53'];const series=current.graph.nodes.map((n,i)=>({field:n.temperature,color:palette[i%palette.length],label:n.id}));const legend=$('temp-legend');legend.replaceChildren();series.forEach(s=>{const span=document.createElement('span'),bar=document.createElement('i');bar.className='line-icon';bar.style.background=s.color;span.append(bar,document.createTextNode(s.label));legend.append(span);});markTemperature=chart('temperature-chart',series,rows,262);chooseField(chosen?.field||current.graph.edges[0]?.flow||current.graph.nodes[0].temperature);setSample(0);}
async function switchCase(entry){
  // An older request cannot re-populate the new case or re-label its source.
  const generation=++caseEpoch;++importEpoch;
  clearEvidence();ok();$('sample-note').textContent='Loading source-linked case…';
  $('case-select').disabled=true;
  try{
    const source=await getJSON(entry.file,entry.sha256);
    if(generation!==caseEpoch)return;
    const parsed=validateCase(source,entry);
    if(generation!==caseEpoch)return;
    current=parsed;chosen=null;
    const selector=$('observation');
    for(const item of availableFields(parsed)){
      const option=document.createElement('option');
      option.value=item.field;option.textContent=item.label+' ('+unitOf(item.field)+')';
      selector.append(option);
    }
    $('model-id').textContent=parsed.modelName;
    $('native-run').textContent='#'+parsed.source.runId;
    $('native-run').href='https://github.com/physicsvigilante/sim_heat/actions/runs/'+parsed.source.runId;
    $('check-count').textContent=parsed.source.checksPassed+' passed; diagnostic_only';
    $('csv-sha').textContent=parsed.source.csvSha256.slice(0,20)+'…';
    $('import-description').textContent=`Original ${parsed.source.canonicalSamples.toLocaleString('en-US')} native samples: download case file ${parsed.source.archiveEntry} from artifact #${parsed.source.artifactId}, and import only the exact original CSV verified by SHA-256.`;
    $('import-status').textContent='No import yet. Source file stays in this browser.';
    updateRows(parsed.rowObjects,'source-bundled preview');
  }catch(e){if(generation===caseEpoch)err(e.message);}
  finally{if(generation===caseEpoch)$('case-select').disabled=false;}
}
$('case-select').addEventListener('change',()=>{const entry=catalog.find(x=>x.id===$('case-select').value);if(entry)switchCase(entry);});$('observation').addEventListener('change',()=>chooseField($('observation').value));$('time-slider').addEventListener('input',()=>{stop();setSample(Number($('time-slider').value));});$('reset').addEventListener('click',()=>{stop();setSample(0);});$('play').addEventListener('click',()=>{if(timer){stop();return;}if(selected===rows.length-1)setSample(0);$('play').textContent='Ⅱ Pause';const stride=Math.max(1,Math.floor(rows.length/320));timer=setInterval(()=>{setSample(Math.min(selected+stride,rows.length-1));if(selected>=rows.length-1)stop();},90);});$('reversal').addEventListener('click',()=>{stop();for(const edge of current.graph.edges){const b=firstSignChange(rows,edge);if(b){chooseField(edge.flow);setSample(b.index);return;}}});
$('native-import').addEventListener('change',async e=>{
  stop();const file=e.target.files?.[0];if(!file||!current)return;
  const generation=caseEpoch,request=++importEpoch,sourceCase=current;
  const stillSelected=()=>generation===caseEpoch && request===importEpoch && current===sourceCase;
  try{
    if(file.size>20*1024*1024)throw Error('Native CSV exceeds size limit');
    const bytes=await file.arrayBuffer();
    if(!stillSelected())return;
    const saved=await parseNativeCsv(bytes,sourceCase);
    if(!stillSelected())return;
    updateRows(saved,'SHA-256 verified full native CSV');
    $('import-status').className='help good';
    $('import-status').textContent='Exact native CSV verified; all '+saved.length+' saved samples are available.';
  }catch(ex){
    if(stillSelected()){
      $('import-status').className='help bad';
      $('import-status').textContent='File refused: '+ex.message;
    }
  }finally{if(request===importEpoch)e.target.value='';}
});
async function start(){try{const index=await getJSON('data/index.json');catalog=validateIndex(index);const select=$('case-select');select.replaceChildren();for(const c of catalog){const opt=document.createElement('option');opt.value=c.id;opt.textContent=c.title;select.append(opt);}select.disabled=false;await switchCase(catalog[0]);}catch(ex){++caseEpoch;++importEpoch;err(ex.message);$('case-select').disabled=true;}}start();
