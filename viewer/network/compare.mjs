import {validateIndex,validateCase,hashHex,unitOf} from './core.mjs';
import {validateCompareIndex,compareNativeCases,recordedBodyTemperatureGap} from './compare_core.mjs';

const $=id=>document.getElementById(id);
const NS='http://www.w3.org/2000/svg';
const numeric=(x,d=3)=>Number(x).toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:0});
const showObserved=(value,unit)=>(unit==='K'?'':value>=0?'+':'')+numeric(value,4)+' '+unit;
let index=[],pairs=[],selected=null,inputs=null,field='',selectedTime=0,epoch=0;
function svg(tag,attrs={},txt){const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(txt!==undefined)n.textContent=txt;return n;}
function clear(){
  // Refusal must purge source-linked DOM data, not just hide stale readings.
  // The pair selector remains enabled so a valid pair can be selected again.
  selected=null;inputs=null;field='';selectedTime=0;
  $('inspector').hidden=true;
  $('comparison-chart').replaceChildren();
  $('revision').textContent='No verified comparison selected.';
  for(const id of ['time-label','time-range','sample-count','quantity-description',
                   'gap-label','gap-details','baseline-value','successor-value',
                   'baseline-model','successor-model','chart-title'])
    $(id).textContent='';
  $('baseline-source').replaceChildren();
  $('successor-source').replaceChildren();
  $('time-slider').disabled=true;
  $('time-slider').value='0';
  $('time-slider').max='0';
  $('quantity-select').disabled=true;
  $('quantity-select').replaceChildren();
}
function fail(e){clear();$('error').textContent='Source comparison refused: '+String(e?.message||e);}
function noteSource(id,data){const p=$(id);p.replaceChildren();const link=document.createElement('a');link.href=`https://github.com/physicsvigilante/sim_heat/actions/runs/${data.source.runId}`;link.rel='noopener';link.target='_blank';link.textContent=`OpenModelica run #${data.source.runId}`;const more=document.createElement('p');more.textContent=`Model ${data.modelName} · artifact #${data.source.artifactId} · original ZIP SHA-256 ${data.source.artifactSha256} · original saved CSV SHA-256 ${data.source.csvSha256}`;p.append(link,more);}
async function getJson(url,expected){const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw Error('Source fetch failed: '+url);const bytes=await response.arrayBuffer();if(bytes.byteLength>4_000_000)throw Error('Source file exceeds static viewer limit');if(expected && await hashHex(bytes)!==expected)throw Error('Source case SHA-256 differs from catalog: '+url);return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}
function drawChart(){if(!inputs)return;const observations=inputs.rows.map(x=>[x.time,x.baseline[field],x.successor[field]]);const chart=$('comparison-chart');chart.replaceChildren();const x0=57,x1=856,y0=32,y1=254;const times=observations.map(p=>p[0]);const tmin=times[0],tmax=times.at(-1);const values=observations.flatMap(p=>[p[1],p[2]]);let vmin=Math.min(...values),vmax=Math.max(...values);if(vmax-vmin<1e-10){vmin-=1;vmax+=1;}else{const pad=(vmax-vmin)*.08;vmin-=pad;vmax+=pad;}const xp=t=>x0+(t-tmin)/(tmax-tmin)*(x1-x0),yp=v=>y1-(v-vmin)/(vmax-vmin)*(y1-y0);
  for(let k=0;k<=4;k++){const y=y0+k*(y1-y0)/4;chart.append(svg('line',{x1:x0,y1:y,x2:x1,y2:y,stroke:'#e2eae7','stroke-width':1}));chart.append(svg('text',{x:x0-10,y:y+4,'text-anchor':'end','font-size':12,fill:'#60757a'},numeric(vmax-k*(vmax-vmin)/4,2)));}
  for(let k=0;k<=4;k++){const x=x0+k*(x1-x0)/4;chart.append(svg('text',{x,y:y1+22,'text-anchor':'middle','font-size':12,fill:'#60757a'},numeric(tmin+k*(tmax-tmin)/4,1)+' s'));}
  for(const [j,color] of [[1,'#267e83'],[2,'#bf7b56']]){const path=observations.map((p,i)=>(i?'L':'M')+xp(p[0]).toFixed(2)+','+yp(p[j]).toFixed(2)).join(' ');chart.append(svg('path',{d:path,fill:'none',stroke:color,'stroke-width':3,'stroke-linejoin':'round'}));for(const p of observations)chart.append(svg('circle',{cx:xp(p[0]),cy:yp(p[j]),r:2.8,fill:color}));}
  const point=inputs.rows[selectedTime],x=xp(point.time);chart.append(svg('line',{x1:x,y1:y0,x2:x,y2:y1,stroke:'#485c65','stroke-dasharray':'4,5'}));$('chart-title').textContent=field+' · recorded native '+unitOf(field);
}
function render(){if(!inputs||!selected)return;const entry=inputs.rows[selectedTime];const u=unitOf(field);$('time-label').textContent=numeric(entry.time,2)+' s';$('baseline-value').textContent=showObserved(entry.baseline[field],u);$('successor-value').textContent=showObserved(entry.successor[field],u);$('quantity-description').textContent='Both are original recorded '+u+' values; positive and negative signs retain the native port convention.';
  const g=recordedBodyTemperatureGap(inputs,selectedTime);
  if(g){$('gap-label').textContent=numeric(g.baseline,3)+' K → '+numeric(g.successor,3)+' K';$('gap-details').textContent='Absolute temperature difference between bodies '+g.bodies.join(' and ')+'; only a subtraction of recorded native K values at this saved time.';}
  else{$('gap-label').textContent='Not applicable';$('gap-details').textContent='A two-body temperature separation is not defined for this topology.';}
  drawChart();
}
async function choose(id){const localEpoch=++epoch;clear();$('error').textContent='';$('time-slider').disabled=true;$('quantity-select').disabled=true;const pair=pairs.find(x=>x.id===id);if(!pair)return;try{
    const a=index.find(x=>x.id===pair.baseline),b=index.find(x=>x.id===pair.successor);if(!a||!b)throw Error('Comparison references an absent original case');
    const [rawA,rawB]=await Promise.all([getJson('./'+a.file,a.sha256),getJson('./'+b.file,b.sha256)]);
    if(localEpoch!==epoch)return;
    const baseline=validateCase(rawA,a),successor=validateCase(rawB,b);
    const linked=compareNativeCases(pair,baseline,successor);
    if(localEpoch!==epoch)return;
    selected=pair;inputs=linked;selectedTime=0;field=linked.defaultField;
    const r=pair.revision;$('revision').textContent=`Hypothetical ${r.target}: ${numeric(r.before)} → ${numeric(r.after)} ${r.unit}. ${r.reason}`;
    $('baseline-model').textContent=baseline.modelName+' · '+baseline.source.publicRequestStatus;
    $('successor-model').textContent=successor.modelName+' · '+successor.source.publicRequestStatus;
    noteSource('baseline-source',baseline);noteSource('successor-source',successor);
    $('time-slider').max=String(linked.rows.length-1);$('time-slider').value='0';$('time-slider').disabled=false;
    $('time-range').textContent=`${numeric(linked.rows[0].time)}–${numeric(linked.rows.at(-1).time)} s`;
    $('sample-count').textContent=linked.rows.length+' shared saved preview instants';
    $('quantity-select').replaceChildren();
    for(const key of linked.fields){const option=document.createElement('option');option.value=key;option.textContent=key+' ('+unitOf(key)+')';$('quantity-select').append(option);}
    $('quantity-select').value=field;$('quantity-select').disabled=false;
    $('inspector').hidden=false;render();
  }catch(e){if(localEpoch===epoch)fail(e);}
}
$('time-slider').addEventListener('input',v=>{if(!inputs)return;selectedTime=Number(v.target.value);render();});
$('quantity-select').addEventListener('change',v=>{if(!inputs)return;field=v.target.value;render();});
$('comparison-select').addEventListener('change',e=>choose(e.target.value));
async function start(){try{const [catalog,comparison]=await Promise.all([getJson('./data/index.json'),getJson('./data/compare_index.json')]);index=validateIndex(catalog);pairs=validateCompareIndex(comparison);$('comparison-select').replaceChildren();for(const p of pairs){const option=document.createElement('option');option.value=p.id;option.textContent=p.title;$('comparison-select').append(option);}$('comparison-select').disabled=false;await choose(pairs[0].id);}catch(e){fail(e);}}
start();
